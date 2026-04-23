"""Entry point for dynamic baseline simulation and result plots."""

import argparse
from pathlib import Path

import matplotlib
import numpy as np
from scipy.integrate import solve_ivp

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import (
    GRID_THETA0_RAD_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    PV_CURVE_IRRADIANCE_LEVELS_W_PER_M2,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid import Microgrid, MicrogridWithBESS


def run_baseline_simulation(model: Microgrid) -> dict[str, np.ndarray]:
    """Run baseline dynamic simulation and return signals for plotting."""
    t_span = (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT)
    y0 = [
        SIM_VDC0_V_DEFAULT,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        GRID_THETA0_RAD_DEFAULT,
    ]

    sol = solve_ivp(
        model.system_dynamics,
        t_span,
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    t = sol.t
    vdc = sol.y[0]
    ia, ib, ic = sol.y[7], sol.y[8], sol.y[9]
    p_bridge = np.zeros_like(t)
    p_pcc = np.zeros_like(t)
    p_load = np.zeros_like(t)

    for k, tk in enumerate(t):
        xk = sol.y[:, k]
        p_bridge[k], p_pcc[k], _, _, _ = model.power_signals(tk, xk)
        i2k = xk[7:10]
        r_load_t = model.load_profile(tk)
        v_pcc_k = i2k * r_load_t
        p_load[k] = float(np.dot(v_pcc_k, i2k))

    return {
        "t": t,
        "vdc": vdc,
        "ia": ia,
        "ib": ib,
        "ic": ic,
        "p_bridge": p_bridge,
        "p_pcc": p_pcc,
        "p_load": p_load,
    }


def save_baseline_figures(model: Microgrid, signals: dict[str, np.ndarray], output_dir: Path) -> None:
    """Save baseline figures to disk without interactive blocking windows."""
    output_dir.mkdir(parents=True, exist_ok=True)
    t = signals["t"]
    vdc = signals["vdc"]
    ia = signals["ia"]
    ib = signals["ib"]
    ic = signals["ic"]
    p_pcc = signals["p_pcc"]
    p_load = signals["p_load"]
    p_bridge = signals["p_bridge"]

    fig1 = plt.figure()
    plt.plot(t, vdc)
    plt.axvline(model.t_step, linestyle="--")
    plt.title("PV + DC-link + LCL baseline averaged model: Vdc(t)")
    plt.xlabel("t [s]")
    plt.ylabel("Vdc [V]")
    plt.grid(True)
    fig1.savefig(output_dir / "baseline_vdc.png", dpi=180, bbox_inches="tight")
    plt.close(fig1)

    fig2 = plt.figure()
    plt.plot(t, ia, label="ia")
    plt.plot(t, ib, label="ib")
    plt.plot(t, ic, label="ic")
    plt.axvline(model.t_step, linestyle="--")
    plt.title("PV + DC-link + LCL baseline averaged model: corrientes trifasicas i2")
    plt.xlabel("t [s]")
    plt.ylabel("i [A]")
    plt.grid(True)
    plt.legend()
    fig2.savefig(output_dir / "baseline_i2_currents.png", dpi=180, bbox_inches="tight")
    plt.close(fig2)

    fig3 = plt.figure()
    plt.plot(t, p_pcc / 1000.0, label="p_pcc")
    plt.plot(t, p_load / 1000.0, label="p_load")
    plt.plot(t, p_bridge / 1000.0, label="p_bridge", alpha=0.8)
    plt.axvline(model.t_step, linestyle="--")
    plt.title("PV + DC-link + LCL baseline averaged model: potencias instantaneas")
    plt.xlabel("t [s]")
    plt.ylabel("P [kW]")
    plt.grid(True)
    plt.legend()
    fig3.savefig(output_dir / "baseline_power_signals.png", dpi=180, bbox_inches="tight")
    plt.close(fig3)

    fig4 = plt.figure()
    for g in PV_CURVE_IRRADIANCE_LEVELS_W_PER_M2:
        voltage, current, power = model.pv.pv_curve(G=g, T_c=MICROGRID_TEMPERATURE_C_DEFAULT)
        idx_mpp = np.argmax(power)
        plt.plot(voltage, current, label=f"G = {int(g)} W/m2")
        plt.plot(voltage[idx_mpp], current[idx_mpp], "ro")
    plt.axvline(SIM_VDC0_V_DEFAULT, linestyle="--", label="Vdc0")
    plt.title("Curvas I-V del arreglo fotovoltaico")
    plt.xlabel("V [V]")
    plt.ylabel("I [A]")
    plt.grid(True)
    plt.legend()
    fig4.savefig(output_dir / "baseline_pv_iv_curves.png", dpi=180, bbox_inches="tight")
    plt.close(fig4)

    fig5 = plt.figure()
    for g in PV_CURVE_IRRADIANCE_LEVELS_W_PER_M2:
        voltage, current, power = model.pv.pv_curve(G=g, T_c=MICROGRID_TEMPERATURE_C_DEFAULT)
        idx_mpp = np.argmax(power)
        plt.plot(voltage, power, label=f"G = {int(g)} W/m2")
        plt.plot(voltage[idx_mpp], power[idx_mpp], "ro")
    plt.axhline(model.P_ref_nominal, linestyle="--", label="P_ref_nominal")
    plt.title("Curvas P-V del arreglo fotovoltaico")
    plt.xlabel("V [V]")
    plt.ylabel("P [W]")
    plt.grid(True)
    plt.legend()
    fig5.savefig(output_dir / "baseline_pv_pv_curves.png", dpi=180, bbox_inches="tight")
    plt.close(fig5)

    print("\nFiguras baseline guardadas en outputs/:")
    print("  - baseline_vdc.png")
    print("  - baseline_i2_currents.png")
    print("  - baseline_power_signals.png")
    print("  - baseline_pv_iv_curves.png")
    print("  - baseline_pv_pv_curves.png")


def run_bess_integrated_simulation(model: MicrogridWithBESS) -> dict[str, np.ndarray]:
    """Run first-step integrated simulation with BESS coupled at DC bus."""
    t_span = (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT)
    y0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
    sol = solve_ivp(
        model.system_dynamics,
        t_span,
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    t = sol.t
    vdc = sol.y[0]
    p_bridge = np.zeros_like(t)
    p_pcc = np.zeros_like(t)
    p_load = np.zeros_like(t)
    i_bess = np.zeros_like(t)
    soc_bess = np.zeros_like(t)
    vt_bess = np.zeros_like(t)
    soh_bess = np.zeros_like(t)

    for k, tk in enumerate(t):
        sig = model.integrated_signals(tk, sol.y[:, k])
        p_bridge[k] = sig["p_bridge"]
        p_pcc[k] = sig["p_pcc"]
        p_load[k] = sig["p_load"]
        i_bess[k] = sig["i_bess"]
        soc_bess[k] = sig["soc_bess"]
        vt_bess[k] = sig["vt_bess"]
        soh_bess[k] = sig["soh_bess"]

    return {
        "t": t,
        "Vdc": vdc,
        "p_bridge": p_bridge,
        "p_pcc": p_pcc,
        "p_load": p_load,
        "i_bess": i_bess,
        "soc_bess": soc_bess,
        "vt_bess": vt_bess,
        "soh_bess": soh_bess,
    }


def _vdc_metrics(t: np.ndarray, vdc: np.ndarray, vdc_ref: float, t_step: float) -> dict[str, float]:
    """Compute simple Vdc metrics for step-response comparison."""
    pre_mask = t < t_step
    post_mask = t >= t_step
    vdc_pre = float(vdc[pre_mask][-1]) if np.any(pre_mask) else float(vdc[0])
    vdc_post = vdc[post_mask] if np.any(post_mask) else vdc

    drop_from_pre = np.maximum(vdc_pre - vdc_post, 0.0)
    drop_from_ref = np.maximum(vdc_ref - vdc_post, 0.0)
    max_drop_pre = float(np.max(drop_from_pre)) if drop_from_pre.size else 0.0
    max_drop_ref = float(np.max(drop_from_ref)) if drop_from_ref.size else 0.0

    t_recovery = float("nan")
    if max_drop_pre <= 1e-12:
        t_recovery = 0.0
    elif np.any(post_mask):
        threshold = vdc_pre - 0.05 * max_drop_pre  # ~95% recovery wrt pre-step value
        t_post = t[post_mask]
        idx_min = int(np.argmin(vdc_post))
        recovered = np.where(vdc_post[idx_min:] >= threshold)[0]
        if recovered.size:
            t_recovery = float(t_post[idx_min + recovered[0]] - t_step)

    return {
        "vdc_min": float(np.min(vdc)),
        "vdc_max": float(np.max(vdc)),
        "vdc_final": float(vdc[-1]),
        "vdc_pre_step": vdc_pre,
        "max_drop_from_pre": max_drop_pre,
        "max_drop_from_ref": max_drop_ref,
        "t_recovery_s": t_recovery,
    }


def run_bess_comparison() -> dict[str, dict[str, np.ndarray] | dict[str, float]]:
    """Run comparable no-BESS vs with-BESS simulations and return key metrics."""
    model_base = Microgrid()
    model_bess = MicrogridWithBESS()
    base = run_baseline_simulation(model_base)
    with_bess = run_bess_integrated_simulation(model_bess)

    metrics_base = _vdc_metrics(
        t=base["t"],
        vdc=base["vdc"],
        vdc_ref=model_base.vdc_ref,
        t_step=model_base.t_step,
    )
    metrics_bess = _vdc_metrics(
        t=with_bess["t"],
        vdc=with_bess["Vdc"],
        vdc_ref=model_bess.vdc_ref,
        t_step=model_bess.t_step,
    )

    # Physical-coherence check around load-step window.
    t0 = model_bess.t_step
    step_window = (with_bess["t"] >= t0) & (with_bess["t"] <= (t0 + 0.1))
    i_bess_step_mean = (
        float(np.mean(with_bess["i_bess"][step_window]))
        if np.any(step_window)
        else float("nan")
    )

    return {
        "baseline": base,
        "with_bess": with_bess,
        "metrics_baseline": metrics_base,
        "metrics_with_bess": metrics_bess,
        "i_bess_step_mean": i_bess_step_mean,
    }


def save_bess_comparison_figures(
    comparison: dict[str, dict[str, np.ndarray] | dict[str, float]],
    output_dir: Path,
    t_step: float,
) -> None:
    """Save compact figures for no-BESS vs with-BESS comparison."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = comparison["baseline"]
    bess = comparison["with_bess"]

    fig1 = plt.figure()
    plt.plot(base["t"], base["vdc"], label="Vdc sin BESS")
    plt.plot(bess["t"], bess["Vdc"], label="Vdc con BESS")
    plt.axvline(t_step, linestyle="--", color="k", alpha=0.7, label="escalon carga")
    plt.title("Comparacion Vdc: sin BESS vs con BESS")
    plt.xlabel("t [s]")
    plt.ylabel("Vdc [V]")
    plt.grid(True)
    plt.legend()
    fig1.savefig(output_dir / "compare_vdc_bess.png", dpi=180, bbox_inches="tight")
    plt.close(fig1)

    fig2, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    axes[0].plot(bess["t"], bess["i_bess"], label="i_bess")
    axes[0].axvline(t_step, linestyle="--", color="k", alpha=0.7)
    axes[0].set_ylabel("A")
    axes[0].grid(True)
    axes[0].legend(loc="best")

    axes[1].plot(bess["t"], bess["soc_bess"], label="soc_bess", color="tab:green")
    axes[1].plot(bess["t"], bess["soh_bess"], label="soh_bess", color="tab:orange")
    axes[1].axvline(t_step, linestyle="--", color="k", alpha=0.7)
    axes[1].set_ylabel("[-]")
    axes[1].grid(True)
    axes[1].legend(loc="best")

    axes[2].plot(bess["t"], bess["vt_bess"], label="vt_bess", color="tab:red")
    axes[2].axvline(t_step, linestyle="--", color="k", alpha=0.7)
    axes[2].set_xlabel("t [s]")
    axes[2].set_ylabel("V")
    axes[2].grid(True)
    axes[2].legend(loc="best")
    fig2.tight_layout()
    fig2.savefig(output_dir / "compare_bess_signals.png", dpi=180, bbox_inches="tight")
    plt.close(fig2)

    fig3 = plt.figure()
    plt.plot(base["t"], base["p_pcc"] / 1000.0, label="p_pcc sin BESS")
    plt.plot(base["t"], base["p_load"] / 1000.0, label="p_load sin BESS")
    plt.plot(bess["t"], bess["p_pcc"] / 1000.0, label="p_pcc con BESS", alpha=0.8)
    plt.plot(bess["t"], bess["p_load"] / 1000.0, label="p_load con BESS", alpha=0.8)
    plt.axvline(t_step, linestyle="--", color="k", alpha=0.7)
    plt.title("Comparacion de potencias")
    plt.xlabel("t [s]")
    plt.ylabel("P [kW]")
    plt.grid(True)
    plt.legend()
    fig3.savefig(output_dir / "compare_power_bess.png", dpi=180, bbox_inches="tight")
    plt.close(fig3)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run baseline simulation and optional first-step BESS-integrated simulation."
    )
    parser.add_argument(
        "--with-bess",
        action="store_true",
        help="Run an additional integrated simulation with BESS coupled to the DC bus.",
    )
    parser.add_argument(
        "--compare-bess",
        action="store_true",
        help="Run side-by-side comparison without BESS vs with BESS under the same load step.",
    )
    args = parser.parse_args()

    output_dir = Path(__file__).resolve().parents[1] / "outputs"
    if args.compare_bess:
        comparison = run_bess_comparison()
        m0 = comparison["metrics_baseline"]
        m1 = comparison["metrics_with_bess"]
        print("\nComparacion Vdc (sin BESS vs con BESS):")
        print(
            f"  Sin BESS: vdc_min={m0['vdc_min']:.3f}, vdc_max={m0['vdc_max']:.3f}, "
            f"vdc_final={m0['vdc_final']:.3f}, max_drop_pre={m0['max_drop_from_pre']:.3f}, "
            f"t_recovery_s={m0['t_recovery_s']:.6f}"
        )
        print(
            f"  Con BESS: vdc_min={m1['vdc_min']:.3f}, vdc_max={m1['vdc_max']:.3f}, "
            f"vdc_final={m1['vdc_final']:.3f}, max_drop_pre={m1['max_drop_from_pre']:.3f}, "
            f"t_recovery_s={m1['t_recovery_s']:.6f}"
        )
        print(f"  i_bess_mean en ventana post-escalon: {comparison['i_bess_step_mean']:.6f} A")
        try:
            save_bess_comparison_figures(
                comparison=comparison,
                output_dir=output_dir,
                t_step=Microgrid().t_step,
            )
            print("\nFiguras comparativas guardadas en outputs/:")
            print("  - compare_vdc_bess.png")
            print("  - compare_bess_signals.png")
            print("  - compare_power_bess.png")
        except Exception as exc:
            print(f"\nwarning=No se pudieron guardar figuras comparativas: {exc}")
        return

    model = Microgrid()
    print(f"P_ref_nominal baseline: {model.P_ref_nominal:.1f} W")
    signals = run_baseline_simulation(model)
    try:
        save_baseline_figures(model, signals, output_dir)
    except Exception as exc:
        print(f"warning=No se pudieron guardar figuras baseline: {exc}")

    if args.with_bess:
        model_bess = MicrogridWithBESS()
        signals_bess = run_bess_integrated_simulation(model_bess)
        print("\nBESS integration (first step) summary:")
        print(
            f"  Vdc_final={signals_bess['Vdc'][-1]:.3f} V | "
            f"i_bess_final={signals_bess['i_bess'][-1]:.3f} A | "
            f"soc_bess_final={signals_bess['soc_bess'][-1]:.6f} | "
            f"soh_bess_final={signals_bess['soh_bess'][-1]:.6f} | "
            f"vt_bess_final={signals_bess['vt_bess'][-1]:.3f} V"
        )


if __name__ == "__main__":
    main()
