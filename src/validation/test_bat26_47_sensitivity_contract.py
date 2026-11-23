"""BAT26-47: source-agnostic checks of sensitivity protocol; no BLAST calls."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.run_bat26_45_multicycle import daily_profile
from validation.run_bat26_47_blast_partition import (
    PARTITIONS, check_partition,
)
from validation.run_bat26_47_ecm_sensitivity import (
    BAT45_ROUNDED_CAPACITIES,
    CURRENTS_A,
    MAX_STEPS_S,
    R0_SENSITIVITY_FACTORS,
    simulate,
)


class Bat2647SensitivityTests(unittest.TestCase):
    def test_partition_coverage_and_shared_boundaries(self):
        t, soc, temp = daily_profile(1)
        self.assertEqual(len(t), 129)
        for name, partitions in PARTITIONS.items():
            with self.subTest(windows=name):
                self.assertEqual(len(partitions), name)
                check_partition(partitions, n_points=len(t))
                self.assertEqual(sum(b-a for a,b in partitions), len(t)-1)
                for (a, b), (c, d) in zip(partitions, partitions[1:]):
                    self.assertEqual((t[b], soc[b], temp[b]),
                                     (t[c], soc[c], temp[c]))

    def test_invalid_window_partition_rejected(self):
        for invalid in (((0, 64), (65, 128)), ((1, 128),),
                        ((0, 80), (79, 128)), ((0, 128), (128, 128))):
            with self.subTest(parts=invalid):
                with self.assertRaises(ValueError):
                    check_partition(invalid)

    def test_sweep_parameters_are_explicit(self):
        self.assertEqual(CURRENTS_A, (-8.0, 4.0, 8.0, 16.0))
        self.assertEqual(MAX_STEPS_S, (120.0, 60.0, 30.0, 15.0))
        self.assertEqual(R0_SENSITIVITY_FACTORS, (0.0, 1.0, 2.0))
        self.assertEqual(BAT45_ROUNDED_CAPACITIES[0], (0, 44.1))
        self.assertEqual(BAT45_ROUNDED_CAPACITIES[-1], (1000, 35.854))

    def test_1rc_soc_discharge_is_stronger_with_lower_q(self):
        fresh = simulate(44.1, 8.0, 60.0)
        aged = simulate(35.854, 8.0, 60.0)
        self.assertLess(aged["soc_final"], fresh["soc_final"])
        self.assertTrue(all(fresh["checks"].values()))
        self.assertTrue(all(aged["checks"].values()))

    def test_1rc_charging_sign_is_preserved(self):
        row = simulate(35.854, -8.0, 60.0)
        self.assertGreater(row["soc_final"], 0.6)
        self.assertLess(row["energy_terminal_signed_wh"], 0.0)
        self.assertTrue(all(row["checks"].values()))

    def test_r0_slope_changes_energy_but_not_soc(self):
        case0 = simulate(35.854, 8.0, 60.0, k_r=0.0)
        case2 = simulate(35.854, 8.0, 60.0, k_r=2.0)
        self.assertAlmostEqual(case0["soc_final"], case2["soc_final"], places=10)
        self.assertGreater(case0["energy_terminal_signed_wh"],
                           case2["energy_terminal_signed_wh"])


if __name__ == "__main__":
    unittest.main()
