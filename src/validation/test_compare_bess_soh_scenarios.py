"""Tests for selected-GFM full-model BESS SoH comparison helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.compare_bess_soh_scenarios import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    GFM_SOH_CSV_PATH,
    _available_limit_order_ok,
    _classify_bess_exchange_mode,
    _classify_gfm_soh_case,
    _combine_gfm_soh_statuses,
    _gfm_soh_scenarios,
)


class TestGFMSoHComparison(unittest.TestCase):
    def test_selected_point_and_scenarios(self) -> None:
        self.assertEqual(GFM_SELECTED_M, 80.0)
        self.assertEqual(GFM_SELECTED_D, 1500.0)
        self.assertEqual(
            GFM_SOH_CSV_PATH.name,
            "gfm_m80_d1500_bess_soh_scenarios_summary.csv",
        )
        scenarios = dict(_gfm_soh_scenarios())
        self.assertEqual(scenarios["SoH_1p00"], 1.0)
        self.assertEqual(scenarios["SoH_0p70"], 0.70)
        self.assertAlmostEqual(scenarios["SoH_nominal"], 44.1 / 66.0)

    def test_case_status_classification(self) -> None:
        self.assertEqual(
            _classify_gfm_soh_case(
                hard_checks_ok=True,
                frequency_criteria_pass=True,
                vdc_criteria_pass=True,
            ),
            "PASS",
        )
        self.assertEqual(
            _classify_gfm_soh_case(
                hard_checks_ok=True,
                frequency_criteria_pass=False,
                vdc_criteria_pass=True,
            ),
            "REVIEW",
        )
        self.assertEqual(
            _classify_gfm_soh_case(
                hard_checks_ok=False,
                frequency_criteria_pass=True,
                vdc_criteria_pass=True,
            ),
            "FAIL",
        )

    def test_overall_status_classification(self) -> None:
        self.assertEqual(
            _combine_gfm_soh_statuses(
                ["PASS", "PASS", "PASS"],
                available_limit_order_ok=True,
            ),
            "PASS",
        )
        self.assertEqual(
            _combine_gfm_soh_statuses(
                ["PASS", "REVIEW", "PASS"],
                available_limit_order_ok=True,
            ),
            "REVIEW",
        )
        self.assertEqual(
            _combine_gfm_soh_statuses(
                ["PASS", "PASS", "PASS"],
                available_limit_order_ok=False,
            ),
            "FAIL",
        )

    def test_bess_exchange_mode_uses_repository_sign_convention(self) -> None:
        self.assertEqual(
            _classify_bess_exchange_mode(np.array([-2.4, -0.8])),
            "charge_only",
        )
        self.assertEqual(
            _classify_bess_exchange_mode(np.array([0.2, 1.0])),
            "discharge_only",
        )
        self.assertEqual(
            _classify_bess_exchange_mode(np.array([-0.5, 0.5])),
            "bidirectional",
        )
        self.assertEqual(
            _classify_bess_exchange_mode(np.zeros(3)),
            "idle",
        )

    def test_available_limit_order(self) -> None:
        rows = [
            {
                "label": "SoH_1p00",
                "i_bess_max_available_initial": 66.0,
                "p_bess_dc_max_available_initial": 22440.0,
            },
            {
                "label": "SoH_0p70",
                "i_bess_max_available_initial": 46.2,
                "p_bess_dc_max_available_initial": 15708.0,
            },
            {
                "label": "SoH_nominal",
                "i_bess_max_available_initial": 44.1,
                "p_bess_dc_max_available_initial": 14994.0,
            },
        ]
        self.assertTrue(_available_limit_order_ok(rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
