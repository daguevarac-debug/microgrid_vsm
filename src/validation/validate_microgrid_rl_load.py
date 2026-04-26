"""Validate the baseline balanced R-L load definition.

This check keeps the load-model validation intentionally small: it verifies the
nominal/moderate/severe P/fp conversions to finite inductive R-L loads and
confirms that the baseline dynamic simulation still runs without NaN/Inf values.
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
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid import BalancedRLLoad, Microgrid


P_NOM_TOL_W = 1e-6
P_STEP_TOL_W = 1e-6


def _load_for_fraction(step_fraction: float) -> BalancedRLLoad:
    return BalancedRLLoad.from_active_power(
        p_3ph_w=MICROGRID_LOAD_P_NOM_W_DEFAULT * (1.0 + step_fraction),
        power_factor=MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
        v_ln_rms=GRID_V_LN_RMS_DEFAULT,
        f_hz=GRID_FREQ_HZ_DEFAULT,
    )


def _z_abs(load: BalancedRLLoad) -> float:
    x_l_ohm = 2.0 * np.pi * load.f_hz * load.l_h
    return float(np.hypot(load.r_ohm, x_l_ohm))


def main() -> int:
    status = "PASS"
    reasons: list[str] = []

    nominal = _load_for_fraction(0.0)
    moderate = _load_for_fraction(MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
    severe = _load_for_fraction(MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT)
    loads = {
        "nominal": nominal,
        "moderate": moderate,
        "severe": severe,
    }

    finite_positive = all(
        np.isfinite(value) and value > 0.0
        for load in loads.values()
        for value in (load.p_3ph_w, load.r_ohm, load.l_h, load.q_3ph_var, _z_abs(load))
    )
    if not finite_positive:
        status = "REVIEW"
        reasons.append("R-L load values are not all finite and positive")

    if not (0.0 < nominal.power_factor <= 1.0):
        status = "REVIEW"
        reasons.append(f"power_factor={nominal.power_factor:.6f} outside (0, 1]")

    if abs(nominal.p_3ph_w - 3000.0) > P_NOM_TOL_W:
        status = "REVIEW"
        reasons.append(f"p_nominal={nominal.p_3ph_w:.6f} W is not approximately 3000 W")
    if abs(moderate.p_3ph_w - 3600.0) > P_STEP_TOL_W:
        status = "REVIEW"
        reasons.append(f"p_moderate={moderate.p_3ph_w:.6f} W is not approximately 3600 W")
    if abs(severe.p_3ph_w - 4200.0) > P_STEP_TOL_W:
        status = "REVIEW"
        reasons.append(f"p_severe={severe.p_3ph_w:.6f} W is not approximately 4200 W")

    if any(load.q_3ph_var <= 0.0 for load in loads.values()):
        status = "REVIEW"
        reasons.append("one or more Q values are not positive for inductive load")

    if not (_z_abs(nominal) > _z_abs(moderate) > _z_abs(severe)):
        status = "REVIEW"
        reasons.append("equivalent impedance does not decrease as P_load increases")

    model = Microgrid()
    if abs(model.p_load_1_w - nominal.p_3ph_w) > P_STEP_TOL_W:
        status = "REVIEW"
        reasons.append(f"default pre-step load={model.p_load_1_w:.6f} W is not nominal")
    if abs(model.p_load_2_w - moderate.p_3ph_w) > P_STEP_TOL_W:
        status = "REVIEW"
        reasons.append(f"default post-step load={model.p_load_2_w:.6f} W is not moderate +20%")
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
    print(f"power_factor={nominal.power_factor:.6f}")
    for name, load in loads.items():
        print(f"p_{name}_w={load.p_3ph_w:.6f}")
        print(f"q_{name}_var={load.q_3ph_var:.6f}")
        print(f"r_{name}_ohm={load.r_ohm:.6f}")
        print(f"l_{name}_h={load.l_h:.9f}")
        print(f"z_{name}_ohm={_z_abs(load):.6f}")
    print(f"default_pre_step_p_w={model.p_load_1_w:.6f}")
    print(f"default_post_step_p_w={model.p_load_2_w:.6f}")
    print(f"simulation_success={sol.success}")
    print(f"states_finite={bool(np.all(np.isfinite(sol.y)))}")
    if reasons:
        print("reasons=" + " | ".join(reasons))

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
