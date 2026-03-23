"""Entry point for dynamic baseline simulation and result plots."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

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
from microgrid import Microgrid


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


def main() -> None:
    model = Microgrid()
    print(f"P_ref_nominal baseline: {model.P_ref_nominal:.1f} W")
    signals = run_baseline_simulation(model)
    output_dir = Path(__file__).resolve().parents[1] / "outputs"
    save_baseline_figures(model, signals, output_dir)


if __name__ == "__main__":
    main()
