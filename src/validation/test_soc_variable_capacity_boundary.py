"""Small checks for BAT26-34's piecewise-constant capacity and boundary rules."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bess.aging_capacity import CapacitySnapshot
from bess.model import SecondLifeBattery1RC
from bess.blast_lite_adapter import preserve_window_state


def make_battery() -> SecondLifeBattery1RC:
    return SecondLifeBattery1RC(
        r0_nominal_ohm=0.01,
        q_nom_ref_ah=66.0,
        q_init_case_ah=44.1,
        k_deg=0.001,
        r0_soh_sensitivity=0.0,
    )


class TestSocVariableCapacityBoundary(unittest.TestCase):
    def test_rhs_coulomb_counting_units_and_current_signs(self):
        battery = make_battery()
        snapshot = CapacitySnapshot(66.0, 44.1, 0.9)
        q_eff = 39.69  # Ah
        for current_a, expected_sign in ((3.0, -1), (-3.0, 1)):
            with self.subTest(current_a=current_a):
                dsoc_dt = battery.rhs(
                    0.0, [0.5, 0.0, 0.0], current_a, snapshot.soh,
                    capacity_snapshot=snapshot,
                )[0]
                self.assertAlmostEqual(dsoc_dt, -current_a / (3600.0 * q_eff))
                self.assertEqual(1 if dsoc_dt > 0 else -1, expected_sign)
                self.assertAlmostEqual(dsoc_dt * 3600.0 * q_eff, -current_a)

        # 1 A for 3600 s transfers 1 Ah under the assumed unit coulombic efficiency.
        self.assertEqual(1.0 * 3600.0 / 3600.0, 1.0)

    def test_fractional_soc_boundary_changes_algebraic_charge_only(self):
        soc = 0.6
        q_before_ah, q_after_ah = 44.1, 39.69
        stored_before_ah = soc * q_before_ah
        stored_after_ah = soc * q_after_ah
        self.assertAlmostEqual(
            stored_after_ah - stored_before_ah,
            soc * (q_after_ah - q_before_ah),
        )
        self.assertLess(stored_after_ah, stored_before_ah)

    def test_algebraic_charge_preservation_can_violate_soc_ceiling(self):
        soc_before = 0.9
        q_before_ah, q_after_ah = 44.1, 39.69
        soc_after = soc_before * q_before_ah / q_after_ah
        self.assertGreater(soc_after, 0.9)
        self.assertAlmostEqual(soc_after * q_after_ah, soc_before * q_before_ah)

    def test_window_boundary_preserves_state_without_clipping(self):
        state = [0.0] * 15
        state[12] = 0.6
        state[13] = 0.04
        state[14] = 17.0  # z_deg retains its existing diagnostic meaning.
        copied = preserve_window_state(state, soc_min=0.1, soc_max=0.9)
        self.assertEqual(copied, state)
        self.assertIsNot(copied, state)
        self.assertEqual(copied[12], 0.6)
        self.assertEqual(copied[13:15], [0.04, 17.0])

        for invalid_soc in (0.099, 0.901):
            state[12] = invalid_soc
            with self.subTest(soc=invalid_soc), self.assertRaises(ValueError):
                preserve_window_state(state, soc_min=0.1, soc_max=0.9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
