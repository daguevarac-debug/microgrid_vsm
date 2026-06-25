"""Create a reproducible DC-link step-response figure for Task 5.1.

The figure is generated from the severe 40% load-step CSV and includes:
- nominal Vdc reference,
- event-relative acceptance band,
- minimum required DC voltage,
- observed post-step minimum,
- maximum event-induced deviation,
- recovery time with dwell,
- final DC-link state.

No model or controller equation is modified.
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
from tuning_metrics import DEFAULT_TUNING_CRITERIA, TuningCriteria, dc_link_performance_metrics


INPUT_CSV_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "dclink_energy_diagnostic"
    / "gfm_m80_d1500_severe_40pct_energy_signals.csv"
)
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "dclink_energy_diagnostic"
OUTPUT_FIGURE_PATH = OUTPUT_DIR / "gfm_m80_d1500_severe_40pct_vdc_response.png"
OUTPUT_METRICS_PATH = OUTPUT_DIR / "gfm_m80_d1500_severe_40pct_vdc_response_metrics.json"
REQUIRED_COLUMNS = ("time_s", "vdc_v")


def load_vdc_trace(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load and validate time and Vdc columns from the diagnostic CSV."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {path}")

    time_values: list[float] = []
    vdc_values: list[float] = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
        if missing:
            raise ValueError(
                "Input CSV is missing required columns: " + ", ".join(missing)
            )
        for row_number, row in enumerate(reader, start=2):
            try:
                time_s = float(row["time_s"])
                vdc_v = float(row["vdc_v"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Row {row_number}: time_s and vdc_v must be numeric."
                ) from exc
            if not np.isfinite(time_s) or not np.isfinite(vdc_v):
                raise ValueError(
                    f"Row {row_number}: time_s and vdc_v must be finite."
                )
            time_values.append(time_s)
            vdc_values.append(vdc_v)

    time = np.asarray(time_values, dtype=float)
    vdc = np.asarray(vdc_values, dtype=float)
    if time.size < 2:
        raise ValueError("Input CSV must contain at least two samples.")
    if not np.all(np.diff(time) > 0.0):
        raise ValueError("time_s must be strictly increasing.")
    return time, vdc


def _recovery_time_with_dwell(
    t: np.ndarray,
    vdc: np.ndarray,
    *,
    t_step: float,
    lower_bound_v: float,
    upper_bound_v: float,
    dwell_s: float,
) -> tuple[float, int | None]:
    """Return first post-step in-band time sustained for the full dwell."""
    post_indices = np.flatnonzero(t >= t_step)
    if post_indices.size == 0:
        raise ValueError("Trace must contain samples at or after t_step.")
    for global_start in post_indices:
        end_time = float(t[global_start]) + dwell_s
        global_end = int(np.searchsorted(t, end_time, side="left"))
        if global_end >= t.size:
            break
        interval = vdc[global_start : global_end + 1]
        if np.all((interval >= lower_bound_v) & (interval <= upper_bound_v)):
            return float(t[global_start] - t_step), int(global_start)
    return float("nan"), None


def build_response_metrics(
    t: np.ndarray,
    vdc: np.ndarray,
    *,
    t_step: float = MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    criteria: TuningCriteria = DEFAULT_TUNING_CRITERIA,
) -> dict[str, Any]:
    """Build plot annotations using the repository DC-link criteria."""
    base_metrics = dc_link_performance_metrics(
        t=t,
        vdc_v=vdc,
        t_step=t_step,
        criteria=criteria,
    )
    vdc_pre = float(base_metrics["vdc_pre_step_v"])
    band_fraction = criteria.max_vdc_event_deviation_pct / 100.0
    lower_bound = vdc_pre * (1.0 - band_fraction)
    upper_bound = vdc_pre * (1.0 + band_fraction)

    post_indices = np.flatnonzero(t >= t_step)
    post_vdc = vdc[post_indices]
    minimum_local_index = int(np.argmin(post_vdc))
    minimum_index = int(post_indices[minimum_local_index])
    deviation_local_index = int(np.argmax(np.abs(post_vdc - vdc_pre)))
    deviation_index = int(post_indices[deviation_local_index])

    recovery_time_s, recovery_index = _recovery_time_with_dwell(
        t,
        vdc,
        t_step=t_step,
        lower_bound_v=lower_bound,
        upper_bound_v=upper_bound,
        dwell_s=criteria.frequency_recovery_dwell_s,
    )
    final_vdc = float(vdc[-1])
    final_in_band = bool(lower_bound <= final_vdc <= upper_bound)

    return {
        **base_metrics,
        "t_step_s": float(t_step),
        "vdc_reference_v": float(criteria.vdc_reference_v),
        "acceptance_basis": "event_relative_to_pre_step_operating_point",
        "acceptance_band_pct": float(criteria.max_vdc_event_deviation_pct),
        "acceptance_band_lower_v": float(lower_bound),
        "acceptance_band_upper_v": float(upper_bound),
        "recovery_dwell_s": float(criteria.frequency_recovery_dwell_s),
        "vdc_recovery_time_s": float(recovery_time_s),
        "recovery_verified": bool(np.isfinite(recovery_time_s)),
        "minimum_time_s": float(t[minimum_index]),
        "maximum_deviation_time_s": float(t[deviation_index]),
        "maximum_deviation_value_v": float(vdc[deviation_index]),
        "final_time_s": float(t[-1]),
        "vdc_final_v": final_vdc,
        "final_in_acceptance_band": final_in_band,
        "minimum_index": minimum_index,
        "maximum_deviation_index": deviation_index,
        "recovery_index": recovery_index,
    }


def save_step_response_figure(
    t: np.ndarray,
    vdc: np.ndarray,
    metrics: dict[str, Any],
    output_path: Path,
    *,
    dpi: int = 300,
) -> Path:
    """Render and save the annotated severe-step Vdc response."""
    if dpi <= 0:
        raise ValueError(f"dpi must be > 0, got {dpi}.")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, axis = plt.subplots(figsize=(10.5, 6.2))
    lower = float(metrics["acceptance_band_lower_v"])
    upper = float(metrics["acceptance_band_upper_v"])
    reference = float(metrics["vdc_reference_v"])
    pre_step = float(metrics["vdc_pre_step_v"])
    minimum_required = float(metrics["vdc_min_required_v"])
    t_step = float(metrics["t_step_s"])

    axis.fill_between(
        t,
        lower,
        upper,
        alpha=0.16,
        label=(
            "Banda de aceptación del evento "
            f"(±{float(metrics['acceptance_band_pct']):.1f}% de Vdc preescalón)"
        ),
    )
    axis.plot(t, vdc, linewidth=1.25, label="Vdc simulada")
    axis.axhline(reference, linestyle="--", linewidth=1.1, label=f"Referencia Vdc = {reference:.1f} V")
    axis.axhline(pre_step, linestyle=":", linewidth=1.0, label=f"Vdc preescalón = {pre_step:.2f} V")
    axis.axhline(
        minimum_required,
        linestyle="-.",
        linewidth=1.0,
        label=f"Vdc mínima requerida = {minimum_required:.2f} V",
    )
    axis.axvline(t_step, linestyle="--", linewidth=1.0, label=f"Escalón de carga, t = {t_step:.2f} s")

    minimum_index = int(metrics["minimum_index"])
    deviation_index = int(metrics["maximum_deviation_index"])
    final_index = t.size - 1
    axis.scatter([t[minimum_index]], [vdc[minimum_index]], zorder=5)
    axis.annotate(
        f"Mínimo observado\n{vdc[minimum_index]:.3f} V",
        xy=(t[minimum_index], vdc[minimum_index]),
        xytext=(10, -36),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->"},
    )
    axis.scatter([t[deviation_index]], [vdc[deviation_index]], zorder=5)
    axis.annotate(
        "Desviación máxima\n"
        f"{float(metrics['vdc_event_max_abs_deviation_v']):.3f} V "
        f"({float(metrics['vdc_event_max_abs_deviation_pct']):.3f}%)",
        xy=(t[deviation_index], vdc[deviation_index]),
        xytext=(12, 28),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->"},
    )

    recovery_index = metrics["recovery_index"]
    if recovery_index is not None:
        recovery_index = int(recovery_index)
        axis.scatter([t[recovery_index]], [vdc[recovery_index]], zorder=5)
        recovery_label = f"Recuperación = {float(metrics['vdc_recovery_time_s']):.4f} s"
        axis.annotate(
            recovery_label,
            xy=(t[recovery_index], vdc[recovery_index]),
            xytext=(10, 46),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->"},
        )
    else:
        recovery_label = "Recuperación no verificada"

    axis.scatter([t[final_index]], [vdc[final_index]], zorder=5)
    final_state = "dentro" if bool(metrics["final_in_acceptance_band"]) else "fuera"
    axis.annotate(
        f"Estado final\n{vdc[final_index]:.3f} V ({final_state} de banda)",
        xy=(t[final_index], vdc[final_index]),
        xytext=(-125, -42),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->"},
    )

    axis.set_xlabel("Tiempo [s]")
    axis.set_ylabel("Tensión del enlace DC [V]")
    axis.set_title("Respuesta del enlace DC ante escalón severo de carga del 40 %")
    axis.grid(True, alpha=0.3)
    axis.legend(loc="best", fontsize=8)
    axis.text(
        0.01,
        0.01,
        recovery_label,
        transform=axis.transAxes,
        fontsize=9,
        verticalalignment="bottom",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _json_ready_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    excluded = {"minimum_index", "maximum_deviation_index", "recovery_index"}
    for key, value in metrics.items():
        if key in excluded:
            continue
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            value = None
        clean[key] = value
    return clean


def run_plot(
    input_path: Path = INPUT_CSV_PATH,
    output_path: Path = OUTPUT_FIGURE_PATH,
    metrics_path: Path = OUTPUT_METRICS_PATH,
    *,
    dpi: int = 300,
) -> dict[str, Any]:
    """Load the severe trace, compute annotations and save PNG plus JSON."""
    t, vdc = load_vdc_trace(input_path)
    metrics = build_response_metrics(t, vdc)
    figure_path = save_step_response_figure(t, vdc, metrics, output_path, dpi=dpi)

    json_metrics = _json_ready_metrics(metrics)
    json_metrics.update(
        {
            "input_csv_path": str(Path(input_path)),
            "figure_path": str(figure_path),
            "status": "PASS",
        }
    )
    metrics_path = Path(metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8") as metrics_file:
        json.dump(json_metrics, metrics_file, indent=2, sort_keys=True)
        metrics_file.write("\n")

    print(f"status={json_metrics['status']}")
    print(f"vdc_reference_v={json_metrics['vdc_reference_v']:.6f}")
    print(
        "acceptance_band_v="
        f"[{json_metrics['acceptance_band_lower_v']:.6f}, "
        f"{json_metrics['acceptance_band_upper_v']:.6f}]"
    )
    print(f"vdc_min_post_step_v={json_metrics['vdc_min_post_step_v']:.6f}")
    print(
        "vdc_event_max_abs_deviation_v="
        f"{json_metrics['vdc_event_max_abs_deviation_v']:.6f}"
    )
    print(f"vdc_recovery_time_s={json_metrics['vdc_recovery_time_s']}")
    print(f"vdc_final_v={json_metrics['vdc_final_v']:.6f}")
    print(f"figure_path={figure_path}")
    print(f"metrics_path={metrics_path}")
    return json_metrics


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_FIGURE_PATH)
    parser.add_argument("--metrics-output", type=Path, default=OUTPUT_METRICS_PATH)
    parser.add_argument("--dpi", type=int, default=300)
    return parser.parse_args(list(argv))


def main() -> int:
    args = parse_args(sys.argv[1:])
    run_plot(
        input_path=args.input,
        output_path=args.output,
        metrics_path=args.metrics_output,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
