"""Baseline grid-following controller for Vdc-regulated operation."""

from __future__ import annotations

from numbers import Real
from typing import TYPE_CHECKING

import numpy as np

from config import (
    GRID_FREQ_HZ_DEFAULT,
    GRID_THETA0_RAD_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.base import ControlOutput, InverterControllerBase
from inverter_source import GridFormingInverter

if TYPE_CHECKING:
    from microgrid import HardwarePlant


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


class GridFollowingController(InverterControllerBase):
    """Baseline PI controller for Vdc with fixed-frequency sinusoidal source."""

    def __init__(
        self,
        f_hz: float = GRID_FREQ_HZ_DEFAULT,
        v_ln_rms: float = GRID_V_LN_RMS_DEFAULT,
        theta0: float = GRID_THETA0_RAD_DEFAULT,
        vdc_ref: float = SIM_VDC0_V_DEFAULT,
        p_ref: float = 0.0,
        kp_vdc: float = 4.0,
        ki_vdc: float = 30.0,
        m_base: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    ):
        f_hz = _positive_float("GridFollowingController.f_hz", f_hz)
        v_ln_rms = _positive_float("GridFollowingController.v_ln_rms", v_ln_rms)
        theta0 = _finite_float("GridFollowingController.theta0", theta0)
        vdc_ref = _positive_float("GridFollowingController.vdc_ref", vdc_ref)
        p_ref = _finite_float("GridFollowingController.p_ref", p_ref)
        kp_vdc = _finite_float("GridFollowingController.kp_vdc", kp_vdc)
        ki_vdc = _finite_float("GridFollowingController.ki_vdc", ki_vdc)
        m_base = _positive_float("GridFollowingController.m_base", m_base)
        self.modulator = GridFormingInverter(f_hz=f_hz, v_ln_rms=v_ln_rms, theta0=theta0)
        self.vdc_ref = vdc_ref
        self.p_ref = p_ref
        self.kp_vdc = kp_vdc
        self.ki_vdc = ki_vdc
        self.m_base = m_base

    @property
    def omega_ref(self) -> float:
        """Fixed angular frequency in baseline mode."""
        return self.modulator.omega

    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
    ) -> ControlOutput:
        del t
        vdc_error = vdc_eff - self.vdc_ref
        p_unsat = self.p_ref + self.kp_vdc * vdc_error + self.ki_vdc * xi_vdc
        p_available = max(vdc_eff * ipv * plant.eta, 0.0)
        p_cmd = float(np.clip(p_unsat, 0.0, p_available))

        if (p_unsat > p_available and vdc_error > 0.0) or (p_unsat < 0.0 and vdc_error < 0.0):
            xi_dot = 0.0
        else:
            xi_dot = vdc_error

        d_theta_dt = self.omega_ref
        pref_scale = max(min(self.p_ref, p_available), 1.0)
        m_ctrl = self.m_base * float(np.clip(p_cmd / pref_scale, 0.0, 1.0))

        if vdc_eff < plant.v_uvlo:
            v_inv = np.zeros(3)
            p_bridge = 0.0
            p_pcc = 0.0
            idc_inv = 0.0
        else:
            v_inv = self.modulator.modulate(theta, vdc_eff, m_max=m_ctrl)
            p_bridge = float(np.dot(v_inv, i1))
            p_pcc = float(np.dot(v_pcc, i2))
            p_dc = max(p_bridge, 0.0) / plant.eta
            idc_inv = p_dc / max(vdc_eff, plant.dcp.Vmin)

        return ControlOutput(
            v_inv=v_inv,
            idc_inv=idc_inv,
            d_xi_vdc_dt=xi_dot,
            d_theta_dt=d_theta_dt,
            p_bridge=p_bridge,
            p_pcc=p_pcc,
            p_cmd=p_cmd,
            m_ctrl=m_ctrl,
        )
