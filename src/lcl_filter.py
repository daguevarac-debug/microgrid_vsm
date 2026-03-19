"""Three-phase LCL filter state-space derivative model."""

from dataclasses import dataclass

import numpy as np

from config import (
    LCL_CF_F_DEFAULT,
    LCL_L1_H_DEFAULT,
    LCL_L2_H_DEFAULT,
    LCL_R1_OHM_DEFAULT,
    LCL_R2_OHM_DEFAULT,
    LCL_RD_OHM_DEFAULT,
)


@dataclass
class LCLFilter:
    L1: float = LCL_L1_H_DEFAULT
    R1: float = LCL_R1_OHM_DEFAULT
    Cf: float = LCL_CF_F_DEFAULT
    Rd: float = LCL_RD_OHM_DEFAULT
    L2: float = LCL_L2_H_DEFAULT
    R2: float = LCL_R2_OHM_DEFAULT

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
