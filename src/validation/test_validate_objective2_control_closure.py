"""Unit tests for Objective 2 consolidated closure validation helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_objective2_control_closure import (
    Criterion,
    EVIDENCE_COMMITS,
    SELECTED_D,
    SELECTED_M,
    ZETA_MIN_EXPECTED,
    ZETA_THRESHOLD,
    aggregate_status,
    approx_equal,
    has_absolute_local_path,
    validate_ranking_1_to_9,
    validate_tuning_shape,
)


CSV_COLUMNS = [
    "criterion_id",
    "activity",
    "scope",
    "blocking",
    "description",
    "status",
    "evidence",
    "details",
]


def _criterion(
    status: str,
    *,
    blocking: bool = True,
    scope: str = "formal",
) -> Criterion:
    return Criterion(
        criterion_id="TEST",
        activity="test",
        scope=scope,
        blocking=blocking,
        description="test criterion",
        status=status,
        evidence="relative/path",
        details="details",
    )


class TestObjective2ControlClosure(unittest.TestCase):
    def test_aggregation_all_pass(self) -> None:
        result = aggregate_status([_criterion("PASS"), _criterion("PASS")])
        self.assertEqual(result["global_status"], "PASS")
        self.assertEqual(result["blocking_failures"], 0)

    def test_aggregation_with_review(self) -> None:
        result = aggregate_status([_criterion("PASS"), _criterion("REVIEW")])
        self.assertEqual(result["global_status"], "REVIEW")
        self.assertEqual(result["review_count"], 1)

    def test_aggregation_with_nonblocking_diagnostic_fail(self) -> None:
        result = aggregate_status([
            _criterion("PASS"),
            _criterion("FAIL", blocking=False, scope="diagnostic"),
        ])
        self.assertEqual(result["global_status"], "REVIEW")
        self.assertEqual(result["diagnostic_failures"], 1)
        self.assertEqual(result["blocking_failures"], 0)

    def test_aggregation_with_blocking_fail(self) -> None:
        result = aggregate_status([_criterion("PASS"), _criterion("FAIL")])
        self.assertEqual(result["global_status"], "FAIL")
        self.assertEqual(result["blocking_failures"], 1)

    def test_detect_absolute_windows_and_unix_paths(self) -> None:
        self.assertTrue(has_absolute_local_path(r"C:\Users\hp\repo\file.txt"))
        self.assertTrue(has_absolute_local_path("/home/user/repo/file.txt"))
        self.assertFalse(has_absolute_local_path("docs/relative/path.md"))

    def test_validate_tuning_shape_9_by_4(self) -> None:
        rows = [
            {"M": str(m), "D": str(d), "scenario": scenario}
            for m in (20, 50, 80)
            for d in (200, 850, 1500)
            for scenario in ("a", "b", "c", "d")
        ]
        self.assertTrue(validate_tuning_shape(rows))
        self.assertFalse(validate_tuning_shape(rows[:-1]))

    def test_validate_ranking_1_to_9(self) -> None:
        ranking = [{"rank": idx} for idx in range(1, 10)]
        self.assertTrue(validate_ranking_1_to_9(ranking))
        self.assertFalse(validate_ranking_1_to_9(ranking[:-1]))

    def test_approx_equal_with_tolerance(self) -> None:
        self.assertTrue(approx_equal(1.0 + 1e-10, 1.0))
        self.assertFalse(approx_equal(1.0 + 1e-6, 1.0))

    def test_selected_point_consistency(self) -> None:
        self.assertEqual((SELECTED_M, SELECTED_D), (80.0, 1500.0))

    def test_zeta_min_exceeds_threshold(self) -> None:
        self.assertGreater(ZETA_MIN_EXPECTED, ZETA_THRESHOLD)

    def test_severe_diagnostic_can_be_nonblocking_fail(self) -> None:
        severe = _criterion("FAIL", blocking=False, scope="diagnostic")
        result = aggregate_status([_criterion("PASS"), severe])
        self.assertEqual(severe.scope, "diagnostic")
        self.assertFalse(severe.blocking)
        self.assertEqual(result["global_status"], "REVIEW")

    def test_csv_row_schema(self) -> None:
        row = _criterion("PASS").to_dict()
        self.assertEqual(list(row.keys()), CSV_COLUMNS)

    def test_evidence_commit_traceability(self) -> None:
        activity_21 = EVIDENCE_COMMITS[
            "2261ec09fee84ace883eac4b37f1c69b11bff845"
        ].lower()
        activity_22 = EVIDENCE_COMMITS[
            "860f03695a9a89c7f4075f91434a579575ee7e72"
        ].lower()
        activity_23 = EVIDENCE_COMMITS[
            "28bfeceadef7055efd779db309e2732da38a9406"
        ].lower()

        self.assertTrue("diseno" in activity_21 or "actividad 2.1" in activity_21)
        self.assertTrue(
            "bess/bms" in activity_22
            or "bess" in activity_22
            or "actividad 2.2" in activity_22
        )
        self.assertTrue(
            "pequena senal" in activity_23
            or "floquet" in activity_23
            or "actividad 2.3" in activity_23
        )


if __name__ == "__main__":
    unittest.main()
