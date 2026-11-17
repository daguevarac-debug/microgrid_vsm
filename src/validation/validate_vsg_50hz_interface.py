"""Paired 50/60 Hz islanded GFM study and 6.5 s audit; run from any directory.

Preserves backward compatibility:
- ``outputs/validation/vsg_50hz_interface.json`` retains the 8-record list format
  extended to the 6.5 s horizon with explicit pre-event, transient, post-event
  and steady-state window metrics plus initial vs global vs post-step Vdc audit.
- ``outputs/validation/vsg_50hz_interface_audit_6p5s.json`` and
  ``outputs/validation/vsg_50hz_interface_audit_6p5s.csv`` store the complete
  audit report (including both 1.4 s legacy and 6.5 s full-horizon comparisons,
  paired 50/60 Hz deltas, +40% physical root-cause quantification, and +40%
  BESS+PI discharge contrast).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    DCLINK_CAP_F_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    MICROGRID_ETA_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from inverter_source import required_vdc_for_vln_rms
from microgrid import BalancedRLLoad, Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from tuning_metrics import (
    DEFAULT_TUNING_CRITERIA,
    TuningCriteria,
    dc_link_performance_metrics,
    frequency_performance_metrics,
)
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)
from validation.validate_gfm_integrated_system import _reference_active_power_w


T_STEP_S = float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
T_END_6P5_S = 6.5
T_END_1P4_S = 1.4
DT_SAMPLE_S = 0.0005  # 0.5 ms diagnostic grid


def _build_bess_pi_model(freq_hz: float, step_fraction: float, bess_enabled: bool = True) -> MicrogridWithBESSPI:
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + float(step_fraction))
    controller = GFMController(
        f_hz=freq_hz,
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=PI_KP_W_PER_V,
        ki_w_per_v_s=PI_KI_W_PER_V_S,
    )
    return MicrogridWithBESSPI(
        controller=controller,
        dc_link_bess_pi=pi,
        bess_enabled=bess_enabled,
        load_frequency_hz=freq_hz,
        load_profile=lambda t: p_pre if t < T_STEP_S else p_post,
    )


def run(
    freq: float,
    step: float,
    bess: bool = False,
    *,
    t_end_s: float = T_END_6P5_S,
    return_traces: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Simulate one islanded GFM scenario and compute explicit windowed metrics."""
    p_ref = _reference_active_power_w()
    controller = GFMController(
        f_hz=freq,
        p_ref=p_ref,
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    if bess:
        model = _build_bess_pi_model(freq, step, bess_enabled=True)
        initial = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0)
    else:
        p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
        p_post = p_pre * (1.0 + float(step))
        model = Microgrid(
            controller=controller,
            load_frequency_hz=freq,
            load_profile=(lambda _t: p_pre) if step == 0 else (lambda t: p_pre if t < T_STEP_S else p_post),
        )
        initial = model.initial_state(vdc0=SIM_VDC0_V_DEFAULT)

    assert model.controller_state_name == "omega" and len(initial) == (16 if bess else 12)
    assert np.isclose(initial[10], 2.0 * np.pi * freq) and initial[11] == controller.modulator.theta0

    sol = solve_ivp(
        model.system_dynamics,
        (0.0, float(t_end_s)),
        initial,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
        dense_output=True,
    )
    if not sol.success or not np.isfinite(sol.y).all():
        raise RuntimeError(sol.message)

    n_samples = int(round(t_end_s / DT_SAMPLE_S)) + 1
    t = np.linspace(0.0, float(t_end_s), n_samples)
    x = sol.sol(t)
    vdc = x[0]
    f = x[10] / (2.0 * np.pi)

    # Explicit windows
    pre = (t >= 0.7) & (t < T_STEP_S)
    pre_legacy = (t >= 0.6) & (t < T_STEP_S)
    transient = (t >= T_STEP_S) & (t <= min(2.0, t_end_s))
    post = t >= T_STEP_S
    ss_start_s = max(t_end_s - 1.0, T_STEP_S + 0.4) if t_end_s >= 2.0 else 1.2
    last = t >= ss_start_s
    last_1p4 = (t >= 1.2) & (t <= min(1.4, t_end_s))

    freq_dot = np.zeros_like(t)
    pcc = np.zeros_like(t)
    bridge = np.zeros_like(t)
    modulation = np.zeros_like(t)
    voltage_sq = np.zeros_like(t)
    p_pv_dc = np.zeros_like(t)
    batt_i = np.zeros_like(t)
    batt_p = np.zeros_like(t)
    batt_i_lim = np.zeros_like(t)
    batt_p_min = np.zeros_like(t)
    batt_p_max = np.zeros_like(t)
    batt_vt = np.zeros_like(t)
    pi_sat = np.zeros_like(t, dtype=bool)
    pi_aw = np.zeros_like(t, dtype=bool)

    for idx, (ti, xi) in enumerate(zip(t, x.T)):
        t_float = float(ti)
        rhs = model.system_dynamics(t_float, xi)
        freq_dot[idx] = rhs[10] / (2.0 * np.pi)
        load = model._load_at_time(t_float)
        _, _, _, v_pcc = model.plant.lcl_derivatives_with_rl_load(
            np.zeros(3), xi[1:4], xi[4:7], xi[7:10], load
        )
        voltage_sq[idx] = float(np.mean(v_pcc * v_pcc))
        ipv = model.plant.pv_current(
            max(float(xi[0]), 0.0),
            float(model.irradiance_profile(t_float)),
            float(model.temperature_profile(t_float)),
        )
        p_pv_dc[idx] = float(xi[0]) * float(ipv)
        if bess:
            sig = model.integrated_signals(t_float, xi)
            pcc[idx] = float(sig["p_pcc"])
            bridge[idx] = float(sig["p_bridge"])
            modulation[idx] = (
                min(INVERTER_MODULATION_INDEX_MAX_DEFAULT, 2.0 * np.sqrt(2.0) * GRID_V_LN_RMS_DEFAULT / xi[0])
                if xi[0] >= model.v_uvlo
                else 0.0
            )
            batt_i[idx] = float(sig["i_bess"])
            batt_p[idx] = float(sig["p_bess_dc"])
            batt_i_lim[idx] = float(sig["i_bess_max_available"])
            batt_p_min[idx] = float(sig["p_bess_ref_min_w"])
            batt_p_max[idx] = float(sig["p_bess_ref_max_w"])
            batt_vt[idx] = float(sig["vt_bess"])
            pi_sat[idx] = bool(sig["pi_saturated"])
            pi_aw[idx] = bool(sig["anti_windup_active"])
        else:
            pb, pp, _, _, m_val = model.power_signals(t_float, xi)
            pcc[idx] = float(pp)
            bridge[idx] = float(pb)
            modulation[idx] = float(m_val)

    vdc_min_req = float(required_vdc_for_vln_rms(GRID_V_LN_RMS_DEFAULT, INVERTER_MODULATION_INDEX_MAX_DEFAULT))

    # Tuning criteria adapted to scenario nominal frequency (50 or 60 Hz)
    criteria = TuningCriteria(nominal_frequency_hz=float(freq))
    freq_metrics = frequency_performance_metrics(t, f, T_STEP_S, criteria=criteria)
    dc_metrics = dc_link_performance_metrics(t, vdc, T_STEP_S, criteria=criteria)

    global_min_idx = int(np.argmin(vdc))
    global_max_idx = int(np.argmax(vdc))
    post_indices = np.flatnonzero(post)
    post_min_idx = int(post_indices[int(np.argmin(vdc[post]))])
    post_max_idx = int(post_indices[int(np.argmax(vdc[post]))])
    f_post_min_idx = int(post_indices[int(np.argmin(f[post]))])

    result: dict[str, Any] = {
        "frequency_hz": float(freq),
        "step": float(step),
        "bess": bool(bess),
        "t_end_s": float(t_end_s),
        "solver_success": bool(sol.success),
        "M": float(GFM_SELECTED_M),
        "D": float(GFM_SELECTED_D),
        "p_ref_w": float(p_ref),
        # Explicit window definitions
        "window_pre_event_s": [0.7, T_STEP_S],
        "window_transient_s": [T_STEP_S, min(2.0, float(t_end_s))],
        "window_post_event_s": [T_STEP_S, float(t_end_s)],
        "window_steady_state_s": [float(ss_start_s), float(t_end_s)],
        # Frequency metrics
        "frequency_pre_mean_hz": float(np.mean(f[pre_legacy])),
        "frequency_pre_step_hz": float(freq_metrics["frequency_pre_step_hz"]),
        "frequency_post_min_hz": float(np.min(f[post])),
        "frequency_post_min_time_s": float(t[f_post_min_idx]),
        "frequency_post_max_hz": float(np.max(f[post])),
        "frequency_final_hz": float(f[-1]),
        "max_frequency_drop_hz": float(freq_metrics["max_frequency_drop_hz"]),
        "max_frequency_abs_deviation_hz": float(freq_metrics["max_frequency_abs_deviation_hz"]),
        "frequency_recovery_time_s": (
            float(freq_metrics["frequency_recovery_time_s"])
            if np.isfinite(freq_metrics["frequency_recovery_time_s"])
            else None
        ),
        "frequency_criteria_pass": bool(freq_metrics["frequency_criteria_pass"]),
        "rocof_post_abs_max_hz_s": float(np.max(np.abs(freq_dot[post]))),
        "rocof_transient_abs_max_hz_s": float(np.max(np.abs(freq_dot[transient]))),
        # Vdc explicit audit: initial vs global vs pre-step vs post-step vs final
        "vdc_initial_v": float(vdc[0]),
        "vdc_global_min_v": float(vdc[global_min_idx]),
        "vdc_global_min_time_s": float(t[global_min_idx]),
        "vdc_global_max_v": float(vdc[global_max_idx]),
        "vdc_global_max_time_s": float(t[global_max_idx]),
        "vdc_pre_step_mean_v": float(dc_metrics["vdc_pre_step_v"]),
        "vdc_transient_min_v": float(np.min(vdc[transient])),
        "vdc_post_min_v": float(vdc[post_min_idx]),
        "vdc_post_min_time_s": float(t[post_min_idx]),
        "vdc_post_max_v": float(vdc[post_max_idx]),
        "vdc_post_max_time_s": float(t[post_max_idx]),
        "vdc_final_v": float(vdc[-1]),
        "vdc_min_required_v": vdc_min_req,
        "vdc_event_max_abs_deviation_v": float(dc_metrics["vdc_event_max_abs_deviation_v"]),
        "vdc_event_max_abs_deviation_pct": float(dc_metrics["vdc_event_max_abs_deviation_pct"]),
        "vdc_event_deviation_pass": bool(dc_metrics["vdc_event_deviation_pass"]),
        "vdc_minimum_voltage_pass": bool(dc_metrics["vdc_minimum_voltage_pass"]),
        "vdc_criteria_pass": bool(dc_metrics["vdc_criteria_pass"]),
        # Voltage, power and modulation metrics
        "pcc_rms_pre_v": float(np.sqrt(np.mean(voltage_sq[pre]))),
        "pcc_rms_last_v": float(np.sqrt(np.mean(voltage_sq[last]))),
        "pcc_rms_1p2_to_1p4_v": float(np.sqrt(np.mean(voltage_sq[last_1p4]))),
        "pcc_power_mean_pre_w": float(np.mean(pcc[pre])),
        "pcc_power_mean_last_w": float(np.mean(pcc[last])),
        "pcc_power_mean_1p2_to_1p4_w": float(np.mean(pcc[last_1p4])),
        "bridge_power_mean_pre_w": float(np.mean(bridge[pre])),
        "bridge_power_mean_last_w": float(np.mean(bridge[last])),
        "pv_dc_power_mean_pre_w": float(np.mean(p_pv_dc[pre])),
        "pv_dc_power_mean_last_w": float(np.mean(p_pv_dc[last])),
        "modulation_pre_mean": float(np.mean(modulation[pre])),
        "modulation_post_max": float(np.max(modulation[post])),
        "modulation_max": float(np.max(modulation)),
        "modulation_limited_fraction_post": float(np.mean(vdc[post] < vdc_min_req)),
        "modulation_limited_fraction_last": float(np.mean(vdc[last] < vdc_min_req)),
    }

    if bess:
        soc = x[12]
        soh = np.array([model._bess_soh(float(z)) for z in x[14]])
        limits_pass = bool(
            np.all(np.abs(batt_i) <= batt_i_lim + 1e-8)
            and np.all(batt_p >= batt_p_min - 1e-8)
            and np.all(batt_p <= batt_p_max + 1e-8)
            and np.all((soc >= model.bess.soc_min - 1e-8) & (soc <= model.bess.soc_max + 1e-8))
            and np.all((soh >= model.bess.soh_min - 1e-8) & (soh <= 1.0 + 1e-8))
        )
        result.update(
            bess_current_min_a=float(np.min(batt_i)),
            bess_current_max_a=float(np.max(batt_i)),
            bess_current_post_min_a=float(np.min(batt_i[post])),
            bess_current_post_max_a=float(np.max(batt_i[post])),
            bess_current_post_mean_a=float(np.mean(batt_i[post])),
            bess_current_last_mean_a=float(np.mean(batt_i[last])),
            bess_power_min_w=float(np.min(batt_p)),
            bess_power_max_w=float(np.max(batt_p)),
            bess_power_post_min_w=float(np.min(batt_p[post])),
            bess_power_post_max_w=float(np.max(batt_p[post])),
            bess_power_post_mean_w=float(np.mean(batt_p[post])),
            bess_power_last_mean_w=float(np.mean(batt_p[last])),
            bess_discharge_observed_post=bool(np.any(batt_i[post] > 1e-6)),
            bess_charge_observed_post=bool(np.any(batt_i[post] < -1e-6)),
            bess_discharge_fraction_post=float(np.mean(batt_i[post] > 1e-6)),
            soc_initial=float(soc[0]),
            soc_min=float(np.min(soc)),
            soc_max=float(np.max(soc)),
            soc_final=float(soc[-1]),
            soh_initial=float(soh[0]),
            soh_min=float(np.min(soh)),
            soh_final=float(soh[-1]),
            vt_bess_min_v=float(np.min(batt_vt)),
            vt_bess_max_v=float(np.max(batt_vt)),
            pi_saturation_fraction=float(np.mean(pi_sat)),
            anti_windup_fraction=float(np.mean(pi_aw)),
            bess_limits_pass=limits_pass,
        )

    # Classification: both frequency and DC-link criteria must pass for PASS
    criteria_ok = bool(result["frequency_criteria_pass"] and result["vdc_criteria_pass"])
    if step == 0:
        criteria_ok = bool(
            result["vdc_post_min_v"] >= vdc_min_req
            and abs(result["frequency_final_hz"] - freq) <= DEFAULT_TUNING_CRITERIA.max_frequency_drop_hz
        )
    result["status"] = "PASS" if criteria_ok else "REVIEW"
    if bess and not result["bess_limits_pass"]:
        result["status"] = "FAIL"

    if return_traces:
        traces = {
            "t": t,
            "vdc": vdc,
            "frequency_hz": f,
            "rocof_hz_s": freq_dot,
            "pcc_power_w": pcc,
            "bridge_power_w": bridge,
            "pv_dc_power_w": p_pv_dc,
            "modulation": modulation,
            "pcc_v_rms_inst": np.sqrt(voltage_sq),
            "i_bess_a": batt_i,
            "p_bess_dc_w": batt_p,
        }
        return result, traces
    return result


