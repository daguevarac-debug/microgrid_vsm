"""Validate Task 4.1 frequency-metric coherence for Activity 2.3 closure.

This script reads the existing cross-validation outputs. It does not rerun the
dynamic simulations and does not modify model equations or controller settings.
"""

from __future__ import annotations

import argparse
import csv
import json
from math import isclose, isfinite
from pathlib import Path
import sys
from typing import Any


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tuning_metrics import DEFAULT_TUNING_CRITERIA, TuningCriteria


CANONICAL_METRIC = "max_frequency_abs_deviation_hz"
NONCANONICAL_ALIAS = "max_abs_frequency_deviation_hz"

DEFAULT_SEVERE_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "selected_m40_d100_severe_40pct.json"
)
DEFAULT_SOH_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_bess_soh_scenarios"
    / "gfm_bess_soh_scenarios_summary.csv"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "activity_2_3_frequency_metric"
    / "activity_2_3_frequency_metric_closure.json"
)

REQUIRED_FIELDS = (
    "frequency_pre_step_hz",
    "frequency_min_post_step_hz",
    "frequency_max_post_step_hz",
    "max_frequency_drop_hz",
    CANONICAL_METRIC,
    "frequency_recovery_time_s",
    "frequency_drop_pass",
    "frequency_recovery_pass",
    "frequency_criteria_pass",
)

FLOAT_REL_TOL = 1e-9
FLOAT_ABS_TOL = 1e-9


def _as_float(record: dict[str, Any], key: str) -> float:
    value = float(record[key])
    if not isfinite(value):
        raise ValueError(f"{key} must be finite, got {value!r}.")
    return value


