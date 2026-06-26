"""Multi-scenario tuning of classical VSG ``M`` and ``D`` for Objective 2.3.

This script evaluates the formal 3x3 refined domain by default. It combines
transient metrics, BESS operational limits and the periodic small-signal
analysis without changing controllers, physical equations, state order, config
defaults or IEEE 33 coupling.
"""

from __future__ import annotations

import argparse
import csv
import json
from itertools import product
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

import numpy as np
from scipy.integrate import solve_ivp


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    GRID_FREQ_HZ_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from tuning_metrics import dc_link_performance_metrics, frequency_performance_metrics
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)
from validation.validate_objective2_small_signal_stability import (
    analyze_point,
    run_validation as run_small_signal_validation,
)


OUTPUT_DIR_DEFAULT = (
    REPO_ROOT / "outputs" / "validation" / "objective2_vsg_tuning"
)
RESULTS_CSV_NAME = "tuning_results.csv"
SUMMARY_JSON_NAME = "tuning_summary.json"
M_VALUES_DEFAULT = (20.0, 50.0, 80.0)
D_VALUES_DEFAULT = (200.0, 850.0, 1500.0)
MAX_VALUES_PER_PARAMETER = 3
SCENARIO_WEIGHT = 0.25
HARD_FAILURE_PENALTY = 1000.0
DEFAULT_T_END_S = 2.0
DEFAULT_ROCOF_DT_S = 1e-3
DEFAULT_MAX_STEP_S = 5e-3
FINAL_WINDOW_S = 0.5
LIMIT_ATOL = 1e-8
IDENTITY_ATOL_W = 1e-8

