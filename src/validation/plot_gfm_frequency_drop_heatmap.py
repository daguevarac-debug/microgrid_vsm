"""Generate a heatmap of maximum frequency drop versus GFM parameters M and D.

The input CSV must contain a complete rectangular grid with the columns
``M``, ``D`` and ``max_frequency_drop_hz``. The resulting figure is saved in
headless mode and is suitable for reproducible validation reports.

Default input:
    outputs/validation/gfm_tuning/refinement_iter2_m20-40_d50-100.csv

Default output:
    outputs/validation/gfm_tuning/frequency_drop_heatmap_refinement_iter2.png
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_INPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "refinement_iter2_m20-40_d50-100.csv"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "frequency_drop_heatmap_refinement_iter2.png"
)
REQUIRED_COLUMNS = ("M", "D", "max_frequency_drop_hz")


@dataclass(frozen=True)
class FrequencyDropGrid:
    """Sorted rectangular frequency-drop grid ready for plotting."""

    m_values: tuple[float, ...]
    d_values: tuple[float, ...]
    drop_hz: np.ndarray

    def __post_init__(self) -> None:
        expected_shape = (len(self.m_values), len(self.d_values))
        if self.drop_hz.shape != expected_shape:
            raise ValueError(
                f"drop_hz shape must be {expected_shape}, got {self.drop_hz.shape}."
            )
        if not np.all(np.isfinite(self.drop_hz)):
            raise ValueError("drop_hz must contain only finite values.")
        if np.any(self.drop_hz < 0.0):
            raise ValueError("Frequency-drop values must be >= 0 Hz.")


def _parse_finite_float(row: dict[str, str], column: str, row_number: int) -> float:
    raw_value = row.get(column, "")
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Row {row_number}: column {column!r} must be numeric, got {raw_value!r}."
        ) from exc
    if not np.isfinite(value):
        raise ValueError(
            f"Row {row_number}: column {column!r} must be finite, got {raw_value!r}."
        )
    return value


def load_frequency_drop_grid(csv_path: Path) -> FrequencyDropGrid:
    """Load and validate a complete rectangular ``(M, D)`` result grid."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {path}")

    values_by_pair: dict[tuple[float, float], float] = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing_columns = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
        if missing_columns:
            raise ValueError(
                "Input CSV is missing required columns: "
                + ", ".join(missing_columns)
            )

        for row_number, row in enumerate(reader, start=2):
            inertia_m = _parse_finite_float(row, "M", row_number)
            damping_d = _parse_finite_float(row, "D", row_number)
            frequency_drop_hz = _parse_finite_float(
                row,
                "max_frequency_drop_hz",
                row_number,
            )
            if inertia_m <= 0.0:
                raise ValueError(f"Row {row_number}: M must be > 0, got {inertia_m}.")
            if damping_d < 0.0:
                raise ValueError(f"Row {row_number}: D must be >= 0, got {damping_d}.")
            if frequency_drop_hz < 0.0:
                raise ValueError(
                    f"Row {row_number}: max_frequency_drop_hz must be >= 0, "
                    f"got {frequency_drop_hz}."
                )

            pair = (inertia_m, damping_d)
            if pair in values_by_pair:
                raise ValueError(
                    f"Duplicate result for M={inertia_m:g}, D={damping_d:g}."
                )
            values_by_pair[pair] = frequency_drop_hz

    if not values_by_pair:
        raise ValueError("Input CSV contains no result rows.")

    m_values = tuple(sorted({pair[0] for pair in values_by_pair}))
    d_values = tuple(sorted({pair[1] for pair in values_by_pair}))
    expected_pairs = {
        (inertia_m, damping_d)
        for inertia_m in m_values
        for damping_d in d_values
    }
    missing_pairs = sorted(expected_pairs.difference(values_by_pair))
    if missing_pairs:
        formatted = ", ".join(
            f"(M={inertia_m:g}, D={damping_d:g})"
            for inertia_m, damping_d in missing_pairs
        )
        raise ValueError(
            "Input CSV does not form a complete rectangular grid; missing "
            + formatted
            + "."
        )

    drop_hz = np.array(
        [
            [values_by_pair[(inertia_m, damping_d)] for damping_d in d_values]
            for inertia_m in m_values
        ],
        dtype=float,
    )
    return FrequencyDropGrid(
        m_values=m_values,
        d_values=d_values,
        drop_hz=drop_hz,
    )


