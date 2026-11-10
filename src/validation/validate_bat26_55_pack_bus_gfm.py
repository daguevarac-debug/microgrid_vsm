"""BAT26-55 algebraic port checks and four-capacity GFM discharge campaign.

All converter values are hypothetical fixtures, not hardware ratings. The
campaign uses one global solve_ivp per independent capacity case.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
from scipy.integrate import solve_ivp

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bess.aging_capacity import CapacitySnapshot
from bess.dc_dc_adapter import DCDCParameters, convert_power
from bess.leaf_48module_pack import Leaf48ModulePack
from bess.model import SecondLifeBattery1RC
from config import BESS_COUPLED_R0_DEFAULT
from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS


CAPACITIES_AH = (44.100, 42.273, 39.038, 35.854)
SOC0 = 0.60
T_END_S = 0.30
EVENT_S = 0.10
ETA_DCDC = 0.95  # hypothetical fixture only
UNIT_CURRENT_LIMIT_A = 10.0  # hypothetical fixture only
BUS_CURRENT_LIMIT_A = 20.0  # hypothetical fixture only
BUS_POWER_LIMIT_W = 5000.0  # hypothetical fixture only


def fixture_parameters(pack: Leaf48ModulePack | None = None, *,
                       unit_current_a: float = UNIT_CURRENT_LIMIT_A,
                       bus_current_a: float = BUS_CURRENT_LIMIT_A,
                       bus_power_w: float = BUS_POWER_LIMIT_W) -> DCDCParameters:
    pack = pack or Leaf48ModulePack()
    return pack.converter_parameters(
        eta_discharge=ETA_DCDC, eta_charge=ETA_DCDC,
        unit_discharge_max_a=unit_current_a, unit_charge_max_a=unit_current_a,
        bus_current_max_a=bus_current_a, bus_power_max_w=bus_power_w,
    )


def adapter_common(parameters: DCDCParameters) -> dict[str, object]:
    return dict(parameters=parameters, bus_voltage_v=340.0, ocv_v=3.75,
                vrc_v=0.0, r0_ohm=0.000970, soc_min=0.10, soc_max=0.90)


class TestBAT26_55Ports(unittest.TestCase):
    def test_bus_current_request_and_signed_integrated_power_balance(self):
        pack = Leaf48ModulePack()
        model = build_model(pack, build_battery(44.1), fixture_parameters(pack), irradiance=200.0)
        state = model.initial_state_with_bess()
        for vdc in (330.0, 350.0):
            state[0] = vdc
            current = model._compute_i_bess(vdc, state[12], pack.capacity().soh)
            signals = model.integrated_signals(0.2, state)
            self.assertEqual(current, 5.0 if vdc == 330.0 else -5.0)
            self.assertAlmostEqual(signals["p_bus"], vdc * current, places=9)
            self.assertEqual(signals["dcdc_saturated"], 0.0)
            self.assertAlmostEqual(signals["p_pack"] - signals["p_bus"],
                                   signals["p_dcdc_loss"], places=9)
            self.assertGreaterEqual(signals["p_dcdc_loss"], 0.0)
            if current > 0:
                self.assertAlmostEqual(signals["p_bus"], ETA_DCDC * signals["p_pack"], places=9)
                self.assertGreater(signals["i_pack"], 0)
            else:
                self.assertAlmostEqual(signals["p_pack"], ETA_DCDC * signals["p_bus"], places=9)
                self.assertLess(signals["i_pack"], 0)
        self.assertEqual(330.0 * 5.0, 1650.0)

    def test_saturation_stages_and_protection_are_distinct(self):
        pack = Leaf48ModulePack()
        model = build_model(pack, build_battery(44.1), fixture_parameters(pack), irradiance=200.0)
        state = model.initial_state_with_bess()
        state[0] = 200.0
        model.p_bess_max_w = 1000.0
        s = model.integrated_signals(0.2, state)
        self.assertEqual(s["p_bus"], 1000.0)
        self.assertEqual((s["dcdc_saturated"], s["dcdc_supervision_saturated"],
                          s["dcdc_adapter_saturated"]), (1.0, 1.0, 0.0))
        # Exercise the separate power clamp even if the normal current
        # supervisor already enforces the same bus-power limit.
        with patch.object(model, "_compute_i_bess", return_value=10.0):
            s = model.integrated_signals(0.2, state)
        self.assertEqual(s["p_bus"], 1000.0)
        self.assertEqual(s["dcdc_supervision_saturated"], 1.0)
        model.p_bess_max_w = 22440.0
        model.dcdc_parameters = fixture_parameters(pack, unit_current_a=1.0)
        state[0] = 330.0
        s = model.integrated_signals(0.2, state)
        self.assertEqual((s["dcdc_saturated"], s["dcdc_supervision_saturated"],
                          s["dcdc_adapter_saturated"]), (1.0, 0.0, 1.0))
        state[13] = 2.0  # zero-current unit undervoltage
        s = model.integrated_signals(0.2, state)
        self.assertEqual(s["dcdc_protection_status"], "unit_undervoltage")
        self.assertEqual(s["p_bus"], 0.0)
        self.assertEqual(s["dcdc_soc_blocked"], 0.0)

    def test_soc_contract_boundaries_and_rhs_interleaving(self):
        pack = Leaf48ModulePack()
        for incompatible in (Leaf48ModulePack(soc_min=0.20),
                             Leaf48ModulePack(soc_max=0.80)):
            with self.assertRaisesRegex(ValueError, "SoC limits"):
                build_model(incompatible, build_battery(44.1),
                            fixture_parameters(pack), irradiance=200.0)
        model = build_model(pack, build_battery(44.1), fixture_parameters(pack), irradiance=200.0)
        x = model.initial_state_with_bess()
        for soc, vdc, blocked in ((.1, 330., True), (.1, 350., False),
                                  (.9, 350., True), (.9, 330., False)):
            x[12], x[0] = soc, vdc
            s = model.integrated_signals(.2, x)
            self.assertEqual(bool(s["dcdc_soc_blocked"]), blocked)
            self.assertEqual(s["i_bus"] == 0.0, blocked)
            if blocked:
                self.assertEqual(s["dcdc_saturated"], 1.0)
                self.assertEqual(s["dcdc_supervision_saturated"], 1.0)
        x[12], x[0] = .6, 330.
        first = model.system_dynamics(.2, x)
        y = x.copy()
        y[0] = 350.
        model.system_dynamics(.1, y)
        self.assertEqual(first, model.system_dynamics(.2, x))

    def test_discharge_charge_and_power_conservation(self):
        pack = Leaf48ModulePack()
        p = fixture_parameters(pack)
        dis = convert_power(bus_power_request_w=3000.0, soc=SOC0,
                            **adapter_common(p))
        ch = convert_power(bus_power_request_w=-2000.0, soc=SOC0,
                           **adapter_common(p))
        self.assertGreater(dis.unit_current_a, 0)
        self.assertGreater(dis.bus_current_a, 0)
        self.assertGreater(dis.bus_power_w, 0)
        self.assertLess(ch.unit_current_a, 0)
        self.assertLess(ch.bus_current_a, 0)
        self.assertLess(ch.bus_power_w, 0)
        for result in (dis, ch):
            self.assertAlmostEqual(result.bus_power_w,
                                   340.0 * result.bus_current_a, places=9)
            self.assertAlmostEqual(result.bank_power_w,
                                   96 * result.unit_voltage_v * result.unit_current_a,
                                   places=8)
            self.assertGreaterEqual(result.loss_power_w, 0.0)
            self.assertAlmostEqual(result.bank_power_w - result.bus_power_w,
                                   result.loss_power_w, places=9)

    def test_converter_power_current_soc_soh_and_voltage_limits(self):
        p = fixture_parameters()
        high = convert_power(bus_power_request_w=10000.0, soc=SOC0,
                             **adapter_common(p))
        self.assertTrue(high.saturated)
        self.assertLessEqual(high.bus_power_w, BUS_POWER_LIMIT_W)
        self.assertLessEqual(abs(high.bus_current_a), BUS_CURRENT_LIMIT_A)
        low_i = convert_power(bus_power_request_w=3000.0, soc=SOC0,
                              **adapter_common(fixture_parameters(unit_current_a=1.0)))
        self.assertTrue(low_i.saturated)
        self.assertLessEqual(abs(low_i.unit_current_a), 1.0 + 1e-12)
        at_min = convert_power(bus_power_request_w=1000.0, soc=0.10,
                               **adapter_common(p))
        at_max = convert_power(bus_power_request_w=-1000.0, soc=0.90,
                               **adapter_common(p))
        self.assertEqual(at_min.bus_power_w, 0.0)
        self.assertEqual(at_max.bus_power_w, 0.0)
        out = convert_power(bus_power_request_w=1000.0, soc=SOC0,
                            **{**adapter_common(p), "ocv_v": 4.20})
        self.assertEqual(out.protection_status, "unit_overvoltage")
        self.assertEqual(out.bus_power_w, 0.0)
        under = convert_power(bus_power_request_w=-1000.0, soc=SOC0,
                              **{**adapter_common(p), "ocv_v": 2.40})
        self.assertEqual(under.protection_status, "unit_undervoltage")
        self.assertEqual(under.bus_power_w, 0.0)
        bad_bus = convert_power(bus_power_request_w=100.0, soc=SOC0,
                                **{**adapter_common(p), "bus_voltage_v": 0.0})
        self.assertEqual(bad_bus.protection_status, "bus_voltage_nonpositive")
        self.assertEqual(bad_bus.bus_current_a, 0.0)

    def test_optional_model_uses_distinct_pack_and_bus_currents_deterministically(self):
        pack = Leaf48ModulePack()
        snapshot = pack.capacity()
        battery = build_battery(44.1)
        model = build_model(pack, battery, fixture_parameters(pack), irradiance=200.0)
        state = model.initial_state_with_bess()
        state[0] = 330.0
        before = model.integrated_signals(0.2, state)
        deriv = model.system_dynamics(0.2, state)
        after = model.integrated_signals(0.2, state)
        self.assertEqual(before, after)
        self.assertEqual(len(deriv), 15)
        self.assertAlmostEqual(before["i_bus"], before["p_bus"] / before["Vdc"], places=10)
        self.assertAlmostEqual(before["p_bess_dc"], before["Vdc"] * before["i_bus"], places=10)
        self.assertGreater(before["i_pack"], 0)
        self.assertGreater(before["i_bus"], 0)
        self.assertNotAlmostEqual(before["i_pack"], before["i_bus"], places=4)
        expected_dsoc = -before["i_pack"] / (3600 * snapshot.q_eff_ah)
        self.assertAlmostEqual(deriv[12], expected_dsoc, places=12)
        self.assertEqual(snapshot.q_eff_ah, 44.1)
        self.assertEqual((pack.n_2p_series, pack.n_parallel_strings), (96, 1))

    def test_historical_path_stays_default_and_optional_pair_is_required(self):
        historical = MicrogridWithBESS()
        self.assertIsNone(historical.dcdc_parameters)
        self.assertIsNone(historical.leaf_pack)
        x = historical.initial_state_with_bess()
        for voltage in (330.0, 350.0):
            x[0] = voltage
            signals = historical.integrated_signals(.2, x)
            expected = historical.kp_bess * (historical.vdc_ref - voltage)
            self.assertAlmostEqual(signals["i_bess"], expected, places=12)
            self.assertEqual(signals["i_pack"], signals["i_bess"])
            self.assertEqual(signals["p_bess_dc"], voltage * expected)
            self.assertAlmostEqual(historical.system_dynamics(.2, x)[12],
                                   -expected / (3600 * historical.bess.q_init_case_ah), places=12)
        with self.assertRaises(ValueError):
            MicrogridWithBESS(leaf_pack=Leaf48ModulePack())
        with self.assertRaises(ValueError):
            MicrogridWithBESS(dcdc_parameters=fixture_parameters())
        other_pack = Leaf48ModulePack(q_init_case_ah=42.273)
        with self.assertRaises(ValueError):
            MicrogridWithBESS(
                bess_model=build_battery(44.1), leaf_pack=other_pack,
                dcdc_parameters=fixture_parameters(other_pack),
            )


def build_battery(q_init_ah: float) -> SecondLifeBattery1RC:
    return SecondLifeBattery1RC(
        r0_nominal_ohm=BESS_COUPLED_R0_DEFAULT,
        q_nom_ref_ah=66.0,
        q_init_case_ah=q_init_ah,
        r0_soh_sensitivity=1.0,
        k_deg=1.478e-6,
        soh_min=0.50,
        q_eff_min_ah=1e-9,
        soc_initial=SOC0,
        soc_min=0.10,
        soc_max=0.90,
    )


def build_model(pack: Leaf48ModulePack, battery: SecondLifeBattery1RC,
                parameters: DCDCParameters, *, irradiance: float) -> MicrogridWithBESS:
    return MicrogridWithBESS(
        controller=GFMController(p_ref=4000.0, inertia_m=80.0, damping_d=1500.0),
        bess_model=battery,
        irradiance_profile=lambda _t: irradiance,
        load_profile=lambda t: 3000.0 if t < EVENT_S else 4200.0,
        leaf_pack=pack,
        dcdc_parameters=parameters,
        capacity_snapshot=(pack.capacity() if battery.q_init_case_ah == pack.q_init_case_ah
                           else None),
        aging_mode=("blast" if battery.q_init_case_ah == pack.q_init_case_ah else "linear"),
        blast_profile_kind=("synthetic" if battery.q_init_case_ah == pack.q_init_case_ah else None),
    )


def run_campaign() -> dict[str, object]:
    """Run four independent 15-state cases with the same profiles and VSG point."""
    cases: list[dict[str, object]] = []
    all_discharge = True
    all_stable = True
    for q_init in CAPACITIES_AH:
        pack = Leaf48ModulePack(q_init_case_ah=q_init)
        snapshot = pack.capacity()
        battery = build_battery(q_init)
        parameters = fixture_parameters(pack)
        model = MicrogridWithBESS(
            controller=GFMController(p_ref=4000.0, inertia_m=80.0, damping_d=1500.0),
            bess_model=battery,
            irradiance_profile=lambda _t: 200.0,
            load_profile=lambda t: 3000.0 if t < EVENT_S else 4200.0,
            leaf_pack=pack,
            dcdc_parameters=parameters,
            capacity_snapshot=snapshot,
            aging_mode="blast",
            blast_profile_kind="synthetic",
        )
        t_eval = np.linspace(0.0, T_END_S, 61)
        solution = solve_ivp(
            model.system_dynamics, (0.0, T_END_S), model.initial_state_with_bess(),
            method="RK45", rtol=1e-6, atol=1e-9, max_step=5e-5, t_eval=t_eval,
        )
        signals = [model.integrated_signals(float(t), solution.y[:, k])
                   for k, t in enumerate(solution.t)]
        finite = bool(np.isfinite(solution.y).all()) and all(
            math.isfinite(float(row[key])) for row in signals
            for key in ("Vdc", "i_pack", "i_bus", "p_pack", "p_bus", "v_pack", "soc_bess", "soh_bess")
        )
        max_i_pack = max(abs(float(s["i_pack"])) for s in signals)
        max_i_bus = max(abs(float(s["i_bus"])) for s in signals)
        max_p_bus = max(abs(float(s["p_bus"])) for s in signals)
        discharge_rows = [s for s in signals if float(s["i_pack"]) > 0
                          and float(s["i_bus"]) > 0 and float(s["p_bus"]) > 0]
        discharge_interval = (len(discharge_rows) * (T_END_S / (len(t_eval) - 1)))
        stable = bool(solution.success and finite and len(solution.y) == 15
                      and np.all(solution.y[0] > 0.0)
                      and np.all(solution.y[12] >= pack.soc_min - 1e-9)
                      and np.all(solution.y[12] <= pack.soc_max + 1e-9)
                      and min(float(s["v_pack"]) for s in signals) >= pack.minimum_voltage_v
                      and max(float(s["v_pack"]) for s in signals) <= pack.maximum_voltage_v
                      and max_i_pack <= min(parameters.unit_discharge_max_a,
                                            model._available_i_bess_max(snapshot.soh)) + 1e-8
                      and max_i_bus <= parameters.bus_current_max_a + 1e-8
                      and max_p_bus <= parameters.bus_power_max_w + 1e-8)
        all_stable &= stable
        all_discharge &= bool(discharge_rows)
        omega = solution.y[10]
        frequency = omega / (2.0 * math.pi)
        energies = {
            "pack_terminal_signed_Wh": float(np.trapezoid([float(s["p_pack"]) for s in signals], solution.t) / 3600.0),
            "bus_signed_Wh": float(np.trapezoid([float(s["p_bus"]) for s in signals], solution.t) / 3600.0),
            "converter_loss_Wh": float(np.trapezoid([float(s["p_dcdc_loss"]) for s in signals], solution.t) / 3600.0),
        }
        cases.append({
            "q_eff_initial_Ah": q_init,
            "soh_initial": snapshot.soh,
            "soc_initial": SOC0,
            "soc_final": float(solution.y[12, -1]),
            "soh_final": float(model._bess_soh(solution.y[14, -1])),
            "state_count": int(solution.y.shape[0]),
            "solver_success": bool(solution.success),
            "solver_message": solution.message,
            "finite_states_signals": finite,
            "Vdc_min_V": float(np.min(solution.y[0])),
            "Vdc_max_V": float(np.max(solution.y[0])),
            "frequency_min_Hz": float(np.min(frequency)),
            "frequency_max_Hz": float(np.max(frequency)),
            "I_pack_max_abs_A": max_i_pack,
            "I_bus_max_abs_A": max_i_bus,
            "P_pack_max_abs_W": max(abs(float(s["p_pack"])) for s in signals),
            "P_bus_max_abs_W": max_p_bus,
            "V_pack_min_V": min(float(s["v_pack"]) for s in signals),
            "V_pack_max_V": max(float(s["v_pack"]) for s in signals),
            "converter_loss_max_W": max(float(s["p_dcdc_loss"]) for s in signals),
            "discharge_samples": len(discharge_rows),
            "discharge_interval_estimate_s": discharge_interval,
            "energies": energies,
            "limits_and_states_pass": stable,
            "discharge_demonstrated": bool(discharge_rows),
        })
    status = "PASS" if all_stable and all_discharge else (
        "REVIEW" if all_stable and not all_discharge else "FAIL"
    )
    return {
        "task": "BAT26-55",
        "status": status,
        "validation_scope": "numerical simulation only; no experimental/HIL validation",
        "topology": "48 modules; 96 2p units in series; one string; capacity is not multiplied",
        "soc_initial": SOC0,
        "profiles": {"irradiance_W_m2": 200.0, "load_pre_W": 3000.0,
                     "load_post_W": 4200.0, "step_time_s": EVENT_S,
                     "duration_s": T_END_S},
        "vsg": {"controller": "GFMController", "M": 80.0, "D": 1500.0,
                "frequency_definition": "omega/(2*pi)"},
        "converter_fixture_hypotheses": {"eta_charge": ETA_DCDC,
            "eta_discharge": ETA_DCDC, "unit_current_limit_A": UNIT_CURRENT_LIMIT_A,
            "bus_current_limit_A": BUS_CURRENT_LIMIT_A,
            "bus_power_limit_W": BUS_POWER_LIMIT_W},
        "cases": cases,
    }


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv.remove("--test")
        unittest.main(verbosity=2)
    else:
        print(json.dumps(run_campaign(), indent=2, ensure_ascii=False))
