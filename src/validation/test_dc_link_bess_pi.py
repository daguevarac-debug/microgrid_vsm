"""Unit tests for the external BESS DC-link PI regulator."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.dc_link_bess_pi import DCLinkBESSPIController


class TestDCLinkBESSPIController(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = DCLinkBESSPIController(
            vdc_ref_v=340.0,
            kp_w_per_v=100.0,
            ki_w_per_v_s=20.0,
        )

    def test_zero_error_and_zero_integral_give_zero_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=340.0, xi_vdc_v_s=0.0)
        self.assertEqual(output.vdc_error_v, 0.0)
        self.assertEqual(output.p_bess_ref_unsat_w, 0.0)
        self.assertEqual(output.p_bess_ref_w, 0.0)
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_undervoltage_generates_positive_discharge_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=335.0, xi_vdc_v_s=0.0)
        self.assertEqual(output.vdc_error_v, 5.0)
        self.assertEqual(output.p_bess_ref_unsat_w, 500.0)
        self.assertEqual(output.p_bess_ref_w, 500.0)
        self.assertEqual(output.d_xi_vdc_dt, 5.0)

    def test_overvoltage_generates_negative_charge_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=345.0, xi_vdc_v_s=0.0)
        self.assertEqual(output.vdc_error_v, -5.0)
        self.assertEqual(output.p_bess_ref_unsat_w, -500.0)
        self.assertEqual(output.p_bess_ref_w, -500.0)
        self.assertEqual(output.d_xi_vdc_dt, -5.0)

    def test_integral_state_contributes_to_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=340.0, xi_vdc_v_s=3.0)
        self.assertEqual(output.vdc_error_v, 0.0)
        self.assertEqual(output.p_bess_ref_unsat_w, 60.0)
        self.assertEqual(output.p_bess_ref_w, 60.0)
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_high_saturation_freezes_integrator_when_error_pushes_higher(self) -> None:
        output = self.controller.compute(
            vdc_v=330.0,
            xi_vdc_v_s=0.0,
            p_min_w=-500.0,
            p_max_w=400.0,
        )
        self.assertEqual(output.p_bess_ref_unsat_w, 1000.0)
        self.assertEqual(output.p_bess_ref_w, 400.0)
        self.assertTrue(output.saturated)
        self.assertTrue(output.anti_windup_active)
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_low_saturation_freezes_integrator_when_error_pushes_lower(self) -> None:
        output = self.controller.compute(
            vdc_v=350.0,
            xi_vdc_v_s=0.0,
            p_min_w=-400.0,
            p_max_w=500.0,
        )
        self.assertEqual(output.p_bess_ref_unsat_w, -1000.0)
        self.assertEqual(output.p_bess_ref_w, -400.0)
        self.assertTrue(output.anti_windup_active)
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_integrator_can_unwind_from_saturation(self) -> None:
        output = self.controller.compute(
            vdc_v=345.0,
            xi_vdc_v_s=100.0,
            p_min_w=-500.0,
            p_max_w=500.0,
        )
        self.assertEqual(output.p_bess_ref_unsat_w, 1500.0)
        self.assertEqual(output.p_bess_ref_w, 500.0)
        self.assertTrue(output.saturated)
        self.assertFalse(output.anti_windup_active)
        self.assertEqual(output.d_xi_vdc_dt, -5.0)

    def test_disabled_bess_forces_zero_reference_and_freezes_integrator(self) -> None:
        output = self.controller.compute(
            vdc_v=330.0,
            xi_vdc_v_s=10.0,
            p_min_w=-1000.0,
            p_max_w=1000.0,
            bess_enabled=False,
        )
        self.assertGreater(output.p_bess_ref_unsat_w, 0.0)
        self.assertEqual(output.p_bess_ref_w, 0.0)
        self.assertFalse(output.bess_enabled)
        self.assertTrue(output.anti_windup_active)
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_invalid_limits_and_negative_gains_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.compute(
                vdc_v=340.0,
                xi_vdc_v_s=0.0,
                p_min_w=100.0,
                p_max_w=-100.0,
            )
        with self.assertRaises(ValueError):
            DCLinkBESSPIController(
                vdc_ref_v=340.0,
                kp_w_per_v=-1.0,
                ki_w_per_v_s=0.0,
            )
        with self.assertRaises(ValueError):
            DCLinkBESSPIController(
                vdc_ref_v=340.0,
                kp_w_per_v=0.0,
                ki_w_per_v_s=-1.0,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
