"""Validate SoH-dependent GFM inertial-support limits under a load step.

Scope:
- Use the real GFMController and the BESS supervision helpers from
  MicrogridWithBESS.
- Simulate the reduced GFM angular states [theta, omega] with a load step.
- Compare SoH = 1.00, SoH = 0.70 and the current nominal SoH case.
- Verify that the effective inertial-support power never exceeds the
  SoH-dependent BESS limit converted from DC to AC.

This validation isolates the power-limit policy. It is not a replacement for
full 15-state microgrid validation and does not modify model equations,
controller equations, sign conventions or state mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from pathlib import Path
import sys
import warnings

import numpy as np
from scipy.integrate import solve_ivp


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.model import SecondLifeBattery1RC
from config import (
    BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
    BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
    BESS_COUPLED_R0_DEFAULT,
    BESS_COUPLED_SOC_INIT_DEFAULT,
    BESS_COUPLED_SOC_MAX_DEFAULT,
    BESS_COUPLED_SOC_MIN_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS


P_REF_W = 30_000.0
INERTIA_M = 2.0
DAMPING_D = 50.0
T_STEP_S = 0.5
T_END_S = 1.5
DELTA_P_LOAD_W = 500.0
POWER_ATOL_W = 1e-6


@dataclass(frozen=True)
class ScenarioMetrics:
    label: str
    soh: float
    p_bess_dc_limit_w: float
    p_inertia_ac_limit_w: float
    p_inertia_ac_requested_w: float
    p_inertia_ac_min_w: float
    p_inertia_ac_max_w: float
    p_inertia_ac_expected_w: float
    p_cmd_w: float
    freq_pre_step_hz: float
    freq_min_post_step_hz: float
    max_frequency_drop_hz: float
    solver_success: bool
    finite_ok: bool
    cap_is_active: bool
    limit_respected: bool
    expected_power_matches: bool
    frequency_drop_ok: bool
    inertia_unchanged: bool


def _build_bess_for_soh(soh_case: float) -> SecondLifeBattery1RC:
    q_nom_ref_ah = BESS_COUPLED_Q_NOM_REF_AH_DEFAULT
    return SecondLifeBattery1RC(
        r0_nominal_ohm=BESS_COUPLED_R0_DEFAULT,
        q_nom_ref_ah=q_nom_ref_ah,
        q_init_case_ah=q_nom_ref_ah * soh_case,
        r0_soh_sensitivity=1.0,
        k_deg=1.478e-6,
        soh_min=0.50,
        q_eff_min_ah=1e-9,
        soc_initial=BESS_COUPLED_SOC_INIT_DEFAULT,
        soc_min=BESS_COUPLED_SOC_MIN_DEFAULT,
        soc_max=BESS_COUPLED_SOC_MAX_DEFAULT,
    )


def _power_vectors(p_e_w: float) -> tuple[np.ndarray, np.ndarray]:
    """Return finite vectors whose dot product equals the requested active power."""
    component = sqrt(max(float(p_e_w), 0.0))
    v_pcc = np.array([component, 0.0, 0.0], dtype=float)
    i2 = np.array([component, 0.0, 0.0], dtype=float)
    return v_pcc, i2


def _simulate_case(label: str, soh_case: float) -> ScenarioMetrics:
    controller = GFMController(
        p_ref=P_REF_W,
        inertia_m=INERTIA_M,
        damping_d=DAMPING_D,
    )
    bess = _build_bess_for_soh(soh_case)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        model = MicrogridWithBESS(
            controller=controller,
            bess_model=bess,
        )

    vdc = SIM_VDC0_V_DEFAULT
    soc_bess = model.bess.soc_initial
    soh_bess = model.bess.soh_init_case
    i_bess_max_available = model._available_i_bess_max(soh_bess)
    p_bess_dc_limit_w = model._available_p_bess_support_w(
        soc_bess=soc_bess,
        soh_bess=soh_bess,
    )
    p_inertia_ac_limit_w = p_bess_dc_limit_w * model.plant.eta

    ipv = model.plant.pv_current(
        vdc,
        MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
        MICROGRID_TEMPERATURE_C_DEFAULT,
    )
    p_pv_ac_available_w = max(vdc * ipv * model.plant.eta, 0.0)
    p_inertia_ac_requested_w = max(P_REF_W - p_pv_ac_available_w, 0.0)
    p_inertia_ac_expected_w = min(
        p_inertia_ac_requested_w,
        p_inertia_ac_limit_w,
    )

    def evaluate_control(t: float, theta: float, omega: float, p_e_w: float):
        v_pcc, i2 = _power_vectors(p_e_w)
        return controller.compute_control(
            t=t,
            theta=theta,
            xi_vdc=omega,
            vdc_eff=vdc,
            v_pcc=v_pcc,
            i1=np.zeros(3),
            i2=i2,
            plant=model.plant,
            ipv=ipv,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_limit_w,
        )

    initial_control = evaluate_control(
        t=0.0,
        theta=controller.modulator.theta0,
        omega=controller.omega_ref,
        p_e_w=0.0,
    )
    p_cmd_w = float(initial_control.p_cmd)

    def p_e_profile(t: float) -> float:
        if t < T_STEP_S:
            return p_cmd_w
        return p_cmd_w + DELTA_P_LOAD_W

    def rhs(t: float, x: np.ndarray) -> list[float]:
        control = evaluate_control(
            t=t,
            theta=float(x[0]),
            omega=float(x[1]),
            p_e_w=p_e_profile(t),
        )
        return [control.d_theta_dt, control.d_xi_vdc_dt]

    t_eval = np.linspace(0.0, T_END_S, 1501)
    sol = solve_ivp(
        rhs,
        (0.0, T_END_S),
        [controller.modulator.theta0, controller.omega_ref],
        t_eval=t_eval,
        max_step=1e-3,
        rtol=1e-8,
        atol=1e-10,
    )

    p_inertia_ac = np.zeros_like(sol.t, dtype=float)
    for k, tk in enumerate(sol.t):
        control = evaluate_control(
            t=float(tk),
            theta=float(sol.y[0, k]),
            omega=float(sol.y[1, k]),
            p_e_w=p_e_profile(float(tk)),
        )
        pv_contribution_w = min(P_REF_W, p_pv_ac_available_w)
        p_inertia_ac[k] = max(float(control.p_cmd) - pv_contribution_w, 0.0)

    frequency_hz = sol.y[1] / (2.0 * pi)
    pre_step = sol.t < T_STEP_S
    post_step = sol.t >= T_STEP_S
    freq_pre_step_hz = float(frequency_hz[pre_step][-1])
    freq_min_post_step_hz = float(np.min(frequency_hz[post_step]))
    max_frequency_drop_hz = freq_pre_step_hz - freq_min_post_step_hz

    finite_ok = bool(
        np.all(np.isfinite(sol.y))
        and np.all(np.isfinite(p_inertia_ac))
        and np.isfinite(p_bess_dc_limit_w)
        and np.isfinite(p_inertia_ac_limit_w)
    )
    cap_is_active = bool(
        p_inertia_ac_requested_w > p_inertia_ac_limit_w + POWER_ATOL_W
    )
    limit_respected = bool(
        np.all(p_inertia_ac <= p_inertia_ac_limit_w + POWER_ATOL_W)
        and np.all(p_inertia_ac >= -POWER_ATOL_W)
    )
    expected_power_matches = bool(
        np.allclose(
            p_inertia_ac,
            p_inertia_ac_expected_w,
            rtol=1e-10,
            atol=POWER_ATOL_W,
        )
    )
    frequency_drop_ok = bool(max_frequency_drop_hz > 0.0)
    inertia_unchanged = bool(
        np.isclose(
            controller.frequency_dynamics.inertia_m,
            INERTIA_M,
            rtol=0.0,
            atol=0.0,
        )
    )

    return ScenarioMetrics(
        label=label,
        soh=float(soh_bess),
        p_bess_dc_limit_w=float(p_bess_dc_limit_w),
        p_inertia_ac_limit_w=float(p_inertia_ac_limit_w),
        p_inertia_ac_requested_w=float(p_inertia_ac_requested_w),
        p_inertia_ac_min_w=float(np.min(p_inertia_ac)),
        p_inertia_ac_max_w=float(np.max(p_inertia_ac)),
        p_inertia_ac_expected_w=float(p_inertia_ac_expected_w),
        p_cmd_w=p_cmd_w,
        freq_pre_step_hz=freq_pre_step_hz,
        freq_min_post_step_hz=freq_min_post_step_hz,
        max_frequency_drop_hz=max_frequency_drop_hz,
        solver_success=bool(sol.success),
        finite_ok=finite_ok,
        cap_is_active=cap_is_active,
        limit_respected=limit_respected,
        expected_power_matches=expected_power_matches,
        frequency_drop_ok=frequency_drop_ok,
        inertia_unchanged=inertia_unchanged,
    )


def main() -> int:
    nominal_soh = (
        BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT
        / BESS_COUPLED_Q_NOM_REF_AH_DEFAULT
    )
    scenarios = (
        ("SoH_1p00", 1.0),
        ("SoH_0p70", 0.70),
        ("SoH_nominal", nominal_soh),
    )

    metrics = [_simulate_case(label, soh) for label, soh in scenarios]
    by_label = {item.label: item for item in metrics}

    scenario_checks = {
        item.label: all(
            (
                item.solver_success,
                item.finite_ok,
                item.cap_is_active,
                item.limit_respected,
                item.expected_power_matches,
                item.frequency_drop_ok,
                item.inertia_unchanged,
            )
        )
        for item in metrics
    }

    limit_order_ok = bool(
        by_label["SoH_1p00"].p_inertia_ac_limit_w
        > by_label["SoH_0p70"].p_inertia_ac_limit_w
        > by_label["SoH_nominal"].p_inertia_ac_limit_w
    )
    support_order_ok = bool(
        by_label["SoH_1p00"].p_inertia_ac_max_w
        > by_label["SoH_0p70"].p_inertia_ac_max_w
        > by_label["SoH_nominal"].p_inertia_ac_max_w
    )
    overall_pass = bool(
        all(scenario_checks.values())
        and limit_order_ok
        and support_order_ok
    )

    print("GFM + BESS inertial-support limit validation")
    print("Scope: reduced GFM load-step simulation with real BESS supervision limits.")
    print(f"p_ref={P_REF_W:.3f} W")
    print(f"inertia_m={INERTIA_M:.6f}")
    print(f"damping_d={DAMPING_D:.6f}")
    print(f"t_step={T_STEP_S:.3f} s")
    print(f"delta_p_load={DELTA_P_LOAD_W:.3f} W")
    print()

    for item in metrics:
        print(
            f"scenario={item.label} | SoH={item.soh:.6f} | "
            f"P_bess_dc_limit={item.p_bess_dc_limit_w:.6f} W | "
            f"P_inertia_ac_limit={item.p_inertia_ac_limit_w:.6f} W | "
            f"P_inertia_ac_max={item.p_inertia_ac_max_w:.6f} W | "
            f"P_cmd={item.p_cmd_w:.6f} W | "
            f"freq_drop={item.max_frequency_drop_hz:.9f} Hz | "
            f"status={'PASS' if scenario_checks[item.label] else 'FAIL'}"
        )

    print()
    print(f"limit_order_1p00_gt_0p70_gt_nominal: {'PASS' if limit_order_ok else 'FAIL'}")
    print(f"support_order_1p00_gt_0p70_gt_nominal: {'PASS' if support_order_ok else 'FAIL'}")
    print(f"Overall status: {'PASS' if overall_pass else 'FAIL'}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
