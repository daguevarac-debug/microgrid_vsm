"""Unit tests for Objective 2.3 multi-scenario VSG tuning helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.tune_objective2_vsg_parameters import (
    aggregate_score,
    build_candidate_grid,
    limited_values,
    max_abs_rocof,
    normalized_terms,
    rank_candidates,
    renormalized_weights,
    scenario_score,
    stability_accepts,
)
from validation.validate_objective2_small_signal_stability import _modal_sensitivity


class TestTuneObjective2VSGParameters(unittest.TestCase):
    def test_build_default_grid_3x3(self) -> None:
        grid = build_candidate_grid()
        self.assertEqual(len(grid), 9)
        self.assertIn({"candidate_id": 9, "M": 80.0, "D": 1500.0}, grid)

    def test_reject_more_than_three_values(self) -> None:
        with self.assertRaises(ValueError):
            limited_values("M", [1, 2, 3, 4], strictly_positive=True)

    def test_normalized_metrics(self) -> None:
        terms = normalized_terms(
            {
                "max_frequency_abs_deviation_hz": 0.25,
                "max_abs_rocof_hz_per_s": 2.5,
                "frequency_recovery_time_s": 2.5,
                "frequency_steady_state_error_hz": 0.05,
                "vdc_event_max_abs_deviation_pct": 2.5,
                "vdc_steady_state_error_pct": 2.5,
                "current_utilization": 0.5,
                "power_utilization": 0.5,
                "delta_soc": 0.4,
                "soc_range": 0.8,
            },
            with_bess=True,
        )
        self.assertAlmostEqual(terms["frequency_deviation"], 0.5)
        self.assertAlmostEqual(terms["soc_excursion"], 0.5)

    def test_renormalized_weights_without_bess(self) -> None:
        weights = renormalized_weights(False)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertEqual(weights["bess_current_stress"], 0.0)

    def test_aggregate_score_and_penalty(self) -> None:
        self.assertAlmostEqual(aggregate_score([1, 1, 1, 1], hard_constraints_pass=True), 1.0)
        self.assertGreater(aggregate_score([0], hard_constraints_pass=False), 999.0)

    def test_scenario_score(self) -> None:
        metrics = {
            "max_frequency_abs_deviation_hz": 0.0,
            "max_abs_rocof_hz_per_s": 0.0,
            "frequency_recovery_time_s": 0.0,
            "frequency_steady_state_error_hz": 0.0,
            "vdc_event_max_abs_deviation_pct": 0.0,
            "vdc_steady_state_error_pct": 0.0,
            "current_utilization": 0.0,
            "power_utilization": 0.0,
            "delta_soc": 0.0,
            "soc_range": 1.0,
        }
        self.assertEqual(scenario_score(metrics, with_bess=True), 0.0)

    def test_deterministic_ranking(self) -> None:
        ranked = rank_candidates([
            {"M": 80.0, "D": 1500.0, "aggregate_score": 1.0, "hard_constraints_pass_all": True, "small_signal_accepted": True},
            {"M": 20.0, "D": 200.0, "aggregate_score": 1.0, "hard_constraints_pass_all": True, "small_signal_accepted": True},
        ])
        self.assertEqual(ranked[0]["M"], 20.0)

    def test_rocof_known_signal(self) -> None:
        t = np.linspace(0, 1, 101)
        f = 60.0 + 2.0 * t
        self.assertAlmostEqual(max_abs_rocof(t, f, dt_s=0.01), 2.0, places=6)

    def test_deeply_damped_mode_sensitivity(self) -> None:
        summary, modes = _modal_sensitivity(np.array([1e-6]), np.array([2e-6]), 1.0)
        self.assertFalse(modes[0]["individual_sensitive"])
        self.assertFalse(summary["strong_sensitivity"])

    def test_near_unit_mode_sensitivity(self) -> None:
        summary, modes = _modal_sensitivity(np.array([0.999]), np.array([0.990]), 1.0)
        self.assertTrue(modes[0]["near_unit_circle"])
        self.assertTrue(summary["strong_sensitivity"])

    def test_first_stable_selection_helper(self) -> None:
        report = {
            "architectures": {
                "gfm_12_state_no_bess": {
                    "unstable_modes": [],
                    "zeta_min": 0.5,
                }
            }
        }
        accepted, _reason = stability_accepts(report)
        self.assertTrue(accepted)


if __name__ == "__main__":
    unittest.main()
