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
    CRITERIA_VERSION,
    CSV_FIELDNAMES,
    D_SWEEP_DEFAULT,
    D_SWEEP_EXTENDED,
    MAX_VALUES_PER_PARAMETER,
    M_SWEEP_DEFAULT,
    M_SWEEP_EXTENDED,
    SWEEP_PROFILE_CUSTOM,
    SWEEP_PROFILE_EXTENDED,
    SWEEP_PROFILE_INITIAL,
    VDC_ACCEPTANCE_BASIS,
    build_parameter_grid,
    main,
    write_runs_csv,
)


class TestGFMParameterGrid(unittest.TestCase):
    def test_default_grid_is_formal_three_by_three(self) -> None:
        grid = build_parameter_grid()

        self.assertEqual(MAX_VALUES_PER_PARAMETER, 3)
        self.assertEqual(M_SWEEP_DEFAULT, (2.0, 20.0, 80.0))
        self.assertEqual(D_SWEEP_DEFAULT, (0.0, 200.0, 1500.0))
        self.assertEqual(len(grid), 9)
        self.assertEqual(grid[0], (2.0, 0.0))
        self.assertEqual(grid[1], (2.0, 200.0))
        self.assertEqual(grid[-1], (80.0, 1500.0))

    def test_historical_extended_grid_has_42_candidates(self) -> None:
        grid = build_parameter_grid(
            M_SWEEP_EXTENDED,
            D_SWEEP_EXTENDED,
            max_values_per_parameter=None,
        )

        self.assertEqual(len(grid), 42)
        self.assertEqual(grid[0], (2.0, 0.0))
        self.assertEqual(grid[-1], (80.0, 1500.0))

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

    def test_more_than_three_unique_m_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3 unique values"):
            build_parameter_grid(
                m_values=(2.0, 5.0, 10.0, 20.0),
                d_values=(0.0,),
            )

    def test_more_than_three_unique_d_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3 unique values"):
            build_parameter_grid(
                m_values=(2.0,),
                d_values=(0.0, 50.0, 100.0, 200.0),
            )

    def test_nonpositive_m_is_rejected(self) -> None:
        for invalid_m in (0.0, -1.0):
            with self.subTest(invalid_m=invalid_m):
                with self.assertRaises(ValueError):
                    build_parameter_grid(
                        m_values=(invalid_m,),
                        d_values=(0.0,),
                    )

    def test_negative_d_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_parameter_grid(
                m_values=(2.0,),
                d_values=(-1.0,),
            )


class TestGFMSweepCSV(unittest.TestCase):
    def test_csv_uses_stable_header_and_one_row_per_record(self) -> None:
        record = {field: "" for field in CSV_FIELDNAMES}
        record.update(
            {
                "run_index": 1,
                "scenario": "load_step_20_no_bess",
                "criteria_version": CRITERIA_VERSION,
                "vdc_acceptance_basis": VDC_ACCEPTANCE_BASIS,
                "M": 2.0,
                "D": 50.0,
                "vdc_event_max_abs_deviation_pct": 3.8,
                "vdc_event_deviation_pass": True,
                "status": "ok",
                "candidate_admissible": False,
            }
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = (
                Path(temporary_directory)
                / "nested"
                / "sensitivity_runs.csv"
            )
            returned_path = write_runs_csv([record], output_path)

            self.assertEqual(returned_path, output_path)
            self.assertTrue(output_path.exists())
            with output_path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)

            self.assertEqual(tuple(reader.fieldnames or ()), CSV_FIELDNAMES)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["scenario"], "load_step_20_no_bess")
            self.assertEqual(rows[0]["criteria_version"], CRITERIA_VERSION)
            self.assertEqual(
                rows[0]["vdc_acceptance_basis"],
                VDC_ACCEPTANCE_BASIS,
            )
            self.assertEqual(rows[0]["M"], "2.0")
            self.assertEqual(rows[0]["D"], "50.0")
            self.assertEqual(
                rows[0]["vdc_event_max_abs_deviation_pct"],
                "3.8",
            )
            self.assertEqual(
                rows[0]["vdc_event_deviation_pass"],
                "True",
            )
            self.assertEqual(rows[0]["status"], "ok")

    def test_schema_contains_event_relative_dc_fields(self) -> None:
        required_fields = {
            "criteria_version",
            "vdc_acceptance_basis",
            "vdc_pre_step_v",
            "vdc_reference_deviation_pct",
            "vdc_event_max_rise_v",
            "vdc_event_max_drop_v",
            "vdc_event_max_abs_deviation_pct",
            "vdc_event_deviation_pass",
        }

        self.assertTrue(required_fields.issubset(set(CSV_FIELDNAMES)))


class TestGFMSweepCLI(unittest.TestCase):
    def test_default_dry_run_is_formal_three_by_three(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["--dry-run"])

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(f"sweep_profile={SWEEP_PROFILE_INITIAL}", text)
        self.assertIn("max_values_per_parameter=3", text)
        self.assertIn("grid_size=9", text)
        self.assertIn("run=9 | M=80 | D=1500", text)
        self.assertIn("sensitivity_runs_initial_3x3.csv", text)
        self.assertIn("simulations_executed=0", text)

    def test_custom_bounded_dry_run_does_not_execute_simulations(
        self,
    ) -> None:
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
        self.assertIn(f"sweep_profile={SWEEP_PROFILE_CUSTOM}", text)
        self.assertIn("grid_size=4", text)
        self.assertIn("run=1 | M=2 | D=0", text)
        self.assertIn("run=4 | M=5 | D=50", text)
        self.assertIn(f"criteria_version={CRITERIA_VERSION}", text)
        self.assertIn(
            f"vdc_acceptance_basis={VDC_ACCEPTANCE_BASIS}",
            text,
        )
        self.assertIn("dry_run=True", text)
        self.assertIn("simulations_executed=0", text)

    def test_extended_grid_requires_explicit_mode(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["--extended-grid", "--dry-run"])

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(f"sweep_profile={SWEEP_PROFILE_EXTENDED}", text)
        self.assertIn(
            "max_values_per_parameter=unbounded_explicit",
            text,
        )
        self.assertIn("grid_size=42", text)
        self.assertIn("run=42 | M=80 | D=1500", text)
        self.assertIn("sensitivity_runs_extended_6x7.csv", text)

    def test_extended_grid_rejects_custom_axis_values(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--extended-grid",
                    "--m-values",
                    "2",
                    "20",
                    "80",
                    "--dry-run",
                ]
            )

        text = output.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("status=FAIL", text)
        self.assertIn("cannot be combined", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