def quantify_40pct_limitation(records_6p5s: list[dict[str, Any]]) -> dict[str, Any]:
    """Quantify the physical root cause of the +40% no-BESS REVIEW at 60 Hz and 50 Hz."""
    ref_model = Microgrid()
    g_w_m2 = float(MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)
    t_c = float(MICROGRID_TEMPERATURE_C_DEFAULT)
    v_grid = np.linspace(250.0, 410.0, 1601)
    p_pv_grid = np.array([v * ref_model.plant.pv_current(float(v), g_w_m2, t_c) for v in v_grid])
    mpp_idx = int(np.argmax(p_pv_grid))
    v_mpp = float(v_grid[mpp_idx])
    p_pv_mpp_dc = float(p_pv_grid[mpp_idx])
    p_ac_max_from_pv = p_pv_mpp_dc * float(MICROGRID_ETA_DEFAULT)

    vdc_min_req = float(required_vdc_for_vln_rms(GRID_V_LN_RMS_DEFAULT, INVERTER_MODULATION_INDEX_MAX_DEFAULT))
    ipv_at_vdc_min_req = float(ref_model.plant.pv_current(vdc_min_req, g_w_m2, t_c))
    p_pv_at_vdc_min_req = vdc_min_req * ipv_at_vdc_min_req
    p_ac_at_vdc_min_req = p_pv_at_vdc_min_req * float(MICROGRID_ETA_DEFAULT)

    by_key = {(int(round(r["frequency_hz"])), round(r["step"], 2), r["bess"]): r for r in records_6p5s}
    r60 = by_key[(60, 0.4, False)]
    r50 = by_key[(50, 0.4, False)]

    e_cap_pre_to_min_req_60_j = 0.5 * float(DCLINK_CAP_F_DEFAULT) * (
        r60["vdc_pre_step_mean_v"] ** 2 - vdc_min_req**2
    )
    e_cap_pre_to_min_obs_60_j = 0.5 * float(DCLINK_CAP_F_DEFAULT) * (
        r60["vdc_pre_step_mean_v"] ** 2 - r60["vdc_post_min_v"] ** 2
    )
    e_cap_pre_to_min_req_50_j = 0.5 * float(DCLINK_CAP_F_DEFAULT) * (
        r50["vdc_pre_step_mean_v"] ** 2 - vdc_min_req**2
    )
    e_cap_pre_to_min_obs_50_j = 0.5 * float(DCLINK_CAP_F_DEFAULT) * (
        r50["vdc_pre_step_mean_v"] ** 2 - r50["vdc_post_min_v"] ** 2
    )

    return {
        "irradiance_w_per_m2": g_w_m2,
        "temperature_c": t_c,
        "inverter_eta": float(MICROGRID_ETA_DEFAULT),
        "dc_link_capacitance_f": float(DCLINK_CAP_F_DEFAULT),
        "vdc_min_required_for_110v_rms_at_m0p95_v": vdc_min_req,
        "pv_mpp_voltage_at_800w_m2_v": v_mpp,
        "pv_mpp_dc_power_at_800w_m2_w": p_pv_mpp_dc,
        "pv_max_ac_power_after_eta_w": p_ac_max_from_pv,
        "pv_dc_power_at_vdc_min_required_w": p_pv_at_vdc_min_req,
        "pv_ac_power_at_vdc_min_required_w": p_ac_at_vdc_min_req,
        "nominal_step_40pct_load_target_ at_110v_w": 4200.0,
        "ac_power_deficit_vs_4200w_at_mpp_w": 4200.0 - p_ac_max_from_pv,
        "ac_power_deficit_vs_4200w_at_vdc_min_req_w": 4200.0 - p_ac_at_vdc_min_req,
        "usable_capacitor_energy_above_modulation_limit_60hz_j": float(e_cap_pre_to_min_req_60_j),
        "observed_capacitor_energy_released_60hz_j": float(e_cap_pre_to_min_obs_60_j),
        "usable_capacitor_energy_above_modulation_limit_50hz_j": float(e_cap_pre_to_min_req_50_j),
        "observed_capacitor_energy_released_50hz_j": float(e_cap_pre_to_min_obs_50_j),
        "equilibrium_60hz": {
            "vdc_post_min_v": r60["vdc_post_min_v"],
            "vdc_final_v": r60["vdc_final_v"],
            "pcc_rms_last_v": r60["pcc_rms_last_v"],
            "pcc_power_mean_last_w": r60["pcc_power_mean_last_w"],
            "bridge_power_mean_last_w": r60["bridge_power_mean_last_w"],
            "pv_dc_power_mean_last_w": r60["pv_dc_power_mean_last_w"],
            "modulation_max": r60["modulation_max"],
            "modulation_limited_fraction_post": r60["modulation_limited_fraction_post"],
            "vdc_event_max_abs_deviation_pct": r60["vdc_event_max_abs_deviation_pct"],
        },
        "equilibrium_50hz": {
            "vdc_post_min_v": r50["vdc_post_min_v"],
            "vdc_final_v": r50["vdc_final_v"],
            "pcc_rms_last_v": r50["pcc_rms_last_v"],
            "pcc_power_mean_last_w": r50["pcc_power_mean_last_w"],
            "bridge_power_mean_last_w": r50["bridge_power_mean_last_w"],
            "pv_dc_power_mean_last_w": r50["pv_dc_power_mean_last_w"],
            "modulation_max": r50["modulation_max"],
            "modulation_limited_fraction_post": r50["modulation_limited_fraction_post"],
            "vdc_event_max_abs_deviation_pct": r50["vdc_event_max_abs_deviation_pct"],
        },
        "physical_explanation": (
            "At G = 800 W/m^2 and Tc = 25 C without BESS, the 10-series PV array "
            "maximum DC power is ~3972.3 W (~3853.1 W AC after eta = 0.97), whereas "
            "a +40% nominal-voltage load step demands 4200 W AC (~4330 W DC). "
            "The DC-link capacitor (Cdc = 2 mF) stores only ~35.9 J above the "
            "modulation threshold Vdc_min = 327.50 V. Once that buffer is exhausted "
            "within ~0.12 s after the step, Vdc drops below 327.50 V, the modulation "
            "index saturates at m_max = 0.95, and the synthesized AC voltage droops "
            "to ~101 V RMS until the constant-impedance R-L load power self-limits "
            "to ~3552 W (60 Hz) / ~3535 W (50 Hz), matching PV generation on the "
            "I-V current-source branch."
        ),
    }


