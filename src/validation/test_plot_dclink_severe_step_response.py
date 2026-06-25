"""Tests for the reproducible severe DC-link response figure."""

from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tuning_metrics import DEFAULT_TUNING_CRITERIA
from validation.plot_dclink_severe_step_response import (
    build_response_metrics,
    load_vdc_trace,
    save_step_response_figure,
)


class TestDCLinkSevereStepResponse(unittest.TestCase):
    def test_csv_loader_reads_requested_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "trace.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=("time_s", "vdc_v", "p_load_w"),
                )
                writer.writeheader()
                writer.writerow({"time_s": 0.0, "vdc_v": 340.0, "p_load_w": 3000.0})
                writer.writerow({"time_s": 1.0, "vdc_v": 338.0, "p_load_w": 4200.0})
            time, vdc = load_vdc_trace(csv_path)
            np.testing.assert_allclose(time, np.array([0.0, 1.0]))
            np.testing.assert_allclose(vdc, np.array([340.0, 338.0]))

    def test_metrics_include_band_minimum_deviation_recovery_and_final_state(self) -> None:
        time = np.linspace(0.0, 2.0, 201)
        vdc = np.full_like(time, 340.0)
        vdc[(time >= 0.8) & (time < 0.9)] = 330.0
        vdc[(time >= 0.9) & (time < 1.0)] = 335.0
        metrics = build_response_metrics(time, vdc, t_step=0.8)

        self.assertAlmostEqual(metrics["vdc_reference_v"], 340.0)
        self.assertAlmostEqual(metrics["acceptance_band_lower_v"], 323.0)
        self.assertAlmostEqual(metrics["acceptance_band_upper_v"], 357.0)
        self.assertAlmostEqual(metrics["vdc_min_post_step_v"], 330.0)
        self.assertAlmostEqual(metrics["vdc_event_max_abs_deviation_v"], 10.0)
        self.assertTrue(metrics["recovery_verified"])
        self.assertAlmostEqual(metrics["vdc_recovery_time_s"], 0.0)
        self.assertAlmostEqual(metrics["vdc_final_v"], 340.0)
        self.assertTrue(metrics["final_in_acceptance_band"])

    def test_recovery_is_unverified_when_trace_stays_outside_band(self) -> None:
        time = np.linspace(0.0, 2.0, 201)
        vdc = np.where(time < 0.8, 340.0, 300.0)
        metrics = build_response_metrics(time, vdc, t_step=0.8)
        self.assertFalse(metrics["recovery_verified"])
        self.assertTrue(np.isnan(metrics["vdc_recovery_time_s"]))
        self.assertFalse(metrics["final_in_acceptance_band"])

    def test_figure_is_saved_as_nonempty_png(self) -> None:
        time = np.linspace(0.0, 2.0, 201)
        vdc = 340.0 - 6.0 * np.exp(-4.0 * np.maximum(time - 0.8, 0.0))
        vdc[time < 0.8] = 340.0
        metrics = build_response_metrics(time, vdc, t_step=0.8)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "vdc_response.png"
            saved_path = save_step_response_figure(
                time,
                vdc,
                metrics,
                output_path,
                dpi=100,
            )
            self.assertEqual(saved_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    def test_band_uses_repository_event_deviation_criterion(self) -> None:
        self.assertAlmostEqual(
            DEFAULT_TUNING_CRITERIA.max_vdc_event_deviation_pct,
            5.0,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
