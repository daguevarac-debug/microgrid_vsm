from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.plot_gfm_frequency_drop_heatmap import (
    FrequencyDropGrid,
    load_frequency_drop_grid,
    main,
    save_frequency_drop_heatmap,
)


FIELDNAMES = ("M", "D", "max_frequency_drop_hz")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames=FIELDNAMES) -> None:
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestFrequencyDropGridLoading(unittest.TestCase):
    def test_rows_are_sorted_into_expected_matrix(self) -> None:
        rows = [
            {"M": 40, "D": 100, "max_frequency_drop_hz": 0.0344},
            {"M": 20, "D": 50, "max_frequency_drop_hz": 0.0689},
            {"M": 40, "D": 50, "max_frequency_drop_hz": 0.0353},
            {"M": 20, "D": 100, "max_frequency_drop_hz": 0.0590},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "runs.csv"
            _write_csv(csv_path, rows)

            grid = load_frequency_drop_grid(csv_path)

        self.assertEqual(grid.m_values, (20.0, 40.0))
        self.assertEqual(grid.d_values, (50.0, 100.0))
        np.testing.assert_allclose(
            grid.drop_hz,
            np.array([[0.0689, 0.0590], [0.0353, 0.0344]]),
        )

    def test_missing_required_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "runs.csv"
            _write_csv(
                csv_path,
                [{"M": 20, "D": 50}],
                fieldnames=("M", "D"),
            )

            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_frequency_drop_grid(csv_path)

    def test_duplicate_parameter_pair_is_rejected(self) -> None:
        rows = [
            {"M": 20, "D": 50, "max_frequency_drop_hz": 0.0689},
            {"M": 20, "D": 50, "max_frequency_drop_hz": 0.0690},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "runs.csv"
            _write_csv(csv_path, rows)

            with self.assertRaisesRegex(ValueError, "Duplicate result"):
                load_frequency_drop_grid(csv_path)

    def test_incomplete_rectangular_grid_is_rejected(self) -> None:
        rows = [
            {"M": 20, "D": 50, "max_frequency_drop_hz": 0.0689},
            {"M": 20, "D": 100, "max_frequency_drop_hz": 0.0590},
            {"M": 40, "D": 50, "max_frequency_drop_hz": 0.0353},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "runs.csv"
            _write_csv(csv_path, rows)

            with self.assertRaisesRegex(ValueError, "complete rectangular grid"):
                load_frequency_drop_grid(csv_path)

    def test_negative_frequency_drop_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "runs.csv"
            _write_csv(
                csv_path,
                [{"M": 20, "D": 50, "max_frequency_drop_hz": -0.01}],
            )

            with self.assertRaisesRegex(ValueError, "must be >= 0"):
                load_frequency_drop_grid(csv_path)


class TestFrequencyDropHeatmapSaving(unittest.TestCase):
    def test_heatmap_is_saved_as_nonempty_png(self) -> None:
        grid = FrequencyDropGrid(
            m_values=(20.0, 30.0, 40.0),
            d_values=(50.0, 75.0, 100.0),
            drop_hz=np.array(
                [
                    [0.0689, 0.0635, 0.0590],
                    [0.0475, 0.0459, 0.0435],
                    [0.0353, 0.0355, 0.0344],
                ]
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "nested" / "heatmap.png"
            returned_path = save_frequency_drop_heatmap(grid, output_path, dpi=120)

            self.assertEqual(returned_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    def test_cli_generates_figure_from_csv(self) -> None:
        rows = [
            {"M": 20, "D": 50, "max_frequency_drop_hz": 0.0689},
            {"M": 20, "D": 100, "max_frequency_drop_hz": 0.0590},
            {"M": 40, "D": 50, "max_frequency_drop_hz": 0.0353},
            {"M": 40, "D": 100, "max_frequency_drop_hz": 0.0344},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            csv_path = directory / "runs.csv"
            output_path = directory / "heatmap.png"
            _write_csv(csv_path, rows)

            exit_code = main(
                [
                    "--input",
                    str(csv_path),
                    "--output",
                    str(output_path),
                    "--dpi",
                    "120",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
