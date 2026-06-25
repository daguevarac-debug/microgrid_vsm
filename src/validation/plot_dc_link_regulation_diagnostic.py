"""Create the consolidated DC-link regulation diagnostic for Task 5.1.

The script reads the severe 40% load-step signal CSV and creates a reproducible
three-panel figure with a shared time axis:
1. Vdc with reference, acceptance band and minimum required voltage.
2. Load, PV-source and BESS DC powers.
3. BESS current.

The figure and numerical summary are stored under
``outputs/validation/dc_link_regulation/``. No controller or plant equation is
modified by this diagnostic.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import MICROGRID_LOAD_STEP_TIME_S_DEFAULT
from tuning_metrics import DEFAULT_TUNING_CRITERIA, dc_link_performance_metrics


INPUT_CSV_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "dclink_energy_diagnostic"
    / "gfm_m80_d1500_severe_40pct_energy_signals.csv"
)
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "dc_link_regulation"
OUTPUT_FIGURE_PATH = OUTPUT_DIR / "gfm_m80_d1500_severe_40pct_dc_link_regulation.png"
OUTPUT_SUMMARY_PATH = OUTPUT_DIR / "gfm_m80_d1500_severe_40pct_dc_link_regulation_summary.json"
REQUIRED_COLUMNS = (
    "time_s",
    "vdc_v",
    "p_load_w",
    "p_source_pv_dc_w",
    "p_bess_dc_w",
    "i_bess_a",
)


def load_diagnostic_signals(csv_path: Path) -> dict[str, np.ndarray]:
    """Load and validate the severe-case signal CSV."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {path}")

    values = {name: [] for name in REQUIRED_COLUMNS}
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
        if missing:
            raise ValueError(
                "Input CSV is missing required columns: " + ", ".join(missing)
            )
        for row_number, row in enumerate(reader, start=2):
            for name in REQUIRED_COLUMNS:
                try:
                    value = float(row[name])
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Row {row_number}: column {name!r} must be numeric."
                    ) from exc
                if not np.isfinite(value):
                    raise ValueError(
                        f"Row {row_number}: column {name!r} must be finite."
                    )
                values[name].append(value)

    arrays = {name: np.asarray(series, dtype=float) for name, series in values.items()}
    if arrays["time_s"].size < 2:
        raise ValueError("Input CSV must contain at least two samples.")
    if not np.all(np.diff(arrays["time_s"]) > 0.0):
        raise ValueError("time_s must be strictly increasing.")
    return arrays


def _mean_over_mask(values: np.ndarray, mask: np.ndarray) -> float:
    return float(np.mean(values[mask])) if np.any(mask) else float("nan")


def _classify_exchange_mode(current_a: np.ndarray, atol: float = 1e-8) -> str:
    discharge = bool(np.any(current_a > atol))
    charge = bool(np.any(current_a < -atol))
    if discharge and charge:
        return "bidirectional"
    if discharge:
        return "discharge_only"
    if charge:
        return "charge_only"
    return "idle"


