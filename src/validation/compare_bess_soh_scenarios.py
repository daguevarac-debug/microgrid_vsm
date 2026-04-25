"""Compare integrated BESS support for several initial SoH scenarios.

Scope:
- Simulate the same MicrogridWithBESS load-step case for SoH 1.00, 0.70 and
  the current nominal case.
- Compare DC-link response and BESS current/power support.
- Do not modify equations, controllers, sign conventions, or the 1RC BESS model.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.model import SecondLifeBattery1RC
from config import (
    BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
    BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
    BESS_COUPLED_R0_DEFAULT,
    BESS_COUPLED_SOC_INIT_DEFAULT,
    BESS_COUPLED_SOC_MAX_DEFAULT,
    BESS_COUPLED_SOC_MIN_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid import MicrogridWithBESS


IDENTITY_ATOL = 1e-8
VOLTAGE_SCALE_REVIEW_THRESHOLD = 20.0
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "bess_soh_scenarios"
CSV_PATH = OUTPUT_DIR / "bess_soh_scenarios_summary.csv"
FREQUENCY_OBSERVATION = (
    "El modelo actual es baseline/grid-following; la frecuencia no se interpreta "
    "como metrica final de soporte hasta activar grid-forming/VSG."
)


def _build_bess_for_soh(soh_case: float) -> SecondLifeBattery1RC:
    q_nom_ref_ah = BESS_COUPLED_Q_NOM_REF_AH_DEFAULT
    q_init_case_ah = q_nom_ref_ah * soh_case
    return SecondLifeBattery1RC.from_excel_characterization(
        excel_path=REPO_ROOT / "OCV_SOC.xlsx",
        q_nom_ref_ah=q_nom_ref_ah,
        q_init_case_ah=q_init_case_ah,
        r0_nominal_ohm=BESS_COUPLED_R0_DEFAULT,
        r0_soh_sensitivity=1.0,
        k_deg=1.478e-6,
        soh_min=0.50,
        q_eff_min_ah=1e-9,
        soc_initial=BESS_COUPLED_SOC_INIT_DEFAULT,
        soc_min=BESS_COUPLED_SOC_MIN_DEFAULT,
        soc_max=BESS_COUPLED_SOC_MAX_DEFAULT,
    )


def _collect_signals(model: MicrogridWithBESS, t: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    keys = (
        "Vdc",
        "i_bess",
        "p_bess_dc",
        "soc_bess",
        "vt_bess",
        "soh_bess",
        "i_bess_max_available",
        "p_bess_dc_max_available",
    )
    signals = {key: np.zeros_like(t, dtype=float) for key in keys}
    for k, tk in enumerate(t):
        sig = model.integrated_signals(float(tk), y[:, k])
        for key in keys:
            signals[key][k] = float(sig[key])
    return signals


def _vdc_drop_metric(t: np.ndarray, vdc: np.ndarray, t_step: float) -> float:
    pre_mask = t < t_step
    post_mask = t >= t_step
    vdc_pre = float(vdc[pre_mask][-1]) if np.any(pre_mask) else float(vdc[0])
    vdc_post = vdc[post_mask] if np.any(post_mask) else vdc
    return float(np.max(np.maximum(vdc_pre - vdc_post, 0.0)))


def _post_step_mean(t: np.ndarray, values: np.ndarray, t_step: float) -> float:
    window = (t >= t_step) & (t <= (t_step + 0.1))
    return float(np.mean(values[window])) if np.any(window) else float("nan")


def _simulate_case(label: str, soh_case: float) -> tuple[dict[str, float | str | bool], dict[str, np.ndarray]]:
    bess = _build_bess_for_soh(soh_case)
    model = MicrogridWithBESS(bess_model=bess)
    y0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
    sol = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    signals = _collect_signals(model, sol.t, sol.y)

    vdc = signals["Vdc"]
    i_bess = signals["i_bess"]
    p_bess_dc = signals["p_bess_dc"]
    soc_bess = signals["soc_bess"]
    vt_bess = signals["vt_bess"]
    soh_bess = signals["soh_bess"]
    i_available = signals["i_bess_max_available"]
    p_available = signals["p_bess_dc_max_available"]

    finite_ok = bool(np.all(np.isfinite(sol.y)) and all(np.all(np.isfinite(v)) for v in signals.values()))
    vdc_positive_ok = bool(np.all(vdc > 0.0))
    vt_positive_ok = bool(np.all(vt_bess > 0.0))
    soc_range_ok = bool(np.all((soc_bess >= model.bess.soc_min) & (soc_bess <= model.bess.soc_max)))
    soh_range_ok = bool(np.all((soh_bess >= model.bess.soh_min) & (soh_bess <= 1.0)))
    current_limit_ok = bool(np.all(np.abs(i_bess) <= i_available + IDENTITY_ATOL))
    power_limit_ok = bool(np.all(np.abs(p_bess_dc) <= p_available + IDENTITY_ATOL))
    identity_ok = bool(np.allclose(p_bess_dc, vdc * i_bess, rtol=1e-9, atol=IDENTITY_ATOL))
    scale_review = bool(np.max(vdc / vt_bess) > VOLTAGE_SCALE_REVIEW_THRESHOLD)
    hard_checks_ok = bool(
        sol.success
        and finite_ok
        and vdc_positive_ok
        and vt_positive_ok
        and soc_range_ok
        and soh_range_ok
        and current_limit_ok
        and power_limit_ok
        and identity_ok
    )

    row: dict[str, float | str | bool] = {
        "label": label,
        "soh_case": float(soh_case),
        "soh_initial": float(model.bess.soh_init_case),
        "q_init_case_ah": float(model.bess.q_init_case_ah),
        "i_bess_max_available_initial": float(i_available[0]),
        "p_bess_dc_max_available_initial": float(p_available[0]),
        "vdc_min": float(np.min(vdc)),
        "vdc_max": float(np.max(vdc)),
        "vdc_final": float(vdc[-1]),
        "max_drop_from_pre": _vdc_drop_metric(sol.t, vdc, model.t_step),
        "i_bess_abs_max": float(np.max(np.abs(i_bess))),
        "p_bess_dc_abs_max": float(np.max(np.abs(p_bess_dc))),
        "p_bess_dc_mean_post_step": _post_step_mean(sol.t, p_bess_dc, model.t_step),
        "soc_final": float(soc_bess[-1]),
        "vt_bess_min": float(np.min(vt_bess)),
        "frequency_metric_available": False,
        "observation_frequency": FREQUENCY_OBSERVATION,
        "solver_success": bool(sol.success),
        "finite_ok": finite_ok,
        "vdc_positive_ok": vdc_positive_ok,
        "vt_positive_ok": vt_positive_ok,
        "soc_range_ok": soc_range_ok,
        "soh_range_ok": soh_range_ok,
        "current_limit_ok": current_limit_ok,
        "power_limit_ok": power_limit_ok,
        "identity_ok": identity_ok,
        "scale_review": scale_review,
        "hard_checks_ok": hard_checks_ok,
    }
    return row, {"t": sol.t, **signals}


def _write_csv(rows: list[dict[str, float | str | bool]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _save_figures(results: dict[str, dict[str, np.ndarray]]) -> list[str]:
    warnings: list[str] = []
    specs = [
        ("bess_soh_scenarios_vdc.png", "Vdc", "Vdc [V]", "Comparacion Vdc por SoH"),
        ("bess_soh_scenarios_power.png", "p_bess_dc", "p_bess_dc [W]", "Comparacion potencia BESS-DC por SoH"),
        ("bess_soh_scenarios_current.png", "i_bess", "i_bess [A]", "Comparacion corriente BESS por SoH"),
    ]
    for filename, key, ylabel, title in specs:
        try:
            fig = plt.figure()
            for label, data in results.items():
                plt.plot(data["t"], data[key], label=label)
            plt.xlabel("t [s]")
            plt.ylabel(ylabel)
            plt.title(title)
            plt.grid(True)
            plt.legend(loc="best")
            fig.savefig(OUTPUT_DIR / filename, dpi=180, bbox_inches="tight")
            plt.close(fig)
        except Exception as exc:
            warnings.append(f"warning=No se pudo guardar {filename}: {exc}")
            plt.close("all")
    return warnings


def main() -> None:
    nominal_soh = BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT / BESS_COUPLED_Q_NOM_REF_AH_DEFAULT
    scenarios = [
        ("SoH_1p00", 1.0),
        ("SoH_0p70", 0.70),
        ("SoH_nominal", nominal_soh),
    ]

    rows: list[dict[str, float | str | bool]] = []
    results: dict[str, dict[str, np.ndarray]] = {}
    for label, soh_case in scenarios:
        row, signals = _simulate_case(label, soh_case)
        rows.append(row)
        results[label] = signals

    csv_ok = False
    csv_error = ""
    try:
        _write_csv(rows)
        csv_ok = True
    except Exception as exc:
        csv_error = str(exc)

    figure_warnings = _save_figures(results) if csv_ok else []
    hard_ok = bool(csv_ok and all(bool(row["hard_checks_ok"]) for row in rows))
    review = bool(any(bool(row["scale_review"]) for row in rows))
    if not hard_ok:
        status = "FAIL"
    elif review:
        status = "REVIEW"
    else:
        status = "PASS"

    print(f"status={status}")
    print(f"csv_path={CSV_PATH}")
    if not csv_ok:
        print(f"csv_error={csv_error}")
    print("frequency_metric_available=False")
    print(f"observation_frequency={FREQUENCY_OBSERVATION}")
    for warning in figure_warnings:
        print(warning)
    for row in rows:
        print(
            "scenario="
            f"{row['label']} | soh_initial={row['soh_initial']:.6f} | "
            f"q_init_case_ah={row['q_init_case_ah']:.6f} | "
            f"i_available={row['i_bess_max_available_initial']:.6f} A | "
            f"p_available={row['p_bess_dc_max_available_initial']:.6f} W | "
            f"vdc_min={row['vdc_min']:.6f} V | "
            f"vdc_final={row['vdc_final']:.6f} V | "
            f"i_abs_max={row['i_bess_abs_max']:.6f} A | "
            f"p_abs_max={row['p_bess_dc_abs_max']:.6f} W | "
            f"p_mean_post_step={row['p_bess_dc_mean_post_step']:.6f} W"
        )


if __name__ == "__main__":
    main()
