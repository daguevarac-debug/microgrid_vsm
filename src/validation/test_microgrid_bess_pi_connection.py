"""Tests for connecting the external DC-link PI to the BESS power channel."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS
from microgrid_bess_pi import MicrogridWithBESSPI


class TestMicrogridWithBESSPIConnection(unittest.TestCase):
    def _build_model(
        self,
        *,
        kp_w_per_v: float = 100.0,
        ki_w_per_v_s: float = 20.0,
    ) -> MicrogridWithBESSPI:
        gfm = GFMController(
            p_ref=3678.1982760994806,
            inertia_m=80.0,
            damping_d=1500.0,
        )
        pi = DCLinkBESSPIController(
            vdc_ref_v=340.0,
            kp_w_per_v=kp_w_per_v,
            ki_w_per_v_s=ki_w_per_v_s,
        )
        return MicrogridWithBESSPI(
            controller=gfm,
            dc_link_bess_pi=pi,
        )

    def test_pi_architecture_appends_state_without_shifting_first_fifteen(self) -> None:
        model = self._build_model()
        state_pi = model.initial_state_with_bess(
            vdc0=340.0,
            xi_bess_vdc0_v_s=2.5,
        )
        state_legacy = MicrogridWithBESS.initial_state_with_bess(model, vdc0=340.0)

        self.assertEqual(len(state_legacy), 15)
        self.assertEqual(len(state_pi), 16)
        self.assertEqual(state_pi[:15], state_legacy)
        self.assertEqual(state_pi[15], 2.5)
        self.assertEqual(model.bess_pi_state_index, 15)

    def test_positive_pi_power_reference_becomes_positive_discharge_current(self) -> None:
        model = self._build_model(kp_w_per_v=100.0, ki_w_per_v_s=0.0)
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=335.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=model.bess.soh_init_case,
            xi_bess_vdc_v_s=0.0,
        )
        self.assertEqual(pi_output.p_bess_ref_unsat_w, 500.0)
        self.assertGreater(current, 0.0)
        self.assertAlmostEqual(current, 500.0 / 335.0)

    def test_negative_pi_power_reference_becomes_negative_charge_current(self) -> None:
        model = self._build_model(kp_w_per_v=100.0, ki_w_per_v_s=0.0)
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=345.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=model.bess.soh_init_case,
            xi_bess_vdc_v_s=0.0,
        )
        self.assertEqual(pi_output.p_bess_ref_unsat_w, -500.0)
        self.assertLess(current, 0.0)
        self.assertAlmostEqual(current, -500.0 / 345.0)

    def test_global_dynamics_returns_integral_derivative_as_sixteenth_state(self) -> None:
        model = self._build_model(kp_w_per_v=100.0, ki_w_per_v_s=20.0)
        state = model.initial_state_with_bess(
            vdc0=335.0,
            xi_bess_vdc0_v_s=0.0,
        )
        derivatives = model.system_dynamics(0.0, state)

        self.assertEqual(len(derivatives), 16)
        self.assertAlmostEqual(derivatives[15], 5.0)

    def test_integrated_signals_expose_pi_reference_and_actual_bess_power(self) -> None:
        model = self._build_model(kp_w_per_v=100.0, ki_w_per_v_s=0.0)
        state = model.initial_state_with_bess(
            vdc0=335.0,
            xi_bess_vdc0_v_s=0.0,
        )
        signals = model.integrated_signals(0.0, state)

        self.assertEqual(signals["p_bess_ref_unsat_w"], 500.0)
        self.assertGreater(signals["i_bess"], 0.0)
        self.assertAlmostEqual(
            signals["p_bess_dc"],
            signals["Vdc"] * signals["i_bess"],
        )
        self.assertEqual(signals["xi_bess_vdc_v_s"], 0.0)

    def test_vsg_parameters_are_not_modified_by_pi_connection(self) -> None:
        model = self._build_model()
        frequency_dynamics = model.controller.frequency_dynamics
        self.assertEqual(frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(frequency_dynamics.damping_d, 1500.0)

        state = model.initial_state_with_bess(vdc0=335.0)
        model.system_dynamics(0.0, state)

        self.assertEqual(frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(frequency_dynamics.damping_d, 1500.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
