"""Reproducible stepped numerical sensitivity campaign for the +40% 50 Hz VSG nadir difference.

Evaluates whether the observed ~62.6 uHz difference between BESS-enabled and
BESS-disabled +40% load-step frequency nadirs persists under tolerance,
step-size, and higher-order method refinement, distinguishing local integrator
tolerance from effective global error.

Preserves M=80.0, D=1500.0, f_hz=50.0, and the protected 16-state vector.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import (  # noqa: E402
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from validation.validate_bess_dcdc_50hz import T_END_S, T_STEP_S, _build_dcdc_model  # noqa: E402

LEVELS = {
    "L1_RK45_base": ("RK45", 5e-5, 1e-6, 1e-8, 5e-4, T_END_S),
    "L2_RK45_tol": ("RK45", 5e-5, 1e-8, 1e-10, 1e-4, T_END_S),
    "L3_RK45_step": ("RK45", 2.5e-5, 1e-8, 1e-10, 1e-4, 4.0),
    "L4_DOP853_hi": ("DOP853", 5e-5, 1e-9, 1e-11, 1e-4, 4.0),
}


def run_level(name: str) -> dict:
    method, max_step, rtol, atol, dt_s, t_end = LEVELS[name]
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + float(MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT))

    def load_profile(t: float) -> float:
        return p_pre if t < T_STEP_S else p_post

    t0 = time.perf_counter()
    case_out = {}
    for bess_en in (True, False):
        m = _build_dcdc_model(freq_hz=50.0, bess_enabled=bess_en, load_profile=load_profile)
        x0 = m.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
        sol = solve_ivp(
            m.system_dynamics,
            (0.0, t_end),
            x0,
            method=method,
            max_step=max_step,
            rtol=rtol,
            atol=atol,
            dense_output=True,
        )
        if not sol.success:
            raise RuntimeError(f"{name} bess={bess_en} failed: {sol.message}")

        n_s = int(round(t_end / dt_s)) + 1
        tg = np.linspace(0.0, t_end, n_s)
        fg = sol.sol(tg)[10] / (2.0 * np.pi)
        post = tg >= T_STEP_S
        idx_min = int(np.argmin(fg[post]))
        f_grid_min = float(fg[post][idx_min])
        t_grid_min = float(tg[post][idx_min])

        opt = minimize_scalar(
            lambda tt: float(sol.sol(tt)[10] / (2.0 * np.pi)),
            bounds=(max(T_STEP_S, t_grid_min - 5.0 * dt_s), min(t_end, t_grid_min + 5.0 * dt_s)),
            method="bounded",
            options={"xatol": 1e-10},
        )
        key = "bess_enabled" if bess_en else "bess_disabled"
        case_out[key] = {
            "f_grid_min_hz": f_grid_min,
            "t_grid_min_s": t_grid_min,
            "f_cont_min_hz": float(opt.fun),
            "t_cont_min_s": float(opt.x),
            "nfev": int(sol.nfev),
        }

    wall_s = time.perf_counter() - t0
    df_grid_uhz = (case_out["bess_enabled"]["f_grid_min_hz"] - case_out["bess_disabled"]["f_grid_min_hz"]) * 1e6
    df_cont_uhz = (case_out["bess_enabled"]["f_cont_min_hz"] - case_out["bess_disabled"]["f_cont_min_hz"]) * 1e6
    entry = {
        "level": name,
        "method": method,
        "max_step_s": max_step,
        "rtol": rtol,
        "atol": atol,
        "dt_sample_s": dt_s,
        "t_end_s": t_end,
        "wall_s": round(wall_s, 3),
        "df_grid_uhz": df_grid_uhz,
        "df_cont_uhz": df_cont_uhz,
        **case_out,
    }
    print(
        f"{name:14s} | wall={wall_s:5.1f}s | "
        f"f_bess={case_out['bess_enabled']['f_cont_min_hz']:.9f} (t={case_out['bess_enabled']['t_cont_min_s']:.4f}s) | "
        f"f_nobess={case_out['bess_disabled']['f_cont_min_hz']:.9f} (t={case_out['bess_disabled']['t_cont_min_s']:.4f}s) | "
        f"df_grid={df_grid_uhz:+.3f} uHz | df_cont={df_cont_uhz:+.3f} uHz | "
        f"nfev=({case_out['bess_enabled']['nfev']},{case_out['bess_disabled']['nfev']})",
        flush=True,
    )
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", nargs="+", default=list(LEVELS.keys()), choices=list(LEVELS.keys()))
    args = parser.parse_args()

    out_path = ROOT / "outputs" / "validation" / "vsg_50hz_nadir_convergence_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        by_level = {item["level"]: item for item in existing.get("levels", [])}
    else:
        by_level = {}

    for name in args.levels:
        by_level[name] = run_level(name)
        ordered = [by_level[k] for k in LEVELS if k in by_level]
        out_path.write_text(
            json.dumps({"scenario": "50Hz_step40_bess_vs_nobess", "levels": ordered}, indent=2),
            encoding="utf-8",
        )

    print(f"Saved: {out_path}", flush=True)


if __name__ == "__main__":
    main()
