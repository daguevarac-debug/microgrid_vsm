"""Tests for the final Task 5.3 frequency and Vdc closure checks."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_dc_link_pi_scenarios import (
    BASE_SCENARIO,
    SEVERE_SCENARIO,
)
from validation.validate_task_5_3_frequency_vdc_closure import (
    classify_closure_status,
    validate_vdc_task_4_1,
    vdc_recovery_time_with_dwell,
)


class TestTask53FrequencyVdcClosure(unittest.TestCase):
    def test_vdc_recovery_is_zero_when_trace_is_already_inside_band(self) -> None:
        time = np.linspace(0.0, 2.0, 201)
        vdc = np.full_like(time, 340.0)
        recovery = vdc_recovery_time_with_dwell(
            time,
            vdc,
            t_step_s=0.8,
            vdc_pre_step_v=340.0,
            band_pct=5.0,
            dwell_s=0.5,
        )
        self.assertAlmostEqual(recovery, 0.0)

    def test_vdc_recovery_requires_continuous_dwell(self) -> None:
        time = np.linspace(0.0, 3.0, 301)
        vdc = np.full_like(time, 340.0)
        vdc[(time >= 0.8) & (time < 1.2)] = 320.0
        vdc[(time >= 1.2) & (time < 1.4)] = 340.0
        vdc[(time >= 1.4) & (time < 1.5)] = 320.0
        vdc[time >= 1.5] = 340.0
        recovery = vdc_recovery_time_with_dwell(
            time,
            vdc,
            t_step_s=0.8,
            vdc_pre_step_v=340.0,
            band_pct=5.0,
            dwell_s=0.5,
        )
        self.assertAlmostEqual(recovery, 0.7)

    def test_vdc_closure_requires_deviation_minimum_and_recovery(self) -> None:
        time = np.linspace(0.0, 2.0, 201)
        vdc = np.full_like(time, 340.0)
        passing_metrics = {
            "vdc_pre_step_v": 340.0,
            "vdc_event_max_abs_deviation_v": 5.0,
            "vdc_event_max_abs_deviation_pct": 5.0 / 340.0 * 100.0,
            "vdc_event_deviation_pass": True,
            "vdc_min_post_step_v": 335.0,
            "vdc_min_required_v": 327.5,
            "vdc_minimum_voltage_pass": True,
        }
        result = validate_vdc_task_4_1(time, vdc, passing_metrics)
        self.assertTrue(result["vdc_recovery_pass"])
        self.assertTrue(result["vdc_task_4_1_closure_pass"])

        failing_metrics = dict(passing_metrics)
        failing_metrics["vdc_minimum_voltage_pass"] = False
        failing = validate_vdc_task_4_1(time, vdc, failing_metrics)
        self.assertFalse(failing["vdc_task_4_1_closure_pass"])

    def test_overall_closure_requires_both_subtasks_in_both_scenarios(self) -> None:
        passing = [
            {
                "scenario": BASE_SCENARIO.name,
                "activity_2_3_frequency_pass": True,
                "vdc_task_4_1_closure_pass": True,
            },
            {
                "scenario": SEVERE_SCENARIO.name,
                "activity_2_3_frequency_pass": True,
                "vdc_task_4_1_closure_pass": True,
            },
        ]
        self.assertEqual(classify_closure_status(passing), "PASS")

        failing = [dict(record) for record in passing]
        failing[1]["activity_2_3_frequency_pass"] = False
        self.assertEqual(classify_closure_status(failing), "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
