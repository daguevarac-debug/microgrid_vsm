"""Reproducible P-05 small-signal stability audit: two-timescale (frozen-slow-state) Floquet analysis.

Evaluates the 16-state GFM+BESS+PI and GFM+BESS+DC/DC architectures without modifying
any protected equations, M=80, D=1500, or state-vector mappings (AGENTS.md).

Methodology (singular perturbation / Tikhonov boundary-layer decomposition):
- Full 16-state vector:
    [Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c, i2_a, i2_b, i2_c,
     omega, theta, soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
- Fast + control boundary-layer subsystem (13 states):
    x_fast = [x[0:12], x[15]]  (electrical LCL + Vdc + VSG omega/theta + PI xi_bess_vdc)
    with slow battery states (soc_bess, vrc_bess, zdeg_bess) frozen at their settled
    quasi-static operating point.
- Extended 14-state subsystem:
    adds vrc_bess (1RC polarization, tau ~ 36 s), freezing only the non-periodic
    integrators (soc_bess, zdeg_bess).
- Computes exact one-electrical-period Floquet multipliers mu_k and continuous-time
  exponents lambda_k = ln(mu_k) / T, periodicity residuals, timescale separation
  ratios, and perturbation-step sensitivity (base 1e-6 vs 2e-6).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (  # noqa: E402
    GRID_FREQ_HZ_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_bess_pi import DCLinkBESSPIController  # noqa: E402
from controllers.gfm_controller import GFMController  # noqa: E402
from microgrid import Microgrid  # noqa: E402
from microgrid_bess_pi import MicrogridWithBESSPI  # noqa: E402
from validation.validate_bess_dcdc_50hz import _build_dcdc_model  # noqa: E402
from validation.validate_bess_pi_minimal_tuning import (  # noqa: E402
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)

OUTPUT_PATH = REPO_ROOT / "outputs" / "audit_p05_p09" / "p05_stability_audit.json"

STATE_NAMES_16 = (
    "Vdc", "i1_a", "i1_b", "i1_c", "vc_a", "vc_b", "vc_c",
    "i2_a", "i2_b", "i2_c", "omega", "theta",
    "soc_bess", "vrc_bess", "zdeg_bess", "xi_bess_vdc",
)
SCALES_16 = np.array(
    [340.0, 20.0, 20.0, 20.0, 250.0, 250.0, 250.0, 20.0, 20.0, 20.0,
     2.0 * np.pi * 60.0, 1.0, 1.0, 5.0, 1.0, 10.0],
    dtype=float,
)


def _reference_active_power_w() -> float:
    ref = Microgrid()
    return float(min(ref.P_ref_nominal, ref.p_available_ref))


def _build_bess_pi_60hz() -> MicrogridWithBESSPI:
    controller = GFMController(
        f_hz=GRID_FREQ_HZ_DEFAULT,
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=PI_KP_W_PER_V,
        ki_w_per_v_s=PI_KI_W_PER_V_S,
    )
    return MicrogridWithBESSPI(
        controller=controller,
        dc_link_bess_pi=pi,
        bess_enabled=True,
    )


def _integrate(rhs, x0: np.ndarray, t_end: float) -> np.ndarray:
    sol = solve_ivp(
        rhs,
        (0.0, float(t_end)),
        np.asarray(x0, dtype=float),
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    if not sol.success or not np.isfinite(sol.y).all():
        raise RuntimeError(f"solve_ivp failed: {sol.message}")
    return np.asarray(sol.y[:, -1], dtype=float)


def _frozen_floquet_audit(
    *,
    label: str,
    model: MicrogridWithBESSPI,
    freq_hz: float,
    active_indices: list[int],
    frozen_indices: list[int],
    settling_s: float = 1.0,
    eps_factors: tuple[float, float] = (1e-6, 2e-6),
) -> dict[str, Any]:
    t0 = time.perf_counter()
    period_s = 1.0 / float(freq_hz)
    x_init = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0)
    x_settled = _integrate(model.system_dynamics, x_init, settling_s)

    # Build frozen-slow-state RHS on active_indices while holding frozen_indices constant.
    frozen_vals = {idx: float(x_settled[idx]) for idx in frozen_indices}
    active_names = [STATE_NAMES_16[i] for i in active_indices]
    scales = SCALES_16[active_indices].copy()
    if 10 in active_indices:
        scales[active_indices.index(10)] = 2.0 * np.pi * float(freq_hz)

    def reduced_rhs(t: float, z: np.ndarray) -> np.ndarray:
        x_full = np.empty(16, dtype=float)
        for pos, idx in enumerate(active_indices):
            x_full[idx] = z[pos]
        for idx, val in frozen_vals.items():
            x_full[idx] = val
        dx_full = np.asarray(model.system_dynamics(t, x_full), dtype=float)
        return dx_full[active_indices]

    z0 = x_settled[active_indices].copy()
    # Settle one extra period in frozen mode to check exact periodicity.
    z_star = _integrate(reduced_rhs, z0, period_s)
    z_next = _integrate(reduced_rhs, z_star, period_s)

    diff = z_next - z_star
    theta_pos = active_indices.index(11)
    diff[theta_pos] -= 2.0 * np.pi
    scaled_residual = np.abs(diff) / scales

    # Central-difference monodromy matrix for both eps factors.
    def monodromy(eps_factor: float) -> np.ndarray:
        n = len(active_indices)
        J = np.zeros((n, n), dtype=float)
        for j in range(n):
            h = eps_factor * scales[j]
            zp = z_star.copy()
            zm = z_star.copy()
            zp[j] += h
            zm[j] -= h
            fp = _integrate(reduced_rhs, zp, period_s)
            fm = _integrate(reduced_rhs, zm, period_s)
            J[:, j] = (fp - fm) / (2.0 * h)
        return J

    J_base = monodromy(eps_factors[0])
    J_comp = monodromy(eps_factors[1])

    eigvals, eigvecs = np.linalg.eig(J_base)
    eigvals_comp = np.linalg.eigvals(J_comp)
    order = np.argsort(np.abs(eigvals))
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    eigvals_comp = eigvals_comp[np.argsort(np.abs(eigvals_comp))]

    modes: list[dict[str, Any]] = []
    non_neutral_max_mu = 0.0
    non_neutral_max_lambda_real = -np.inf
    zeta_min = np.inf
    pi_mode_info: dict[str, Any] | None = None
    vsg_mode_info: dict[str, Any] | None = None
    theta_mode_info: dict[str, Any] | None = None

    for k, (mu, mu_c) in enumerate(zip(eigvals, eigvals_comp), start=1):
        lam = np.log(complex(mu)) / period_s
        lam_c = np.log(complex(mu_c)) / period_s
        vec = np.abs(eigvecs[:, k - 1]) / scales
        vec_norm = vec / (np.linalg.norm(vec) + 1e-30)
        top_idx = np.argsort(vec_norm)[::-1][:3]
        top_states = [active_names[i] for i in top_idx]
        top_weights = [round(float(vec_norm[i]), 4) for i in top_idx]
        freq_modal_hz = abs(lam.imag) / (2.0 * np.pi)
        zeta = (-lam.real / abs(lam)) if (freq_modal_hz > 1e-3 and abs(lam) > 0.0) else None

        is_theta_symmetry = (top_states[0] == "theta" and abs(abs(mu) - 1.0) < 1e-3)
        if is_theta_symmetry:
            subsystem = "phase_symmetry_SO2"
        elif top_states[0] == "xi_bess_vdc":
            subsystem = "control_dc_link_pi"
        elif top_states[0] == "vrc_bess":
            subsystem = "battery_1rc_polarization"
        elif abs(lam.real + GFM_SELECTED_D / GFM_SELECTED_M) < 0.2 and abs(lam.imag) < 1e-3:
            subsystem = "control_vsg_swing"
        else:
            subsystem = "electrical_lcl_dclink"

        rec = {
            "mode_id": k,
            "subsystem": subsystem,
            "dominant_states": top_states,
            "dominant_weights": top_weights,
            "mu_real": float(mu.real),
            "mu_imag": float(mu.imag),
            "mu_magnitude": float(abs(mu)),
            "lambda_real_s_inv": float(lam.real),
            "lambda_imag_rad_s": float(lam.imag),
            "modal_frequency_hz": float(freq_modal_hz),
            "zeta": None if zeta is None else float(zeta),
            "delta_mu_sensitivity": float(abs(abs(mu) - abs(mu_c))),
            "delta_lambda_real_sensitivity": float(abs(lam.real - lam_c.real)),
        }
        modes.append(rec)

        if is_theta_symmetry:
            theta_mode_info = rec
        else:
            non_neutral_max_mu = max(non_neutral_max_mu, float(abs(mu)))
            non_neutral_max_lambda_real = max(non_neutral_max_lambda_real, float(lam.real))
            if zeta is not None:
                zeta_min = min(zeta_min, float(zeta))
        if subsystem == "control_dc_link_pi":
            pi_mode_info = rec
        if subsystem == "control_vsg_swing":
            vsg_mode_info = rec

    # Analytical slow battery rates at settled point.
    dx_settled = np.asarray(model.system_dynamics(settling_s, x_settled), dtype=float)
    r1_settled = float(model.bess.r1(float(x_settled[12])))
    c1_settled = float(model.bess.c1(float(x_settled[12])))
    tau_rc_s = r1_settled * c1_settled
    soc_rate = abs(float(dx_settled[12]))
    zdeg_rate = abs(float(dx_settled[14]))
    tau_soc_s = (1.0 / soc_rate) if soc_rate > 1e-18 else float("inf")
    tau_vsg_s = float(GFM_SELECTED_M / GFM_SELECTED_D)

    return {
        "label": label,
        "freq_hz": float(freq_hz),
        "period_s": float(period_s),
        "active_state_count": len(active_indices),
        "active_states": active_names,
        "frozen_states": {STATE_NAMES_16[i]: float(x_settled[i]) for i in frozen_indices},
        "wall_s": round(time.perf_counter() - t0, 3),
        "periodicity_residual": {
            "max_abs_scaled_residual": float(np.max(scaled_residual)),
            "l2_scaled_residual": float(np.linalg.norm(scaled_residual)),
            "theta_increment_error_rad": float(abs(diff[theta_pos])),
            "vdc_relative_error": float(abs(diff[0]) / max(abs(z_star[0]), 1.0)),
        },
        "summary": {
            "all_non_neutral_strictly_stable": bool(non_neutral_max_mu < 1.0 and non_neutral_max_lambda_real < 0.0),
            "non_neutral_max_mu_magnitude": float(non_neutral_max_mu),
            "non_neutral_max_lambda_real_s_inv": float(non_neutral_max_lambda_real),
            "zeta_min_oscillatory": float(zeta_min),
            "vsg_analytical_pole_s_inv": -float(GFM_SELECTED_D / GFM_SELECTED_M),
            "vsg_numerical_mode": vsg_mode_info,
            "pi_integrator_mode": pi_mode_info,
            "theta_symmetry_mode": theta_mode_info,
        },
        "timescale_separation": {
            "tau_vsg_s": tau_vsg_s,
            "tau_pi_s": (None if pi_mode_info is None or pi_mode_info["lambda_real_s_inv"] >= 0
                         else float(-1.0 / pi_mode_info["lambda_real_s_inv"])),
            "tau_rc_analytical_s": float(tau_rc_s),
            "lambda_rc_analytical_s_inv": float(-1.0 / tau_rc_s),
            "soc_drift_rate_per_s": float(soc_rate),
            "zdeg_drift_rate_ah_per_s": float(zdeg_rate),
            "tau_soc_characteristic_s": (None if not np.isfinite(tau_soc_s) else float(tau_soc_s)),
            "epsilon_vsg_over_rc": float(tau_vsg_s / tau_rc_s),
            "epsilon_vsg_over_soc": (0.0 if not np.isfinite(tau_soc_s) else float(tau_vsg_s / tau_soc_s)),
        },
        "modes": modes,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    active_13 = list(range(12)) + [15]
    frozen_3 = [12, 13, 14]

    results = {
        "m_vsg": float(GFM_SELECTED_M),
        "d_vsg": float(GFM_SELECTED_D),
        "pi_kp_w_per_v": float(PI_KP_W_PER_V),
        "pi_ki_w_per_v_s": float(PI_KI_W_PER_V_S),
        "cases": [
            _frozen_floquet_audit(
                label="bess_pi_60hz_13state_frozen_battery",
                model=_build_bess_pi_60hz(),
                freq_hz=GRID_FREQ_HZ_DEFAULT,
                active_indices=active_13,
                frozen_indices=frozen_3,
                settling_s=1.0,
            ),
            _frozen_floquet_audit(
                label="bess_dcdc_50hz_13state_frozen_battery",
                model=_build_dcdc_model(freq_hz=50.0, soc_initial=0.60, bess_enabled=True),
                freq_hz=50.0,
                active_indices=active_13,
                frozen_indices=frozen_3,
                settling_s=1.0,
            ),
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for c in results["cases"]:
        s = c["summary"]
        ts = c["timescale_separation"]
        print(json.dumps({
            "label": c["label"],
            "wall_s": c["wall_s"],
            "max_scaled_residual": c["periodicity_residual"]["max_abs_scaled_residual"],
            "all_non_neutral_strictly_stable": s["all_non_neutral_strictly_stable"],
            "non_neutral_max_mu": s["non_neutral_max_mu_magnitude"],
            "non_neutral_max_lambda_real": s["non_neutral_max_lambda_real_s_inv"],
            "zeta_min": s["zeta_min_oscillatory"],
            "pi_lambda_real": None if s["pi_integrator_mode"] is None else s["pi_integrator_mode"]["lambda_real_s_inv"],
            "vsg_lambda_real": None if s["vsg_numerical_mode"] is None else s["vsg_numerical_mode"]["lambda_real_s_inv"],
            "theta_mu": None if s["theta_symmetry_mode"] is None else s["theta_symmetry_mode"]["mu_magnitude"],
            "lambda_rc_analytical": ts["lambda_rc_analytical_s_inv"],
            "epsilon_vsg_over_rc": ts["epsilon_vsg_over_rc"],
            "epsilon_vsg_over_soc": ts["epsilon_vsg_over_soc"],
        }, indent=2))


if __name__ == "__main__":
    main()
