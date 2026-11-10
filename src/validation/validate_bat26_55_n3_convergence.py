"""BAT26-55 N3: RK45 convergence for the 15-state Leaf pack–bus–GFM model."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import platform
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import scipy
from scipy.integrate import solve_ivp

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.validate_bat26_55_n1_profile import (
    ATOL, D, MAX_STEP_S, M, P_REF_W, QEFF_AH, RTOL, SAMPLE_DT_S,
    SOC0, T_END_S, build_battery, fixture_parameters, irradiance_profile,
    load_profile,
)
from bess.leaf_48module_pack import Leaf48ModulePack
from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS

OUTPUT = ROOT / "outputs" / "validation" / "bat26_55_n3_convergence.json"
REFINED = {"method": "RK45", "rtol": 1e-7, "atol": 1e-10, "max_step_s": 2.5e-5}
REL_TOL = 0.01
# Grid spacing is 0.5 ms: a one-grid-cell window change is the resolution floor.
ABS_TOL = {"window_duration_s": SAMPLE_DT_S, "energy_Wh": 7e-4,
           "frequency_deviation_Hz": 1e-5, "state_zdeg_Ah": 1e-12}


def make_model():
    pack = Leaf48ModulePack(q_init_case_ah=QEFF_AH)
    model = MicrogridWithBESS(
        controller=GFMController(p_ref=P_REF_W, inertia_m=M, damping_d=D),
        bess_model=build_battery(QEFF_AH), irradiance_profile=irradiance_profile,
        load_profile=load_profile, leaf_pack=pack,
        dcdc_parameters=fixture_parameters(pack), capacity_snapshot=pack.capacity(),
        aging_mode="blast", blast_profile_kind="synthetic",
    )
    return model, pack


def longest_window(mask: np.ndarray, t: np.ndarray) -> dict[str, float | None]:
    ids = np.flatnonzero(mask)
    if not ids.size:
        return {"duration_s": 0.0, "start_s": None, "end_s": None}
    groups = np.split(ids, np.where(np.diff(ids) > 1)[0] + 1)
    selected = max(groups, key=len)
    return {"duration_s": float(t[selected[-1]] - t[selected[0]]),
            "start_s": float(t[selected[0]]), "end_s": float(t[selected[-1]])}


def run_case(name: str, config: dict[str, float]) -> dict[str, object]:
    model, pack = make_model()
    initial = model.initial_state_with_bess()
    if len(initial) != 15 or initial[12] != SOC0 or initial[14] != 0.0:
        raise AssertionError("Unexpected 15-state initial condition")
    stage_min = math.inf
    stage_negative_count = 0

    def rhs(t, y):
        nonlocal stage_min, stage_negative_count
        z = float(y[14])
        stage_min = min(stage_min, z)
        stage_negative_count += int(z < 0.0)
        return model.system_dynamics(t, y)

    start = time.perf_counter()
    solution = solve_ivp(rhs, (0.0, T_END_S), initial, method="RK45",
                         rtol=config["rtol"], atol=config["atol"],
                         max_step=config["max_step_s"], dense_output=True)
    elapsed = time.perf_counter() - start
    if not solution.success or solution.sol is None:
        raise RuntimeError(f"{name} solver failed: {solution.message}")
    # Identical output grid for both integrations, independent of accepted steps.
    t = np.linspace(0.0, T_END_S, round(T_END_S / SAMPLE_DT_S) + 1)
    y = solution.sol(t)
    signals = [model.integrated_signals(float(tt), y[:, k]) for k, tt in enumerate(t)]
    value = lambda key: np.asarray([float(row[key]) for row in signals])
    vdc, ip, ib = value("Vdc"), value("i_pack"), value("i_bus")
    pp, pb, loss = value("p_pack"), value("p_bus"), value("p_dcdc_loss")
    vpack, soc = value("v_pack"), value("soc_bess")
    frequency = y[10] / (2 * math.pi)
    freq_deviation = float(np.max(np.abs(frequency - 60.0)))
    # Compute windows on the full shared grid, then clip to the declared phases.
    charge_mask = (ip < 0) & (ib < 0) & (pb < 0) & (t >= .45) & (t < .8)
    discharge_mask = (ip > 0) & (ib > 0) & (pb > 0) & (t >= .85) & (t < 1.2)
    charge = longest_window(charge_mask, t)
    discharge = longest_window(discharge_mask, t)
    energy_pack = float(np.trapezoid(pp, t) / 3600)
    energy_bus = float(np.trapezoid(pb, t) / 3600)
    energy_loss = float(np.trapezoid(loss, t) / 3600)
    absolute_energy = float(np.trapezoid(np.abs(pp) + np.abs(pb), t) / 3600)
    balance_residual = energy_pack - energy_bus - energy_loss
    power_residual = pp - pb - loss
    bus_residual = pb - vdc * ib
    states_accepted = solution.y
    checks = {
        "solver_success": bool(solution.success), "state_count_15": states_accepted.shape[0] == 15,
        "accepted_states_finite": bool(np.isfinite(states_accepted).all()),
        "sampled_states_finite": bool(np.isfinite(y).all()), "Vdc_positive": bool(np.all(vdc > 0)),
        "SoC_in_bounds": bool(np.all((soc >= pack.soc_min - 1e-9) & (soc <= pack.soc_max + 1e-9))),
        "zdeg_accepted_nonnegative": bool(np.min(states_accepted[14]) >= 0),
        "pack_voltage_in_envelope": bool(np.all((vpack >= pack.minimum_voltage_v) & (vpack <= pack.maximum_voltage_v))),
        "currents_within_limits": bool(np.max(np.abs(ip)) <= 10 + 1e-8 and np.max(np.abs(ib)) <= 20 + 1e-8),
        "bus_power_within_limit": bool(np.max(np.abs(pb)) <= 5000 + 1e-8),
        "losses_nonnegative": bool(np.all(loss >= -1e-12)),
        "power_balance": bool(np.max(np.abs(power_residual)) <= 1e-8 + 1e-10 * max(1., float(np.max(np.abs(pp))))),
        "bus_power_identity": bool(np.max(np.abs(bus_residual)) <= 1e-8 + 1e-10 * max(1., float(np.max(np.abs(pb))))),
        "energy_balance_0p1pct": bool(abs(balance_residual) <= .001 * absolute_energy),
        "charge_window_ge_0p1s": charge["duration_s"] >= .1,
        "discharge_window_ge_0p1s": discharge["duration_s"] >= .1,
    }
    return {
        "configuration": config, "success": bool(solution.success), "message": str(solution.message),
        "nfev": int(solution.nfev), "accepted_steps": int(len(solution.t) - 1),
        "elapsed_s": elapsed, "minimum_internal_stage_zdeg_Ah": float(stage_min),
        "negative_internal_stage_count": stage_negative_count,
        "minimum_accepted_zdeg_Ah": float(np.min(states_accepted[14])),
        "metrics": {
            "Vdc_min_V": float(np.min(vdc)), "Vdc_max_V": float(np.max(vdc)),
            "frequency_max_deviation_Hz": freq_deviation,
            "I_pack_peak_abs_A": float(np.max(np.abs(ip))),
            "I_bus_peak_abs_A": float(np.max(np.abs(ib))),
            "absolute_transferred_energy_Wh": absolute_energy,
            "pack_energy_signed_Wh": energy_pack, "bus_energy_signed_Wh": energy_bus,
            "loss_energy_Wh": energy_loss, "energy_balance_residual_Wh": balance_residual,
            "max_power_balance_residual_W": float(np.max(np.abs(power_residual))),
            "max_bus_power_identity_residual_W": float(np.max(np.abs(bus_residual))),
            "SoC_final": float(soc[-1]),
            "minimum_accepted_zdeg_Ah": float(np.min(states_accepted[14])),
            "charge_window": charge,
            "discharge_window": discharge,
            "charge_classified_samples": int(np.count_nonzero((ip < 0) & (ib < 0) & (pb < 0))),
            "discharge_classified_samples": int(np.count_nonzero((ip > 0) & (ib > 0) & (pb > 0))),
        },
        "checks": checks,
    }


def compare(reference: dict, refined: dict) -> dict[str, object]:
    a, b = reference["metrics"], refined["metrics"]
    keys = ("Vdc_min_V", "Vdc_max_V", "frequency_max_deviation_Hz", "I_pack_peak_abs_A",
            "I_bus_peak_abs_A", "absolute_transferred_energy_Wh", "pack_energy_signed_Wh",
            "bus_energy_signed_Wh", "loss_energy_Wh", "SoC_final",
            "minimum_accepted_zdeg_Ah")
    differences = {}
    passed = True
    for key in keys:
        av, bv = float(a[key]), float(b[key])
        absolute = abs(bv - av)
        relative = absolute / abs(av) if av else None
        tol = (ABS_TOL["frequency_deviation_Hz"] if key == "frequency_max_deviation_Hz"
               else ABS_TOL["energy_Wh"] if "energy" in key.lower()
               else ABS_TOL["state_zdeg_Ah"] if "zdeg" in key.lower() else 1e-8)
        ok = absolute <= tol if abs(av) < tol else relative < REL_TOL
        differences[key] = {"reference": av, "refined": bv, "absolute": absolute,
                            "relative": relative, "criterion": "absolute" if abs(av) < tol else "relative",
                            "tolerance": tol if abs(av) < tol else REL_TOL, "pass": ok}
        passed &= ok
    for key in ("charge_window", "discharge_window"):
        av, bv = a[key]["duration_s"], b[key]["duration_s"]
        delta = abs(bv - av)
        ok = delta <= ABS_TOL["window_duration_s"]
        differences[key] = {"reference_s": av, "refined_s": bv, "absolute_s": delta,
                            "relative": delta / abs(av) if av else None,
                            "criterion": "absolute", "tolerance_s": ABS_TOL["window_duration_s"], "pass": ok}
        passed &= ok
    classifications_same = (
        (a["charge_classified_samples"] > 0) == (b["charge_classified_samples"] > 0)
        and (a["discharge_classified_samples"] > 0) == (b["discharge_classified_samples"] > 0)
        and a["charge_window"]["duration_s"] > 0 and b["charge_window"]["duration_s"] > 0
        and a["discharge_window"]["duration_s"] > 0 and b["discharge_window"]["duration_s"] > 0
    )
    return {"status": "PASS" if passed and classifications_same else "FAIL",
            "relative_limit": REL_TOL, "absolute_tolerances": ABS_TOL,
            "metric_differences": differences,
            "charge_discharge_classification_unchanged": classifications_same}


def zdeg_probes() -> dict[str, object]:
    model, _ = make_model()
    x = model.initial_state_with_bess(); x[0] = 330.0
    zero_rhs = np.asarray(model.system_dynamics(0.0, x))
    samples = []
    for z in (-1.01e-9, -1e-9, -1e-10, -1e-12, -1e-13, -1e-15, 0.0, 1e-15):
        trial = x.copy(); trial[14] = z
        try:
            rhs = np.asarray(model.system_dynamics(0.0, trial))
            samples.append({"zdeg_Ah": z, "accepted_by_rhs": True,
                            "max_abs_rhs_delta": float(np.max(np.abs(rhs - zero_rhs)))})
        except ValueError as exc:
            samples.append({"zdeg_Ah": z, "accepted_by_rhs": False, "error": str(exc)})
    # Replay the N2 near-zero initial condition over only 2 ms, varying the
    # diagnostic rejection threshold without changing the production RHS.
    short_probes = []
    for threshold in (1e-9, 1e-10, 1e-13):
        probe_model, _ = make_model()
        probe_x = probe_model.initial_state_with_bess(); probe_x[12] = .90; probe_x[0] = 339.999
        stage_min = math.inf
        probe_start = time.perf_counter()
        def probe_rhs(t, y):
            nonlocal stage_min
            stage_min = min(stage_min, float(y[14]))
            if y[14] < -threshold:
                raise ValueError(f"probe threshold {threshold:g} Ah crossed by z_deg={y[14]!r}")
            return probe_model.system_dynamics(t, y)
        try:
            short = solve_ivp(probe_rhs, (0.0, .002), probe_x, method="RK45",
                              rtol=RTOL, atol=ATOL, max_step=MAX_STEP_S)
            short_probes.append({"reject_threshold_Ah": threshold, "completed": bool(short.success),
                                 "nfev": int(short.nfev), "minimum_internal_stage_zdeg_Ah": float(stage_min),
                                 "minimum_accepted_zdeg_Ah": float(np.min(short.y[14])),
                                 "elapsed_s": time.perf_counter() - probe_start})
        except ValueError as exc:
            short_probes.append({"reject_threshold_Ah": threshold, "completed": False,
                                 "minimum_internal_stage_zdeg_Ah": float(stage_min),
                                 "error": str(exc)})
    # The largest possible SoH perturbation represented by clamping the full band.
    k_deg = model.bess.k_deg
    return {"tolerance_band_Ah": 1e-9, "refined_atol_Ah": REFINED["atol"],
            "band_to_refined_atol_ratio": 10.0,
            "max_abs_SoH_effect_from_band": float(k_deg * 1e-9),
            "max_abs_Qeff_effect_Ah": float(model.bess.q_nom_ref_ah * k_deg * 1e-9),
            "rhs_value_probes": samples, "short_near_zero_integrations": short_probes,
            "diagnosis": "The 1e-9 Ah production band is 10x refined atol; short N2-boundary probes quantify sensitivity. Negative RK stages are trial values; accepted zdeg remains nonnegative. The band changes no physical law and its maximum SoH/Qeff effect is quantified above."}


def main() -> int:
    started_utc = datetime.now(timezone.utc)
    clock = time.perf_counter()
    ref_config = {"method": "RK45", "rtol": RTOL, "atol": ATOL, "max_step_s": MAX_STEP_S}
    report = {"task": "BAT26-55 N3 numerical convergence", "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "command": sys.argv, "utc_start": started_utc.isoformat(),
              "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
              "model": {"controller": "GFMController", "M": M, "D": D, "P_ref_W": P_REF_W,
                        "qeff_Ah": QEFF_AH, "SoC_initial": SOC0, "horizon_s": T_END_S,
                        "state_count": 15, "frequency": "x[10]/(2*pi)"},
              "profile": "N1 profile E; irradiance/load transitions at 0.4/0.8 s; identical 0.5 ms evaluation grid",
              "scope": "internal numerical evidence; hypothetical DC/DC fixture; no hardware/HIL claims",
              "acceptance_criteria": {
                  "PASS": "Both solves succeed; all physical/integrity checks pass; relative differences <1% for significant metrics and declared absolute tolerances for near-zero metrics; classifications unchanged.",
                  "REVIEW": "Numerical checks may pass while unmodelled design limitations remain; reported separately.",
                  "FAIL": "Solver failure, invariant failure, classification change, or convergence criterion failure.",
              },
              "tolerances_history": {"previous_plan_refined_atol": 1e-9,
                                     "executed_refined_atol": REFINED["atol"],
                                     "reason": "Corrected to the explicitly requested 1e-10; the 1e-9 plan line was stale."}}
    try:
        report["reference"] = run_case("reference", ref_config)
        report["refined"] = run_case("refined", REFINED)
        report["comparison"] = compare(report["reference"], report["refined"])
        report["zdeg_audit"] = zdeg_probes()
        physical_pass = all(all(case["checks"].values()) for case in (report["reference"], report["refined"]))
        report["physical_checks_status"] = "PASS" if physical_pass else "FAIL"
        report["status"] = "PASS" if physical_pass and report["comparison"]["status"] == "PASS" else "FAIL"
        report["design_review"] = {
            "status": "REVIEW",
            "reason": "No upper DC bus voltage protection is modelled; the observed Vdc maximum is numerical evidence, not a safety assessment.",
        }
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = repr(exc)
    report["utc_end"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_total_s"] = time.perf_counter() - clock
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"output_path={OUTPUT}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