NORMALIZATION_SCALES = {
    "frequency_deviation": 0.50,
    "rocof": 5.0,
    "frequency_recovery": 5.0,
    "steady_frequency_error": 0.10,
    "vdc_event_deviation": 5.0,
    "steady_vdc_error": 5.0,
    "bess_current_stress": 1.0,
    "bess_power_stress": 1.0,
    "soc_excursion": 1.0,
}
OBJECTIVE_WEIGHTS = {
    "frequency_deviation": 0.25,
    "rocof": 0.10,
    "frequency_recovery": 0.10,
    "steady_frequency_error": 0.10,
    "vdc_event_deviation": 0.20,
    "steady_vdc_error": 0.10,
    "bess_current_stress": 0.05,
    "bess_power_stress": 0.05,
    "soc_excursion": 0.05,
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unavailable"


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def limited_values(
    name: str,
    values: Iterable[float],
    *,
    strictly_positive: bool,
    max_values: int = MAX_VALUES_PER_PARAMETER,
) -> tuple[float, ...]:
    """Validate one tuning axis and enforce the formal three-value limit."""
    out: list[float] = []
    for raw in values:
        value = float(raw)
        if not np.isfinite(value):
            raise ValueError(f"{name} values must be finite.")
        if strictly_positive and value <= 0.0:
            raise ValueError(f"{name} values must be > 0.")
        if not strictly_positive and value < 0.0:
            raise ValueError(f"{name} values must be >= 0.")
        if value not in out:
            out.append(value)
    if not out:
        raise ValueError(f"At least one {name} value is required.")
    if len(out) > max_values:
        raise ValueError(f"{name} accepts at most {max_values} unique values.")
    return tuple(out)


def build_candidate_grid(
    m_values: Iterable[float] = M_VALUES_DEFAULT,
    d_values: Iterable[float] = D_VALUES_DEFAULT,
) -> list[dict[str, float | int]]:
    """Return deterministic Cartesian candidates."""
    m_axis = limited_values("M", m_values, strictly_positive=True)
    d_axis = limited_values("D", d_values, strictly_positive=False)
    return [
        {"candidate_id": index, "M": m, "D": d}
        for index, (m, d) in enumerate(product(m_axis, d_axis), start=1)
    ]


def max_abs_rocof(
    time_s: np.ndarray,
    frequency_hz: np.ndarray,
    *,
    dt_s: float = DEFAULT_ROCOF_DT_S,
) -> float:
    """Compute RoCoF after interpolation to a uniform time grid."""
    time = np.asarray(time_s, dtype=float)
    frequency = np.asarray(frequency_hz, dtype=float)
    if time.ndim != 1 or frequency.shape != time.shape or time.size < 2:
        raise ValueError("time and frequency must be one-dimensional traces.")
    if dt_s <= 0.0:
        raise ValueError("dt_s must be positive.")
    uniform_time = np.arange(float(time[0]), float(time[-1]) + 0.5 * dt_s, dt_s)
    uniform_frequency = np.interp(uniform_time, time, frequency)
    rocof = np.gradient(uniform_frequency, dt_s)
    return float(np.max(np.abs(rocof)))


def renormalized_weights(with_bess: bool) -> dict[str, float]:
    """Return objective weights, dropping BESS terms for no-BESS scenarios."""
    weights = dict(OBJECTIVE_WEIGHTS)
    if not with_bess:
        for key in ("bess_current_stress", "bess_power_stress", "soc_excursion"):
            weights[key] = 0.0
    total = sum(weights.values())
    return {key: value / total for key, value in weights.items()}


def normalized_terms(metrics: dict[str, float], *, with_bess: bool) -> dict[str, float]:
    """Normalize one scenario metric set for scoring."""
    recovery = metrics.get("frequency_recovery_time_s", float("nan"))
    if not np.isfinite(recovery):
        recovery = NORMALIZATION_SCALES["frequency_recovery"]
    terms = {
        "frequency_deviation": metrics["max_frequency_abs_deviation_hz"]
        / NORMALIZATION_SCALES["frequency_deviation"],
        "rocof": metrics["max_abs_rocof_hz_per_s"] / NORMALIZATION_SCALES["rocof"],
        "frequency_recovery": min(recovery, 5.0)
        / NORMALIZATION_SCALES["frequency_recovery"],
        "steady_frequency_error": abs(metrics["frequency_steady_state_error_hz"])
        / NORMALIZATION_SCALES["steady_frequency_error"],
        "vdc_event_deviation": metrics["vdc_event_max_abs_deviation_pct"]
        / NORMALIZATION_SCALES["vdc_event_deviation"],
        "steady_vdc_error": abs(metrics["vdc_steady_state_error_pct"])
        / NORMALIZATION_SCALES["steady_vdc_error"],
        "bess_current_stress": metrics["current_utilization"],
        "bess_power_stress": metrics["power_utilization"],
        "soc_excursion": abs(metrics["delta_soc"])
        / max(metrics.get("soc_range", 1.0), 1e-12),
    }
    if not with_bess:
        terms["bess_current_stress"] = 0.0
        terms["bess_power_stress"] = 0.0
        terms["soc_excursion"] = 0.0
    return terms


def scenario_score(metrics: dict[str, float], *, with_bess: bool) -> float:
    terms = normalized_terms(metrics, with_bess=with_bess)
    weights = renormalized_weights(with_bess)
    return float(sum(weights[key] * terms[key] for key in weights))


def aggregate_score(
    scenario_scores: Iterable[float],
    *,
    hard_constraints_pass: bool,
) -> float:
    base = float(sum(SCENARIO_WEIGHT * score for score in scenario_scores))
    if not hard_constraints_pass:
        base += HARD_FAILURE_PENALTY
    return base


def _gfm_controller(m_value: float, d_value: float) -> GFMController:
    return GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=m_value,
        damping_d=d_value,
    )


