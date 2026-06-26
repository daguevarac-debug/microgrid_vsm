"""Unit tests for Objective 2.3 periodic small-signal helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_objective2_small_signal_stability import (
    build_state_scales,
    classify_mode,
    modal_values,
    mu_to_lambda,
    period_map_jacobian,
)


class TestObjective2SmallSignalHelpers(unittest.TestCase):
    def test_build_state_scales(self) -> None:
        scales_12 = build_state_scales(12)
        scales_16 = build_state_scales(16)
        self.assertEqual(scales_12.shape, (12,))
        self.assertEqual(scales_16.shape, (16,))
        self.assertTrue(np.all(scales_12 > 0.0))
        self.assertEqual(scales_12[0], 340.0)

    def test_period_map_jacobian_linear_function(self) -> None:
        matrix = np.array([[2.0, -1.0], [0.5, 3.0]])
        jac = period_map_jacobian(
            lambda x: matrix @ x,
            np.array([1.0, -2.0]),
            np.array([1.0, 2.0]),
            1e-6,
        )
        self.assertTrue(np.allclose(jac, matrix, atol=1e-8))

    def test_mu_to_lambda(self) -> None:
        exponent = -2.0 + 3.0j
        period = 0.25
        mu = np.exp(exponent * period)
        recovered = mu_to_lambda(mu, period)
        self.assertAlmostEqual(recovered.real, exponent.real)
        self.assertAlmostEqual(recovered.imag, exponent.imag)

    def test_zeta_calculation(self) -> None:
        exponent = -3.0 + 4.0j
        mu = np.exp(exponent * 0.1)
        values = modal_values(mu, 0.1)
        self.assertAlmostEqual(values["zeta"], 3.0 / 5.0)

    def test_neutral_phase_mode_classification(self) -> None:
        vec = np.zeros(12, dtype=complex)
        vec[11] = 1.0
        classification, relevant, reason = classify_mode(
            1.0 + 0.0j,
            0.0 + 0.0j,
            vec,
            build_state_scales(12),
            (
                "Vdc",
                "i1_a",
                "i1_b",
                "i1_c",
                "vc_a",
                "vc_b",
                "vc_c",
                "i2_a",
                "i2_b",
                "i2_c",
                "omega",
                "theta",
            ),
        )
        self.assertEqual(classification, "neutral_phase_mode")
        self.assertFalse(relevant)
        self.assertIn("phase", reason)

    def test_unstable_mode_classification(self) -> None:
        vec = np.ones(12, dtype=complex)
        classification, relevant, _reason = classify_mode(
            1.02 + 0.0j,
            1.0 + 0.0j,
            vec,
            build_state_scales(12),
            (
                "Vdc",
                "i1_a",
                "i1_b",
                "i1_c",
                "vc_a",
                "vc_b",
                "vc_c",
                "i2_a",
                "i2_b",
                "i2_c",
                "omega",
                "theta",
            ),
        )
        self.assertEqual(classification, "unstable")
        self.assertTrue(relevant)


if __name__ == "__main__":
    unittest.main()
