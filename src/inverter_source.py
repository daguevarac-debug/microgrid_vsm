"""Inverter source models for grid-forming and virtual synchronous operation."""

from dataclasses import dataclass
import warnings

import numpy as np

from config import (
    GRID_FREQ_HZ_DEFAULT,
    GRID_THETA0_RAD_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    THREE_PHASE_120_DEG_RAD,
    VSG_DAMPING_D_DEFAULT,
    VSG_INERTIA_J_DEFAULT,
)


def required_vdc_for_vln_rms(v_ln_rms: float, m_max: float) -> float:
    """Minimum DC bus voltage required to synthesize target phase RMS voltage."""
    if m_max <= 0.0:
        raise ValueError("m_max must be > 0 to compute required Vdc.")
    return 2.0 * np.sqrt(2.0) * v_ln_rms / m_max


def validate_dc_bus_capability(
    vdc0: float,
    vdc_ref: float,
    v_ln_rms: float = GRID_V_LN_RMS_DEFAULT,
    m_max: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    strict: bool = False,
    context: str = "inverter",
) -> float:
    """
    Validate if Vdc0 and Vdc_ref can synthesize target Vln,rms at modulation limit.

    Returns:
        Minimum required Vdc [V].
    """
    vdc_min_required = required_vdc_for_vln_rms(v_ln_rms=v_ln_rms, m_max=m_max)
    check_vdc0 = vdc0 >= vdc_min_required
    check_vdc_ref = vdc_ref >= vdc_min_required

    if not (check_vdc0 and check_vdc_ref):
        msg = (
            f"[{context}] DC bus nominal inconsistency: required Vdc >= {vdc_min_required:.2f} V "
            f"for Vln,rms={v_ln_rms:.2f} V and m_max={m_max:.3f}. "
            f"Current values: Vdc0={vdc0:.2f} V, Vdc_ref={vdc_ref:.2f} V."
        )
        if strict:
            raise AssertionError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)

    return vdc_min_required


@dataclass
class GridFormingInverter:
    f_hz: float = GRID_FREQ_HZ_DEFAULT
    v_ln_rms: float = GRID_V_LN_RMS_DEFAULT
    theta0: float = GRID_THETA0_RAD_DEFAULT

    @property
    def omega(self):
        return 2.0 * np.pi * self.f_hz

    @property
    def v_pk(self):
        return np.sqrt(2.0) * self.v_ln_rms

    def modulate(
        self,
        theta: float,
        Vdc: float,
        m_max: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    ):
        """Generate limited three-phase inverter voltage references."""
        Vpk_cmd = self.v_pk
        Vpk_avail = m_max * max(Vdc, 0.0) / 2.0
        Vpk = min(Vpk_cmd, Vpk_avail)

        va = Vpk * np.sin(theta)
        vb = Vpk * np.sin(theta - THREE_PHASE_120_DEG_RAD)
        vc = Vpk * np.sin(theta + THREE_PHASE_120_DEG_RAD)
        return np.array([va, vb, vc])


@dataclass
class VirtualSynchronousInverter:
    """Virtual synchronous inverter with swing-equation state derivatives."""

    f_hz: float = GRID_FREQ_HZ_DEFAULT
    v_ln_rms: float = GRID_V_LN_RMS_DEFAULT
    theta0: float = GRID_THETA0_RAD_DEFAULT
    J: float = VSG_INERTIA_J_DEFAULT
    D: float = VSG_DAMPING_D_DEFAULT

    @property
    def omega_ref(self):
        return 2.0 * np.pi * self.f_hz

    @property
    def omega(self):
        return self.omega_ref

    @property
    def v_pk(self):
        return np.sqrt(2.0) * self.v_ln_rms

    def modulate(
        self,
        theta: float,
        Vdc: float,
        m_max: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    ):
        """Generate limited three-phase inverter voltage references."""
        Vpk_cmd = self.v_pk
        Vpk_avail = m_max * max(Vdc, 0.0) / 2.0
        Vpk = min(Vpk_cmd, Vpk_avail)

        va = Vpk * np.sin(theta)
        vb = Vpk * np.sin(theta - THREE_PHASE_120_DEG_RAD)
        vc = Vpk * np.sin(theta + THREE_PHASE_120_DEG_RAD)
        return np.array([va, vb, vc])

    def calculate_derivatives(self, P_ref, P_elec, omega, theta):
        """Compute VSG swing-equation derivatives: (d_omega_dt, d_theta_dt)."""
        d_omega_dt = (P_ref - P_elec - self.D * (omega - self.omega_ref)) / self.J
        d_theta_dt = omega
        return d_omega_dt, d_theta_dt
