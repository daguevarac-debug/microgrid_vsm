from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.grid_forming import GridFormingFrequencyDynamics


class TestGridFormingFrequencyDynamics(unittest.TestCase):
    """Unit checks for the isolated minimal GFM frequency state."""

    def test_initial_state_uses_theta0_and_omega_ref(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843, theta0=0.25)

        self.assertEqual(dynamics.initial_state(), [0.25, 376.99111843])

    def test_theta_derivative_returns_omega_exactly(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        self.assertEqual(dynamics.theta_derivative(theta=1.2, omega=377.5), 377.5)

    def test_rhs_returns_omega_as_dtheta_dt(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        dtheta_dt, _ = dynamics.rhs(t=0.0, x=[0.1, 377.5])

        self.assertEqual(dtheta_dt, 377.5)

    def test_rhs_keeps_domega_dt_zero_in_this_subtask(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        _, domega_dt = dynamics.rhs(t=0.0, x=[0.1, 377.5])

        self.assertEqual(domega_dt, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
