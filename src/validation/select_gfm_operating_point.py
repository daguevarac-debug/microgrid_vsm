"""Select a classical GFM operating point from a compliant sweep chain.

The selector does not run simulations or modify the controller. It validates a
formal initial sweep followed by one or more nested refinements, and selects the
fully admissible candidate with the smallest maximum frequency drop in the last
refinement stage.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence

import numpy as np


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]

EXPECTED_CRITERIA_VERSION = "obj2_vdc_event_relative_v2"
EXPECTED_VDC_ACCEPTANCE_BASIS = "max_abs_event_deviation_from_pre_step"
EXPECTED_SCENARIO = "load_step_20_no_bess"
SELECTION_SCOPE = "selected_within_compliant_initial_and_nested_refinement_domain"
MAX_VALUES_PER_PARAMETER = 3
MAX_RUNS_PER_STAGE = 9
PREVIOUS_SELECTED_M = 40.0
PREVIOUS_SELECTED_D = 100.0

DEFAULT_INITIAL_CSV = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "sensitivity_runs_initial_3x3.csv"
)
DEFAULT_REFINEMENT_CSV = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "refinement_compliant_iter1_m20-80_d200-1500.csv"
)
DEFAULT_OUTPUT_JSON = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "operating_point_selection_summary.json"
)

BOOLEAN_FIELDS = (
    "solver_success",
    "states_finite",
    "frequency_criteria_pass",
    "vdc_criteria_pass",
    "candidate_admissible",
)
METRIC_FIELDS = (
    "max_frequency_drop_hz",
    "frequency_recovery_time_s",
    "vdc_event_max_abs_deviation_pct",
    "vdc_min_post_step_v",
)
REQUIRED_FIELDS = (
    "scenario",
    "criteria_version",
    "vdc_acceptance_basis",
    "M",
    "D",
    *BOOLEAN_FIELDS,
    *METRIC_FIELDS,
)


def _parse_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{name} must be boolean-like, got {value!r}.")


def _parse_number(name: str, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric, got {value!r}.") from exc


def _normalized_record(
    raw: dict[str, Any], *, source: Path, row_number: int
) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise ValueError(
            f"{source}: row {row_number} is missing required fields: "
            f"{', '.join(missing)}."
        )

    scenario = str(raw["scenario"]).strip()
    criteria_version = str(raw["criteria_version"]).strip()
    vdc_basis = str(raw["vdc_acceptance_basis"]).strip()

    if scenario != EXPECTED_SCENARIO:
        raise ValueError(
            f"{source}: row {row_number} uses scenario={scenario!r}; "
            f"expected {EXPECTED_SCENARIO!r}."
        )
    if criteria_version != EXPECTED_CRITERIA_VERSION:
        raise ValueError(
            f"{source}: row {row_number} uses criteria_version={criteria_version!r}; "
            f"expected {EXPECTED_CRITERIA_VERSION!r}."
        )
    if vdc_basis != EXPECTED_VDC_ACCEPTANCE_BASIS:
        raise ValueError(
            f"{source}: row {row_number} uses vdc_acceptance_basis={vdc_basis!r}; "
            f"expected {EXPECTED_VDC_ACCEPTANCE_BASIS!r}."
        )

    record = dict(raw)
    record["scenario"] = scenario
    record["criteria_version"] = criteria_version
    record["vdc_acceptance_basis"] = vdc_basis
    record["M"] = _parse_number("M", raw["M"])
    record["D"] = _parse_number("D", raw["D"])

    for field in BOOLEAN_FIELDS:
        record[field] = _parse_bool(field, raw[field])
    for field in METRIC_FIELDS:
        record[field] = _parse_number(field, raw[field])

    if not np.isfinite(record["M"]) or record["M"] <= 0.0:
        raise ValueError(f"{source}: row {row_number} must have finite M > 0.")
    if not np.isfinite(record["D"]) or record["D"] < 0.0:
        raise ValueError(f"{source}: row {row_number} must have finite D >= 0.")

    return record


def load_sweep_csv(path: Path | str) -> list[dict[str, Any]]:
    """Load one sweep CSV while preserving explicitly invalid result rows."""
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Sweep CSV does not exist: {source}.")

    with source.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"Sweep CSV has no header: {source}.")
        records = [
            _normalized_record(raw, source=source, row_number=row_number)
            for row_number, raw in enumerate(reader, start=2)
        ]

    if not records:
        raise ValueError(f"Sweep CSV contains no data rows: {source}.")
    return records


def _is_fully_admissible(record: dict[str, Any]) -> bool:
    flags_pass = all(bool(record[field]) for field in BOOLEAN_FIELDS)
    metrics_finite = all(np.isfinite(record[field]) for field in METRIC_FIELDS)
    return bool(flags_pass and metrics_finite)


def _admissible(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if _is_fully_admissible(record)]


def _best_by_frequency_drop(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    candidates = list(records)
    if not candidates:
        raise ValueError("No fully admissible candidates were found.")
    return min(
        candidates,
        key=lambda record: (
            record["max_frequency_drop_hz"],
            record["M"],
            record["D"],
        ),
    )


def _find_point(
    records: Iterable[dict[str, Any]],
    *,
    inertia_m: float,
    damping_d: float,
    require_admissible: bool = True,
) -> dict[str, Any]:
    matches = [
        record
        for record in records
        if np.isclose(record["M"], inertia_m, rtol=0.0, atol=1e-12)
        and np.isclose(record["D"], damping_d, rtol=0.0, atol=1e-12)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one candidate at M={inertia_m:g}, D={damping_d:g}; "
            f"found {len(matches)}."
        )
    if require_admissible and not _is_fully_admissible(matches[0]):
        raise ValueError(
            f"The reference candidate M={inertia_m:g}, D={damping_d:g} "
            "is not fully admissible."
        )
    return matches[0]


def _point_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "M": record["M"],
        "D": record["D"],
        "max_frequency_drop_hz": record["max_frequency_drop_hz"],
        "frequency_recovery_time_s": record["frequency_recovery_time_s"],
        "vdc_event_max_abs_deviation_pct": record[
            "vdc_event_max_abs_deviation_pct"
        ],
        "vdc_min_post_step_v": record["vdc_min_post_step_v"],
        "candidate_admissible": record["candidate_admissible"],
    }


def _is_axis_boundary(record: dict[str, Any], records: Iterable[dict[str, Any]]) -> bool:
    candidates = list(records)
    m_values = [candidate["M"] for candidate in candidates]
    d_values = [candidate["D"] for candidate in candidates]
    return bool(
        np.isclose(record["M"], min(m_values))
        or np.isclose(record["M"], max(m_values))
        or np.isclose(record["D"], min(d_values))
        or np.isclose(record["D"], max(d_values))
    )


def _is_upper_corner(record: dict[str, Any], records: Iterable[dict[str, Any]]) -> bool:
    candidates = list(records)
    return bool(
        np.isclose(record["M"], max(candidate["M"] for candidate in candidates))
        and np.isclose(record["D"], max(candidate["D"] for candidate in candidates))
    )


def _reduction(reference: float, selected: float) -> tuple[float, float]:
    absolute = reference - selected
    relative_pct = 100.0 * absolute / reference if reference > 0.0 else float("nan")
    return float(absolute), float(relative_pct)


def _validate_stage(
    records: Sequence[dict[str, Any]], *, stage_name: str
) -> dict[str, Any]:
    if not records:
        raise ValueError(f"{stage_name} contains no records.")

    for row_number, record in enumerate(records, start=1):
        if record.get("scenario") != EXPECTED_SCENARIO:
            raise ValueError(
                f"{stage_name} row {row_number} uses an unexpected scenario."
            )
        if record.get("criteria_version") != EXPECTED_CRITERIA_VERSION:
            raise ValueError(
                f"{stage_name} row {row_number} uses an unexpected criteria version."
            )
        if record.get("vdc_acceptance_basis") != EXPECTED_VDC_ACCEPTANCE_BASIS:
            raise ValueError(
                f"{stage_name} row {row_number} uses an unexpected DC acceptance basis."
            )

    m_values = sorted({float(record["M"]) for record in records})
    d_values = sorted({float(record["D"]) for record in records})
    pairs = [(float(record["M"]), float(record["D"])) for record in records]

    if len(m_values) > MAX_VALUES_PER_PARAMETER:
        raise ValueError(
            f"{stage_name} contains {len(m_values)} unique M values; "
            f"maximum is {MAX_VALUES_PER_PARAMETER}."
        )
    if len(d_values) > MAX_VALUES_PER_PARAMETER:
        raise ValueError(
            f"{stage_name} contains {len(d_values)} unique D values; "
            f"maximum is {MAX_VALUES_PER_PARAMETER}."
        )
    if len(records) > MAX_RUNS_PER_STAGE:
        raise ValueError(
            f"{stage_name} contains {len(records)} runs; maximum is "
            f"{MAX_RUNS_PER_STAGE}."
        )
    if len(set(pairs)) != len(pairs):
        raise ValueError(f"{stage_name} contains duplicate (M, D) pairs.")

    expected_runs = len(m_values) * len(d_values)
    if len(records) != expected_runs:
        raise ValueError(
            f"{stage_name} is not a complete Cartesian grid: expected "
            f"{expected_runs} runs, found {len(records)}."
        )

    admissible = _admissible(records)
    if not admissible:
        raise ValueError(f"{stage_name} contains no fully admissible candidates.")

    best = _best_by_frequency_drop(admissible)
    return {
        "stage_name": stage_name,
        "runs_total": len(records),
        "candidates_admissible": len(admissible),
        "M_values": m_values,
        "D_values": d_values,
        "M_min": min(m_values),
        "M_max": max(m_values),
        "D_min": min(d_values),
        "D_max": max(d_values),
        "best_admissible": _point_summary(best),
        "best_on_boundary": _is_axis_boundary(best, records),
        "best_on_upper_corner": _is_upper_corner(best, records),
    }


def _validate_nested_refinement(
    parent: dict[str, Any], child: dict[str, Any]
) -> None:
    atol = 1e-12
    if child["M_min"] < parent["M_min"] - atol or child["M_max"] > parent["M_max"] + atol:
        raise ValueError(
            f"{child['stage_name']} M range is outside {parent['stage_name']}."
        )
    if child["D_min"] < parent["D_min"] - atol or child["D_max"] > parent["D_max"] + atol:
        raise ValueError(
            f"{child['stage_name']} D range is outside {parent['stage_name']}."
        )

    parent_m_width = parent["M_max"] - parent["M_min"]
    parent_d_width = parent["D_max"] - parent["D_min"]
    child_m_width = child["M_max"] - child["M_min"]
    child_d_width = child["D_max"] - child["D_min"]

    if child_m_width > parent_m_width + atol or child_d_width > parent_d_width + atol:
        raise ValueError(f"{child['stage_name']} does not narrow the parent domain.")
    if (
        np.isclose(child_m_width, parent_m_width, rtol=0.0, atol=atol)
        and np.isclose(child_d_width, parent_d_width, rtol=0.0, atol=atol)
    ):
        raise ValueError(
            f"{child['stage_name']} must narrow at least one parameter interval."
        )


def select_operating_point(
    initial_records: Iterable[dict[str, Any]],
    refinement_stages: Iterable[Iterable[dict[str, Any]]],
) -> dict[str, Any]:
    """Select the admissible minimum in the last compliant refinement stage."""
    initial_all = list(initial_records)
    refinement_all = [list(stage) for stage in refinement_stages]
    if not refinement_all:
        raise ValueError("At least one refinement stage is required.")

    all_stages = [initial_all, *refinement_all]
    stage_metadata = [
        _validate_stage(
            stage,
            stage_name=(
                "initial_3x3" if index == 0 else f"refinement_{index}"
            ),
        )
        for index, stage in enumerate(all_stages)
    ]

    for parent, child in zip(stage_metadata, stage_metadata[1:]):
        _validate_nested_refinement(parent, child)

    final_all = all_stages[-1]
    final_admissible = _admissible(final_all)
    selected = _best_by_frequency_drop(final_admissible)

    final_meta = stage_metadata[-1]
    midpoint_m = final_meta["M_values"][len(final_meta["M_values"]) // 2]
    midpoint_d = final_meta["D_values"][len(final_meta["D_values"]) // 2]
    midpoint = _find_point(
        final_all,
        inertia_m=midpoint_m,
        damping_d=midpoint_d,
        require_admissible=False,
    )
    same_m_lowest_d = min(
        (
            candidate
            for candidate in final_admissible
            if np.isclose(candidate["M"], selected["M"], rtol=0.0, atol=1e-12)
        ),
        key=lambda record: record["D"],
    )

    if _is_fully_admissible(midpoint):
        midpoint_abs, midpoint_pct = _reduction(
            midpoint["max_frequency_drop_hz"],
            selected["max_frequency_drop_hz"],
        )
    else:
        midpoint_abs = None
        midpoint_pct = None
    same_m_abs, same_m_pct = _reduction(
        same_m_lowest_d["max_frequency_drop_hz"],
        selected["max_frequency_drop_hz"],
    )

    selection_changed = not (
        np.isclose(selected["M"], PREVIOUS_SELECTED_M, rtol=0.0, atol=1e-12)
        and np.isclose(selected["D"], PREVIOUS_SELECTED_D, rtol=0.0, atol=1e-12)
    )

    return {
        "status": "PASS",
        "selection_scope": SELECTION_SCOPE,
        "selection_rule": (
            "minimum max_frequency_drop_hz among fully admissible candidates "
            "in the last compliant nested refinement; exact ties use lower M "
            "and then lower D"
        ),
        "scenario": EXPECTED_SCENARIO,
        "criteria_version": EXPECTED_CRITERIA_VERSION,
        "vdc_acceptance_basis": EXPECTED_VDC_ACCEPTANCE_BASIS,
        "stages": stage_metadata,
        "initial_best_diagnostic": stage_metadata[0]["best_admissible"],
        "final_midpoint_reference": _point_summary(midpoint),
        "selected_operating_point": _point_summary(selected),
        "same_m_lowest_d_reference": _point_summary(same_m_lowest_d),
        "previous_selected_operating_point": {
            "M": PREVIOUS_SELECTED_M,
            "D": PREVIOUS_SELECTED_D,
        },
        "diagnostics": {
            "selection_changed_from_previous": selection_changed,
            "selected_on_final_boundary": _is_axis_boundary(selected, final_all),
            "selected_on_final_upper_corner": _is_upper_corner(selected, final_all),
            "frequency_drop_reduction_vs_final_midpoint_hz": midpoint_abs,
            "frequency_drop_reduction_vs_final_midpoint_pct": midpoint_pct,
            "frequency_drop_reduction_vs_same_m_lowest_d_hz": same_m_abs,
            "frequency_drop_reduction_vs_same_m_lowest_d_pct": same_m_pct,
            "global_optimum_claimed": False,
            "cross_validation_pending": selection_changed,
            "severe_no_bess_robustness_confirmed": (
                None if selection_changed else False
            ),
            "bess_soh_base_validation_pass": (
                None if selection_changed else True
            ),
        },
    }


def write_summary(summary: dict[str, Any], output_path: Path | str) -> Path:
    """Write a local JSON summary under outputs/."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select the classical GFM operating point from a compliant initial "
            "3x3 sweep and one or more nested refinements."
        )
    )
    parser.add_argument("--initial", type=Path, default=DEFAULT_INITIAL_CSV)
    parser.add_argument(
        "--refinement",
        type=Path,
        action="append",
        default=None,
        help=(
            "Refinement CSV in chronological order. Repeat this option for "
            "multiple nested stages."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    refinement_paths = (
        args.refinement if args.refinement is not None else [DEFAULT_REFINEMENT_CSV]
    )

    try:
        summary = select_operating_point(
            load_sweep_csv(args.initial),
            [load_sweep_csv(path) for path in refinement_paths],
        )
        summary["input_files"] = {
            "initial": str(args.initial),
            "refinements": [str(path) for path in refinement_paths],
        }
        output_path = write_summary(summary, args.output)
    except (OSError, ValueError) as exc:
        print("status=FAIL")
        print(f"error={exc}")
        return 1

    selected = summary["selected_operating_point"]
    initial_best = summary["initial_best_diagnostic"]
    diagnostics = summary["diagnostics"]

    print("status=PASS")
    print(f"selection_scope={summary['selection_scope']}")
    print(f"scenario={summary['scenario']}")
    print(f"criteria_version={summary['criteria_version']}")
    print(f"vdc_acceptance_basis={summary['vdc_acceptance_basis']}")
    print(f"stages_total={len(summary['stages'])}")
    print(
        "initial_best_diagnostic="
        f"M={initial_best['M']:g},D={initial_best['D']:g},"
        f"drop_hz={initial_best['max_frequency_drop_hz']:.10f}"
    )
    print(
        "selected_operating_point="
        f"M={selected['M']:g},D={selected['D']:g},"
        f"drop_hz={selected['max_frequency_drop_hz']:.10f},"
        f"vdc_event_dev_pct={selected['vdc_event_max_abs_deviation_pct']:.10f},"
        f"vdc_min_v={selected['vdc_min_post_step_v']:.6f}"
    )
    print(
        "selection_changed_from_previous="
        f"{diagnostics['selection_changed_from_previous']}"
    )
    print(
        "selected_on_final_boundary="
        f"{diagnostics['selected_on_final_boundary']}"
    )
    print(
        "selected_on_final_upper_corner="
        f"{diagnostics['selected_on_final_upper_corner']}"
    )
    print(f"global_optimum_claimed={diagnostics['global_optimum_claimed']}")
    print(f"cross_validation_pending={diagnostics['cross_validation_pending']}")
    print(f"summary_path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
