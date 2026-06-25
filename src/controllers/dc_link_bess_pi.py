"""External PI regulator for BESS support of the DC link.

This module implements only the unsaturated PI law requested in Task 5.2:

    e_vdc = vdc_ref - vdc
    p_bess_ref = kp * e_vdc + ki * xi_vdc
    d(xi_vdc)/dt = e_vdc

Positive power reference denotes BESS discharge into the DC link. Saturation,
anti-windup, BESS enable logic and plant integration are intentionally deferred
to later Task 5.2 subtasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import numpy as np


def _finite_float(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _positive_float(name: str, value: Real) -> float:
    out = _finite_float(name, value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


def _nonnegative_float(name: str, value: Real) -> float:
    out = _finite_float(name, value)
    if out < 0.0:
        raise ValueError(f"{name} must be >= 0, got {value!r}.")
    return out


@dataclass(frozen=True)
class DCLinkBESSPIOutput:
    """Unsaturated external-PI output and integral-state derivative."""

    vdc_error_v: float
    p_bess_ref_unsat_w: float
    d_xi_vdc_dt: float


class DCLinkBESSPIController:
    """Minimal external PI regulator that commands BESS DC power.

    Parameters
    ----------
    vdc_ref_v:
        DC-link voltage reference [V].
    kp_w_per_v:
        Proportional gain [W/V].
    ki_w_per_v_s:
        Integral gain [W/(V*s)].

    Notes
    -----
    The integral state ``xi_vdc`` has units V*s and must later be integrated by
    the same global solver as the plant. This isolated block does not alter the
    current protected GFM+BESS state mapping.
    """

    def __init__(
        self,
        *,
        vdc_ref_v: float,
        kp_w_per_v: float,
        ki_w_per_v_s: float,
    ) -> None:
        self.vdc_ref_v = _positive_float(
            "DCLinkBESSPIController.vdc_ref_v", vdc_ref_v
        )
        self.kp_w_per_v = _nonnegative_float(
            "DCLinkBESSPIController.kp_w_per_v", kp_w_per_v
        )
        self.ki_w_per_v_s = _nonnegative_float(
            "DCLinkBESSPIController.ki_w_per_v_s", ki_w_per_v_s
        )

    def compute(self, *, vdc_v: float, xi_vdc_v_s: float) -> DCLinkBESSPIOutput:
        """Return the unsaturated BESS power reference and integrator derivative."""
        vdc = _finite_float("DCLinkBESSPIController.vdc_v", vdc_v)
        xi_vdc = _finite_float(
            "DCLinkBESSPIController.xi_vdc_v_s", xi_vdc_v_s
        )
        error = self.vdc_ref_v - vdc
        p_bess_ref = (
            self.kp_w_per_v * error
            + self.ki_w_per_v_s * xi_vdc
        )
        return DCLinkBESSPIOutput(
            vdc_error_v=float(error),
            p_bess_ref_unsat_w=float(p_bess_ref),
            d_xi_vdc_dt=float(error),
        )
