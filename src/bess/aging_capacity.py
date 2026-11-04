"""Immutable effective-capacity snapshot for slow aging / fast 1RC coupling.

This module DOES NOT implement BLAST-Lite or replace the linear baseline.
Its only responsibility is to distinguish second-life initial capacity from
nominal-new reference capacity without double counting initial degradation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True)
class CapacitySnapshot:
    """Frozen capacity boundary for one fast simulation interval.

    q_nom_ref_ah: reference 66 Ah for one Nissan Leaf 2p unit (not DC bus).
    q_init_case_ah: capacity at the beginning of the thesis case, e.g. 44.1 Ah.
    retention_since_case_start: dimensionless fractional retention [0,1],
        initialized at 1.0; this is NOT the BLAST original 0.7 multiplier.
    """

    q_nom_ref_ah: float
    q_init_case_ah: float
    retention_since_case_start: float
    q_eff_ah: float = field(init=False)
    soh: float = field(init=False)

    def __post_init__(self) -> None:
        values = {
            "q_nom_ref_ah": self.q_nom_ref_ah,
            "q_init_case_ah": self.q_init_case_ah,
            "retention_since_case_start": self.retention_since_case_start,
        }
        for name, raw in values.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{name} must be a finite real number")
            if not isfinite(raw):
                raise ValueError(f"{name} must be finite")

        if self.q_nom_ref_ah <= 0:
            raise ValueError("q_nom_ref_ah must be positive")
        if not (0 < self.q_init_case_ah <= self.q_nom_ref_ah):
            raise ValueError("q_init_case_ah must be in (0, q_nom_ref_ah]")
        if not (0 < self.retention_since_case_start <= 1):
            raise ValueError("retention_since_case_start must be in (0, 1]")

        q_eff = float(self.q_init_case_ah * self.retention_since_case_start)
        object.__setattr__(self, "q_eff_ah", q_eff)
        object.__setattr__(self, "soh", q_eff / float(self.q_nom_ref_ah))
