"""Run a reproducible coarse sweep of classical GFM parameters.

The script evaluates the documented 20% load-step scenario without BESS for a
Cartesian grid of virtual-inertia ``M`` and damping ``D`` values. Each run is
integrated with the existing global microgrid ODE and evaluated with the Task
4.1 tuning metrics.

Default output:
    outputs/validation/gfm_tuning/sensitivity_runs.csv

Examples:
    # Inspect the configured grid without running simulations.
    python src/validation/tune_gfm_parameters.py --dry-run

    # Run one smoke-test candidate.
    python src/validation/tune_gfm_parameters.py --m-values 2 --d-values 50 \
        --output outputs/validation/gfm_tuning/smoke_single_run.csv

    # Run the complete 42-point coarse grid.
    python src/validation/tune_gfm_parameters.py
"""

from __future__ import annotations

import argparse
import csv
from itertools import product
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Iterable

import numpy as np
from scipy.integrate import solve_ivp

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.gfm_controller import GFMController
from microgrid import Microgrid
from tuning_metrics import (
    dc_link_performance_metrics,
    frequency_performance_metrics,
)


M_SWEEP_DEFAULT = (2.0, 5.0, 10.0, 20.0, 40.0, 80.0)
D_SWEEP_DEFAULT = (0.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 1500.0)
TUNING_T_END_S_DEFAULT = 6.5
SCENARIO_NAME = "load_step_20_no_bess"
CRITERIA_VERSION = "obj2_vdc_event_relative_v2"
VDC_ACCEPTANCE_BASIS = "max_abs_event_deviation_from_pre_step"
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "sensitivity_runs.csv"
)

CSV_FIELDNAMES = (
    "run_index",
    "scenario",
    "criteria_version",
    "vdc_acceptance_basis",
    "bess_active",
    "M",
    "D",
    "p_ref_w",
    "p_load_pre_step_w",
    "p_load_post_step_w",
    "load_step_pct",
    "power_factor",
    "t_start_s",
    "t_step_s",
    "t_end_s",
    "solver_success",
    "solver_message",
    "states_finite",
    "n_time_points",
    "nfev",
    "elapsed_wall_s",
    "frequency_pre_step_hz",
    "frequency_min_post_step_hz",
    "frequency_max_post_step_hz",
    "max_frequency_drop_hz",
    "max_frequency_rise_hz",
    "max_frequency_abs_deviation_hz",
    "frequency_recovery_time_s",
    "frequency_drop_pass",
    "frequency_recovery_pass",
    "frequency_criteria_pass",
    "vdc_pre_step_v",
    "vdc_reference_deviation_v",
    "vdc_reference_deviation_pct",
    "vdc_max_post_step_v",
    "vdc_min_post_step_v",
    "vdc_overshoot_v",
    "vdc_overshoot_pct",
    "vdc_undershoot_v",
    "vdc_undershoot_pct",
    "vdc_event_max_rise_v",
    "vdc_event_max_drop_v",
    "vdc_event_max_abs_deviation_v",
    "vdc_event_max_abs_deviation_pct",
    "vdc_min_required_v",
    "vdc_min_margin_v",
    "vdc_overshoot_pass",
    "vdc_event_deviation_pass",
    "vdc_minimum_voltage_pass",
    "vdc_criteria_pass",
    "candidate_admissible",
    "status",
    "error_message",
)


def _validated_values(
    name: str,
    values: Iterable[float],
    *,
    strictly_positive: bool,
) -> tuple[float, ...]:
    """Return finite, ordered sweep values after enforcing parameter bounds."""
    validated: list[float] = []
    for raw_value in values:
        value = float(raw_value)
        if not np.isfinite(value):
            raise ValueError(f"{name} values must be finite, got {raw_value!r}.")
        if strictly_positive and value <= 0.0:
            raise ValueError(f"{name} values must be > 0, got {value}.")
        if not strictly_positive and value < 0.0:
            raise ValueError(f"{name} values must be >= 0, got {value}.")
        if value not in validated:
            validated.append(value)
    if not validated:
        raise ValueError(f"At least one {name} value is required.")
    return tuple(validated)


def build_parameter_grid(
    m_values: Iterable[float] = M_SWEEP_DEFAULT,
    d_values: Iterable[float] = D_SWEEP_DEFAULT,
) -> tuple[tuple[float, float], ...]:
    """Return the Cartesian ``(M, D)`` grid in deterministic order."""
    m_grid = _validated_values("M", m_values, strictly_positive=True)
    d_grid = _validated_values("D", d_values, strictly_positive=False)
    return tuple((m_value, d_value) for m_value, d_value in product(m_grid, d_grid))


