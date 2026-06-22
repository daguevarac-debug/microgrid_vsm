"""Reproducible performance metrics for Bucket 4 VSG tuning.

The acceptance limits defined here are thesis design criteria, not universal
standards. They are intentionally separated from controller parameters so the
same definitions can be applied to every candidate (M, D) and, later, FOVIC
parameter set.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np

from config import (
    GRID_FREQ_HZ_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    SIM_VDC0_V_DEFAULT,
    TUNING_FREQUENCY_RECOVERY_BAND_HZ_DEFAULT,
    TUNING_FREQUENCY_RECOVERY_DWELL_S_DEFAULT,
    TUNING_MAX_FREQUENCY_DROP_HZ_DEFAULT,
    TUNING_MAX_FREQUENCY_RECOVERY_S_DEFAULT,
    TUNING_MAX_VDC_OVERSHOOT_PCT_DEFAULT,
    TUNING_PRE_STEP_WINDOW_S_DEFAULT,
)


@dataclass(frozen=True)
class TuningCriteria:
    """Numerical acceptance criteria adopted for Task 4.1.

    The frequency and DC-link limits are hard constraints. For a second-life
    BESS, meeting these constraints is necessary but not sufficient: battery
    current, power, energy throughput, SoC, SoH and terminal-voltage limits
    must also be respected before a tuning candidate can be selected.
    """

    nominal_frequency_hz: float = GRID_FREQ_HZ_DEFAULT
    max_frequency_drop_hz: float = TUNING_MAX_FREQUENCY_DROP_HZ_DEFAULT
    frequency_recovery_band_hz: float = TUNING_FREQUENCY_RECOVERY_BAND_HZ_DEFAULT
    max_frequency_recovery_s: float = TUNING_MAX_FREQUENCY_RECOVERY_S_DEFAULT
    frequency_recovery_dwell_s: float = TUNING_FREQUENCY_RECOVERY_DWELL_S_DEFAULT
    pre_step_window_s: float = TUNING_PRE_STEP_WINDOW_S_DEFAULT

    vdc_reference_v: float = SIM_VDC0_V_DEFAULT
    max_vdc_overshoot_pct: float = TUNING_MAX_VDC_OVERSHOOT_PCT_DEFAULT
    ac_phase_voltage_rms_v: float = GRID_V_LN_RMS_DEFAULT
    modulation_index_max: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT

    def __post_init__(self) -> None:
        strictly_positive = {
            "nominal_frequency_hz": self.nominal_frequency_hz,
            "max_frequency_drop_hz": self.max_frequency_drop_hz,
            "frequency_recovery_band_hz": self.frequency_recovery_band_hz,
            "max_frequency_recovery_s": self.max_frequency_recovery_s,
            "frequency_recovery_dwell_s": self.frequency_recovery_dwell_s,
            "pre_step_window_s": self.pre_step_window_s,
            "vdc_reference_v": self.vdc_reference_v,
            "max_vdc_overshoot_pct": self.max_vdc_overshoot_pct,
            "ac_phase_voltage_rms_v": self.ac_phase_voltage_rms_v,
            "modulation_index_max": self.modulation_index_max,
        }
        for name, value in strictly_positive.items():
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and > 0, got {value!r}.")

    @property
    def vdc_min_required_v(self) -> float:
        """Minimum DC voltage required to synthesize the nominal AC voltage."""
        return 2.0 * sqrt(2.0) * self.ac_phase_voltage_rms_v / self.modulation_index_max


DEFAULT_TUNING_CRITERIA = TuningCriteria()


def _validated_trace(
    t: np.ndarray | list[float],
    values: np.ndarray | list[float],
    *,
    value_name: str,
) -> tuple[np.ndarray, np.ndarray]:
    time = np.asarray(t, dtype=float)
    signal = np.asarray(values, dtype=float)
    if time.ndim != 1 or signal.ndim != 1:
        raise ValueError("t and signal traces must be one-dimensional.")
    if time.size < 2 or signal.size != time.size:
        raise ValueError("t and signal traces must have equal length >= 2.")
    if not np.all(np.isfinite(time)) or not np.all(np.isfinite(signal)):
        raise ValueError(f"t and {value_name} must contain only finite values.")
    if not np.all(np.diff(time) > 0.0):
        raise ValueError("t must be strictly increasing.")
    return time, signal


def _pre_step_mean(
    t: np.ndarray,
    signal: np.ndarray,
    t_step: float,
    window_s: float,
) -> float:
    window_mask = (t >= (t_step - window_s)) & (t < t_step)
    if np.any(window_mask):
        return float(np.mean(signal[window_mask]))

    pre_mask = t < t_step
    if np.any(pre_mask):
        return float(signal[pre_mask][-1])
    return float(signal[0])


def _recovery_time_with_dwell(
    t_post: np.ndarray,
    error_post: np.ndarray,
    *,
    t_step: float,
    band: float,
    dwell_s: float,
) -> float:
    """Return first recovery time with a continuous in-band dwell interval."""
    for start_idx, start_time in enumerate(t_post):
        end_time = start_time + dwell_s
        end_idx = int(np.searchsorted(t_post, end_time, side="left"))
        if end_idx >= t_post.size:
            break
        if np.all(np.abs(error_post[start_idx : end_idx + 1]) <= band):
            return float(start_time - t_step)
    return float("nan")


def frequency_performance_metrics(
    t: np.ndarray | list[float],
    frequency_hz: np.ndarray | list[float],
    t_step: float,
    criteria: TuningCriteria = DEFAULT_TUNING_CRITERIA,
) -> dict[str, Any]:
    """Evaluate frequency drop and recovery after a disturbance.

    Maximum drop is measured from the mean pre-step frequency. Recovery is
    measured relative to the nominal frequency and requires the signal to stay
    inside the adopted band for the complete dwell interval.
    """
    time, frequency = _validated_trace(t, frequency_hz, value_name="frequency_hz")
    if not np.isfinite(t_step):
        raise ValueError("t_step must be finite.")

    post_mask = time >= t_step
    if not np.any(post_mask):
        raise ValueError("The trace must include at least one sample at or after t_step.")

    frequency_pre = _pre_step_mean(
        time,
        frequency,
        t_step,
        criteria.pre_step_window_s,
    )
    t_post = time[post_mask]
    frequency_post = frequency[post_mask]
    frequency_min = float(np.min(frequency_post))
    frequency_max = float(np.max(frequency_post))
    max_drop = max(frequency_pre - frequency_min, 0.0)
    max_rise = max(frequency_max - frequency_pre, 0.0)
    max_abs_deviation = float(
        np.max(np.abs(frequency_post - criteria.nominal_frequency_hz))
    )

    recovery_time = _recovery_time_with_dwell(
        t_post,
        frequency_post - criteria.nominal_frequency_hz,
        t_step=t_step,
        band=criteria.frequency_recovery_band_hz,
        dwell_s=criteria.frequency_recovery_dwell_s,
    )
    drop_pass = bool(max_drop <= criteria.max_frequency_drop_hz)
    recovery_pass = bool(
        np.isfinite(recovery_time)
        and recovery_time <= criteria.max_frequency_recovery_s
    )

    return {
        "frequency_pre_step_hz": frequency_pre,
        "frequency_min_post_step_hz": frequency_min,
        "frequency_max_post_step_hz": frequency_max,
        "max_frequency_drop_hz": float(max_drop),
        "max_frequency_rise_hz": float(max_rise),
        "max_frequency_abs_deviation_hz": max_abs_deviation,
        "frequency_recovery_time_s": recovery_time,
        "frequency_drop_pass": drop_pass,
        "frequency_recovery_pass": recovery_pass,
        "frequency_criteria_pass": bool(drop_pass and recovery_pass),
    }


def dc_link_performance_metrics(
    t: np.ndarray | list[float],
    vdc_v: np.ndarray | list[float],
    t_step: float,
    criteria: TuningCriteria = DEFAULT_TUNING_CRITERIA,
) -> dict[str, Any]:
    """Evaluate positive DC-link overshoot and minimum-voltage feasibility."""
    time, vdc = _validated_trace(t, vdc_v, value_name="vdc_v")
    if not np.isfinite(t_step):
        raise ValueError("t_step must be finite.")

    post_mask = time >= t_step
    if not np.any(post_mask):
        raise ValueError("The trace must include at least one sample at or after t_step.")

    vdc_post = vdc[post_mask]
    vdc_max = float(np.max(vdc_post))
    vdc_min = float(np.min(vdc_post))
    overshoot_v = max(vdc_max - criteria.vdc_reference_v, 0.0)
    undershoot_v = max(criteria.vdc_reference_v - vdc_min, 0.0)
    overshoot_pct = 100.0 * overshoot_v / criteria.vdc_reference_v
    undershoot_pct = 100.0 * undershoot_v / criteria.vdc_reference_v
    min_required = criteria.vdc_min_required_v
    overshoot_pass = bool(overshoot_pct <= criteria.max_vdc_overshoot_pct)
    minimum_voltage_pass = bool(vdc_min >= min_required)

    return {
        "vdc_max_post_step_v": vdc_max,
        "vdc_min_post_step_v": vdc_min,
        "vdc_overshoot_v": float(overshoot_v),
        "vdc_overshoot_pct": float(overshoot_pct),
        "vdc_undershoot_v": float(undershoot_v),
        "vdc_undershoot_pct": float(undershoot_pct),
        "vdc_min_required_v": float(min_required),
        "vdc_min_margin_v": float(vdc_min - min_required),
        "vdc_overshoot_pass": overshoot_pass,
        "vdc_minimum_voltage_pass": minimum_voltage_pass,
        "vdc_criteria_pass": bool(overshoot_pass and minimum_voltage_pass),
    }


def bess_stress_metrics(
    t: np.ndarray | list[float],
    i_bess_a: np.ndarray | list[float],
    p_bess_w: np.ndarray | list[float],
    t_step: float,
    soc: np.ndarray | list[float] | None = None,
) -> dict[str, float]:
    """Record BESS electrical stress without imposing unverified limits.

    These diagnostics are required when comparing admissible controllers for a
    second-life battery. Lower frequency error must not be rewarded at the cost
    of excessive current, power, energy throughput or SoC excursion.
    """
    time, current = _validated_trace(t, i_bess_a, value_name="i_bess_a")
    time_power, power = _validated_trace(t, p_bess_w, value_name="p_bess_w")
    if not np.array_equal(time, time_power):
        raise ValueError("Current and power traces must use the same time vector.")

    post_mask = time >= t_step
    if not np.any(post_mask):
        raise ValueError("The trace must include at least one sample at or after t_step.")

    t_post = time[post_mask]
    i_post = current[post_mask]
    p_post = power[post_mask]
    result = {
        "i_bess_peak_abs_a": float(np.max(np.abs(i_post))),
        "i_bess_rms_a": float(np.sqrt(np.mean(np.square(i_post)))),
        "i_bess_max_discharge_a": float(np.max(i_post)),
        "i_bess_max_charge_a": float(np.min(i_post)),
        "p_bess_peak_abs_w": float(np.max(np.abs(p_post))),
        "p_bess_max_discharge_w": float(np.max(p_post)),
        "p_bess_max_charge_w": float(np.min(p_post)),
        "bess_energy_throughput_wh": float(np.trapezoid(np.abs(p_post), t_post) / 3600.0),
    }

    if soc is not None:
        _, soc_trace = _validated_trace(time, soc, value_name="soc")
        soc_post = soc_trace[post_mask]
        result.update(
            {
                "soc_min": float(np.min(soc_post)),
                "soc_max": float(np.max(soc_post)),
                "soc_swing": float(np.max(soc_post) - np.min(soc_post)),
            }
        )
    return result
