"""Unit tests for the non-invasive BAT26-53 MicrogridWithBESSDCDC interface."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from controllers.dc_link_bess_pi import DCLinkBESSPIController  # noqa: E402
from controllers.gfm_controller import GFMController  # noqa: E402
from microgrid_bess_dcdc import (  # noqa: E402
    BAT26_53_N_SERIES_2P_UNITS,
    MicrogridWithBESSDCDC,
    default_bat26_53_dcdc_parameters,
)
from validation.compare_bess_soh_scenarios import _build_bess_for_soh, _nominal_soh  # noqa: E402


class TestMicrogridWithBESSDCDC(unittest.TestCase):
    def _make_model(
        self,
        *,
        soc_initial: float = 0.60,
        eta_discharge: float = 0.95,
        eta_charge: float = 0.95,
        bess_enabled: bool = True,
    ) -> MicrogridWithBESSDCDC:
        bess = _build_bess_for_soh(_nominal_soh())
        bess.soc_initial = soc_initial
        gfm = GFMController(f_hz=50.0, inertia_m=80.0, damping_d=1500.0)
        pi = DCLinkBESSPIController(vdc_ref_v=340.0, kp_w_per_v=160.0, ki_w_per_v_s=400.0)
        dcdc_params = default_bat26_53_dcdc_parameters(
            eta_discharge=eta_discharge,
            eta_charge=eta_charge,
        )
        return MicrogridWithBESSDCDC(
            controller=gfm,
            dc_link_bess_pi=pi,
            bess_enabled=bess_enabled,
            bess_model=bess,
            dcdc_parameters=dcdc_params,
            load_frequency_hz=50.0,
        )

    def test_bat26_53_topology_and_16_state_mapping(self) -> None:
        m = self._make_model()
        self.assertEqual(m.dcdc_parameters.n_series, BAT26_53_N_SERIES_2P_UNITS)
        self.assertEqual(m.dcdc_parameters.n_series, 96)
        self.assertEqual(m.dcdc_parameters.n_parallel, 1)
        x0 = m.initial_state_with_bess(vdc0=340.0)
        self.assertEqual(len(x0), 16)
        self.assertEqual(m.bess_pi_state_index, 15)
        self.assertAlmostEqual(float(x0[10]), 2.0 * math.pi * 50.0, places=9)

    def test_bidirectional_above_and_below_340v_distinguishes_bank_and_bus(self) -> None:
        for soc0, expect_above_340 in ((0.60, True), (0.12, False)):
            m = self._make_model(soc_initial=soc0, eta_discharge=0.95, eta_charge=0.95)
            # Discharge request: Vdc = 335 V < 340 V -> e_vdc = +5 V -> P_req > 0
            c_dis = m._evaluate_dcdc_coupling(
                vdc_v=335.0, soc_bess=soc0, vrc_bess=0.0, soh_bess=_nominal_soh(), xi_bess_vdc_v_s=0.0
            )
            if expect_above_340:
                self.assertGreater(c_dis.v_bank_v, 340.0)
            else:
                self.assertLess(c_dis.v_bank_v, 340.0)
            self.assertGreater(c_dis.i_bank_a, 0.0)
            self.assertGreater(c_dis.i_bus_a, 0.0)
            self.assertNotAlmostEqual(c_dis.i_bank_a, c_dis.i_bus_a, places=2)
            self.assertAlmostEqual(c_dis.p_bank_w - c_dis.p_bus_w, c_dis.p_loss_w, places=9)
            self.assertGreater(c_dis.p_loss_w, 0.0)

            # Charge request: Vdc = 345 V > 340 V -> e_vdc = -5 V -> P_req < 0
            c_ch = m._evaluate_dcdc_coupling(
                vdc_v=345.0, soc_bess=soc0, vrc_bess=0.0, soh_bess=_nominal_soh(), xi_bess_vdc_v_s=0.0
            )
            self.assertLess(c_ch.i_bank_a, 0.0)
            self.assertLess(c_ch.i_bus_a, 0.0)
            self.assertNotAlmostEqual(c_ch.i_bank_a, c_ch.i_bus_a, places=2)
            self.assertAlmostEqual(c_ch.p_bank_w - c_ch.p_bus_w, c_ch.p_loss_w, places=9)
            self.assertGreater(c_ch.p_loss_w, 0.0)

    def test_disabled_bess_forces_zero_currents_and_losses(self) -> None:
        m = self._make_model(bess_enabled=False)
        x0 = m.initial_state_with_bess(vdc0=330.0)
        sig = m.integrated_signals(0.0, x0)
        self.assertEqual(sig["i_bess_bank_a"], 0.0)
        self.assertEqual(sig["i_bess_bus_a"], 0.0)
        self.assertEqual(sig["p_bess_bank_w"], 0.0)
        self.assertEqual(sig["p_bess_bus_w"], 0.0)
        self.assertEqual(sig["p_dcdc_loss_w"], 0.0)

    def test_ode_uses_unit_current_for_soc_and_bus_current_for_vdc(self) -> None:
        m = self._make_model(soc_initial=0.60, eta_discharge=0.90, eta_charge=0.90)
        x0 = m.initial_state_with_bess(vdc0=335.0)
        dx = m.system_dynamics(0.0, x0)
        sig = m.integrated_signals(0.0, x0)
        q_eff = m.bess.effective_capacity_ah(soh=_nominal_soh())
        expected_dsoc_dt = -float(sig["i_bess_unit_a"]) / (3600.0 * q_eff)
        self.assertAlmostEqual(dx[12], expected_dsoc_dt, places=12)
        self.assertNotAlmostEqual(float(sig["i_bess_unit_a"]), float(sig["i_bess_bus_a"]), places=2)
        ipv = m.plant.pv_current(x0[0], m.irradiance_profile(0), m.temperature_profile(0))
        expected_dvdc = (ipv + sig["i_bess_bus_a"] - sig["p_inv_dc_w"] / x0[0]) / m.plant.dcp.Cdc
        self.assertAlmostEqual(dx[0], expected_dvdc, places=9)

    def test_low_bus_voltage_respects_converter_current_limit(self) -> None:
        m = self._make_model()
        c = m._evaluate_dcdc_coupling(
            vdc_v=10.0, soc_bess=0.6, vrc_bess=0.0,
            soh_bess=_nominal_soh(), xi_bess_vdc_v_s=0.0,
        )
        self.assertLessEqual(abs(c.i_bus_a), m.dcdc_parameters.bus_current_max_a + 1e-9)
        self.assertAlmostEqual(c.p_bus_w, 10.0 * c.i_bus_a)

    def test_inherited_power_limit_applies_with_custom_converter(self) -> None:
        m = self._make_model()
        m.p_bess_max_w = 100.0
        for vdc in (330.0, 350.0):
            with self.subTest(vdc=vdc):
                c = m._evaluate_dcdc_coupling(
                    vdc_v=vdc, soc_bess=0.6, vrc_bess=0.0,
                    soh_bess=_nominal_soh(), xi_bess_vdc_v_s=0.0,
                )
                self.assertLessEqual(abs(c.p_bus_w), 100.0 + 1e-9)
                self.assertTrue(c.pi_output.anti_windup_active)


if __name__ == "__main__":
    unittest.main()
