"""Select the classical GFM operating point from validated sweep CSV files.

The selector does not run simulations or modify the controller. It applies a
deterministic rule to the existing coarse and refined results generated with the
Objective 2 DC-link criterion v2.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]

EXPECTED_CRITERIA_VERSION = "obj2_vdc_event_relative_v2"
EXPECTED_VDC_ACCEPTANCE_BASIS = "max_abs_event_deviation_from_pre_step"
SELECTION_SCOPE = "selected_within_explored_and_refined_domain"
BALANCED_REFERENCE_M = 30.0
BALANCED_REFERENCE_D = 75.0

DEFAULT_COARSE_CSV = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "sensitivity_runs_v2_event_relative.csv"
)
DEFAULT_REFINED_CSV = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "refinement_iter2_m20-40_d50-100.csv"
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

    criteria_version = str(raw["criteria_version"]).strip()
    vdc_basis = str(raw["vdc_acceptance_basis"]).strip()
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
    records: Iterable[dict[str, Any]], *, inertia_m: float, damping_d: float
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
    if not _is_fully_admissible(matches[0]):
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


def _reduction(reference: float, selected: float) -> tuple[float, float]:
    absolute = reference - selected
    relative_pct = 100.0 * absolute / reference if reference > 0.0 else float("nan")
    return float(absolute), float(relative_pct)


def select_operating_point(
    coarse_records: Iterable[dict[str, Any]],
    refined_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Select the refined admissible minimum and retain coarse diagnostics."""
    coarse_all = list(coarse_records)
    refined_all = list(refined_records)
    coarse_admissible = _admissible(coarse_all)
    refined_admissible = _admissible(refined_all)
    if not coarse_admissible:
        raise ValueError("The coarse sweep contains no fully admissible candidates.")
    if not refined_admissible:
        raise ValueError("The refined sweep contains no fully admissible candidates.")

    coarse_best = _best_by_frequency_drop(coarse_admissible)
    selected = _best_by_frequency_drop(refined_admissible)
    balanced = _find_point(
        refined_admissible,
        inertia_m=BALANCED_REFERENCE_M,
        damping_d=BALANCED_REFERENCE_D,
    )
    same_m_lowest_d = min(
        (
            candidate
            for candidate in refined_admissible
            if np.isclose(candidate["M"], selected["M"], rtol=0.0, atol=1e-12)
        ),
        key=lambda record: record["D"],
    )

    balanced_abs, balanced_pct = _reduction(
        balanced["max_frequency_drop_hz"], selected["max_frequency_drop_hz"]
    )
    same_m_abs, same_m_pct = _reduction(
        same_m_lowest_d["max_frequency_drop_hz"],
        selected["max_frequency_drop_hz"],
    )

    return {
        "status": "PASS",
        "selection_scope": SELECTION_SCOPE,
        "selection_rule": (
            "minimum max_frequency_drop_hz among fully admissible refined "
            "candidates; exact ties use lower M and then lower D"
        ),
        "criteria_version": EXPECTED_CRITERIA_VERSION,
        "vdc_acceptance_basis": EXPECTED_VDC_ACCEPTANCE_BASIS,
        "coarse_runs_total": len(coarse_all),
        "coarse_candidates_admissible": len(coarse_admissible),
        "refined_runs_total": len(refined_all),
        "refined_candidates_admissible": len(refined_admissible),
        "coarse_best_diagnostic": _point_summary(coarse_best),
        "balanced_reference": _point_summary(balanced),
        "selected_operating_point": _point_summary(selected),
        "same_m_lowest_d_reference": _point_summary(same_m_lowest_d),
        "diagnostics": {
            "coarse_best_on_explored_boundary": _is_axis_boundary(
                coarse_best, coarse_all
            ),
            "selected_on_refined_boundary": _is_axis_boundary(
                selected, refined_all
            ),
            "frequency_drop_reduction_vs_balanced_hz": balanced_abs,
            "frequency_drop_reduction_vs_balanced_pct": balanced_pct,
            "frequency_drop_reduction_vs_same_m_lowest_d_hz": same_m_abs,
            "frequency_drop_reduction_vs_same_m_lowest_d_pct": same_m_pct,
            "global_optimum_claimed": False,
            "cross_validation_pending": True,
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
            "Select the classical GFM operating point from coarse and refined "
            "Objective 2 sweep CSV files."
        )
    )
    parser.add_argument("--coarse", type=Path, default=DEFAULT_COARSE_CSV)
    parser.add_argument("--refined", type=Path, default=DEFAULT_REFINED_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary = select_operating_point(
            load_sweep_csv(args.coarse),
            load_sweep_csv(args.refined),
        )
        output_path = write_summary(summary, args.output)
    except (OSError, ValueError) as exc:
        print("status=FAIL")
        print(f"error={exc}")
        return 1

    selected = summary["selected_operating_point"]
    coarse_best = summary["coarse_best_diagnostic"]
    diagnostics = summary["diagnostics"]
    print("status=PASS")
    print(f"selection_scope={summary['selection_scope']}")
    print(f"criteria_version={summary['criteria_version']}")
    print(f"vdc_acceptance_basis={summary['vdc_acceptance_basis']}")
    print(
        "coarse_best_diagnostic="
        f"M={coarse_best['M']:g},D={coarse_best['D']:g},"
        f"drop_hz={coarse_best['max_frequency_drop_hz']:.10f}"
    )
    print(
        "selected_operating_point="
        f"M={selected['M']:g},D={selected['D']:g},"
        f"drop_hz={selected['max_frequency_drop_hz']:.10f},"
        f"vdc_event_dev_pct={selected['vdc_event_max_abs_deviation_pct']:.10f},"
        f"vdc_min_v={selected['vdc_min_post_step_v']:.6f}"
    )
    print(
        "frequency_drop_reduction_vs_balanced_pct="
        f"{diagnostics['frequency_drop_reduction_vs_balanced_pct']:.6f}"
    )
    print(
        "frequency_drop_reduction_vs_same_m_lowest_d_pct="
        f"{diagnostics['frequency_drop_reduction_vs_same_m_lowest_d_pct']:.6f}"
    )
    print(f"selected_on_refined_boundary={diagnostics['selected_on_refined_boundary']}")
    print(f"global_optimum_claimed={diagnostics['global_optimum_claimed']}")
    print(f"cross_validation_pending={diagnostics['cross_validation_pending']}")
    print(f"summary_path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
