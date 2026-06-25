"""Close Task 5.3 frequency and DC-link performance checks.

For each required GFM+BESS+PI scenario this script:

1. validates the frequency record with the canonical Activity 2.3 definitions
   at the selected point (M, D) = (80, 1500);
2. confirms DC-link maximum event deviation and minimum voltage;
3. measures DC-link recovery into the existing event-relative ±5% band,
   requiring entry within 5.0 s and continuous residence for 0.50 s.

The DC-link recovery check applies the Task 4.1 common recovery horizon and
continuous-dwell requirement to the repository's current event-relative Vdc
acceptance band. It does not change controller parameters or plant equations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from tuning_metrics import (
    DEFAULT_TUNING_CRITERIA,
    dc_link_performance_metrics,
    frequency_performance_metrics,
)
from validation.validate_activity_2_3_frequency_metric import (
    EXPECTED_SELECTED_D,
    EXPECTED_SELECTED_M,
    validate_frequency_record,
)
from validation.validate_dc_link_pi_scenarios import (
    OUTPUT_DIR,
    SCENARIOS,
    T_END_S,
    ScenarioSpec,
    build_model,
)


OUTPUT_PATH = OUTPUT_DIR / "task_5_3_frequency_vdc_closure.json"


def vdc_recovery_time_with_dwell(
    t: np.ndarray,
    vdc: np.ndarray,
    *,
    t_step_s: float,
    vdc_pre_step_v: float,
    band_pct: float,
    dwell_s: float,
) -> float:
    """Return first event-relative in-band time sustained for the full dwell."""
    time = np.asarray(t, dtype=float)
    voltage = np.asarray(vdc, dtype=float)
    if time.ndim != 1 or voltage.ndim != 1 or time.size != voltage.size:
        raise ValueError("t and vdc must be one-dimensional traces of equal length.")
    if time.size < 2 or not np.all(np.diff(time) > 0.0):
        raise ValueError("t must contain at least two strictly increasing samples.")
    if not np.all(np.isfinite(time)) or not np.all(np.isfinite(voltage)):
        raise ValueError("t and vdc must contain finite values.")
    if vdc_pre_step_v <= 0.0:
        raise ValueError("vdc_pre_step_v must be > 0.")
    if band_pct <= 0.0 or dwell_s <= 0.0:
        raise ValueError("band_pct and dwell_s must be > 0.")

    band_fraction = band_pct / 100.0
    lower = vdc_pre_step_v * (1.0 - band_fraction)
    upper = vdc_pre_step_v * (1.0 + band_fraction)
    post_indices = np.flatnonzero(time >= t_step_s)
    if post_indices.size == 0:
        raise ValueError("Trace must contain samples at or after t_step_s.")

    for start_index in post_indices:
        end_time = float(time[start_index]) + dwell_s
        end_index = int(np.searchsorted(time, end_time, side="left"))
        if end_index >= time.size:
            break
        interval = voltage[start_index : end_index + 1]
        if np.all((interval >= lower) & (interval <= upper)):
            return float(time[start_index] - t_step_s)
    return float("nan")


def validate_vdc_task_4_1(
    t: np.ndarray,
    vdc: np.ndarray,
    dc_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Validate Vdc deviation, minimum and recovery with existing limits."""
    criteria = DEFAULT_TUNING_CRITERIA
    recovery_time = vdc_recovery_time_with_dwell(
        t,
        vdc,
        t_step_s=MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
        vdc_pre_step_v=float(dc_metrics["vdc_pre_step_v"]),
        band_pct=criteria.max_vdc_event_deviation_pct,
        dwell_s=criteria.frequency_recovery_dwell_s,
    )
    recovery_pass = bool(
        np.isfinite(recovery_time)
        and recovery_time <= criteria.max_frequency_recovery_s
    )
    deviation_pass = bool(dc_metrics["vdc_event_deviation_pass"])
    minimum_pass = bool(dc_metrics["vdc_minimum_voltage_pass"])
    closure_pass = bool(deviation_pass and minimum_pass and recovery_pass)

    vdc_pre = float(dc_metrics["vdc_pre_step_v"])
    band_fraction = criteria.max_vdc_event_deviation_pct / 100.0
    return {
        "criteria_source": "Task 4.1",
        "recovery_interpretation": (
            "Task 4.1 common 5.0 s recovery horizon and 0.50 s dwell applied "
            "to the current event-relative Vdc acceptance band"
        ),
        "vdc_pre_step_v": vdc_pre,
        "vdc_event_max_abs_deviation_v": float(
            dc_metrics["vdc_event_max_abs_deviation_v"]
        ),
        "vdc_event_max_abs_deviation_pct": float(
            dc_metrics["vdc_event_max_abs_deviation_pct"]
        ),
        "vdc_event_deviation_limit_pct": float(
            criteria.max_vdc_event_deviation_pct
        ),
        "vdc_event_deviation_pass": deviation_pass,
        "vdc_min_post_step_v": float(dc_metrics["vdc_min_post_step_v"]),
        "vdc_min_required_v": float(dc_metrics["vdc_min_required_v"]),
        "vdc_minimum_voltage_pass": minimum_pass,
        "vdc_recovery_band_lower_v": float(vdc_pre * (1.0 - band_fraction)),
        "vdc_recovery_band_upper_v": float(vdc_pre * (1.0 + band_fraction)),
        "vdc_recovery_time_s": float(recovery_time),
        "vdc_recovery_time_limit_s": float(criteria.max_frequency_recovery_s),
        "vdc_recovery_dwell_s": float(criteria.frequency_recovery_dwell_s),
        "vdc_recovery_pass": recovery_pass,
        "vdc_task_4_1_closure_pass": closure_pass,
    }


