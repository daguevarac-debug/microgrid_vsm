"""Shared external-validation helpers for Braco Fig. 5(b) SL discharge cases.

These utilities compare literature-digitalized Voltage-vs-Ah curves against the
existing 1RC model without changing model physics.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

import matplotlib
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.capacity import Q_NOM_REF_NISSAN_LEAF_2P_AH, derive_soh_init_case
from bess.model import SecondLifeBattery1RC

OCV_MODEL_FILENAME = "OCV_SOC.xlsx"
MAPE_PASS_THRESHOLD_PCT = 10.0
# Braco (2020, 2021): nominal R0 used in external Fig.5(b) baseline validation.
R0_NOMINAL_BRACO_OHM = 0.000970


@dataclass(frozen=True)
class BracoValidationCase:
    case_label: str
    input_curve_filename: str
    discharge_current_a: float
    output_subdir: Path


@dataclass
class CurveData:
    sheet_name: str
    ah: np.ndarray
    voltage: np.ndarray


@dataclass
class SimulationData:
    t: np.ndarray
    ah: np.ndarray
    soc: np.ndarray
    vrc: np.ndarray
    voltage: np.ndarray


def _resolve_repo_paths(case: BracoValidationCase) -> tuple[Path, Path, Path]:
    repo_root = SRC_DIR.parent
    curve_path = repo_root / case.input_curve_filename
    ocv_model_path = repo_root / OCV_MODEL_FILENAME
    out_dir = repo_root / case.output_subdir
    return curve_path, ocv_model_path, out_dir


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def _find_equivalent_column(columns: list[str], candidates: set[str]) -> str | None:
    lookup = {_norm_name(col): col for col in columns}
    for candidate in candidates:
        hit = lookup.get(_norm_name(candidate))
        if hit is not None:
            return hit
    return None


def load_and_clean_reference_curve(curve_path: Path) -> CurveData:
    if not curve_path.exists():
        raise FileNotFoundError(f"Reference curve file not found: {curve_path}")

    xls = pd.ExcelFile(curve_path, engine="openpyxl")
    ah_candidates = {"Ah", "Capacity_Ah", "Q_Ah", "Discharged_Ah"}
    voltage_candidates = {"Voltage", "V", "Volt", "TerminalVoltage"}

    selected_sheet = None
    selected_df: pd.DataFrame | None = None
    selected_ah_col = None
    selected_v_col = None

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(curve_path, sheet_name=sheet_name, engine="openpyxl")
        ah_col = _find_equivalent_column(list(df.columns), ah_candidates)
        v_col = _find_equivalent_column(list(df.columns), voltage_candidates)
        if ah_col is not None and v_col is not None:
            selected_sheet = sheet_name
            selected_df = df[[ah_col, v_col]].copy()
            selected_ah_col = ah_col
            selected_v_col = v_col
            break

    if selected_df is None:
        raise KeyError(
            f"No valid sheet with Ah/Voltage equivalent columns found in {curve_path.name}."
        )

    selected_df[selected_ah_col] = pd.to_numeric(selected_df[selected_ah_col], errors="coerce")
    selected_df[selected_v_col] = pd.to_numeric(selected_df[selected_v_col], errors="coerce")
    selected_df = selected_df.dropna(subset=[selected_ah_col, selected_v_col])
    selected_df = selected_df.rename(
        columns={selected_ah_col: "ah_ref", selected_v_col: "v_ref"}
    )

    selected_df = selected_df[selected_df["ah_ref"] >= 0.0]
    selected_df = selected_df.sort_values("ah_ref", ascending=True)
    selected_df = selected_df.drop_duplicates(subset=["ah_ref"], keep="first")

    if len(selected_df) < 10:
        raise ValueError(
            "Reference curve has too few valid points after cleaning; need at least 10."
        )

    ah = selected_df["ah_ref"].to_numpy(dtype=float)
    v = selected_df["v_ref"].to_numpy(dtype=float)
    if not np.all(np.isfinite(ah)) or not np.all(np.isfinite(v)):
        raise ValueError("Reference curve contains non-finite values after cleaning.")
    if not np.all(np.diff(ah) > 0.0):
        raise ValueError("Reference Ah values must be strictly increasing after cleaning.")
    if (ah[-1] - ah[0]) <= 0.05:
        raise ValueError("Reference Ah span is too small for meaningful comparison.")

    return CurveData(sheet_name=selected_sheet, ah=ah, voltage=v)


def build_case_model(
    ocv_model_path: Path,
    q_init_case_ah: float,
    soc_initial: float,
    r0_nominal_ohm: float = R0_NOMINAL_BRACO_OHM,
) -> SecondLifeBattery1RC:
    if not ocv_model_path.exists():
        raise FileNotFoundError(f"OCV model file not found: {ocv_model_path}")

    return SecondLifeBattery1RC.from_excel_characterization(
        excel_path=ocv_model_path,
        q_nom_ref_ah=Q_NOM_REF_NISSAN_LEAF_2P_AH,
        q_init_case_ah=q_init_case_ah,
        r0_nominal_ohm=r0_nominal_ohm,
        r0_soh_sensitivity=1.0,
        k_deg=1.478e-6,
        soh_min=0.50,
        q_eff_min_ah=1e-9,
        soc_initial=soc_initial,
        soc_min=0.0,
        soc_max=1.0,
    )


def run_constant_discharge_case(
    model: SecondLifeBattery1RC,
    i_bess_discharge_a: float,
    ah_target: float,
) -> SimulationData:
    if ah_target <= 0.0:
        raise ValueError(f"ah_target must be > 0, got {ah_target}.")
    if i_bess_discharge_a <= 0.0:
        raise ValueError(f"i_bess_discharge_a must be > 0, got {i_bess_discharge_a}.")

    t_end_s = 1.05 * (3600.0 * ah_target / i_bess_discharge_a)
    n_eval = int(max(400, min(5000, np.ceil(t_end_s / 5.0))))
    t_eval = np.linspace(0.0, t_end_s, n_eval)

    x0 = model.initial_state(soc=model.soc_initial, v_rc=0.0)

    def rhs_fn(t: float, x: np.ndarray) -> list[float]:
        return model.rhs(
            t=t,
            x=x,
            i_bess=i_bess_discharge_a,
            soh=model.soh_init_case,
        )

    sol = solve_ivp(
        rhs_fn,
        (float(t_eval[0]), float(t_eval[-1])),
        x0,
        t_eval=t_eval,
        max_step=2.0,
        rtol=1e-7,
        atol=1e-9,
        events=model.soc_min_event,
        dense_output=False,
    )
    if sol.status not in (0, 1):
        raise RuntimeError(f"solve_ivp failed: {sol.message}")

    t = sol.t
    soc = sol.y[0]
    vrc = sol.y[1]
    ah_sim = (i_bess_discharge_a * t) / 3600.0
    v_sim = np.array(
        [
            model.terminal_voltage(
                soc=s_i,
                v_rc=vr_i,
                i_bess=i_bess_discharge_a,
                soh=model.soh_init_case,
            )
            for s_i, vr_i in zip(soc, vrc)
        ],
        dtype=float,
    )

    return SimulationData(t=t, ah=ah_sim, soc=soc, vrc=vrc, voltage=v_sim)


def align_curves_by_ah(
    ah_ref: np.ndarray,
    v_ref: np.ndarray,
    ah_sim: np.ndarray,
    v_sim: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ah_min = max(float(np.min(ah_ref)), float(np.min(ah_sim)))
    ah_max = min(float(np.max(ah_ref)), float(np.max(ah_sim)))
    if ah_max <= ah_min:
        raise ValueError("No common Ah domain between reference and simulation.")

    n_points = int(max(100, min(2000, max(len(ah_ref), len(ah_sim)))))
    ah_common = np.linspace(ah_min, ah_max, n_points)
    v_ref_common = np.interp(ah_common, ah_ref, v_ref)
    v_sim_common = np.interp(ah_common, ah_sim, v_sim)
    return ah_common, v_ref_common, v_sim_common


def compute_metrics(
    ah_common: np.ndarray,
    v_ref: np.ndarray,
    v_sim: np.ndarray,
) -> dict[str, float]:
    err = v_sim - v_ref
    abs_err = np.abs(err)

    mae_v = float(np.mean(abs_err))
    rmse_v = float(np.sqrt(np.mean(np.square(err))))
    v_range = float(np.max(v_ref) - np.min(v_ref))
    nrmse = float(rmse_v / v_range) if v_range > 1e-12 else float("nan")

    mape_mask = np.abs(v_ref) > 1e-12
    mape_pct = (
        float(np.mean(abs_err[mape_mask] / np.abs(v_ref[mape_mask])) * 100.0)
        if np.any(mape_mask)
        else float("nan")
    )

    # Simple cutoff-capacity proxy at reference minimum voltage.
    idx_ref_cutoff = int(np.argmin(v_ref))
    ah_cutoff_ref = float(ah_common[idx_ref_cutoff])
    v_cutoff_ref = float(v_ref[idx_ref_cutoff])
    idx_sim_cutoff = int(np.argmin(np.abs(v_sim - v_cutoff_ref)))
    ah_cutoff_sim = float(ah_common[idx_sim_cutoff])
    cutoff_capacity_err_ah = ah_cutoff_sim - ah_cutoff_ref

    return {
        "mae_v": mae_v,
        "rmse_v": rmse_v,
        "nrmse_ref_range": nrmse,
        "mape_pct": mape_pct,
        "max_abs_err_v": float(np.max(abs_err)),
        "n_points": float(len(v_ref)),
        "ah_cutoff_ref": ah_cutoff_ref,
        "ah_cutoff_sim": ah_cutoff_sim,
        "cutoff_capacity_err_ah": cutoff_capacity_err_ah,
        "abs_cutoff_capacity_err_ah": abs(cutoff_capacity_err_ah),
    }


def export_artifacts(
    case: BracoValidationCase,
    out_dir: Path,
    ah_common: np.ndarray,
    v_ref_common: np.ndarray,
    v_sim_common: np.ndarray,
    metrics: dict[str, float],
    show_plot: bool,
) -> list[str]:
    warnings: list[str] = []

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        warnings.append(f"Could not create output directory: {exc}")
        return warnings

    fig_path = out_dir / "reference_vs_simulation.png"
    aligned_csv_path = out_dir / "aligned_curves.csv"
    metrics_csv_path = out_dir / "metrics_summary.csv"

    try:
        if not show_plot:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # local import to keep helper reusable

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(ah_common, v_ref_common, label="Reference (Braco Fig.5b digitalized)", linewidth=2.0)
        ax.plot(ah_common, v_sim_common, label="Simulation (1RC model)", linewidth=2.0)
        ax.set_xlabel("Discharged capacity [Ah]")
        ax.set_ylabel("Voltage [V]")
        ax.set_title(f"External Validation: {case.case_label}")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(fig_path, dpi=150)
        if show_plot:
            plt.show()
        plt.close(fig)
    except Exception as exc:
        warnings.append(f"Could not save figure: {exc}")

    try:
        aligned_df = pd.DataFrame(
            {
                "ah_common": ah_common,
                "v_ref": v_ref_common,
                "v_sim": v_sim_common,
                "v_err": v_sim_common - v_ref_common,
                "abs_v_err": np.abs(v_sim_common - v_ref_common),
            }
        )
        aligned_df.to_csv(aligned_csv_path, index=False, encoding="utf-8")
    except Exception as exc:
        warnings.append(f"Could not save aligned curves CSV: {exc}")

    try:
        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_csv(metrics_csv_path, index=False, encoding="utf-8")
    except Exception as exc:
        warnings.append(f"Could not save metrics CSV: {exc}")

    return warnings


def print_console_report(
    case: BracoValidationCase,
    reference: CurveData,
    q_init_case_ah: float,
    soh_init_case: float,
    metrics: dict[str, float],
    output_dir: Path,
    warnings: list[str],
) -> None:
    print(f"\n--- External Validation: {case.case_label} ---")
    print(f"input_file={case.input_curve_filename}")
    print(f"sheet_used={reference.sheet_name}")
    print(f"reference_points={len(reference.ah)}")
    print(f"q_nom_ref_ah={Q_NOM_REF_NISSAN_LEAF_2P_AH:.6f}")
    print(f"i_bess_discharge_a={case.discharge_current_a:.6f}")
    print(f"q_init_case_ah={q_init_case_ah:.6f}")
    print(f"soh_init_case={soh_init_case:.6f}")
    print(f"ah_ref_min={reference.ah.min():.6f}, ah_ref_max={reference.ah.max():.6f}")
    print(f"mae_v={metrics['mae_v']:.6e}")
    print(f"rmse_v={metrics['rmse_v']:.6e}")
    print(f"nrmse_ref_range={metrics['nrmse_ref_range']:.6e}")
    print(f"mape_pct={metrics['mape_pct']:.6e}")
    print(f"max_abs_err_v={metrics['max_abs_err_v']:.6e}")
    print(f"n_points={int(metrics['n_points'])}")
    print(f"ah_cutoff_ref={metrics['ah_cutoff_ref']:.6f}")
    print(f"ah_cutoff_sim={metrics['ah_cutoff_sim']:.6f}")
    print(f"cutoff_capacity_err_ah={metrics['cutoff_capacity_err_ah']:.6e}")
    print(f"abs_cutoff_capacity_err_ah={metrics['abs_cutoff_capacity_err_ah']:.6e}")

    status = "PASS" if metrics["mape_pct"] < MAPE_PASS_THRESHOLD_PCT else "FAIL"
    print(f"criterion=MAPE<{MAPE_PASS_THRESHOLD_PCT:.1f}%")
    print(f"status={status}")
    print(f"output_dir={output_dir}")
    for warning_text in warnings:
        print(f"warning={warning_text}")


def parse_args(case: BracoValidationCase, argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"External validation vs {case.case_label} digitalized curve."
    )
    parser.add_argument(
        "--q-init-case-ah",
        type=float,
        default=None,
        help=(
            "Initial available capacity for the case [Ah]. "
            "Default: max Ah from the digitalized reference curve."
        ),
    )
    parser.add_argument(
        "--soc-initial",
        type=float,
        default=0.999,
        help="Initial SoC for discharge simulation (near 1.0 by default).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show plot window in addition to file export.",
    )
    return parser.parse_args(argv)


def run_case(case: BracoValidationCase, argv: list[str] | None = None) -> int:
    args = parse_args(case, sys.argv[1:] if argv is None else argv)
    curve_path, ocv_model_path, output_dir = _resolve_repo_paths(case)
    reference = load_and_clean_reference_curve(curve_path)

    # q_init_case_ah is case-dependent; not a universal second-life value.
    q_init_case_ah = (
        float(np.max(reference.ah)) if args.q_init_case_ah is None else float(args.q_init_case_ah)
    )
    if q_init_case_ah <= 0.0:
        raise ValueError(f"q_init_case_ah must be > 0, got {q_init_case_ah}.")

    soh_init_case = derive_soh_init_case(
        q_init_case_ah=q_init_case_ah,
        q_nom_ref_ah=Q_NOM_REF_NISSAN_LEAF_2P_AH,
    )

    model = build_case_model(
        ocv_model_path=ocv_model_path,
        q_init_case_ah=q_init_case_ah,
        soc_initial=float(args.soc_initial),
    )
    simulation = run_constant_discharge_case(
        model=model,
        i_bess_discharge_a=case.discharge_current_a,
        ah_target=float(np.max(reference.ah)),
    )

    ah_common, v_ref_common, v_sim_common = align_curves_by_ah(
        ah_ref=reference.ah,
        v_ref=reference.voltage,
        ah_sim=simulation.ah,
        v_sim=simulation.voltage,
    )
    metrics = compute_metrics(
        ah_common=ah_common,
        v_ref=v_ref_common,
        v_sim=v_sim_common,
    )
    warnings = export_artifacts(
        case=case,
        out_dir=output_dir,
        ah_common=ah_common,
        v_ref_common=v_ref_common,
        v_sim_common=v_sim_common,
        metrics=metrics,
        show_plot=bool(args.show),
    )
    print_console_report(
        case=case,
        reference=reference,
        q_init_case_ah=q_init_case_ah,
        soh_init_case=soh_init_case,
        metrics=metrics,
        output_dir=output_dir,
        warnings=warnings,
    )

    return 0 if metrics["mape_pct"] < MAPE_PASS_THRESHOLD_PCT else 1
