"""Capacity snapshots coupled to the protected BESS state layouts."""
from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bess.aging_capacity import CapacitySnapshot
from bess.model import SecondLifeBattery1RC
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS
from microgrid_bess_pi import MicrogridWithBESSPI


def battery():
    return SecondLifeBattery1RC(r0_nominal_ohm=0.01, q_nom_ref_ah=66.0,
                                q_init_case_ah=44.1, k_deg=0.001,
                                r0_soh_sensitivity=0.0)


class TestCapacitySnapshotIntegration(unittest.TestCase):
    def setUp(self):
        self.snapshot = CapacitySnapshot(66.0, 44.1, 1.0)
        self.bess = battery()

    def model(self, pi=False, snapshot=None):
        kwargs = dict(bess_model=self.bess, controller=GFMController(
            p_ref=0.0, inertia_m=80.0, damping_d=1500.0), capacity_snapshot=snapshot,
            aging_mode="blast" if snapshot is not None else "linear",
            blast_profile_kind="synthetic" if snapshot is not None else None)
        if pi:
            return MicrogridWithBESSPI(dc_link_bess_pi=DCLinkBESSPIController(
                vdc_ref_v=340.0, kp_w_per_v=100.0, ki_w_per_v_s=20.0), **kwargs)
        return MicrogridWithBESS(**kwargs)

    def test_initial_capacity_and_one_hour_coulomb_counting(self):
        self.assertEqual(self.snapshot.q_eff_ah, 44.1)
        self.assertAlmostEqual(self.snapshot.soh, 44.1 / 66.0)
        result = solve_ivp(lambda t, x: self.bess.rhs(t, x, 4.41, self.snapshot.soh,
                           capacity_snapshot=self.snapshot), (0, 3600), [0.6, 0, 0], method="Radau")
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.y[0, -1], 0.5)
        self.assertAlmostEqual(result.y[2, -1], 4.41)

    def test_snapshot_is_frozen_and_capacity_independent_of_throughput(self):
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.retention_since_case_start = 0.9
        for z in (0.0, 10.0, 100.0):
            derivative = self.bess.rhs(0, [0.6, 0, z], 10, 0.7,
                                       capacity_snapshot=self.snapshot)
            self.assertAlmostEqual(derivative[0], -10 / (3600 * 44.1))
            self.assertAlmostEqual(derivative[2], 10 / 3600)

    def test_legacy_linear_mode_remains_independent(self):
        z = 10.0
        expected_soh = self.bess.soh_init_case - self.bess.k_deg * z
        self.assertAlmostEqual(self.bess.soh_from_z_deg(z), expected_soh)
        d = self.bess.rhs(0, [0.6, 0, z], 10, self.bess.soh_init_case)
        self.assertAlmostEqual(d[0], -10 / (3600 * 66 * expected_soh))
        self.assertNotAlmostEqual(d[0], self.bess.rhs(0, [0.6, 0, z], 10,
            self.snapshot.soh, capacity_snapshot=self.snapshot)[0], places=9)

    def test_incompatible_or_below_limit_snapshots_are_rejected(self):
        for snapshot in (CapacitySnapshot(66, 45, 1), CapacitySnapshot(65, 44.1, 1),
                         CapacitySnapshot(66, 44.1, 0.7)):
            with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                self.model(snapshot=snapshot)
        with self.assertRaises(ValueError):
            self.bess.rhs(0, [0.6, 0], 1, self.snapshot.soh, capacity_snapshot=self.snapshot)

    def test_snapshot_mode_preserves_states_and_supervision_in_both_architectures(self):
        for pi in (False, True):
            with self.subTest(pi=pi):
                model = self.model(pi=pi, snapshot=self.snapshot)
                state = model.initial_state_with_bess(vdc0=330.0)
                self.assertEqual(len(state), 16 if pi else 15)
                self.assertEqual(state[12:15], [self.bess.soc_initial, 0.0, 0.0])
                if pi:
                    self.assertEqual(state[15], 0.0)
                    self.assertEqual(model.bess_pi_state_index, 15)
                state[14] = 100.0
                signals = model.integrated_signals(0, state)
                derivatives = model.system_dynamics(0, state)
                self.assertEqual(len(derivatives), len(state))
                self.assertAlmostEqual(signals["soh_bess"], self.snapshot.soh)
                self.assertAlmostEqual(signals["i_bess_max_available"], 66 * self.snapshot.soh)
                self.assertAlmostEqual(derivatives[12], -signals["i_bess"] / (3600 * 44.1))
                self.assertAlmostEqual(derivatives[14], abs(signals["i_bess"]) / 3600)
                self.assertEqual(model.controller.frequency_dynamics.inertia_m, 80)
                self.assertEqual(model.controller.frequency_dynamics.damping_d, 1500)

    def test_new_window_uses_new_snapshot_without_linear_fade(self):
        next_snapshot = CapacitySnapshot(66, 44.1, 0.9)
        first, second = self.model(snapshot=self.snapshot), self.model(snapshot=next_snapshot)
        state = first.initial_state_with_bess(vdc0=330)
        state[14] = 50
        self.assertAlmostEqual(first.integrated_signals(0, state)["soh_bess"], self.snapshot.soh)
        self.assertAlmostEqual(second.integrated_signals(0, state)["soh_bess"], next_snapshot.soh)
        self.assertAlmostEqual(second.system_dynamics(0, state)[12],
            -second.integrated_signals(0, state)["i_bess"] / (3600 * next_snapshot.q_eff_ah))


if __name__ == "__main__":
    unittest.main(verbosity=2)

