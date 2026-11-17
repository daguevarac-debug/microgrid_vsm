"""Unit and regression tests for 50 Hz VSG audit (Phase 1) and BESS discharge (Phase 2)."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from microgrid import BalancedRLLoad, Microgrid  # noqa: E402
from microgrid_bess_pi import MicrogridWithBESSPI  # noqa: E402
from controllers.dc_link_bess_pi import DCLinkBESSPIController  # noqa: E402
from controllers.gfm_controller import GFMController  # noqa: E402


class TestVSG50HzAndBESSDischarge(unittest.TestCase):
    def test_50hz_rl_load_preserves_impedance_and_reactive_power(self) -> None:
        load60 = BalancedRLLoad.from_active_power(
            p_3ph_w=3000.0,
            power_factor=0.95,
            v_ln_rms=110.0,
            f_hz=60.0,
        )
        load50 = BalancedRLLoad.from_active_power(
            p_3ph_w=3000.0,
            power_factor=0.95,
            v_ln_rms=110.0,
            f_hz=50.0,
        )
        self.assertAlmostEqual(load50.r_ohm, load60.r_ohm, places=9)
        self.assertAlmostEqual(
            2.0 * math.pi * 50.0 * load50.l_h,
            2.0 * math.pi * 60.0 * load60.l_h,
            places=9,
        )
        self.assertAlmostEqual(load50.l_h / load60.l_h, 60.0 / 50.0, places=9)
        self.assertAlmostEqual(load50.q_3ph_var, load60.q_3ph_var, places=6)

    def test_50hz_microgrid_and_bess_pi_state_mappings_protected(self) -> None:
        omega50 = 2.0 * math.pi * 50.0
        gfm50 = GFMController(f_hz=50.0, inertia_m=80.0, damping_d=1500.0)
        mg12 = Microgrid(controller=gfm50, load_frequency_hz=50.0)
        x0_12 = mg12.initial_state()
        self.assertEqual(len(x0_12), 12)
        self.assertEqual(mg12.controller.controller_state_name, "omega")
        self.assertAlmostEqual(float(x0_12[10]), omega50, places=9)

        pi = DCLinkBESSPIController(vdc_ref_v=340.0, kp_w_per_v=160.0, ki_w_per_v_s=400.0)
        mg16 = MicrogridWithBESSPI(
            controller=gfm50,
            dc_link_bess_pi=pi,
            load_frequency_hz=50.0,
        )
        x0_16 = mg16.initial_state_with_bess()
        self.assertEqual(len(x0_16), 16)
        self.assertEqual(mg16.bess_pi_state_index, 15)
        self.assertEqual(mg16.state_count_with_bess_pi, 16)
        self.assertAlmostEqual(float(x0_16[10]), omega50, places=9)

    def test_phase1_6p5s_audit_json_invariants(self) -> None:
        audit_path = ROOT / "outputs" / "validation" / "vsg_50hz_interface_audit_6p5s.json"
        self.assertTrue(audit_path.exists(), f"Missing {audit_path}")
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertAlmostEqual(float(payload["t_end_s"]), 6.5, places=6)
        self.assertEqual(payload["M"], 80.0)
        self.assertEqual(payload["D"], 1500.0)

        by_cfg = {
            (int(round(s["frequency_hz"])), round(s["step"], 2), bool(s["bess"])): s
            for s in payload["scenarios_6p5s"]
        }
        self.assertIn((50, 0.4, False), by_cfg)
        self.assertIn((60, 0.4, False), by_cfg)
        self.assertIn((50, 0.2, False), by_cfg)

        # Verify explicit Vdc window separation (initial vs global min vs post-step min)
        s20_50 = by_cfg[(50, 0.2, False)]
        self.assertAlmostEqual(float(s20_50["vdc_initial_v"]), 340.0, places=6)
        self.assertAlmostEqual(float(s20_50["vdc_global_min_v"]), 340.0, places=6)
        self.assertGreater(float(s20_50["vdc_post_min_v"]), 360.0)
        self.assertEqual(s20_50["status"], "PASS")

        # Verify +40% no-BESS remains REVIEW due to physical PV MPP limit
        s40_50 = by_cfg[(50, 0.4, False)]
        self.assertEqual(s40_50["status"], "REVIEW")
        vdc_min_req = float(
            payload["severe_40pct_limitation_analysis"]["vdc_min_required_for_110v_rms_at_m0p95_v"]
        )
        self.assertLess(float(s40_50["vdc_post_min_v"]), vdc_min_req)
        self.assertGreater(float(s40_50["modulation_limited_fraction_post"]), 0.95)

    def test_phase2_bess_discharge_json_invariants(self) -> None:
        summary_path = (
            ROOT / "outputs" / "validation" / "bess_50hz_discharge" / "bess_50hz_discharge_summary.json"
        )
        self.assertTrue(summary_path.exists(), f"Missing {summary_path}")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "PASS")

        cases = {c["label"]: c for c in payload["scenarios"]}
        c_step40_on = cases["step40_50hz_soh_1p00"]
        c_step40_off = cases["step40_50hz_bess_disabled"]
        self.assertEqual(c_step40_on["status"], "PASS")
        self.assertEqual(c_step40_off["status"], "REVIEW")
        self.assertGreater(float(c_step40_on["i_bess_post_max_a"]), 0.8)
        self.assertGreater(float(c_step40_on["p_bess_dc_post_max_w"]), 250.0)
        self.assertGreater(float(c_step40_on["e_bess_dc_post_j"]), 1500.0)
        self.assertAlmostEqual(float(c_step40_off["e_bess_dc_post_j"]), 0.0, places=9)
        self.assertLess(abs(float(c_step40_on["e_balance_residual_post_j"])), 0.1)
        self.assertLess(float(c_step40_on["one_rc_power_decomposition_max_residual_w"]), 1e-9)

        c_irr_on = cases["irrad_drop_50hz_bess_enabled"]
        c_irr_off = cases["irrad_drop_50hz_bess_disabled"]
        self.assertEqual(c_irr_on["status"], "PASS")
        self.assertEqual(c_irr_off["status"], "REVIEW")
        self.assertGreater(float(c_irr_on["p_bess_dc_post_max_w"]), 1200.0)
        self.assertGreater(float(c_irr_on["e_bess_dc_post_j"]), 6500.0)
        self.assertGreater(float(c_irr_on["vdc_min_post_step_v"]), 330.0)
        self.assertLess(float(c_irr_off["vdc_min_post_step_v"]), 230.0)


if __name__ == "__main__":
    unittest.main()
