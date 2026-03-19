"""Shared typed containers for microgrid control/model coupling."""

from dataclasses import dataclass
from numbers import Real

import numpy as np


def _finite_float(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


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

    def __post_init__(self) -> None:
        self.v_inv = np.asarray(self.v_inv, dtype=float)
        if self.v_inv.shape != (3,) or not np.isfinite(self.v_inv).all():
            raise ValueError(
                f"ControlOutput.v_inv must be a finite 3-element vector, got shape {self.v_inv.shape}."
            )
        self.idc_inv = _finite_float("ControlOutput.idc_inv", self.idc_inv)
        self.d_xi_vdc_dt = _finite_float("ControlOutput.d_xi_vdc_dt", self.d_xi_vdc_dt)
        self.d_theta_dt = _finite_float("ControlOutput.d_theta_dt", self.d_theta_dt)
        self.p_bridge = _finite_float("ControlOutput.p_bridge", self.p_bridge)
        self.p_pcc = _finite_float("ControlOutput.p_pcc", self.p_pcc)
        self.p_cmd = _finite_float("ControlOutput.p_cmd", self.p_cmd)
        self.m_ctrl = _finite_float("ControlOutput.m_ctrl", self.m_ctrl)
