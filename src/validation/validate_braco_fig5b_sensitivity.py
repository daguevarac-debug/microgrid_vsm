"""Parametric sensitivity for external Braco Fig. 5(b) validations.

Runs one-at-a-time perturbations (without recalibration) over:
- q_init_case_ah: -5%, 0%, +5%
- r0_nominal_ohm: -10%, 0%, +10%
- soc_initial: 0.98, 0.999, 1.0

Scope:
- Braco Fig.5(b) SL 0.5C, 1C, 1.5C at 25C
- Reuses existing external-validation architecture/helpers
- Preserves baseline model physics and equations
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib
import numpy as np
import pandas as pd

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.capacity import Q_NOM_REF_NISSAN_LEAF_2P_AH
from bess.model import SecondLifeBattery1RC
from validation.braco_fig5b_external_common import (
    OCV_MODEL_FILENAME,
    BracoValidationCase,
    align_curves_by_ah,
    compute_metrics,
    load_and_clean_reference_curve,
    run_constant_discharge_case,
)
from validation.validate_braco_fig5b_sl_0p5c import CASE as CASE_0P5C
from validation.validate_braco_fig5b_sl_1c import CASE as CASE_1C
from validation.validate_braco_fig5b_sl_1p5c import CASE as CASE_1P5C

DEFAULT_R0_OHM = 0.000970
DEFAULT_SOC_INITIAL = 0.999
OUTPUT_SUBDIR = Path("outputs") / "validation" / "braco_fig5b_sensitivity"

Q_INIT_REL_SWEEP = (-0.05, 0.0, 0.05)
R0_REL_SWEEP = (-0.10, 0.0, 0.10)
SOC_ABS_SWEEP = (0.98, 0.999, 1.0)


@dataclass(frozen=True)
class SweepSpec:
    parameter: str
    mode: str
    sweep_values: tuple[float, ...]


SWEEPS = (
    SweepSpec("q_init_case_ah", "relative", Q_INIT_REL_SWEEP),
    SweepSpec("r0_nominal_ohm", "relative", R0_REL_SWEEP),
    SweepSpec("soc_initial", "absolute", SOC_ABS_SWEEP),
)


def _build_model(
    ocv_model_path: Path,
    q_init_case_ah: float,
    r0_nominal_ohm: float,
    soc_initial: float,
) -> SecondLifeBattery1RC:
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


def _safe_mkdir(path: Path) -> str | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return f"Could not create output directory {path}: {exc}"
    return None


def _safe_write_csv(df: pd.DataFrame, path: Path) -> str | None:
    try:
        df.to_csv(path, index=False, encoding="utf-8")
    except Exception as exc:
        return f"Could not write CSV {path}: {exc}"
    return None


def _safe_plot_mape_impact(summary_df: pd.DataFrame, fig_path: Path, show: bool) -> str | None:
    try:
        if not show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        cases = list(summary_df["case_label"])
        x = np.arange(len(cases))
        width = 0.25

        q_vals = summary_df["mape_impact_span_q_init_case_ah"].to_numpy(dtype=float)
        r0_vals = summary_df["mape_impact_span_r0_nominal_ohm"].to_numpy(dtype=float)
        soc_vals = summary_df["mape_impact_span_soc_initial"].to_numpy(dtype=float)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(x - width, q_vals, width=width, label="q_init_case_ah")
        ax.bar(x, r0_vals, width=width, label="r0_nominal_ohm")
        ax.bar(x + width, soc_vals, width=width, label="soc_initial")
        ax.set_xticks(x)
        ax.set_xticklabels(cases, rotation=10, ha="right")
        ax.set_ylabel("MAPE impact span [%]")
        ax.set_title("Braco Fig.5(b): MAPE sensitivity span by parameter")
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(fig_path, dpi=150)
        if show:
            plt.show()
        plt.close(fig)
    except Exception as exc:
        return f"Could not save figure {fig_path}: {exc}"
    return None


def _argmax_param(row: pd.Series, metric_prefix: str) -> str:
    values = {
        "q_init_case_ah": float(row[f"{metric_prefix}_q_init_case_ah"]),
        "r0_nominal_ohm": float(row[f"{metric_prefix}_r0_nominal_ohm"]),
        "soc_initial": float(row[f"{metric_prefix}_soc_initial"]),
    }
    return max(values, key=values.get)


def _impact_note(delta_mape: float, delta_cutoff: float) -> str:
    return (
        f"delta_mape={delta_mape:+.3e}% ; "
        f"delta_cutoff_capacity_err_ah={delta_cutoff:+.3e}"
    )


def _run_single_case(
    case: BracoValidationCase,
    ocv_model_path: Path,
) -> list[dict[str, object]]:
    curve_path = REPO_ROOT / case.input_curve_filename
    reference = load_and_clean_reference_curve(curve_path)
    q_base = float(np.max(reference.ah))
    r0_base = DEFAULT_R0_OHM
    soc_base = DEFAULT_SOC_INITIAL
    ah_target = float(np.max(reference.ah))

    runs: list[dict[str, object]] = []
    base_metrics: dict[str, float] | None = None

    for sweep in SWEEPS:
        for sweep_val in sweep.sweep_values:
            q_val = q_base
            r0_val = r0_base
            soc_val = soc_base
            if sweep.parameter == "q_init_case_ah":
                q_val = q_base * (1.0 + float(sweep_val))
            elif sweep.parameter == "r0_nominal_ohm":
                r0_val = r0_base * (1.0 + float(sweep_val))
            elif sweep.parameter == "soc_initial":
                soc_val = float(sweep_val)
            else:
                raise ValueError(f"Unsupported parameter: {sweep.parameter}")

            run_record: dict[str, object] = {
                "case_label": case.case_label,
                "input_curve_filename": case.input_curve_filename,
                "discharge_current_a": case.discharge_current_a,
                "parameter": sweep.parameter,
                "sweep_mode": sweep.mode,
                "sweep_value": float(sweep_val),
                "is_baseline_run": bool(np.isclose(float(sweep_val), 0.0))
                if sweep.mode == "relative"
                else bool(np.isclose(float(sweep_val), soc_base)),
                "q_init_case_ah_used": q_val,
                "r0_nominal_ohm_used": r0_val,
                "soc_initial_used": soc_val,
                "status": "ok",
                "error_message": "",
            }

            try:
                model = _build_model(
                    ocv_model_path=ocv_model_path,
                    q_init_case_ah=q_val,
                    r0_nominal_ohm=r0_val,
                    soc_initial=soc_val,
                )
                simulation = run_constant_discharge_case(
                    model=model,
                    i_bess_discharge_a=case.discharge_current_a,
                    ah_target=ah_target,
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
                run_record.update(metrics)
            except Exception as exc:
                run_record.update(
                    {
                        "status": "error",
                        "error_message": str(exc),
                        "mae_v": np.nan,
                        "rmse_v": np.nan,
                        "nrmse_ref_range": np.nan,
                        "mape_pct": np.nan,
                        "max_abs_err_v": np.nan,
                        "n_points": np.nan,
                        "ah_cutoff_ref": np.nan,
                        "ah_cutoff_sim": np.nan,
                        "cutoff_capacity_err_ah": np.nan,
                        "abs_cutoff_capacity_err_ah": np.nan,
                    }
                )

            if run_record["parameter"] == "q_init_case_ah" and run_record["is_baseline_run"]:
                if run_record["status"] == "ok":
                    base_metrics = {
                        "mape_pct": float(run_record["mape_pct"]),
                        "cutoff_capacity_err_ah": float(run_record["cutoff_capacity_err_ah"]),
                    }

            if base_metrics is None:
                run_record["delta_mape_vs_base_pct"] = np.nan
                run_record["delta_cutoff_capacity_err_ah_vs_base"] = np.nan
                run_record["impact_observation"] = "baseline not set yet"
            elif run_record["status"] == "ok":
                delta_mape = float(run_record["mape_pct"]) - base_metrics["mape_pct"]
                delta_cutoff = (
                    float(run_record["cutoff_capacity_err_ah"])
                    - base_metrics["cutoff_capacity_err_ah"]
                )
                run_record["delta_mape_vs_base_pct"] = delta_mape
                run_record["delta_cutoff_capacity_err_ah_vs_base"] = delta_cutoff
                run_record["impact_observation"] = _impact_note(delta_mape, delta_cutoff)
            else:
                run_record["delta_mape_vs_base_pct"] = np.nan
                run_record["delta_cutoff_capacity_err_ah_vs_base"] = np.nan
                run_record["impact_observation"] = "run error"

            runs.append(run_record)
            print(
                f"case={run_record['case_label']} | "
                f"parameter={run_record['parameter']} | "
                f"value={run_record['sweep_value']} | "
                f"MAPE={run_record['mape_pct']} | "
                f"cutoff_capacity_err_ah={run_record['cutoff_capacity_err_ah']} | "
                f"obs={run_record['impact_observation']}"
            )
            if run_record["status"] == "error":
                print(f"warning=Run failed for sensitivity point: {run_record['error_message']}")

    return runs


def _summarize_case(df_case: pd.DataFrame) -> dict[str, object]:
    def span(metric_col: str, parameter: str) -> float:
        vals = pd.to_numeric(
            df_case.loc[
                (df_case["parameter"] == parameter) & (df_case["status"] == "ok"),
                metric_col,
            ],
            errors="coerce",
        ).dropna()
        if vals.empty:
            return float("nan")
        return float(vals.max() - vals.min())

    summary = {
        "case_label": str(df_case["case_label"].iloc[0]),
        "mape_impact_span_q_init_case_ah": span("mape_pct", "q_init_case_ah"),
        "mape_impact_span_r0_nominal_ohm": span("mape_pct", "r0_nominal_ohm"),
        "mape_impact_span_soc_initial": span("mape_pct", "soc_initial"),
        "cutoff_impact_span_q_init_case_ah": span("cutoff_capacity_err_ah", "q_init_case_ah"),
        "cutoff_impact_span_r0_nominal_ohm": span("cutoff_capacity_err_ah", "r0_nominal_ohm"),
        "cutoff_impact_span_soc_initial": span("cutoff_capacity_err_ah", "soc_initial"),
        "n_ok_runs": int((df_case["status"] == "ok").sum()),
        "n_error_runs": int((df_case["status"] == "error").sum()),
    }
    summary["highest_mape_impact_param"] = _argmax_param(
        pd.Series(summary), "mape_impact_span"
    )
    summary["highest_cutoff_impact_param"] = _argmax_param(
        pd.Series(summary), "cutoff_impact_span"
    )
    return summary


def _print_case_conclusion(row: pd.Series) -> None:
    mape_param = str(row["highest_mape_impact_param"])
    cutoff_param = str(row["highest_cutoff_impact_param"])
    mape_span = float(row[f"mape_impact_span_{mape_param}"])
    cutoff_span = float(row[f"cutoff_impact_span_{cutoff_param}"])

    print(f"\nConclusion case={row['case_label']}")
    print(
        "MAPE shows highest sensitivity to "
        f"{mape_param} "
        f"(span={mape_span:.6e}%)."
    )
    print(
        "cutoff_capacity_err_ah shows highest sensitivity to "
        f"{cutoff_param} "
        f"(span={cutoff_span:.6e} Ah)."
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sensitivity for Braco Fig.5(b) external validation cases."
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the summary figure in addition to saving it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    ocv_model_path = REPO_ROOT / OCV_MODEL_FILENAME
    if not ocv_model_path.exists():
        raise FileNotFoundError(f"OCV model file not found: {ocv_model_path}")

    cases = (CASE_0P5C, CASE_1C, CASE_1P5C)
    all_runs: list[dict[str, object]] = []
    for case in cases:
        all_runs.extend(_run_single_case(case=case, ocv_model_path=ocv_model_path))

    runs_df = pd.DataFrame(all_runs)
    summary_records = []
    for case_label in runs_df["case_label"].drop_duplicates().tolist():
        summary_records.append(_summarize_case(runs_df[runs_df["case_label"] == case_label]))
    summary_df = pd.DataFrame(summary_records)

    out_dir = REPO_ROOT / OUTPUT_SUBDIR
    warnings: list[str] = []
    mkdir_warning = _safe_mkdir(out_dir)
    if mkdir_warning:
        warnings.append(mkdir_warning)
    else:
        runs_warning = _safe_write_csv(runs_df, out_dir / "sensitivity_runs.csv")
        if runs_warning:
            warnings.append(runs_warning)
        summary_warning = _safe_write_csv(summary_df, out_dir / "sensitivity_summary.csv")
        if summary_warning:
            warnings.append(summary_warning)
        fig_warning = _safe_plot_mape_impact(
            summary_df=summary_df,
            fig_path=out_dir / "mape_sensitivity_span.png",
            show=bool(args.show),
        )
        if fig_warning:
            warnings.append(fig_warning)

    print("\n=== Sensitivity Summary ===")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(summary_df)
    if warnings:
        for warning_text in warnings:
            print(f"warning={warning_text}")

    for _, row in summary_df.iterrows():
        _print_case_conclusion(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
