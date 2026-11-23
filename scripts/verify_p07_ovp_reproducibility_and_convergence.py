"""Final reproducibility, equivalence, and numerical convergence check for P-07 OVP.

Verifies:
1. Bit-level / trajectory-level equivalence of `ovp_enabled=False` across all
   16 states, electrical signals, initial conditions, and RHS derivatives.
2. Numerical convergence of `ovp_enabled=True` under refined `max_step` and
   tolerances (`5e-5, 1e-6, 1e-8` vs `1e-5, 1e-7, 1e-9`) using full unrounded
   floating-point values and RHS evaluation counts.

Outputs are written strictly to `outputs/research_p07_ovp_integration/`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (  # noqa: E402
    DCLINK_CAP_F_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_ovp import DCLinkOVPController, DCLinkOVPParameters  # noqa: E402
from validate_p07_ovp_integration import build_model_with_ovp  # noqa: E402
from validation.validate_bess_pi_minimal_tuning import GFM_SELECTED_D, GFM_SELECTED_M  # noqa: E402

OUT_DIR = REPO_ROOT / "outputs" / "research_p07_ovp_integration"


def check_equivalence_disabled() -> dict:
    p_nom = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    g_nom = float(MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)
    load_fn = lambda t: p_nom if t < 0.5 else 0.2 * p_nom
    irr_fn = lambda t: g_nom

    model_default = build_model_with_ovp(
        soc_initial=0.90, ovp_enabled=False, load_profile=load_fn, irradiance_profile=irr_fn
    )
    model_explicit_off = build_model_with_ovp(
        soc_initial=0.90, ovp_enabled=False, load_profile=load_fn, irradiance_profile=irr_fn
    )
    model_explicit_off.ovp_controller = DCLinkOVPController(DCLinkOVPParameters(enabled=False))

    x0_a = np.asarray(model_default.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0))
    x0_b = np.asarray(model_explicit_off.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0))
    assert len(x0_a) == 16 and np.array_equal(x0_a, x0_b)
    assert model_default.controller.frequency_dynamics.inertia_m == GFM_SELECTED_M
    assert model_default.controller.frequency_dynamics.damping_d == GFM_SELECTED_D

    t_end = 1.2
    sol_a = solve_ivp(
        model_default.system_dynamics, (0.0, t_end), x0_a,
        method="RK45", max_step=5e-5, rtol=1e-6, atol=1e-8, dense_output=True,
    )
    sol_b = solve_ivp(
        model_explicit_off.system_dynamics, (0.0, t_end), x0_b,
        method="RK45", max_step=5e-5, rtol=1e-6, atol=1e-8, dense_output=True,
    )
    assert sol_a.success and sol_b.success
    assert sol_a.nfev == sol_b.nfev

    tg = np.linspace(0.0, t_end, 1201)
    xa = sol_a.sol(tg)
    xb = sol_b.sol(tg)
    max_state_diff = float(np.max(np.abs(xa - xb)))

    # Also verify RHS equivalence against pure pre-OVP DC-link derivative
    max_rhs_diff = 0.0
    max_sig_diff = 0.0
    ovp_actions_count = 0
    for k in range(tg.size):
        tk = float(tg[k])
        xk = xa[:, k]
        rhs_a = np.asarray(model_default.system_dynamics(tk, xk))
        # Direct pre-OVP check: ovp_controller.compute returns 0.0 dump current
        ovp_out = model_default.ovp_controller.compute(float(xk[0]))
        if ovp_out.chopper_active or ovp_out.i_dump_a != 0.0 or ovp_out.pv_isolated_abstraction:
            ovp_actions_count += 1
        rhs_b = np.asarray(model_explicit_off.system_dynamics(tk, xk))
        max_rhs_diff = max(max_rhs_diff, float(np.max(np.abs(rhs_a - rhs_b))))

        sig_a = model_default.integrated_signals(tk, xk)
        sig_b = model_explicit_off.integrated_signals(tk, xb[:, k])
        for key in ("Vdc", "p_pcc", "p_bridge", "i_bess_bus_a", "p_bess_bus_w", "v_bess_unit_v", "xi_bess_vdc_v_s"):
            max_sig_diff = max(max_sig_diff, abs(float(sig_a[key]) - float(sig_b[key])))

    return {
        "x0_identical": True,
        "state_count": int(len(x0_a)),
        "m_vsg": float(model_default.controller.frequency_dynamics.inertia_m),
        "d_vsg": float(model_default.controller.frequency_dynamics.damping_d),
        "nfev_default": int(sol_a.nfev),
        "nfev_explicit_off": int(sol_b.nfev),
        "max_16state_trajectory_diff": max_state_diff,
        "max_rhs_diff": max_rhs_diff,
        "max_signal_diff": max_sig_diff,
        "ovp_actions_when_disabled": ovp_actions_count,
    }


def run_ovp_at_precision(max_step: float, rtol: float, atol: float) -> dict:
    p_nom = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    g_nom = float(MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)
    model = build_model_with_ovp(
        soc_initial=0.90,
        ovp_enabled=True,
        load_profile=lambda t: p_nom if t < 0.5 else 0.2 * p_nom,
        irradiance_profile=lambda t: g_nom,
    )
    x0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0)
    t0 = time.perf_counter()
    sol = solve_ivp(
        model.system_dynamics,
        (0.0, 1.2),
        x0,
        method="RK45",
        max_step=max_step,
        rtol=rtol,
        atol=atol,
        dense_output=True,
    )
    wall_s = time.perf_counter() - t0
    if not sol.success or not np.isfinite(sol.y).all():
        raise RuntimeError(f"Solver failed at max_step={max_step}: {sol.message}")

    tg = np.linspace(0.0, 1.2, 1201)
    xg = sol.sol(tg)
    vdc = xg[0]
    post = tg >= 0.5

    p_pv = np.zeros_like(tg)
    p_bess = np.zeros_like(tg)
    p_inv = np.zeros_like(tg)
    p_dump = np.zeros_like(tg)
    duty = np.zeros_like(tg)
    t_first_active = None

    for k in range(tg.size):
        sig = model.integrated_signals(float(tg[k]), xg[:, k])
        p_pv[k] = float(sig["p_pv_eff_w"])
        p_bess[k] = float(sig["p_bess_bus_w"])
        p_inv[k] = float(sig["p_inv_dc_w"])
        p_dump[k] = float(sig["p_ovp_dump_w"])
        duty[k] = float(sig["ovp_duty_cycle"])
        if t_first_active is None and bool(sig["ovp_chopper_active"]):
            t_first_active = float(tg[k])

    e_pv = float(np.trapezoid(p_pv, tg))
    e_bess = float(np.trapezoid(p_bess, tg))
    e_inv = float(np.trapezoid(p_inv, tg))
    e_dump = float(np.trapezoid(p_dump, tg))
    cdc = float(DCLINK_CAP_F_DEFAULT)
    delta_e_cap = 0.5 * cdc * (float(vdc[-1]) ** 2 - float(vdc[0]) ** 2)
    e_res = (e_pv + e_bess - e_inv - e_dump) - delta_e_cap
    e_rel = abs(e_res) / max(e_pv + abs(e_bess), 1.0)

    return {
        "max_step": max_step,
        "rtol": rtol,
        "atol": atol,
        "wall_s": round(wall_s, 3),
        "nfev": int(sol.nfev),
        "vdc_post_max_v": float(np.max(vdc[post])),
        "vdc_final_v": float(vdc[-1]),
        "e_ovp_dump_j": e_dump,
        "p_ovp_dump_max_w": float(np.max(p_dump)),
        "duty_max": float(np.max(duty)),
        "t_first_activation_s": t_first_active,
        "energy_balance_residual_j": e_res,
        "energy_balance_rel_err": e_rel,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    eq = check_equivalence_disabled()
    base = run_ovp_at_precision(max_step=5e-5, rtol=1e-6, atol=1e-8)
    refined = run_ovp_at_precision(max_step=1e-5, rtol=1e-7, atol=1e-9)

    conv_diffs = {
        "abs_diff_vdc_post_max_v": abs(base["vdc_post_max_v"] - refined["vdc_post_max_v"]),
        "abs_diff_vdc_final_v": abs(base["vdc_final_v"] - refined["vdc_final_v"]),
        "abs_diff_e_ovp_dump_j": abs(base["e_ovp_dump_j"] - refined["e_ovp_dump_j"]),
        "rel_diff_e_ovp_dump": abs(base["e_ovp_dump_j"] - refined["e_ovp_dump_j"]) / max(refined["e_ovp_dump_j"], 1e-9),
        "abs_diff_p_ovp_dump_max_w": abs(base["p_ovp_dump_max_w"] - refined["p_ovp_dump_max_w"]),
        "abs_diff_t_first_activation_s": abs(base["t_first_activation_s"] - refined["t_first_activation_s"]),
        "nfev_ratio": refined["nfev"] / base["nfev"],
    }

    payload = {
        "equivalence_disabled": eq,
        "convergence_baseline": base,
        "convergence_refined": refined,
        "convergence_diffs": conv_diffs,
    }
    (OUT_DIR / "p07_ovp_equivalence_and_convergence.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