def build_numerical_summary(
    signals: dict[str, np.ndarray],
    *,
    t_step: float = MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
) -> dict[str, Any]:
    """Compute the numerical summary used by the figure and report."""
    t = signals["time_s"]
    vdc = signals["vdc_v"]
    post = t >= t_step
    pre = t < t_step
    if not np.any(post):
        raise ValueError("Trace must contain samples at or after t_step.")

    dc_metrics = dc_link_performance_metrics(
        t=t,
        vdc_v=vdc,
        t_step=t_step,
        criteria=DEFAULT_TUNING_CRITERIA,
    )
    pre_step_vdc = float(dc_metrics["vdc_pre_step_v"])
    band_fraction = DEFAULT_TUNING_CRITERIA.max_vdc_event_deviation_pct / 100.0
    band_lower = pre_step_vdc * (1.0 - band_fraction)
    band_upper = pre_step_vdc * (1.0 + band_fraction)

    i_bess_post = signals["i_bess_a"][post]
    p_bess_post = signals["p_bess_dc_w"][post]
    summary: dict[str, Any] = {
        "scenario": "gfm_selected_load_step_40_with_bess_energy_diagnostic",
        "status": "PASS",
        "scope": "diagnostic_before_controller_modification",
        "controller_modified": False,
        "t_step_s": float(t_step),
        "t_start_s": float(t[0]),
        "t_end_s": float(t[-1]),
        "n_samples": int(t.size),
        "acceptance_basis": "event_relative_to_pre_step_operating_point",
        "acceptance_band_pct": float(
            DEFAULT_TUNING_CRITERIA.max_vdc_event_deviation_pct
        ),
        "acceptance_band_lower_v": float(band_lower),
        "acceptance_band_upper_v": float(band_upper),
        **dc_metrics,
        "vdc_final_v": float(vdc[-1]),
        "vdc_final_in_acceptance_band": bool(band_lower <= vdc[-1] <= band_upper),
        "p_load_pre_step_mean_w": _mean_over_mask(signals["p_load_w"], pre),
        "p_load_post_step_mean_w": _mean_over_mask(signals["p_load_w"], post),
        "p_load_min_w": float(np.min(signals["p_load_w"])),
        "p_load_max_w": float(np.max(signals["p_load_w"])),
        "p_source_pre_step_mean_w": _mean_over_mask(
            signals["p_source_pv_dc_w"], pre
        ),
        "p_source_post_step_mean_w": _mean_over_mask(
            signals["p_source_pv_dc_w"], post
        ),
        "p_source_min_w": float(np.min(signals["p_source_pv_dc_w"])),
        "p_source_max_w": float(np.max(signals["p_source_pv_dc_w"])),
        "p_bess_post_step_mean_w": float(np.mean(p_bess_post)),
        "p_bess_post_step_min_w": float(np.min(p_bess_post)),
        "p_bess_post_step_max_w": float(np.max(p_bess_post)),
        "i_bess_post_step_mean_a": float(np.mean(i_bess_post)),
        "i_bess_post_step_min_a": float(np.min(i_bess_post)),
        "i_bess_post_step_max_a": float(np.max(i_bess_post)),
        "bess_exchange_mode_post_step": _classify_exchange_mode(i_bess_post),
        "bess_power_identity_ok": bool(
            np.allclose(
                signals["p_bess_dc_w"],
                signals["vdc_v"] * signals["i_bess_a"],
                rtol=1e-9,
                atol=1e-8,
            )
        ),
        "diagnostic_conclusion": (
            "The severe-case signals are documented before any controller change. "
            "Positive BESS power/current denotes discharge and negative values denote charge."
        ),
    }
    return summary


