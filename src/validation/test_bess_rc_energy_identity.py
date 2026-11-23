"""Local algebraic identity for the provisional SoC-dependent 1RC model."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bess.model import SecondLifeBattery1RC


class RCEnergyIdentityTests(unittest.TestCase):
    def test_variable_capacitance_term_for_charge_and_discharge(self):
        b = SecondLifeBattery1RC(r0_nominal_ohm=.01, q_nom_ref_ah=66., q_init_case_ah=44.1)
        soc, vrc, soh = .6, .12, b.soh_init_case
        h = 1e-5  # Within a linear lookup segment, away from its knots.
        c1 = b.c1(soc)
        dc_ds = (b.c1(soc+h)-b.c1(soc-h))/(2*h)
        self.assertNotEqual(dc_ds, 0.)
        for current in (7., -7.):
            with self.subTest(current=current):
                ds, dv, _ = b.rhs(0, [soc, vrc, 0.], current, soh)
                terminal = b.terminal_voltage(soc, vrc, current, soh)*current
                d_energy_rc = c1*vrc*dv + .5*vrc**2*dc_ds*ds
                decomposition = (terminal + current**2*b.r0(soh) + vrc**2/b.r1(soc)
                                 + d_energy_rc - .5*vrc**2*dc_ds*ds)
                self.assertAlmostEqual(b.ocv(soc)*current, decomposition, places=10)
                self.assertNotAlmostEqual(b.ocv(soc)*current,
                                          decomposition + .5*vrc**2*dc_ds*ds, places=9)


if __name__ == '__main__':
    unittest.main()