def _build_model(scenario: str, m_value: float, d_value: float) -> tuple[Microgrid, bool]:
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    t_step = float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
    if scenario == "load_step_20_no_bess":
        p_post = p_pre * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
        return Microgrid(
            controller=_gfm_controller(m_value, d_value),
            load_profile=lambda t: p_pre if t < t_step else p_post,
        ), False
    if scenario == "load_step_40_no_bess":
        p_post = p_pre * (1.0 + MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT)
        return Microgrid(
            controller=_gfm_controller(m_value, d_value),
            load_profile=lambda t: p_pre if t < t_step else p_post,
        ), False
    if scenario == "load_step_20_bess_pi_nominal_soh":
        p_post = p_pre * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
        return MicrogridWithBESSPI(
            controller=_gfm_controller(m_value, d_value),
            dc_link_bess_pi=DCLinkBESSPIController(
                vdc_ref_v=SIM_VDC0_V_DEFAULT,
                kp_w_per_v=PI_KP_W_PER_V,
                ki_w_per_v_s=PI_KI_W_PER_V_S,
            ),
            bess_enabled=True,
            load_profile=lambda t: p_pre if t < t_step else p_post,
        ), True
    if scenario == "irradiance_drop_20_bess_pi":
        return MicrogridWithBESSPI(
            controller=_gfm_controller(m_value, d_value),
            dc_link_bess_pi=DCLinkBESSPIController(
                vdc_ref_v=SIM_VDC0_V_DEFAULT,
                kp_w_per_v=PI_KP_W_PER_V,
                ki_w_per_v_s=PI_KI_W_PER_V_S,
            ),
            bess_enabled=True,
            load_profile=lambda _t: p_pre,
            irradiance_profile=lambda t: 1000.0 if t < t_step else 800.0,
            temperature_profile=lambda _t: MICROGRID_TEMPERATURE_C_DEFAULT,
        ), True
    raise ValueError(f"Unknown scenario: {scenario}")


SCENARIOS = (
    "load_step_20_no_bess",
    "load_step_40_no_bess",
    "load_step_20_bess_pi_nominal_soh",
    "irradiance_drop_20_bess_pi",
)


def _initial_state(model: Microgrid):
    if isinstance(model, MicrogridWithBESSPI):
        return model.initial_state_with_bess(
            vdc0=SIM_VDC0_V_DEFAULT,
            xi_bess_vdc0_v_s=0.0,
        )
    return model.initial_state(vdc0=SIM_VDC0_V_DEFAULT)


def _final_mean(time: np.ndarray, values: np.ndarray, window_s: float = FINAL_WINDOW_S) -> float:
    mask = time >= max(float(time[-1]) - window_s, float(time[0]))
    return float(np.mean(values[mask]))


def _bess_signals(model: MicrogridWithBESSPI, sol) -> dict[str, np.ndarray]:
    keys = (
        "i_bess",
        "p_bess_dc",
        "p_bess_ref_min_w",
        "p_bess_ref_max_w",
        "soc_bess",
        "soh_bess",
        "i_bess_max_available",
        "p_bess_dc_max_available",
    )
    signals = {key: np.zeros(sol.t.size, dtype=float) for key in keys}
    for idx, tk in enumerate(sol.t):
        sample = model.integrated_signals(float(tk), sol.y[:, idx])
        for key in keys:
            signals[key][idx] = float(sample[key])
    return signals


