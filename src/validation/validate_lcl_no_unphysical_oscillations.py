"""Practical check for non-physical oscillation growth in baseline LCL states.

This script runs the baseline Microgrid simulation and evaluates whether the
LCL state groups (i1, vc, i2) remain finite and avoid evident artificial growth
in the final simulation segment.
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
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid import Microgrid


EPS = 1e-12
GROWTH_LIMIT = 1.2


def _group_rms(signal_3xn: np.ndarray) -> float:
    """Return RMS of a 3xN signal group over all phases and samples."""
    if signal_3xn.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(signal_3xn))))


def _window_mask(t: np.ndarray, t0: float, t1: float, include_right: bool = False) -> np.ndarray:
    """Create a time-window mask [t0, t1) or [t0, t1] for the last segment."""
    if include_right:
        return (t >= t0) & (t <= t1)
    return (t >= t0) & (t < t1)


def main() -> int:
    model = Microgrid()
    t_span = (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT)
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
        t_span,
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    status = "PASS"
    reasons: list[str] = []

    if not sol.success:
        status = "REVIEW"
        reasons.append(f"solve_ivp unsuccessful: {sol.message}")

    y_all_finite = bool(np.all(np.isfinite(sol.y)))
    if not y_all_finite:
        status = "REVIEW"
        reasons.append("state vector contains NaN/Inf")

    i1 = sol.y[1:4]
    vc = sol.y[4:7]
    i2 = sol.y[7:10]

    max_abs_i1 = float(np.max(np.abs(i1))) if i1.size else float("nan")
    max_abs_vc = float(np.max(np.abs(vc))) if vc.size else float("nan")
    max_abs_i2 = float(np.max(np.abs(i2))) if i2.size else float("nan")

    if not (np.isfinite(max_abs_i1) and np.isfinite(max_abs_vc) and np.isfinite(max_abs_i2)):
        status = "REVIEW"
        reasons.append("max abs metrics are not finite")

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

    i1_rms_a = _group_rms(i1[:, mask_a])
    i1_rms_b = _group_rms(i1[:, mask_b])
    vc_rms_a = _group_rms(vc[:, mask_a])
    vc_rms_b = _group_rms(vc[:, mask_b])
    i2_rms_a = _group_rms(i2[:, mask_a])
    i2_rms_b = _group_rms(i2[:, mask_b])

    growth_i1 = i1_rms_b / max(i1_rms_a, EPS)
    growth_vc = vc_rms_b / max(vc_rms_a, EPS)
    growth_i2 = i2_rms_b / max(i2_rms_a, EPS)

    if growth_i1 > GROWTH_LIMIT:
        status = "REVIEW"
        reasons.append(f"i1 growth_ratio={growth_i1:.4f} > {GROWTH_LIMIT}")
    if growth_vc > GROWTH_LIMIT:
        status = "REVIEW"
        reasons.append(f"vc growth_ratio={growth_vc:.4f} > {GROWTH_LIMIT}")
    if growth_i2 > GROWTH_LIMIT:
        status = "REVIEW"
        reasons.append(f"i2 growth_ratio={growth_i2:.4f} > {GROWTH_LIMIT}")

    print(f"status={status}")
    print(f"solver_success={sol.success}")
    print(f"all_states_finite={y_all_finite}")
    print(f"max_abs_i1_A={max_abs_i1:.6f}")
    print(f"max_abs_vc_V={max_abs_vc:.6f}")
    print(f"max_abs_i2_A={max_abs_i2:.6f}")
    print(f"growth_ratio_i1={growth_i1:.6f}")
    print(f"growth_ratio_vc={growth_vc:.6f}")
    print(f"growth_ratio_i2={growth_i2:.6f}")

    if reasons:
        print("review_reasons:")
        for item in reasons:
            print(f"- {item}")

    print(
        "note=Chequeo practico de no crecimiento no fisico en ventanas finales; "
        "no reemplaza una demostracion formal de estabilidad ni el analisis de control."
    )

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
