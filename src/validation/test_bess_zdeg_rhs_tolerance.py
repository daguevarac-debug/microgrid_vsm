"""Boundary checks for RK stage handling; public state validation stays strict."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from microgrid import MicrogridWithBESS
from validation.validate_bat26_55_n2_protections import make_model

class ThroughputStageTests(unittest.TestCase):
    def test_rhs_tolerance_and_strict_public_state_in_both_aging_modes(self):
        for model in (MicrogridWithBESS(), make_model()[0]):
            with self.subTest(snapshot=model._capacity_snapshot is not None):
                x = model.initial_state_with_bess(); x[0] = 330
                expected = model.system_dynamics(0, x)
                x[14] = -1e-9
                self.assertEqual(model.system_dynamics(0, x), expected)
                self.assertEqual(x[14], -1e-9)
                with self.assertRaises(ValueError): model.integrated_signals(0, x)
                with self.assertRaises(ValueError): model.bess.initial_state_with_degradation(z_deg=x[14])
                x[14] = -1.0001e-9
                with self.assertRaises(ValueError): model.system_dynamics(0, x)
                x[14] = float('nan')
                with self.assertRaises(ValueError): model.system_dynamics(0, x)

if __name__ == '__main__': unittest.main()