def annotation_text_color(normalized_value: float) -> str:
    """Return readable annotation color for the default dark-to-bright colormap."""
    value = float(normalized_value)
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(
            f"normalized_value must be finite and within [0, 1], got {normalized_value}."
        )
    return "white" if value < 0.58 else "black"


def save_frequency_drop_heatmap(
    grid: FrequencyDropGrid,
    output_path: Path,
    *,
    title: str = "Caída máxima de frecuencia frente a M y D",
    dpi: int = 300,
) -> Path:
    """Render and save an annotated heatmap for one validated result grid."""
    if dpi <= 0:
        raise ValueError(f"dpi must be > 0, got {dpi}.")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    width = max(7.0, 1.05 * len(grid.d_values) + 3.2)
    height = max(5.2, 0.82 * len(grid.m_values) + 2.5)
    fig, axis = plt.subplots(figsize=(width, height))
    image = axis.imshow(grid.drop_hz, origin="lower", aspect="auto")

    axis.set_xticks(np.arange(len(grid.d_values)))
    axis.set_xticklabels([f"{value:g}" for value in grid.d_values])
    axis.set_yticks(np.arange(len(grid.m_values)))
    axis.set_yticklabels([f"{value:g}" for value in grid.m_values])
    axis.set_xlabel("Amortiguamiento D")
    axis.set_ylabel("Inercia virtual M")
    axis.set_title(title)

    colorbar = fig.colorbar(image, ax=axis)
    colorbar.set_label("Caída máxima de frecuencia [Hz]")

    for row_index in range(grid.drop_hz.shape[0]):
        for column_index in range(grid.drop_hz.shape[1]):
            value = float(grid.drop_hz[row_index, column_index])
            normalized = float(image.norm(value))
            axis.text(
                column_index,
                row_index,
                f"{value:.4f}",
                ha="center",
                va="center",
                color=annotation_text_color(normalized),
                fontsize=9,
            )

    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot maximum frequency drop as a heatmap over M and D."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=(
            "Input CSV. Default: "
            "outputs/validation/gfm_tuning/refinement_iter2_m20-40_d50-100.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "Output PNG. Default: "
            "outputs/validation/gfm_tuning/"
            "frequency_drop_heatmap_refinement_iter2.png"
        ),
    )
    parser.add_argument(
        "--title",
        default="Caída máxima de frecuencia frente a M y D",
        help="Figure title.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Output resolution in dots per inch. Default: 300.",
    )
    return parser.parse_args(list(argv))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    grid = load_frequency_drop_grid(args.input)
    output_path = save_frequency_drop_heatmap(
        grid,
        args.output,
        title=args.title,
        dpi=args.dpi,
    )

    minimum_index = np.unravel_index(np.argmin(grid.drop_hz), grid.drop_hz.shape)
    maximum_index = np.unravel_index(np.argmax(grid.drop_hz), grid.drop_hz.shape)
    print(f"input_csv={Path(args.input)}")
    print(f"grid_shape={grid.drop_hz.shape[0]}x{grid.drop_hz.shape[1]}")
    print(f"frequency_drop_min_hz={grid.drop_hz[minimum_index]:.9f}")
    print(
        "frequency_drop_min_at="
        f"M={grid.m_values[minimum_index[0]]:g},"
        f"D={grid.d_values[minimum_index[1]]:g}"
    )
    print(f"frequency_drop_max_hz={grid.drop_hz[maximum_index]:.9f}")
    print(
        "frequency_drop_max_at="
        f"M={grid.m_values[maximum_index[0]]:g},"
        f"D={grid.d_values[maximum_index[1]]:g}"
    )
    print(f"figure_path={output_path}")
    return 0 if output_path.exists() and output_path.stat().st_size > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
