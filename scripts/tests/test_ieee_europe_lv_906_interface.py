"""Unit tests for Phase 3 transformer interface math and Phase 4 QSTS energy profiles."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ieee_europe_lv_906_interface_and_qsts import (  # noqa: E402
    TRANSFORMER_SENSITIVITY_CASES,
    synthetic_bess_grid_power_kw,
)


class TestIEEE906InterfaceAndQSTS(unittest.TestCase):
    def test_transformer_hypothesis_properties_and_turns_ratio(self) -> None:
        h2 = [
            h for h in TRANSFORMER_SENSITIVITY_CASES if h.name == "H2_YNyn0_zk4p2_r1p5_nominal_hyp"
        ][0]
        self.assertAlmostEqual(float(h2.turns_ratio), 416.0 / (110.0 * math.sqrt(3.0)), places=5)
        self.assertAlmostEqual(float(h2.s_nom_kva), 5.0, places=6)
        self.assertAlmostEqual(float(h2.i_nom_inv_a), 5000.0 / (math.sqrt(3.0) * 190.5255888), places=4)
        self.assertAlmostEqual(float(h2.i_nom_grid_a), 5000.0 / (math.sqrt(3.0) * 416.0), places=4)
        reg_3kw = h2.regulation_approx_pct(s_load_kva=3.0, pf=1.0, lagging=True)
        self.assertGreater(reg_3kw, 0.8)
        self.assertLess(reg_3kw, 1.1)

    def test_synthetic_bess_24h_profile_is_energy_neutral(self) -> None:
        eta = 0.95
        p_bess = np.array(
            [synthetic_bess_grid_power_kw(m, eta_roundtrip_single_way=eta) for m in range(1440)],
            dtype=float,
        )
        e_charge_ac_kwh = float(np.sum(-p_bess[p_bess < 0]) / 60.0)
        e_discharge_ac_kwh = float(np.sum(p_bess[p_bess > 0]) / 60.0)
        # Internal battery energy stored vs withdrawn: E_in = eta * E_charge_ac, E_out = E_discharge_ac / eta
        e_internal_stored_kwh = eta * e_charge_ac_kwh
        e_internal_withdrawn_kwh = e_discharge_ac_kwh / eta
        self.assertAlmostEqual(e_internal_stored_kwh, e_internal_withdrawn_kwh, places=4)
        self.assertGreater(e_charge_ac_kwh, 3.5)
        self.assertLess(e_discharge_ac_kwh, e_charge_ac_kwh)

    def test_phase3_phase4_summary_json_exists_and_valid(self) -> None:
        summary_path = (
            ROOT
            / "outputs"
            / "analysis"
            / "ieee_europe_lv_906"
            / "phase3_phase4_interface_and_qsts_summary.json"
        )
        self.assertTrue(summary_path.exists(), f"Missing {summary_path}")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["phase3_transformer_design_hypotheses"]["analytical_cases"]), 5)
        self.assertEqual(
            len(payload["phase3_transformer_design_hypotheses"]["opendss_noon_3kw_sensitivity"]), 12
        )
        self.assertEqual(len(payload["phase4_qsts_24h_scenarios"]["scenarios"]), 7)


if __name__ == "__main__":
    unittest.main()
