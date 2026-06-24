"""Unit tests for Activity 2.3 frequency-metric closure."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_activity_2_3_frequency_metric import (
    CANONICAL_METRIC,
    EXPECTED_SELECTED_D,
    EXPECTED_SELECTED_M,
    NONCANONICAL_ALIAS,
    validate_activity_2_3,
    validate_frequency_record,
)


def _record(
    *,
    label: str = "case",
    frequency_pre: float = 60.0526506942,
    frequency_min: float = 59.9275662220,
    frequency_max: float = 60.058,
    recovery_time: float = 1e-6,
) -> dict[str, object]:
    max_abs = max(
        abs(frequency_min - 60.0),
        abs(frequency_max - 60.0),
    )
    max_drop = max(frequency_pre - frequency_min, 0.0)
    return {
        "label": label,
        "M": EXPECTED_SELECTED_M,
        "D": EXPECTED_SELECTED_D,
        "frequency_pre_step_hz": frequency_pre,
        "frequency_min_post_step_hz": frequency_min,
        "frequency_max_post_step_hz": frequency_max,
        "max_frequency_drop_hz": max_drop,
        CANONICAL_METRIC: max_abs,
        "frequency_recovery_time_s": recovery_time,
        "frequency_drop_pass": max_drop <= 0.50,
        "frequency_recovery_pass": recovery_time <= 5.0,
        "frequency_criteria_pass": (
            max_drop <= 0.50 and recovery_time <= 5.0
        ),
    }


class TestActivity23FrequencyMetric(unittest.TestCase):
    def test_canonical_record_is_coherent(self) -> None:
        result = validate_frequency_record(
            _record(),
            label="severe",
        )
        self.assertTrue(result["frequency_metric_coherent"])
        self.assertTrue(
            result["entire_post_step_within_recovery_band"]
        )

    def test_drop_and_absolute_deviation_use_different_references(self) -> None:
        result = validate_frequency_record(
            _record(),
            label="severe",
        )
        self.assertGreater(
            result["max_frequency_drop_hz"],
            result[CANONICAL_METRIC],
        )
        self.assertTrue(result["drop_definition_ok"])
        self.assertTrue(result["metric_definition_ok"])

    def test_noncanonical_alias_is_rejected(self) -> None:
        record = _record()
        record[NONCANONICAL_ALIAS] = record[CANONICAL_METRIC]
        result = validate_frequency_record(
            record,
            label="alias_case",
        )
        self.assertFalse(result["noncanonical_alias_absent"])
        self.assertFalse(result["frequency_metric_coherent"])

    def test_incorrect_metric_value_is_rejected(self) -> None:
        record = _record()
        record[CANONICAL_METRIC] = 0.5
        result = validate_frequency_record(
            record,
            label="bad_metric",
        )
        self.assertFalse(result["metric_definition_ok"])
        self.assertFalse(result["frequency_metric_coherent"])

    def test_other_selected_point_is_rejected(self) -> None:
        record = _record()
        record["M"] = 40.0
        record["D"] = 100.0
        result = validate_frequency_record(
            record,
            label="stale_selected_point",
        )
        self.assertFalse(result["selected_point_matches"])
        self.assertFalse(result["frequency_metric_coherent"])

    def test_full_closure_report_passes_for_consistent_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            severe_path = root / "severe.json"
            soh_path = root / "soh.csv"
            output_path = root / "report.json"

            severe = _record(label="severe")
            severe["scenario"] = "severe"
            severe_path.write_text(
                json.dumps(severe),
                encoding="utf-8",
            )

            rows = [
                _record(
                    label="SoH_1p00",
                    frequency_pre=60.052,
                    frequency_min=60.046,
                    frequency_max=60.058,
                    recovery_time=8e-6,
                ),
                _record(
                    label="SoH_0p70",
                    frequency_pre=60.052,
                    frequency_min=60.046,
                    frequency_max=60.058,
                    recovery_time=8e-6,
                ),
                _record(
                    label="SoH_nominal",
                    frequency_pre=60.052,
                    frequency_min=60.046,
                    frequency_max=60.058,
                    recovery_time=8e-6,
                ),
            ]
            with soh_path.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=list(rows[0].keys()),
                )
                writer.writeheader()
                writer.writerows(rows)

            report = validate_activity_2_3(
                severe_path=severe_path,
                soh_path=soh_path,
                output_path=output_path,
            )

            self.assertEqual(report["status"], "PASS")
            self.assertTrue(
                report["all_frequency_metrics_coherent"]
            )
            self.assertTrue(
                report["all_frequency_criteria_pass"]
            )
            self.assertTrue(
                report["all_selected_point_records_match"]
            )
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
