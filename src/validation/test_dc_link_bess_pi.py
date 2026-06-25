"""Unit tests for the isolated external BESS DC-link PI regulator."""

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
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_undervoltage_generates_positive_discharge_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=335.0, xi_vdc_v_s=0.0)
        self.assertEqual(output.vdc_error_v, 5.0)
        self.assertEqual(output.p_bess_ref_unsat_w, 500.0)
        self.assertEqual(output.d_xi_vdc_dt, 5.0)

    def test_overvoltage_generates_negative_charge_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=345.0, xi_vdc_v_s=0.0)
        self.assertEqual(output.vdc_error_v, -5.0)
        self.assertEqual(output.p_bess_ref_unsat_w, -500.0)
        self.assertEqual(output.d_xi_vdc_dt, -5.0)

    def test_integral_state_contributes_to_power_reference(self) -> None:
        output = self.controller.compute(vdc_v=340.0, xi_vdc_v_s=3.0)
        self.assertEqual(output.vdc_error_v, 0.0)
        self.assertEqual(output.p_bess_ref_unsat_w, 60.0)
        self.assertEqual(output.d_xi_vdc_dt, 0.0)

    def test_negative_gains_are_rejected(self) -> None:
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