def evaluate_scenario(
    candidate_id: int,
    scenario: str,
    m_value: float,
    d_value: float,
    *,
    t_end_s: float,
    rocof_dt_s: float,
    max_step_s: float,
) -> dict[str, Any]:
    model, with_bess = _build_model(scenario, m_value, d_value)
    y0 = _initial_state(model)
    sol = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, float(t_end_s)),
        y0,
        max_step=max_step_s,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    states_finite = bool(np.all(np.isfinite(sol.t)) and np.all(np.isfinite(sol.y)))
    frequency_hz = sol.y[10] / (2.0 * np.pi) if states_finite else np.array([np.nan])
    vdc = sol.y[0] if states_finite else np.array([np.nan])
    frequency_metrics = (
        frequency_performance_metrics(sol.t, frequency_hz, MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
        if sol.success and states_finite
        else {}
    )
    dc_metrics = (
        dc_link_performance_metrics(sol.t, vdc, MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
        if sol.success and states_finite
        else {}
    )
    max_rocof = max_abs_rocof(sol.t, frequency_hz, dt_s=rocof_dt_s) if sol.success and states_finite else float("nan")
    freq_ss_error = _final_mean(sol.t, frequency_hz) - GRID_FREQ_HZ_DEFAULT if sol.success and states_finite else float("nan")
    vdc_pre = float(dc_metrics.get("vdc_pre_step_v", np.nan))
    vdc_ss_error_pct = (
        100.0 * (_final_mean(sol.t, vdc) - vdc_pre) / max(abs(vdc_pre), 1e-12)
        if sol.success and states_finite
        else float("nan")
    )

    i_peak = i_rms = p_peak = energy_wh = delta_soc = 0.0
    current_util = power_util = 0.0
    identity_residual = 0.0
    soc_violation = soh_violation = current_violation = power_violation = False
    if with_bess and sol.success and states_finite:
        bess = _bess_signals(model, sol)  # type: ignore[arg-type]
        i_bess = bess["i_bess"]
        p_bess = bess["p_bess_dc"]
        soc = bess["soc_bess"]
        soh = bess["soh_bess"]
        i_limit = bess["i_bess_max_available"]
        p_max = np.maximum(np.abs(bess["p_bess_ref_min_w"]), np.abs(bess["p_bess_ref_max_w"]))
        p_available = np.maximum(bess["p_bess_dc_max_available"], p_max)
        i_peak = float(np.max(np.abs(i_bess)))
        i_rms = float(np.sqrt(np.mean(np.square(i_bess))))
        p_peak = float(np.max(np.abs(p_bess)))
        energy_wh = float(np.trapezoid(np.abs(p_bess), sol.t) / 3600.0)
        delta_soc = float(np.max(soc) - np.min(soc))
        current_util = float(np.max(np.abs(i_bess) / np.maximum(i_limit, 1e-12)))
        power_util = float(np.max(np.abs(p_bess) / np.maximum(p_available, 1e-12)))
        identity_residual = float(np.max(np.abs(p_bess - vdc * i_bess)))
        soc_violation = bool(
            np.any(soc < model.bess.soc_min - LIMIT_ATOL)
            or np.any(soc > model.bess.soc_max + LIMIT_ATOL)
        )
        soh_violation = bool(
            np.any(soh < model.bess.soh_min - LIMIT_ATOL)
            or np.any(soh > 1.0 + LIMIT_ATOL)
        )
        current_violation = bool(np.any(np.abs(i_bess) > i_limit + LIMIT_ATOL))
        power_violation = bool(np.any(np.abs(p_bess) > p_available + LIMIT_ATOL))

    frequency_pass = bool(frequency_metrics.get("frequency_criteria_pass", False))
    vdc_min_pass = bool(dc_metrics.get("vdc_minimum_voltage_pass", False))
    severe_energy_review = bool(
        scenario == "load_step_40_no_bess"
        and sol.success
        and states_finite
        and frequency_pass
        and float(dc_metrics.get("vdc_event_max_abs_deviation_pct", 0.0)) > 5.0
    )
    physical_identity_ok = bool(identity_residual <= IDENTITY_ATOL_W)
    common_constraints_pass = bool(
        sol.success
        and states_finite
        and model.controller_state_name == "omega"
        and physical_identity_ok
        and not soc_violation
        and not soh_violation
        and not current_violation
        and not power_violation
        and frequency_pass
    )
    hard_constraints_pass = bool(
        common_constraints_pass
        and vdc_min_pass
    )
    if severe_energy_review and common_constraints_pass:
        hard_constraints_pass = True
    status = "PASS"
    if not hard_constraints_pass:
        status = "FAIL"
    elif severe_energy_review:
        status = "REVIEW_SEVERE_ENERGY_DEFICIT"

    metrics_for_score = {
        "max_frequency_abs_deviation_hz": float(frequency_metrics.get("max_frequency_abs_deviation_hz", np.nan)),
        "max_abs_rocof_hz_per_s": max_rocof,
        "frequency_recovery_time_s": float(frequency_metrics.get("frequency_recovery_time_s", np.nan)),
        "frequency_steady_state_error_hz": float(freq_ss_error),
        "vdc_event_max_abs_deviation_pct": float(dc_metrics.get("vdc_event_max_abs_deviation_pct", np.nan)),
        "vdc_steady_state_error_pct": float(vdc_ss_error_pct),
        "current_utilization": current_util,
        "power_utilization": power_util,
        "delta_soc": delta_soc,
        "soc_range": (
            float(model.bess.soc_max - model.bess.soc_min)
            if with_bess and isinstance(model, MicrogridWithBESSPI)
            else 1.0
        ),
    }
    score = scenario_score(metrics_for_score, with_bess=with_bess)
    if not hard_constraints_pass:
        score += HARD_FAILURE_PENALTY

    return {
        "candidate_id": candidate_id,
        "scenario": scenario,
        "M": float(m_value),
        "D": float(d_value),
        "solver_success": bool(sol.success),
        "states_finite": states_finite,
        "max_frequency_abs_deviation_hz": metrics_for_score["max_frequency_abs_deviation_hz"],
        "max_frequency_drop_hz": float(frequency_metrics.get("max_frequency_drop_hz", np.nan)),
        "max_abs_rocof_hz_per_s": max_rocof,
        "frequency_recovery_time_s": metrics_for_score["frequency_recovery_time_s"],
        "frequency_steady_state_error_hz": metrics_for_score["frequency_steady_state_error_hz"],
        "vdc_event_max_abs_deviation_pct": metrics_for_score["vdc_event_max_abs_deviation_pct"],
        "vdc_min_post_step_v": float(dc_metrics.get("vdc_min_post_step_v", np.nan)),
        "vdc_steady_state_error_pct": vdc_ss_error_pct,
        "i_bess_peak_abs_a": i_peak,
        "i_bess_rms_a": i_rms,
        "p_bess_peak_abs_w": p_peak,
        "energy_throughput_wh": energy_wh,
        "delta_soc": delta_soc,
        "current_utilization": current_util,
        "power_utilization": power_util,
        "power_identity_residual_w": identity_residual,
        "hard_constraints_pass": hard_constraints_pass,
        "scenario_status": status,
        "scenario_score": score,
        "with_bess": with_bess,
        "frequency_criteria_pass": frequency_pass,
        "vdc_minimum_voltage_pass": vdc_min_pass,
        "severe_energy_review": severe_energy_review,
    }


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (
            not item["hard_constraints_pass_all"],
            not item.get("small_signal_accepted", False),
            item["aggregate_score"],
            item["M"],
            item["D"],
        ),
    )


def stability_accepts(report: dict[str, Any]) -> tuple[bool, str]:
    formal = report["architectures"]["gfm_12_state_no_bess"]
    if formal["unstable_modes"]:
        return False, "relevant unstable mode"
    zeta_min = formal["zeta_min"]
    if zeta_min is None or zeta_min <= 0.10:
        return False, "zeta_min <= 0.10 or unavailable"
    return True, "stable formal modes with zeta_min > 0.10"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def run_tuning(
    *,
    output_dir: Path = OUTPUT_DIR_DEFAULT,
    write: bool = True,
    m_values: Iterable[float] = M_VALUES_DEFAULT,
    d_values: Iterable[float] = D_VALUES_DEFAULT,
    t_end_s: float = DEFAULT_T_END_S,
    rocof_dt_s: float = DEFAULT_ROCOF_DT_S,
    max_step_s: float = DEFAULT_MAX_STEP_S,
) -> dict[str, Any]:
    if max_step_s <= 0.0:
        raise ValueError("max_step_s must be positive.")
    candidates = build_candidate_grid(m_values, d_values)
    rows: list[dict[str, Any]] = []
    candidate_summaries: list[dict[str, Any]] = []

    for candidate in candidates:
        scenario_rows = [
            evaluate_scenario(
                int(candidate["candidate_id"]),
                scenario,
                float(candidate["M"]),
                float(candidate["D"]),
                t_end_s=t_end_s,
                rocof_dt_s=rocof_dt_s,
                max_step_s=max_step_s,
            )
            for scenario in SCENARIOS
        ]
        rows.extend(scenario_rows)
        hard_all = bool(all(row["hard_constraints_pass"] for row in scenario_rows))
        aggregate = aggregate_score(
            [float(row["scenario_score"]) for row in scenario_rows],
            hard_constraints_pass=hard_all,
        )
        candidate_summaries.append(
            {
                **candidate,
                "hard_constraints_pass_all": hard_all,
                "aggregate_score": aggregate,
                "scenario_scores": {
                    row["scenario"]: row["scenario_score"] for row in scenario_rows
                },
                "scenario_statuses": {
                    row["scenario"]: row["scenario_status"] for row in scenario_rows
                },
                "small_signal_checked": False,
                "small_signal_accepted": False,
                "small_signal_rejection_reason": "not evaluated",
            }
        )

    transient_ranking = sorted(
        candidate_summaries,
        key=lambda item: (
            not item["hard_constraints_pass_all"],
            item["aggregate_score"],
            item["M"],
            item["D"],
        ),
    )

    selected: dict[str, Any] | None = None
    analyzed: list[dict[str, Any]] = []
    for candidate in transient_ranking:
        if not candidate["hard_constraints_pass_all"]:
            candidate["small_signal_rejection_reason"] = "hard constraints failed"
            continue
        stability_report = analyze_point(
            float(candidate["M"]),
            float(candidate["D"]),
            formal_only=True,
        )
        accepted, reason = stability_accepts(stability_report)
        formal = stability_report["architectures"]["gfm_12_state_no_bess"]
        candidate.update(
            {
                "small_signal_checked": True,
                "small_signal_status": stability_report["status"],
                "small_signal_accepted": accepted,
                "small_signal_rejection_reason": reason if not accepted else "",
                "zeta_min": formal["zeta_min"],
                "zeta_min_mode": formal["zeta_min_mode"],
                "unstable_modes": formal["unstable_modes"],
            }
        )
        analyzed.append(candidate)
        if accepted:
            selected = candidate
            break

    if selected is None:
        global_status = "FAIL"
        selected = transient_ranking[0]
    else:
        has_review = any(
            "REVIEW" in status
            for candidate in candidate_summaries
            for status in candidate["scenario_statuses"].values()
        )
        global_status = "REVIEW" if has_review else "PASS"

    output_dir = Path(output_dir)
    if write and selected is not None:
        run_small_signal_validation(
            output_dir=output_dir,
            write=True,
            inertia_m=float(selected["M"]),
            damping_d=float(selected["D"]),
            formal_only=False,
        )

    for index, candidate in enumerate(rank_candidates(candidate_summaries), start=1):
        candidate["rank"] = index

    previous = next(
        item
        for item in candidate_summaries
        if float(item["M"]) == GFM_SELECTED_M and float(item["D"]) == GFM_SELECTED_D
    )
    comparison = {
        "previous_M": GFM_SELECTED_M,
        "previous_D": GFM_SELECTED_D,
        "selected_M": selected["M"],
        "selected_D": selected["D"],
        "aggregate_score_previous": previous["aggregate_score"],
        "aggregate_score_selected": selected["aggregate_score"],
        "aggregate_score_delta_selected_minus_previous": (
            selected["aggregate_score"] - previous["aggregate_score"]
        ),
    }
    summary = {
        "model_commit": _git_commit(),
        "status": global_status,
        "domain": {"M": list(limited_values("M", m_values, strictly_positive=True)), "D": list(limited_values("D", d_values, strictly_positive=False))},
        "scenarios": list(SCENARIOS),
        "normalization_scales": NORMALIZATION_SCALES,
        "weights": OBJECTIVE_WEIGHTS,
        "scenario_weight": SCENARIO_WEIGHT,
        "hard_failure_penalty": HARD_FAILURE_PENALTY,
        "tolerances": {
            "limit_atol": LIMIT_ATOL,
            "identity_atol_w": IDENTITY_ATOL_W,
            "solver_rtol": SIM_SOLVER_RTOL_DEFAULT,
            "solver_atol": SIM_SOLVER_ATOL_DEFAULT,
            "config_solver_max_step_s": SIM_SOLVER_MAX_STEP_S_DEFAULT,
            "tuning_solver_max_step_s": max_step_s,
            "rocof_dt_s": rocof_dt_s,
        },
        "candidates": candidate_summaries,
        "ranking": rank_candidates(candidate_summaries),
        "rejected_candidates": [
            item for item in candidate_summaries if not item.get("small_signal_accepted", False)
        ],
        "small_signal_analyzed_candidates": analyzed,
        "previous_point": {"M": GFM_SELECTED_M, "D": GFM_SELECTED_D},
        "selected_point": selected,
        "comparison_selected_vs_previous": comparison,
        "zeta_min": selected.get("zeta_min"),
        "zeta_min_mode": selected.get("zeta_min_mode"),
        "stability_status": selected.get("small_signal_status"),
        "limitations": [
            "No global optimum is claimed.",
            "The severe no-BESS scenario may retain the documented DC energy deficit.",
            "Objective weights are design scales, not universal standards.",
        ],
        "no_global_optimum_claimed": True,
    }
    clean = _json_ready(summary)

    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / RESULTS_CSV_NAME).open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=[
                "candidate_id", "scenario", "M", "D", "solver_success", "states_finite",
                "max_frequency_abs_deviation_hz", "max_frequency_drop_hz",
                "max_abs_rocof_hz_per_s", "frequency_recovery_time_s",
                "frequency_steady_state_error_hz", "vdc_event_max_abs_deviation_pct",
                "vdc_min_post_step_v", "vdc_steady_state_error_pct",
                "i_bess_peak_abs_a", "i_bess_rms_a", "p_bess_peak_abs_w",
                "energy_throughput_wh", "delta_soc", "current_utilization",
                "power_utilization", "power_identity_residual_w",
                "hard_constraints_pass", "scenario_status", "scenario_score",
            ], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        with (output_dir / SUMMARY_JSON_NAME).open("w", encoding="utf-8") as json_file:
            json.dump(clean, json_file, indent=2, sort_keys=True)
            json_file.write("\n")

    print(f"candidates_evaluated={len(candidates)}")
    print(f"scenarios_executed={len(SCENARIOS)}")
    print(f"selected_M={selected['M']}")
    print(f"selected_D={selected['D']}")
    print(f"global_status={global_status}")
    if write:
        print(f"tuning_results={output_dir / RESULTS_CSV_NAME}")
        print(f"tuning_summary={output_dir / SUMMARY_JSON_NAME}")
    else:
        print("no_write=True")
    return clean


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--m-values", nargs="+", type=float, default=list(M_VALUES_DEFAULT))
    parser.add_argument("--d-values", nargs="+", type=float, default=list(D_VALUES_DEFAULT))
    parser.add_argument("--t-end", type=float, default=DEFAULT_T_END_S)
    parser.add_argument("--rocof-dt", type=float, default=DEFAULT_ROCOF_DT_S)
    parser.add_argument("--max-step", type=float, default=DEFAULT_MAX_STEP_S)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_tuning(
        output_dir=args.output_dir,
        write=not args.no_write,
        m_values=args.m_values,
        d_values=args.d_values,
        t_end_s=args.t_end,
        rocof_dt_s=args.rocof_dt,
        max_step_s=args.max_step,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
