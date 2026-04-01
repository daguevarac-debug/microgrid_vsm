"""Input validation helpers for BESS model parameters."""

from __future__ import annotations

from numbers import Real
from typing import Sequence

import numpy as np


def _ensure_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _ensure_positive(name: str, value: float) -> float:
    out = _ensure_finite(name, value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


def _ensure_fraction(name: str, value: float) -> float:
    out = _ensure_finite(name, value)
    if out < 0.0 or out > 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value!r}.")
    return out


def _ensure_real_array(name: str, data: Sequence[float]) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D sequence, got shape {arr.shape}.")
    if arr.size < 2:
        raise ValueError(f"{name} must contain at least 2 points, got {arr.size}.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values.")
    return arr
