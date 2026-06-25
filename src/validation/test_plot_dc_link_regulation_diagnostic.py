"""Tests for the consolidated DC-link regulation diagnostic."""

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

from validation.plot_dc_link_regulation_diagnostic import (
    OUTPUT_DIR,
    REQUIRED_COLUMNS,
    build_numerical_summary,
    load_diagnostic_signals,
    save_consolidated_figure,
)


class TestDCLinkRegulationDiagnostic(unittest.TestCase):
    def _write_trace(self, path: Path) -> None:
        time = np.linspace(0.0, 2.0, 201)
        vdc = np.where(time < 0.8, 344.0, 338.5)
        p_load = np.where(time < 0.8, 3000.0, 4200.0)
        p_source = np.full_like(time, 3780.0)
        i_bess = 0.5 * (340.0 - vdc)
        p_bess = vdc * i_bess
        with path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_COLUMNS)
            writer.writeheader()
            for k in range(time.size):
                writer.writerow(
                    {
                        "time_s": time[k],
                        "vdc_v": vdc[k],
                        "p_load_w": p_load[k],
                        "p_source_pv_dc_w": p_source[k],
                        "p_bess_dc_w": p_bess[k],
                        "i_bess_a": i_bess[k],
                    }
                )

    def test_default_output_directory_matches_task_requirement(self) -> None:
        self.assertEqual(OUTPUT_DIR.name, "dc_link_regulation")
        self.assertEqual(OUTPUT_DIR.parent.name, "validation")

    def test_loader_reads_all_required_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signals.csv"
            self._write_trace(csv_path)
            signals = load_diagnostic_signals(csv_path)
            self.assertEqual(tuple(signals), REQUIRED_COLUMNS)
            self.assertEqual(signals["time_s"].size, 201)

    def test_summary_records_controller_unchanged_and_bess_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signals.csv"
            self._write_trace(csv_path)
            signals = load_diagnostic_signals(csv_path)
            summary = build_numerical_summary(signals, t_step=0.8)
            self.assertFalse(summary["controller_modified"])
            self.assertTrue(summary["bess_power_identity_ok"])
            self.assertEqual(summary["bess_exchange_mode_post_step"], "discharge_only")
            self.assertAlmostEqual(summary["p_load_post_step_mean_w"], 4200.0)
            self.assertAlmostEqual(summary["vdc_final_v"], 338.5)

    def test_consolidated_figure_is_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signals.csv"
            figure_path = Path(tmp_dir) / "diagnostic.png"
            self._write_trace(csv_path)
            signals = load_diagnostic_signals(csv_path)
            summary = build_numerical_summary(signals, t_step=0.8)
            saved = save_consolidated_figure(
                signals,
                summary,
                figure_path,
                dpi=100,
            )
            self.assertEqual(saved, figure_path)
            self.assertTrue(figure_path.exists())
            self.assertGreater(figure_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
