"""Robust Step-2 validation for BESS second-life 1RC dynamic model.

Scope:
- Validate dynamic behavior (SoC, V_rc, V_terminal) without changing physics.
- Keep baseline sign convention: i_bess > 0 discharge, i_bess < 0 charge.
- Use placeholder lookup data already embedded in bess_second_life.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib
import numpy as np
from scipy.integrate import solve_ivp

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bess.model import SecondLifeBattery1RC
from bess.capacity import Q_NOM_REF_NISSAN_LEAF_2P_AH, derive_q_init_case_ah


NUM_TOL = 1e-10
MONO_TOL = 1e-10
STATE_DIM = 2


@dataclass
class CaseResult:
    name: str
    passed: bool
    t: np.ndarray
    i: np.ndarray
    soc: np.ndarray
    vrc: np.ndarray
    vt: np.ndarray
    ocv: np.ndarray
    notes: str = ""


def _build_model() -> SecondLifeBattery1RC:
    """Model instance using current placeholders (no new real data injected)."""
    q_nom_ref_ah = Q_NOM_REF_NISSAN_LEAF_2P_AH
    q_init_case_ah = derive_q_init_case_ah(soh_init_case=0.80, q_nom_ref_ah=q_nom_ref_ah)
    return SecondLifeBattery1RC(
        q_nom_ref_ah=q_nom_ref_ah,
        q_init_case_ah=q_init_case_ah,
        r0_nominal_ohm=0.02,
        r0_soh_sensitivity=1.0,
        soc_initial=0.60,
        soc_min=0.10,
        soc_max=0.90,
    )


def _run_piecewise_case(
    model: SecondLifeBattery1RC,
    name: str,
    t_eval: np.ndarray,
    i_profile,
    soh_profile,
    x0: list[float] | None = None,
) -> CaseResult:
    x0_local = model.initial_state() if x0 is None else x0

    # Dimensional consistency (state must remain [SoC, V_rc]).
    assert len(x0_local) == STATE_DIM, f"{name}: expected state dimension {STATE_DIM}."

    def rhs_timevarying(t: float, x: np.ndarray) -> list[float]:
        return model.rhs(t, x, i_bess=float(i_profile(t)), soh=float(soh_profile(t)))

    sol = solve_ivp(
        rhs_timevarying,
        (float(t_eval[0]), float(t_eval[-1])),
        x0_local,
        t_eval=t_eval,
        max_step=0.5,
        rtol=1e-7,
        atol=1e-9,
    )
    assert sol.success, f"{name}: solve_ivp failed -> {sol.message}"
    assert sol.y.shape[0] == STATE_DIM, f"{name}: unexpected state rows {sol.y.shape[0]}."

    t = sol.t
    soc = sol.y[0]
    vrc = sol.y[1]
    i = np.array([float(i_profile(tt)) for tt in t], dtype=float)
    soh = np.array([float(soh_profile(tt)) for tt in t], dtype=float)
    ocv = np.array([model.ocv(s) for s in soc], dtype=float)
    vt = np.array(
        [model.terminal_voltage(s, vr, i_bess=ib, soh=sh) for s, vr, ib, sh in zip(soc, vrc, i, soh)],
        dtype=float,
    )

    # Numerical robustness checks.
    for signal_name, signal in (
        ("time", t),
        ("soc", soc),
        ("vrc", vrc),
        ("i", i),
        ("ocv", ocv),
        ("vt", vt),
    ):
        assert np.all(np.isfinite(signal)), f"{name}: {signal_name} contains NaN/Inf."

    return CaseResult(name=name, passed=True, t=t, i=i, soc=soc, vrc=vrc, vt=vt, ocv=ocv)


def _print_summary(result: CaseResult) -> None:
    soc_ini, soc_fin = float(result.soc[0]), float(result.soc[-1])
    vrc_ini, vrc_fin = float(result.vrc[0]), float(result.vrc[-1])
    vt_ini, vt_fin = float(result.vt[0]), float(result.vt[-1])
    vt_min, vt_max = float(np.min(result.vt)), float(np.max(result.vt))

    print(f"\n--- {result.name} ---")
    print(f"soc_ini={soc_ini:.6f}, soc_fin={soc_fin:.6f}")
    print(f"vrc_ini={vrc_ini:.6f}, vrc_fin={vrc_fin:.6f}")
    print(f"vt_ini={vt_ini:.6f}, vt_fin={vt_fin:.6f}")
    print(f"vt_min={vt_min:.6f}, vt_max={vt_max:.6f}")
    print(f"status={'PASS' if result.passed else 'FAIL'}")
    if result.notes:
        print(f"notes={result.notes}")


def _plot_case(result: CaseResult, out_dir: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True)

    axes[0].plot(result.t, result.soc, color="tab:blue", label="SoC")
    axes[0].set_ylabel("SoC [-]")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    axes[1].plot(result.t, result.vrc, color="tab:orange", label="V_rc")
    axes[1].set_ylabel("V_rc [V]")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="best")

    axes[2].plot(result.t, result.vt, color="tab:green", label="V_terminal")
    axes[2].plot(result.t, result.ocv, "--", color="tab:red", label="OCV")
    axes[2].set_ylabel("Voltage [V]")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend(loc="best")

    axes[3].step(result.t, result.i, where="post", color="tab:purple", label="i_bess")
    axes[3].set_ylabel("Current [A]")
    axes[3].set_xlabel("Time [s]")
    axes[3].grid(True, alpha=0.3)
    axes[3].legend(loc="best")

    fig.suptitle(result.name)
    fig.tight_layout()
    outfile = out_dir / f"{result.name.lower().replace(' ', '_').replace(':', '')}.png"
    fig.savefig(outfile, dpi=150)
    plt.close(fig)


def main(show_plots: bool = False) -> int:
    out_dir = SRC_DIR.parent / "outputs" / "validation" / "bess_step2"
    out_dir.mkdir(parents=True, exist_ok=True)

    model = _build_model()

    # Shared horizon for steady tests.
    t_eval = np.linspace(0.0, 300.0, 601)
    soh_fixed = 0.80

    # Case A: rest (i_bess = 0) with non-zero V_rc to check relaxation.
    case_a = _run_piecewise_case(
        model=model,
        name="Case A: Rest",
        t_eval=t_eval,
        i_profile=lambda _t: 0.0,
        soh_profile=lambda _t: soh_fixed,
        x0=[model.soc_initial, 0.12],
    )
    assert np.max(np.abs(case_a.soc - case_a.soc[0])) < 1e-7, "Case A: SoC drift at rest."
    assert abs(case_a.vrc[-1]) < abs(case_a.vrc[0]), "Case A: V_rc did not relax."
    # At rest, V_terminal = OCV - V_rc. Equivalence is expected after V_rc relaxation.
    tail_start = int(0.9 * len(case_a.t))
    assert np.max(np.abs(case_a.vt[tail_start:] - case_a.ocv[tail_start:])) < 5e-3, (
        "Case A: V_terminal not close to OCV during relaxed tail."
    )

    # Case B: constant discharge (i_bess > 0).
    i_discharge = 12.0
    case_b = _run_piecewise_case(
        model=model,
        name="Case B: Constant Discharge",
        t_eval=t_eval,
        i_profile=lambda _t: i_discharge,
        soh_profile=lambda _t: soh_fixed,
    )
    dsoc0_b = model.rhs(0.0, [case_b.soc[0], case_b.vrc[0]], i_bess=i_discharge, soh=soh_fixed)[0]
    assert dsoc0_b < 0.0, "Case B: dSoC/dt must be < 0 for discharge."
    assert np.all(np.diff(case_b.soc) <= MONO_TOL), "Case B: SoC must decrease monotonically."
    assert np.all(case_b.vt < case_b.ocv + NUM_TOL), "Case B: V_terminal must stay below OCV."

    # Case C: constant charge (i_bess < 0).
    i_charge = -12.0
    case_c = _run_piecewise_case(
        model=model,
        name="Case C: Constant Charge",
        t_eval=t_eval,
        i_profile=lambda _t: i_charge,
        soh_profile=lambda _t: soh_fixed,
    )
    dsoc0_c = model.rhs(0.0, [case_c.soc[0], case_c.vrc[0]], i_bess=i_charge, soh=soh_fixed)[0]
    assert dsoc0_c > 0.0, "Case C: dSoC/dt must be > 0 for charge."
    assert np.all(np.diff(case_c.soc) >= -MONO_TOL), "Case C: SoC must increase monotonically."
    assert float(np.mean(case_c.vt)) > float(np.mean(case_b.vt)), (
        "Case C: average V_terminal should be higher than discharge case."
    )

    # Case D: discharge-rest-charge pulse profile.
    t_eval_d = np.linspace(0.0, 900.0, 1801)

    def i_profile_d(t: float) -> float:
        if t < 300.0:
            return 12.0
        if t < 600.0:
            return 0.0
        return -8.0

    case_d = _run_piecewise_case(
        model=model,
        name="Case D: Pulse Discharge-Rest-Charge",
        t_eval=t_eval_d,
        i_profile=i_profile_d,
        soh_profile=lambda _t: soh_fixed,
    )
    idx_300 = int(np.searchsorted(case_d.t, 300.0))
    idx_600 = int(np.searchsorted(case_d.t, 600.0))
    vrc_rest_start = abs(case_d.vrc[idx_300])
    vrc_rest_end = abs(case_d.vrc[idx_600 - 1])
    assert vrc_rest_end < vrc_rest_start, "Case D: V_rc must relax during rest interval."

    # Case E: SoH sensitivity at same discharge current.
    i_e = 12.0
    t_eval_e = np.linspace(0.0, 600.0, 1201)
    soh_good = 0.90
    soh_bad = 0.60

    case_e_good = _run_piecewise_case(
        model=model,
        name="Case E1: SoH 0.90",
        t_eval=t_eval_e,
        i_profile=lambda _t: i_e,
        soh_profile=lambda _t: soh_good,
    )
    case_e_bad = _run_piecewise_case(
        model=model,
        name="Case E2: SoH 0.60",
        t_eval=t_eval_e,
        i_profile=lambda _t: i_e,
        soh_profile=lambda _t: soh_bad,
    )
    r0_good = model.r0(soh_good)
    r0_bad = model.r0(soh_bad)
    assert r0_bad > r0_good, "Case E: worse SoH must increase R0."
    assert model.effective_capacity_ah(soh_bad) < model.effective_capacity_ah(soh_good), (
        "Case E: worse SoH must reduce effective capacity."
    )
    # Same current and initial SoC: poorer SoH should end with lower terminal voltage.
    assert float(np.mean(case_e_bad.vt)) < float(np.mean(case_e_good.vt)), (
        "Case E: worse SoH should produce lower average terminal voltage."
    )

    cases = [case_a, case_b, case_c, case_d, case_e_good, case_e_bad]
    for result in cases:
        _print_summary(result)
        _plot_case(result, out_dir=out_dir)

    print(f"\nValidation plots saved to: {out_dir}")

    if show_plots:
        # Optional interactive mode for manual inspection.
        from matplotlib import image as mpimg

        fig, axes = plt.subplots(3, 2, figsize=(14, 10))
        axes = axes.ravel()
        for ax, result in zip(axes, cases):
            img_path = out_dir / f"{result.name.lower().replace(' ', '_').replace(':', '')}.png"
            ax.imshow(mpimg.imread(img_path))
            ax.set_title(result.name)
            ax.axis("off")
        fig.tight_layout()
        plt.show()

    print("\nOverall status: PASS")
    return 0


if __name__ == "__main__":
    show = "--show" in sys.argv
    raise SystemExit(main(show_plots=show))
