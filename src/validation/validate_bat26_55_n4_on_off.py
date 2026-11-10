"""N4 comparison of the same PV/GFM microgrid with Leaf pack ON and OFF."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import numpy as np
import scipy
from scipy.integrate import solve_ivp

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bess.leaf_48module_pack import Leaf48ModulePack
from config import MICROGRID_TEMPERATURE_C_DEFAULT
from controllers.gfm_controller import GFMController
from microgrid import Microgrid, MicrogridWithBESS
from validation.validate_bat26_55_n1_profile import (
    ATOL, D, ETA_DCDC, MAX_STEP_S, M, P_REF_W, QEFF_AH, RTOL,
    SAMPLE_DT_S, SOC0, T_END_S, build_battery, fixture_parameters,
    irradiance_profile, load_profile,
)

BLOCKED_OUTPUT = ROOT / "outputs" / "validation" / "bat26_55_n4_on_off.json"
OUTPUT = ROOT / "outputs" / "validation" / "bat26_55_n4_pre_uvlo.json"
LOG = ROOT / "outputs" / "validation" / "bat26_55_n4_performance.log"
VDC_REF_V = 340.0
PRE_UVLO_EVENT_V = 201.0
FALLBACK_HORIZON_S = 0.85
OFF_EVENT_TIMEOUT_S = 60.0
CASE_TIMEOUT_S = 90.0
TRANSIENT_SKIP_S = 0.05
EVAL_TIMES = np.linspace(0.0, T_END_S, round(T_END_S / SAMPLE_DT_S) + 1)
STAGES = {
    "preconditioning": (0.0, 0.4),
    "solar_surplus_steady": (0.45, 0.8),
    "solar_surplus_transition": (0.4, 0.45),
    "load_deficit_steady": (0.85, 1.2),
    "load_deficit_transition": (0.8, 0.85),
}


def make_pair():
    controller_off = GFMController(p_ref=P_REF_W, inertia_m=M, damping_d=D)
    controller_on = GFMController(p_ref=P_REF_W, inertia_m=M, damping_d=D)
    temperature = lambda _t: MICROGRID_TEMPERATURE_C_DEFAULT
    common = {"irradiance_profile": irradiance_profile,
              "temperature_profile": temperature, "load_profile": load_profile}
    off = Microgrid(**common, controller=controller_off)
    pack = Leaf48ModulePack(q_init_case_ah=QEFF_AH)
    snapshot = pack.capacity()
    on = MicrogridWithBESS(
        **common, controller=controller_on, bess_model=build_battery(QEFF_AH),
        leaf_pack=pack, dcdc_parameters=fixture_parameters(pack),
        capacity_snapshot=snapshot, aging_mode="blast", blast_profile_kind="synthetic",
    )
    x_off = np.asarray(off.initial_state(), dtype=float)
    x_on = np.asarray(on.initial_state_with_bess(), dtype=float)
    if x_off.shape != (12,) or x_on.shape != (15,):
        raise AssertionError(f"Protected state sizes differ: OFF={x_off.shape}, ON={x_on.shape}")
    if not np.array_equal(x_off, x_on[:12]):
        raise AssertionError("The first 12 initial states are not exactly equal")
    if x_on[12] != SOC0 or x_on[14] != 0.0:
        raise AssertionError("Unexpected ON battery initial state")

    c_off, c_on = off.controller, on.controller
    ctrl = lambda c: {
        "p_ref_W": c.p_ref, "M": c.frequency_dynamics.inertia_m,
        "D": c.frequency_dynamics.damping_d, "omega_ref_rad_s": c.omega_ref,
        "theta0_rad": c.modulator.theta0, "f_hz": c.modulator.f_hz,
        "v_ln_rms_V": c.modulator.v_ln_rms, "m_base": c.m_base,
    }
    common_equivalence = {
        "initial_first_12_exact": True,
        "controller_settings_equal": ctrl(c_off) == ctrl(c_on),
        "plant_pv_parameters_equal": asdict(off.pv.p) == asdict(on.pv.p),
        "dc_link_parameters_equal": asdict(off.dcp) == asdict(on.dcp),
        "lcl_parameters_equal": asdict(off.lcl) == asdict(on.lcl),
        "inverter_efficiency_equal": off.eta == on.eta,
        "uvlo_equal": off.v_uvlo == on.v_uvlo,
        "profiles_equal_at_boundaries_and_midpoints": all(
            off.irradiance_profile(t) == on.irradiance_profile(t)
            and off.load_profile(t) == on.load_profile(t)
            and off.temperature_profile(t) == on.temperature_profile(t)
            for t in (0.0, .2, .4, .6, .8, 1.0, 1.2)
        ),
    }
    if not all(common_equivalence.values()):
        raise AssertionError(f"ON/OFF setup is not equivalent: {common_equivalence}")
    return off, on, x_off, x_on, pack, snapshot, ctrl(c_off), common_equivalence


def evaluate_model(name: str, model, initial: np.ndarray, is_on: bool,
                   horizon_s: float, stop_at_pre_uvlo: bool = False) -> dict[str, object]:
    start = time.perf_counter()
    last = start
    nfev = 0
    max_rhs_t = 0.0
    def rhs(t, x):
        nonlocal last, nfev, max_rhs_t
        nfev += 1
        max_rhs_t = max(max_rhs_t, float(t))
        now = time.perf_counter()
        if now - last >= 5.0:
            print(json.dumps({'event': 'integration_progress', 'case': name,
                              'max_rhs_time_s': max_rhs_t, 'nfev': nfev,
                              'elapsed_s': now-start}), flush=True)
            last = now
        return model.system_dynamics(t, x)
    print(json.dumps({'event': 'integration_start', 'case': name}), flush=True)
    events = None
    if stop_at_pre_uvlo:
        def pre_uvlo_event(_t, x):
            return float(x[0]) - PRE_UVLO_EVENT_V
        pre_uvlo_event.terminal = True
        pre_uvlo_event.direction = -1
        events = pre_uvlo_event
    sol = solve_ivp(rhs, (0.0, horizon_s), initial,
                    method="RK45", rtol=RTOL, atol=ATOL,
                    max_step=MAX_STEP_S, dense_output=True, events=events)
    elapsed = time.perf_counter() - start
    print(json.dumps({'event': 'integration_end', 'case': name, 'nfev': sol.nfev,
                      'elapsed_s': elapsed, 'message': sol.message}), flush=True)
    event_hit = bool(stop_at_pre_uvlo and sol.t_events and sol.t_events[0].size)
    if not sol.success or sol.sol is None or (stop_at_pre_uvlo and not event_hit):
        raise RuntimeError(f"{name} integration incomplete: {sol.message}")
    post_start = time.perf_counter()
    print(json.dumps({'event': 'reconstruction_start', 'case': name}), flush=True)
    integration_end_s = float(sol.t_events[0][0]) if event_hit else float(horizon_s)
    sample_times = np.arange(0.0, integration_end_s, SAMPLE_DT_S, dtype=float)
    if sample_times.size == 0 or integration_end_s - sample_times[-1] > 1e-12:
        sample_times = np.append(sample_times, integration_end_s)
    else:
        sample_times[-1] = integration_end_s
    sampled_states = sol.sol(sample_times)
    rows = []
    rhs_evaluations = 0
    for k, t in enumerate(sample_times):
        x = sampled_states[:, k]
        if is_on:
            b = model.integrated_signals(float(t), x)
            _, _, control = model._compute_step_control(
                float(t), x[0], x[1:4], x[7:10], x[10], x[11], vc=x[4:7],
                soc_bess=b['soc_bess'], soh_bess=b['soh_bess'],
                i_bess_max_available=b['i_bess_max_available'],
                p_bess_dc_max_available=b['p_bess_dc_max_available'],
                p_bess_dc_actual=b['p_bus'])
            p_bridge, p_pcc, idc_inv, p_cmd, m_ctrl = (
                control.p_bridge, b['p_pcc'], control.idc_inv, control.p_cmd, control.m_ctrl)
        else:
            p_bridge, p_pcc, idc_inv, p_cmd, m_ctrl = model.power_signals(float(t), x)
        vdc = float(x[0])
        g = float(model.irradiance_profile(float(t)))
        temp = float(model.temperature_profile(float(t)))
        ipv = float(model.plant.pv_current(max(vdc, 0.0), g, temp))
        p_pv = max(vdc * ipv, 0.0)
        d = model.system_dynamics(float(t), x)
        rhs_evaluations += 1
        p_bus = p_pack = p_loss = i_pack = i_bus = 0.0
        soc = soh = None
        saturation = {"dcdc_saturated": 0.0, "dcdc_supervision_saturated": 0.0,
                      "dcdc_adapter_saturated": 0.0, "dcdc_soc_blocked": 0.0}
        p_bess_available = 0.0
        if is_on:
            i_pack, i_bus = float(b["i_pack"]), float(b["i_bus"])
            p_pack, p_bus, p_loss = float(b["p_pack"]), float(b["p_bus"]), float(b["p_dcdc_loss"])
            soc, soh = float(b["soc_bess"]), float(b["soh_bess"])
            p_bess_available = float(b["p_bess_dc_max_available"])
            for key in saturation:
                saturation[key] = float(b.get(key, 0.0))
        p_bess_actual_for_gfm = min(p_bus, p_bess_available) if p_bus > 0.0 else p_bus
        p_dc_net = p_pv + p_bess_actual_for_gfm
        p_ac_available = max(p_dc_net * model.eta, 0.0)
        supervision_expected_p_cmd = min(P_REF_W, p_ac_available)
        p_dc_inv = vdc * float(idc_inv)
        p_cap_rate = vdc * model.dcp.Cdc * float(d[0])
        dc_balance_residual = p_pv + p_bus - p_dc_inv - p_cap_rate
        rows.append({
            "Vdc_V": vdc, "frequency_Hz": float(x[10]) / (2.0 * math.pi),
            "P_pcc_W": float(p_pcc), "P_pv_dc_W": p_pv,
            "P_pv_ac_available_W": p_pv * model.eta,
            "P_bridge_W": float(p_bridge), "P_dc_inverter_W": p_dc_inv,
            "P_dc_net_available_W": p_dc_net, "P_ac_available_W": p_ac_available,
            "P_ref_effective_W": float(p_cmd), "idc_inv_A": float(idc_inv),
            "m_ctrl": float(m_ctrl), "i_pack_A": i_pack, "i_bus_A": i_bus,
            "P_pack_W": p_pack, "P_bus_W": p_bus, "P_loss_W": p_loss,
            "SoC": soc, "SoH": soh, "saturation": saturation,
            "gfm_supervision_inputs": (None if not is_on else {
                "soc": soc, "soh": soh,
                "i_bess_max_available_A": float(b["i_bess_max_available"]),
                "p_bess_dc_max_available_W": p_bess_available,
                "p_bess_dc_actual_W": p_bus,
            }),
            "supervision_expected_p_cmd_W": supervision_expected_p_cmd,
            "dc_balance_residual_W": dc_balance_residual,
            "pack_bus_residual_W": p_pack - p_bus - p_loss,
            "bus_identity_residual_W": p_bus - vdc * i_bus,
        })

    arrays = {key: np.asarray([r[key] for r in rows], dtype=float)
              for key in ("Vdc_V", "frequency_Hz", "P_pcc_W", "P_pv_dc_W",
                          "P_pv_ac_available_W", "P_bridge_W", "P_dc_inverter_W",
                          "P_dc_net_available_W", "P_ac_available_W", "P_ref_effective_W",
                          "idc_inv_A", "m_ctrl", "i_pack_A", "i_bus_A", "P_pack_W",
                          "P_bus_W", "P_loss_W", "dc_balance_residual_W",
                          "pack_bus_residual_W", "bus_identity_residual_W")}
    freq = arrays["frequency_Hz"]
    rocof = np.gradient(freq, sample_times)
    finite_rows = all(np.isfinite(a).all() for a in arrays.values())

    def segment_metrics(mask: np.ndarray) -> dict[str, object]:
        t = sample_times[mask]
        result: dict[str, object] = {"sample_count": int(t.size)}
        for key in ("Vdc_V", "frequency_Hz", "P_pcc_W", "P_pv_dc_W", "P_pv_ac_available_W",
                    "P_bridge_W", "P_dc_inverter_W", "P_dc_net_available_W",
                    "P_ac_available_W", "P_ref_effective_W", "idc_inv_A", "m_ctrl"):
            values = arrays[key][mask]
            result[key] = {"min": float(np.min(values)), "max": float(np.max(values))}
        v = arrays["Vdc_V"][mask]
        f = arrays["frequency_Hz"][mask]
        result.update({
            "Vdc_min_V": float(np.min(v)), "Vdc_max_V": float(np.max(v)),
            "Vdc_max_abs_excursion_from_340_V": float(np.max(np.abs(v - VDC_REF_V))),
            "frequency_nadir_Hz": float(np.min(f)), "frequency_peak_Hz": float(np.max(f)),
            "frequency_max_abs_deviation_from_60_Hz": float(np.max(np.abs(f - 60.0))),
            "RoCoF_max_abs_Hz_s": float(np.max(np.abs(rocof[mask]))),
            "RoCoF_min_Hz_s": float(np.min(rocof[mask])),
            "RoCoF_max_Hz_s": float(np.max(rocof[mask])),
        })
        for key in ("P_pcc_W", "P_pv_dc_W", "P_bridge_W", "P_dc_inverter_W",
                    "P_dc_net_available_W", "P_ac_available_W", "P_ref_effective_W",
                    "P_pack_W", "P_bus_W", "P_loss_W"):
            values = arrays[key][mask]
            result[f"energy_{key}_Wh"] = float(np.trapezoid(values, t) / 3600.0) if t.size > 1 else 0.0
            result[f"energy_abs_{key}_Wh"] = float(np.trapezoid(np.abs(values), t) / 3600.0) if t.size > 1 else 0.0
        result["absolute_bus_energy_transfer_Wh"] = result["energy_abs_P_bus_W_Wh"]
        result["absolute_pack_energy_transfer_Wh"] = result["energy_abs_P_pack_W_Wh"]
        result["max_abs_dc_balance_residual_W"] = float(np.max(np.abs(arrays["dc_balance_residual_W"][mask])))
        if is_on:
            result["I_pack_peak_abs_A"] = float(np.max(np.abs(arrays["i_pack_A"][mask])))
            result["I_bus_peak_abs_A"] = float(np.max(np.abs(arrays["i_bus_A"][mask])))
            result["max_abs_pack_bus_residual_W"] = float(np.max(np.abs(arrays["pack_bus_residual_W"][mask])))
            result["max_abs_bus_identity_residual_W"] = float(np.max(np.abs(arrays["bus_identity_residual_W"][mask])))
            for state_key in ("SoC", "SoH"):
                vals = np.asarray([r[state_key] for k, r in enumerate(rows) if mask[k]], dtype=float)
                result[state_key] = {"min": float(np.min(vals)), "max": float(np.max(vals)),
                                     "start": float(vals[0]), "end": float(vals[-1])}
            result["saturation_fractions"] = {
                key: float(np.mean([r["saturation"][key] > .5 for k, r in enumerate(rows) if mask[k]]))
                for key in rows[0]["saturation"]
            }
            result["pack_charge_samples"] = int(np.count_nonzero(arrays["i_pack_A"][mask] < 0))
            result["pack_discharge_samples"] = int(np.count_nonzero(arrays["i_pack_A"][mask] > 0))
        return result

    segments = {}
    for label, (start_s, end_s) in STAGES.items():
        mask = (sample_times >= start_s) & (sample_times < end_s)
        if math.isclose(end_s, T_END_S):
            mask |= np.isclose(sample_times, end_s)
        segments[label] = segment_metrics(mask)
    all_mask = np.ones(sample_times.size, dtype=bool)
    metrics = segment_metrics(all_mask)
    metrics["Vdc_min_time_s"] = float(sample_times[np.argmin(arrays["Vdc_V"])])
    metrics["Vdc_max_time_s"] = float(sample_times[np.argmax(arrays["Vdc_V"])])
    metrics["frequency_nadir_time_s"] = float(sample_times[np.argmin(freq)])
    metrics["frequency_peak_time_s"] = float(sample_times[np.argmax(freq)])
    metrics["RoCoF_max_abs_time_s"] = float(sample_times[np.argmax(np.abs(rocof))])
    metrics["SoC_final"] = float(rows[-1]["SoC"]) if is_on else None
    metrics["SoH_final"] = float(rows[-1]["SoH"]) if is_on else None
    metrics["energy_absolute_bus_Wh"] = float(np.trapezoid(np.abs(arrays["P_bus_W"]), sample_times) / 3600.0)
    metrics["energy_signed_bus_Wh"] = float(np.trapezoid(arrays["P_bus_W"], sample_times) / 3600.0)
    metrics["energy_absolute_pack_Wh"] = float(np.trapezoid(np.abs(arrays["P_pack_W"]), sample_times) / 3600.0)
    metrics["energy_signed_pack_Wh"] = float(np.trapezoid(arrays["P_pack_W"], sample_times) / 3600.0)
    metrics["energy_loss_Wh"] = float(np.trapezoid(arrays["P_loss_W"], sample_times) / 3600.0)

    checks = {
        "solver_success": bool(sol.success), "expected_state_count": sol.y.shape[0] == (15 if is_on else 12),
        "finite_states_and_signals": bool(np.isfinite(sol.y).all() and finite_rows),
        "Vdc_positive": bool(np.all(arrays["Vdc_V"] > 0.0)),
        "frequency_dynamic_from_omega": bool(np.array_equal(arrays["frequency_Hz"], sampled_states[10] / (2 * math.pi))),
        "dc_power_balance": bool(np.max(np.abs(arrays["dc_balance_residual_W"])) <= 1e-8 + 1e-10 * max(1., float(np.max(np.abs(arrays["P_pv_dc_W"]))))),
        "bridge_to_dc_conversion": bool(np.max(np.abs(arrays["P_dc_inverter_W"] - np.maximum(arrays["P_bridge_W"], 0.0) / model.eta)) <= 1e-8 + 1e-10 * max(1., float(np.max(np.abs(arrays["P_dc_inverter_W"]))))),
    }
    if is_on:
        checks.update({
            "SoC_in_bounds": bool(np.all((sampled_states[12] >= model.bess.soc_min - 1e-9) & (sampled_states[12] <= model.bess.soc_max + 1e-9))),
            "zdeg_nonnegative": bool(np.all(sampled_states[14] >= 0.0)),
            "pack_bus_energy_balance": bool(np.max(np.abs(arrays["pack_bus_residual_W"])) <= 1e-8 + 1e-10 * max(1., float(np.max(np.abs(arrays["P_pack_W"]))))),
            "bus_power_identity": bool(np.max(np.abs(arrays["bus_identity_residual_W"])) <= 1e-8 + 1e-10 * max(1., float(np.max(np.abs(arrays["P_bus_W"]))))),
            "losses_nonnegative": bool(np.all(arrays["P_loss_W"] >= -1e-12)),
            "signed_port_conventions": bool(np.all((arrays["i_pack_A"] > 0) == (arrays["P_pack_W"] > 0))
                                                   and np.all((arrays["i_bus_A"] > 0) == (arrays["P_bus_W"] > 0))),
            "gfm_supervision_p_cmd_matches_reconstruction": bool(np.allclose(
                arrays["P_ref_effective_W"],
                np.minimum(P_REF_W, np.maximum(
                    arrays["P_pv_dc_W"] + np.where(arrays["P_bus_W"] > 0.0,
                        np.minimum(arrays["P_bus_W"], np.asarray([
                            float(r["gfm_supervision_inputs"]["p_bess_dc_max_available_W"])
                            for r in rows], dtype=float)), arrays["P_bus_W"]), 0.0) * model.eta),
                rtol=0.0, atol=1e-8)),
        })
    reconstruction_elapsed = time.perf_counter() - post_start
    print(json.dumps({'event': 'reconstruction_end', 'case': name,
                      'elapsed_s': reconstruction_elapsed}), flush=True)
    return {
        "success": bool(sol.success), "message": str(sol.message), "state_count": int(sampled_states.shape[0]),
        "nfev": int(sol.nfev), "elapsed_s": elapsed,
        "accepted_steps": int(max(0, len(sol.t) - 1)),
        "termination_reason": "terminal_event_Vdc_201V" if event_hit else "horizon_reached",
        "event": ({"name": "Vdc_minus_observation_threshold_V", "terminal": True,
                   "direction": -1, "observation_threshold_V": PRE_UVLO_EVENT_V,
                   "implemented_uvlo_threshold_V": float(model.v_uvlo),
                   "is_uvlo_trip": False,
                   "time_to_observation_threshold_s": float(sol.t_events[0][0]),
                   "t_event_s": float(sol.t_events[0][0]),
                   "state": sol.y_events[0][0].tolist(),
                   "Vdc_event_V": float(sol.y_events[0][0][0])} if event_hit else None),
        "horizon_requested_s": float(horizon_s), "horizon_reached_s": integration_end_s,
        "reconstruction_elapsed_s": reconstruction_elapsed,
        "diagnostic_rhs_evaluations_for_dc_balance": rhs_evaluations,
        "sample_times_s": sample_times.tolist(),
        "metrics": metrics, "segments": segments, "checks": checks,
        "signals_sampled": rows,
    }


def compare_metric(on_value, off_value) -> dict[str, float | None]:
    delta = float(on_value) - float(off_value)
    relative = abs(delta) / abs(float(off_value)) if float(off_value) != 0.0 else None
    return {"ON": float(on_value), "OFF": float(off_value),
            "difference_ON_minus_OFF": delta, "absolute_difference": abs(delta),
            "relative_difference_vs_OFF": relative}


def diagnose_uvlo() -> None:
    """Stop before UVLO and probe both sides without changing the plant."""
    model, _, initial, *_ = make_pair()
    started = time.perf_counter()
    count = 0
    last = started
    def rhs(t, x):
        nonlocal count, last
        count += 1
        now = time.perf_counter()
        if now-last >= 5:
            print(json.dumps({'event': 'uvlo_progress', 'rhs_t_s': float(t),
                              'vdc_V': float(x[0]), 'nfev': count,
                              'elapsed_s': now-started}), flush=True)
            last = now
        return model.system_dynamics(t, x)
    def event(t, x):
        return x[0] - (model.v_uvlo + .001)
    event.terminal = True
    event.direction = -1
    solution = solve_ivp(rhs, (0, .91), initial, method='RK45', rtol=RTOL,
                         atol=ATOL, max_step=MAX_STEP_S, events=event)
    if not solution.success or not len(solution.t_events[0]):
        raise RuntimeError('UVLO approach event was not reached')
    x = solution.y[:, -1].copy()
    print(json.dumps({'event': 'uvlo_approach', 't_s': float(solution.t[-1]),
                      'vdc_V': float(x[0]), 'nfev': solution.nfev,
                      'elapsed_s': time.perf_counter()-started}), flush=True)
    for voltage in (model.v_uvlo - 1e-6, model.v_uvlo + 1e-6):
        probe = x.copy(); probe[0] = voltage
        derivative = model.system_dynamics(float(solution.t[-1]), probe)
        bridge, _, current, _, _ = model.power_signals(float(solution.t[-1]), probe)
        print(json.dumps({'event': 'uvlo_probe', 'vdc_V': voltage,
                          'dVdc_dt_V_s': float(derivative[0]),
                          'p_bridge_W': bridge, 'idc_inv_A': current}), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['ON', 'OFF'])
    parser.add_argument('--result', type=Path)
    parser.add_argument('--horizon-s', type=float, default=T_END_S)
    parser.add_argument('--stop-at-pre-uvlo', action='store_true')
    parser.add_argument('--diagnose-uvlo', action='store_true')
    args = parser.parse_args()
    if args.diagnose_uvlo:
        diagnose_uvlo()
        return 0
    if args.worker:
        if args.result is None:
            parser.error('--worker requires --result')
        off, on, x_off, x_on, *_ = make_pair()
        is_on = args.worker == 'ON'
        result = evaluate_model(args.worker, on if is_on else off,
                                x_on if is_on else x_off, is_on,
                                horizon_s=args.horizon_s,
                                stop_at_pre_uvlo=args.stop_at_pre_uvlo)
        start = time.perf_counter()
        args.result.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({'event': 'worker_json_written', 'case': args.worker,
                          'elapsed_s': time.perf_counter()-start}), flush=True)
        return 0
    utc_start = datetime.now(timezone.utc)
    clock = time.perf_counter()
    previous = json.loads(BLOCKED_OUTPUT.read_text(encoding='utf-8')) if BLOCKED_OUTPUT.exists() else None
    report: dict[str, object] = {
        "task": "BAT26-55 N4 PV/GFM Leaf pack ON/OFF comparison",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "command": sys.argv, "utc_start": utc_start.isoformat(),
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "solver": {"method": "RK45", "rtol": RTOL, "atol": ATOL,
                   "max_step_s": MAX_STEP_S, "sample_dt_s": SAMPLE_DT_S},
        "horizon_s": T_END_S, "frequency_definition": "x[10]/(2*pi)",
        "evaluation_grid": {"spacing_s": SAMPLE_DT_S, "end_point": "common endpoint included, including event time"},
        "profiles": {"segments": [
            {"interval_s": [0.0, 0.4], "irradiance_W_m2": 800.0, "load_W": 3000.0},
            {"interval_s": [0.4, 0.8], "irradiance_W_m2": 1000.0, "load_W": 2400.0},
            {"interval_s": [0.8, 1.2], "irradiance_W_m2": 400.0, "load_W": 4200.0}],
            "temperature_C": MICROGRID_TEMPERATURE_C_DEFAULT,
            "transient_skip_s": TRANSIENT_SKIP_S,
            "steady_windows": {"preconditioning_s": [0.0, 0.4],
                               "solar_surplus_s": [0.45, 0.8],
                               "load_deficit_s": [0.85, 1.2]}},
        "on_model": {"class": "MicrogridWithBESS + Leaf48ModulePack + DC/DC", "states": 15,
                     "qeff_initial_Ah": QEFF_AH, "soc_initial": SOC0,
                     "converter_hypotheses_only": {"eta_charge": ETA_DCDC, "eta_discharge": ETA_DCDC,
                         "unit_current_limit_A": 10.0, "bus_current_limit_A": 20.0,
                         "bus_power_limit_W": 5000.0}},
        "off_model": {"class": "Microgrid + GFMController", "states": 12,
                      "battery_states_added": False},
        "gfm": {"controller": "GFMController", "M": M, "D": D, "P_ref_W": P_REF_W},
        "scope": "paired numerical simulation only; no measured hardware/HIL; no dynamic aging sensitivity",
        "previous_attempt": previous,
        "diagnostic_endpoint": {
            "name": "time_to_201V_observation_threshold",
            "observation_threshold_V": PRE_UVLO_EVENT_V,
            "implemented_uvlo_threshold_V": 200.0,
            "is_uvlo_trip_or_physical_protection": False,
            "methodology_adopted_after_exploratory_runs": True,
        },
        "pre_uvlo_event_V": PRE_UVLO_EVENT_V,
        "process_timeouts_s": {"off_event": OFF_EVENT_TIMEOUT_S,
                               "case": CASE_TIMEOUT_S},
        "full_1p20s_status": "BLOCKED",
    }
    def save_progress() -> None:
        report["utc_updated"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        off, on, x_off, x_on, pack, snapshot, controller, equivalence = make_pair()
        report["common_condition_equivalence"] = equivalence
        report["common_initial_state_12"] = x_off.tolist()
        report["common_controller_parameters"] = controller
        report["capacity_snapshot"] = {"q_nom_ref_Ah": snapshot.q_nom_ref_ah,
                                       "q_init_case_Ah": snapshot.q_init_case_ah,
                                       "retention_since_case_start": snapshot.retention_since_case_start,
                                       "q_eff_Ah": snapshot.q_eff_ah,
                                       "soh": snapshot.soh}
        report["status"] = "BLOCKED"
        report["current_case"] = "OFF"
        save_progress()
        print("Running OFF 12-state solve to pre-UVLO event", flush=True)
        def run_worker(case, horizon_s, *, stop_at_pre_uvlo=False, timeout_s=CASE_TIMEOUT_S):
            with tempfile.TemporaryDirectory(prefix='bat26_n4_') as directory:
                path = Path(directory) / 'result.json'
                cmd = [sys.executable, '-u', str(Path(__file__).resolve()),
                       '--worker', case, '--result', str(path), '--horizon-s', str(horizon_s)]
                if stop_at_pre_uvlo:
                    cmd.append('--stop-at-pre-uvlo')
                with LOG.open('a', encoding='utf-8', buffering=1) as log:
                    log.write(f'COMMAND {cmd}, timeout_s={timeout_s}\n')
                    process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
                    try:
                        code = process.wait(timeout=timeout_s)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt':
                            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                           stdout=log, stderr=subprocess.STDOUT, check=False)
                        else:
                            process.kill()
                        process.wait()
                        log.write(f'BLOCKED {case}: process exceeded {timeout_s:g} s\n')
                        raise TimeoutError(f'{case} exceeded {timeout_s:g} s; see {LOG}')
                    if code != 0:
                        raise RuntimeError(f'{case} worker exited {code}; see {LOG}')
                    read_start = time.perf_counter()
                    result = json.loads(path.read_text(encoding='utf-8'))
                    result['parent_json_read_s'] = time.perf_counter()-read_start
                    return result
        event_attempt = {"status": "started", "threshold_V": PRE_UVLO_EVENT_V,
                         "threshold_role": "diagnostic_observation_only_not_UVLO_trip",
                         "implemented_uvlo_threshold_V": float(off.v_uvlo),
                         "direction": -1, "terminal": True,
                         "timeout_s": OFF_EVENT_TIMEOUT_S}
        report["off_event_attempt"] = event_attempt
        save_progress()
        try:
            off_result = run_worker("OFF", T_END_S, stop_at_pre_uvlo=True,
                                    timeout_s=OFF_EVENT_TIMEOUT_S)
            event_attempt.update({"status": "event_reached", "t_event_s": off_result["event"]["t_event_s"],
                                  "nfev": off_result["nfev"], "elapsed_s": off_result["elapsed_s"],
                                  "termination_reason": off_result["termination_reason"]})
            comparison_horizon = float(off_result["event"]["t_event_s"])
        except (TimeoutError, RuntimeError) as exc:
            event_attempt.update({"status": "not_reached_within_budget", "error": str(exc)})
            report["off_event_attempt"] = event_attempt
            report["fallback"] = {"status": "started", "fixed_horizon_s": FALLBACK_HORIZON_S,
                                  "reason": "Pre-UVLO event did not complete within its process time budget."}
            report["current_case"] = "OFF_FALLBACK"
            save_progress()
            off_result = run_worker("OFF", FALLBACK_HORIZON_S, timeout_s=CASE_TIMEOUT_S)
            report["fallback"].update({"status": "completed", "nfev": off_result["nfev"],
                                       "elapsed_s": off_result["elapsed_s"]})
            comparison_horizon = FALLBACK_HORIZON_S
        report["off_event_attempt"] = event_attempt
        report["comparison_horizon_s"] = comparison_horizon
        report["off"] = off_result
        report.pop("current_case", None)
        report["current_case"] = "ON"
        save_progress()
        print(f"Running ON 15-state solve to t={comparison_horizon:.9f} s", flush=True)
        on_result = run_worker("ON", comparison_horizon, timeout_s=CASE_TIMEOUT_S)
        report.pop("current_case", None)
        report["off"] = off_result
        report["on"] = on_result
        metric_keys = ("Vdc_min_V", "Vdc_max_V", "Vdc_max_abs_excursion_from_340_V",
                       "frequency_nadir_Hz", "frequency_peak_Hz",
                       "frequency_max_abs_deviation_from_60_Hz", "RoCoF_max_abs_Hz_s",
                       "RoCoF_min_Hz_s", "RoCoF_max_Hz_s", "energy_P_pcc_W_Wh",
                       "energy_P_pv_dc_W_Wh", "energy_P_bridge_W_Wh",
                       "energy_P_dc_inverter_W_Wh", "energy_absolute_bus_Wh",
                       "energy_signed_bus_Wh", "energy_absolute_pack_Wh",
                       "energy_signed_pack_Wh", "energy_loss_Wh")
        report["global_comparison"] = {
            key: compare_metric(on_result["metrics"][key], off_result["metrics"].get(key, 0.0))
            for key in metric_keys if key in on_result["metrics"]
        }
        extrema_keys = ("P_pcc_W", "P_pv_dc_W", "P_bridge_W", "P_dc_inverter_W",
                        "P_dc_net_available_W", "P_ac_available_W", "P_ref_effective_W",
                        "idc_inv_A", "m_ctrl")
        report["global_comparison"]["signal_extrema"] = {
            key: {bound: compare_metric(on_result["metrics"][key][bound],
                                        off_result["metrics"][key][bound])
                  for bound in ("min", "max")}
            for key in extrema_keys
        }
        stage_comparison = {}
        stage_keys = ("Vdc_min_V", "Vdc_max_V", "Vdc_max_abs_excursion_from_340_V",
                      "frequency_nadir_Hz", "frequency_peak_Hz",
                      "frequency_max_abs_deviation_from_60_Hz", "RoCoF_max_abs_Hz_s",
                      "energy_P_pcc_W_Wh", "energy_P_pv_dc_W_Wh", "energy_P_bridge_W_Wh",
                      "energy_P_bus_W_Wh", "energy_abs_P_bus_W_Wh", "energy_P_pack_W_Wh",
                      "energy_abs_P_pack_W_Wh", "energy_P_loss_W_Wh")
        for stage in STAGES:
            on_metrics, off_metrics = on_result["segments"][stage], off_result["segments"][stage]
            stage_comparison[stage] = {
                key: compare_metric(on_metrics[key], off_metrics.get(key, 0.0))
                for key in stage_keys if key in on_metrics
            }
            stage_comparison[stage]["signal_extrema"] = {
                key: {bound: compare_metric(on_metrics[key][bound], off_metrics[key][bound])
                      for bound in ("min", "max")}
                for key in extrema_keys
            }
        report["stage_comparison"] = stage_comparison
        checks = {**{f"equivalence_{key}": bool(value) for key, value in equivalence.items()},
                  **{f"OFF_{key}": bool(value) for key, value in off_result["checks"].items()},
                  **{f"ON_{key}": bool(value) for key, value in on_result["checks"].items()}}
        checks["common_comparison_interval_and_grid"] = (
            np.array_equal(off_result["sample_times_s"], on_result["sample_times_s"])
            and off_result["sample_times_s"][0] == 0.0
            and off_result["sample_times_s"][-1] == comparison_horizon
            and on_result["sample_times_s"][-1] == comparison_horizon
        )
        checks["event_is_201V_observation_not_uvlo_trip"] = (
            off_result.get("event") is not None
            and off_result["event"]["Vdc_event_V"] == PRE_UVLO_EVENT_V
            and off_result["event"]["implemented_uvlo_threshold_V"] == off.v_uvlo
            and off_result["event"]["is_uvlo_trip"] is False
        )
        checks["capacity_snapshot_matches_pack"] = (
            snapshot.q_eff_ah == QEFF_AH and pack.capacity() == snapshot)
        report["checks"] = checks
        report["validation_status"] = "PASS" if all(checks.values()) else "FAIL"
        on_above_event = on_result["metrics"]["Vdc_min_V"] >= PRE_UVLO_EVENT_V
        report["on_remained_above_201V"] = bool(on_above_event)
        report["n4_pre_uvlo_status"] = "PASS" if all(checks.values()) else "FAIL"
        report["deficit_window"] = {
            "after_50ms_transient_start_s": 0.85,
            "available_duration_s": max(0.0, comparison_horizon - 0.85),
            "sufficient_for_0p10s_analysis": comparison_horizon - 0.85 >= 0.10,
        }
        if report["n4_pre_uvlo_status"] == "PASS" and not on_above_event:
            report["interpretation_status"] = "REVIEW"
            report["interpretation_reason"] = "ON reached or crossed the diagnostic 201 V observation level before the OFF event time; the paired numerical comparison remains valid only over its reported interval."
        elif report["n4_pre_uvlo_status"] == "PASS":
            report["interpretation_status"] = "REVIEW"
            report["interpretation_reason"] = "The comparison reports effects without requiring ON to improve Vdc or frequency; findings apply only through the pre-UVLO interval."
        report["design_review"] = {
            "status": "REVIEW",
            "reason": "The model has no upper DC-link protection. Reported voltage extrema are simulation results, not safety limits; N4 has no predeclared efficacy target.",
        }
        report["status"] = report["n4_pre_uvlo_status"]
        report["full_1p20s_status"] = "BLOCKED"
    except TimeoutError as exc:
        report["status"] = report["validation_status"] = "BLOCKED"
        report["n4_pre_uvlo_status"] = "BLOCKED"
        report["full_1p20s_status"] = "BLOCKED"
        report["error"] = str(exc)
    except Exception as exc:
        report["status"] = "FAIL"
        report["validation_status"] = "FAIL"
        report["n4_pre_uvlo_status"] = "FAIL"
        report["full_1p20s_status"] = "BLOCKED"
        report["error"] = repr(exc)
    except KeyboardInterrupt:
        report["status"] = "BLOCKED"
        report["validation_status"] = "BLOCKED"
        report["n4_pre_uvlo_status"] = "BLOCKED"
        report["full_1p20s_status"] = "BLOCKED"
        report["error"] = "Interrupted before both integrations completed; partial case data, if present, are not a PASS."
    report["utc_end"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_total_s"] = time.perf_counter() - clock
    save_progress()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"output_path={OUTPUT}")
    return 0 if report.get("validation_status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
