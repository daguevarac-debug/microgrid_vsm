"""Validate the complete GFM microgrid in four combined scenarios.

The validation executes:

1. ``steady_operation``: nominal constant load without BESS;
2. ``load_step_20``: 20% load increase without BESS;
3. ``load_step_40``: 40% load increase without BESS;
4. ``bess_vs_no_bess``: the 20% step with and without the BESS PI.

Every simulated model uses ``GFMController`` at the selected operating point
``(M, D) = (80, 1500)``. The BESS case reuses the accepted DC-link PI model and
gains already consolidated in the repository. The no-BESS result from the 20%
step is reused by the comparison, so the four reported scenarios require four
ODE integrations rather than five.

A scenario is marked ``FAIL`` only when execution, state integrity, controller
selection, PI activation, or BESS physical-limit checks fail. A numerically
valid scenario is marked ``REVIEW`` when the existing frequency or DC-link
design criteria are not met. This preserves the known severe-case evidence
without misclassifying a successful simulation as a software failure.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

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
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.gfm_controller import GFMController
from microgrid import Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from tuning_metrics import (
    DEFAULT_TUNING_CRITERIA,
    bess_stress_metrics,
    dc_link_performance_metrics,
    frequency_performance_metrics,
)
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)
from validation.validate_dc_link_pi_scenarios import (
    BASE_SCENARIO as ACCEPTED_BESS_PI_BASE_SCENARIO,
    build_model as build_accepted_bess_pi_model,
)


T_END_S_DEFAULT = 6.5
OUTPUT_PATH_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_integrated_system"
    / "gfm_integrated_system_summary.json"
)
GROWTH_LIMIT = 1.2
LIMIT_ATOL = 1e-8


@dataclass(frozen=True)
class ScenarioSpec:
    """Configuration for one integrated GFM simulation."""

    name: str
    step_fraction: float
    with_bess_pi: bool
    constant_load: bool = False

    @property
    def p_load_pre_w(self) -> float:
        return float(MICROGRID_LOAD_P_NOM_W_DEFAULT)

    @property
    def p_load_post_w(self) -> float:
        if self.constant_load:
            return self.p_load_pre_w
        return self.p_load_pre_w * (1.0 + float(self.step_fraction))

    @property
    def load_step_pct(self) -> float:
        return 100.0 * (self.p_load_post_w - self.p_load_pre_w) / self.p_load_pre_w


STEADY_SPEC = ScenarioSpec(
    name="steady_operation",
    step_fraction=0.0,
    with_bess_pi=False,
    constant_load=True,
)
STEP_20_SPEC = ScenarioSpec(
    name="load_step_20",
    step_fraction=MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    with_bess_pi=False,
)
STEP_40_SPEC = ScenarioSpec(
    name="load_step_40",
    step_fraction=MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    with_bess_pi=False,
)
STEP_20_BESS_PI_SPEC = ScenarioSpec(
    name="load_step_20_with_bess_pi",
    step_fraction=MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    with_bess_pi=True,
)


def _reference_active_power_w() -> float:
    """Return the active-power reference used by the selected GFM studies."""
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def _build_gfm_controller(p_ref_w: float) -> GFMController:
    """Build the selected classical GFM controller explicitly."""
    return GFMController(
        p_ref=p_ref_w,
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )


def _assert_selected_gfm(model: Microgrid, scenario_name: str) -> None:
    """Reject any model that is not using the selected GFM point."""
    if not isinstance(model.controller, GFMController):
        raise TypeError(
            f"{scenario_name}: expected GFMController, got "
            f"{type(model.controller).__name__}."
        )
    if model.controller_state_name != "omega":
        raise ValueError(
            f"{scenario_name}: expected controller state 'omega', got "
            f"{model.controller_state_name!r}."
        )

    dynamics = model.controller.frequency_dynamics
    if not np.isclose(dynamics.inertia_m, GFM_SELECTED_M):
        raise ValueError(
            f"{scenario_name}: expected M={GFM_SELECTED_M}, got "
            f"{dynamics.inertia_m}."
        )
    if not np.isclose(dynamics.damping_d, GFM_SELECTED_D):
        raise ValueError(
            f"{scenario_name}: expected D={GFM_SELECTED_D}, got "
            f"{dynamics.damping_d}."
        )


def build_model(spec: ScenarioSpec, p_ref_w: float) -> Microgrid:
    """Build one scenario with the selected GFM and, when requested, BESS PI."""
    if spec.with_bess_pi:
        if not np.isclose(
            spec.step_fraction,
            MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
        ):
            raise ValueError("The accepted BESS PI comparison is defined for the 20% step.")
        model = build_accepted_bess_pi_model(ACCEPTED_BESS_PI_BASE_SCENARIO)
        if not isinstance(model, MicrogridWithBESSPI):
            raise TypeError(
                "Accepted BESS PI builder did not return MicrogridWithBESSPI."
            )
        if not model.bess_enabled:
            raise ValueError("The accepted BESS PI model must have the BESS enabled.")
    else:
        t_step = float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
        p_pre = spec.p_load_pre_w
        p_post = spec.p_load_post_w
        if spec.constant_load:
            load_profile = lambda _t: p_pre
        else:
            load_profile = lambda t: p_pre if t < t_step else p_post
        model = Microgrid(
            load_profile=load_profile,
            controller=_build_gfm_controller(p_ref_w),
        )

    _assert_selected_gfm(model, spec.name)
    if not np.isclose(model.controller.p_ref, p_ref_w):
        raise ValueError(
            f"{spec.name}: controller p_ref={model.controller.p_ref} does not "
            f"match expected p_ref={p_ref_w}."
        )
    return model


def _initial_state(model: Microgrid) -> list[float]:
    if isinstance(model, MicrogridWithBESSPI):
        return model.initial_state_with_bess(
            vdc0=SIM_VDC0_V_DEFAULT,
            xi_bess_vdc0_v_s=0.0,
        )
    return model.initial_state(vdc0=SIM_VDC0_V_DEFAULT)


def _growth_ratio(signal: np.ndarray, t: np.ndarray) -> float:
    """Compare RMS values in two adjacent windows near the simulation end."""
    t0 = float(t[0])
    tf = float(t[-1])
    duration = tf - t0
    mask_a = (t >= t0 + 0.70 * duration) & (t < t0 + 0.85 * duration)
    mask_b = (t >= t0 + 0.85 * duration) & (t <= tf)
    if not np.any(mask_a) or not np.any(mask_b):
        return float("nan")

    rms_a = float(np.sqrt(np.mean(np.square(signal[..., mask_a]))))
    rms_b = float(np.sqrt(np.mean(np.square(signal[..., mask_b]))))
    return rms_b / max(rms_a, 1e-12)


def _runtime_checks(model: Microgrid, solution) -> dict[str, Any]:
    states_finite = bool(np.all(np.isfinite(solution.y)))
    vdc = solution.y[0]
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    dynamics = model.controller.frequency_dynamics
    gfm_parameters_match = bool(
        np.isclose(dynamics.inertia_m, GFM_SELECTED_M)
        and np.isclose(dynamics.damping_d, GFM_SELECTED_D)
    )
    return {
        "solver_success": bool(solution.success),
        "solver_message": str(solution.message),
        "states_finite": states_finite,
        "vdc_positive": bool(states_finite and np.all(vdc > 0.0)),
        "frequency_finite": bool(np.all(np.isfinite(frequency_hz))),
        "gfm_controller_active": isinstance(model.controller, GFMController),
        "gfm_parameters_match": gfm_parameters_match,
        "controller_class": type(model.controller).__name__,
        "controller_state_name": model.controller_state_name,
        "state_count": int(solution.y.shape[0]),
        "n_time_points": int(solution.t.size),
        "nfev": int(solution.nfev),
    }


def _runtime_pass(checks: dict[str, Any]) -> bool:
    return bool(
        checks["solver_success"]
        and checks["states_finite"]
        and checks["vdc_positive"]
        and checks["frequency_finite"]
        and checks["gfm_controller_active"]
        and checks["gfm_parameters_match"]
        and checks["controller_state_name"] == "omega"
    )


def _classify_performance(runtime_pass: bool, criteria_pass: bool) -> str:
    if not runtime_pass:
        return "FAIL"
    return "PASS" if criteria_pass else "REVIEW"


def _step_metrics(solution) -> tuple[dict[str, Any], dict[str, Any]]:
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    frequency_metrics = frequency_performance_metrics(
        solution.t,
        frequency_hz,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    dc_metrics = dc_link_performance_metrics(
        solution.t,
        solution.y[0],
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    return frequency_metrics, dc_metrics


def _steady_metrics(solution) -> dict[str, Any]:
    criteria = DEFAULT_TUNING_CRITERIA
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    vdc = solution.y[0]
    i2 = solution.y[7:10]

    max_frequency_abs_deviation_hz = float(
        np.max(np.abs(frequency_hz - GRID_FREQ_HZ_DEFAULT))
    )
    vdc_min_v = float(np.min(vdc))
    growth_vdc = _growth_ratio(vdc, solution.t)
    growth_i2 = _growth_ratio(i2, solution.t)
    growth_frequency = _growth_ratio(frequency_hz, solution.t)

    finite_growth = bool(
        np.isfinite(growth_vdc)
        and np.isfinite(growth_i2)
        and np.isfinite(growth_frequency)
    )
    criteria_pass = bool(
        finite_growth
        and max_frequency_abs_deviation_hz <= criteria.max_frequency_drop_hz
        and vdc_min_v >= criteria.vdc_min_required_v
        and growth_vdc <= GROWTH_LIMIT
        and growth_i2 <= GROWTH_LIMIT
        and growth_frequency <= GROWTH_LIMIT
    )
    return {
        "frequency_final_hz": float(frequency_hz[-1]),
        "max_frequency_abs_deviation_hz": max_frequency_abs_deviation_hz,
        "vdc_min_v": vdc_min_v,
        "vdc_final_v": float(vdc[-1]),
        "vdc_min_required_v": float(criteria.vdc_min_required_v),
        "growth_ratio_vdc": growth_vdc,
        "growth_ratio_i2": growth_i2,
        "growth_ratio_frequency": growth_frequency,
        "steady_criteria_pass": criteria_pass,
    }


def _bess_pi_diagnostics(
    model: MicrogridWithBESSPI,
    solution,
) -> dict[str, Any]:
    """Collect PI, BESS stress, and mandatory physical-limit evidence."""
    n = solution.t.size
    i_bess = np.zeros(n, dtype=float)
    p_bess = np.zeros(n, dtype=float)
    p_ref = np.zeros(n, dtype=float)
    p_min = np.zeros(n, dtype=float)
    p_max = np.zeros(n, dtype=float)
    soc = np.zeros(n, dtype=float)
    soh = np.zeros(n, dtype=float)
    vt_bess = np.zeros(n, dtype=float)
    saturated = np.zeros(n, dtype=bool)
    anti_windup = np.zeros(n, dtype=bool)
    enabled = np.zeros(n, dtype=bool)

    for k, tk in enumerate(solution.t):
        signal = model.integrated_signals(float(tk), solution.y[:, k])
        i_bess[k] = float(signal["i_bess"])
        p_bess[k] = float(signal["p_bess_dc"])
        p_ref[k] = float(signal["p_bess_ref_w"])
        p_min[k] = float(signal["p_bess_ref_min_w"])
        p_max[k] = float(signal["p_bess_ref_max_w"])
        soc[k] = float(signal["soc_bess"])
        soh[k] = float(signal["soh_bess"])
        vt_bess[k] = float(signal["vt_bess"])
        saturated[k] = bool(signal["pi_saturated"])
        anti_windup[k] = bool(signal["anti_windup_active"])
        enabled[k] = bool(signal["bess_enabled"])

    stress = bess_stress_metrics(
        solution.t,
        i_bess,
        p_bess,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
        soc=soc,
    )
    signals_finite = bool(
        all(
            np.all(np.isfinite(values))
            for values in (
                i_bess,
                p_bess,
                p_ref,
                p_min,
                p_max,
                soc,
                soh,
                vt_bess,
            )
        )
    )
    current_limit = np.asarray(
        [model._available_i_bess_max(value) for value in soh],
        dtype=float,
    )
    current_limit_ok = bool(
        np.all(np.abs(i_bess) <= current_limit + LIMIT_ATOL)
    )
    power_limit_ok = bool(
        np.all(p_ref >= p_min - LIMIT_ATOL)
        and np.all(p_ref <= p_max + LIMIT_ATOL)
        and np.all(p_bess >= p_min - LIMIT_ATOL)
        and np.all(p_bess <= p_max + LIMIT_ATOL)
    )
    soc_range_ok = bool(
        np.all(soc >= model.bess.soc_min - LIMIT_ATOL)
        and np.all(soc <= model.bess.soc_max + LIMIT_ATOL)
    )
    soh_range_ok = bool(
        np.all(soh >= model.bess.soh_min - LIMIT_ATOL)
        and np.all(soh <= 1.0 + LIMIT_ATOL)
    )
    terminal_voltage_positive = bool(np.all(vt_bess > 0.0))
    pi_active = bool(model.bess_enabled and np.all(enabled))
    physical_limits_pass = bool(
        signals_finite
        and current_limit_ok
        and power_limit_ok
        and soc_range_ok
        and soh_range_ok
        and terminal_voltage_positive
        and pi_active
    )

    return {
        **stress,
        "pi_controller_class": type(model.dc_link_bess_pi).__name__,
        "pi_kp_w_per_v": float(model.dc_link_bess_pi.kp_w_per_v),
        "pi_ki_w_per_v_s": float(model.dc_link_bess_pi.ki_w_per_v_s),
        "pi_gains_match_accepted": bool(
            np.isclose(model.dc_link_bess_pi.kp_w_per_v, PI_KP_W_PER_V)
            and np.isclose(model.dc_link_bess_pi.ki_w_per_v_s, PI_KI_W_PER_V_S)
        ),
        "pi_active": pi_active,
        "pi_saturation_fraction": float(np.mean(saturated)),
        "anti_windup_fraction": float(np.mean(anti_windup)),
        "signals_finite": signals_finite,
        "soc_min": float(np.min(soc)),
        "soc_max": float(np.max(soc)),
        "soc_final": float(soc[-1]),
        "soc_range_ok": soc_range_ok,
        "soh_min": float(np.min(soh)),
        "soh_final": float(soh[-1]),
        "soh_range_ok": soh_range_ok,
        "vt_bess_min_v": float(np.min(vt_bess)),
        "vt_bess_final_v": float(vt_bess[-1]),
        "terminal_voltage_positive": terminal_voltage_positive,
        "i_bess_limit_max_a": float(np.max(current_limit)),
        "p_bess_ref_min_w": float(np.min(p_ref)),
        "p_bess_ref_max_w": float(np.max(p_ref)),
        "current_limit_ok": current_limit_ok,
        "power_limit_ok": power_limit_ok,
        "physical_limits_pass": physical_limits_pass,
    }


def run_scenario(
    spec: ScenarioSpec,
    *,
    p_ref_w: float,
    t_end_s: float,
) -> tuple[dict[str, Any], Any, Microgrid]:
    """Build, solve, and classify one explicit GFM scenario."""
    model = build_model(spec, p_ref_w)
    solution = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, float(t_end_s)),
        _initial_state(model),
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    runtime = _runtime_checks(model, solution)
    runtime_pass = _runtime_pass(runtime)

    record: dict[str, Any] = {
        "scenario": spec.name,
        "status": "FAIL",
        "M": float(GFM_SELECTED_M),
        "D": float(GFM_SELECTED_D),
        "p_ref_w": float(p_ref_w),
        "bess_active": bool(spec.with_bess_pi),
        "bess_pi_active": bool(spec.with_bess_pi),
        "t_start_s": float(SIM_T_START_S_DEFAULT),
        "t_end_s": float(t_end_s),
        "t_step_s": float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT),
        "p_load_pre_step_w": spec.p_load_pre_w,
        "p_load_post_step_w": spec.p_load_post_w,
        "load_step_pct": spec.load_step_pct,
        **runtime,
    }

    if spec.constant_load:
        steady = _steady_metrics(solution)
        record.update(steady)
        record["status"] = _classify_performance(
            runtime_pass,
            bool(steady["steady_criteria_pass"]),
        )
    else:
        frequency_metrics, dc_metrics = _step_metrics(solution)
        record.update(frequency_metrics)
        record.update(dc_metrics)
        criteria_pass = bool(
            frequency_metrics["frequency_criteria_pass"]
            and dc_metrics["vdc_criteria_pass"]
        )

        if isinstance(model, MicrogridWithBESSPI):
            bess_pi = _bess_pi_diagnostics(model, solution)
            record["bess_pi"] = bess_pi
            runtime_and_limits_pass = bool(
                runtime_pass
                and bess_pi["physical_limits_pass"]
                and bess_pi["pi_gains_match_accepted"]
            )
            record["status"] = _classify_performance(
                runtime_and_limits_pass,
                criteria_pass,
            )
        else:
            record["status"] = _classify_performance(runtime_pass, criteria_pass)

    return record, solution, model


def _comparison_record(
    no_bess: dict[str, Any],
    with_bess_pi: dict[str, Any],
) -> dict[str, Any]:
    """Create the fourth requested scenario from matched 20% simulations."""
    same_load_profile = bool(
        np.isclose(
            no_bess["p_load_pre_step_w"],
            with_bess_pi["p_load_pre_step_w"],
        )
        and np.isclose(
            no_bess["p_load_post_step_w"],
            with_bess_pi["p_load_post_step_w"],
        )
    )
    comparison_execution_pass = bool(
        no_bess["status"] != "FAIL"
        and with_bess_pi["status"] != "FAIL"
        and no_bess["gfm_controller_active"]
        and with_bess_pi["gfm_controller_active"]
        and with_bess_pi["bess_pi"]["pi_active"]
        and same_load_profile
    )
    comparison_performance_pass = bool(
        no_bess.get("frequency_criteria_pass", False)
        and no_bess.get("vdc_criteria_pass", False)
        and with_bess_pi.get("frequency_criteria_pass", False)
        and with_bess_pi.get("vdc_criteria_pass", False)
    )

    return {
        "scenario": "bess_vs_no_bess",
        "status": _classify_performance(
            comparison_execution_pass,
            comparison_performance_pass,
        ),
        "M": float(GFM_SELECTED_M),
        "D": float(GFM_SELECTED_D),
        "load_step_pct": float(no_bess["load_step_pct"]),
        "same_load_profile": same_load_profile,
        "both_gfm_active": bool(
            no_bess["gfm_controller_active"]
            and with_bess_pi["gfm_controller_active"]
        ),
        "bess_pi_active": bool(with_bess_pi["bess_pi"]["pi_active"]),
        "comparison_execution_pass": comparison_execution_pass,
        "comparison_performance_pass": comparison_performance_pass,
        "frequency_drop_change_hz_with_bess": float(
            with_bess_pi["max_frequency_drop_hz"]
            - no_bess["max_frequency_drop_hz"]
        ),
        "vdc_event_deviation_change_pct_with_bess": float(
            with_bess_pi["vdc_event_max_abs_deviation_pct"]
            - no_bess["vdc_event_max_abs_deviation_pct"]
        ),
        "bess_reduces_frequency_drop": bool(
            with_bess_pi["max_frequency_drop_hz"]
            <= no_bess["max_frequency_drop_hz"]
        ),
        "bess_reduces_vdc_event_deviation": bool(
            with_bess_pi["vdc_event_max_abs_deviation_pct"]
            <= no_bess["vdc_event_max_abs_deviation_pct"]
        ),
        "no_bess": no_bess,
        "with_bess_pi": with_bess_pi,
        "note": (
            "Dynamic improvement is reported as evidence; it is not imposed as "
            "an additional failure condition."
        ),
    }


def _overall_status(records: list[dict[str, Any]]) -> str:
    statuses = {str(record["status"]) for record in records}
    if "FAIL" in statuses:
        return "FAIL"
    if "REVIEW" in statuses:
        return "REVIEW"
    return "PASS"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def run_validation(
    *,
    output_path: Path = OUTPUT_PATH_DEFAULT,
    t_end_s: float = T_END_S_DEFAULT,
) -> dict[str, Any]:
    """Run the four requested scenarios and write one consolidated JSON report."""
    if not np.isfinite(t_end_s) or t_end_s <= MICROGRID_LOAD_STEP_TIME_S_DEFAULT:
        raise ValueError(
            "t_end_s must be finite and greater than the configured load-step time."
        )

    p_ref_w = _reference_active_power_w()
    steady, _, _ = run_scenario(
        STEADY_SPEC,
        p_ref_w=p_ref_w,
        t_end_s=t_end_s,
    )
    step_20, _, _ = run_scenario(
        STEP_20_SPEC,
        p_ref_w=p_ref_w,
        t_end_s=t_end_s,
    )
    step_40, _, _ = run_scenario(
        STEP_40_SPEC,
        p_ref_w=p_ref_w,
        t_end_s=t_end_s,
    )
    step_20_bess_pi, _, _ = run_scenario(
        STEP_20_BESS_PI_SPEC,
        p_ref_w=p_ref_w,
        t_end_s=t_end_s,
    )
    comparison = _comparison_record(step_20, step_20_bess_pi)

    scenarios = [steady, step_20, step_40, comparison]
    status = _overall_status(scenarios)
    all_controllers_gfm_active = bool(
        steady["gfm_controller_active"]
        and step_20["gfm_controller_active"]
        and step_40["gfm_controller_active"]
        and comparison["both_gfm_active"]
    )
    report: dict[str, Any] = {
        "task": "Validacion del sistema completo en escenarios combinados",
        "status": status,
        "scenario_count": 4,
        "simulation_count": 4,
        "all_controllers_gfm_active": all_controllers_gfm_active,
        "controller_class": "GFMController",
        "M": float(GFM_SELECTED_M),
        "D": float(GFM_SELECTED_D),
        "p_ref_w": p_ref_w,
        "bess_pi": {
            "controller_class": "DCLinkBESSPIController",
            "kp_w_per_v": float(PI_KP_W_PER_V),
            "ki_w_per_v_s": float(PI_KI_W_PER_V_S),
        },
        "t_end_s": float(t_end_s),
        "status_semantics": {
            "PASS": "simulation and existing design criteria pass",
            "REVIEW": "simulation is valid but at least one design criterion is not met",
            "FAIL": (
                "execution, state integrity, controller selection, PI activation, "
                "or BESS limits fail"
            ),
        },
        "scenarios": scenarios,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(output_path)
    clean_report = _json_ready(report)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(clean_report, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    for scenario in scenarios:
        print(f"scenario={scenario['scenario']}")
        print(f"status={scenario['status']}")
        if scenario["scenario"] == "bess_vs_no_bess":
            print(f"both_gfm_active={scenario['both_gfm_active']}")
            print(f"bess_pi_active={scenario['bess_pi_active']}")
        else:
            print(f"gfm_controller_active={scenario['gfm_controller_active']}")
    print(f"overall_status={status}")
    print(f"all_controllers_gfm_active={all_controllers_gfm_active}")
    print(f"output_path={output_path}")
    return clean_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH_DEFAULT)
    parser.add_argument("--t-end", type=float, default=T_END_S_DEFAULT)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 for REVIEW as well as FAIL.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_validation(output_path=args.output, t_end_s=args.t_end)
    if report["status"] == "FAIL":
        return 1
    if args.strict and report["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
