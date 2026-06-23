"""Compare integrated BESS support for several initial SoH scenarios.

Scope:
- Simulate the same MicrogridWithBESS load-step case for SoH 1.00, 0.70 and
  the current nominal case.
- Compare DC-link response and BESS current/power support.
- Do not modify equations, controllers, sign conventions, or the 1RC BESS model.
"""

from __future__ import annotations

import argparse
import csv
from math import pi
from pathlib import Path
import sys
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
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
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.gfm_controller import GFMController
from microgrid import Microgrid, MicrogridWithBESS
from tuning_metrics import (
    bess_stress_metrics,
    dc_link_performance_metrics,
    frequency_performance_metrics,
)


IDENTITY_ATOL = 1e-8
LIMIT_ATOL = 1e-9
VOLTAGE_SCALE_REVIEW_THRESHOLD = 20.0
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "bess_soh_scenarios"
CSV_PATH = OUTPUT_DIR / "bess_soh_scenarios_summary.csv"
GFM_SOH_OUTPUT_DIR = (
    REPO_ROOT / "outputs" / "validation" / "gfm_bess_soh_scenarios"
)
GFM_SOH_CSV_PATH = GFM_SOH_OUTPUT_DIR / "gfm_bess_soh_scenarios_summary.csv"
GFM_SELECTED_M = 40.0
GFM_SELECTED_D = 100.0
GFM_SOH_T_END_S = 6.5
GFM_CRITERIA_VERSION = "obj2_vdc_event_relative_v2"
GFM_VDC_ACCEPTANCE_BASIS = "max_abs_event_deviation_from_pre_step"
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
    soc_soh_filename = "bess_soh_scenarios_soc_soh.png"
    try:
        fig, axes = plt.subplots(2, 1, sharex=True)
        for label, data in results.items():
            axes[0].plot(data["t"], data["soc_bess"], label=label)
            axes[1].plot(data["t"], data["soh_bess"], label=label)
        axes[0].set_ylabel("SoC [-]")
        axes[0].ticklabel_format(axis="y", style="plain", useOffset=False)
        axes[0].yaxis.set_major_formatter(
            FuncFormatter(lambda value, _position: f"{value:.6f}".replace(".", ","))
        )
        axes[1].set_xlabel("t [s]")
        axes[1].set_ylabel("SoH [-]")
        for ax in axes:
            ax.grid(True)
            ax.legend(loc="best")
        fig.suptitle("Escenarios de degradación BESS-SLB: SoC(t) y SoH(t)")
        fig.savefig(OUTPUT_DIR / soc_soh_filename, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Figura guardada: {soc_soh_filename}")
    except Exception as exc:
        warnings.append(f"warning=No se pudo guardar {soc_soh_filename}: {exc}")
        plt.close("all")
    return warnings


def _run_baseline() -> int:
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


    return 0 if hard_ok else 1



def _nominal_soh() -> float:
    return float(
        BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT
        / BESS_COUPLED_Q_NOM_REF_AH_DEFAULT
    )


def _gfm_soh_scenarios() -> tuple[tuple[str, float], ...]:
    return (
        ("SoH_1p00", 1.0),
        ("SoH_0p70", 0.70),
        ("SoH_nominal", _nominal_soh()),
    )


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(
        min(
            reference_model.P_ref_nominal,
            reference_model.p_available_ref,
        )
    )


def _classify_gfm_soh_case(
    *,
    hard_checks_ok: bool,
    frequency_criteria_pass: bool,
    vdc_criteria_pass: bool,
) -> str:
    if not hard_checks_ok:
        return "FAIL"
    if frequency_criteria_pass and vdc_criteria_pass:
        return "PASS"
    return "REVIEW"


def _combine_gfm_soh_statuses(
    statuses: list[str],
    *,
    available_limit_order_ok: bool,
) -> str:
    if not available_limit_order_ok or any(status == "FAIL" for status in statuses):
        return "FAIL"
    if any(status == "REVIEW" for status in statuses):
        return "REVIEW"
    return "PASS"


def _classify_bess_exchange_mode(
    current_post_step_a: np.ndarray,
    *,
    atol_a: float = LIMIT_ATOL,
) -> str:
    """Classify BESS exchange using the repository sign convention."""
    current = np.asarray(current_post_step_a, dtype=float)
    discharge_observed = bool(np.any(current > atol_a))
    charge_observed = bool(np.any(current < -atol_a))
    if discharge_observed and charge_observed:
        return "bidirectional"
    if discharge_observed:
        return "discharge_only"
    if charge_observed:
        return "charge_only"
    return "idle"


def _available_limit_order_ok(rows: list[dict[str, Any]]) -> bool:
    by_label = {str(row["label"]): row for row in rows}
    if set(by_label) != {"SoH_1p00", "SoH_0p70", "SoH_nominal"}:
        return False
    return bool(
        float(by_label["SoH_1p00"]["i_bess_max_available_initial"])
        > float(by_label["SoH_0p70"]["i_bess_max_available_initial"])
        > float(by_label["SoH_nominal"]["i_bess_max_available_initial"])
        and float(by_label["SoH_1p00"]["p_bess_dc_max_available_initial"])
        > float(by_label["SoH_0p70"]["p_bess_dc_max_available_initial"])
        > float(by_label["SoH_nominal"]["p_bess_dc_max_available_initial"])
    )


def _simulate_gfm_soh_case(
    label: str,
    soh_case: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    p_load_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_load_post = float(
        p_load_pre * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
    )
    load_step_pct = 100.0 * (p_load_post - p_load_pre) / p_load_pre
    t_step = float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
    p_ref_w = _reference_active_power_w()

    controller = GFMController(
        p_ref=p_ref_w,
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    model = MicrogridWithBESS(
        controller=controller,
        bess_model=_build_bess_for_soh(soh_case),
        load_profile=lambda t: p_load_pre if t < t_step else p_load_post,
    )
    y0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
    sol = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, GFM_SOH_T_END_S),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    signals = _collect_signals(model, sol.t, sol.y)
    frequency_hz = sol.y[10] / (2.0 * pi)
    signals["frequency_hz"] = frequency_hz

    states_finite = bool(
        np.all(np.isfinite(sol.t)) and np.all(np.isfinite(sol.y))
    )
    signals_finite = bool(
        all(np.all(np.isfinite(value)) for value in signals.values())
    )
    scenario_configuration_ok = bool(
        model.controller_state_name == "omega"
        and len(y0) == 15
        and np.isclose(y0[10], controller.omega_ref)
        and abs(load_step_pct - 20.0) <= 1e-9
        and np.isclose(model.bess.soh_init_case, soh_case)
        and GFM_SOH_T_END_S >= t_step + 5.5
    )

    vdc = signals["Vdc"]
    i_bess = signals["i_bess"]
    p_bess_dc = signals["p_bess_dc"]
    soc_bess = signals["soc_bess"]
    soh_bess = signals["soh_bess"]
    vt_bess = signals["vt_bess"]
    i_available = signals["i_bess_max_available"]
    p_available = signals["p_bess_dc_max_available"]

    post_step_mask = sol.t >= t_step
    i_bess_post_step = i_bess[post_step_mask]
    bess_exchange_mode = _classify_bess_exchange_mode(i_bess_post_step)
    bess_discharge_observed = bess_exchange_mode in {
        "discharge_only",
        "bidirectional",
    }
    bess_charge_observed = bess_exchange_mode in {
        "charge_only",
        "bidirectional",
    }

    vdc_positive_ok = bool(np.all(vdc > 0.0))
    vt_positive_ok = bool(np.all(vt_bess > 0.0))
    soc_range_ok = bool(
        np.all(
            (soc_bess >= model.bess.soc_min)
            & (soc_bess <= model.bess.soc_max)
        )
    )
    soh_range_ok = bool(
        np.all((soh_bess >= model.bess.soh_min) & (soh_bess <= 1.0))
    )
    current_limit_ok = bool(
        np.all(np.abs(i_bess) <= i_available + LIMIT_ATOL)
    )
    power_limit_ok = bool(
        np.all(np.abs(p_bess_dc) <= p_available + LIMIT_ATOL)
    )
    identity_ok = bool(
        np.allclose(
            p_bess_dc,
            vdc * i_bess,
            rtol=1e-9,
            atol=IDENTITY_ATOL,
        )
    )
    scale_review = bool(
        np.max(vdc / vt_bess) > VOLTAGE_SCALE_REVIEW_THRESHOLD
    )
    hard_checks_ok = bool(
        sol.success
        and states_finite
        and signals_finite
        and scenario_configuration_ok
        and vdc_positive_ok
        and vt_positive_ok
        and soc_range_ok
        and soh_range_ok
        and current_limit_ok
        and power_limit_ok
        and identity_ok
    )

    frequency_metrics = frequency_performance_metrics(
        t=sol.t,
        frequency_hz=frequency_hz,
        t_step=t_step,
    )
    vdc_metrics = dc_link_performance_metrics(
        t=sol.t,
        vdc_v=vdc,
        t_step=t_step,
    )
    bess_metrics = bess_stress_metrics(
        t=sol.t,
        i_bess_a=i_bess,
        p_bess_w=p_bess_dc,
        t_step=t_step,
        soc=soc_bess,
    )

    status = _classify_gfm_soh_case(
        hard_checks_ok=hard_checks_ok,
        frequency_criteria_pass=bool(
            frequency_metrics["frequency_criteria_pass"]
        ),
        vdc_criteria_pass=bool(vdc_metrics["vdc_criteria_pass"]),
    )

    reasons: list[str] = []
    observations: list[str] = []
    if not hard_checks_ok:
        reasons.append("numerical, configuration or BESS-limit checks failed")
    if hard_checks_ok and not bool(
        frequency_metrics["frequency_criteria_pass"]
    ):
        reasons.append("frequency acceptance criteria are not met")
    if hard_checks_ok and not bool(vdc_metrics["vdc_criteria_pass"]):
        reasons.append("DC-link acceptance criteria are not met")
    if scale_review:
        observations.append("Vdc/vt_bess scale warning is diagnostic only")
    if not bess_discharge_observed:
        observations.append(
            "BESS remains in charge/absorption mode; no discharge support observed"
        )

    row: dict[str, Any] = {
        "label": label,
        "status": status,
        "criteria_version": GFM_CRITERIA_VERSION,
        "vdc_acceptance_basis": GFM_VDC_ACCEPTANCE_BASIS,
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "bess_active": True,
        "soh_case": float(soh_case),
        "soh_initial": float(model.bess.soh_init_case),
        "q_init_case_ah": float(model.bess.q_init_case_ah),
        "p_ref_w": p_ref_w,
        "p_load_pre_step_w": p_load_pre,
        "p_load_post_step_w": p_load_post,
        "load_step_pct": load_step_pct,
        "power_factor": float(MICROGRID_LOAD_POWER_FACTOR_DEFAULT),
        "t_step_s": t_step,
        "t_end_s": GFM_SOH_T_END_S,
        "controller_state_name": model.controller_state_name,
        "state_count": len(y0),
        "scenario_configuration_ok": scenario_configuration_ok,
        "solver_success": bool(sol.success),
        "solver_message": str(sol.message),
        "states_finite": states_finite,
        "signals_finite": signals_finite,
        "n_time_points": int(sol.t.size),
        "nfev": int(sol.nfev),
        "i_bess_max_available_initial": float(i_available[0]),
        "p_bess_dc_max_available_initial": float(p_available[0]),
        "bess_exchange_mode": bess_exchange_mode,
        "bess_discharge_observed": bess_discharge_observed,
        "bess_charge_observed": bess_charge_observed,
        "soc_final": float(soc_bess[-1]),
        "soh_final": float(soh_bess[-1]),
        "vt_bess_min_v": float(np.min(vt_bess)),
        "vdc_positive_ok": vdc_positive_ok,
        "vt_positive_ok": vt_positive_ok,
        "soc_range_ok": soc_range_ok,
        "soh_range_ok": soh_range_ok,
        "current_limit_ok": current_limit_ok,
        "power_limit_ok": power_limit_ok,
        "identity_ok": identity_ok,
        "scale_review": scale_review,
        "hard_checks_ok": hard_checks_ok,
        "review_reasons": "; ".join(reasons),
        "observations": "; ".join(observations),
    }
    row.update(frequency_metrics)
    row.update(vdc_metrics)
    row.update(bess_metrics)
    return row, {"t": sol.t, **signals}


def _run_gfm_selected_soh() -> int:
    rows: list[dict[str, Any]] = []
    for label, soh_case in _gfm_soh_scenarios():
        row, _signals = _simulate_gfm_soh_case(label, soh_case)
        rows.append(row)

    GFM_SOH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with GFM_SOH_CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    available_limit_order_ok = _available_limit_order_ok(rows)
    overall_status = _combine_gfm_soh_statuses(
        [str(row["status"]) for row in rows],
        available_limit_order_ok=available_limit_order_ok,
    )

    print("GFM + BESS full 15-state SoH validation")
    print(f"status={overall_status}")
    print(f"M={GFM_SELECTED_M:.6f}")
    print(f"D={GFM_SELECTED_D:.6f}")
    print("load_step_pct=20.000000")
    print(f"available_limit_order_ok={available_limit_order_ok}")
    print(f"csv_path={GFM_SOH_CSV_PATH}")
    for row in rows:
        print(
            f"scenario={row['label']} | status={row['status']} | "
            f"SoH={row['soh_initial']:.6f} | "
            f"freq_drop={row['max_frequency_drop_hz']:.9f} Hz | "
            f"freq_pass={row['frequency_criteria_pass']} | "
            f"vdc_event_dev="
            f"{row['vdc_event_max_abs_deviation_pct']:.6f} pct | "
            f"vdc_min={row['vdc_min_post_step_v']:.6f} V | "
            f"vdc_pass={row['vdc_criteria_pass']} | "
            f"i_peak={row['i_bess_peak_abs_a']:.6f} A | "
            f"p_peak={row['p_bess_peak_abs_w']:.6f} W | "
            f"mode={row['bess_exchange_mode']} | "
            f"discharge_observed={row['bess_discharge_observed']} | "
            f"energy={row['bess_energy_throughput_wh']:.9f} Wh | "
            f"soc_swing={row['soc_swing']:.9f}"
        )
        if row["review_reasons"]:
            print(f"review_reasons_{row['label']}={row['review_reasons']}")
        if row["observations"]:
            print(f"observations_{row['label']}={row['observations']}")

    return 0 if overall_status == "PASS" else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare BESS SoH scenarios in baseline or selected-GFM mode."
    )
    parser.add_argument(
        "--gfm-selected",
        action="store_true",
        help=(
            "Run the selected GFM point with the full 15-state BESS model "
            "for the three SoH cases."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.gfm_selected:
        return _run_gfm_selected_soh()
    return _run_baseline()


if __name__ == "__main__":
    raise SystemExit(main())
