"""Validate islanded operation scenarios.

This module is the consolidation point for the islanded-operation validation
bucket. For now it includes only the nominal steady-operation scenario. Future
functions can add the 20% load step, severe load change, no-BESS, and BESS
support scenarios without creating one script per subtarea.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    GRID_THETA0_RAD_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid import BalancedRLLoad, Microgrid


EPS = 1e-12
GROWTH_LIMIT = 1.2
VDC_STEP_20_DELTA_LIMIT_PCT = 10.0
VDC_ABRUPT_STEP_DELTA_LIMIT_PCT = 15.0


def _rms(signal: np.ndarray) -> float:
    if signal.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(signal))))


def _window_mask(t: np.ndarray, t0: float, t1: float, include_right: bool = False) -> np.ndarray:
    if include_right:
        return (t >= t0) & (t <= t1)
    return (t >= t0) & (t < t1)


def _growth_ratio(signal: np.ndarray, mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    rms_a = _rms(signal[..., mask_a])
    rms_b = _rms(signal[..., mask_b])
    return rms_b / max(rms_a, EPS)


def validate_steady_operation() -> str:
    """Validate nominal islanded steady operation without load step or BESS."""
    status = "PASS"
    reasons: list[str] = []

    load = BalancedRLLoad.from_active_power(
        p_3ph_w=MICROGRID_LOAD_P_NOM_W_DEFAULT,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    )
    model = Microgrid(load_profile=lambda _t: MICROGRID_LOAD_P_NOM_W_DEFAULT)

    y0 = [
        SIM_VDC0_V_DEFAULT,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        GRID_THETA0_RAD_DEFAULT,
    ]
    sol = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    solver_success = bool(sol.success)
    states_finite = bool(np.all(np.isfinite(sol.y)))
    if not solver_success:
        status = "REVIEW"
        reasons.append(f"solve_ivp unsuccessful: {sol.message}")
    if not states_finite:
        status = "REVIEW"
        reasons.append("state vector contains NaN/Inf")

    vdc = sol.y[0]
    i2 = sol.y[7:10]
    p_bridge = np.zeros_like(sol.t)
    p_pcc = np.zeros_like(sol.t)
    for k, (tk, xk) in enumerate(zip(sol.t, sol.y.T)):
        p_bridge[k], p_pcc[k], _, _, _ = model.power_signals(float(tk), xk)

    vdc_final = float(vdc[-1])
    p_bridge_final = float(p_bridge[-1])
    p_pcc_final = float(p_pcc[-1])
    max_abs_i2 = float(np.max(np.abs(i2))) if i2.size else float("nan")

    if not np.isfinite(vdc_final) or vdc_final <= 0.0:
        status = "REVIEW"
        reasons.append(f"Vdc_final={vdc_final:.6f} is not finite and positive")
    if not np.isfinite(load.p_3ph_w) or load.p_3ph_w <= 0.0:
        status = "REVIEW"
        reasons.append(f"p_load_nominal={load.p_3ph_w:.6f} is not finite and positive")
    if not np.isfinite(p_pcc_final):
        status = "REVIEW"
        reasons.append("p_pcc_final is not finite")
    if not np.isfinite(p_bridge_final):
        status = "REVIEW"
        reasons.append("p_bridge_final is not finite")
    if not np.isfinite(max_abs_i2):
        status = "REVIEW"
        reasons.append("i2 current metrics are not finite")

    t0 = float(sol.t[0])
    tf = float(sol.t[-1])
    dt = tf - t0
    t_a0 = t0 + 0.70 * dt
    t_a1 = t0 + 0.85 * dt
    t_b0 = t_a1
    t_b1 = tf
    mask_a = _window_mask(sol.t, t_a0, t_a1, include_right=False)
    mask_b = _window_mask(sol.t, t_b0, t_b1, include_right=True)

    if not np.any(mask_a) or not np.any(mask_b):
        status = "REVIEW"
        reasons.append("insufficient samples in one or both final windows")

    growth_vdc = _growth_ratio(vdc, mask_a, mask_b)
    growth_i2 = _growth_ratio(i2, mask_a, mask_b)
    growth_p_pcc = _growth_ratio(p_pcc, mask_a, mask_b)
    growth_p_bridge = _growth_ratio(p_bridge, mask_a, mask_b)

    for name, value in (
        ("Vdc", growth_vdc),
        ("i2", growth_i2),
        ("p_pcc", growth_p_pcc),
        ("p_bridge", growth_p_bridge),
    ):
        if value > GROWTH_LIMIT:
            status = "REVIEW"
            reasons.append(f"{name} growth_ratio={value:.6f} > {GROWTH_LIMIT}")

    print("scenario=steady_operation")
    print(f"status={status}")
    print(f"solver_success={solver_success}")
    print(f"states_finite={states_finite}")
    print("bess_active=False")
    print(f"p_load_nominal_w={load.p_3ph_w:.6f}")
    print(f"q_load_nominal_var={load.q_3ph_var:.6f}")
    print(f"power_factor={load.power_factor:.6f}")
    print("constant_load_profile=True")
    print(f"Vdc_final_V={vdc_final:.6f}")
    print(f"p_load_positive={bool(load.p_3ph_w > 0.0)}")
    print(f"p_pcc_final_W={p_pcc_final:.6f}")
    print(f"p_bridge_final_W={p_bridge_final:.6f}")
    print(f"max_abs_i2_A={max_abs_i2:.6f}")
    print(f"growth_ratio_Vdc={growth_vdc:.6f}")
    print(f"growth_ratio_i2={growth_i2:.6f}")
    print(f"growth_ratio_p_pcc={growth_p_pcc:.6f}")
    print(f"growth_ratio_p_bridge={growth_p_bridge:.6f}")
    if reasons:
        print("review_reasons:")
        for item in reasons:
            print(f"- {item}")

    print(
        "note=Operacion nominal sin escalon de carga; chequeo practico de no "
        "crecimiento en ventanas finales, no validacion experimental."
    )

    return status


def _validate_load_step_scenario(
    scenario_name: str,
    step_fraction: float,
    expected_pct: float,
    delta_limit_pct: float,
) -> str:
    """Validate an islanded load-step scenario without BESS."""
    status = "PASS"
    reasons: list[str] = []

    p_pre = MICROGRID_LOAD_P_NOM_W_DEFAULT
    p_post = MICROGRID_LOAD_P_NOM_W_DEFAULT * (1.0 + step_fraction)
    t_step = MICROGRID_LOAD_STEP_TIME_S_DEFAULT
    load_pre = BalancedRLLoad.from_active_power(
        p_3ph_w=p_pre,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    )
    load_post = BalancedRLLoad.from_active_power(
        p_3ph_w=p_post,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    )
    model = Microgrid(load_profile=lambda t: p_pre if t < t_step else p_post)

    y0 = [
        SIM_VDC0_V_DEFAULT,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        GRID_THETA0_RAD_DEFAULT,
    ]
    sol = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    solver_success = bool(sol.success)
    states_finite = bool(np.all(np.isfinite(sol.y)))
    if not solver_success:
        status = "FAIL"
        reasons.append(f"solve_ivp unsuccessful: {sol.message}")
    if not states_finite:
        status = "FAIL"
        reasons.append("state vector contains NaN/Inf")

    vdc = sol.y[0]
    i2 = sol.y[7:10]
    p_bridge = np.zeros_like(sol.t)
    p_pcc = np.zeros_like(sol.t)
    for k, (tk, xk) in enumerate(zip(sol.t, sol.y.T)):
        p_bridge[k], p_pcc[k], _, _, _ = model.power_signals(float(tk), xk)

    step_index = int(np.searchsorted(sol.t, t_step, side="left"))
    pre_index = max(0, step_index - 1)
    post_mask = sol.t >= t_step
    vdc_pre_step = float(vdc[pre_index])
    vdc_min_post_step = float(np.min(vdc[post_mask])) if np.any(post_mask) else float("nan")
    vdc_final = float(vdc[-1])
    delta_vdc_abs = abs(vdc_pre_step - vdc_min_post_step)
    delta_vdc_pct = 100.0 * delta_vdc_abs / max(abs(vdc_pre_step), EPS)
    max_abs_i2 = float(np.max(np.abs(i2))) if i2.size else float("nan")
    load_step_pct = 100.0 * (p_post - p_pre) / p_pre

    p_pcc_final = float(p_pcc[-1])
    p_bridge_final = float(p_bridge[-1])
    if not np.all(np.isfinite(vdc)) or np.any(vdc <= 0.0):
        status = "FAIL"
        reasons.append("Vdc is not finite and positive throughout the simulation")
    if not (np.isfinite(load_pre.p_3ph_w) and np.isfinite(load_post.p_3ph_w)):
        status = "FAIL"
        reasons.append("p_load values are not finite")
    if not np.all(np.isfinite(p_pcc)):
        status = "FAIL"
        reasons.append("p_pcc contains NaN/Inf")
    if not np.all(np.isfinite(p_bridge)):
        status = "FAIL"
        reasons.append("p_bridge contains NaN/Inf")
    if not np.isfinite(max_abs_i2):
        status = "FAIL"
        reasons.append("i2 current metrics are not finite")
    if not p_post > p_pre:
        status = "FAIL"
        reasons.append("post-step load is not greater than pre-step load")
    if abs(load_step_pct - expected_pct) > 1e-9:
        status = "FAIL"
        reasons.append(f"load_step_pct={load_step_pct:.6f} is not approximately {expected_pct:.1f}%")
    if not np.isfinite(delta_vdc_pct) or delta_vdc_pct > delta_limit_pct:
        status = "FAIL"
        reasons.append(
            f"delta_vdc_pct={delta_vdc_pct:.6f} > {delta_limit_pct:.2f}%"
        )

    t0 = float(sol.t[0])
    tf = float(sol.t[-1])
    dt = tf - t0
    t_a0 = t0 + 0.70 * dt
    t_a1 = t0 + 0.85 * dt
    t_b0 = t_a1
    t_b1 = tf
    mask_a = _window_mask(sol.t, t_a0, t_a1, include_right=False)
    mask_b = _window_mask(sol.t, t_b0, t_b1, include_right=True)

    if not np.any(mask_a) or not np.any(mask_b):
        status = "FAIL"
        reasons.append("insufficient samples in one or both final windows")

    growth_vdc = _growth_ratio(vdc, mask_a, mask_b)
    growth_i2 = _growth_ratio(i2, mask_a, mask_b)
    growth_p_pcc = _growth_ratio(p_pcc, mask_a, mask_b)
    growth_p_bridge = _growth_ratio(p_bridge, mask_a, mask_b)

    for name, value in (
        ("Vdc", growth_vdc),
        ("i2", growth_i2),
        ("p_pcc", growth_p_pcc),
        ("p_bridge", growth_p_bridge),
    ):
        if value > GROWTH_LIMIT:
            status = "FAIL"
            reasons.append(f"{name} growth_ratio={value:.6f} > {GROWTH_LIMIT}")

    print(f"scenario={scenario_name}")
    print(f"status={status}")
    print(f"solver_success={solver_success}")
    print(f"states_finite={states_finite}")
    print("bess_active=False")
    print(f"t_step_s={t_step:.6f}")
    print(f"p_load_pre_step_w={load_pre.p_3ph_w:.6f}")
    print(f"p_load_post_step_w={load_post.p_3ph_w:.6f}")
    print(f"q_load_pre_step_var={load_pre.q_3ph_var:.6f}")
    print(f"q_load_post_step_var={load_post.q_3ph_var:.6f}")
    print(f"load_step_pct={load_step_pct:.6f}")
    print(f"vdc_pre_step_v={vdc_pre_step:.6f}")
    print(f"vdc_min_post_step_v={vdc_min_post_step:.6f}")
    print(f"vdc_final_v={vdc_final:.6f}")
    print(f"delta_vdc_abs_v={delta_vdc_abs:.6f}")
    print(f"delta_vdc_pct={delta_vdc_pct:.6f}")
    print(f"delta_vdc_limit_pct={delta_limit_pct:.6f}")
    print(f"p_pcc_final_w={p_pcc_final:.6f}")
    print(f"p_bridge_final_w={p_bridge_final:.6f}")
    print(f"max_abs_i2_a={max_abs_i2:.6f}")
    print(f"growth_ratio_vdc={growth_vdc:.6f}")
    print(f"growth_ratio_i2={growth_i2:.6f}")
    print(f"growth_ratio_p_pcc={growth_p_pcc:.6f}")
    print(f"growth_ratio_p_bridge={growth_p_bridge:.6f}")
    if reasons:
        print("fail_reasons:")
        for item in reasons:
            print(f"- {item}")

    print(
        f"note=Escalon de carga del {expected_pct:.0f}%; delta_vdc_pct es un umbral interno "
        "de validacion baseline, no un criterio normativo."
    )

    return status


def validate_load_step_20() -> str:
    """Validate islanded operation under the baseline 20% load step."""
    return _validate_load_step_scenario(
        scenario_name="load_step_20",
        step_fraction=MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
        expected_pct=20.0,
        delta_limit_pct=VDC_STEP_20_DELTA_LIMIT_PCT,
    )


def validate_abrupt_load_change() -> str:
    """Validate islanded operation under the severe 40% load step."""
    return _validate_load_step_scenario(
        scenario_name="abrupt_load_change",
        step_fraction=MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
        expected_pct=40.0,
        delta_limit_pct=VDC_ABRUPT_STEP_DELTA_LIMIT_PCT,
    )


def main() -> int:
    statuses = [
        validate_steady_operation(),
        validate_load_step_20(),
        validate_abrupt_load_change(),
    ]
    return 0 if all(status == "PASS" for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
