"""Contract tests for the stand-alone CapacitySnapshot module.

No NumPy/SciPy dependency. This imports the exact source file directly;
it does not validate bess.__init__ or the coupled ECM/VSG model.

Place in <repo>/src/validation/test_aging_capacity_contract.py and run:
    <repo>/.venv/Scripts/python.exe src/validation/test_aging_capacity_contract.py
or standalone from anywhere with CAPACITY_MODULE_PATH set to the source file.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, is_dataclass, replace
from importlib.util import module_from_spec, spec_from_file_location
from math import isclose
from os import environ
from pathlib import Path
import sys
import unittest


def load_snapshot_class():
    raw = environ.get("CAPACITY_MODULE_PATH")
    if raw:
        module_path = Path(raw)
    else:
        module_path = Path(__file__).resolve().parents[1] / "bess" / "aging_capacity.py"
    if not module_path.is_file():
        raise FileNotFoundError(
            f"CapacitySnapshot source not found: {module_path}. "
            "Place this test in src/validation, or set CAPACITY_MODULE_PATH."
        )
    spec = spec_from_file_location("aging_capacity_contract_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.CapacitySnapshot


CapacitySnapshot = load_snapshot_class()


class TestCapacitySnapshotContract(unittest.TestCase):
    def test_initial_state_is_case_capacity_not_blast_70pct_again(self):
        value = CapacitySnapshot(66.0, 44.1, 1.0)
        self.assertAlmostEqual(value.q_eff_ah, 44.1, places=12)
        self.assertAlmostEqual(value.soh, 44.1 / 66.0, places=12)
        self.assertNotAlmostEqual(value.q_eff_ah, 0.7 * 44.1, places=5)

    def test_original_blast_initial_reference_is_a_distinct_case(self):
        value = CapacitySnapshot(66.0, 46.2, 1.0)
        self.assertAlmostEqual(value.soh, 0.7, places=12)

    def test_relative_retention_applied_to_case_initial_capacity(self):
        value = CapacitySnapshot(66.0, 44.1, 0.90)
        self.assertAlmostEqual(value.q_eff_ah, 39.69, places=12)
        self.assertAlmostEqual(value.soh, 39.69 / 66.0, places=12)

    def test_nominal_new_case_gives_full_capacity(self):
        value = CapacitySnapshot(66.0, 66.0, 1.0)
        self.assertEqual(value.soh, 1.0)
        self.assertEqual(value.q_eff_ah, 66.0)

    def test_retention_is_monotone_in_q_effective_and_soh(self):
        rates = (1.0, 0.98, 0.95, 0.90, 0.75, 0.50)
        values = [CapacitySnapshot(66.0, 44.1, r) for r in rates]
        for before, after in zip(values, values[1:]):
            self.assertLess(after.q_eff_ah, before.q_eff_ah)
            self.assertLess(after.soh, before.soh)
            self.assertTrue(0 < after.q_eff_ah <= 44.1)
            self.assertTrue(0 < after.soh <= 1.0)

    def test_snapshot_is_frozen_even_for_computed_fields(self):
        value = CapacitySnapshot(66.0, 44.1, 1.0)
        self.assertTrue(is_dataclass(value))
        with self.assertRaises(FrozenInstanceError):
            value.retention_since_case_start = 0.90
        with self.assertRaises(FrozenInstanceError):
            value.q_eff_ah = 11.0
        with self.assertRaises(FrozenInstanceError):
            value.soh = 0.2

    def test_new_window_uses_a_new_snapshot_without_mutating_previous(self):
        before = CapacitySnapshot(66.0, 44.1, 1.0)
        after = replace(before, retention_since_case_start=0.9)
        self.assertAlmostEqual(before.q_eff_ah, 44.1)
        self.assertAlmostEqual(after.q_eff_ah, 39.69)
        self.assertNotEqual(before, after)

    def test_rejects_zero_negative_or_excessive_values(self):
        for qnom, qinit, retention in (
            (0, 44.1, 1), (-66, 44.1, 1), (66, 0, 1),
            (66, -1, 1), (66, 70, 1), (66, 44.1, 0),
            (66, 44.1, -0.01), (66, 44.1, 1.01),
        ):
            with self.subTest(qnom=qnom, qinit=qinit, retention=retention):
                with self.assertRaises(ValueError):
                    CapacitySnapshot(qnom, qinit, retention)

    def test_rejects_nans_and_infinities(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            for index in range(3):
                values = [66.0, 44.1, 1.0]
                values[index] = bad
                with self.subTest(bad=bad, index=index):
                    with self.assertRaises(ValueError):
                        CapacitySnapshot(*values)

    def test_rejects_bool_strings_and_none_in_all_fields(self):
        for bad in (True, False, "0.95", None):
            for index in range(3):
                values = [66.0, 44.1, 1.0]
                values[index] = bad
                with self.subTest(bad=bad, index=index):
                    with self.assertRaises(ValueError):
                        CapacitySnapshot(*values)

    def test_reported_fields_match_exact_contract(self):
        value = CapacitySnapshot(66.0, 44.1, 0.95)
        documented = asdict(value)
        self.assertEqual(
            set(documented),
            {"q_nom_ref_ah", "q_init_case_ah", "retention_since_case_start", "q_eff_ah", "soh"},
        )
        self.assertTrue(isclose(documented["q_eff_ah"], 41.895))


if __name__ == "__main__":
    unittest.main(verbosity=2)
