from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from microgrid import Microgrid


class TestDCLinkDerivative(unittest.TestCase):
    """Basic unit checks for DC-link current balance and sign convention."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plant = Microgrid().plant
        cls.cdc = cls.plant.dcp.Cdc

    def test_dvdc_positive_when_inflow_exceeds_outflow(self) -> None:
        """If currents entering the DC bus exceed inverter draw, Vdc must rise."""
        ipv = 10.0
        i_bess = 1.0
        idc_inv = 7.0

        dvdc_dt = self.plant.dc_link_derivative(ipv=ipv, i_bess=i_bess, idc_inv=idc_inv)

        self.assertGreater(dvdc_dt, 0.0)
        self.assertAlmostEqual(dvdc_dt, (ipv + i_bess - idc_inv) / self.cdc, places=12)

    def test_dvdc_negative_when_outflow_exceeds_inflow(self) -> None:
        """If inverter draw exceeds incoming currents, Vdc must fall."""
        ipv = 6.0
        i_bess = 0.0
        idc_inv = 9.0

        dvdc_dt = self.plant.dc_link_derivative(ipv=ipv, i_bess=i_bess, idc_inv=idc_inv)

        self.assertLess(dvdc_dt, 0.0)
        self.assertAlmostEqual(dvdc_dt, (ipv + i_bess - idc_inv) / self.cdc, places=12)

    def test_dvdc_zero_when_currents_are_balanced(self) -> None:
        """Balanced DC-link current must produce zero voltage derivative."""
        ipv = 8.0
        i_bess = -1.5
        idc_inv = 6.5

        dvdc_dt = self.plant.dc_link_derivative(ipv=ipv, i_bess=i_bess, idc_inv=idc_inv)

        self.assertAlmostEqual(dvdc_dt, 0.0, places=12)

    def test_bess_discharge_supports_dc_bus(self) -> None:
        """Positive i_bess (discharge) increases dVdc/dt relative to no BESS."""
        ipv = 5.0
        idc_inv = 7.0

        dvdc_without_bess = self.plant.dc_link_derivative(ipv=ipv, i_bess=0.0, idc_inv=idc_inv)
        dvdc_with_discharge = self.plant.dc_link_derivative(ipv=ipv, i_bess=3.0, idc_inv=idc_inv)

        self.assertGreater(dvdc_with_discharge, dvdc_without_bess)

    def test_bess_charge_draws_from_dc_bus(self) -> None:
        """Negative i_bess (charge) decreases dVdc/dt relative to no BESS."""
        ipv = 9.0
        idc_inv = 7.0

        dvdc_without_bess = self.plant.dc_link_derivative(ipv=ipv, i_bess=0.0, idc_inv=idc_inv)
        dvdc_with_charge = self.plant.dc_link_derivative(ipv=ipv, i_bess=-2.0, idc_inv=idc_inv)

        self.assertLess(dvdc_with_charge, dvdc_without_bess)


if __name__ == "__main__":
    unittest.main(verbosity=2)
