"""External PI regulator for BESS support of the DC link.

Control law:

    e_vdc = vdc_ref - vdc
    p_bess_ref_unsat = kp * e_vdc + ki * xi_vdc
    p_bess_ref = sat(p_bess_ref_unsat, p_min, p_max)

Positive BESS power denotes discharge into the DC link. Conditional-integration
anti-windup freezes the integral when saturation is active and the voltage error
would drive the command farther into the active limit. Integration resumes when
the error acts toward the admissible interval.
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


def _optional_bound(name: str, value: Real | None, default: float) -> float:
    if value is None:
        return default
    return _finite_float(name, value)


@dataclass(frozen=True)
class DCLinkBESSPIOutput:
    """Saturated external-PI output and integral-state derivative."""

    vdc_error_v: float
    p_bess_ref_unsat_w: float
    p_bess_ref_w: float
    p_min_w: float
    p_max_w: float
    saturated: bool
    anti_windup_active: bool
    bess_enabled: bool
    d_xi_vdc_dt: float


class DCLinkBESSPIController:
    """External PI regulator that commands signed BESS DC power.

    ``xi_vdc`` has units V*s and is integrated by the same global solver as the
    plant. Saturation limits are supplied at each evaluation so the plant/BMS
    layer remains the source of truth for SoC-, SoH-, current- and power-based
    availability.
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

    def compute(
        self,
        *,
        vdc_v: float,
        xi_vdc_v_s: float,
        p_min_w: float | None = None,
        p_max_w: float | None = None,
        bess_enabled: bool = True,
    ) -> DCLinkBESSPIOutput:
        """Return the limited power reference and anti-windup derivative.

        ``p_min_w`` is the most negative admissible charging power and
        ``p_max_w`` is the most positive admissible discharging power. Omitting
        both preserves the former unsaturated behavior for isolated unit tests.
        """
        if not isinstance(bess_enabled, bool):
            raise ValueError(
                "DCLinkBESSPIController.bess_enabled must be bool, got "
                f"{bess_enabled!r}."
            )

        vdc = _finite_float("DCLinkBESSPIController.vdc_v", vdc_v)
        xi_vdc = _finite_float(
            "DCLinkBESSPIController.xi_vdc_v_s", xi_vdc_v_s
        )
        p_min = _optional_bound(
            "DCLinkBESSPIController.p_min_w", p_min_w, -np.inf
        )
        p_max = _optional_bound(
            "DCLinkBESSPIController.p_max_w", p_max_w, np.inf
        )
        if p_min > p_max:
            raise ValueError(
                f"p_min_w must be <= p_max_w, got {p_min!r} > {p_max!r}."
            )

        error = self.vdc_ref_v - vdc
        p_unsat = self.kp_w_per_v * error + self.ki_w_per_v_s * xi_vdc

        if not bess_enabled:
            p_min_effective = 0.0
            p_max_effective = 0.0
        else:
            p_min_effective = p_min
            p_max_effective = p_max

        p_limited = float(np.clip(p_unsat, p_min_effective, p_max_effective))
        saturated_high = bool(p_unsat > p_max_effective)
        saturated_low = bool(p_unsat < p_min_effective)
        saturated = saturated_high or saturated_low

        drives_further_high = saturated_high and error > 0.0
        drives_further_low = saturated_low and error < 0.0
        anti_windup_active = bool(
            not bess_enabled or drives_further_high or drives_further_low
        )
        d_xi = 0.0 if anti_windup_active else float(error)

        return DCLinkBESSPIOutput(
            vdc_error_v=float(error),
            p_bess_ref_unsat_w=float(p_unsat),
            p_bess_ref_w=p_limited,
            p_min_w=float(p_min_effective),
            p_max_w=float(p_max_effective),
            saturated=bool(saturated),
            anti_windup_active=anti_windup_active,
            bess_enabled=bess_enabled,
            d_xi_vdc_dt=d_xi,
        )
