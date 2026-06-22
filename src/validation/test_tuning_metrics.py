from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tuning_metrics import (
    DEFAULT_TUNING_CRITERIA,
    TuningCriteria,
    bess_stress_metrics,
    dc_link_performance_metrics,
    frequency_performance_metrics,
)


class TestTuningCriteria(unittest.TestCase):
    def test_default_numerical_limits(self) -> None:
        criteria = DEFAULT_TUNING_CRITERIA

        self.assertEqual(criteria.max_frequency_drop_hz, 0.50)
        self.assertEqual(criteria.frequency_recovery_band_hz, 0.10)
        self.assertEqual(criteria.max_frequency_recovery_s, 5.0)
        self.assertEqual(criteria.frequency_recovery_dwell_s, 0.50)
        self.assertEqual(criteria.max_vdc_overshoot_pct, 5.0)
        self.assertAlmostEqual(criteria.vdc_min_required_v, 327.5021, places=3)

    def test_nonpositive_limits_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TuningCriteria(max_frequency_drop_hz=0.0)


class TestFrequencyPerformanceMetrics(unittest.TestCase):
    def setUp(self) -> None:
        self.t = np.arange(0.0, 7.01, 0.01)
        self.t_step = 1.0

    def test_accepted_frequency_response(self) -> None:
        frequency = np.full_like(self.t, 60.0)
        tau = self.t - self.t_step
        post = tau >= 0.0
        recovery_ramp = np.clip((tau[post] - 0.05) / 2.0, 0.0, 1.0)
        frequency[post] = 59.6 + 0.4 * recovery_ramp

        metrics = frequency_performance_metrics(self.t, frequency, self.t_step)

        self.assertAlmostEqual(metrics["max_frequency_drop_hz"], 0.4, places=6)
        self.assertTrue(metrics["frequency_drop_pass"])
        self.assertTrue(metrics["frequency_recovery_pass"])
        self.assertTrue(metrics["frequency_criteria_pass"])
        self.assertLessEqual(metrics["frequency_recovery_time_s"], 5.0)

    def test_frequency_drop_above_half_hertz_is_rejected(self) -> None:
        frequency = np.full_like(self.t, 60.0)
        post = self.t >= self.t_step
        frequency[post] = 59.4

        metrics = frequency_performance_metrics(self.t, frequency, self.t_step)

        self.assertAlmostEqual(metrics["max_frequency_drop_hz"], 0.6, places=6)
        self.assertFalse(metrics["frequency_drop_pass"])
        self.assertFalse(metrics["frequency_criteria_pass"])

    def test_no_verified_dwell_returns_nan_recovery(self) -> None:
        frequency = np.full_like(self.t, 60.0)
        post = self.t >= self.t_step
        frequency[post] = 59.8

        metrics = frequency_performance_metrics(self.t, frequency, self.t_step)

        self.assertTrue(np.isnan(metrics["frequency_recovery_time_s"]))
        self.assertFalse(metrics["frequency_recovery_pass"])


class TestDcLinkPerformanceMetrics(unittest.TestCase):
    def setUp(self) -> None:
        self.t = np.arange(0.0, 2.01, 0.01)
        self.t_step = 0.5

    def test_accepted_dc_link_response(self) -> None:
        vdc = np.full_like(self.t, 340.0)
        vdc[(self.t >= 0.5) & (self.t < 0.7)] = 330.0
        vdc[(self.t >= 0.7) & (self.t < 0.8)] = 353.6

        metrics = dc_link_performance_metrics(self.t, vdc, self.t_step)

        self.assertAlmostEqual(metrics["vdc_overshoot_pct"], 4.0, places=6)
        self.assertTrue(metrics["vdc_overshoot_pass"])
        self.assertTrue(metrics["vdc_minimum_voltage_pass"])
        self.assertTrue(metrics["vdc_criteria_pass"])

    def test_excess_overshoot_and_undervoltage_are_rejected(self) -> None:
        vdc = np.full_like(self.t, 340.0)
        vdc[(self.t >= 0.5) & (self.t < 0.7)] = 325.0
        vdc[(self.t >= 0.7) & (self.t < 0.8)] = 360.4

        metrics = dc_link_performance_metrics(self.t, vdc, self.t_step)

        self.assertAlmostEqual(metrics["vdc_overshoot_pct"], 6.0, places=6)
        self.assertFalse(metrics["vdc_overshoot_pass"])
        self.assertFalse(metrics["vdc_minimum_voltage_pass"])
        self.assertFalse(metrics["vdc_criteria_pass"])


class TestSecondLifeBessDiagnostics(unittest.TestCase):
    def test_bess_stress_is_recorded_without_unverified_pass_fail_limit(self) -> None:
        t = np.linspace(0.0, 2.0, 201)
        current = np.zeros_like(t)
        power = np.zeros_like(t)
        soc = np.full_like(t, 0.60)
        post = t >= 0.5
        current[post] = 12.0
        power[post] = 3600.0
        soc[post] = np.linspace(0.60, 0.59, np.count_nonzero(post))

        metrics = bess_stress_metrics(t, current, power, t_step=0.5, soc=soc)

        self.assertEqual(metrics["i_bess_peak_abs_a"], 12.0)
        self.assertEqual(metrics["p_bess_peak_abs_w"], 3600.0)
        self.assertGreater(metrics["bess_energy_throughput_wh"], 0.0)
        self.assertAlmostEqual(metrics["soc_swing"], 0.01, places=9)
        self.assertNotIn("bess_pass", metrics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
