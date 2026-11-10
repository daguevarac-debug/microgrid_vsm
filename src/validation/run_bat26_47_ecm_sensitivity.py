"""BAT26-47: 1RC sensitivity without inventing experimental validation.

Run under the main microgrid Python. All cases use the same existing battery
ECM, with independently initialized checkpoints from BAT26-45 (rounded).
Variation of k_R is an illustrative perturbation, NOT a calibrated interval.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.compare_bess_soh_scenarios import _build_bess_for_soh
from validation.run_bat26_46_soh_levels import BAT45_ROUNDED_CAPACITIES

OUTPUT_ROOT = ROOT / "outputs" / "analysis" / "bat26_47_ecm_sensitivity"
DURATION_S = 3600.0
SOC_INITIAL = 0.6
CURRENTS_A = (-8.0, 4.0, 8.0, 16.0)
MAX_STEPS_S = (120.0, 60.0, 30.0, 15.0)
R0_SENSITIVITY_FACTORS = (0.0, 1.0, 2.0)
RTOL = 1e-9
ATOL = 1e-11


def git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def simulate(capacity_ah: float, current_a: float, max_step_s: float,
             *, k_r: float = 1.0) -> dict:
    """Integrate the unaltered 1RC equations on the battery-port side."""
    if capacity_ah <= 0 or current_a not in CURRENTS_A or max_step_s not in MAX_STEPS_S:
        raise ValueError("scenario outside the preregistered sweep")
    if k_r not in R0_SENSITIVITY_FACTORS:
        raise ValueError("k_R outside the preregistered sweep")

    model = _build_bess_for_soh(capacity_ah / 66.0)
    model.r0_soh_sensitivity = k_r  # one local scenario instance, NOT production config
    x0 = model.initial_state_with_degradation(
        soc=SOC_INITIAL, v_rc=0.0, z_deg=0.0,
    )
    t_eval = np.linspace(0.0, DURATION_S, 121)
    sol = solve_ivp(
        lambda t, y: model.rhs(
            t=t, x=y, i_bess=current_a,
            soh=model.soh_from_z_deg(float(y[2])),
        ),
        (0.0, DURATION_S), x0, t_eval=t_eval,
        rtol=RTOL, atol=ATOL, max_step=max_step_s,
    )
    if not sol.success or sol.y.shape != (3, len(t_eval)):
        raise RuntimeError("1RC solver failure")
    soc, vrc, zdeg = sol.y
    soh = np.asarray([model.soh_from_z_deg(float(z)) for z in zdeg])
    voltage = np.asarray([
        model.terminal_voltage(soc=float(s), v_rc=float(v),
                               i_bess=current_a, soh=float(h))
        for s, v, h in zip(soc, vrc, soh)
    ])
    q_initial = model.effective_capacity_ah(soh=model.soh_init_case)
    current_limit = 66.0 * soh
    checks = {
        "finite_states": bool(np.all(np.isfinite(sol.y)) and np.all(np.isfinite(voltage))),
        "soc_in_operating_bounds": bool(np.all(soc >= model.soc_min - 1e-9)
                                        and np.all(soc <= model.soc_max + 1e-9)),
        "soh_in_operating_bounds": bool(np.all(soh >= model.soh_min)
                                        and np.all(soh <= 1.0)),
        "current_within_model_limit": bool(np.all(abs(current_a) <= current_limit + 1e-9)),
        "voltage_positive": bool(np.all(voltage > 0.0)),
        "signed_soc_response": bool(
            (current_a > 0 and soc[-1] < soc[0])
            or (current_a < 0 and soc[-1] > soc[0])
        ),
        "throughput_match": bool(abs(zdeg[-1] - abs(current_a)) < 1e-8),
    }
    if not all(checks.values()):
        raise RuntimeError(f"1RC invariant failed for Q={capacity_ah}, I={current_a}: {checks}")
    energy_signed_wh = float(np.trapezoid(voltage * current_a, t_eval) / 3600.0)
    return {
        "capacity_ah": float(capacity_ah),
        "soh_initial_pct": 100.0 * capacity_ah / 66.0,
        "current_battery_port_a": float(current_a),
        "max_solver_step_s": float(max_step_s),
        "k_r_assumption": float(k_r),
        "soc_final": float(soc[-1]),
        "delta_soc_pp": 100.0 * float(soc[-1] - soc[0]),
        "qeff_initial_ah": float(q_initial),
        "voltage_final_v": float(voltage[-1]),
        "energy_terminal_signed_wh": energy_signed_wh,
        "charge_throughput_ah": float(zdeg[-1]),
        "checks": checks,
    }


def summarize_step_sensitivity(results: list[dict]) -> list[dict]:
    """Differences relative to the finest step; no fabricated acceptance tolerance."""
    baseline = {
        (r["capacity_ah"], r["current_battery_port_a"]): r for r in results
        if r["max_solver_step_s"] == min(MAX_STEPS_S)
    }
    rows = []
    for r in results:
        reference = baseline[(r["capacity_ah"], r["current_battery_port_a"])]
        rows.append({
            "capacity_ah": r["capacity_ah"],
            "current_battery_port_a": r["current_battery_port_a"],
            "max_solver_step_s": r["max_solver_step_s"],
            "delta_soc_final_vs_15s_pp":
                100.0 * (r["soc_final"] - reference["soc_final"]),
            "delta_terminal_energy_vs_15s_wh":
                r["energy_terminal_signed_wh"] - reference["energy_terminal_signed_wh"],
        })
    return rows


def csv_output(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    out = OUTPUT_ROOT / datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ"
    )
    out.mkdir(parents=True, exist_ok=False)

    capacities = [q for cycles, q in BAT45_ROUNDED_CAPACITIES if cycles in (0, 1000)]
    result = {
        "task": "BAT26-47", "component": "1RC_sensitivity",
        "status": "IN_PROGRESS",
        "scope": "Numerical/synthetic sensitivity; no independent experimental validation",
        "git_head": git_sha(),
        "python_version": sys.version.split()[0],
        "scenario": {
            "checkpoint_capacities_ah": capacities,
            "checkpoint_source": "BAT26-45 rounded report",
            "currents_a": CURRENTS_A,
            "max_steps_s": MAX_STEPS_S,
            "k_R_factors": R0_SENSITIVITY_FACTORS,
            "k_R_label": "Illustrative 0 / 1 / 2, NOT a confidence interval",
            "t_end_s": DURATION_S,
            "soc_initial": SOC_INITIAL,
            "rtol": RTOL, "atol": ATOL,
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "outcome": {},
        "error": None,
        "experimental_validation": "NOT_EVALUABLE",
    }
    try:
        records = [
            simulate(q, i, h)
            for q in capacities for i in CURRENTS_A for h in MAX_STEPS_S
        ]
        step_rows = summarize_step_sensitivity(records)
        kr_rows = [
            simulate(q, 8.0, 60.0, k_r=k)
            for q in capacities for k in R0_SENSITIVITY_FACTORS
        ]
        for kind, rows in (("steps", step_rows), ("r0", kr_rows)):
            cleaned = [
                {k: v for k, v in row.items() if k != "checks"}
                for row in rows
            ]
            csv_output(out / f"{kind}.csv", cleaned)
        result["outcome"] = {
            "case_count": len(records),
            "parameter_sensitivity_count": len(kr_rows),
            "step_sensitivity": step_rows,
            "r0_sensitivity": kr_rows,
            "max_abs_delta_soc_final_pp": max(
                abs(x["delta_soc_final_vs_15s_pp"]) for x in step_rows
            ),
            "max_abs_delta_terminal_energy_wh": max(
                abs(x["delta_terminal_energy_vs_15s_wh"]) for x in step_rows
            ),
            "all_invariants_pass": True,
        }
        result["status"] = "PASS"
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
    (out / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"BAT26-47 ECM {result['status']} | {out.relative_to(ROOT)}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
