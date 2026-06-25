"""Tests for the single-candidate minimal BESS PI validation."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
    build_model,
    classify_status,
)


class TestMinimalBESSPITuning(unittest.TestCase):
    def test_only_one_fixed_candidate_is_defined(self) -> None:
        self.assertEqual(PI_KP_W_PER_V, 170.0)
        self.assertEqual(PI_KI_W_PER_V_S, 10.0)
        self.assertEqual(GFM_SELECTED_M, 80.0)
        self.assertEqual(GFM_SELECTED_D, 1500.0)

    def test_model_uses_explicit_pi_architecture_and_sixteen_states(self) -> None:
        model = build_model()
        state = model.initial_state_with_bess()
        self.assertEqual(len(state), 16)
        self.assertEqual(model.dc_link_bess_pi.kp_w_per_v, 170.0)
        self.assertEqual(model.dc_link_bess_pi.ki_w_per_v_s, 10.0)
        self.assertEqual(model.controller.frequency_dynamics.inertia_m, 80.0)
        self.assertEqual(model.controller.frequency_dynamics.damping_d, 1500.0)

    def test_status_requires_all_existing_criteria_and_bess_limits(self) -> None:
        self.assertEqual(
            classify_status(
                solver_success=True,
                states_finite=True,
                dc_criteria_pass=True,
                frequency_criteria_pass=True,
                bess_limits_pass=True,
            ),
            "PASS",
        )
        for failed_name in (
            "solver_success",
            "states_finite",
            "dc_criteria_pass",
            "frequency_criteria_pass",
            "bess_limits_pass",
        ):
            flags = {
                "solver_success": True,
                "states_finite": True,
                "dc_criteria_pass": True,
                "frequency_criteria_pass": True,
                "bess_limits_pass": True,
            }
            flags[failed_name] = False
            self.assertEqual(classify_status(**flags), "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
