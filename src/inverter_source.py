"""Inverter source models for grid-forming and virtual synchronous operation."""

from dataclasses import dataclass
from numbers import Real
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


def required_vdc_for_vln_rms(v_ln_rms: float, m_max: float) -> float:
    """Minimum DC bus voltage required to synthesize target phase RMS voltage."""
    v_ln_rms = _positive_float("v_ln_rms", v_ln_rms)
    m_max = _positive_float("m_max", m_max)
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
    vdc0 = _finite_float("vdc0", vdc0)
    vdc_ref = _finite_float("vdc_ref", vdc_ref)
    v_ln_rms = _positive_float("v_ln_rms", v_ln_rms)
    m_max = _positive_float("m_max", m_max)
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
            raise ValueError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)

    return vdc_min_required


@dataclass
class GridFormingInverter:
    f_hz: float = GRID_FREQ_HZ_DEFAULT
    v_ln_rms: float = GRID_V_LN_RMS_DEFAULT
    theta0: float = GRID_THETA0_RAD_DEFAULT

    def __post_init__(self) -> None:
        self.f_hz = _positive_float("GridFormingInverter.f_hz", self.f_hz)
        self.v_ln_rms = _positive_float("GridFormingInverter.v_ln_rms", self.v_ln_rms)
        self.theta0 = _finite_float("GridFormingInverter.theta0", self.theta0)

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
        theta = _finite_float("theta", theta)
        Vdc = _finite_float("Vdc", Vdc)
        m_max = validate_nonzero_positive_modulation(m_max)
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

    def __post_init__(self) -> None:
        self.f_hz = _positive_float("VirtualSynchronousInverter.f_hz", self.f_hz)
        self.v_ln_rms = _positive_float("VirtualSynchronousInverter.v_ln_rms", self.v_ln_rms)
        self.theta0 = _finite_float("VirtualSynchronousInverter.theta0", self.theta0)
        self.J = _positive_float("VirtualSynchronousInverter.J", self.J)
        self.D = _positive_float("VirtualSynchronousInverter.D", self.D)

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
        theta = _finite_float("theta", theta)
        Vdc = _finite_float("Vdc", Vdc)
        m_max = validate_nonzero_positive_modulation(m_max)
        Vpk_cmd = self.v_pk
        Vpk_avail = m_max * max(Vdc, 0.0) / 2.0
        Vpk = min(Vpk_cmd, Vpk_avail)

        va = Vpk * np.sin(theta)
        vb = Vpk * np.sin(theta - THREE_PHASE_120_DEG_RAD)
        vc = Vpk * np.sin(theta + THREE_PHASE_120_DEG_RAD)
        return np.array([va, vb, vc])

    def calculate_derivatives(self, P_ref, P_elec, omega, theta):
        """Compute VSG swing-equation derivatives: (d_omega_dt, d_theta_dt)."""
        P_ref = _finite_float("P_ref", P_ref)
        P_elec = _finite_float("P_elec", P_elec)
        omega = _finite_float("omega", omega)
        theta = _finite_float("theta", theta)
        d_omega_dt = (P_ref - P_elec - self.D * (omega - self.omega_ref)) / self.J
        d_theta_dt = omega
        return d_omega_dt, d_theta_dt


def validate_nonzero_positive_modulation(m_max: float) -> float:
    """Validate modulation index for internal modulation calls."""
    return _positive_float("m_max", m_max)
