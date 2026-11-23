"""BAT26-48: standard-library tests for the pre-optimization data contract."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.bat26_48_dispatch_contract import (
    AgingBoundary, EconomicScenario, nominal_efc_from_battery_port_throughput,
    require_verified_dc_port_mapping,
)


class Bat2648DispatchContractTests(unittest.TestCase):
    def test_initial_case_no_double_degradation(self):
        b = AgingBoundary(66.0, 44.1, 1.0, soc=0.6)
        self.assertAlmostEqual(b.q_eff_ah, 44.1)
        self.assertAlmostEqual(b.soh, 44.1 / 66)
        self.assertAlmostEqual(b.dischargeable_charge_ah, 22.05)
        self.assertAlmostEqual(b.chargeable_charge_ah, 13.23)

    def test_aging_checkpoint_soh_and_charge(self):
        b = AgingBoundary(66.0, 44.1, 35.854 / 44.1, soc=0.6)
        self.assertAlmostEqual(b.q_eff_ah, 35.854)
        self.assertAlmostEqual(b.soh, 35.854 / 66)
        self.assertAlmostEqual(b.dischargeable_charge_ah, 17.927)
        self.assertLess(b.dischargeable_charge_ah, 22.05)

    def test_coulomb_sign_and_frozen_capacity(self):
        fresh = AgingBoundary(66, 44.1, 1.0, soc=0.6)
        aged = AgingBoundary(66, 44.1, 35.854 / 44.1, soc=0.6)
        discharge_fresh = fresh.soc_after_port_current(
            battery_port_current_a=8, duration_s=3600,
        )
        discharge_aged = aged.soc_after_port_current(
            battery_port_current_a=8, duration_s=3600,
        )
        self.assertGreater(discharge_fresh, discharge_aged)
        self.assertAlmostEqual(discharge_fresh, 0.6 - 8 / 44.1)
        charge = fresh.soc_after_port_current(
            battery_port_current_a=-8, duration_s=3600,
        )
        self.assertGreater(charge, 0.6)
        self.assertAlmostEqual(fresh.q_eff_ah, 44.1)

    def test_limits_reject_not_clip(self):
        b = AgingBoundary(66, 44.1, 1.0, soc=0.1)
        with self.assertRaises(ValueError):
            b.soc_after_port_current(battery_port_current_a=8, duration_s=60)
        with self.assertRaises(ValueError):
            AgingBoundary(66, 44.1, 0.70, soc=0.6)  # 46.8% < 50% floor

    def test_battery_port_not_equated_to_dc_bus(self):
        b = AgingBoundary(66, 44.1, 1, soc=0.6)
        d = b.to_dispatch_boundary()
        self.assertIsNone(d["energy_usable_at_bus_kwh"])
        self.assertIsNone(d["dc_bus_p_dis_max_kw"])
        self.assertIsNone(d["battery_port_i_max_a"])
        self.assertIn("BLOCKED", d["dispatch_power_ready"])
        with self.assertRaises(NotImplementedError):
            require_verified_dc_port_mapping(b)

    def test_efc_not_equal_daily_cycle_counter(self):
        self.assertEqual(nominal_efc_from_battery_port_throughput(
            throughput_ah=1.6 * 44.1, q_reference_ah=44.1,
        ), 0.8)
        self.assertAlmostEqual(nominal_efc_from_battery_port_throughput(
            throughput_ah=0, q_reference_ah=44.1,
        ), 0)
        with self.assertRaises(ValueError):
            nominal_efc_from_battery_port_throughput(
                throughput_ah=-1, q_reference_ah=44.1,
            )

    def test_hypothetical_wear_cost_is_not_hardcoded(self):
        economic = EconomicScenario(
            asset_cost_cop=1110, residual_value_cop=0,
            q_case_initial_ah=44.1, q_retirement_ah=33,
        )
        self.assertAlmostEqual(economic.assumed_cop_per_lost_ah, 100)
        self.assertAlmostEqual(economic.cost_for_capacity_loss(
            q_before_ah=44.1, q_after_ah=43.1,
        ), 100)
        with self.assertRaises(ValueError):
            economic.cost_for_capacity_loss(q_before_ah=44.1, q_after_ah=32)
        with self.assertRaises(ValueError):
            EconomicScenario(
                asset_cost_cop=1000, residual_value_cop=100,
                q_case_initial_ah=44.1, q_retirement_ah=33,
                source_label="REAL_MARKET_PRICE",
            )


if __name__ == "__main__":
    unittest.main()
