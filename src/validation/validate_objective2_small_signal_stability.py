"""Periodic small-signal stability analysis for the selected classical VSG.

The formal analysis uses the one-period map of the 12-state GFM model, not an
instantaneous RHS Jacobian. A 16-state GFM+BESS+PI case is also evaluated as a
diagnostic because slow battery and PI states can prevent a true periodic orbit.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

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
    MICROGRID_TEMPERATURE_C_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
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
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)


OUTPUT_DIR_DEFAULT = (
    REPO_ROOT / "outputs" / "validation" / "objective2_vsg_tuning"
)
EIGENVALUES_CSV_NAME = "eigenvalues.csv"
SUMMARY_JSON_NAME = "small_signal_summary.json"
ALPHA_NOT_APPLICABLE = "no aplicable"

STATE_NAMES_12 = (
    "Vdc",
    "i1_a",
    "i1_b",
    "i1_c",
    "vc_a",
    "vc_b",
    "vc_c",
    "i2_a",
    "i2_b",
    "i2_c",
    "omega",
    "theta",
)
STATE_NAMES_16 = STATE_NAMES_12 + (
    "soc_bess",
    "vrc_bess",
    "zdeg_bess",
    "xi_bess_vdc",
)
ANGLE_INDEX = 11
NEUTRAL_TOL = 5e-3
UNIT_CIRCLE_TOL = 5e-3
REAL_LAMBDA_TOL = 1e-5
PERIODIC_RESIDUAL_TOL = 5e-3
ABC_RESIDUAL_TOL = 5e-3
OMEGA_REL_TOL = 5e-5
THETA_RESIDUAL_TOL_RAD = 5e-3
SENSITIVITY_MU_TOL = 5e-3
SENSITIVITY_LAMBDA_TOL = 1.0
OSC_FREQ_TOL_HZ = 1e-3
ZETA_MIN_REQUIRED = 0.10


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


def build_state_scales(state_count: int) -> np.ndarray:
    """Return reproducible physical perturbation scales for each state."""
    if state_count not in (12, 16):
        raise ValueError("state_count must be 12 or 16.")
    scales = [
        SIM_VDC0_V_DEFAULT,
        20.0,
        20.0,
        20.0,
        250.0,
        250.0,
        250.0,
        20.0,
        20.0,
        20.0,
        2.0 * np.pi * GRID_FREQ_HZ_DEFAULT,
        1.0,
    ]
    if state_count == 16:
        scales.extend([1.0, 5.0, 1.0, 10.0])
    return np.asarray(scales, dtype=float)


def _state_names(state_count: int) -> tuple[str, ...]:
    if state_count == 12:
        return STATE_NAMES_12
    if state_count == 16:
        return STATE_NAMES_16
    raise ValueError("Unsupported state_count.")


def mu_to_lambda(mu: complex, period_s: float) -> complex:
    """Convert a Floquet multiplier to a continuous-time exponent."""
    return np.log(complex(mu)) / float(period_s)


def modal_values(mu: complex, period_s: float) -> dict[str, float | None]:
    lamb = mu_to_lambda(mu, period_s)
    natural_frequency = abs(lamb)
    modal_frequency_hz = abs(lamb.imag) / (2.0 * np.pi)
    if modal_frequency_hz > OSC_FREQ_TOL_HZ and natural_frequency > 0.0:
        zeta = -float(lamb.real) / float(natural_frequency)
    else:
        zeta = None
    return {
        "lambda_real": float(lamb.real),
        "lambda_imag": float(lamb.imag),
        "natural_frequency_rad_s": float(natural_frequency),
        "modal_frequency_hz": float(modal_frequency_hz),
        "zeta": zeta,
    }


def _integrate_map(
    rhs: Callable[[float, np.ndarray], list[float]],
    x0: np.ndarray,
    period_s: float,
) -> tuple[np.ndarray, Any]:
    sol = solve_ivp(
        rhs,
        (0.0, float(period_s)),
        np.asarray(x0, dtype=float),
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    return np.asarray(sol.y[:, -1], dtype=float), sol


def period_map_jacobian(
    phi: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    scales: np.ndarray,
    perturbation_factor: float,
) -> np.ndarray:
    """Central-difference Jacobian of a known period map."""
    x = np.asarray(x0, dtype=float)
    scales = np.asarray(scales, dtype=float)
    if x.ndim != 1 or scales.shape != x.shape:
        raise ValueError("x0 and scales must be one-dimensional and same length.")
    if perturbation_factor <= 0.0:
        raise ValueError("perturbation_factor must be positive.")

    jac = np.zeros((x.size, x.size), dtype=float)
    for index in range(x.size):
        h = float(perturbation_factor * scales[index])
        if h <= 0.0 or not np.isfinite(h):
            raise ValueError(f"Invalid perturbation step for state {index}.")
        plus = x.copy()
        minus = x.copy()
        plus[index] += h
        minus[index] -= h
        jac[:, index] = (phi(plus) - phi(minus)) / (2.0 * h)
    return jac


def _constant_profiles_model(controller: GFMController) -> Microgrid:
    return Microgrid(
        irradiance_profile=lambda _t: MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
        temperature_profile=lambda _t: MICROGRID_TEMPERATURE_C_DEFAULT,
        load_profile=lambda _t: MICROGRID_LOAD_P_NOM_W_DEFAULT,
        controller=controller,
    )


def build_formal_model(
    inertia_m: float = GFM_SELECTED_M,
    damping_d: float = GFM_SELECTED_D,
) -> Microgrid:
    return _constant_profiles_model(
        GFMController(
            p_ref=_reference_active_power_w(),
            inertia_m=inertia_m,
            damping_d=damping_d,
        )
    )


def build_bess_pi_model(
    inertia_m: float = GFM_SELECTED_M,
    damping_d: float = GFM_SELECTED_D,
) -> MicrogridWithBESSPI:
    controller = GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=inertia_m,
        damping_d=damping_d,
    )
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=PI_KP_W_PER_V,
        ki_w_per_v_s=PI_KI_W_PER_V_S,
    )
    return MicrogridWithBESSPI(
        irradiance_profile=lambda _t: MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
        temperature_profile=lambda _t: MICROGRID_TEMPERATURE_C_DEFAULT,
        load_profile=lambda _t: MICROGRID_LOAD_P_NOM_W_DEFAULT,
        controller=controller,
        dc_link_bess_pi=pi,
        bess_enabled=True,
    )


def _initial_state(model: Microgrid) -> list[float]:
    if isinstance(model, MicrogridWithBESSPI):
        return model.initial_state_with_bess(
            vdc0=SIM_VDC0_V_DEFAULT,
            xi_bess_vdc0_v_s=0.0,
        )
    return model.initial_state(vdc0=SIM_VDC0_V_DEFAULT)


def _settle_model(model: Microgrid, settling_time_s: float):
    y0 = _initial_state(model)
    sol = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, float(settling_time_s)),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    return np.asarray(sol.y[:, -1], dtype=float), sol


def periodic_residual(
    x0: np.ndarray,
    xT: np.ndarray,
    scales: np.ndarray,
) -> dict[str, Any]:
    diff = np.asarray(xT, dtype=float) - np.asarray(x0, dtype=float)
    diff[ANGLE_INDEX] -= 2.0 * np.pi
    scaled = diff / np.asarray(scales, dtype=float)
    abc_indices = np.r_[1:10]
    omega_rel = abs(diff[10]) / max(abs(float(x0[10])), 1.0)
    result = {
        "vdc_relative_error": float(abs(diff[0]) / max(abs(float(x0[0])), 1.0)),
        "abc_scaled_error_norm": float(np.linalg.norm(scaled[abc_indices])),
        "omega_relative_error": float(omega_rel),
        "theta_increment_error_rad": float(diff[ANGLE_INDEX]),
        "scaled_total_residual_norm": float(
            np.linalg.norm(scaled) / np.sqrt(scaled.size)
        ),
        "max_abs_scaled_residual": float(np.max(np.abs(scaled))),
    }
    result["periodic_enough"] = bool(
        result["vdc_relative_error"] <= PERIODIC_RESIDUAL_TOL
        and result["abc_scaled_error_norm"] <= ABC_RESIDUAL_TOL
        and result["omega_relative_error"] <= OMEGA_REL_TOL
        and abs(result["theta_increment_error_rad"]) <= THETA_RESIDUAL_TOL_RAD
        and result["scaled_total_residual_norm"] <= PERIODIC_RESIDUAL_TOL
    )
    return result


def _dominant_states(eigenvector: np.ndarray, scales: np.ndarray, names: tuple[str, ...]) -> list[str]:
    scaled = np.abs(np.asarray(eigenvector, dtype=complex) / scales)
    order = np.argsort(scaled)[::-1]
    return [str(names[index]) for index in order[:3]]


def classify_mode(
    mu: complex,
    lamb: complex,
    eigenvector: np.ndarray,
    scales: np.ndarray,
    names: tuple[str, ...],
    *,
    sensitivity_flag: bool = False,
) -> tuple[str, bool, str]:
    """Classify one Floquet mode under the Objective 2.3 rules."""
    magnitude = abs(mu)
    dominant = _dominant_states(eigenvector, scales, names)
    theta_dominant = "theta" in dominant
    if abs(mu - 1.0) <= NEUTRAL_TOL and theta_dominant:
        return "neutral_phase_mode", False, "phase symmetry mode near mu=1"
    if magnitude > 1.0 + UNIT_CIRCLE_TOL or lamb.real > REAL_LAMBDA_TOL:
        return "unstable", True, ""
    if sensitivity_flag:
        return "numerically_uncertain", True, ""
    if abs(magnitude - 1.0) <= UNIT_CIRCLE_TOL:
        return "near_unit_circle_review", True, ""
    if abs(lamb.imag) / (2.0 * np.pi) > OSC_FREQ_TOL_HZ:
        return "stable_oscillatory", True, ""
    return "stable_real", True, ""


def _sorted_eigs(eigvals: np.ndarray, eigvecs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.lexsort((np.imag(eigvals), np.real(eigvals), np.abs(eigvals)))
    return eigvals[order], eigvecs[:, order]


def _match_eigenvalues(reference: np.ndarray, comparison: np.ndarray) -> list[int]:
    remaining = set(range(comparison.size))
    matches: list[int] = []
    for value in reference:
        index = min(remaining, key=lambda item: abs(value - comparison[item]))
        matches.append(index)
        remaining.remove(index)
    return matches


def _stable_flag(mu: complex) -> str:
    if abs(mu - 1.0) <= NEUTRAL_TOL:
        return "neutral"
    if abs(mu) > 1.0 + UNIT_CIRCLE_TOL:
        return "unstable"
    if abs(abs(mu) - 1.0) <= UNIT_CIRCLE_TOL:
        return "near_unit"
    return "stable"


def _modal_sensitivity(
    eigvals_a: np.ndarray,
    eigvals_b: np.ndarray,
    period_s: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    matches = _match_eigenvalues(eigvals_a, eigvals_b)
    paired = eigvals_b[matches]
    mu_mag_change = np.abs(np.abs(eigvals_a) - np.abs(paired))
    lambda_a = np.asarray([mu_to_lambda(mu, period_s) for mu in eigvals_a])
    lambda_b = np.asarray([mu_to_lambda(mu, period_s) for mu in paired])
    real_change = np.abs(np.real(lambda_a) - np.real(lambda_b))

    records: list[dict[str, Any]] = []
    strong_flags: list[bool] = []
    classification_stable = True
    for index, (mu_a, mu_b, delta_mu, delta_real) in enumerate(
        zip(eigvals_a, paired, mu_mag_change, real_change),
        start=1,
    ):
        flag_a = _stable_flag(mu_a)
        flag_b = _stable_flag(mu_b)
        classification_changed = flag_a != flag_b
        classification_stable = classification_stable and not classification_changed
        near_unit = bool(
            abs(abs(mu_a) - 1.0) <= 5.0 * UNIT_CIRCLE_TOL
            or abs(abs(mu_b) - 1.0) <= 5.0 * UNIT_CIRCLE_TOL
        )
        deeply_damped = bool(abs(mu_a) < 1e-4 and abs(mu_b) < 1e-4)
        if deeply_damped:
            sensitive = bool(classification_changed or delta_mu > SENSITIVITY_MU_TOL)
        elif near_unit:
            sensitive = bool(
                classification_changed
                or delta_mu > SENSITIVITY_MU_TOL
                or delta_real > SENSITIVITY_LAMBDA_TOL
            )
        else:
            sensitive = bool(classification_changed or delta_mu > SENSITIVITY_MU_TOL)
        strong_flags.append(sensitive)
        records.append(
            {
                "mode_id": index,
                "paired_mu_real": float(np.real(mu_b)),
                "paired_mu_imag": float(np.imag(mu_b)),
                "delta_mu_magnitude": float(delta_mu),
                "delta_lambda_real": float(delta_real),
                "classification_a": flag_a,
                "classification_b": flag_b,
                "classification_changed": bool(classification_changed),
                "near_unit_circle": near_unit,
                "deeply_damped": deeply_damped,
                "individual_sensitive": sensitive,
            }
        )
    return {
        "max_mu_magnitude_change": float(np.max(mu_mag_change)),
        "max_lambda_real_change": float(np.max(real_change)),
        "classification_stable": classification_stable,
        "strong_sensitivity": bool(any(strong_flags)),
    }, records


def _analyze_architecture(
    *,
    architecture: str,
    model: Microgrid,
    settling_time_s: float,
    perturbation_factor: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    period_s = 1.0 / GRID_FREQ_HZ_DEFAULT
    x0, settle_sol = _settle_model(model, settling_time_s)
    state_count = x0.size
    scales = build_state_scales(state_count)
    names = _state_names(state_count)
    xT, base_period_sol = _integrate_map(model.system_dynamics, x0, period_s)
    residual = periodic_residual(x0, xT, scales)
    solver_ok = bool(
        settle_sol.success
        and base_period_sol.success
        and np.all(np.isfinite(settle_sol.y))
        and np.all(np.isfinite(base_period_sol.y))
    )

    def phi(state: np.ndarray) -> np.ndarray:
        mapped, sol = _integrate_map(model.system_dynamics, state, period_s)
        if not sol.success or not np.all(np.isfinite(mapped)):
            raise RuntimeError(str(sol.message))
        return mapped

    jac_a = period_map_jacobian(phi, x0, scales, perturbation_factor)
    jac_b = period_map_jacobian(phi, x0, scales, 2.0 * perturbation_factor)
    eigvals_a, eigvecs_a = np.linalg.eig(jac_a)
    eigvals_b = np.linalg.eigvals(jac_b)
    eigvals, eigvecs = _sorted_eigs(eigvals_a, eigvecs_a)
    sensitivity, modal_sensitivity = _modal_sensitivity(eigvals, eigvals_b, period_s)

    modes: list[dict[str, Any]] = []
    zeta_values: list[tuple[int, float]] = []
    neutral_modes: list[int] = []
    unstable_modes: list[int] = []
    for mode_index, (mu, vec) in enumerate(zip(eigvals, eigvecs.T), start=1):
        sensitivity_record = modal_sensitivity[mode_index - 1]
        lamb = mu_to_lambda(mu, period_s)
        values = modal_values(mu, period_s)
        classification, relevant, exclusion = classify_mode(
            mu,
            lamb,
            vec,
            scales,
            names,
            sensitivity_flag=bool(sensitivity_record["individual_sensitive"]),
        )
        dominant = _dominant_states(vec, scales, names)
        if classification == "neutral_phase_mode":
            neutral_modes.append(mode_index)
        if classification == "unstable":
            unstable_modes.append(mode_index)
        if relevant and values["zeta"] is not None:
            zeta_values.append((mode_index, float(values["zeta"])))
        modes.append(
            {
                "architecture": architecture,
                "mode_id": mode_index,
                "mu_real": float(np.real(mu)),
                "mu_imag": float(np.imag(mu)),
                "mu_magnitude": float(abs(mu)),
                **values,
                "classification": classification,
                "relevant_mode": relevant,
                "exclusion_reason": exclusion,
                "dominant_state_1": dominant[0],
                "dominant_state_2": dominant[1],
                "dominant_state_3": dominant[2],
                "perturbation_sensitivity": (
                    "strong"
                    if sensitivity_record["individual_sensitive"]
                    else "acceptable"
                ),
                "delta_mu_magnitude": sensitivity_record["delta_mu_magnitude"],
                "delta_lambda_real": sensitivity_record["delta_lambda_real"],
                "sensitivity_classification_changed": sensitivity_record[
                    "classification_changed"
                ],
                "near_unit_circle_sensitivity": sensitivity_record[
                    "near_unit_circle"
                ],
            }
        )

    relevant_modes = [mode for mode in modes if mode["relevant_mode"]]
    non_neutral_stable = bool(
        relevant_modes
        and all(mode["mu_magnitude"] < 1.0 for mode in relevant_modes)
        and all(mode["lambda_real"] < 0.0 for mode in relevant_modes)
    )
    zeta_min = min((item[1] for item in zeta_values), default=None)
    zeta_mode = (
        min(zeta_values, key=lambda item: item[1])[0] if zeta_values else None
    )
    zeta_criterion = None if zeta_min is None else bool(zeta_min > ZETA_MIN_REQUIRED)

    bess_drift: dict[str, float] = {}
    bess_drift_review = False
    if state_count == 16:
        diff = xT - x0
        diff[ANGLE_INDEX] -= 2.0 * np.pi
        bess_drift = {
            "soc_bess": float(diff[12]),
            "vrc_bess": float(diff[13]),
            "zdeg_bess": float(diff[14]),
            "xi_bess_vdc": float(diff[15]),
        }
        bess_scaled = np.abs(diff[12:16] / scales[12:16])
        bess_drift_review = bool(np.max(bess_scaled) > PERIODIC_RESIDUAL_TOL)

    if not solver_ok or unstable_modes:
        status = "FAIL"
    elif (
        not residual["periodic_enough"]
        or sensitivity["strong_sensitivity"]
        or any(mode["classification"] == "near_unit_circle_review" for mode in modes)
        or zeta_criterion is None
        or bess_drift_review
    ):
        status = "REVIEW"
    elif zeta_criterion is False:
        status = "FAIL"
    else:
        status = "PASS"

    reason = ""
    if state_count == 16 and bess_drift_review:
        reason = "slow BESS or integrator drift prevents a true periodic orbit"
    elif not residual["periodic_enough"]:
        reason = "base orbit is not sufficiently periodic"
    elif sensitivity["strong_sensitivity"]:
        reason = "Floquet spectrum is strongly sensitive to perturbation step"
    elif zeta_criterion is None:
        reason = "no relevant oscillatory modes for zeta criterion"

    summary = {
        "architecture": architecture,
        "status": status,
        "reason": reason,
        "state_count": state_count,
        "period_s": period_s,
        "settling_time_s": settling_time_s,
        "solver_success": solver_ok,
        "settle_solver_message": str(settle_sol.message),
        "period_solver_message": str(base_period_sol.message),
        "periodicity": residual,
        "bess_slow_state_drift": bess_drift,
        "sensitivity": sensitivity,
        "modal_sensitivity": modal_sensitivity,
        "neutral_modes": neutral_modes,
        "unstable_modes": unstable_modes,
        "zeta_min": zeta_min,
        "zeta_min_mode": zeta_mode,
        "zeta_criterion_pass": zeta_criterion,
        "real_part_criterion_pass": non_neutral_stable,
        "modes": modes,
    }
    return summary, modes


def _overall_status(formal: dict[str, Any], bess: dict[str, Any] | None) -> str:
    if formal["status"] == "FAIL":
        return "FAIL"
    if bess is None:
        return formal["status"]
    if (
        formal["status"] == "PASS"
        and bess["status"] != "REVIEW"
        and bess["status"] != "FAIL"
    ):
        return "PASS"
    if bess["status"] == "FAIL" and formal["status"] == "PASS":
        return "REVIEW"
    return "REVIEW"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def run_validation(
    *,
    output_dir: Path = OUTPUT_DIR_DEFAULT,
    write: bool = True,
    settling_time_s: float = 1.0,
    perturbation_factor: float = 1e-6,
    inertia_m: float = GFM_SELECTED_M,
    damping_d: float = GFM_SELECTED_D,
    formal_only: bool = False,
) -> dict[str, Any]:
    formal_summary, formal_modes = _analyze_architecture(
        architecture="gfm_12_state_no_bess",
        model=build_formal_model(inertia_m=inertia_m, damping_d=damping_d),
        settling_time_s=settling_time_s,
        perturbation_factor=perturbation_factor,
    )
    if formal_only:
        bess_summary = None
        bess_modes: list[dict[str, Any]] = []
    else:
        bess_summary, bess_modes = _analyze_architecture(
            architecture="gfm_bess_pi_16_state_diagnostic",
            model=build_bess_pi_model(inertia_m=inertia_m, damping_d=damping_d),
            settling_time_s=settling_time_s,
            perturbation_factor=perturbation_factor,
        )
    modes = formal_modes + bess_modes
    global_status = _overall_status(formal_summary, bess_summary)
    output_dir = Path(output_dir)
    eigenvalues_csv = output_dir / EIGENVALUES_CSV_NAME
    summary_json = output_dir / SUMMARY_JSON_NAME

    report = {
        "method": "central-difference Jacobian of the one-electrical-period map",
        "periodic_analysis_justification": (
            "abc states and theta form a periodic orbit; an instantaneous RHS "
            "Jacobian is not used as the formal stability proof."
        ),
        "model_commit": _git_commit(),
        "M": float(inertia_m),
        "D": float(damping_d),
        "alpha": ALPHA_NOT_APPLICABLE,
        "status": global_status,
        "architectures": {
            formal_summary["architecture"]: formal_summary,
        },
        "tolerances": {
            "neutral_tol": NEUTRAL_TOL,
            "unit_circle_tol": UNIT_CIRCLE_TOL,
            "real_lambda_tol": REAL_LAMBDA_TOL,
            "periodic_residual_tol": PERIODIC_RESIDUAL_TOL,
            "zeta_min_required": ZETA_MIN_REQUIRED,
            "solver_rtol": SIM_SOLVER_RTOL_DEFAULT,
            "solver_atol": SIM_SOLVER_ATOL_DEFAULT,
            "solver_max_step_s": SIM_SOLVER_MAX_STEP_S_DEFAULT,
        },
        "perturbation_steps": {
            "base_factor": perturbation_factor,
            "comparison_factor": 2.0 * perturbation_factor,
            "state_scaled": True,
        },
        "all_multipliers": [
            {
                "architecture": mode["architecture"],
                "mode_id": mode["mode_id"],
                "mu_real": mode["mu_real"],
                "mu_imag": mode["mu_imag"],
                "mu_magnitude": mode["mu_magnitude"],
            }
            for mode in modes
        ],
        "all_exponents": [
            {
                "architecture": mode["architecture"],
                "mode_id": mode["mode_id"],
                "lambda_real": mode["lambda_real"],
                "lambda_imag": mode["lambda_imag"],
            }
            for mode in modes
        ],
        "neutral_modes": formal_summary["neutral_modes"],
        "unstable_modes": formal_summary["unstable_modes"],
        "zeta_min": formal_summary["zeta_min"],
        "zeta_min_mode": formal_summary["zeta_min_mode"],
        "zeta_min_criterion": formal_summary["zeta_criterion_pass"],
        "real_part_criterion": formal_summary["real_part_criterion_pass"],
        "limitations": [
            "Numerical Floquet analysis, not an experimental validation.",
            "The BESS/PI architecture contains slow states and is diagnostic.",
            "No new multi-scenario tuner is implemented in this activity part.",
        ],
        "output_paths": {
            "eigenvalues_csv": str(eigenvalues_csv),
            "small_signal_summary_json": str(summary_json),
        },
    }
    if bess_summary is not None:
        report["architectures"][bess_summary["architecture"]] = bess_summary
    clean = _json_ready(report)

    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        with eigenvalues_csv.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=(
                    "architecture",
                    "mode_id",
                    "mu_real",
                    "mu_imag",
                    "mu_magnitude",
                    "lambda_real",
                    "lambda_imag",
                    "natural_frequency_rad_s",
                    "modal_frequency_hz",
                    "zeta",
                    "classification",
                    "relevant_mode",
                    "exclusion_reason",
                    "dominant_state_1",
                    "dominant_state_2",
                    "dominant_state_3",
                    "perturbation_sensitivity",
                    "delta_mu_magnitude",
                    "delta_lambda_real",
                    "sensitivity_classification_changed",
                    "near_unit_circle_sensitivity",
                ),
            )
            writer.writeheader()
            writer.writerows(modes)
        with summary_json.open("w", encoding="utf-8") as json_file:
            json.dump(clean, json_file, indent=2, sort_keys=True)
            json_file.write("\n")

    print(f"formal_status={formal_summary['status']}")
    print(f"formal_periodic={formal_summary['periodicity']['periodic_enough']}")
    print(f"formal_modes={len(formal_modes)}")
    print(f"formal_neutral_modes={formal_summary['neutral_modes']}")
    print(f"formal_unstable_modes={formal_summary['unstable_modes']}")
    print(f"formal_zeta_min={formal_summary['zeta_min']}")
    print(f"formal_zeta_min_mode={formal_summary['zeta_min_mode']}")
    if bess_summary is None:
        print("bess_status=SKIPPED")
        print("bess_reason=formal_only")
    else:
        print(f"bess_status={bess_summary['status']}")
        print(f"bess_reason={bess_summary['reason']}")
    print(f"global_status={global_status}")
    if write:
        print(f"eigenvalues_csv={eigenvalues_csv}")
        print(f"summary_json={summary_json}")
    else:
        print("no_write=True")
    return clean


def analyze_point(
    inertia_m: float,
    damping_d: float,
    *,
    formal_only: bool = True,
    settling_time_s: float = 1.0,
    perturbation_factor: float = 1e-6,
) -> dict[str, Any]:
    """Analyze one ``(M, D)`` point and return evidence without writing files."""
    return run_validation(
        write=False,
        settling_time_s=settling_time_s,
        perturbation_factor=perturbation_factor,
        inertia_m=inertia_m,
        damping_d=damping_d,
        formal_only=formal_only,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--settling-time", type=float, default=1.0)
    parser.add_argument("--perturbation-factor", type=float, default=1e-6)
    parser.add_argument("--m", type=float, default=GFM_SELECTED_M)
    parser.add_argument("--d", type=float, default=GFM_SELECTED_D)
    parser.add_argument("--formal-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_validation(
        output_dir=args.output_dir,
        write=not args.no_write,
        settling_time_s=args.settling_time,
        perturbation_factor=args.perturbation_factor,
        inertia_m=args.m,
        damping_d=args.d,
        formal_only=args.formal_only,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
