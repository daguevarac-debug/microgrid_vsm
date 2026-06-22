from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.refine_gfm_parameters import (
    D_REFINEMENT_DEFAULT,
    M_REFINEMENT_DEFAULT,
    MAX_VALUES_PER_PARAMETER,
    bisection_triplet,
    build_refinement_grid,
    main,
    resolve_refinement_values,
)


class TestBoundedRefinementGrid(unittest.TestCase):
    def test_default_grid_is_three_by_three(self) -> None:
        grid = build_refinement_grid()

        self.assertEqual(MAX_VALUES_PER_PARAMETER, 3)
        self.assertEqual(len(grid), 9)
        self.assertEqual(grid[0], (10.0, 50.0))
        self.assertEqual(grid[-1], (40.0, 200.0))
        self.assertEqual(
            grid,
            tuple(
                (m_value, d_value)
                for m_value in M_REFINEMENT_DEFAULT
                for d_value in D_REFINEMENT_DEFAULT
            ),
        )

    def test_more_than_three_unique_m_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3 unique M"):
            build_refinement_grid(
                m_values=(10.0, 15.0, 20.0, 25.0),
                d_values=(50.0,),
            )

    def test_more_than_three_unique_d_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3 unique D"):
            build_refinement_grid(
                m_values=(20.0,),
                d_values=(50.0, 75.0, 100.0, 125.0),
            )

    def test_duplicate_values_do_not_consume_extra_slots(self) -> None:
        grid = build_refinement_grid(
            m_values=(10.0, 10.0, 20.0, 40.0),
            d_values=(50.0, 50.0, 100.0),
        )

        self.assertEqual(len(grid), 6)
        self.assertEqual(grid[0], (10.0, 50.0))
        self.assertEqual(grid[-1], (40.0, 100.0))


class TestBisectionRefinement(unittest.TestCase):
    def test_bisection_returns_bounds_and_midpoint(self) -> None:
        self.assertEqual(
            bisection_triplet("M", 10.0, 40.0, strictly_positive=True),
            (10.0, 25.0, 40.0),
        )
        self.assertEqual(
            bisection_triplet("D", 50.0, 200.0, strictly_positive=False),
            (50.0, 125.0, 200.0),
        )

    def test_invalid_or_reversed_range_is_rejected(self) -> None:
        for lower, upper in ((10.0, 10.0), (20.0, 10.0)):
            with self.subTest(lower=lower, upper=upper):
                with self.assertRaises(ValueError):
                    bisection_triplet(
                        "M",
                        lower,
                        upper,
                        strictly_positive=True,
                    )

    def test_parameter_bounds_are_preserved_for_ranges(self) -> None:
        with self.assertRaises(ValueError):
            bisection_triplet("M", 0.0, 10.0, strictly_positive=True)
        with self.assertRaises(ValueError):
            bisection_triplet("D", -1.0, 10.0, strictly_positive=False)

    def test_ranges_generate_at_most_nine_candidates(self) -> None:
        m_values, d_values = resolve_refinement_values(
            m_range=(10.0, 25.0),
            d_range=(50.0, 125.0),
        )
        grid = build_refinement_grid(
            m_range=(10.0, 25.0),
            d_range=(50.0, 125.0),
        )

        self.assertEqual(m_values, (10.0, 17.5, 25.0))
        self.assertEqual(d_values, (50.0, 87.5, 125.0))
        self.assertEqual(len(grid), 9)


class TestRefinementCLI(unittest.TestCase):
    def test_default_dry_run_prints_nine_candidates_without_simulation(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["--dry-run"])

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("max_values_per_parameter=3", text)
        self.assertIn("m_values=10 20 40", text)
        self.assertIn("d_values=50 100 200", text)
        self.assertIn("grid_size=9", text)
        self.assertIn("run=9 | M=40 | D=200", text)
        self.assertIn("simulations_executed=0", text)

    def test_range_dry_run_prints_bisection_triplets(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--m-range",
                    "10",
                    "25",
                    "--d-range",
                    "50",
                    "125",
                    "--dry-run",
                ]
            )

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("m_values=10 17.5 25", text)
        self.assertIn("d_values=50 87.5 125", text)
        self.assertIn("grid_size=9", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
