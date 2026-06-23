from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.select_gfm_operating_point import (
    EXPECTED_CRITERIA_VERSION,
    EXPECTED_VDC_ACCEPTANCE_BASIS,
    load_sweep_csv,
    select_operating_point,
)


class TestGFMOperatingPointSelection(unittest.TestCase):
    @staticmethod
    def _record(
        inertia_m: float,
        damping_d: float,
        frequency_drop_hz: float,
        *,
        admissible: bool = True,
        criteria_version: str = EXPECTED_CRITERIA_VERSION,
    ) -> dict[str, object]:
        return {
            "criteria_version": criteria_version,
            "vdc_acceptance_basis": EXPECTED_VDC_ACCEPTANCE_BASIS,
            "M": inertia_m,
            "D": damping_d,
            "solver_success": admissible,
            "states_finite": admissible,
            "frequency_criteria_pass": admissible,
            "vdc_criteria_pass": admissible,
            "candidate_admissible": admissible,
            "max_frequency_drop_hz": frequency_drop_hz,
            "frequency_recovery_time_s": 0.0,
            "vdc_event_max_abs_deviation_pct": 3.83,
            "vdc_min_post_step_v": 364.8,
        }

    def setUp(self) -> None:
        self.coarse = [
            self._record(20.0, 100.0, 0.0589),
            self._record(40.0, 100.0, 0.0344),
            self._record(80.0, 1500.0, 0.0101),
        ]
        self.refined = [
            self._record(20.0, 50.0, 0.0688946510),
            self._record(20.0, 75.0, 0.0634844694),
            self._record(20.0, 100.0, 0.0589592787),
            self._record(30.0, 50.0, 0.0474927213),
            self._record(30.0, 75.0, 0.0459252153),
            self._record(30.0, 100.0, 0.0434930424),
            self._record(40.0, 50.0, 0.0353277149),
            self._record(40.0, 75.0, 0.0354788988),
            self._record(40.0, 100.0, 0.0344426647),
        ]

    def test_selects_refined_minimum_not_coarse_extreme(self) -> None:
        summary = select_operating_point(self.coarse, self.refined)

        selected = summary["selected_operating_point"]
        coarse_best = summary["coarse_best_diagnostic"]
        diagnostics = summary["diagnostics"]

        self.assertEqual((selected["M"], selected["D"]), (40.0, 100.0))
        self.assertEqual((coarse_best["M"], coarse_best["D"]), (80.0, 1500.0))
        self.assertTrue(diagnostics["coarse_best_on_explored_boundary"])
        self.assertTrue(diagnostics["selected_on_refined_boundary"])
        self.assertFalse(diagnostics["global_optimum_claimed"])
        self.assertTrue(diagnostics["cross_validation_pending"])
        self.assertAlmostEqual(
            diagnostics["frequency_drop_reduction_vs_balanced_pct"],
            25.003,
            places=3,
        )

    def test_nonadmissible_lower_drop_is_ignored(self) -> None:
        refined = list(self.refined)
        refined.append(self._record(35.0, 80.0, 0.001, admissible=False))

        summary = select_operating_point(self.coarse, refined)

        self.assertEqual(
            (
                summary["selected_operating_point"]["M"],
                summary["selected_operating_point"]["D"],
            ),
            (40.0, 100.0),
        )

    def test_exact_tie_uses_lower_m_then_lower_d(self) -> None:
        refined = list(self.refined)
        refined[-1] = self._record(40.0, 100.0, 0.0344)
        refined.append(self._record(35.0, 90.0, 0.0344))
        refined.append(self._record(35.0, 80.0, 0.0344))

        summary = select_operating_point(self.coarse, refined)

        selected = summary["selected_operating_point"]
        self.assertEqual((selected["M"], selected["D"]), (35.0, 80.0))

    def test_missing_balanced_reference_is_rejected(self) -> None:
        refined = [
            record
            for record in self.refined
            if not (record["M"] == 30.0 and record["D"] == 75.0)
        ]

        with self.assertRaisesRegex(ValueError, "M=30, D=75"):
            select_operating_point(self.coarse, refined)

    def test_csv_loader_rejects_legacy_dc_criteria(self) -> None:
        legacy = self._record(
            30.0,
            75.0,
            0.0459,
            criteria_version="legacy_nominal_vdc_reference",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "legacy.csv"
            with path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(legacy.keys()))
                writer.writeheader()
                writer.writerow(legacy)

            with self.assertRaisesRegex(ValueError, "criteria_version"):
                load_sweep_csv(path)

    def test_csv_loader_parses_boolean_strings(self) -> None:
        record = self._record(30.0, 75.0, 0.0459)
        csv_record = {
            key: (str(value).lower() if isinstance(value, bool) else value)
            for key, value in record.items()
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "valid.csv"
            with path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(csv_record.keys()))
                writer.writeheader()
                writer.writerow(csv_record)

            loaded = load_sweep_csv(path)

        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded[0]["candidate_admissible"])
        self.assertEqual((loaded[0]["M"], loaded[0]["D"]), (30.0, 75.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