def _as_bool(record: dict[str, Any], key: str) -> bool:
    value = record[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{key} is not a recognized boolean: {value!r}.")


def _close(a: float, b: float) -> bool:
    return isclose(a, b, rel_tol=FLOAT_REL_TOL, abs_tol=FLOAT_ABS_TOL)


def validate_frequency_record(
    record: dict[str, Any],
    *,
    label: str,
    criteria: TuningCriteria = DEFAULT_TUNING_CRITERIA,
) -> dict[str, Any]:
    """Check metric naming, definitions and Task 4.1 acceptance logic."""
    missing = [key for key in REQUIRED_FIELDS if key not in record]
    canonical_name_ok = CANONICAL_METRIC in record
    noncanonical_alias_absent = NONCANONICAL_ALIAS not in record

    result: dict[str, Any] = {
        "label": label,
        "canonical_metric_name": CANONICAL_METRIC,
        "canonical_metric_name_ok": canonical_name_ok,
        "noncanonical_alias_absent": noncanonical_alias_absent,
        "missing_fields": missing,
        "metric_definition_ok": False,
        "drop_definition_ok": False,
        "drop_pass_logic_ok": False,
        "recovery_pass_logic_ok": False,
        "frequency_criteria_logic_ok": False,
        "entire_post_step_within_recovery_band": False,
        "frequency_metric_coherent": False,
    }
    if missing:
        return result

    frequency_pre = _as_float(record, "frequency_pre_step_hz")
    frequency_min = _as_float(record, "frequency_min_post_step_hz")
    frequency_max = _as_float(record, "frequency_max_post_step_hz")
    max_abs_deviation = _as_float(record, CANONICAL_METRIC)
    max_drop = _as_float(record, "max_frequency_drop_hz")
    recovery_time = _as_float(record, "frequency_recovery_time_s")

    expected_abs_deviation = max(
        abs(frequency_min - criteria.nominal_frequency_hz),
        abs(frequency_max - criteria.nominal_frequency_hz),
    )
    expected_drop = max(frequency_pre - frequency_min, 0.0)

    reported_drop_pass = _as_bool(record, "frequency_drop_pass")
    reported_recovery_pass = _as_bool(record, "frequency_recovery_pass")
    reported_criteria_pass = _as_bool(record, "frequency_criteria_pass")

    expected_drop_pass = max_drop <= criteria.max_frequency_drop_hz
    expected_recovery_pass = (
        recovery_time >= 0.0
        and recovery_time <= criteria.max_frequency_recovery_s
    )
    expected_criteria_pass = expected_drop_pass and expected_recovery_pass

    metric_definition_ok = _close(
        max_abs_deviation,
        expected_abs_deviation,
    )
    drop_definition_ok = _close(max_drop, expected_drop)
    drop_pass_logic_ok = reported_drop_pass == expected_drop_pass
    recovery_pass_logic_ok = (
        reported_recovery_pass == expected_recovery_pass
    )
    frequency_criteria_logic_ok = (
        reported_criteria_pass == expected_criteria_pass
    )
    entire_post_step_within_band = (
        max_abs_deviation <= criteria.frequency_recovery_band_hz
    )

    frequency_metric_coherent = all(
        (
            canonical_name_ok,
            noncanonical_alias_absent,
            not missing,
            metric_definition_ok,
            drop_definition_ok,
            drop_pass_logic_ok,
            recovery_pass_logic_ok,
            frequency_criteria_logic_ok,
        )
    )

    result.update(
        {
            "frequency_pre_step_hz": frequency_pre,
            "frequency_min_post_step_hz": frequency_min,
            "frequency_max_post_step_hz": frequency_max,
            CANONICAL_METRIC: max_abs_deviation,
            "expected_max_frequency_abs_deviation_hz": (
                expected_abs_deviation
            ),
            "max_frequency_drop_hz": max_drop,
            "expected_max_frequency_drop_hz": expected_drop,
            "frequency_recovery_time_s": recovery_time,
            "max_frequency_drop_limit_hz": (
                criteria.max_frequency_drop_hz
            ),
            "frequency_recovery_band_hz": (
                criteria.frequency_recovery_band_hz
            ),
            "max_frequency_recovery_s": (
                criteria.max_frequency_recovery_s
            ),
            "frequency_recovery_dwell_s": (
                criteria.frequency_recovery_dwell_s
            ),
            "frequency_drop_pass": reported_drop_pass,
            "frequency_recovery_pass": reported_recovery_pass,
            "frequency_criteria_pass": reported_criteria_pass,
            "metric_definition_ok": metric_definition_ok,
            "drop_definition_ok": drop_definition_ok,
            "drop_pass_logic_ok": drop_pass_logic_ok,
            "recovery_pass_logic_ok": recovery_pass_logic_ok,
            "frequency_criteria_logic_ok": (
                frequency_criteria_logic_ok
            ),
            "entire_post_step_within_recovery_band": (
                entire_post_step_within_band
            ),
            "frequency_metric_coherent": frequency_metric_coherent,
        }
    )
    return result


def _load_severe(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("The severe-scenario JSON must contain one object.")
    return data


def _load_soh(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError("The SoH summary CSV contains no scenarios.")
    return rows


def validate_activity_2_3(
    *,
    severe_path: Path = DEFAULT_SEVERE_PATH,
    soh_path: Path = DEFAULT_SOH_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Validate all cross-validation frequency records and write a report."""
    severe = _load_severe(Path(severe_path))
    soh_rows = _load_soh(Path(soh_path))

    records = [
        validate_frequency_record(
            severe,
            label=str(
                severe.get(
                    "scenario",
                    "gfm_selected_load_step_40_no_bess",
                )
            ),
        )
    ]
    records.extend(
        validate_frequency_record(
            row,
            label=str(row.get("label", "unnamed_soh_case")),
        )
        for row in soh_rows
    )

    all_metrics_coherent = all(
        bool(record["frequency_metric_coherent"])
        for record in records
    )
    all_frequency_criteria_pass = all(
        bool(record.get("frequency_criteria_pass", False))
        for record in records
    )
    all_post_step_within_band = all(
        bool(record["entire_post_step_within_recovery_band"])
        for record in records
    )
    closure_status = (
        "PASS"
        if all_metrics_coherent and all_frequency_criteria_pass
        else "FAIL"
    )

    report = {
        "activity": "2.3",
        "status": closure_status,
        "canonical_metric": CANONICAL_METRIC,
        "noncanonical_alias": NONCANONICAL_ALIAS,
        "criteria_source": "Task 4.1",
        "nominal_frequency_hz": (
            DEFAULT_TUNING_CRITERIA.nominal_frequency_hz
        ),
        "max_frequency_drop_limit_hz": (
            DEFAULT_TUNING_CRITERIA.max_frequency_drop_hz
        ),
        "frequency_recovery_band_hz": (
            DEFAULT_TUNING_CRITERIA.frequency_recovery_band_hz
        ),
        "max_frequency_recovery_s": (
            DEFAULT_TUNING_CRITERIA.max_frequency_recovery_s
        ),
        "frequency_recovery_dwell_s": (
            DEFAULT_TUNING_CRITERIA.frequency_recovery_dwell_s
        ),
        "all_frequency_metrics_coherent": all_metrics_coherent,
        "all_frequency_criteria_pass": all_frequency_criteria_pass,
        "all_post_step_traces_within_recovery_band": (
            all_post_step_within_band
        ),
        "records": records,
        "scope_note": (
            "Activity 2.3 closes the frequency-metric consistency check. "
            "It does not convert the severe no-BESS scenario from REVIEW "
            "to PASS because its DC-link criterion remains unmet."
        ),
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, sort_keys=True)
        file.write("\n")
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Activity 2.3 frequency-metric coherence using "
            "existing cross-validation outputs."
        )
    )
    parser.add_argument(
        "--severe-json",
        type=Path,
        default=DEFAULT_SEVERE_PATH,
    )
    parser.add_argument(
        "--soh-csv",
        type=Path,
        default=DEFAULT_SOH_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = validate_activity_2_3(
        severe_path=args.severe_json,
        soh_path=args.soh_csv,
        output_path=args.output,
    )

    print("Activity 2.3 frequency-metric closure")
    print(f"status={report['status']}")
    print(f"canonical_metric={report['canonical_metric']}")
    print(
        "all_frequency_metrics_coherent="
        f"{report['all_frequency_metrics_coherent']}"
    )
    print(
        "all_frequency_criteria_pass="
        f"{report['all_frequency_criteria_pass']}"
    )
    print(
        "all_post_step_traces_within_recovery_band="
        f"{report['all_post_step_traces_within_recovery_band']}"
    )
    print(f"output_path={args.output}")
    for record in report["records"]:
        print(
            f"scenario={record['label']} | "
            f"max_abs_dev="
            f"{record.get(CANONICAL_METRIC, float('nan')):.12f} Hz | "
            f"max_drop="
            f"{record.get('max_frequency_drop_hz', float('nan')):.12f} Hz | "
            f"recovery="
            f"{record.get('frequency_recovery_time_s', float('nan')):.12g} s | "
            f"coherent={record['frequency_metric_coherent']} | "
            f"frequency_pass="
            f"{record.get('frequency_criteria_pass', False)}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
