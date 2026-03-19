"""DC-link parameter container and load current helper functions."""

from dataclasses import dataclass
from numbers import Real

import numpy as np

from config import DCLINK_VMIN_DEFAULT


def _finite_float(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _positive_float(name: str, value) -> float:
    out = _finite_float(name, value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


@dataclass
class DCLinkParams:
    Cdc: float
    Vmin: float = DCLINK_VMIN_DEFAULT

    def __post_init__(self) -> None:
        self.Cdc = _positive_float("DCLinkParams.Cdc", self.Cdc)
        self.Vmin = _positive_float("DCLinkParams.Vmin", self.Vmin)


def i_load_const_power(Vdc: float, P: float, Vmin: float = DCLINK_VMIN_DEFAULT) -> float:
    """Constant-power DC load: I = P / V."""
    Vdc = _finite_float("Vdc", Vdc)
    P = _finite_float("P", P)
    Vmin = _positive_float("Vmin", Vmin)
    Veff = max(Vdc, Vmin)
    return P / Veff


def i_load_resistor(Vdc: float, R: float) -> float:
    """Resistive DC load: I = V / R."""
    Vdc = _finite_float("Vdc", Vdc)
    R = _positive_float("R", R)
    return Vdc / R
