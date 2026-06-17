from __future__ import annotations

import sys
import unittest
import warnings
from pathlib import Path

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController
from microgrid import Microgrid


class TestMicrogridControllerStateMapping(unittest.TestCase):
    """Checks the protected x[10]/x[11] mapping for GFL and GFM modes."""

    @staticmethod
    def _build_model(controller=None) -> Microgrid:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return Microgrid(controller=controller)

    def test_grid_following_keeps_x10_as_xi_vdc(self) -> None:
        model = self._build_model()

        x0 = model.initial_state()

        self.assertEqual(len(x0), 12)
        self.assertEqual(model.controller_state_name, "xi_vdc")
        self.assertEqual(x0[10], 0.0)
        self.assertEqual(x0[11], model.controller.modulator.theta0)

    def test_gfm_replaces_xi_vdc_with_omega_at_x10(self) -> None:
        controller = GFMController(
            p_ref=0.0,
            inertia_m=2.0,
            damping_d=5.0,
        )
        model = self._build_model(controller=controller)

        x0 = model.initial_state()

        self.assertEqual(len(x0), 12)
        self.assertEqual(model.controller_state_name, "omega")
        self.assertAlmostEqual(x0[10], controller.omega_ref)
        self.assertAlmostEqual(x0[11], controller.modulator.theta0)

    def test_system_dynamics_routes_gfm_omega_and_theta_derivatives(self) -> None:
        controller = GFMController(
            p_ref=0.0,
            inertia_m=2.0,
            damping_d=5.0,
        )
        model = self._build_model(controller=controller)
        x0 = model.initial_state()

        derivatives = model.system_dynamics(t=0.0, x=x0)

        self.assertEqual(len(derivatives), 12)
        self.assertAlmostEqual(derivatives[10], 0.0)
        self.assertAlmostEqual(derivatives[11], controller.omega_ref)


if __name__ == "__main__":
    unittest.main(verbosity=2)
