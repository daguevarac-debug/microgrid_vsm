"""Validate isolated grid-forming operation without an external grid.

Scope:
- Use only GridFormingFrequencyDynamics and a local electrical power P_e(t).
- Keep the GFM block disconnected from Microgrid, IEEE33 and main.py.
- Check steady islanded equilibrium with P_e = P_ref.
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
class IslandedMetrics:
    theta_initial: float
    theta_final: float
    omega_initial: float
    omega_final: float
    freq_initial_hz: float
    freq_final_hz: float
    max_abs_freq_deviation_hz: float


def _rad_s_to_hz(omega: np.ndarray | float) -> np.ndarray | float:
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
    t_end = 2.0
    t_eval = np.linspace(0.0, t_end, 1001)

    dynamics = GridFormingFrequencyDynamics(
        omega_ref=omega_ref,
        theta0=theta0,
        p_ref=p_ref,
        inertia_m=inertia_m,
        damping_d=damping_d,
    )

    def p_e_profile(_t: float) -> float:
        return p_ref

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
    freq_hz = _rad_s_to_hz(omega)
    all_finite = bool(np.all(np.isfinite(theta)) and np.all(np.isfinite(omega)))

    metrics = IslandedMetrics(
        theta_initial=float(theta[0]),
        theta_final=float(theta[-1]),
        omega_initial=float(omega[0]),
        omega_final=float(omega[-1]),
        freq_initial_hz=float(freq_hz[0]),
        freq_final_hz=float(freq_hz[-1]),
        max_abs_freq_deviation_hz=float(np.max(np.abs(freq_hz - 60.0))),
    )

    checks = {
        "theta_final > theta_initial": metrics.theta_final > metrics.theta_initial,
        "abs(freq_final_hz - 60.0) < 1e-6": abs(metrics.freq_final_hz - 60.0) < 1e-6,
        "theta and omega finite": all_finite,
        "no NaN/Inf": all_finite,
        "no forbidden grid imports": _forbidden_imports_absent(),
    }
    passed = all(checks.values())

    print("Grid-forming islanded operation validation")
    print("Scope: isolated GFM block with local P_e(t), no external grid.")
    print("\nParameters:")
    print(f"omega_ref={omega_ref:.9f} rad/s")
    print(f"theta0={theta0:.6f} rad")
    print(f"p_ref={p_ref:.3f} W")
    print(f"inertia_m={inertia_m:.6f}")
    print(f"damping_d={damping_d:.6f}")
    print(f"t_end={t_end:.3f} s")
    print("\nLocal power profile:")
    print("p_e(t)=p_ref")
    print("\nMetrics:")
    print(f"theta_initial={metrics.theta_initial:.9f} rad")
    print(f"theta_final={metrics.theta_final:.9f} rad")
    print(f"omega_initial={metrics.omega_initial:.9f} rad/s")
    print(f"omega_final={metrics.omega_final:.9f} rad/s")
    print(f"freq_initial_hz={metrics.freq_initial_hz:.9f} Hz")
    print(f"freq_final_hz={metrics.freq_final_hz:.9f} Hz")
    print(f"max_abs_freq_deviation_hz={metrics.max_abs_freq_deviation_hz:.9e} Hz")
    print("\nChecks:")
    for name, ok in checks.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    print(f"\nOverall status: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