def classify_closure_status(records: list[dict[str, Any]]) -> str:
    """Both required scenarios must pass both requested closure checks."""
    required_names = {spec.name for spec in SCENARIOS}
    actual_names = {str(record.get("scenario")) for record in records}
    if actual_names != required_names:
        return "FAIL"
    return (
        "PASS"
        if all(
            bool(record.get("activity_2_3_frequency_pass"))
            and bool(record.get("vdc_task_4_1_closure_pass"))
            for record in records
        )
        else "FAIL"
    )


def run_closure_scenario(spec: ScenarioSpec) -> dict[str, Any]:
    """Rerun one fixed scenario and evaluate the two closure subtasks."""
    model = build_model(spec)
    initial_state = model.initial_state_with_bess(
        vdc0=SIM_VDC0_V_DEFAULT,
        xi_bess_vdc0_v_s=0.0,
    )
    solution = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, T_END_S),
        initial_state,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    vdc = solution.y[0]
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    dc_metrics = dc_link_performance_metrics(
        solution.t,
        vdc,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    frequency_metrics = frequency_performance_metrics(
        solution.t,
        frequency_hz,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )

    frequency_record: dict[str, Any] = {
        "M": EXPECTED_SELECTED_M,
        "D": EXPECTED_SELECTED_D,
        **frequency_metrics,
    }
    frequency_audit = validate_frequency_record(
        frequency_record,
        label=spec.name,
    )
    activity_2_3_frequency_pass = bool(
        frequency_audit["selected_point_matches"]
        and frequency_audit["frequency_metric_coherent"]
        and frequency_audit["frequency_criteria_pass"]
    )
    vdc_audit = validate_vdc_task_4_1(solution.t, vdc, dc_metrics)

    return {
        "scenario": spec.name,
        "scenario_label": spec.label,
        "load_step_pct": float(spec.step_pct),
        "solver_success": bool(solution.success),
        "states_finite": bool(np.all(np.isfinite(solution.y))),
        "M": EXPECTED_SELECTED_M,
        "D": EXPECTED_SELECTED_D,
        "activity_2_3_frequency_pass": activity_2_3_frequency_pass,
        "frequency_audit": frequency_audit,
        **vdc_audit,
        "status": (
            "PASS"
            if bool(solution.success)
            and bool(np.all(np.isfinite(solution.y)))
            and activity_2_3_frequency_pass
            and bool(vdc_audit["vdc_task_4_1_closure_pass"])
            else "FAIL"
        ),
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def run_closure(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Run both scenarios and write the requested closure report."""
    records = [run_closure_scenario(spec) for spec in SCENARIOS]
    status = classify_closure_status(records)
    report: dict[str, Any] = {
        "task": "5.3",
        "status": status,
        "subtasks": {
            "activity_2_3_frequency_confirmation": bool(
                all(record["activity_2_3_frequency_pass"] for record in records)
            ),
            "task_4_1_vdc_confirmation": bool(
                all(record["vdc_task_4_1_closure_pass"] for record in records)
            ),
        },
        "M": EXPECTED_SELECTED_M,
        "D": EXPECTED_SELECTED_D,
        "scenario_count": len(records),
        "scenarios": records,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(output_path)
    clean = _json_ready(report)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(clean, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    for record in records:
        print(f"scenario={record['scenario']}")
        print(
            "activity_2_3_frequency_pass="
            f"{record['activity_2_3_frequency_pass']}"
        )
        print(
            "vdc_task_4_1_closure_pass="
            f"{record['vdc_task_4_1_closure_pass']}"
        )
        print(f"vdc_recovery_time_s={record['vdc_recovery_time_s']}")
    print(f"task_5_3_closure_status={status}")
    print(f"output_path={output_path}")
    return clean


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_closure(output_path=args.output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
