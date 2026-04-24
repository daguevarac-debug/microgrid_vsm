"""Validate isolated GFM frequency response to a load step.

Scope:
- Exercise GridFormingFrequencyDynamics without coupling it to Microgrid.
- Represent a post-step active-power deficit: P_e > P_ref.
- Check that frequency initially drops below omega_ref.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from math import pi
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.grid_forming import GridFormingFrequencyDynamics


@dataclass(frozen=True)
class StepResponseMetrics:
    omega_initial: float
    omega_min_post_step: float
    omega_final: float
    freq_initial_hz: float
    freq_pre_step_hz: float
    freq_min_post_step_hz: float
    freq_final_hz: float
    max_frequency_drop_hz: float
    power_imbalance_post_step: float


def _rad_s_to_hz(omega: float) -> float:
    return omega / (2.0 * pi)


def _forbidden_imports_absent() -> bool:
    source = THIS_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {"microgrid", "ieee33", "main", "pandapower"}
    forbidden_names = {"GridFollowingController"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_roots:
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_roots:
                return False
            if any(alias.name in forbidden_names for alias in node.names):
                return False
    return True


def main() -> int:
    omega_ref = 2.0 * pi * 60.0
    theta0 = 0.0
    p_ref = 5000.0
    inertia_m = 1.0
    damping_d = 50.0
    t_step = 0.5
    t_end = 2.0
    delta_p_load = 500.0
    t_eval = np.linspace(0.0, t_end, 1001)

    dynamics = GridFormingFrequencyDynamics(
        omega_ref=omega_ref,
        theta0=theta0,
        p_ref=p_ref,
        inertia_m=inertia_m,
        damping_d=damping_d,
    )

    def p_e_profile(t: float) -> float:
        if t < t_step:
            return p_ref
        return p_ref + delta_p_load

    def rhs(t: float, x: np.ndarray) -> list[float]:
        return dynamics.rhs(t=t, x=x, p_e=p_e_profile(t))

    sol = solve_ivp(
        rhs,
        (float(t_eval[0]), float(t_eval[-1])),
        dynamics.initial_state(),
        t_eval=t_eval,
        max_step=1e-3,
        rtol=1e-8,
        atol=1e-10,
    )
    assert sol.success, f"solve_ivp failed: {sol.message}"
    assert sol.y.shape[0] == 2, f"expected GFM state [theta, omega], got {sol.y.shape[0]} rows."

    theta = sol.y[0]
    omega = sol.y[1]
    pre_step = sol.t < t_step
    post_step = sol.t >= t_step

    all_finite = bool(np.all(np.isfinite(theta)) and np.all(np.isfinite(omega)))
    omega_initial = float(omega[0])
    omega_min_post_step = float(np.min(omega[post_step]))
    omega_final = float(omega[-1])
    freq_initial_hz = _rad_s_to_hz(omega_initial)
    freq_pre_step_hz = _rad_s_to_hz(float(omega[pre_step][-1]))
    freq_min_post_step_hz = _rad_s_to_hz(omega_min_post_step)
    freq_final_hz = _rad_s_to_hz(omega_final)
    max_frequency_drop_hz = freq_pre_step_hz - freq_min_post_step_hz
    power_imbalance_post_step = dynamics.power_imbalance(p_e=p_ref + delta_p_load)

    metrics = StepResponseMetrics(
        omega_initial=omega_initial,
        omega_min_post_step=omega_min_post_step,
        omega_final=omega_final,
        freq_initial_hz=freq_initial_hz,
        freq_pre_step_hz=freq_pre_step_hz,
        freq_min_post_step_hz=freq_min_post_step_hz,
        freq_final_hz=freq_final_hz,
        max_frequency_drop_hz=max_frequency_drop_hz,
        power_imbalance_post_step=power_imbalance_post_step,
    )

    checks = {
        "power_imbalance_post_step < 0": metrics.power_imbalance_post_step < 0.0,
        "freq_min_post_step_hz < freq_pre_step_hz": (
            metrics.freq_min_post_step_hz < metrics.freq_pre_step_hz
        ),
        "max_frequency_drop_hz > 0": metrics.max_frequency_drop_hz > 0.0,
        "theta and omega finite": all_finite,
        "no NaN/Inf": all_finite,
        "no forbidden grid imports": _forbidden_imports_absent(),
    }
    passed = all(checks.values())

    print("Grid-forming isolated step response validation")
    print("Scope: isolated x_gfm = [theta, omega], no Microgrid coupling.")
    print("\nParameters:")
    print(f"omega_ref={omega_ref:.9f} rad/s")
    print(f"theta0={theta0:.6f} rad")
    print(f"p_ref={p_ref:.3f} W")
    print(f"inertia_m={inertia_m:.6f}")
    print(f"damping_d={damping_d:.6f}")
    print(f"t_step={t_step:.3f} s")
    print(f"t_end={t_end:.3f} s")
    print(f"delta_p_load={delta_p_load:.3f} W")
    print("\nScenario:")
    print("pre-step: P_e = P_ref")
    print("post-step: P_e = P_ref + delta_p_load")
    print("expected qualitative response: frequency drops after the load increase")
    print("\nMetrics:")
    print(f"freq_initial_hz={metrics.freq_initial_hz:.9f} Hz")
    print(f"freq_pre_step_hz={metrics.freq_pre_step_hz:.9f} Hz")
    print(f"freq_min_post_step_hz={metrics.freq_min_post_step_hz:.9f} Hz")
    print(f"freq_final_hz={metrics.freq_final_hz:.9f} Hz")
    print(f"max_frequency_drop_hz={metrics.max_frequency_drop_hz:.9f} Hz")
    print(f"omega_initial={metrics.omega_initial:.9f} rad/s")
    print(f"omega_min_post_step={metrics.omega_min_post_step:.9f} rad/s")
    print(f"omega_final={metrics.omega_final:.9f} rad/s")
    print(f"power_imbalance_post_step={metrics.power_imbalance_post_step:.9f} W")
    print("\nNote:")
    print("This is a qualitative isolated validation; it is not a full microgrid or PCC-coupled frequency-regulation test.")
    print("\nChecks:")
    for name, ok in checks.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    print(f"\nOverall status: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
