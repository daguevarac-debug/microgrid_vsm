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
    p_ref: float = 0.0
    inertia_m: float = 1.0
    damping_d: float = 0.0

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
        object.__setattr__(
            self,
            "p_ref",
            _finite_float("GridFormingFrequencyDynamics.p_ref", self.p_ref),
        )
        inertia_m = _finite_float("GridFormingFrequencyDynamics.inertia_m", self.inertia_m)
        if inertia_m <= 0.0:
            raise ValueError(
                f"GridFormingFrequencyDynamics.inertia_m must be > 0, got {self.inertia_m!r}."
            )
        object.__setattr__(self, "inertia_m", inertia_m)

        damping_d = _finite_float("GridFormingFrequencyDynamics.damping_d", self.damping_d)
        if damping_d < 0.0:
            raise ValueError(
                f"GridFormingFrequencyDynamics.damping_d must be >= 0, got {self.damping_d!r}."
            )
        object.__setattr__(self, "damping_d", damping_d)

    def initial_state(self) -> list[float]:
        """Return the isolated GFM state [theta0, omega_ref]."""
        return [self.theta0, self.omega_ref]

    def theta_derivative(self, theta: float, omega: float) -> float:
        """Evaluate dtheta/dt = omega for the minimal GFM structure."""
        del theta
        return _finite_float("omega", omega)

    def omega_derivative(self, omega: float, p_e: float, p_ref: float | None = None) -> float:
        """Evaluate the reduced VSG/swing frequency derivative."""
        omega = _finite_float("omega", omega)
        p_e = _finite_float("p_e", p_e)
        p_ref_eval = self.p_ref if p_ref is None else _finite_float("p_ref", p_ref)
        return (
            p_ref_eval
            - p_e
            - self.damping_d * (omega - self.omega_ref)
        ) / self.inertia_m

    def rhs(
        self,
        t: float,
        x: Sequence[float],
        p_e: float | None = None,
        p_ref: float | None = None,
    ) -> list[float]:
        """Return [dtheta_dt, domega_dt] for the isolated reduced swing model."""
        del t
        if len(x) != 2:
            raise ValueError("x must contain [theta, omega].")
        theta = _finite_float("theta", x[0])
        omega = _finite_float("omega", x[1])
        p_ref_eval = self.p_ref if p_ref is None else _finite_float("p_ref", p_ref)
        p_e_eval = p_ref_eval if p_e is None else _finite_float("p_e", p_e)
        return [
            self.theta_derivative(theta, omega),
            self.omega_derivative(omega=omega, p_e=p_e_eval, p_ref=p_ref_eval),
        ]
