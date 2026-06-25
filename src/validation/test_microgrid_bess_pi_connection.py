"""Tests for the PI-to-BESS connection, limits and enable logic."""

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
        bess_enabled: bool = True,
        **model_kwargs,
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
            bess_enabled=bess_enabled,
            **model_kwargs,
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
        self.assertEqual(pi_output.p_bess_ref_w, 500.0)
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
        self.assertEqual(pi_output.p_bess_ref_w, -500.0)
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

    def test_integrated_signals_expose_limited_reference_and_actual_power(self) -> None:
        model = self._build_model(kp_w_per_v=100.0, ki_w_per_v_s=0.0)
        state = model.initial_state_with_bess(
            vdc0=335.0,
            xi_bess_vdc0_v_s=0.0,
        )
        signals = model.integrated_signals(0.0, state)

        self.assertEqual(signals["p_bess_ref_unsat_w"], 500.0)
        self.assertEqual(signals["p_bess_ref_w"], 500.0)
        self.assertGreater(signals["i_bess"], 0.0)
        self.assertAlmostEqual(
            signals["p_bess_dc"],
            signals["Vdc"] * signals["i_bess"],
        )
        self.assertFalse(signals["pi_saturated"])
        self.assertFalse(signals["anti_windup_active"])
        self.assertTrue(signals["bess_discharge_available"])

    def test_disabled_bess_orders_no_discharge_and_freezes_integrator(self) -> None:
        model = self._build_model(
            kp_w_per_v=1000.0,
            ki_w_per_v_s=20.0,
            bess_enabled=False,
        )
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=330.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=model.bess.soh_init_case,
            xi_bess_vdc_v_s=5.0,
        )
        self.assertGreater(pi_output.p_bess_ref_unsat_w, 0.0)
        self.assertEqual(pi_output.p_bess_ref_w, 0.0)
        self.assertEqual(current, 0.0)
        self.assertTrue(pi_output.anti_windup_active)
        self.assertEqual(pi_output.d_xi_vdc_dt, 0.0)

        state = model.initial_state_with_bess(vdc0=330.0)
        derivatives = model.system_dynamics(0.0, state)
        self.assertEqual(derivatives[15], 0.0)

    def test_soc_min_blocks_discharge_and_activates_anti_windup(self) -> None:
        model = self._build_model(kp_w_per_v=1000.0, ki_w_per_v_s=20.0)
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=330.0,
            soc_bess=model.bess.soc_min,
            soh_bess=model.bess.soh_init_case,
            xi_bess_vdc_v_s=0.0,
        )
        self.assertEqual(pi_output.p_max_w, 0.0)
        self.assertEqual(pi_output.p_bess_ref_w, 0.0)
        self.assertEqual(current, 0.0)
        self.assertTrue(pi_output.anti_windup_active)
        self.assertEqual(pi_output.d_xi_vdc_dt, 0.0)

    def test_soc_max_blocks_charge_and_activates_anti_windup(self) -> None:
        model = self._build_model(kp_w_per_v=1000.0, ki_w_per_v_s=20.0)
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=350.0,
            soc_bess=model.bess.soc_max,
            soh_bess=model.bess.soh_init_case,
            xi_bess_vdc_v_s=0.0,
        )
        self.assertEqual(pi_output.p_min_w, 0.0)
        self.assertEqual(pi_output.p_bess_ref_w, 0.0)
        self.assertEqual(current, 0.0)
        self.assertTrue(pi_output.anti_windup_active)
        self.assertEqual(pi_output.d_xi_vdc_dt, 0.0)

    def test_current_limit_saturates_power_reference_and_current(self) -> None:
        model = self._build_model(
            kp_w_per_v=100000.0,
            ki_w_per_v_s=0.0,
            i_bess_max=1.0,
            p_bess_max_w=100000.0,
        )
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=330.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=1.0,
            xi_bess_vdc_v_s=0.0,
        )
        self.assertAlmostEqual(pi_output.p_max_w, 330.0)
        self.assertAlmostEqual(pi_output.p_bess_ref_w, 330.0)
        self.assertAlmostEqual(current, 1.0)
        self.assertTrue(pi_output.anti_windup_active)

    def test_power_limit_saturates_reference_before_current_conversion(self) -> None:
        model = self._build_model(
            kp_w_per_v=100000.0,
            ki_w_per_v_s=0.0,
            i_bess_max=66.0,
            p_bess_max_w=500.0,
        )
        pi_output, current = model._compute_pi_bess_command(
            vdc_v=330.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=1.0,
            xi_bess_vdc_v_s=0.0,
        )
        self.assertAlmostEqual(pi_output.p_max_w, 500.0)
        self.assertAlmostEqual(pi_output.p_bess_ref_w, 500.0)
        self.assertAlmostEqual(current, 500.0 / 330.0)

    def test_lower_soh_reduces_charge_and_discharge_limits(self) -> None:
        model = self._build_model()
        full = model._operating_power_limits(
            vdc_v=340.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=1.0,
        )
        half = model._operating_power_limits(
            vdc_v=340.0,
            soc_bess=model.bess.soc_initial,
            soh_bess=0.5,
        )
        self.assertAlmostEqual(half[0], 0.5 * full[0])
        self.assertAlmostEqual(half[1], 0.5 * full[1])

    def test_vsg_parameters_are_not_modified_by_limits_or_enable_logic(self) -> None:
        model = self._build_model()
        frequency_dynamics = model.controller.frequency_dynamics
        self.assertEqual(frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(frequency_dynamics.damping_d, 1500.0)

        model.set_bess_enabled(False)
        state = model.initial_state_with_bess(vdc0=335.0)
        model.system_dynamics(0.0, state)

        self.assertEqual(frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(frequency_dynamics.damping_d, 1500.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
