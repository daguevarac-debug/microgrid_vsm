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


def main() -> int:
    status = validate_steady_operation()
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
