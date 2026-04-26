"""Validate the baseline balanced R-L load definition.

This check keeps the load-model validation intentionally small: it verifies the
nominal P/fp conversion to a finite inductive R-L load and confirms that the
baseline dynamic simulation still runs without NaN/Inf values.
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
    GRID_FREQ_HZ_DEFAULT,
    GRID_THETA0_RAD_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
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


P_NOM_TOL_W = 1e-6


def main() -> int:
    status = "PASS"
    reasons: list[str] = []

    load = BalancedRLLoad.from_active_power(
        p_3ph_w=MICROGRID_LOAD_P_NOM_W_DEFAULT,
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
        v_ln_rms=GRID_V_LN_RMS_DEFAULT,
        f_hz=GRID_FREQ_HZ_DEFAULT,
    )

    finite_positive = all(
        np.isfinite(value) and value > 0.0
        for value in (load.p_3ph_w, load.r_ohm, load.l_h, load.q_3ph_var)
    )
    if not finite_positive:
        status = "REVIEW"
        reasons.append("nominal R-L load values are not all finite and positive")

    if not (0.0 < load.power_factor <= 1.0):
        status = "REVIEW"
        reasons.append(f"power_factor={load.power_factor:.6f} outside (0, 1]")

    if abs(load.p_3ph_w - 3000.0) > P_NOM_TOL_W:
        status = "REVIEW"
        reasons.append(f"p_nominal={load.p_3ph_w:.6f} W is not approximately 3000 W")

    if load.q_3ph_var <= 0.0:
        status = "REVIEW"
        reasons.append(f"q_nominal={load.q_3ph_var:.6f} var is not positive for inductive load")

    model = Microgrid()
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

    if not sol.success:
        status = "REVIEW"
        reasons.append(f"solve_ivp unsuccessful: {sol.message}")
    if not np.all(np.isfinite(sol.y)):
        status = "REVIEW"
        reasons.append("baseline state vector contains NaN/Inf")

    print("validate_microgrid_rl_load")
    print(f"status={status}")
    print(f"p_nominal_w={load.p_3ph_w:.6f}")
    print(f"power_factor={load.power_factor:.6f}")
    print(f"q_nominal_var={load.q_3ph_var:.6f}")
    print(f"r_load_ohm={load.r_ohm:.6f}")
    print(f"l_load_h={load.l_h:.9f}")
    print(f"simulation_success={sol.success}")
    print(f"states_finite={bool(np.all(np.isfinite(sol.y)))}")
    if reasons:
        print("reasons=" + " | ".join(reasons))

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
