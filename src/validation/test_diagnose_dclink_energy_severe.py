"""Tests for the severe DC-link energy-signal diagnostic helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.diagnose_dclink_energy_severe import (
    CSV_COLUMNS,
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    _build_scenario,
    _source_power_w,
)


class TestDCLinkEnergyDiagnostic(unittest.TestCase):
    def test_selected_point_and_requested_columns(self) -> None:
        self.assertEqual(GFM_SELECTED_M, 80.0)
        self.assertEqual(GFM_SELECTED_D, 1500.0)
        self.assertEqual(
            CSV_COLUMNS,
            (
                "time_s",
                "vdc_v",
                "p_load_w",
                "p_source_pv_dc_w",
                "p_bess_dc_w",
                "i_bess_a",
            ),
        )

    def test_scenario_is_gfm_with_bess_and_severe_step(self) -> None:
        model, initial_state, metadata = _build_scenario()
        self.assertEqual(model.controller_state_name, "omega")
        self.assertEqual(len(initial_state), 15)
        self.assertAlmostEqual(metadata["load_step_pct"], 40.0)
        self.assertGreater(
            metadata["p_load_post_step_w"],
            metadata["p_load_pre_step_w"],
        )

    def test_source_power_uses_dc_link_pv_current(self) -> None:
        model, initial_state, _ = _build_scenario()
        vdc = float(initial_state[0])
        t = 0.0
        irradiance = float(model.irradiance_profile(t))
        temperature = float(model.temperature_profile(t))
        ipv = model.plant.pv_current(vdc, irradiance, temperature)
        expected = vdc * ipv
        actual = _source_power_w(model, t, vdc)
        self.assertTrue(np.isfinite(actual))
        self.assertAlmostEqual(actual, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
