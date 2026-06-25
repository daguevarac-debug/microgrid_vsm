"""Export PASS/REVIEW/FAIL for each integrated GFM scenario to CSV.

The source of truth is the JSON report produced by
``validate_gfm_integrated_system.py``. This exporter validates that the four
required scenarios are present exactly once, preserves their authoritative
status classification, and writes:

``outputs/validation/gfm_integrated/summary.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
INPUT_PATH_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_integrated_system"
    / "gfm_integrated_system_summary.json"
)
OUTPUT_PATH_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_integrated"
    / "summary.csv"
)
VALID_STATUSES = {"PASS", "REVIEW", "FAIL"}
REQUIRED_SCENARIOS = (
    "steady_operation",
    "load_step_20",
    "load_step_40",
    "bess_vs_no_bess",
)
FIELDNAMES = (
    "scenario",
    "status",
    "load_step_pct",
    "gfm_active",
    "bess_pi_active",
    "execution_pass",
    "frequency_criteria_pass",
    "vdc_criteria_pass",
    "performance_pass",
    "status_basis",
)


def _load_report(input_path: Path) -> dict[str, Any]:
    """Load and minimally validate the integrated-system JSON report."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(
            f"Integrated validation report not found: {input_path}. "
            "Run validate_gfm_integrated_system.py first."
        )

    with input_path.open("r", encoding="utf-8") as input_file:
        report = json.load(input_file)
    if not isinstance(report, dict):
        raise ValueError("Integrated validation report must be a JSON object.")

    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("Integrated validation report must contain a scenarios list.")
    return report


def _status_basis(record: dict[str, Any]) -> str:
    """Return a compact, auditable explanation of the stored classification."""
    status = str(record["status"])
    scenario = str(record["scenario"])

    if scenario == "bess_vs_no_bess":
        execution_pass = bool(record.get("comparison_execution_pass", False))
        performance_pass = bool(record.get("comparison_performance_pass", False))
        if status == "FAIL":
            return "comparison execution, GFM activation, BESS PI, or matched profile failed"
        if status == "REVIEW":
            return "comparison executed correctly but at least one design criterion was not met"
        if execution_pass and performance_pass:
            return "comparison execution and applicable design criteria passed"
        return "stored PASS requires review because comparison flags are inconsistent"

    execution_pass = bool(
        record.get("solver_success", False)
        and record.get("states_finite", False)
        and record.get("gfm_controller_active", False)
    )
    if status == "FAIL":
        return "solver, state integrity, GFM selection, PI activation, or BESS limits failed"
    if scenario == "steady_operation":
        if status == "REVIEW":
            return "simulation valid but steady-operation criteria were not met"
        if execution_pass and bool(record.get("steady_criteria_pass", False)):
            return "execution and steady-operation criteria passed"
        return "stored PASS requires review because steady-operation flags are inconsistent"

    frequency_pass = bool(record.get("frequency_criteria_pass", False))
    vdc_pass = bool(record.get("vdc_criteria_pass", False))
    if status == "REVIEW":
        failed = []
        if not frequency_pass:
            failed.append("frequency")
        if not vdc_pass:
            failed.append("DC-link")
        failed_text = " and ".join(failed) if failed else "one or more"
        return f"simulation valid but {failed_text} criteria were not met"
    if execution_pass and frequency_pass and vdc_pass:
        return "execution, frequency, and DC-link criteria passed"
    return "stored PASS requires review because scenario flags are inconsistent"


def _normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten one scenario record into the stable CSV schema."""
    scenario = str(record.get("scenario", ""))
    status = str(record.get("status", ""))
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Scenario {scenario!r} has invalid status {status!r}; "
            f"expected one of {sorted(VALID_STATUSES)}."
        )

    if scenario == "bess_vs_no_bess":
        gfm_active = bool(record.get("both_gfm_active", False))
        bess_pi_active = bool(record.get("bess_pi_active", False))
        execution_pass = bool(record.get("comparison_execution_pass", False))
        performance_pass = bool(record.get("comparison_performance_pass", False))
        frequency_pass: bool | str = ""
        vdc_pass: bool | str = ""
    else:
        gfm_active = bool(record.get("gfm_controller_active", False))
        bess_pi_active = bool(record.get("bess_pi_active", False))
        execution_pass = bool(
            record.get("solver_success", False)
            and record.get("states_finite", False)
            and gfm_active
        )
        if scenario == "steady_operation":
            performance_pass = bool(record.get("steady_criteria_pass", False))
            frequency_pass = ""
            vdc_pass = ""
        else:
            frequency_pass = bool(record.get("frequency_criteria_pass", False))
            vdc_pass = bool(record.get("vdc_criteria_pass", False))
            performance_pass = bool(frequency_pass and vdc_pass)

    return {
        "scenario": scenario,
        "status": status,
        "load_step_pct": record.get("load_step_pct", ""),
        "gfm_active": gfm_active,
        "bess_pi_active": bess_pi_active,
        "execution_pass": execution_pass,
        "frequency_criteria_pass": frequency_pass,
        "vdc_criteria_pass": vdc_pass,
        "performance_pass": performance_pass,
        "status_basis": _status_basis(record),
    }


def build_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exactly four ordered rows for the required integrated scenarios."""
    scenarios = report["scenarios"]
    records_by_name: dict[str, dict[str, Any]] = {}
    for raw_record in scenarios:
        if not isinstance(raw_record, dict):
            raise ValueError("Every scenario entry must be a JSON object.")
        name = str(raw_record.get("scenario", ""))
        if name in records_by_name:
            raise ValueError(f"Duplicate scenario in integrated report: {name!r}.")
        records_by_name[name] = raw_record

    actual_names = set(records_by_name)
    required_names = set(REQUIRED_SCENARIOS)
    if actual_names != required_names:
        missing = sorted(required_names - actual_names)
        unexpected = sorted(actual_names - required_names)
        raise ValueError(
            "Integrated report scenario set mismatch: "
            f"missing={missing}, unexpected={unexpected}."
        )

    return [_normalise_record(records_by_name[name]) for name in REQUIRED_SCENARIOS]


def write_summary_csv(rows: list[dict[str, Any]], output_path: Path) -> Path:
    """Write the four scenario classifications atomically enough for local use."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(output_path)
    return output_path


def export_summary(
    *,
    input_path: Path = INPUT_PATH_DEFAULT,
    output_path: Path = OUTPUT_PATH_DEFAULT,
) -> dict[str, Any]:
    """Read the integrated report and export its scenario statuses to CSV."""
    report = _load_report(input_path)
    rows = build_rows(report)
    written_path = write_summary_csv(rows, output_path)

    for row in rows:
        print(f"scenario={row['scenario']}")
        print(f"status={row['status']}")
    print(f"scenario_count={len(rows)}")
    print(f"overall_status={report.get('status', '')}")
    print(f"csv_path={written_path}")
    return {
        "status": "PASS",
        "scenario_count": len(rows),
        "integrated_overall_status": report.get("status"),
        "csv_path": str(written_path),
        "rows": rows,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_PATH_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        export_summary(input_path=args.input, output_path=args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"status=FAIL")
        print(f"error={exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
