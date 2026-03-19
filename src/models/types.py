"""Shared typed containers for microgrid control/model coupling."""

from dataclasses import dataclass

import numpy as np


@dataclass
class ControlOutput:
    """Controller outputs required by baseline plant integration."""

    v_inv: np.ndarray
    idc_inv: float
    d_xi_vdc_dt: float
    d_theta_dt: float
    p_bridge: float
    p_pcc: float
    p_cmd: float
    m_ctrl: float

