"""Run bounded GFM parameter-refinement sweeps.

Each refinement iteration is limited to at most three unique ``M`` values and
three unique ``D`` values, for a maximum of nine simulations. Additional
resolution is obtained by narrowing a promising interval and evaluating its
lower bound, midpoint and upper bound.

Examples:
    # Default 3x3 refinement grid.
    python src/validation/refine_gfm_parameters.py --dry-run

    # Explicit values, at most three per parameter.
    python src/validation/refine_gfm_parameters.py \
        --m-values 10 20 40 --d-values 50 100 200

    # Bisection triplets generated from promising ranges.
    python src/validation/refine_gfm_parameters.py \
        --m-range 10 25 --d-range 50 125 --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.tune_gfm_parameters import (
    TUNING_T_END_S_DEFAULT,
    build_parameter_grid,
    run_parameter_sweep,
)


MAX_VALUES_PER_PARAMETER = 3
M_REFINEMENT_DEFAULT = (10.0, 20.0, 40.0)
D_REFINEMENT_DEFAULT = (50.0, 100.0, 200.0)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "gfm_tuning"
    / "refinement_runs.csv"
)


def _limited_values(
    name: str,
    values: Iterable[float],
    *,
    strictly_positive: bool,
) -> tuple[float, ...]:
    """Validate one refinement axis and enforce the three-value limit."""
    validated: list[float] = []
    for raw_value in values:
        value = float(raw_value)
        if not np.isfinite(value):
            raise ValueError(f"{name} values must be finite, got {raw_value!r}.")
        if strictly_positive and value <= 0.0:
            raise ValueError(f"{name} values must be > 0, got {value}.")
        if not strictly_positive and value < 0.0:
            raise ValueError(f"{name} values must be >= 0, got {value}.")
        if value not in validated:
            validated.append(value)

    if not validated:
        raise ValueError(f"At least one {name} value is required.")
    if len(validated) > MAX_VALUES_PER_PARAMETER:
        raise ValueError(
            f"Refinement accepts at most {MAX_VALUES_PER_PARAMETER} unique {name} "
            f"values per iteration, got {len(validated)}: {validated}."
        )
    return tuple(validated)


def bisection_triplet(
    name: str,
    lower: float,
    upper: float,
    *,
    strictly_positive: bool,
) -> tuple[float, float, float]:
    """Return ``(lower, midpoint, upper)`` for one valid promising interval."""
    lower_value = float(lower)
    upper_value = float(upper)
    if not np.isfinite(lower_value) or not np.isfinite(upper_value):
        raise ValueError(f"{name} range bounds must be finite.")
    if upper_value <= lower_value:
        raise ValueError(
            f"{name} range upper bound must be greater than lower bound, "
            f"got [{lower_value}, {upper_value}]."
        )

    values = (
        lower_value,
        0.5 * (lower_value + upper_value),
        upper_value,
    )
    return _limited_values(
        name,
        values,
        strictly_positive=strictly_positive,
    )  # type: ignore[return-value]


def resolve_refinement_values(
    *,
    m_values: Iterable[float] | None = None,
    d_values: Iterable[float] | None = None,
    m_range: tuple[float, float] | None = None,
    d_range: tuple[float, float] | None = None,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Resolve explicit values or bisection ranges for both parameters."""
    if m_values is not None and m_range is not None:
        raise ValueError("Provide either m_values or m_range, not both.")
    if d_values is not None and d_range is not None:
        raise ValueError("Provide either d_values or d_range, not both.")

    if m_range is not None:
        resolved_m = bisection_triplet(
            "M",
            m_range[0],
            m_range[1],
            strictly_positive=True,
        )
    else:
        resolved_m = _limited_values(
            "M",
            M_REFINEMENT_DEFAULT if m_values is None else m_values,
            strictly_positive=True,
        )

    if d_range is not None:
        resolved_d = bisection_triplet(
            "D",
            d_range[0],
            d_range[1],
            strictly_positive=False,
        )
    else:
        resolved_d = _limited_values(
            "D",
            D_REFINEMENT_DEFAULT if d_values is None else d_values,
            strictly_positive=False,
        )

    return resolved_m, resolved_d


