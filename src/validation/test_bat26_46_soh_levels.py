"""BAT26-46: low-cost numerical contract tests for the SoH input scenarios."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.run_bat26_46_soh_levels import (
    BAT45_ROUNDED_CAPACITIES,
    BATTERY_PORT_I_A,
    _scenario_valid,
)


class Bat2646ScenarioTests(unittest.TestCase):
    def test_four_checkpoints_are_ordered_and_within_operating_soh(self):
        _scenario_valid()
        values = BAT45_ROUNDED_CAPACITIES
        self.assertEqual([cycle for cycle, _ in values], [0, 100, 500, 1000])
        self.assertTrue(all(0.50 <= q / 66.0 <= 1 for _, q in values))
        self.assertTrue(all(qa > qb for (_, qa), (_, qb) in zip(values, values[1:])))

    def test_same_8ah_discharge_changes_soc_more_as_capacity_fades(self):
        drops = [BATTERY_PORT_I_A / q for _, q in BAT45_ROUNDED_CAPACITIES]
        self.assertTrue(all(a < b for a, b in zip(drops, drops[1:])))
        self.assertAlmostEqual(drops[0], 8.0 / 44.1)
        self.assertAlmostEqual(drops[-1], 8.0 / 35.854)

    def test_initial_usable_charge_is_monotonic(self):
        usable = [(0.6 - 0.1) * q for _, q in BAT45_ROUNDED_CAPACITIES]
        self.assertAlmostEqual(usable[0], 22.05)
        self.assertAlmostEqual(usable[-1], 17.927)
        self.assertTrue(all(a > b for a, b in zip(usable, usable[1:])))


if __name__ == "__main__":
    unittest.main()
