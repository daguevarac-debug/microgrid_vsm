"""Minimal grid-forming frequency dynamics scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Sequence

import numpy as np


def _finite_float(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


@dataclass(frozen=True)
class GridFormingFrequencyDynamics:
    """Minimal GFM angular state model: x_gfm = [theta, omega]."""

    omega_ref: float
    theta0: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "omega_ref",
            _finite_float("GridFormingFrequencyDynamics.omega_ref", self.omega_ref),
        )
        object.__setattr__(
            self,
            "theta0",
            _finite_float("GridFormingFrequencyDynamics.theta0", self.theta0),
        )

    def initial_state(self) -> list[float]:
        """Return the isolated GFM state [theta0, omega_ref]."""
        return [self.theta0, self.omega_ref]

    def theta_derivative(self, theta: float, omega: float) -> float:
        """Evaluate dtheta/dt = omega for the minimal GFM structure."""
        del theta
        return _finite_float("omega", omega)

    def rhs(self, t: float, x: Sequence[float]) -> list[float]:
        """Return [dtheta_dt, domega_dt] with domega_dt held at 0.0 for now."""
        del t
        if len(x) != 2:
            raise ValueError("x must contain [theta, omega].")
        theta = _finite_float("theta", x[0])
        omega = _finite_float("omega", x[1])
        return [self.theta_derivative(theta, omega), 0.0]
