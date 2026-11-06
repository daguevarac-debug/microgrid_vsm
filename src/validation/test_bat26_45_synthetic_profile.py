"""BAT26-45: deterministic profile checks, no BLAST installation required."""
import sys
from pathlib import Path
import unittest

import numpy as np

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from validation.run_bat26_45_multicycle import (
    ACTIVE_END_S,
    C_RATE,
    DAY_S,
    INITIAL_CASE_AH,
    daily_profile,
)


class Bat2645ProfileTests(unittest.TestCase):
    def test_initial_closed_profile_and_efc(self):
        t, soc, temperature = daily_profile(1)
        self.assertEqual(len(t), 129)
        self.assertEqual((t[0], t[-1]), (0.0, DAY_S))
        self.assertEqual(soc[0], soc[-1])
        self.assertAlmostEqual(soc[0], 0.5)
        self.assertAlmostEqual(np.min(soc), 0.1)
        self.assertAlmostEqual(np.max(soc), 0.9)
        self.assertAlmostEqual(np.sum(np.abs(np.diff(soc))) / 2, 0.8)
        self.assertTrue(np.all(temperature == 25.0))

    def test_no_hidden_soc_jump_between_days(self):
        t1, s1, _ = daily_profile(1)
        t2, s2, _ = daily_profile(2)
        self.assertEqual(t1[-1], t2[0])
        self.assertEqual(s1[-1], s2[0])
        self.assertTrue(np.all(np.diff(t1) > 0))
        self.assertTrue(np.all(np.diff(t2) > 0))

    def test_active_c_rate_and_rest(self):
        t, soc, _ = daily_profile(1)
        active = t <= ACTIVE_END_S
        rest = t > ACTIVE_END_S
        dt = np.diff(t[active])
        i_equiv = -3600 * INITIAL_CASE_AH * np.diff(soc[active]) / dt
        self.assertTrue(np.allclose(np.abs(i_equiv), INITIAL_CASE_AH * C_RATE))
        self.assertTrue(np.all(soc[rest] == 0.5))
        self.assertAlmostEqual(float(t[-1] - ACTIVE_END_S) / 3600, 20.8)

    def test_invalid_cycle_index_rejected(self):
        with self.assertRaises(ValueError):
            daily_profile(0)


if __name__ == "__main__":
    unittest.main()