def _empty_metrics_record() -> dict[str, Any]:
    """Return explicit defaults for metrics that may be unavailable after failure."""
    return {
        "frequency_pre_step_hz": np.nan,
        "frequency_min_post_step_hz": np.nan,
        "frequency_max_post_step_hz": np.nan,
        "max_frequency_drop_hz": np.nan,
        "max_frequency_rise_hz": np.nan,
        "max_frequency_abs_deviation_hz": np.nan,
        "frequency_recovery_time_s": np.nan,
        "frequency_drop_pass": False,
        "frequency_recovery_pass": False,
        "frequency_criteria_pass": False,
        "vdc_pre_step_v": np.nan,
        "vdc_reference_deviation_v": np.nan,
        "vdc_reference_deviation_pct": np.nan,
        "vdc_max_post_step_v": np.nan,
        "vdc_min_post_step_v": np.nan,
        "vdc_overshoot_v": np.nan,
        "vdc_overshoot_pct": np.nan,
        "vdc_undershoot_v": np.nan,
        "vdc_undershoot_pct": np.nan,
        "vdc_event_max_rise_v": np.nan,
        "vdc_event_max_drop_v": np.nan,
        "vdc_event_max_abs_deviation_v": np.nan,
        "vdc_event_max_abs_deviation_pct": np.nan,
        "vdc_min_required_v": np.nan,
        "vdc_min_margin_v": np.nan,
        "vdc_overshoot_pass": False,
        "vdc_event_deviation_pass": False,
        "vdc_minimum_voltage_pass": False,
        "vdc_criteria_pass": False,
        "candidate_admissible": False,
    }


