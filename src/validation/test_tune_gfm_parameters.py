from __future__ import annotations

import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.tune_gfm_parameters import (
    CSV_FIELDNAMES,
    D_SWEEP_DEFAULT,
    M_SWEEP_DEFAULT,
    build_parameter_grid,
    main,
    write_runs_csv,
)


class TestGFMParameterGrid(unittest.TestCase):
    def test_default_grid_has_42_ordered_candidates(self) -> None:
        grid = build_parameter_grid()

        self.assertEqual(len(grid), 42)
        self.assertEqual(grid[0], (2.0, 0.0))
        self.assertEqual(grid[1], (2.0, 50.0))
        self.assertEqual(grid[-1], (80.0, 1500.0))
        self.assertEqual(
            grid,
            tuple(
                (m_value, d_value)
                for m_value in M_SWEEP_DEFAULT
                for d_value in D_SWEEP_DEFAULT
            ),
        )

    def test_duplicate_values_are_removed_without_reordering(self) -> None:
        grid = build_parameter_grid(
            m_values=(2.0, 2.0, 5.0),
            d_values=(50.0, 0.0, 50.0),
        )

        self.assertEqual(
            grid,
            (
                (2.0, 50.0),
                (2.0, 0.0),
                (5.0, 50.0),
                (5.0, 0.0),
            ),
        )

    def test_nonpositive_m_is_rejected(self) -> None:
        for invalid_m in (0.0, -1.0):
            with self.subTest(invalid_m=invalid_m):
                with self.assertRaises(ValueError):
                    build_parameter_grid(m_values=(invalid_m,), d_values=(0.0,))

    def test_negative_d_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_parameter_grid(m_values=(2.0,), d_values=(-1.0,))


class TestGFMSweepCSV(unittest.TestCase):
    def test_csv_uses_stable_header_and_one_row_per_record(self) -> None:
        record = {field: "" for field in CSV_FIELDNAMES}
        record.update(
            {
                "run_index": 1,
                "scenario": "load_step_20_no_bess",
                "M": 2.0,
                "D": 50.0,
                "status": "ok",
                "candidate_admissible": False,
            }
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "nested" / "sensitivity_runs.csv"
            returned_path = write_runs_csv([record], output_path)

            self.assertEqual(returned_path, output_path)
            self.assertTrue(output_path.exists())
            with output_path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)

            self.assertEqual(tuple(reader.fieldnames or ()), CSV_FIELDNAMES)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["scenario"], "load_step_20_no_bess")
            self.assertEqual(rows[0]["M"], "2.0")
            self.assertEqual(rows[0]["D"], "50.0")
            self.assertEqual(rows[0]["status"], "ok")

    def test_dry_run_does_not_execute_simulations(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--m-values",
                    "2",
                    "5",
                    "--d-values",
                    "0",
                    "50",
                    "--dry-run",
                ]
            )

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("grid_size=4", text)
        self.assertIn("run=1 | M=2 | D=0", text)
        self.assertIn("run=4 | M=5 | D=50", text)
        self.assertIn("dry_run=True", text)
        self.assertIn("simulations_executed=0", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
