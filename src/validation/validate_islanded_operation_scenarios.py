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
from microgrid import BalancedRLLoad, Microgrid, MicrogridWithBESS


EPS = 1e-12
GROWTH_LIMIT = 1.2
VDC_STEP_20_DELTA_LIMIT_PCT = 10.0
VDC_ABRUPT_STEP_DELTA_LIMIT_PCT = 15.0
LIMIT_ATOL = 1e-9


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


def _base_initial_state() -> list[float]:
    return [
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


def _solve_model(model: Microgrid, y0: list[float]):
    return solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )


def _final_window_masks(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t0 = float(t[0])
    tf = float(t[-1])
    dt = tf - t0
    t_a0 = t0 + 0.70 * dt
    t_a1 = t0 + 0.85 * dt
    t_b0 = t_a1
    t_b1 = tf
    return (
        _window_mask(t, t_a0, t_a1, include_right=False),
        _window_mask(t, t_b0, t_b1, include_right=True),
    )


def _step_common_metrics(
    t: np.ndarray,
    y: np.ndarray,
    p_bridge: np.ndarray,
    p_pcc: np.ndarray,
    t_step: float,
) -> dict[str, float | bool]:
    vdc = y[0]
    i2 = y[7:10]
    step_index = int(np.searchsorted(t, t_step, side="left"))
    pre_index = max(0, step_index - 1)
    post_mask = t >= t_step
    vdc_pre_step = float(vdc[pre_index])
    vdc_min_post_step = float(np.min(vdc[post_mask])) if np.any(post_mask) else float("nan")
    delta_vdc_abs = abs(vdc_pre_step - vdc_min_post_step)
    delta_vdc_pct = 100.0 * delta_vdc_abs / max(abs(vdc_pre_step), EPS)
    mask_a, mask_b = _final_window_masks(t)

    return {
        "states_finite": bool(np.all(np.isfinite(y))),
        "vdc_positive": bool(np.all(np.isfinite(vdc)) and np.all(vdc > 0.0)),
        "p_bridge_finite": bool(np.all(np.isfinite(p_bridge))),
        "p_pcc_finite": bool(np.all(np.isfinite(p_pcc))),
        "i2_finite": bool(np.all(np.isfinite(i2))),
        "vdc_pre_step": vdc_pre_step,
        "vdc_min_post_step": vdc_min_post_step,
        "vdc_final": float(vdc[-1]),
        "delta_vdc_pct": delta_vdc_pct,
        "max_abs_i2": float(np.max(np.abs(i2))) if i2.size else float("nan"),
        "growth_vdc": _growth_ratio(vdc, mask_a, mask_b),
        "growth_i2": _growth_ratio(i2, mask_a, mask_b),
        "growth_p_pcc": _growth_ratio(p_pcc, mask_a, mask_b),
        "growth_p_bridge": _growth_ratio(p_bridge, mask_a, mask_b),
        "windows_ok": bool(np.any(mask_a) and np.any(mask_b)),
    }


def validate_steady_operation() -> str:
    """Validate nominal islanded steady operation without load step or BESS."""
    status = "PASS"
    reasons: list[str] = []

    load = BalancedRLLoad.from_active_power(
        p_3ph_w=MICROGRID_LOAD_P_NOM_W_DEFAULT,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    )
    model = Microgrid(load_profile=lambda _t: MICROGRID_LOAD_P_NOM_W_DEFAULT)

    sol = _solve_model(model, _base_initial_state())

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

    sol = _solve_model(model, _base_initial_state())

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

    mask_a, mask_b = _final_window_masks(sol.t)

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


def validate_bess_vs_no_bess() -> str:
    """Validate no-BESS and preliminary-BESS cases under the same 20% load step."""
    status = "PASS"
    reasons: list[str] = []

    p_pre = MICROGRID_LOAD_P_NOM_W_DEFAULT
    p_post = MICROGRID_LOAD_P_NOM_W_DEFAULT * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
    t_step = MICROGRID_LOAD_STEP_TIME_S_DEFAULT
    load_pre = BalancedRLLoad.from_active_power(
        p_3ph_w=p_pre,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    )
    load_post = BalancedRLLoad.from_active_power(
        p_3ph_w=p_post,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    )
    load_step_pct = 100.0 * (p_post - p_pre) / p_pre

    load_profile = lambda t: p_pre if t < t_step else p_post
    no_bess_model = Microgrid(load_profile=load_profile)
    with_bess_model = MicrogridWithBESS(load_profile=load_profile)

    no_bess_sol = _solve_model(no_bess_model, _base_initial_state())
    with_bess_sol = _solve_model(
        with_bess_model,
        with_bess_model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT),
    )

    no_bess_p_bridge = np.zeros_like(no_bess_sol.t)
    no_bess_p_pcc = np.zeros_like(no_bess_sol.t)
    for k, (tk, xk) in enumerate(zip(no_bess_sol.t, no_bess_sol.y.T)):
        no_bess_p_bridge[k], no_bess_p_pcc[k], _, _, _ = no_bess_model.power_signals(float(tk), xk)

    bess_keys = (
        "i_bess",
        "p_bess_dc",
        "i_bess_max_available",
        "p_bess_dc_max_available",
        "soc_bess",
        "vt_bess",
        "soh_bess",
        "p_bridge",
        "p_pcc",
    )
    bess_signals = {key: np.zeros_like(with_bess_sol.t, dtype=float) for key in bess_keys}
    for k, (tk, xk) in enumerate(zip(with_bess_sol.t, with_bess_sol.y.T)):
        sig = with_bess_model.integrated_signals(float(tk), xk)
        for key in bess_keys:
            bess_signals[key][k] = float(sig[key])

    no_bess_metrics = _step_common_metrics(
        no_bess_sol.t,
        no_bess_sol.y,
        no_bess_p_bridge,
        no_bess_p_pcc,
        t_step,
    )
    with_bess_metrics = _step_common_metrics(
        with_bess_sol.t,
        with_bess_sol.y,
        bess_signals["p_bridge"],
        bess_signals["p_pcc"],
        t_step,
    )

    i_bess = bess_signals["i_bess"]
    p_bess_dc = bess_signals["p_bess_dc"]
    soc_bess = bess_signals["soc_bess"]
    soh_bess = bess_signals["soh_bess"]
    vt_bess = bess_signals["vt_bess"]
    i_bess_max_available = bess_signals["i_bess_max_available"]
    p_bess_dc_max_available = bess_signals["p_bess_dc_max_available"]

    no_bess_solver_success = bool(no_bess_sol.success)
    with_bess_solver_success = bool(with_bess_sol.success)
    bess_signals_finite = bool(all(np.all(np.isfinite(value)) for value in bess_signals.values()))
    soc_range_ok = bool(
        np.all((soc_bess >= with_bess_model.bess.soc_min) & (soc_bess <= with_bess_model.bess.soc_max))
    )
    soh_range_ok = bool(np.all((soh_bess >= with_bess_model.bess.soh_min) & (soh_bess <= 1.0)))
    current_limit_ok = bool(np.all(np.abs(i_bess) <= i_bess_max_available + LIMIT_ATOL))
    power_limit_ok = bool(np.all(np.abs(p_bess_dc) <= p_bess_dc_max_available + LIMIT_ATOL))
    vt_positive_ok = bool(np.all(vt_bess > 0.0))

    for prefix, solver_success, metrics in (
        ("no_bess", no_bess_solver_success, no_bess_metrics),
        ("with_bess", with_bess_solver_success, with_bess_metrics),
    ):
        if not solver_success:
            status = "FAIL"
            reasons.append(f"{prefix} solve_ivp unsuccessful")
        if not bool(metrics["states_finite"]):
            status = "FAIL"
            reasons.append(f"{prefix} state vector contains NaN/Inf")
        if not bool(metrics["vdc_positive"]):
            status = "FAIL"
            reasons.append(f"{prefix} Vdc is not finite and positive")
        if not bool(metrics["p_pcc_finite"]):
            status = "FAIL"
            reasons.append(f"{prefix} p_pcc contains NaN/Inf")
        if not bool(metrics["p_bridge_finite"]):
            status = "FAIL"
            reasons.append(f"{prefix} p_bridge contains NaN/Inf")
        if not bool(metrics["i2_finite"]) or not np.isfinite(float(metrics["max_abs_i2"])):
            status = "FAIL"
            reasons.append(f"{prefix} i2 current metrics are not finite")
        if not bool(metrics["windows_ok"]):
            status = "FAIL"
            reasons.append(f"{prefix} insufficient samples in one or both final windows")
        if float(metrics["delta_vdc_pct"]) > VDC_STEP_20_DELTA_LIMIT_PCT:
            status = "FAIL"
            reasons.append(
                f"{prefix} delta_vdc_pct={float(metrics['delta_vdc_pct']):.6f} "
                f"> {VDC_STEP_20_DELTA_LIMIT_PCT:.2f}%"
            )
        for name in ("growth_vdc", "growth_i2", "growth_p_pcc", "growth_p_bridge"):
            if float(metrics[name]) > GROWTH_LIMIT:
                status = "FAIL"
                reasons.append(f"{prefix} {name}={float(metrics[name]):.6f} > {GROWTH_LIMIT}")

    if abs(load_step_pct - 20.0) > 1e-9:
        status = "FAIL"
        reasons.append(f"load_step_pct={load_step_pct:.6f} is not approximately 20%")
    if not p_post > p_pre:
        status = "FAIL"
        reasons.append("post-step load is not greater than pre-step load")
    if not bess_signals_finite:
        status = "FAIL"
        reasons.append("BESS diagnostic signals contain NaN/Inf")
    if not soc_range_ok:
        status = "FAIL"
        reasons.append("SoC is outside operational limits")
    if not soh_range_ok:
        status = "FAIL"
        reasons.append("SoH is outside physical range")
    if not current_limit_ok:
        status = "FAIL"
        reasons.append("i_bess exceeds available current limit")
    if not power_limit_ok:
        status = "FAIL"
        reasons.append("p_bess_dc exceeds available power limit")
    if not vt_positive_ok:
        status = "FAIL"
        reasons.append("vt_bess is not positive")

    delta_vdc_pct_difference = float(with_bess_metrics["delta_vdc_pct"]) - float(
        no_bess_metrics["delta_vdc_pct"]
    )

    print("scenario=bess_vs_no_bess_load_step_20")
    print(f"status={status}")
    print(f"t_step_s={t_step:.6f}")
    print(f"p_load_pre_step_w={load_pre.p_3ph_w:.6f}")
    print(f"p_load_post_step_w={load_post.p_3ph_w:.6f}")
    print(f"q_load_pre_step_var={load_pre.q_3ph_var:.6f}")
    print(f"q_load_post_step_var={load_post.q_3ph_var:.6f}")
    print(f"load_step_pct={load_step_pct:.6f}")
    print("no_bess_active=False")
    print(f"no_bess_solver_success={no_bess_solver_success}")
    print(f"no_bess_states_finite={bool(no_bess_metrics['states_finite'])}")
    print(f"no_bess_vdc_pre_step_v={float(no_bess_metrics['vdc_pre_step']):.6f}")
    print(f"no_bess_vdc_min_post_step_v={float(no_bess_metrics['vdc_min_post_step']):.6f}")
    print(f"no_bess_vdc_final_v={float(no_bess_metrics['vdc_final']):.6f}")
    print(f"no_bess_delta_vdc_pct={float(no_bess_metrics['delta_vdc_pct']):.6f}")
    print(f"no_bess_max_abs_i2_a={float(no_bess_metrics['max_abs_i2']):.6f}")
    print(f"with_bess_solver_success={with_bess_solver_success}")
    print(f"with_bess_states_finite={bool(with_bess_metrics['states_finite'])}")
    print(f"with_bess_vdc_pre_step_v={float(with_bess_metrics['vdc_pre_step']):.6f}")
    print(f"with_bess_vdc_min_post_step_v={float(with_bess_metrics['vdc_min_post_step']):.6f}")
    print(f"with_bess_vdc_final_v={float(with_bess_metrics['vdc_final']):.6f}")
    print(f"with_bess_delta_vdc_pct={float(with_bess_metrics['delta_vdc_pct']):.6f}")
    print(f"with_bess_max_abs_i2_a={float(with_bess_metrics['max_abs_i2']):.6f}")
    print(f"i_bess_min_a={float(np.min(i_bess)):.6f}")
    print(f"i_bess_max_a={float(np.max(i_bess)):.6f}")
    print(f"i_bess_final_a={float(i_bess[-1]):.6f}")
    print(f"p_bess_dc_min_w={float(np.min(p_bess_dc)):.6f}")
    print(f"p_bess_dc_max_w={float(np.max(p_bess_dc)):.6f}")
    print(f"p_bess_dc_final_w={float(p_bess_dc[-1]):.6f}")
    print(f"soc_bess_min={float(np.min(soc_bess)):.6f}")
    print(f"soc_bess_max={float(np.max(soc_bess)):.6f}")
    print(f"soc_bess_final={float(soc_bess[-1]):.6f}")
    print(f"soh_bess_final={float(soh_bess[-1]):.6f}")
    print(f"vt_bess_final_v={float(vt_bess[-1]):.6f}")
    print(f"delta_vdc_pct_difference={delta_vdc_pct_difference:.6f}")
    print("bess_active=True")
    print(f"no_bess_growth_ratio_vdc={float(no_bess_metrics['growth_vdc']):.6f}")
    print(f"no_bess_growth_ratio_i2={float(no_bess_metrics['growth_i2']):.6f}")
    print(f"no_bess_growth_ratio_p_pcc={float(no_bess_metrics['growth_p_pcc']):.6f}")
    print(f"no_bess_growth_ratio_p_bridge={float(no_bess_metrics['growth_p_bridge']):.6f}")
    print(f"with_bess_growth_ratio_vdc={float(with_bess_metrics['growth_vdc']):.6f}")
    print(f"with_bess_growth_ratio_i2={float(with_bess_metrics['growth_i2']):.6f}")
    print(f"with_bess_growth_ratio_p_pcc={float(with_bess_metrics['growth_p_pcc']):.6f}")
    print(f"with_bess_growth_ratio_p_bridge={float(with_bess_metrics['growth_p_bridge']):.6f}")
    if reasons:
        print("fail_reasons:")
        for item in reasons:
            print(f"- {item}")

    print(
        "note=Comparacion bajo el mismo escalon del 20%; la mejora dinamica "
        "del BESS se reporta pero no es criterio de fallo en esta etapa."
    )

    return status


def main() -> int:
    statuses = [
        validate_steady_operation(),
        validate_load_step_20(),
        validate_abrupt_load_change(),
        validate_bess_vs_no_bess(),
    ]
    return 0 if all(status == "PASS" for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
