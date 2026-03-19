"""Three-phase LCL filter state-space derivative model."""

from dataclasses import dataclass
from numbers import Real

import numpy as np

from config import (
    LCL_CF_F_DEFAULT,
    LCL_L1_H_DEFAULT,
    LCL_L2_H_DEFAULT,
    LCL_R1_OHM_DEFAULT,
    LCL_R2_OHM_DEFAULT,
    LCL_RD_OHM_DEFAULT,
)


def _positive_float(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a positive real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


@dataclass
class LCLFilter:
    L1: float = LCL_L1_H_DEFAULT
    R1: float = LCL_R1_OHM_DEFAULT
    Cf: float = LCL_CF_F_DEFAULT
    Rd: float = LCL_RD_OHM_DEFAULT
    L2: float = LCL_L2_H_DEFAULT
    R2: float = LCL_R2_OHM_DEFAULT

    def __post_init__(self) -> None:
        self.L1 = _positive_float("LCLFilter.L1", self.L1)
        self.R1 = _positive_float("LCLFilter.R1", self.R1)
        self.Cf = _positive_float("LCLFilter.Cf", self.Cf)
        self.Rd = _positive_float("LCLFilter.Rd", self.Rd)
        self.L2 = _positive_float("LCLFilter.L2", self.L2)
        self.R2 = _positive_float("LCLFilter.R2", self.R2)

    def calculate_derivatives(self, v_inv, v_pcc, i1, vc, i2):
        v_inv = np.asarray(v_inv, dtype=float)
        v_pcc = np.asarray(v_pcc, dtype=float)
        i1 = np.asarray(i1, dtype=float)
        vc = np.asarray(vc, dtype=float)
        i2 = np.asarray(i2, dtype=float)

        di1dt = (v_inv - vc - self.R1 * i1) / self.L1
        dvcdt = (i1 - i2 - vc / self.Rd) / self.Cf
        di2dt = (vc - v_pcc - self.R2 * i2) / self.L2

        return di1dt, dvcdt, di2dt
