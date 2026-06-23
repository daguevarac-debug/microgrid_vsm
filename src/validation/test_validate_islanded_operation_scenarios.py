"""Unit tests for the selected-GFM severe-scenario validation helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_islanded_operation_scenarios import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    GFM_SEVERE_T_END_S,
    _classify_selected_gfm_severe_status,
    _json_ready_record,
)


class TestSelectedGFMSevereValidation(unittest.TestCase):
    def test_selected_operating_point_and_horizon_are_fixed(self) -> None:
        self.assertEqual(GFM_SELECTED_M, 40.0)
        self.assertEqual(GFM_SELECTED_D, 100.0)
        self.assertEqual(GFM_SEVERE_T_END_S, 6.5)

    def test_pass_requires_all_acceptance_conditions(self) -> None:
        status = _classify_selected_gfm_severe_status(
            solver_success=True,
            states_finite=True,
            scenario_configuration_ok=True,
            frequency_criteria_pass=True,
            vdc_criteria_pass=True,
        )
        self.assertEqual(status, "PASS")

    def test_valid_simulation_with_criterion_violation_requires_review(self) -> None:
        status = _classify_selected_gfm_severe_status(
            solver_success=True,
            states_finite=True,
            scenario_configuration_ok=True,
            frequency_criteria_pass=False,
            vdc_criteria_pass=True,
        )
        self.assertEqual(status, "REVIEW")

    def test_numerical_or_configuration_failure_is_fail(self) -> None:
        for kwargs in (
            {
                "solver_success": False,
                "states_finite": True,
                "scenario_configuration_ok": True,
            },
            {
                "solver_success": True,
                "states_finite": False,
                "scenario_configuration_ok": True,
            },
            {
                "solver_success": True,
                "states_finite": True,
                "scenario_configuration_ok": False,
            },
        ):
            with self.subTest(kwargs=kwargs):
                status = _classify_selected_gfm_severe_status(
                    frequency_criteria_pass=True,
                    vdc_criteria_pass=True,
                    **kwargs,
                )
                self.assertEqual(status, "FAIL")

    def test_json_record_replaces_nonfinite_float_with_null(self) -> None:
        converted = _json_ready_record(
            {
                "finite": np.float64(1.25),
                "nan_value": float("nan"),
                "flag": np.bool_(True),
            }
        )
        self.assertEqual(converted["finite"], 1.25)
        self.assertIsNone(converted["nan_value"])
        self.assertIs(converted["flag"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
