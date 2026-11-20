"""Minimal reproducible boundary audit: UVLO (200 V) and upper Vdc overvoltage (no OVP).

Preserves all protected equations, M=80, D=1500, 16-state vector, and config constants.
Evaluates three short stress scenarios (50 Hz, MicrogridWithBESSDCDC):
1. overvoltage_socmax_load_rejection: soc(0)=0.90 (charge blocked), load -80% at t=0.5s.
2. overvoltage_bess_active_load_rejection: soc(0)=0.60 (BESS absorbs), load -80% at t=0.5s.
3. uvlo_irradiance_collapse_no_bess: bess_enabled=False, G: 800->0 W/m^2 at t=0.5s.

Outputs are saved strictly in `outputs/audit_obj2_review_closure/`.
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
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_UVLO_V_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from validation.validate_bess_dcdc_50hz import _build_dcdc_model  # noqa: E402

OUT_DIR = REPO_ROOT / "outputs" / "audit_obj2_review_closure"


def run_stress(
    label: str,
    *,
    bess_enabled: bool,
    soc_initial: float,
    t_end: float,
    load_profile,
    irradiance_profile,
) -> dict:
    t0 = time.perf_counter()
    model = _build_dcdc_model(
        freq_hz=50.0,
        soc_initial=soc_initial,
        bess_enabled=bess_enabled,
        load_profile=load_profile,
        irradiance_profile=irradiance_profile,
    )
    x0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT, xi_bess_vdc0_v_s=0.0)
    sol = solve_ivp(
        model.system_dynamics,
        (0.0, t_end),
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

    tg = np.linspace(0.0, t_end, int(round(t_end / 0.001)) + 1)
    xg = sol.sol(tg)
    vdc = xg[0]
    freq = xg[10] / (2.0 * np.pi)
    soc = xg[12]

    post = tg >= 0.5
    uvlo_samples = 0
    uvlo_violations = 0
    max_i_bus_abs = 0.0
    min_i_bus = 1e9
    max_i_bus = -1e9
    for k in range(tg.size):
        sig = model.integrated_signals(float(tg[k]), xg[:, k])
        i_bus = float(sig["i_bess_bus_a"])
        max_i_bus_abs = max(max_i_bus_abs, abs(i_bus))
        min_i_bus = min(min_i_bus, i_bus)
        max_i_bus = max(max_i_bus, i_bus)
        if vdc[k] < MICROGRID_UVLO_V_DEFAULT:
            uvlo_samples += 1
            if abs(float(sig["p_bridge"])) > 1e-12 or abs(float(sig["p_inv_dc_w"])) > 1e-12:
                uvlo_violations += 1

    return {
        "case": label,
        "bess_enabled": bess_enabled,
        "soc_initial": soc_initial,
        "t_end_s": t_end,
        "wall_s": wall_s,
        "nfev": int(sol.nfev),
        "solver_success": bool(sol.success),
        "all_finite": bool(np.isfinite(sol.y).all()),
        "vdc_post_min_v": round(float(np.min(vdc[post])), 4),
        "vdc_post_max_v": round(float(np.max(vdc[post])), 4),
        "vdc_final_v": round(float(vdc[-1]), 4),
        "freq_post_min_hz": round(float(np.min(freq[post])), 6),
        "freq_post_max_hz": round(float(np.max(freq[post])), 6),
        "soc_final": round(float(soc[-1]), 6),
        "i_bus_min_a": round(min_i_bus, 4),
        "i_bus_max_a": round(max_i_bus, 4),
        "uvlo_threshold_v": float(MICROGRID_UVLO_V_DEFAULT),
        "uvlo_samples_below_threshold": uvlo_samples,
        "uvlo_bridge_power_violations": uvlo_violations,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p_nom = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    g_nom = float(MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)

    results = [
        run_stress(
            "overvoltage_socmax_load_rejection_m80pct",
            bess_enabled=True,
            soc_initial=0.90,
            t_end=1.2,
            load_profile=lambda t: p_nom if t < 0.5 else 0.2 * p_nom,
            irradiance_profile=lambda t: g_nom,
        ),
        run_stress(
            "overvoltage_bess_active_load_rejection_m80pct",
            bess_enabled=True,
            soc_initial=0.60,
            t_end=1.2,
            load_profile=lambda t: p_nom if t < 0.5 else 0.2 * p_nom,
            irradiance_profile=lambda t: g_nom,
        ),
        run_stress(
            "uvlo_irradiance_collapse_no_bess",
            bess_enabled=False,
            soc_initial=0.60,
            t_end=1.0,
            load_profile=lambda t: p_nom,
            irradiance_profile=lambda t: g_nom if t < 0.5 else 0.0,
        ),
    ]
    out_path = OUT_DIR / "uvlo_and_overvoltage_audit.json"
    out_path.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
