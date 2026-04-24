"""Validate isolated GFM frequency behavior for active-power scenarios.

Scope:
- Use GridFormingFrequencyDynamics without coupling it to Microgrid or PCC signals.
- Check frequency behavior for P_e = P_ref, P_e > P_ref and P_e < P_ref.
- Keep this validation isolated from external grid models.
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
class FrequencyScenario:
    name: str
    p_e_profile: object


@dataclass(frozen=True)
class FrequencyMetrics:
    scenario_name: str
    freq_initial_hz: float
    freq_min_hz: float
    freq_max_hz: float
    freq_min_post_step_hz: float
    freq_max_post_step_hz: float
    freq_final_hz: float
    max_frequency_drop_hz: float
    max_frequency_rise_hz: float
    all_finite: bool


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


def _simulate_scenario(
    dynamics: GridFormingFrequencyDynamics,
    scenario: FrequencyScenario,
    t_eval: np.ndarray,
    t_step: float,
) -> FrequencyMetrics:
    def rhs(t: float, x: np.ndarray) -> list[float]:
        return dynamics.rhs(t=t, x=x, p_e=float(scenario.p_e_profile(t)))

    sol = solve_ivp(
        rhs,
        (float(t_eval[0]), float(t_eval[-1])),
        dynamics.initial_state(),
        t_eval=t_eval,
        max_step=1e-3,
        rtol=1e-8,
        atol=1e-10,
    )
    assert sol.success, f"{scenario.name}: solve_ivp failed: {sol.message}"
    assert sol.y.shape[0] == 2, f"{scenario.name}: expected GFM state [theta, omega]."

    theta = sol.y[0]
    omega = sol.y[1]
    freq_hz = _rad_s_to_hz(omega)
    post_step = sol.t >= t_step
    freq_initial_hz = float(freq_hz[0])
    freq_min_hz = float(np.min(freq_hz))
    freq_max_hz = float(np.max(freq_hz))
    freq_min_post_step_hz = float(np.min(freq_hz[post_step]))
    freq_max_post_step_hz = float(np.max(freq_hz[post_step]))
    freq_final_hz = float(freq_hz[-1])

    return FrequencyMetrics(
        scenario_name=scenario.name,
        freq_initial_hz=freq_initial_hz,
        freq_min_hz=freq_min_hz,
        freq_max_hz=freq_max_hz,
        freq_min_post_step_hz=freq_min_post_step_hz,
        freq_max_post_step_hz=freq_max_post_step_hz,
        freq_final_hz=freq_final_hz,
        max_frequency_drop_hz=freq_initial_hz - freq_min_hz,
        max_frequency_rise_hz=freq_max_hz - freq_initial_hz,
        all_finite=bool(np.all(np.isfinite(theta)) and np.all(np.isfinite(omega))),
    )


def _scenario_passed(metrics: FrequencyMetrics) -> bool:
    if not metrics.all_finite:
        return False
    if metrics.scenario_name == "A_equilibrium":
        return abs(metrics.freq_final_hz - 60.0) < 1e-6
    if metrics.scenario_name == "B_load_increase":
        return metrics.freq_min_post_step_hz < 60.0 and metrics.max_frequency_drop_hz > 0.0
    if metrics.scenario_name == "C_load_reduction":
        return metrics.freq_max_post_step_hz > 60.0 and metrics.max_frequency_rise_hz > 0.0
    return False


def _print_metrics(metrics: FrequencyMetrics) -> None:
    print(f"\n--- {metrics.scenario_name} ---")
    print(f"freq_initial_hz={metrics.freq_initial_hz:.9f} Hz")
    print(f"freq_min_hz={metrics.freq_min_hz:.9f} Hz")
    print(f"freq_max_hz={metrics.freq_max_hz:.9f} Hz")
    print(f"freq_final_hz={metrics.freq_final_hz:.9f} Hz")
    print(f"max_frequency_drop_hz={metrics.max_frequency_drop_hz:.9f} Hz")
    print(f"max_frequency_rise_hz={metrics.max_frequency_rise_hz:.9f} Hz")
    print(f"finite_theta_omega={'PASS' if metrics.all_finite else 'FAIL'}")
    print(f"status={'PASS' if _scenario_passed(metrics) else 'FAIL'}")


def main() -> int:
    omega_ref = 2.0 * pi * 60.0
    theta0 = 0.0
    p_ref = 5000.0
    inertia_m = 1.0
    damping_d = 50.0
    t_end = 2.0
    t_step = 0.5
    delta_p = 500.0
    t_eval = np.linspace(0.0, t_end, 1001)

    dynamics = GridFormingFrequencyDynamics(
        omega_ref=omega_ref,
        theta0=theta0,
        p_ref=p_ref,
        inertia_m=inertia_m,
        damping_d=damping_d,
    )

    scenarios = [
        FrequencyScenario(name="A_equilibrium", p_e_profile=lambda _t: p_ref),
        FrequencyScenario(
            name="B_load_increase",
            p_e_profile=lambda t: p_ref if t < t_step else p_ref + delta_p,
        ),
        FrequencyScenario(
            name="C_load_reduction",
            p_e_profile=lambda t: p_ref if t < t_step else p_ref - delta_p,
        ),
    ]
    metrics = [
        _simulate_scenario(
            dynamics=dynamics,
            scenario=scenario,
            t_eval=t_eval,
            t_step=t_step,
        )
        for scenario in scenarios
    ]

    forbidden_imports_ok = _forbidden_imports_absent()
    passed = all(_scenario_passed(item) for item in metrics) and forbidden_imports_ok

    print("Grid-forming isolated frequency behavior validation")
    print("Scope: isolated GFM frequency dynamics, no Microgrid/PCC coupling.")
    print("\nParameters:")
    print(f"omega_ref={omega_ref:.9f} rad/s")
    print(f"theta0={theta0:.6f} rad")
    print(f"p_ref={p_ref:.3f} W")
    print(f"inertia_m={inertia_m:.6f}")
    print(f"damping_d={damping_d:.6f}")
    print(f"t_end={t_end:.3f} s")
    print(f"t_step={t_step:.3f} s")
    print(f"delta_p={delta_p:.3f} W")

    for item in metrics:
        _print_metrics(item)

    print("\nChecks:")
    print(f"no forbidden grid imports: {'PASS' if forbidden_imports_ok else 'FAIL'}")
    print(f"\nOverall status: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
