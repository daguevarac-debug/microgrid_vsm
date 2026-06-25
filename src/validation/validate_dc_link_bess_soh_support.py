"""Validate BESS discharge support, SoH cases and no-support comparison.

Task 5.3 closure extension:

- verify that the corrected PI+BESS architecture discharges during the severe
  40% post-step power deficit without exceeding current or power limits;
- repeat the full validation for SoH = 1.00, SoH = 0.70 and nominal SoH;
- compare the former selected-GFM case without BESS support against the
  corrected nominal-SoH PI+BESS case in one reproducible figure;
- write a numerical summary, comparison CSV and Markdown validation record.

No controller gain, VSG equation, M or D value is modified by this script.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

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

from config import (
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from tuning_metrics import dc_link_performance_metrics, frequency_performance_metrics
from validation.compare_bess_soh_scenarios import _build_bess_for_soh, _nominal_soh
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)


T_END_S = 6.5
LIMIT_ATOL = 1e-8
DISCHARGE_ATOL_W = 1e-6
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "dc_link_regulation"
SUMMARY_PATH = OUTPUT_DIR / "task_5_3_bess_soh_support_summary.json"
SOH_CSV_PATH = OUTPUT_DIR / "task_5_3_bess_soh_support_summary.csv"
COMPARISON_CSV_PATH = OUTPUT_DIR / "task_5_3_no_support_vs_bess_pi.csv"
FIGURE_PATH = OUTPUT_DIR / "task_5_3_no_support_vs_bess_pi.png"
DOC_PATH = REPO_ROOT / "docs" / "dc_link_regulation_validation.md"


def soh_scenarios() -> tuple[tuple[str, float], ...]:
    """Return the three explicitly required SoH validation cases."""
    return (
        ("SoH_1p00", 1.0),
        ("SoH_0p70", 0.70),
        ("SoH_nominal", _nominal_soh()),
    )


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def _load_levels() -> tuple[float, float]:
    pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    post = pre * (1.0 + MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT)
    return pre, post


def _gfm_controller() -> GFMController:
    return GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )


def build_supported_model(soh_case: float) -> MicrogridWithBESSPI:
    """Build the corrected PI+BESS severe-step model for one initial SoH."""
    p_pre, p_post = _load_levels()
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=PI_KP_W_PER_V,
        ki_w_per_v_s=PI_KI_W_PER_V_S,
    )
    return MicrogridWithBESSPI(
        controller=_gfm_controller(),
        dc_link_bess_pi=pi,
        bess_enabled=True,
        bess_model=_build_bess_for_soh(soh_case),
        load_profile=lambda t: (
            p_pre if t < MICROGRID_LOAD_STEP_TIME_S_DEFAULT else p_post
        ),
    )


def build_no_support_model() -> Microgrid:
    """Build the former selected-GFM severe case without BESS support."""
    p_pre, p_post = _load_levels()
    return Microgrid(
        controller=_gfm_controller(),
        load_profile=lambda t: (
            p_pre if t < MICROGRID_LOAD_STEP_TIME_S_DEFAULT else p_post
        ),
    )


def _solve(model: Any, initial_state: list[float]):
    return solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, T_END_S),
        initial_state,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )


def classify_soh_case(
    *,
    solver_success: bool,
    finite: bool,
    frequency_pass: bool,
    vdc_pass: bool,
    discharge_observed: bool,
    positive_mean_discharge: bool,
    current_limit_pass: bool,
    power_limit_pass: bool,
    soc_limit_pass: bool,
    soh_limit_pass: bool,
) -> str:
    """Require physical discharge support and every existing acceptance check."""
    return (
        "PASS"
        if all(
            (
                solver_success,
                finite,
                frequency_pass,
                vdc_pass,
                discharge_observed,
                positive_mean_discharge,
                current_limit_pass,
                power_limit_pass,
                soc_limit_pass,
                soh_limit_pass,
            )
        )
        else "FAIL"
    )


def run_supported_soh_case(
    label: str,
    soh_case: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run and evaluate one corrected PI+BESS SoH case."""
    model = build_supported_model(soh_case)
    initial_state = model.initial_state_with_bess(
        vdc0=SIM_VDC0_V_DEFAULT,
        xi_bess_vdc0_v_s=0.0,
    )
    solution = _solve(model, initial_state)

    n = solution.t.size
    vdc = solution.y[0]
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    i_bess = np.zeros(n, dtype=float)
    p_bess = np.zeros(n, dtype=float)
    p_ref = np.zeros(n, dtype=float)
    p_min = np.zeros(n, dtype=float)
    p_max = np.zeros(n, dtype=float)
    i_max = np.zeros(n, dtype=float)
    soc = np.zeros(n, dtype=float)
    soh = np.zeros(n, dtype=float)

    for k, tk in enumerate(solution.t):
        signal = model.integrated_signals(float(tk), solution.y[:, k])
        i_bess[k] = float(signal["i_bess"])
        p_bess[k] = float(signal["p_bess_dc"])
        p_ref[k] = float(signal["p_bess_ref_w"])
        p_min[k] = float(signal["p_bess_ref_min_w"])
        p_max[k] = float(signal["p_bess_ref_max_w"])
        i_max[k] = float(signal["i_bess_max_available"])
        soc[k] = float(signal["soc_bess"])
        soh[k] = float(signal["soh_bess"])

    post = solution.t >= MICROGRID_LOAD_STEP_TIME_S_DEFAULT
    post_i = i_bess[post]
    post_p = p_bess[post]
    discharge_observed = bool(np.any(post_p > DISCHARGE_ATOL_W))
    positive_mean_discharge = bool(np.mean(post_p) > DISCHARGE_ATOL_W)
    discharge_fraction = float(np.mean(post_p > DISCHARGE_ATOL_W))

    finite = bool(
        np.all(np.isfinite(solution.y))
        and all(
            np.all(np.isfinite(values))
            for values in (vdc, frequency_hz, i_bess, p_bess, p_ref, p_min, p_max, i_max, soc, soh)
        )
    )
    current_limit_pass = bool(np.all(np.abs(i_bess) <= i_max + LIMIT_ATOL))
    power_limit_pass = bool(
        np.all(p_ref >= p_min - LIMIT_ATOL)
        and np.all(p_ref <= p_max + LIMIT_ATOL)
        and np.all(p_bess >= p_min - LIMIT_ATOL)
        and np.all(p_bess <= p_max + LIMIT_ATOL)
    )
    soc_limit_pass = bool(
        np.all(soc >= model.bess.soc_min - LIMIT_ATOL)
        and np.all(soc <= model.bess.soc_max + LIMIT_ATOL)
    )
    soh_limit_pass = bool(
        np.all(soh >= model.bess.soh_min - LIMIT_ATOL)
        and np.all(soh <= 1.0 + LIMIT_ATOL)
    )

    dc_metrics = dc_link_performance_metrics(
        solution.t,
        vdc,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    frequency_metrics = frequency_performance_metrics(
        solution.t,
        frequency_hz,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    status = classify_soh_case(
        solver_success=bool(solution.success),
        finite=finite,
        frequency_pass=bool(frequency_metrics["frequency_criteria_pass"]),
        vdc_pass=bool(dc_metrics["vdc_criteria_pass"]),
        discharge_observed=discharge_observed,
        positive_mean_discharge=positive_mean_discharge,
        current_limit_pass=current_limit_pass,
        power_limit_pass=power_limit_pass,
        soc_limit_pass=soc_limit_pass,
        soh_limit_pass=soh_limit_pass,
    )

    p_pre, p_post = _load_levels()
    result: dict[str, Any] = {
        "label": label,
        "status": status,
        "soh_case": float(soh_case),
        "soh_initial": float(model.bess.soh_init_case),
        "load_step_pct": 100.0 * MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
        "p_load_pre_step_w": p_pre,
        "p_load_post_step_w": p_post,
        "reference_available_power_w": _reference_active_power_w(),
        "post_step_commanded_power_deficit_w": float(p_post - _reference_active_power_w()),
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "Kp_w_per_v": PI_KP_W_PER_V,
        "Ki_w_per_v_s": PI_KI_W_PER_V_S,
        "bess_active": True,
        "solver_success": bool(solution.success),
        "solver_message": str(solution.message),
        "finite": finite,
        "state_count": int(solution.y.shape[0]),
        "discharge_observed_post_step": discharge_observed,
        "positive_mean_discharge_post_step": positive_mean_discharge,
        "discharge_fraction_post_step": discharge_fraction,
        "i_bess_min_post_step_a": float(np.min(post_i)),
        "i_bess_max_post_step_a": float(np.max(post_i)),
        "i_bess_peak_abs_a": float(np.max(np.abs(i_bess))),
        "i_bess_available_min_a": float(np.min(i_max)),
        "p_bess_min_post_step_w": float(np.min(post_p)),
        "p_bess_max_post_step_w": float(np.max(post_p)),
        "p_bess_mean_post_step_w": float(np.mean(post_p)),
        "p_bess_peak_abs_w": float(np.max(np.abs(p_bess))),
        "p_bess_discharge_limit_min_w": float(np.min(p_max)),
        "current_limit_pass": current_limit_pass,
        "power_limit_pass": power_limit_pass,
        "soc_limit_pass": soc_limit_pass,
        "soh_limit_pass": soh_limit_pass,
        "soc_min_observed": float(np.min(soc)),
        "soc_max_observed": float(np.max(soc)),
        "soh_min_observed": float(np.min(soh)),
        **dc_metrics,
        **frequency_metrics,
    }
    traces = {
        "t": solution.t,
        "vdc": vdc,
        "frequency_hz": frequency_hz,
        "i_bess": i_bess,
        "p_bess": p_bess,
    }
    return result, traces


def run_no_support_case() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run the former no-BESS selected-GFM severe case."""
    model = build_no_support_model()
    initial_state = model.initial_state(vdc0=SIM_VDC0_V_DEFAULT)
    solution = _solve(model, initial_state)
    vdc = solution.y[0]
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    dc_metrics = dc_link_performance_metrics(
        solution.t,
        vdc,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    frequency_metrics = frequency_performance_metrics(
        solution.t,
        frequency_hz,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    result: dict[str, Any] = {
        "label": "no_support",
        "solver_success": bool(solution.success),
        "states_finite": bool(np.all(np.isfinite(solution.y))),
        "state_count": int(solution.y.shape[0]),
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "bess_active": False,
        **dc_metrics,
        **frequency_metrics,
        "vdc_final_v": float(vdc[-1]),
    }
    traces = {
        "t": solution.t,
        "vdc": vdc,
        "frequency_hz": frequency_hz,
        "p_bess": np.zeros_like(solution.t),
    }
    return result, traces


def save_comparison_outputs(
    no_support: dict[str, np.ndarray],
    corrected: dict[str, np.ndarray],
    *,
    figure_path: Path = FIGURE_PATH,
    csv_path: Path = COMPARISON_CSV_PATH,
) -> tuple[Path, Path]:
    """Save one shared-time comparison figure and interpolated CSV."""
    figure_path = Path(figure_path)
    csv_path = Path(csv_path)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    common_time = np.linspace(SIM_T_START_S_DEFAULT, T_END_S, 2001)
    no_vdc = np.interp(common_time, no_support["t"], no_support["vdc"])
    corrected_vdc = np.interp(common_time, corrected["t"], corrected["vdc"])
    no_frequency = np.interp(
        common_time,
        no_support["t"],
        no_support["frequency_hz"],
    )
    corrected_frequency = np.interp(
        common_time,
        corrected["t"],
        corrected["frequency_hz"],
    )
    corrected_power = np.interp(
        common_time,
        corrected["t"],
        corrected["p_bess"],
    )

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            (
                "time_s",
                "vdc_no_support_v",
                "vdc_corrected_bess_pi_v",
                "frequency_no_support_hz",
                "frequency_corrected_bess_pi_hz",
                "p_bess_no_support_w",
                "p_bess_corrected_w",
            )
        )
        for values in zip(
            common_time,
            no_vdc,
            corrected_vdc,
            no_frequency,
            corrected_frequency,
            np.zeros_like(common_time),
            corrected_power,
        ):
            writer.writerow(values)

    fig, axes = plt.subplots(3, 1, figsize=(11.0, 10.0), sharex=True)
    axes[0].plot(common_time, no_vdc, label="Anterior: sin soporte BESS")
    axes[0].plot(common_time, corrected_vdc, label="Corregido: PI+BESS nominal")
    axes[0].axhline(SIM_VDC0_V_DEFAULT, linestyle="--", linewidth=1.0, label="Vdc ref")
    axes[0].set_ylabel("Vdc [V]")
    axes[0].legend(loc="best")

    axes[1].plot(common_time, no_frequency, label="Anterior: sin soporte BESS")
    axes[1].plot(common_time, corrected_frequency, label="Corregido: PI+BESS nominal")
    axes[1].axhline(60.0, linestyle="--", linewidth=1.0, label="60 Hz")
    axes[1].set_ylabel("Frecuencia [Hz]")
    axes[1].legend(loc="best")

    axes[2].plot(common_time, np.zeros_like(common_time), label="Sin soporte: PBESS=0")
    axes[2].plot(common_time, corrected_power, label="PBESS corregida")
    axes[2].axhline(0.0, linewidth=0.8)
    axes[2].set_ylabel("PBESS [W]")
    axes[2].set_xlabel("Tiempo [s]")
    axes[2].legend(loc="best")

    for axis in axes:
        axis.axvline(MICROGRID_LOAD_STEP_TIME_S_DEFAULT, linestyle="--", linewidth=0.9)
        axis.grid(True, alpha=0.3)
    fig.suptitle("Escalón severo del 40 %: caso anterior vs soporte corregido del BESS")
    fig.tight_layout()
    fig.savefig(figure_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return figure_path, csv_path


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_soh_csv(rows: list[dict[str, Any]], path: Path = SOH_CSV_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_markdown_report(report: dict[str, Any]) -> str:
    """Create the required human-readable validation record."""
    rows = report["soh_cases"]
    lines = [
        "# Validación de la regulación del enlace DC",
        "",
        "## Configuración",
        "",
        f"- Punto VSG: `(M, D) = ({report['M']}, {report['D']})`.",
        f"- PI del BESS: `Kp = {report['Kp_w_per_v']} W/V`, `Ki = {report['Ki_w_per_v_s']} W/(V*s)`.",
        "- Escenario: escalón severo de carga del 40 %, de 3000 W a 4200 W en `t = 0.8 s`.",
        "- Convención: `PBESS > 0` e `IBESS > 0` representan descarga.",
        "",
        "## Resultados por SoH",
        "",
        "| Caso | SoH inicial | Estado | Descarga observada | PBESS media post [W] | IBESS máx. descarga [A] | Límite corriente | Límite potencia | Vdc cumple | Frecuencia cumple |",
        "|---|---:|---|---|---:|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {label} | {soh_initial:.6f} | {status} | {discharge} | "
            "{p_mean:.6f} | {i_max:.6f} | {i_ok} | {p_ok} | {vdc_ok} | {f_ok} |".format(
                label=row["label"],
                soh_initial=row["soh_initial"],
                status=row["status"],
                discharge=row["discharge_observed_post_step"],
                p_mean=row["p_bess_mean_post_step_w"],
                i_max=row["i_bess_max_post_step_a"],
                i_ok=row["current_limit_pass"],
                p_ok=row["power_limit_pass"],
                vdc_ok=row["vdc_criteria_pass"],
                f_ok=row["frequency_criteria_pass"],
            )
        )

    comparison = report["comparison"]
    lines.extend(
        [
            "",
            "## Comparación sin soporte y con soporte corregido",
            "",
            "La figura compara el caso GFM anterior sin BESS contra el caso PI+BESS con SoH nominal, usando la misma carga, el mismo horizonte y los mismos parámetros `M` y `D`.",
            "",
            f"- Vdc mínima sin soporte: `{comparison['no_support']['vdc_min_post_step_v']:.6f} V`.",
            f"- Vdc mínima con soporte: `{comparison['corrected_support']['vdc_min_post_step_v']:.6f} V`.",
            f"- Caída máxima de frecuencia sin soporte: `{comparison['no_support']['max_frequency_drop_hz']:.9f} Hz`.",
            f"- Caída máxima de frecuencia con soporte: `{comparison['corrected_support']['max_frequency_drop_hz']:.9f} Hz`.",
            "",
            "## Criterios",
            "",
            "- Descarga positiva observada y potencia media positiva después del escalón.",
            "- Corriente real dentro del límite dinámico dependiente de SoH.",
            "- Potencia real y referencia saturada dentro de los límites dinámicos.",
            "- SoC y SoH dentro de sus rangos operativos.",
            "- Criterios vigentes de frecuencia y enlace DC cumplidos.",
            "",
            "## Limitaciones",
            "",
            "- Modelo promediado y reducido; no representa conmutación detallada del convertidor DC/DC.",
            "- No se modelan retardos de comunicación del BMS ni dinámica térmica.",
            "- El horizonte de 6.5 s valida respuesta dinámica corta, no envejecimiento de largo plazo.",
            "- `Kp` y `Ki` corresponden a un ajuste mínimo admisible, no a una optimización global.",
            "- La comparación usa SoH nominal para el caso corregido; los otros SoH se reportan por separado.",
            "",
            "## Archivos generados",
            "",
            f"- `{report['summary_path']}`",
            f"- `{report['soh_csv_path']}`",
            f"- `{report['comparison_csv_path']}`",
            f"- `{report['figure_path']}`",
            "- `docs/dc_link_regulation_validation.md`",
            "",
            f"## Estado final: {report['status']}",
            "",
        ]
    )
    return "\n".join(lines)


def run_validation(
    *,
    summary_path: Path = SUMMARY_PATH,
    doc_path: Path = DOC_PATH,
) -> dict[str, Any]:
    """Run all four requested closure subtasks and write every artifact."""
    soh_rows: list[dict[str, Any]] = []
    traces_by_label: dict[str, dict[str, np.ndarray]] = {}
    for label, soh_case in soh_scenarios():
        row, traces = run_supported_soh_case(label, soh_case)
        soh_rows.append(row)
        traces_by_label[label] = traces

    no_support_result, no_support_traces = run_no_support_case()
    nominal_result = next(row for row in soh_rows if row["label"] == "SoH_nominal")
    nominal_traces = traces_by_label["SoH_nominal"]
    figure_path, comparison_csv_path = save_comparison_outputs(
        no_support_traces,
        nominal_traces,
    )
    soh_csv_path = write_soh_csv(soh_rows)

    available_limit_order_ok = bool(
        soh_rows[0]["i_bess_available_min_a"]
        > soh_rows[1]["i_bess_available_min_a"]
        > soh_rows[2]["i_bess_available_min_a"]
    )
    all_soh_cases_pass = bool(all(row["status"] == "PASS" for row in soh_rows))
    status = "PASS" if all_soh_cases_pass and available_limit_order_ok else "FAIL"

    report: dict[str, Any] = {
        "task": "5.3",
        "status": status,
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "Kp_w_per_v": PI_KP_W_PER_V,
        "Ki_w_per_v_s": PI_KI_W_PER_V_S,
        "load_step_pct": 100.0 * MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
        "all_soh_cases_pass": all_soh_cases_pass,
        "available_limit_order_ok": available_limit_order_ok,
        "soh_cases": soh_rows,
        "comparison": {
            "no_support": no_support_result,
            "corrected_support": nominal_result,
        },
        "summary_path": str(Path(summary_path)),
        "soh_csv_path": str(soh_csv_path),
        "comparison_csv_path": str(comparison_csv_path),
        "figure_path": str(figure_path),
        "doc_path": str(Path(doc_path)),
        "limitations": [
            "averaged reduced-order converter model",
            "no BMS communication delay or thermal dynamics",
            "6.5 s horizon does not establish long-term ageing performance",
            "minimal admissible PI tuning is not a global optimum",
        ],
    }

    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    clean = _json_ready(report)
    with summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(clean, summary_file, indent=2, sort_keys=True)
        summary_file.write("\n")

    doc_path = Path(doc_path)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(build_markdown_report(clean), encoding="utf-8")

    for row in soh_rows:
        print(
            f"scenario={row['label']} | status={row['status']} | "
            f"discharge={row['discharge_observed_post_step']} | "
            f"i_limit_pass={row['current_limit_pass']} | "
            f"p_limit_pass={row['power_limit_pass']}"
        )
    print(f"available_limit_order_ok={available_limit_order_ok}")
    print(f"task_5_3_bess_soh_support_status={status}")
    print(f"figure_path={figure_path}")
    print(f"summary_path={summary_path}")
    print(f"doc_path={doc_path}")
    return clean


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--doc-output", type=Path, default=DOC_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_validation(
        summary_path=args.summary_output,
        doc_path=args.doc_output,
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