def _reference_active_power_w() -> float:
    """Return the same available active-power reference used elsewhere in the repo."""
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def run_single_candidate(
    *,
    run_index: int,
    inertia_m: float,
    damping_d: float,
    p_ref_w: float,
    t_end_s: float = TUNING_T_END_S_DEFAULT,
) -> dict[str, Any]:
    """Simulate and score one classical GFM ``(M, D)`` candidate."""
    inertia_m = _validated_values("M", (inertia_m,), strictly_positive=True)[0]
    damping_d = _validated_values("D", (damping_d,), strictly_positive=False)[0]
    t_end_s = float(t_end_s)
    if not np.isfinite(t_end_s) or t_end_s <= MICROGRID_LOAD_STEP_TIME_S_DEFAULT:
        raise ValueError(
            "t_end_s must be finite and greater than the load-step time "
            f"({MICROGRID_LOAD_STEP_TIME_S_DEFAULT} s), got {t_end_s}."
        )

    p_load_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_load_post = float(
        MICROGRID_LOAD_P_NOM_W_DEFAULT
        * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
    )
    load_step_pct = 100.0 * (p_load_post - p_load_pre) / p_load_pre

    record: dict[str, Any] = {
        "run_index": int(run_index),
        "scenario": SCENARIO_NAME,
        "criteria_version": CRITERIA_VERSION,
        "vdc_acceptance_basis": VDC_ACCEPTANCE_BASIS,
        "bess_active": False,
        "M": inertia_m,
        "D": damping_d,
        "p_ref_w": float(p_ref_w),
        "p_load_pre_step_w": p_load_pre,
        "p_load_post_step_w": p_load_post,
        "load_step_pct": load_step_pct,
        "power_factor": float(MICROGRID_LOAD_POWER_FACTOR_DEFAULT),
        "t_start_s": float(SIM_T_START_S_DEFAULT),
        "t_step_s": float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT),
        "t_end_s": t_end_s,
        "solver_success": False,
        "solver_message": "not started",
        "states_finite": False,
        "n_time_points": 0,
        "nfev": 0,
        "elapsed_wall_s": np.nan,
        "status": "error",
        "error_message": "",
    }
    record.update(_empty_metrics_record())

    start_wall = perf_counter()
    try:
        controller = GFMController(
            p_ref=float(p_ref_w),
            inertia_m=inertia_m,
            damping_d=damping_d,
        )
        model = Microgrid(controller=controller)
        solution = solve_ivp(
            model.system_dynamics,
            (float(SIM_T_START_S_DEFAULT), t_end_s),
            model.initial_state(vdc0=SIM_VDC0_V_DEFAULT),
            max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
            rtol=SIM_SOLVER_RTOL_DEFAULT,
            atol=SIM_SOLVER_ATOL_DEFAULT,
        )

        solver_success = bool(solution.success)
        states_finite = bool(
            np.all(np.isfinite(solution.t)) and np.all(np.isfinite(solution.y))
        )
        record.update(
            {
                "solver_success": solver_success,
                "solver_message": str(solution.message),
                "states_finite": states_finite,
                "n_time_points": int(solution.t.size),
                "nfev": int(solution.nfev),
            }
        )

        if not solver_success:
            record["status"] = "solver_error"
            record["error_message"] = str(solution.message)
        elif not states_finite:
            record["status"] = "invalid_states"
            record["error_message"] = "Time or state arrays contain NaN/Inf."
        else:
            frequency_hz = solution.y[10] / (2.0 * np.pi)
            frequency_metrics = frequency_performance_metrics(
                t=solution.t,
                frequency_hz=frequency_hz,
                t_step=model.t_step,
            )
            vdc_metrics = dc_link_performance_metrics(
                t=solution.t,
                vdc_v=solution.y[0],
                t_step=model.t_step,
            )
            record.update(frequency_metrics)
            record.update(vdc_metrics)
            record["candidate_admissible"] = bool(
                solver_success
                and states_finite
                and frequency_metrics["frequency_criteria_pass"]
                and vdc_metrics["vdc_criteria_pass"]
            )
            record["status"] = "ok"
    except Exception as exc:
        record["status"] = "exception"
        record["error_message"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["elapsed_wall_s"] = float(perf_counter() - start_wall)

    return record


def write_runs_csv(records: Iterable[dict[str, Any]], output_path: Path) -> Path:
    """Write sweep records with a stable column order and UTF-8 encoding."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDNAMES,
            extrasaction="ignore",
        )
        writer.writeheader()
        for record in records:
            writer.writerow(record)
    return path


def run_parameter_sweep(
    *,
    m_values: Iterable[float] = M_SWEEP_DEFAULT,
    d_values: Iterable[float] = D_SWEEP_DEFAULT,
    t_end_s: float = TUNING_T_END_S_DEFAULT,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> tuple[list[dict[str, Any]], Path]:
    """Run all requested candidates and write one row per simulation."""
    grid = build_parameter_grid(m_values=m_values, d_values=d_values)
    p_ref_w = _reference_active_power_w()
    records: list[dict[str, Any]] = []

    print(f"scenario={SCENARIO_NAME}")
    print(f"criteria_version={CRITERIA_VERSION}")
    print(f"vdc_acceptance_basis={VDC_ACCEPTANCE_BASIS}")
    print(f"grid_size={len(grid)}")
    print(f"p_ref_w={p_ref_w:.6f}")
    print(f"t_step_s={MICROGRID_LOAD_STEP_TIME_S_DEFAULT:.6f}")
    print(f"t_end_s={float(t_end_s):.6f}")

    for run_index, (inertia_m, damping_d) in enumerate(grid, start=1):
        print(
            f"run={run_index}/{len(grid)} | M={inertia_m:g} | D={damping_d:g}",
            flush=True,
        )
        record = run_single_candidate(
            run_index=run_index,
            inertia_m=inertia_m,
            damping_d=damping_d,
            p_ref_w=p_ref_w,
            t_end_s=t_end_s,
        )
        records.append(record)
        print(
            "result="
            f"{record['status']} | admissible={record['candidate_admissible']} | "
            f"drop_hz={record['max_frequency_drop_hz']} | "
            f"recovery_s={record['frequency_recovery_time_s']} | "
            f"vdc_event_dev_pct={record['vdc_event_max_abs_deviation_pct']} | "
            f"vdc_min_v={record['vdc_min_post_step_v']} | "
            f"elapsed_s={record['elapsed_wall_s']:.3f}",
            flush=True,
        )

    csv_path = write_runs_csv(records, output_path)
    return records, csv_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep classical GFM inertia M and damping D under the documented "
            "20% load-step scenario."
        )
    )
    parser.add_argument(
        "--m-values",
        nargs="+",
        type=float,
        default=list(M_SWEEP_DEFAULT),
        help="Virtual-inertia values. Default: 2 5 10 20 40 80.",
    )
    parser.add_argument(
        "--d-values",
        nargs="+",
        type=float,
        default=list(D_SWEEP_DEFAULT),
        help="Damping values. Default: 0 50 100 200 500 1000 1500.",
    )
    parser.add_argument(
        "--t-end",
        type=float,
        default=TUNING_T_END_S_DEFAULT,
        help="Tuning-only final simulation time in seconds. Default: 6.5.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "CSV output path. Default: "
            "outputs/validation/gfm_tuning/sensitivity_runs.csv"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the parameter grid without solving the model.",
    )
    return parser.parse_args(argv)


def _print_grid(grid: tuple[tuple[float, float], ...]) -> None:
    print(f"grid_size={len(grid)}")
    for run_index, (inertia_m, damping_d) in enumerate(grid, start=1):
        print(f"run={run_index} | M={inertia_m:g} | D={damping_d:g}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    grid = build_parameter_grid(args.m_values, args.d_values)
    if args.dry_run:
        _print_grid(grid)
        print(f"criteria_version={CRITERIA_VERSION}")
        print(f"vdc_acceptance_basis={VDC_ACCEPTANCE_BASIS}")
        print("dry_run=True")
        print("simulations_executed=0")
        return 0

    records, csv_path = run_parameter_sweep(
        m_values=args.m_values,
        d_values=args.d_values,
        t_end_s=args.t_end,
        output_path=args.output,
    )
    n_ok = sum(record["status"] == "ok" for record in records)
    n_invalid = len(records) - n_ok
    n_admissible = sum(bool(record["candidate_admissible"]) for record in records)

    print("\n=== GFM tuning sweep summary ===")
    print(f"runs_total={len(records)}")
    print(f"runs_ok={n_ok}")
    print(f"runs_invalid={n_invalid}")
    print(f"candidates_admissible={n_admissible}")
    print(f"csv_path={csv_path}")

    return 0 if records and csv_path.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
