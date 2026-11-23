"""Focused integration validation for optional P-07 DC-link OVP in 16-state model.

Evaluates ``DCLinkOVPController`` integrated into ``MicrogridWithBESSDCDC``
without altering protected equations, 16-state layout, or M=80, D=1500.

Outputs are written strictly to ``outputs/research_p07_ovp_integration/``.
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
    MICROGRID_UVLO_V_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_bess_pi import DCLinkBESSPIController  # noqa: E402
from controllers.dc_link_ovp import DCLinkOVPController, DCLinkOVPParameters  # noqa: E402
from controllers.gfm_controller import GFMController  # noqa: E402
from microgrid_bess_dcdc import MicrogridWithBESSDCDC, default_bat26_53_dcdc_parameters  # noqa: E402
from validation.compare_bess_soh_scenarios import _build_bess_for_soh, _nominal_soh  # noqa: E402
from validation.validate_bess_pi_minimal_tuning import (  # noqa: E402
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)
from validation.validate_gfm_integrated_system import _reference_active_power_w  # noqa: E402

OUT_DIR = REPO_ROOT / "outputs" / "research_p07_ovp_integration"


def build_model_with_ovp(
    *,
    soc_initial: float,
    ovp_enabled: bool,
    load_profile,
    irradiance_profile,
    r_dump_ohm: float = 25.0,
    pv_isolation_enabled: bool = False,
) -> MicrogridWithBESSDCDC:
    bess = _build_bess_for_soh(_nominal_soh())
    bess.soc_initial = float(soc_initial)
    controller = GFMController(
        f_hz=50.0,
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=PI_KP_W_PER_V,
        ki_w_per_v_s=PI_KI_W_PER_V_S,
    )
    ovp = (
        DCLinkOVPController(
            DCLinkOVPParameters(
                enabled=True,
                v_warn_v=357.0,
                v_on_v=374.0,
                v_hard_v=391.0,
                r_dump_ohm=r_dump_ohm,
                pv_isolation_enabled=pv_isolation_enabled,
            )
        )
        if ovp_enabled
        else None
    )
    return MicrogridWithBESSDCDC(
        controller=controller,
        dc_link_bess_pi=pi,
        bess_enabled=True,
        bess_model=bess,
        dcdc_parameters=default_bat26_53_dcdc_parameters(),
        p_bess_max_w=22440.0,
        ovp_controller=ovp,
        load_frequency_hz=50.0,
        load_profile=load_profile,
        irradiance_profile=irradiance_profile,
    )


def run_case(
    label: str,
    *,
    soc_initial: float,
    ovp_enabled: bool,
    load_profile,
    irradiance_profile,
    t_end_s: float = 1.2,
    r_dump_ohm: float = 25.0,
    pv_isolation_enabled: bool = False,
) -> tuple[dict, np.ndarray]:
    t0 = time.perf_counter()
    model = build_model_with_ovp(
        soc_initial=soc_initial,
        ovp_enabled=ovp_enabled,
        load_profile=load_profile,
        irradiance_profile=irradiance_profile,
        r_dump_ohm=r_dump_ohm,
        pv_isolation_enabled=pv_isolation_enabled,
    )
    x0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0)
    assert len(x0) == 16
    sol = solve_ivp(
        model.system_dynamics,
        (0.0, t_end_s),
        x0,
        method="RK45",
        max_step=5e-5,
        rtol=1e-6,
        atol=1e-8,
        dense_output=True,
    )
    wall_s = round(time.perf_counter() - t0, 3)
    if not sol.success or not np.isfinite(sol.y).all():
        raise RuntimeError(f"Solver failed for {label}: {sol.message}")

    dt = 0.001
    tg = np.linspace(0.0, t_end_s, int(round(t_end_s / dt)) + 1)
    xg = sol.sol(tg)
    vdc = xg[0]
    freq = xg[10] / (2.0 * np.pi)
    post = tg >= 0.5

    p_pv_eff = np.zeros_like(tg)
    p_bess_bus = np.zeros_like(tg)
    p_inv_dc = np.zeros_like(tg)
    p_dump = np.zeros_like(tg)
    i_dump = np.zeros_like(tg)
    duty = np.zeros_like(tg)
    chopper_active = np.zeros_like(tg, dtype=bool)
    uvlo_violations = 0

    for k in range(tg.size):
        sig = model.integrated_signals(float(tg[k]), xg[:, k])
        p_pv_eff[k] = float(sig["p_pv_eff_w"])
        p_bess_bus[k] = float(sig["p_bess_bus_w"])
        p_inv_dc[k] = float(sig["p_inv_dc_w"])
        p_dump[k] = float(sig["p_ovp_dump_w"])
        i_dump[k] = float(sig["i_ovp_dump_a"])
        duty[k] = float(sig["ovp_duty_cycle"])
        chopper_active[k] = bool(sig["ovp_chopper_active"])
        if vdc[k] < MICROGRID_UVLO_V_DEFAULT:
            if abs(float(sig["p_bridge"])) > 1e-12 or abs(float(sig["p_inv_dc_w"])) > 1e-12:
                uvlo_violations += 1

    e_pv = float(np.trapezoid(p_pv_eff, tg))
    e_bess = float(np.trapezoid(p_bess_bus, tg))
    e_inv = float(np.trapezoid(p_inv_dc, tg))
    e_dump = float(np.trapezoid(p_dump, tg))
    cdc = float(DCLINK_CAP_F_DEFAULT)
    delta_e_cap = 0.5 * cdc * (float(vdc[-1]) ** 2 - float(vdc[0]) ** 2)
    e_residual = (e_pv + e_bess - e_inv - e_dump) - delta_e_cap
    e_rel_err = abs(e_residual) / max(e_pv + abs(e_bess), 1.0)

    metrics = {
        "case": label,
        "ovp_enabled": ovp_enabled,
        "soc_initial": soc_initial,
        "wall_s": wall_s,
        "nfev": int(sol.nfev),
        "solver_success": bool(sol.success),
        "all_finite": bool(np.isfinite(sol.y).all()),
        "state_count": int(len(x0)),
        "m_vsg": GFM_SELECTED_M,
        "d_vsg": GFM_SELECTED_D,
        "vdc_post_min_v": round(float(np.min(vdc[post])), 4),
        "vdc_post_max_v": round(float(np.max(vdc[post])), 4),
        "vdc_final_v": round(float(vdc[-1]), 4),
        "freq_post_min_hz": round(float(np.min(freq[post])), 6),
        "freq_post_max_hz": round(float(np.max(freq[post])), 6),
        "t_averaged_chopper_active_s": round(float(np.sum(chopper_active) * dt), 4),
        "duty_max": round(float(np.max(duty)), 4),
        "i_ovp_dump_max_a": round(float(np.max(i_dump)), 3),
        "p_ovp_dump_max_w": round(float(np.max(p_dump)), 2),
        "e_ovp_dump_j": round(e_dump, 3),
        "e_pv_eff_j": round(e_pv, 3),
        "e_bess_bus_j": round(e_bess, 3),
        "e_inv_dc_j": round(e_inv, 3),
        "delta_e_cap_j": round(delta_e_cap, 3),
        "energy_balance_residual_j": round(e_residual, 4),
        "energy_balance_rel_err": float(e_rel_err),
        "uvlo_violations": uvlo_violations,
    }
    return metrics, vdc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p_nom = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    g_nom = float(MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)

    m_off_socmax, vdc_off_socmax = run_case(
        "socmax_m80pct_ovp_disabled_default",
        soc_initial=0.90,
        ovp_enabled=False,
        load_profile=lambda t: p_nom if t < 0.5 else 0.2 * p_nom,
        irradiance_profile=lambda t: g_nom,
    )
    m_on_socmax, vdc_on_socmax = run_case(
        "socmax_m80pct_ovp_enabled_r25",
        soc_initial=0.90,
        ovp_enabled=True,
        load_profile=lambda t: p_nom if t < 0.5 else 0.2 * p_nom,
        irradiance_profile=lambda t: g_nom,
    )
    m_on_soc060, _ = run_case(
        "bess_active_soc060_m80pct_ovp_enabled_r25",
        soc_initial=0.60,
        ovp_enabled=True,
        load_profile=lambda t: p_nom if t < 0.5 else 0.2 * p_nom,
        irradiance_profile=lambda t: g_nom,
    )
    m_on_g1000, _ = run_case(
        "socmax_g1000_m99pct_ovp_enabled_r25",
        soc_initial=0.90,
        ovp_enabled=True,
        load_profile=lambda t: p_nom if t < 0.5 else 0.01 * p_nom,
        irradiance_profile=lambda t: 1000.0,
    )

    # Assertions
    assert abs(m_off_socmax["vdc_post_max_v"] - 403.609) < 0.01
    assert m_on_socmax["vdc_post_max_v"] < 391.0
    assert m_on_soc060["e_ovp_dump_j"] == 0.0
    assert m_on_soc060["t_averaged_chopper_active_s"] == 0.0
    assert m_on_g1000["vdc_post_max_v"] < 391.0
    for m in (m_off_socmax, m_on_socmax, m_on_soc060, m_on_g1000):
        assert m["solver_success"] and m["all_finite"]
        assert m["energy_balance_rel_err"] < 5e-3
        assert m["uvlo_violations"] == 0

    results = [m_off_socmax, m_on_socmax, m_on_soc060, m_on_g1000]
    out_path = OUT_DIR / "p07_ovp_integration_results.json"
    out_path.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
