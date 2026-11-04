"""BAT26-42: mathematical DC-link energy identity and provisional 1RC envelopes.

These tests do not validate a physical battery-to-DC/DC-to-bus energy balance.
No BLAST-Lite dependency or experimental voltage/current limit is assumed.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.aging_capacity import CapacitySnapshot
from bess.model import SecondLifeBattery1RC
from controllers.gfm_controller import GFMController
from microgrid import Microgrid, MicrogridWithBESS


class TestDCCapacitorEnergyIdentity(unittest.TestCase):
    """BAT26-38 M10: capacitor power identity, not overall efficiency."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plant = Microgrid().plant
        cls.cdc = float(cls.plant.dcp.Cdc)
        if cls.cdc <= 0:
            raise AssertionError("Cdc must be positive for this test")

    def test_instantaneous_power_for_both_bess_directions(self) -> None:
        cases = (
            (8.0, 0.0, 8.0),       # Balanced, no battery exchange
            (8.0, 2.0, 8.0),       # Battery discharge raises DC voltage
            (8.0, -2.0, 8.0),      # Battery charge lowers DC voltage
            (7.0, 0.0, 9.0),       # Inverter draws more than PV delivers
            (9.0, -1.0, 8.0),      # Balanced with battery charging
        )
        for vdc in (300.0, 340.0, 380.0):
            for ipv, i_bess, idc_inv in cases:
                with self.subTest(vdc=vdc, currents=(ipv, i_bess, idc_inv)):
                    dv_dt = self.plant.dc_link_derivative(
                        ipv=ipv, i_bess=i_bess, idc_inv=idc_inv
                    )
                    lhs_w = self.cdc * vdc * dv_dt
                    rhs_w = vdc * (ipv + i_bess - idc_inv)
                    self.assertTrue(
                        math.isclose(lhs_w, rhs_w, rel_tol=1e-12, abs_tol=1e-10),
                        msg=f"DC capacitor identity: {lhs_w=} != {rhs_w=}",
                    )

    def test_incremental_battery_current_changes_dc_power_by_vdc_times_i(self) -> None:
        vdc = 340.0
        baseline = self.plant.dc_link_derivative(
            ipv=8.0, i_bess=0.0, idc_inv=8.0
        )
        for current in (3.0, -3.0):
            with self.subTest(i_bess=current):
                actual = self.plant.dc_link_derivative(
                    ipv=8.0, i_bess=current, idc_inv=8.0
                )
                observed_w = self.cdc * vdc * (actual - baseline)
                self.assertTrue(math.isclose(
                    observed_w, vdc * current, rel_tol=1e-12, abs_tol=1e-10
                ))

    def test_exact_constant_current_window_energy(self) -> None:
        # Under constant net current, Vdc is affine in time. The trapezoidal
        # integral of the DC port powers is therefore analytically exact.
        vdc0 = 340.0
        cases = (
            (8.0, 2.0, 9.0, 0.01),   # Net positive current
            (8.0, -2.0, 9.0, 0.01),  # Net negative current
            (8.0, -1.0, 7.0, 0.02),  # Balanced including battery charge
        )
        for ipv, i_bess, idc_inv, duration_s in cases:
            with self.subTest(currents=(ipv, i_bess, idc_inv)):
                net_current_a = ipv + i_bess - idc_inv
                vdc1 = vdc0 + duration_s * self.plant.dc_link_derivative(
                    ipv=ipv, i_bess=i_bess, idc_inv=idc_inv
                )
                self.assertGreater(vdc1, 0.0)
                delta_e_j = 0.5 * self.cdc * (vdc1**2 - vdc0**2)
                ports_e_j = 0.5 * (vdc0 + vdc1) * net_current_a * duration_s
                self.assertTrue(math.isclose(
                    delta_e_j, ports_e_j, rel_tol=1e-12, abs_tol=1e-10
                ))


class TestProvisionalBESSLimits(unittest.TestCase):
    """Test limits currently applied to the model's equivalent DC current."""

    @staticmethod
    def make_case(retention: float) -> tuple[MicrogridWithBESS, CapacitySnapshot]:
        snap = CapacitySnapshot(66.0, 44.1, retention)
        battery = SecondLifeBattery1RC(
            r0_nominal_ohm=0.000970,
            q_nom_ref_ah=66.0,
            q_init_case_ah=44.1,
            r0_soh_sensitivity=1.0,
        )
        grid = MicrogridWithBESS(
            bess_model=battery,
            controller=GFMController(
                p_ref=0.0, inertia_m=80.0, damping_d=1500.0
            ),
            kp_bess=1000.0,  # Deliberately forces saturation, synthetic only
            aging_mode="blast",
            blast_profile_kind="synthetic",
            capacity_snapshot=snap,
        )
        return grid, snap

    def test_soh_snapshot_reduces_current_and_power_envelopes(self) -> None:
        original, initial = self.make_case(1.0)
        aged, reduced = self.make_case(0.9)
        for grid, snapshot in ((original, initial), (aged, reduced)):
            with self.subTest(retention=snapshot.retention_since_case_start):
                i_av = grid._available_i_bess_max(snapshot.soh)
                p_av = grid._available_p_bess_max_w(snapshot.soh)
                self.assertAlmostEqual(i_av, 66.0 * snapshot.soh)
                self.assertAlmostEqual(p_av, 340.0 * i_av)
                self.assertAlmostEqual(
                    grid._compute_i_bess(330.0, 0.6, snapshot.soh), i_av
                )
                self.assertAlmostEqual(
                    grid._compute_i_bess(380.0, 0.6, snapshot.soh),
                    -min(i_av, p_av / 380.0),
                )
                self.assertEqual(
                    grid._compute_i_bess(330.0, grid.bess.soc_min, snapshot.soh),
                    0.0,
                )
                self.assertEqual(
                    grid._compute_i_bess(380.0, grid.bess.soc_max, snapshot.soh),
                    0.0,
                )
        self.assertLess(aged._available_i_bess_max(reduced.soh),
                        original._available_i_bess_max(initial.soh))

    def test_three_state_rhs_uses_snapshot_without_second_linear_fade(self) -> None:
        grid, snapshot = self.make_case(0.9)
        i_bess = 25.0
        low_throughput = grid.bess.rhs(
            0.0, [0.6, 0.0, 0.0], i_bess, snapshot.soh,
            capacity_snapshot=snapshot,
        )
        high_throughput = grid.bess.rhs(
            0.0, [0.6, 0.0, 1000.0], i_bess, snapshot.soh,
            capacity_snapshot=snapshot,
        )
        self.assertAlmostEqual(low_throughput[0],
                               -i_bess / (3600.0 * snapshot.q_eff_ah))
        self.assertAlmostEqual(low_throughput[2], i_bess / 3600.0)
        self.assertEqual(low_throughput, high_throughput)


if __name__ == "__main__":
    unittest.main(verbosity=2)
