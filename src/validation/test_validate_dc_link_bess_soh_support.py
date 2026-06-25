"""Tests for BESS discharge, SoH and no-support comparison validation."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_dc_link_bess_soh_support import (
    build_markdown_report,
    build_no_support_model,
    build_supported_model,
    classify_soh_case,
    save_comparison_outputs,
    soh_scenarios,
)


class TestDCLinkBESSSoHSupport(unittest.TestCase):
    def test_required_soh_cases_are_exactly_present(self) -> None:
        scenarios = soh_scenarios()
        labels = [label for label, _ in scenarios]
        values = [value for _, value in scenarios]
        self.assertEqual(labels, ["SoH_1p00", "SoH_0p70", "SoH_nominal"])
        self.assertEqual(values[0], 1.0)
        self.assertEqual(values[1], 0.70)
        self.assertLess(values[2], 0.70)
        self.assertGreaterEqual(values[2], 0.50)

    def test_comparison_models_differ_only_by_support_architecture(self) -> None:
        no_support = build_no_support_model()
        supported = build_supported_model(soh_scenarios()[2][1])
        no_support_state = no_support.initial_state()
        supported_state = supported.initial_state_with_bess()

        self.assertEqual(len(no_support_state), 12)
        self.assertEqual(len(supported_state), 16)
        self.assertTrue(supported.bess_enabled)
        self.assertEqual(no_support.controller.frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(supported.controller.frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(no_support.controller.frequency_dynamics.damping_d, 1500.0)
        self.assertEqual(supported.controller.frequency_dynamics.damping_d, 1500.0)

    def test_soh_case_pass_requires_discharge_and_every_limit(self) -> None:
        passing = {
            "solver_success": True,
            "finite": True,
            "frequency_pass": True,
            "vdc_pass": True,
            "discharge_observed": True,
            "positive_mean_discharge": True,
            "current_limit_pass": True,
            "power_limit_pass": True,
            "soc_limit_pass": True,
            "soh_limit_pass": True,
        }
        self.assertEqual(classify_soh_case(**passing), "PASS")
        for failed_name in passing:
            flags = dict(passing)
            flags[failed_name] = False
            self.assertEqual(classify_soh_case(**flags), "FAIL")

    def test_comparison_figure_and_csv_are_created(self) -> None:
        time = np.linspace(0.0, 1.0, 11)
        no_support = {
            "t": time,
            "vdc": np.full_like(time, 340.0),
            "frequency_hz": np.full_like(time, 60.0),
            "p_bess": np.zeros_like(time),
        }
        corrected = {
            "t": time,
            "vdc": np.full_like(time, 339.0),
            "frequency_hz": np.full_like(time, 59.99),
            "p_bess": np.full_like(time, 100.0),
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            figure_path = Path(tmp_dir) / "comparison.png"
            csv_path = Path(tmp_dir) / "comparison.csv"
            saved_figure, saved_csv = save_comparison_outputs(
                no_support,
                corrected,
                figure_path=figure_path,
                csv_path=csv_path,
            )
            self.assertEqual(saved_figure, figure_path)
            self.assertEqual(saved_csv, csv_path)
            self.assertTrue(figure_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertGreater(figure_path.stat().st_size, 0)
            self.assertGreater(csv_path.stat().st_size, 0)

    def test_markdown_report_contains_results_criteria_limitations_and_files(self) -> None:
        case = {
            "label": "SoH_1p00",
            "soh_initial": 1.0,
            "status": "PASS",
            "discharge_observed_post_step": True,
            "p_bess_mean_post_step_w": 100.0,
            "i_bess_max_post_step_a": 1.0,
            "current_limit_pass": True,
            "power_limit_pass": True,
            "vdc_criteria_pass": True,
            "frequency_criteria_pass": True,
        }
        report = {
            "M": 80.0,
            "D": 1500.0,
            "Kp_w_per_v": 170.0,
            "Ki_w_per_v_s": 10.0,
            "soh_cases": [case],
            "comparison": {
                "no_support": {
                    "vdc_min_post_step_v": 330.0,
                    "max_frequency_drop_hz": 0.1,
                },
                "corrected_support": {
                    "vdc_min_post_step_v": 335.0,
                    "max_frequency_drop_hz": 0.05,
                },
            },
            "summary_path": "summary.json",
            "soh_csv_path": "soh.csv",
            "comparison_csv_path": "comparison.csv",
            "figure_path": "comparison.png",
            "status": "PASS",
        }
        markdown = build_markdown_report(report)
        self.assertIn("## Resultados por SoH", markdown)
        self.assertIn("## Criterios", markdown)
        self.assertIn("## Limitaciones", markdown)
        self.assertIn("## Archivos generados", markdown)
        self.assertIn("## Estado final: PASS", markdown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