def save_consolidated_figure(
    signals: dict[str, np.ndarray],
    summary: dict[str, Any],
    output_path: Path,
    *,
    dpi: int = 300,
) -> Path:
    """Save the shared-time-axis Vdc, power and BESS-current figure."""
    if dpi <= 0:
        raise ValueError(f"dpi must be > 0, got {dpi}.")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    t = signals["time_s"]
    t_step = float(summary["t_step_s"])
    fig, axes = plt.subplots(3, 1, figsize=(11.0, 10.0), sharex=True)

    vdc_axis = axes[0]
    vdc_axis.fill_between(
        t,
        float(summary["acceptance_band_lower_v"]),
        float(summary["acceptance_band_upper_v"]),
        alpha=0.16,
        label=(
            "Banda de aceptación del evento "
            f"(±{float(summary['acceptance_band_pct']):.1f}%)"
        ),
    )
    vdc_axis.plot(t, signals["vdc_v"], linewidth=1.2, label="Vdc")
    vdc_axis.axhline(
        float(DEFAULT_TUNING_CRITERIA.vdc_reference_v),
        linestyle="--",
        linewidth=1.0,
        label=f"Referencia Vdc = {DEFAULT_TUNING_CRITERIA.vdc_reference_v:.1f} V",
    )
    vdc_axis.axhline(
        float(summary["vdc_min_required_v"]),
        linestyle="-.",
        linewidth=1.0,
        label=f"Vdc mínima requerida = {float(summary['vdc_min_required_v']):.2f} V",
    )
    vdc_axis.set_ylabel("Vdc [V]")
    vdc_axis.set_title("Diagnóstico energético del enlace DC ante escalón de carga del 40 %")
    vdc_axis.legend(loc="best", fontsize=8)
    vdc_axis.grid(True, alpha=0.3)

    power_axis = axes[1]
    power_axis.plot(t, signals["p_load_w"], linewidth=1.1, label="Pload")
    power_axis.plot(
        t,
        signals["p_source_pv_dc_w"],
        linewidth=1.1,
        label="Psource (FV-DC)",
    )
    power_axis.plot(t, signals["p_bess_dc_w"], linewidth=1.1, label="PBESS")
    power_axis.axhline(0.0, linewidth=0.8)
    power_axis.set_ylabel("Potencia [W]")
    power_axis.legend(loc="best", fontsize=8)
    power_axis.grid(True, alpha=0.3)

    current_axis = axes[2]
    current_axis.plot(t, signals["i_bess_a"], linewidth=1.1, label="IBESS")
    current_axis.axhline(0.0, linewidth=0.8)
    current_axis.set_xlabel("Tiempo [s]")
    current_axis.set_ylabel("Corriente [A]")
    current_axis.legend(loc="best", fontsize=8)
    current_axis.grid(True, alpha=0.3)

    for axis in axes:
        axis.axvline(
            t_step,
            linestyle="--",
            linewidth=0.9,
            label=None,
        )

    figure_note = (
        f"Vdc,min={float(summary['vdc_min_post_step_v']):.3f} V | "
        f"ΔVdc,max={float(summary['vdc_event_max_abs_deviation_v']):.3f} V | "
        f"Vdc,final={float(summary['vdc_final_v']):.3f} V | "
        f"modo BESS={summary['bess_exchange_mode_post_step']}"
    )
    fig.text(0.5, 0.01, figure_note, ha="center", fontsize=9)
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _json_ready(summary: dict[str, Any]) -> dict[str, Any]:
    ready: dict[str, Any] = {}
    for key, value in summary.items():
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            value = None
        ready[key] = value
    return ready


def run_diagnostic_plot(
    input_path: Path = INPUT_CSV_PATH,
    figure_path: Path = OUTPUT_FIGURE_PATH,
    summary_path: Path = OUTPUT_SUMMARY_PATH,
    *,
    dpi: int = 300,
) -> dict[str, Any]:
    """Generate the consolidated figure and numerical summary."""
    signals = load_diagnostic_signals(input_path)
    summary = build_numerical_summary(signals)
    saved_figure = save_consolidated_figure(
        signals,
        summary,
        figure_path,
        dpi=dpi,
    )

    json_summary = _json_ready(summary)
    json_summary.update(
        {
            "input_csv_path": str(Path(input_path)),
            "figure_path": str(saved_figure),
            "summary_path": str(Path(summary_path)),
        }
    )
    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(json_summary, summary_file, indent=2, sort_keys=True)
        summary_file.write("\n")

    print(f"status={json_summary['status']}")
    print(f"controller_modified={json_summary['controller_modified']}")
    print(f"bess_exchange_mode_post_step={json_summary['bess_exchange_mode_post_step']}")
    print(f"figure_path={saved_figure}")
    print(f"summary_path={summary_path}")
    return json_summary


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV_PATH)
    parser.add_argument("--figure-output", type=Path, default=OUTPUT_FIGURE_PATH)
    parser.add_argument("--summary-output", type=Path, default=OUTPUT_SUMMARY_PATH)
    parser.add_argument("--dpi", type=int, default=300)
    return parser.parse_args(list(argv))


def main() -> int:
    args = parse_args(sys.argv[1:])
    run_diagnostic_plot(
        input_path=args.input,
        figure_path=args.figure_output,
        summary_path=args.summary_output,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