def build_refinement_grid(
    *,
    m_values: Iterable[float] | None = None,
    d_values: Iterable[float] | None = None,
    m_range: tuple[float, float] | None = None,
    d_range: tuple[float, float] | None = None,
) -> tuple[tuple[float, float], ...]:
    """Build a deterministic refinement grid containing at most nine pairs."""
    resolved_m, resolved_d = resolve_refinement_values(
        m_values=m_values,
        d_values=d_values,
        m_range=m_range,
        d_range=d_range,
    )
    grid = build_parameter_grid(resolved_m, resolved_d)
    if len(grid) > MAX_VALUES_PER_PARAMETER**2:
        raise RuntimeError(
            "Internal refinement-grid limit violation: "
            f"expected at most 9 candidates, got {len(grid)}."
        )
    return grid


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a GFM refinement sweep limited to at most three M values and "
            "three D values."
        )
    )

    m_group = parser.add_mutually_exclusive_group()
    m_group.add_argument(
        "--m-values",
        nargs="+",
        type=float,
        help="Explicit M values, maximum three unique values.",
    )
    m_group.add_argument(
        "--m-range",
        nargs=2,
        type=float,
        metavar=("LOWER", "UPPER"),
        help="Generate M=[lower, midpoint, upper] for bisection refinement.",
    )

    d_group = parser.add_mutually_exclusive_group()
    d_group.add_argument(
        "--d-values",
        nargs="+",
        type=float,
        help="Explicit D values, maximum three unique values.",
    )
    d_group.add_argument(
        "--d-range",
        nargs=2,
        type=float,
        metavar=("LOWER", "UPPER"),
        help="Generate D=[lower, midpoint, upper] for bisection refinement.",
    )

    parser.add_argument(
        "--t-end",
        type=float,
        default=TUNING_T_END_S_DEFAULT,
        help="Final simulation time in seconds. Default: 6.5.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "CSV output path. Default: "
            "outputs/validation/gfm_tuning/refinement_runs.csv"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the bounded grid without solving the model.",
    )
    return parser.parse_args(argv)


def _print_grid(
    m_values: tuple[float, ...],
    d_values: tuple[float, ...],
) -> None:
    grid = build_parameter_grid(m_values, d_values)
    print(f"max_values_per_parameter={MAX_VALUES_PER_PARAMETER}")
    print(f"m_values={' '.join(f'{value:g}' for value in m_values)}")
    print(f"d_values={' '.join(f'{value:g}' for value in d_values)}")
    print(f"grid_size={len(grid)}")
    for run_index, (inertia_m, damping_d) in enumerate(grid, start=1):
        print(f"run={run_index} | M={inertia_m:g} | D={damping_d:g}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    m_range = None if args.m_range is None else tuple(args.m_range)
    d_range = None if args.d_range is None else tuple(args.d_range)
    m_values, d_values = resolve_refinement_values(
        m_values=args.m_values,
        d_values=args.d_values,
        m_range=m_range,
        d_range=d_range,
    )

    if args.dry_run:
        _print_grid(m_values, d_values)
        print("dry_run=True")
        print("simulations_executed=0")
        return 0

    records, csv_path = run_parameter_sweep(
        m_values=m_values,
        d_values=d_values,
        t_end_s=args.t_end,
        output_path=args.output,
    )
    n_ok = sum(record["status"] == "ok" for record in records)
    n_admissible = sum(bool(record["candidate_admissible"]) for record in records)

    print("\n=== bounded GFM refinement summary ===")
    print(f"runs_total={len(records)}")
    print(f"runs_ok={n_ok}")
    print(f"runs_invalid={len(records) - n_ok}")
    print(f"candidates_admissible={n_admissible}")
    print(f"csv_path={csv_path}")
    return 0 if records and csv_path.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
