"""Step-3 quantitative validation for first-order BESS degradation model.

Scope:
- Validate z_deg/SoH/Q_eff/R0 consistency with the implemented equations.
- Keep Thevenin 1RC physics unchanged.
- Use OCV/R1/C1 parameterization loaded from literature-digitized Excel.
- Produce thesis-ready plots and summary tables.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
import sys

import matplotlib
import numpy as np
from scipy.integrate import solve_ivp

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bess.model import SecondLifeBattery1RC


MONO_TOL = 1e-8
SLOPE_RTOL = 2e-3
SLOPE_ATOL = 5e-8
Q_NOM_AH = 66.0
Q_AVAILABLE_2ND_LIFE_AH = 44.1
SOH_INITIAL = Q_AVAILABLE_2ND_LIFE_AH / Q_NOM_AH
R0_NOMINAL_OHM = 0.000970


@dataclass
class CaseResult:
    name: str
    t: np.ndarray
    i: np.ndarray
    soc: np.ndarray
    vrc: np.ndarray
    zdeg: np.ndarray
    soh: np.ndarray
    qeff: np.ndarray
    r0: np.ndarray
    vt: np.ndarray
    soc_expected: np.ndarray
    zdeg_expected: np.ndarray
    vt_residual: np.ndarray


def _build_model(**overrides) -> SecondLifeBattery1RC:
    repo_root = SRC_DIR.parent
    excel_path = repo_root / "OCV_SOC.xlsx"
    base = dict(
        excel_path=excel_path,
        q_nom_ah=Q_NOM_AH,
        soh_initial=SOH_INITIAL,
        r0_nominal_ohm=R0_NOMINAL_OHM,
        r0_soh_sensitivity=1.0,
        k_deg=1.478e-6,
        soh_min=0.50,
        q_eff_min_ah=1e-9,
        soc_initial=0.60,
        soc_min=0.10,
        soc_max=0.90,
    )
    base.update(overrides)
    # Parameterization note:
    # OCV(SoC), R1(SoC), C1(SoC) are loaded from literature-digitized Excel.
    return SecondLifeBattery1RC.from_excel_characterization(**base)


def _mae(x: np.ndarray) -> float:
    return float(np.mean(np.abs(x)))


def _rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def _integrate_rate(rate: np.ndarray, t: np.ndarray, x0: float) -> np.ndarray:
    """Trapezoidal integration of dx/dt samples on t-grid."""
    out = np.empty_like(rate, dtype=float)
    out[0] = float(x0)
    if len(rate) == 1:
        return out
    dt = np.diff(t)
    incr = 0.5 * (rate[:-1] + rate[1:]) * dt
    out[1:] = out[0] + np.cumsum(incr)
    return out


def _run_case(
    model: SecondLifeBattery1RC,
    name: str,
    t_eval: np.ndarray,
    i_profile,
    x0: list[float] | None = None,
) -> CaseResult:
    x0_local = model.initial_state_with_degradation() if x0 is None else x0
    assert len(x0_local) == 3, f"{name}: expected 3-state initial condition."

    def f(t: float, x: np.ndarray) -> list[float]:
        # `soh` is ignored by dynamic mode with x=[SoC, Vrc, z_deg], kept for compatibility.
        return model.rhs(t, x, i_bess=float(i_profile(t)), soh=model.soh_initial)

    sol = solve_ivp(
        f,
        (float(t_eval[0]), float(t_eval[-1])),
        x0_local,
        t_eval=t_eval,
        max_step=1.0,
        rtol=1e-7,
        atol=1e-9,
        # Fix: SoC event stop — step3 validation.
        events=model.soc_min_event,
        # Fix: SoC event stop — step3 validation.
        dense_output=False,
    )
    # Fix: SoC event stop — step3 validation.
    assert sol.status in (0, 1), f"{name}: solve_ivp failed -> {sol.message}"
    # Fix: SoC event stop — step3 validation.
    if sol.status == 1:
        print(
            f"  [{name}] SoC alcanzó soc_min en t={sol.t[-1]:.1f} s "
            f"(t_max solicitado: {t_eval[-1]:.1f} s)"
        )
    assert sol.y.shape[0] == 3, f"{name}: expected 3 states, got {sol.y.shape[0]}."

    t = sol.t
    soc = sol.y[0]
    vrc = sol.y[1]
    zdeg = sol.y[2]
    i = np.array([float(i_profile(tt)) for tt in t], dtype=float)
    soh = np.array([model.soh_from_z_deg(z) for z in zdeg], dtype=float)
    qeff = np.array([model.effective_capacity_from_z_deg(z) for z in zdeg], dtype=float)
    r0 = np.array([model.r0_from_z_deg(z) for z in zdeg], dtype=float)
    vt = np.array(
        [model.terminal_voltage(s, vr, i_bess=ib, soh=sh) for s, vr, ib, sh in zip(soc, vrc, i, soh)],
        dtype=float,
    )
    soc_rate_expected = -i / (3600.0 * qeff)
    zdeg_rate_expected = np.abs(i) / 3600.0
    soc_expected = _integrate_rate(soc_rate_expected, t=t, x0=float(soc[0]))
    zdeg_expected = _integrate_rate(zdeg_rate_expected, t=t, x0=float(zdeg[0]))
    vt_expected = np.array(
        [model.ocv(s) - ib * rr - vr for s, ib, rr, vr in zip(soc, i, r0, vrc)],
        dtype=float,
    )
    vt_residual = vt - vt_expected

    for signal_name, signal in (
        ("t", t),
        ("soc", soc),
        ("vrc", vrc),
        ("zdeg", zdeg),
        ("soh", soh),
        ("qeff", qeff),
        ("r0", r0),
        ("vt", vt),
        ("soc_expected", soc_expected),
        ("zdeg_expected", zdeg_expected),
        ("vt_residual", vt_residual),
    ):
        assert np.all(np.isfinite(signal)), f"{name}: {signal_name} contains NaN/Inf."

    return CaseResult(
        name=name,
        t=t,
        i=i,
        soc=soc,
        vrc=vrc,
        zdeg=zdeg,
        soh=soh,
        qeff=qeff,
        r0=r0,
        vt=vt,
        soc_expected=soc_expected,
        zdeg_expected=zdeg_expected,
        vt_residual=vt_residual,
    )


def _assert_core_degradation_consistency(model: SecondLifeBattery1RC, result: CaseResult) -> None:
    # z_deg is throughput, must be non-decreasing.
    assert np.all(np.diff(result.zdeg) >= -MONO_TOL), f"{result.name}: z_deg must be monotonic non-decreasing."
    # SoH bounded and non-increasing.
    assert np.all(result.soh >= model.soh_min - MONO_TOL), f"{result.name}: SoH fell below soh_min."
    assert np.all(np.diff(result.soh) <= MONO_TOL), f"{result.name}: SoH must be monotonic non-increasing."
    # R0 and Qeff consistency.
    assert np.all(np.diff(result.r0) >= -MONO_TOL), f"{result.name}: R0 must be monotonic non-decreasing."
    assert np.all(result.qeff > 0.0), f"{result.name}: Q_eff must stay strictly positive."
    # dz/dt consistency for constant-current windows.
    dt = np.diff(result.t)
    dz = np.diff(result.zdeg)
    slope = dz / dt
    i_mid = 0.5 * (result.i[:-1] + result.i[1:])
    target = np.abs(i_mid) / 3600.0
    # Ignore bins that straddle current discontinuities in piecewise profiles.
    const_mask = np.abs(np.diff(result.i)) < 1e-12
    assert np.allclose(slope[const_mask], target[const_mask], rtol=SLOPE_RTOL, atol=SLOPE_ATOL), (
        f"{result.name}: dz_deg/dt mismatch against |i|/3600."
    )


def _print_summary(result: CaseResult) -> None:
    print(f"\n--- {result.name} ---")
    print(f"soc_ini={result.soc[0]:.6f}, soc_fin={result.soc[-1]:.6f}")
    print(f"vrc_ini={result.vrc[0]:.6f}, vrc_fin={result.vrc[-1]:.6f}")
    print(f"zdeg_ini={result.zdeg[0]:.6f}, zdeg_fin={result.zdeg[-1]:.6f}")
    print(f"soh_ini={result.soh[0]:.6f}, soh_fin={result.soh[-1]:.6f}, soh_min={np.min(result.soh):.6f}")
    print(f"r0_ini={result.r0[0]:.6f}, r0_fin={result.r0[-1]:.6f}")
    print(f"qeff_ini={result.qeff[0]:.6f}, qeff_fin={result.qeff[-1]:.6f}")
    print(f"vt_min={np.min(result.vt):.6f}, vt_max={np.max(result.vt):.6f}")
    print(f"soc_mae={_mae(result.soc - result.soc_expected):.6e}, soc_rmse={_rmse(result.soc - result.soc_expected):.6e}")
    print(
        f"zdeg_mae={_mae(result.zdeg - result.zdeg_expected):.6e}, "
        f"zdeg_rmse={_rmse(result.zdeg - result.zdeg_expected):.6e}"
    )
    print(
        f"vt_identity_mae={_mae(result.vt_residual):.6e}, "
        f"vt_identity_rmse={_rmse(result.vt_residual):.6e}"
    )
    print("status=PASS")


def _plot_case(result: CaseResult, out_dir: Path) -> None:
    fig, axes = plt.subplots(6, 1, figsize=(10, 14), sharex=True)

    axes[0].plot(result.t, result.soc, color="tab:blue", label="SoC")
    axes[0].set_ylabel("SoC [-]")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    axes[1].plot(result.t, result.vrc, color="tab:orange", label="V_rc")
    axes[1].set_ylabel("V_rc [V]")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="best")

    axes[2].plot(result.t, result.zdeg, color="tab:brown", label="z_deg")
    axes[2].set_ylabel("z_deg [Ah]")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend(loc="best")

    axes[3].plot(result.t, result.soh, color="tab:green", label="SoH")
    axes[3].set_ylabel("SoH [-]")
    axes[3].grid(True, alpha=0.3)
    axes[3].legend(loc="best")

    axes[4].plot(result.t, result.r0, color="tab:red", label="R0")
    axes[4].set_ylabel("R0 [Ohm]")
    axes[4].grid(True, alpha=0.3)
    axes[4].legend(loc="best")

    axes[5].plot(result.t, result.vt, color="tab:purple", label="V_terminal")
    axes[5].step(result.t, result.i, where="post", color="tab:gray", alpha=0.4, label="i_bess [A]")
    axes[5].set_ylabel("Voltage / Current")
    axes[5].set_xlabel("Time [s]")
    axes[5].grid(True, alpha=0.3)
    axes[5].legend(loc="best")

    fig.suptitle(result.name)
    fig.tight_layout()
    out_file = out_dir / f"{result.name.lower().replace(' ', '_').replace(':', '')}.png"
    fig.savefig(out_file, dpi=150)
    plt.close(fig)


def _write_summary_csv(cases: list[CaseResult], out_dir: Path) -> None:
    metrics_path = out_dir / "summary_metrics.csv"
    cases_path = out_dir / "summary_cases.csv"

    with metrics_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case",
                "soc_mae",
                "soc_rmse",
                "zdeg_mae",
                "zdeg_rmse",
                "vt_identity_mae",
                "vt_identity_rmse",
            ],
        )
        writer.writeheader()
        for c in cases:
            writer.writerow(
                {
                    "case": c.name,
                    "soc_mae": f"{_mae(c.soc - c.soc_expected):.12e}",
                    "soc_rmse": f"{_rmse(c.soc - c.soc_expected):.12e}",
                    "zdeg_mae": f"{_mae(c.zdeg - c.zdeg_expected):.12e}",
                    "zdeg_rmse": f"{_rmse(c.zdeg - c.zdeg_expected):.12e}",
                    "vt_identity_mae": f"{_mae(c.vt_residual):.12e}",
                    "vt_identity_rmse": f"{_rmse(c.vt_residual):.12e}",
                }
            )

    with cases_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case",
                "q_nom_ah",
                "q_available_initial_ah",
                "soh_initial",
                "soc_ini",
                "soc_fin",
                "zdeg_ini_ah",
                "zdeg_fin_ah",
                "soh_fin",
                "qeff_fin_ah",
                "r0_ini_ohm",
                "r0_fin_ohm",
                "vt_min_v",
                "vt_max_v",
                "t_end_s",
            ],
        )
        writer.writeheader()
        for c in cases:
            writer.writerow(
                {
                    "case": c.name,
                    "q_nom_ah": f"{Q_NOM_AH:.6f}",
                    "q_available_initial_ah": f"{Q_AVAILABLE_2ND_LIFE_AH:.6f}",
                    "soh_initial": f"{SOH_INITIAL:.12f}",
                    "soc_ini": f"{c.soc[0]:.12f}",
                    "soc_fin": f"{c.soc[-1]:.12f}",
                    "zdeg_ini_ah": f"{c.zdeg[0]:.12f}",
                    "zdeg_fin_ah": f"{c.zdeg[-1]:.12f}",
                    "soh_fin": f"{c.soh[-1]:.12f}",
                    "qeff_fin_ah": f"{c.qeff[-1]:.12f}",
                    "r0_ini_ohm": f"{c.r0[0]:.12f}",
                    "r0_fin_ohm": f"{c.r0[-1]:.12f}",
                    "vt_min_v": f"{np.min(c.vt):.12f}",
                    "vt_max_v": f"{np.max(c.vt):.12f}",
                    "t_end_s": f"{c.t[-1]:.3f}",
                }
            )


def main(show_plots: bool = False) -> int:
    out_dir = SRC_DIR.parent / "outputs" / "validation" / "bess_step3"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Validation scope note:
    # This is a consistency-of-equations validation using literature-based
    # parameterization, not a fit against a measured experimental time series.

    # Case A: constant discharge.
    model = _build_model()
    t1 = np.linspace(0.0, 12.0 * 3600.0, 2401)
    case_1 = _run_case(
        model=model,
        name="Case A: Constant Discharge",
        t_eval=t1,
        i_profile=lambda _t: 8.0,
    )
    _assert_core_degradation_consistency(model, case_1)
    assert case_1.soc[-1] < case_1.soc[0], "Case 1: SoC should decrease under discharge."

    # Case B: pulse discharge-rest-charge.
    t2 = np.linspace(0.0, 6.0 * 3600.0, 1801)

    def i_profile_2(t: float) -> float:
        if t < 2.0 * 3600.0:
            return 10.0
        if t < 4.0 * 3600.0:
            return 0.0
        return -6.0

    case_2 = _run_case(
        model=model,
        name="Case B: Pulse Discharge-Rest-Charge",
        t_eval=t2,
        i_profile=i_profile_2,
    )
    _assert_core_degradation_consistency(model, case_2)
    assert np.all(np.diff(case_2.zdeg) >= -MONO_TOL), "Case 2: z_deg should remain non-decreasing."
    # Rest window: z_deg slope should be ~0.
    rest_mask = (case_2.t[:-1] >= 2.0 * 3600.0) & (case_2.t[:-1] < 4.0 * 3600.0)
    dzdt_rest = np.diff(case_2.zdeg)[rest_mask] / np.diff(case_2.t)[rest_mask]
    assert np.allclose(dzdt_rest, 0.0, atol=1e-6), "Case 2: z_deg must remain constant at rest."

    cases = [case_1, case_2]
    for case in cases:
        _print_summary(case)
        _plot_case(case, out_dir)
    _write_summary_csv(cases, out_dir)

    print(f"\nValidation plots saved to: {out_dir}")
    print(f"Summary table: {out_dir / 'summary_cases.csv'}")
    print(f"Metrics table: {out_dir / 'summary_metrics.csv'}")
    print("\nOverall status: PASS")

    if show_plots:
        from matplotlib import image as mpimg

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        axes = axes.ravel()
        for ax, case in zip(axes, cases):
            p = out_dir / f"{case.name.lower().replace(' ', '_').replace(':', '')}.png"
            ax.imshow(mpimg.imread(p))
            ax.set_title(case.name)
            ax.axis("off")
        fig.tight_layout()
        plt.show()

    return 0


if __name__ == "__main__":
    show = "--show" in sys.argv
    raise SystemExit(main(show_plots=show))
