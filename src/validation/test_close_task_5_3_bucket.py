"""Tests for the formal Task 5.3 severe-scenario closure gate."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.close_task_5_3_bucket import (
    REQUIRED_CHECKS,
    build_closure_report,
    classify_bucket,
)
from validation.validate_dc_link_pi_scenarios import SEVERE_SCENARIO


class TestTask53BucketClosure(unittest.TestCase):
    def _passing_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "scenario": SEVERE_SCENARIO.name,
            "load_step_pct": 40.0,
        }
        record.update({check: True for check in REQUIRED_CHECKS})
        return record

    def test_bucket_closes_only_when_every_required_condition_passes(self) -> None:
        status, failed = classify_bucket(self._passing_record())
        self.assertEqual(status, "CLOSED")
        self.assertEqual(failed, [])

    def test_any_failed_frequency_dc_or_bess_check_keeps_bucket_open(self) -> None:
        for failed_check in (
            "frequency_criteria_pass",
            "vdc_criteria_pass",
            "current_limit_pass",
            "power_limit_pass",
            "soc_limit_pass",
            "soh_limit_pass",
            "bess_limits_pass",
        ):
            with self.subTest(failed_check=failed_check):
                record = self._passing_record()
                record[failed_check] = False
                status, failed = classify_bucket(record)
                self.assertEqual(status, "OPEN")
                self.assertIn(failed_check, failed)

    def test_nonsevere_or_wrong_load_step_cannot_close_bucket(self) -> None:
        record = self._passing_record()
        record["scenario"] = "base_20pct"
        record["load_step_pct"] = 20.0
        status, failed = classify_bucket(record)
        self.assertEqual(status, "OPEN")
        self.assertIn("severe_scenario_identity", failed)
        self.assertIn("severe_load_step_40pct", failed)

    def test_report_contains_explicit_three_domain_closure_matrix(self) -> None:
        report = build_closure_report(self._passing_record())
        self.assertEqual(report["bucket_status"], "CLOSED")
        self.assertTrue(report["conditions"]["frequency_pass"])
        self.assertTrue(report["conditions"]["dc_link_pass"])
        self.assertTrue(report["conditions"]["bess_restrictions_pass"])
        self.assertFalse(report["controller_modified_during_closure"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