def save_50_vs_60_figure(
    traces_map: dict[tuple[int, float, bool], dict[str, np.ndarray]],
    output_path: Path,
) -> Path:
    """Save a publication-grade 50 Hz vs 60 Hz dynamic comparison figure (6.5 s)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(3, 2, figsize=(13.5, 9.5), sharex=True)
    vdc_min_req = required_vdc_for_vln_rms(GRID_V_LN_RMS_DEFAULT, INVERTER_MODULATION_INDEX_MAX_DEFAULT)

    case_styles = [
        (0.0, False, "Nominal (0%)", "-", 1.3),
        (0.2, False, "Escalón +20% sin BESS", "--", 1.3),
        (0.4, False, "Escalón +40% sin BESS (REVIEW)", "-.", 1.4),
        (0.2, True, "Escalón +20% con BESS+PI", ":", 1.5),
        (0.4, True, "Escalón +40% con BESS+PI", "-", 1.8),
    ]

    for col, freq in enumerate((60, 50)):
        ax_f = axes[0, col]
        ax_vdc = axes[1, col]
        ax_p = axes[2, col]

        for step, bess, label, ls, lw in case_styles:
            key = (freq, step, bess)
            if key not in traces_map:
                continue
            tr = traces_map[key]
            t = tr["t"]
            df_mhz = (tr["frequency_hz"] - float(freq)) * 1000.0
            ax_f.plot(t, df_mhz, linestyle=ls, linewidth=lw, label=label)
            ax_vdc.plot(t, tr["vdc"], linestyle=ls, linewidth=lw, label=label)
            ax_p.plot(t, tr["pcc_power_w"] / 1000.0, linestyle=ls, linewidth=lw, label=label)

        ax_f.set_title(f"Variante {freq} Hz (M = 80, D = 1500)")
        ax_f.axhline(0.0, color="black", linewidth=0.7, alpha=0.5)
        ax_vdc.axhline(SIM_VDC0_V_DEFAULT, color="gray", linestyle="--", linewidth=0.9, label="Vdc ref (340 V)")
        ax_vdc.axhline(vdc_min_req, color="red", linestyle=":", linewidth=1.0, label="Umbral m=0.95 (327.5 V)")

        for ax in (ax_f, ax_vdc, ax_p):
            ax.axvline(T_STEP_S, color="black", linestyle="--", linewidth=0.8, alpha=0.6)
            ax.grid(True, alpha=0.3)

        ax_p.set_xlabel("Tiempo [s]")

    axes[0, 0].set_ylabel("Δf = f - f_nom [mHz]")
    axes[1, 0].set_ylabel("Tensión bus DC, Vdc [V]")
    axes[2, 0].set_ylabel("Potencia activa PCC [kW]")
    axes[0, 1].legend(loc="best", fontsize=7.5)
    axes[1, 1].legend(loc="best", fontsize=7.5)

    fig.suptitle("Auditoría dinámica pareada 60 Hz vs 50 Hz en horizonte de 6,5 s (VSG M=80, D=1500)", fontsize=12)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    a = Microgrid()
    b = Microgrid(load_frequency_hz=50)
    assert np.isclose(a._load_at_time(0).f_hz, 60.0)
    assert np.isclose(b._load_at_time(0).f_hz, 50.0)
    assert np.isclose(b._load_at_time(0).l_h / a._load_at_time(0).l_h, 1.2)
    assert np.isclose(b._load_at_time(0).r_ohm, a._load_at_time(0).r_ohm)
    assert np.isclose(b._load_at_time(0).q_3ph_var, a._load_at_time(0).q_3ph_var)
    try:
        Microgrid(load_frequency_hz=0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero frequency accepted")

    # 1. Run the 8 canonical paired scenarios + 2 severe (+40%) BESS+PI scenarios at 6.5 s
    results_6p5s: list[dict[str, Any]] = []
    traces_map: dict[tuple[int, float, bool], dict[str, np.ndarray]] = {}
    for freq in (60, 50):
        for step in (0.0, 0.2, 0.4):
            res, tr = run(freq, step, bess=False, t_end_s=T_END_6P5_S, return_traces=True)
            results_6p5s.append(res)
            traces_map[(freq, step, False)] = tr
            print(f"[6.5s] freq={freq} step={step} bess=False status={res['status']} vdc_post_min={res['vdc_post_min_v']:.2f}", flush=True)
        for step_bess in (0.2, 0.4):
            res, tr = run(freq, step_bess, bess=True, t_end_s=T_END_6P5_S, return_traces=True)
            results_6p5s.append(res)
            traces_map[(freq, step_bess, True)] = tr
            print(f"[6.5s] freq={freq} step={step_bess} bess=True status={res['status']} i_bess=[{res['bess_current_post_min_a']:.3f}, {res['bess_current_post_max_a']:.3f}]", flush=True)

    # Preserve the 8-scenario list in outputs/validation/vsg_50hz_interface.json (now at 6.5 s)
    canonical_8 = [r for r in results_6p5s if not (r["bess"] and np.isclose(r["step"], 0.4))]
    out_canonical = REPO_ROOT / "outputs" / "validation" / "vsg_50hz_interface.json"
    out_canonical.parent.mkdir(parents=True, exist_ok=True)
    out_canonical.write_text(json.dumps(canonical_8, indent=2) + "\n", encoding="utf-8")

    # Build paired 50 Hz vs 60 Hz comparison table
    by_cfg = {(int(round(r["frequency_hz"])), round(r["step"], 2), r["bess"]): r for r in results_6p5s}
    paired_comparisons = []
    for step, bess in ((0.0, False), (0.2, False), (0.4, False), (0.2, True), (0.4, True)):
        r60 = by_cfg[(60, step, bess)]
        r50 = by_cfg[(50, step, bess)]
        paired_comparisons.append({
            "step": step,
            "bess": bess,
            "status_60hz": r60["status"],
            "status_50hz": r50["status"],
            "delta_max_freq_drop_hz_50_minus_60": r50["max_frequency_drop_hz"] - r60["max_frequency_drop_hz"],
            "delta_rocof_abs_max_hz_s_50_minus_60": r50["rocof_post_abs_max_hz_s"] - r60["rocof_post_abs_max_hz_s"],
            "delta_vdc_pre_step_v_50_minus_60": r50["vdc_pre_step_mean_v"] - r60["vdc_pre_step_mean_v"],
            "delta_vdc_post_min_v_50_minus_60": r50["vdc_post_min_v"] - r60["vdc_post_min_v"],
            "delta_vdc_final_v_50_minus_60": r50["vdc_final_v"] - r60["vdc_final_v"],
            "delta_pcc_rms_last_v_50_minus_60": r50["pcc_rms_last_v"] - r60["pcc_rms_last_v"],
            "delta_pcc_power_last_w_50_minus_60": r50["pcc_power_mean_last_w"] - r60["pcc_power_mean_last_w"],
        })

    limitation_40pct = quantify_40pct_limitation(results_6p5s)
    fig_path = save_50_vs_60_figure(
        traces_map,
        REPO_ROOT / "outputs" / "validation" / "vsg_50hz_vs_60hz_6p5s.png",
    )

    # Save CSV summary
    csv_path = REPO_ROOT / "outputs" / "validation" / "vsg_50hz_interface_audit_6p5s.csv"
    csv_fields = [
        "frequency_hz", "step", "bess", "status", "t_end_s",
        "frequency_pre_step_hz", "frequency_post_min_hz", "frequency_post_max_hz",
        "max_frequency_drop_hz", "frequency_recovery_time_s", "rocof_post_abs_max_hz_s",
        "vdc_initial_v", "vdc_global_min_v", "vdc_global_min_time_s",
        "vdc_pre_step_mean_v", "vdc_post_min_v", "vdc_post_min_time_s",
        "vdc_post_max_v", "vdc_final_v", "vdc_event_max_abs_deviation_pct",
        "pcc_rms_pre_v", "pcc_rms_last_v", "pcc_power_mean_pre_w", "pcc_power_mean_last_w",
        "bridge_power_mean_last_w", "pv_dc_power_mean_last_w",
        "modulation_max", "modulation_limited_fraction_post",
        "bess_current_post_min_a", "bess_current_post_max_a", "bess_power_post_mean_w",
        "soc_min", "soc_max", "bess_limits_pass",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results_6p5s)

    audit_payload = {
        "study": "Phase 1 Audit and 6.5 s Regression of 50 Hz VSG Variant vs 60 Hz Baseline",
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "t_step_s": T_STEP_S,
        "t_end_s": T_END_6P5_S,
        "load_design_verification": {
            "v_ln_rms_v": GRID_V_LN_RMS_DEFAULT,
            "p_nom_3ph_w": MICROGRID_LOAD_P_NOM_W_DEFAULT,
            "power_factor_lagging": MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
            "r_ohm_60hz": float(a._load_at_time(0).r_ohm),
            "r_ohm_50hz": float(b._load_at_time(0).r_ohm),
            "l_mh_60hz": float(a._load_at_time(0).l_h * 1e3),
            "l_mh_50hz": float(b._load_at_time(0).l_h * 1e3),
            "x_ohm_60hz": float(2.0 * np.pi * 60.0 * a._load_at_time(0).l_h),
            "x_ohm_50hz": float(2.0 * np.pi * 50.0 * b._load_at_time(0).l_h),
            "lcl_x1_ohm_60hz": float(2.0 * np.pi * 60.0 * a.lcl.L1),
            "lcl_x1_ohm_50hz": float(2.0 * np.pi * 50.0 * b.lcl.L1),
            "lcl_x2_ohm_60hz": float(2.0 * np.pi * 60.0 * a.lcl.L2),
            "lcl_x2_ohm_50hz": float(2.0 * np.pi * 50.0 * b.lcl.L2),
        },
        "vdc_window_semantics_audit": (
            "In all no-BESS scenarios, Vdc starts at vdc_initial_v = 340.0 V at t = 0.0 s "
            "with zero AC inductor currents and capacitor voltages. During the initial "
            "startup transient (0 to 0.6 s), PV charging raises Vdc to its pre-step "
            "equilibrium (~379.31 V at 60 Hz, ~378.93 V at 50 Hz). Therefore, for nominal "
            "and +20% scenarios without BESS, the global minimum Vdc is 340.0 V at t = 0.0 s, "
            "whereas the post-step minimum Vdc (t >= 0.8 s) is 379.31/378.93 V (nominal) "
            "and 364.76/363.52 V (+20%). Both metrics are reported separately."
        ),
        "scenarios_6p5s": results_6p5s,
        "paired_50_vs_60_comparisons": paired_comparisons,
        "severe_40pct_limitation_analysis": limitation_40pct,
        "figure_path": str(fig_path),
        "csv_path": str(csv_path),
    }
    audit_json_path = REPO_ROOT / "outputs" / "validation" / "vsg_50hz_interface_audit_6p5s.json"
    audit_json_path.write_text(json.dumps(audit_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved: {out_canonical}, {audit_json_path}, {csv_path}, {fig_path}", flush=True)


if __name__ == "__main__":
    main()
