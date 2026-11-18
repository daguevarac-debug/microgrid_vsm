"""Controlled step-size refinement audit for the 50 Hz +40% load-step VSG nadir.

Reproduces the step-refinement sensitivity campaign (50 us, 25 us, 12.5 us)
using RK45 with dense output and continuous bounded minimization on omega/(2*pi),
without modifying protected physical equations, M=80, D=1500, or PR #57 outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (  # noqa: E402
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from validation.validate_bess_dcdc_50hz import T_END_S, T_STEP_S, _build_dcdc_model  # noqa: E402

DEFAULT_AUDIT_DIR = REPO_ROOT / "outputs" / "audit_pending_review"
DEFAULT_BASELINE_JSON = REPO_ROOT / "outputs" / "validation" / "vsg_50hz_nadir_convergence_audit.json"


def run_case(
    *,
    max_step: float,
    rtol: float = 1e-8,
    atol: float = 1e-10,
    bess_enabled: bool,
    method: str = "RK45",
    t_end_s: float = T_END_S,
    dt_sample_s: float = 1e-4,
) -> dict:
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + float(MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT))

    def load_profile(t: float) -> float:
        return p_pre if t < T_STEP_S else p_post

    model = _build_dcdc_model(freq_hz=50.0, bess_enabled=bess_enabled, load_profile=load_profile)
    x0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)

    t0 = time.perf_counter()
    sol = solve_ivp(
        model.system_dynamics,
        (0.0, float(t_end_s)),
        x0,
        method=method,
        max_step=max_step,
        rtol=rtol,
        atol=atol,
        dense_output=True,
    )
    wall_s = time.perf_counter() - t0
    if not sol.success:
        raise RuntimeError(f"Solver failed: {sol.message}")

    n_s = int(round(t_end_s / dt_sample_s)) + 1
    tg = np.linspace(0.0, float(t_end_s), n_s)
    fg = sol.sol(tg)[10] / (2.0 * np.pi)
    post = tg >= T_STEP_S
    idx_min = int(np.argmin(fg[post]))
    f_grid_min = float(fg[post][idx_min])
    t_grid_min = float(tg[post][idx_min])

    opt = minimize_scalar(
        lambda tt: float(sol.sol(tt)[10] / (2.0 * np.pi)),
        bounds=(max(T_STEP_S, t_grid_min - 5.0 * dt_sample_s), min(t_end_s, t_grid_min + 5.0 * dt_sample_s)),
        method="bounded",
        options={"xatol": 1e-12},
    )

    flat_mask = tg >= min(3.2, float(t_end_s))
    f_flat_min = float(np.min(fg[flat_mask]))
    f_flat_max = float(np.max(fg[flat_mask]))
    probe_times = [pt for pt in (0.8918415, 2.0, 3.2673639, 4.0, 5.5, 6.4231, 6.5) if pt <= t_end_s]
    probes = {str(pt): float(sol.sol(pt)[10] / (2.0 * np.pi)) for pt in probe_times}

    return {
        "method": method,
        "max_step_s": max_step,
        "rtol": rtol,
        "atol": atol,
        "dt_sample_s": dt_sample_s,
        "t_end_s": float(t_end_s),
        "bess_enabled": bess_enabled,
        "wall_s": round(wall_s, 3),
        "nfev": int(sol.nfev),
        "n_steps": int(len(sol.t) - 1),
        "f_grid_min_hz": f_grid_min,
        "t_grid_min_s": t_grid_min,
        "f_cont_min_hz": float(opt.fun),
        "t_cont_min_s": float(opt.x),
        "flat_3p2_6p5_span_hz": f_flat_max - f_flat_min,
        "probes_hz": probes,
    }


def build_summary(audit_dir: Path, baseline_json: Path) -> list[dict]:
    base = json.loads(baseline_json.read_text(encoding="utf-8"))
    l1, l2 = base["levels"][0], base["levels"][1]
    b25 = json.loads((audit_dir / "nadir_25us_bess_true.json").read_text(encoding="utf-8"))
    n25 = json.loads((audit_dir / "nadir_25us_bess_false.json").read_text(encoding="utf-8"))
    b12 = json.loads((audit_dir / "nadir_12p5us_bess_true.json").read_text(encoding="utf-8"))
    n12 = json.loads((audit_dir / "nadir_12p5us_bess_false.json").read_text(encoding="utf-8"))

    rows = [
        ("L1_RK45_50us_tol1e-6", 50.0, "1e-6/1e-8", l1["bess_enabled"], l1["bess_disabled"], l1["wall_s"]),
        ("L2_RK45_50us_tol1e-8", 50.0, "1e-8/1e-10", l2["bess_enabled"], l2["bess_disabled"], l2["wall_s"]),
        ("L3_RK45_25us_tol1e-8", 25.0, "1e-8/1e-10", b25, n25, round(b25["wall_s"] + n25["wall_s"], 3)),
        ("L4_RK45_12.5us_tol1e-8", 12.5, "1e-8/1e-10", b12, n12, round(b12["wall_s"] + n12["wall_s"], 3)),
    ]

    summary = []
    for i, (name, h_us, tol, be, bd, wall) in enumerate(rows):
        df_cont = (be["f_cont_min_hz"] - bd["f_cont_min_hz"]) * 1e6
        df_grid = (be["f_grid_min_hz"] - bd["f_grid_min_hz"]) * 1e6
        entry = {
            "level": name,
            "max_step_us": h_us,
            "tol": tol,
            "f_bess_hz": be["f_cont_min_hz"],
            "t_bess_s": be["t_cont_min_s"],
            "f_nobess_hz": bd["f_cont_min_hz"],
            "t_nobess_s": bd["t_cont_min_s"],
            "df_cont_uhz": df_cont,
            "df_grid_uhz": df_grid,
            "nfev_bess": be["nfev"],
            "nfev_nobess": bd["nfev"],
            "wall_total_s": wall,
        }
        if i == 0:
            entry["delta_df_vs_prev_uhz"] = 0.0
            entry["delta_fbess_vs_prev_uhz"] = 0.0
            entry["delta_fnobess_vs_prev_uhz"] = 0.0
        else:
            prev = summary[i - 1]
            entry["delta_df_vs_prev_uhz"] = df_cont - prev["df_cont_uhz"]
            entry["delta_fbess_vs_prev_uhz"] = (entry["f_bess_hz"] - prev["f_bess_hz"]) * 1e6
            entry["delta_fnobess_vs_prev_uhz"] = (entry["f_nobess_hz"] - prev["f_nobess_hz"]) * 1e6
        summary.append(entry)

    out_summary = audit_dir / "nadir_step_convergence_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-step", type=float, default=2.5e-5, help="RK45 max_step in seconds.")
    parser.add_argument("--rtol", type=float, default=1e-8)
    parser.add_argument("--atol", type=float, default=1e-10)
    parser.add_argument("--bess", choices=["true", "false"], help="Run single case with bess_enabled=true/false.")
    parser.add_argument("--t-end", type=float, default=T_END_S, help="Simulation horizon in seconds (default 6.5).")
    parser.add_argument("--dt-sample", type=float, default=1e-4, help="Sampling grid step in seconds.")
    parser.add_argument("--out", type=Path, help="Output JSON path for single-case run.")
    parser.add_argument("--summarize", action="store_true", help="Rebuild summary JSON from existing level outputs.")
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE_JSON)
    args = parser.parse_args()

    if args.summarize:
        summary = build_summary(args.audit_dir.resolve(), args.baseline_json.resolve())
        print(f"Summary verified and saved ({len(summary)} levels).")
        return

    if args.bess is None or args.out is None:
        parser.error("Provide --bess {true,false} and --out PATH, or use --summarize.")

    res = run_case(
        max_step=args.max_step,
        rtol=args.rtol,
        atol=args.atol,
        bess_enabled=(args.bess == "true"),
        t_end_s=args.t_end,
        dt_sample_s=args.dt_sample,
    )
    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(
        f"DONE max_step={args.max_step} bess={args.bess} t_end={args.t_end}: "
        f"f_cont={res['f_cont_min_hz']:.12f} t={res['t_cont_min_s']:.6f} wall={res['wall_s']}s"
    )


if __name__ == "__main__":
    main()
