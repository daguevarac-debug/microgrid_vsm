"""BAT26-44: reproduce Obj1/Obj2 regressions and matched GFM+BESS-PI OFF/ON.

The 16-state pair differs only in the bess_enabled flag. No plant/controller
physics or historical BLAST results are modified. REVIEW is performance, not
a solver or invariant failure.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import (
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.gfm_controller import GFMController
from tuning_metrics import dc_link_performance_metrics, frequency_performance_metrics
from validation.validate_dc_link_pi_scenarios import (
    BASE_SCENARIO,
    T_END_S,
    build_model,
)
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)

OUT_PARENT = ROOT / "outputs" / "analysis" / "bat26_44_off_on"
SCRIPTS = (
    ("obj1", "validate_obj1_regression.py", ("PASS",)),
    ("gfm_obj2", "validate_gfm_integrated_system.py", ("PASS", "REVIEW")),
    ("physical_invariants", "validate_physical_invariants.py", ("PASS",)),
)
TOL = 1e-7


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _git_head() -> str | None:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _json_safe(obj):
    if isinstance(obj, np.generic):
        return _json_safe(obj.item())
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {key: _json_safe(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(value) for value in obj]
    return obj


def _run_existing(name: str, script: str, accepted: tuple[str, ...],
                  out: Path) -> tuple[dict, dict | None]:
    json_path = out / (name + ".json")
    cmd = [sys.executable, "-B", str(SRC / "validation" / script),
           "--output", str(json_path)]
    proc = subprocess.run(
        cmd, cwd=ROOT, text=True, capture_output=True, check=False,
        errors="replace", env=dict(os.environ, MPLBACKEND="Agg",
                                   PYTHONDONTWRITEBYTECODE="1"),
    )
    (out / (name + ".log")).write_text(
        proc.stdout + "\n" + proc.stderr, encoding="utf-8",
    )
    data = None
    parse_error = None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parse_error = str(exc)
    source_status = data.get("status") if isinstance(data, dict) else None
    accepted_status = proc.returncode == 0 and source_status in accepted
    row = {
        "name": name,
        "script": script,
        "source_status": source_status,
        "status": "PASS" if accepted_status else "FAIL",
        "exit_code": proc.returncode,
        "accepted_statuses": list(accepted),
        "result_file": json_path.name if data is not None else None,
        "log_file": name + ".log",
        "parse_error": parse_error,
    }
    return row, data


def _simulate_flag(enabled: bool, t_eval: np.ndarray) -> tuple[dict, np.ndarray]:
    model = build_model(BASE_SCENARIO)
    model.set_bess_enabled(enabled)
    initial = model.initial_state_with_bess(
        vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0,
    )
    sol = solve_ivp(
        model.system_dynamics,
        (float(SIM_T_START_S_DEFAULT), float(T_END_S)),
        initial,
        t_eval=t_eval,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    valid_solution = bool(
        sol.success and sol.y.shape == (16, len(t_eval))
        and np.all(np.isfinite(sol.y))
    )
    row = {
        "flag": "ON" if enabled else "OFF",
        "enabled": bool(enabled),
        "solver_success": bool(sol.success),
        "solver_message": str(sol.message),
        "finite_state_trajectory": bool(np.all(np.isfinite(sol.y))),
        "state_count": int(sol.y.shape[0]),
        "controller_class": type(model.controller).__name__,
        "controller_state_name": model.controller_state_name,
        "M": float(model.controller.frequency_dynamics.inertia_m),
        "D": float(model.controller.frequency_dynamics.damping_d),
        "pi_kp_w_per_v": float(model.dc_link_bess_pi.kp_w_per_v),
        "pi_ki_w_per_v_s": float(model.dc_link_bess_pi.ki_w_per_v_s),
        "t_start_s": float(SIM_T_START_S_DEFAULT),
        "t_end_s": float(T_END_S),
        "load_step_pct": float(BASE_SCENARIO.step_pct),
        "initial_state": [float(v) for v in initial],
        "status": "FAIL",
    }
    if not valid_solution:
        return row, np.asarray(initial, dtype=float)
    records = [
        model.integrated_signals(float(t), sol.y[:, idx])
        for idx, t in enumerate(sol.t)
    ]
    i_bess = np.asarray([float(a["i_bess"]) for a in records])
    p_bess = np.asarray([float(a["p_bess_dc"]) for a in records])
    soc = sol.y[12, :]
    soh = np.asarray([float(a["soh_bess"]) for a in records])
    vdc = sol.y[0, :]
    max_current = np.asarray([model._available_i_bess_max(float(x)) for x in soh])
    max_power = np.asarray([model._available_p_bess_max_w(float(x)) for x in soh])
    zero_when_off = bool(enabled or (
        np.all(np.abs(i_bess) <= 1e-12) and
        np.all(np.abs(p_bess) <= 1e-9) and
        np.allclose(soc, soc[0], atol=1e-12, rtol=0)
    ))
    bounds = bool(
        np.all(soc >= model.bess.soc_min - TOL)
        and np.all(soc <= model.bess.soc_max + TOL)
        and np.all(soh >= model.bess.soh_min - TOL)
        and np.all(soh <= 1.0 + TOL)
        and np.all(np.abs(i_bess) <= max_current + TOL)
        and np.all(np.abs(p_bess) <= max_power + TOL)
    )
    dc_identity = bool(np.allclose(p_bess, vdc * i_bess,
                                   atol=1e-7, rtol=1e-9))
    configured = bool(
        isinstance(model.controller, GFMController)
        and model.controller_state_name == "omega"
        and np.isclose(row["M"], GFM_SELECTED_M)
        and np.isclose(row["D"], GFM_SELECTED_D)
        and np.isclose(row["pi_kp_w_per_v"], PI_KP_W_PER_V)
        and np.isclose(row["pi_ki_w_per_v_s"], PI_KI_W_PER_V_S)
    )
    freq = frequency_performance_metrics(
        sol.t, sol.y[10, :] / (2 * np.pi),
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    dc = dc_link_performance_metrics(
        sol.t, vdc, MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    invariant_ok = bool(configured and bounds and dc_identity and zero_when_off)
    status = ("FAIL" if not invariant_ok else
              "PASS" if freq["frequency_criteria_pass"]
              and dc["vdc_criteria_pass"] else "REVIEW")
    row.update({
        "status": status,
        "invariants_pass": invariant_ok,
        "configuration_pass": configured,
        "bess_operational_limits_pass": bounds,
        "dc_power_identity_pass": dc_identity,
        "off_zero_current_and_power_pass": zero_when_off,
        "max_abs_i_bess_a": float(np.max(np.abs(i_bess))),
        "max_abs_p_bess_dc_w": float(np.max(np.abs(p_bess))),
        "soc_initial": float(soc[0]),
        "soc_final": float(soc[-1]),
        "soh_initial": float(soh[0]),
        "soh_final": float(soh[-1]),
        "vdc_event_max_abs_deviation_pct":
            float(dc["vdc_event_max_abs_deviation_pct"]),
        "max_frequency_drop_hz": float(freq["max_frequency_drop_hz"]),
        "frequency_criteria_pass": bool(freq["frequency_criteria_pass"]),
        "vdc_criteria_pass": bool(dc["vdc_criteria_pass"]),
    })
    return row, np.asarray(initial, dtype=float)


def _matched_comparison() -> dict:
    t_eval = np.linspace(float(SIM_T_START_S_DEFAULT), float(T_END_S), 1301)
    off, y0_off = _simulate_flag(False, t_eval)
    on, y0_on = _simulate_flag(True, t_eval)
    matched = bool(
        np.array_equal(y0_off, y0_on)
        and off["state_count"] == on["state_count"] == 16
        and off["controller_state_name"] == on["controller_state_name"] == "omega"
        and off["M"] == on["M"] == GFM_SELECTED_M
        and off["D"] == on["D"] == GFM_SELECTED_D
        and off["pi_kp_w_per_v"] == on["pi_kp_w_per_v"] == PI_KP_W_PER_V
        and off["pi_ki_w_per_v_s"] == on["pi_ki_w_per_v_s"] == PI_KI_W_PER_V_S
        and off["load_step_pct"] == on["load_step_pct"] == BASE_SCENARIO.step_pct
    )
    valid = matched and off["status"] != "FAIL" and on["status"] != "FAIL"
    status = ("FAIL" if not valid else
              "PASS" if off["status"] == on["status"] == "PASS" else "REVIEW")
    difference = None
    if valid:
        difference = {
            "vdc_event_deviation_on_minus_off_pct":
                on["vdc_event_max_abs_deviation_pct"]
                - off["vdc_event_max_abs_deviation_pct"],
            "frequency_drop_on_minus_off_hz":
                on["max_frequency_drop_hz"] - off["max_frequency_drop_hz"],
            "bess_reduces_vdc_deviation":
                on["vdc_event_max_abs_deviation_pct"]
                <= off["vdc_event_max_abs_deviation_pct"],
            "bess_reduces_frequency_drop":
                on["max_frequency_drop_hz"] <= off["max_frequency_drop_hz"],
        }
    return {
        "status": status,
        "matched_except_bess_enabled": matched,
        "fixed_architecture": "GFM+BESS+external_PI_16_states",
        "step_pct": float(BASE_SCENARIO.step_pct),
        "off": off,
        "on": on,
        "difference": difference,
        "note": "An improvement is measured, not required for software PASS.",
    }


def main() -> int:
    out = OUT_PARENT / datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ",
    )
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "task": "BAT26-44",
        "status": "IN_PROGRESS",
        "scope": "synthetic software regression; not experimental BESS or DC/DC",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "python_version": sys.version.split()[0],
        "hashes": {
            str(path): _sha256(ROOT / path)
            for path in (
                "AGENTS.md", "src/microgrid.py", "src/microgrid_bess_pi.py",
                "src/controllers/gfm_controller.py",
                "src/controllers/dc_link_bess_pi.py",
                "src/validation/validate_obj1_regression.py",
                "src/validation/validate_gfm_integrated_system.py",
                "src/validation/validate_physical_invariants.py",
            )
        },
        "regressions": [],
        "matched_off_on": None,
    }
    raw = {}
    for name, script, acceptable in SCRIPTS:
        entry, data = _run_existing(name, script, acceptable, out)
        report["regressions"].append(entry)
        raw[name] = data
        print(name, entry["status"], entry["source_status"], flush=True)

    try:
        gfm = raw.get("gfm_obj2")
        if not isinstance(gfm, dict):
            raise ValueError("GFM integrated JSON is absent")
        match = next(
            item for item in gfm["scenarios"]
            if item.get("scenario") == "bess_vs_no_bess"
        )
        report["historical_12_vs_16_comparison"] = {
            "status": match["status"],
            "comparison_execution_pass": match["comparison_execution_pass"],
            "same_load_profile": match["same_load_profile"],
            "both_gfm_active": match["both_gfm_active"],
            "caveat": "12-state OFF vs 16-state ON is not a single-flag experiment.",
        }
        if not match["comparison_execution_pass"]:
            raise ValueError("Legacy GFM OFF/ON comparison failed execution checks")
        report["matched_off_on"] = _matched_comparison()
    except Exception as exc:
        report["matched_off_on"] = {"status": "FAIL", "error": str(exc)}
    statuses = [row["status"] for row in report["regressions"]]
    statuses.append(report["matched_off_on"]["status"])
    report["status"] = (
        "FAIL" if "FAIL" in statuses else
        "PASS" if all(s == "PASS" for s in statuses) else "REVIEW"
    )
    path = out / "summary.json"
    path.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n", encoding="utf-8",
    )
    print("BAT26-44:", report["status"], "| summary:", path.relative_to(ROOT))
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
