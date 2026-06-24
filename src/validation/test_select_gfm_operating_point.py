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

from validation.select_gfm_operating_point import (
    EXPECTED_CRITERIA_VERSION,
    EXPECTED_SCENARIO,
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
        scenario: str = EXPECTED_SCENARIO,
    ) -> dict[str, object]:
        return {
            "scenario": scenario,
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

    @classmethod
    def _grid(
        cls,
        m_values: list[float],
        d_values: list[float],
        *,
        best_pair: tuple[float, float],
    ) -> list[dict[str, object]]:
        records = []
        for inertia_m in m_values:
            for damping_d in d_values:
                distance = abs(best_pair[0] - inertia_m) + abs(best_pair[1] - damping_d) / 1000.0
                records.append(
                    cls._record(
                        inertia_m,
                        damping_d,
                        0.01 + 0.001 * distance,
                    )
                )
        return records

    @staticmethod
    def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

    def setUp(self) -> None:
        self.initial = self._grid(
            [2.0, 20.0, 80.0],
            [0.0, 200.0, 1500.0],
            best_pair=(80.0, 1500.0),
        )
        self.refinement = self._grid(
            [20.0, 50.0, 80.0],
            [200.0, 850.0, 1500.0],
            best_pair=(80.0, 1500.0),
        )

    def test_selects_last_refinement_minimum(self) -> None:
        summary = select_operating_point(self.initial, [self.refinement])

        selected = summary["selected_operating_point"]
        diagnostics = summary["diagnostics"]

        self.assertEqual((selected["M"], selected["D"]), (80.0, 1500.0))
        self.assertEqual(len(summary["stages"]), 2)
        self.assertTrue(diagnostics["selection_changed_from_previous"])
        self.assertTrue(diagnostics["selected_on_final_boundary"])
        self.assertTrue(diagnostics["selected_on_final_upper_corner"])
        self.assertTrue(diagnostics["cross_validation_pending"])
        self.assertFalse(diagnostics["global_optimum_claimed"])
        self.assertIsNone(diagnostics["severe_no_bess_robustness_confirmed"])
        self.assertIsNone(diagnostics["bess_soh_base_validation_pass"])

    def test_nonadmissible_lower_drop_is_ignored(self) -> None:
        refinement = list(self.refinement)
        target = next(
            record
            for record in refinement
            if record["M"] == 50.0 and record["D"] == 850.0
        )
        target.update(
            self._record(50.0, 850.0, 0.0001, admissible=False)
        )

        summary = select_operating_point(self.initial, [refinement])
        selected = summary["selected_operating_point"]
        self.assertEqual((selected["M"], selected["D"]), (80.0, 1500.0))

    def test_exact_tie_uses_lower_m_then_lower_d(self) -> None:
        refinement = list(self.refinement)
        for record in refinement:
            if (record["M"], record["D"]) in {
                (50.0, 850.0),
                (50.0, 1500.0),
                (80.0, 1500.0),
            }:
                record["max_frequency_drop_hz"] = 0.001

        summary = select_operating_point(self.initial, [refinement])
        selected = summary["selected_operating_point"]
        self.assertEqual((selected["M"], selected["D"]), (50.0, 850.0))

    def test_more_than_three_values_are_rejected(self) -> None:
        invalid = self._grid(
            [20.0, 40.0, 60.0, 80.0],
            [200.0],
            best_pair=(80.0, 200.0),
        )
        with self.assertRaisesRegex(ValueError, "unique M values"):
            select_operating_point(self.initial, [invalid])

    def test_incomplete_cartesian_grid_is_rejected(self) -> None:
        incomplete = self.refinement[:-1]
        with self.assertRaisesRegex(ValueError, "complete Cartesian grid"):
            select_operating_point(self.initial, [incomplete])

    def test_refinement_outside_parent_bounds_is_rejected(self) -> None:
        outside = self._grid(
            [20.0, 50.0, 100.0],
            [200.0, 850.0, 1500.0],
            best_pair=(100.0, 1500.0),
        )
        with self.assertRaisesRegex(ValueError, "outside initial_3x3"):
            select_operating_point(self.initial, [outside])

    def test_identical_domain_is_not_a_refinement(self) -> None:
        identical = self._grid(
            [2.0, 20.0, 80.0],
            [0.0, 200.0, 1500.0],
            best_pair=(80.0, 1500.0),
        )
        with self.assertRaisesRegex(ValueError, "must narrow"):
            select_operating_point(self.initial, [identical])

    def test_at_least_one_refinement_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one refinement"):
            select_operating_point(self.initial, [])

    def test_csv_loader_rejects_legacy_dc_criteria(self) -> None:
        legacy = [
            self._record(
                50.0,
                850.0,
                0.02,
                criteria_version="legacy_nominal_vdc_reference",
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "legacy.csv"
            self._write_csv(path, legacy)
            with self.assertRaisesRegex(ValueError, "criteria_version"):
                load_sweep_csv(path)

    def test_csv_loader_rejects_other_scenario(self) -> None:
        other = [
            self._record(
                50.0,
                850.0,
                0.02,
                scenario="other_scenario",
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "other.csv"
            self._write_csv(path, other)
            with self.assertRaisesRegex(ValueError, "scenario"):
                load_sweep_csv(path)

    def test_csv_loader_parses_boolean_strings(self) -> None:
        record = self._record(50.0, 850.0, 0.02)
        csv_record = {
            key: (str(value).lower() if isinstance(value, bool) else value)
            for key, value in record.items()
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "valid.csv"
            self._write_csv(path, [csv_record])
            loaded = load_sweep_csv(path)

        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded[0]["candidate_admissible"])
        self.assertEqual((loaded[0]["M"], loaded[0]["D"]), (50.0, 850.0))

    def test_csv_loader_preserves_nan_metrics_on_invalid_rows(self) -> None:
        invalid = self._record(20.0, 200.0, float("nan"), admissible=False)
        invalid["frequency_recovery_time_s"] = float("nan")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.csv"
            self._write_csv(path, [invalid])
            loaded = load_sweep_csv(path)

        self.assertEqual(len(loaded), 1)
        self.assertFalse(loaded[0]["candidate_admissible"])
        self.assertTrue(np.isnan(loaded[0]["max_frequency_drop_hz"]))
        self.assertTrue(np.isnan(loaded[0]["frequency_recovery_time_s"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
