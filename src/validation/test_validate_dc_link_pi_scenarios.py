"""Tests for Task 5.3 base and severe DC-link PI validation."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_dc_link_pi_scenarios import (
    BASE_SCENARIO,
    OUTPUT_DIR,
    SCENARIOS,
    SEVERE_SCENARIO,
    build_model,
    classify_overall_status,
    classify_scenario_status,
)


class TestDCLinkPIScenarios(unittest.TestCase):
    def test_required_scenarios_are_exactly_base_20_and_severe_40(self) -> None:
        self.assertEqual(len(SCENARIOS), 2)
        self.assertAlmostEqual(BASE_SCENARIO.step_pct, 20.0)
        self.assertAlmostEqual(SEVERE_SCENARIO.step_pct, 40.0)
        self.assertEqual(BASE_SCENARIO.label, "base")
        self.assertEqual(SEVERE_SCENARIO.label, "severe")

    def test_both_models_use_active_bess_and_selected_pi_gains(self) -> None:
        for spec in SCENARIOS:
            with self.subTest(scenario=spec.name):
                model = build_model(spec)
                state = model.initial_state_with_bess()
                self.assertTrue(model.bess_enabled)
                self.assertEqual(len(state), 16)
                self.assertEqual(model.dc_link_bess_pi.kp_w_per_v, 170.0)
                self.assertEqual(model.dc_link_bess_pi.ki_w_per_v_s, 10.0)
                self.assertEqual(model.controller.frequency_dynamics.inertia_m, 80.0)
                self.assertEqual(model.controller.frequency_dynamics.damping_d, 1500.0)

    def test_scenario_pass_requires_active_bess_and_all_existing_criteria(self) -> None:
        passing = {
            "solver_success": True,
            "states_finite": True,
            "dc_criteria_pass": True,
            "frequency_criteria_pass": True,
            "bess_limits_pass": True,
            "bess_active": True,
        }
        self.assertEqual(classify_scenario_status(**passing), "PASS")
        for failed_name in passing:
            flags = dict(passing)
            flags[failed_name] = False
            self.assertEqual(classify_scenario_status(**flags), "FAIL")

    def test_overall_pass_requires_both_named_scenarios_to_pass(self) -> None:
        passing_records = [
            {"scenario": BASE_SCENARIO.name, "status": "PASS"},
            {"scenario": SEVERE_SCENARIO.name, "status": "PASS"},
        ]
        self.assertEqual(classify_overall_status(passing_records), "PASS")

        one_failed = [
            {"scenario": BASE_SCENARIO.name, "status": "PASS"},
            {"scenario": SEVERE_SCENARIO.name, "status": "FAIL"},
        ]
        self.assertEqual(classify_overall_status(one_failed), "FAIL")

        missing_severe = [{"scenario": BASE_SCENARIO.name, "status": "PASS"}]
        self.assertEqual(classify_overall_status(missing_severe), "FAIL")

    def test_outputs_use_dc_link_regulation_directory(self) -> None:
        self.assertEqual(OUTPUT_DIR.name, "dc_link_regulation")
        self.assertEqual(OUTPUT_DIR.parent.name, "validation")
        self.assertNotEqual(BASE_SCENARIO.output_filename, SEVERE_SCENARIO.output_filename)


if __name__ == "__main__":
    unittest.main(verbosity=2)
