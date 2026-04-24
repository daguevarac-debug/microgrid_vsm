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
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=376.99111843,
            theta0=0.25,
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        self.assertEqual(dynamics.initial_state(), [0.25, 376.99111843])

    def test_theta_derivative_returns_omega_exactly(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        self.assertEqual(dynamics.theta_derivative(theta=1.2, omega=377.5), 377.5)

    def test_power_imbalance_returns_reference_minus_electrical_power(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843, p_ref=1000.0)

        imbalance = dynamics.power_imbalance(p_e=875.0)

        self.assertEqual(imbalance, 125.0)

    def test_power_imbalance_is_positive_when_reference_exceeds_electrical_power(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        imbalance = dynamics.power_imbalance(p_e=900.0, p_ref=1000.0)

        self.assertGreater(imbalance, 0.0)

    def test_power_imbalance_is_negative_when_electrical_power_exceeds_reference(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        imbalance = dynamics.power_imbalance(p_e=1100.0, p_ref=1000.0)

        self.assertLess(imbalance, 0.0)

    def test_power_imbalance_is_zero_at_power_equilibrium(self) -> None:
        dynamics = GridFormingFrequencyDynamics(omega_ref=376.99111843)

        imbalance = dynamics.power_imbalance(p_e=1000.0, p_ref=1000.0)

        self.assertEqual(imbalance, 0.0)

    def test_omega_derivative_is_zero_at_power_and_frequency_equilibrium(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        domega_dt = dynamics.omega_derivative(omega=omega_ref, p_e=1000.0)

        self.assertEqual(domega_dt, 0.0)

    def test_omega_derivative_positive_when_reference_exceeds_electrical_power(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=1200.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        domega_dt = dynamics.omega_derivative(omega=omega_ref, p_e=1000.0)

        self.assertGreater(domega_dt, 0.0)

    def test_omega_derivative_negative_when_electrical_power_exceeds_reference(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=800.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        domega_dt = dynamics.omega_derivative(omega=omega_ref, p_e=1000.0)

        self.assertLess(domega_dt, 0.0)

    def test_omega_derivative_negative_above_reference_frequency_due_to_damping(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        domega_dt = dynamics.omega_derivative(omega=omega_ref + 1.0, p_e=1000.0)

        self.assertLess(domega_dt, 0.0)

    def test_rhs_returns_theta_and_omega_derivatives(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=1200.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        dtheta_dt, domega_dt = dynamics.rhs(t=0.0, x=[0.1, 377.5], p_e=1000.0)
        expected_domega_dt = dynamics.omega_derivative(omega=377.5, p_e=1000.0)

        self.assertEqual(dtheta_dt, 377.5)
        self.assertEqual(domega_dt, expected_domega_dt)

    def test_rhs_domega_dt_is_coherent_with_power_imbalance(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=1200.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        _, domega_dt = dynamics.rhs(t=0.0, x=[0.1, omega_ref], p_e=1000.0)
        expected_domega_dt = dynamics.power_imbalance(p_e=1000.0) / dynamics.inertia_m

        self.assertEqual(domega_dt, expected_domega_dt)

    def test_rhs_uses_power_equilibrium_when_pe_is_omitted(self) -> None:
        omega_ref = 376.99111843
        dynamics = GridFormingFrequencyDynamics(
            omega_ref=omega_ref,
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        _, domega_dt = dynamics.rhs(t=0.0, x=[0.1, omega_ref])

        self.assertEqual(domega_dt, 0.0)

    def test_inertia_m_must_be_strictly_positive(self) -> None:
        with self.assertRaises(ValueError):
            GridFormingFrequencyDynamics(omega_ref=376.99111843, inertia_m=0.0)

    def test_damping_d_must_be_non_negative(self) -> None:
        with self.assertRaises(ValueError):
            GridFormingFrequencyDynamics(omega_ref=376.99111843, damping_d=-1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
