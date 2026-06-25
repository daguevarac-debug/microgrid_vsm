"""Tests for the BESS charge-only root-cause diagnostic."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.diagnose_bess_charge_only_cause import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    _build_case,
    _determine_root_cause,
    _exchange_mode,
)


class TestBESSChargeOnlyCauseDiagnostic(unittest.TestCase):
    def test_case_matches_selected_gfm_nominal_soh_comparison(self) -> None:
        model, initial_state, metadata = _build_case()
        self.assertEqual(GFM_SELECTED_M, 80.0)
        self.assertEqual(GFM_SELECTED_D, 1500.0)
        self.assertEqual(model.controller_state_name, "omega")
        self.assertEqual(len(initial_state), 15)
        self.assertAlmostEqual(metadata["load_step_pct"], 20.0)
        self.assertGreater(model.kp_bess, 0.0)

    def test_exchange_mode_uses_repository_sign_convention(self) -> None:
        self.assertEqual(_exchange_mode(np.array([-2.0, -0.5])), "charge_only")
        self.assertEqual(_exchange_mode(np.array([0.2, 1.0])), "discharge_only")
        self.assertEqual(_exchange_mode(np.array([-0.4, 0.4])), "bidirectional")
        self.assertEqual(_exchange_mode(np.zeros(3)), "idle")

    def test_root_cause_prioritizes_sign_and_activation_errors(self) -> None:
        self.assertEqual(
            _determine_root_cause(
                sign_coherence_ok=False,
                unexplained_discharge_blocking=False,
                exchange_mode="charge_only",
                vdc_above_ref_fraction=1.0,
                integral_dc_link_state_present=False,
            ),
            "sign_error",
        )
        self.assertEqual(
            _determine_root_cause(
                sign_coherence_ok=True,
                unexplained_discharge_blocking=True,
                exchange_mode="charge_only",
                vdc_above_ref_fraction=1.0,
                integral_dc_link_state_present=False,
            ),
            "incorrect_activation_or_blocking",
        )

    def test_charge_only_above_reference_without_integral_state_is_classified(self) -> None:
        self.assertEqual(
            _determine_root_cause(
                sign_coherence_ok=True,
                unexplained_discharge_blocking=False,
                exchange_mode="charge_only",
                vdc_above_ref_fraction=0.9,
                integral_dc_link_state_present=False,
            ),
            "vdc_operating_point_above_reference_with_proportional_only_support",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
