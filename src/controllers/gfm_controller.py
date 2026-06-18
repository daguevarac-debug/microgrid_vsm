"""Classical GFM/VSG controller compatible with the baseline controller contract."""

from __future__ import annotations

from numbers import Real
from typing import TYPE_CHECKING

import numpy as np

from config import (
    GRID_FREQ_HZ_DEFAULT,
    GRID_THETA0_RAD_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
)
from controllers.base import ControlOutput, InverterControllerBase
from controllers.grid_forming import GridFormingFrequencyDynamics
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


def _nonnegative_float(name: str, value) -> float:
    out = _finite_float(name, value)
    if out < 0.0:
        raise ValueError(f"{name} must be >= 0, got {value!r}.")
    return out


def _phase_vector(name: str, value) -> np.ndarray:
    out = np.asarray(value, dtype=float)
    if out.shape != (3,) or not np.isfinite(out).all():
        raise ValueError(f"{name} must be a finite 3-element vector, got shape {out.shape}.")
    return out


def _validate_bess_supervision_inputs(
    soc_bess: float | None,
    soh_bess: float | None,
    i_bess_max_available: float | None,
    p_bess_dc_max_available: float | None,
) -> None:
    """Validate the optional BESS/BMS interface without applying limits yet."""
    values = {
        "soc_bess": soc_bess,
        "soh_bess": soh_bess,
        "i_bess_max_available": i_bess_max_available,
        "p_bess_dc_max_available": p_bess_dc_max_available,
    }
    if all(value is None for value in values.values()):
        return

    missing = [name for name, value in values.items() if value is None]
    if missing:
        raise ValueError(
            "BESS supervision inputs must be provided together; missing: "
            + ", ".join(missing)
            + "."
        )

    soc = _finite_float("GFMController.soc_bess", soc_bess)
    soh = _finite_float("GFMController.soh_bess", soh_bess)
    if not 0.0 <= soc <= 1.0:
        raise ValueError(f"GFMController.soc_bess must be within [0, 1], got {soc}.")
    if not 0.0 <= soh <= 1.0:
        raise ValueError(f"GFMController.soh_bess must be within [0, 1], got {soh}.")
    _nonnegative_float("GFMController.i_bess_max_available", i_bess_max_available)
    _nonnegative_float("GFMController.p_bess_dc_max_available", p_bess_dc_max_available)


class GFMController(InverterControllerBase):
    """Minimum classical GFM controller using reduced swing dynamics.

    The method signature intentionally matches ``GridFollowingController`` so
    the controller can be introduced without changing the current plant-control
    call boundary. Under the protected GFM state mapping, ``xi_vdc`` in the
    compatibility signature carries ``omega = x[10]`` and the returned
    ``d_xi_vdc_dt`` carries ``domega/dt``.

    The supplied ``v_pcc`` must be the complete R-L PCC voltage when the class
    is fully integrated. The legacy resistive approximation is not sufficient
    for the final GFM active-power feedback.

    The optional BESS supervision values are transported through this interface
    for Activity 2.2. This subtask validates their contract but deliberately does
    not yet use them to modify ``p_ref_eff``.
    """

    controller_state_name = "omega"

    def __init__(
        self,
        f_hz: float = GRID_FREQ_HZ_DEFAULT,
        v_ln_rms: float = GRID_V_LN_RMS_DEFAULT,
        theta0: float = GRID_THETA0_RAD_DEFAULT,
        p_ref: float = 0.0,
        inertia_m: float = 1.0,
        damping_d: float = 0.0,
        m_base: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    ):
        f_hz = _positive_float("GFMController.f_hz", f_hz)
        v_ln_rms = _positive_float("GFMController.v_ln_rms", v_ln_rms)
        theta0 = _finite_float("GFMController.theta0", theta0)
        p_ref = _nonnegative_float("GFMController.p_ref", p_ref)
        inertia_m = _positive_float("GFMController.inertia_m", inertia_m)
        damping_d = _nonnegative_float("GFMController.damping_d", damping_d)
        m_base = _positive_float("GFMController.m_base", m_base)

        self.modulator = GridFormingInverter(
            f_hz=f_hz,
            v_ln_rms=v_ln_rms,
            theta0=theta0,
        )
        self.frequency_dynamics = GridFormingFrequencyDynamics(
            omega_ref=self.modulator.omega,
            theta0=theta0,
            p_ref=p_ref,
            inertia_m=inertia_m,
            damping_d=damping_d,
        )
        self.p_ref = p_ref
        self.m_base = m_base

    @property
    def omega_ref(self) -> float:
        """Nominal angular frequency used by the reduced swing equation."""
        return self.frequency_dynamics.omega_ref

    def initial_controller_state(self) -> float:
        """Return omega_ref for the protected GFM state x[10]."""
        return self.omega_ref

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
        *,
        soc_bess: float | None = None,
        soh_bess: float | None = None,
        i_bess_max_available: float | None = None,
        p_bess_dc_max_available: float | None = None,
    ) -> ControlOutput:
        """Return GFM voltage synthesis, power exchange and angular derivatives."""
        t = _finite_float("GFMController.t", t)
        theta = _finite_float("GFMController.theta", theta)
        # Compatibility mapping: in GFM mode x[10] is omega, not xi_vdc.
        omega = _finite_float("GFMController.omega", xi_vdc)
        vdc_eff = _nonnegative_float("GFMController.vdc_eff", vdc_eff)
        ipv = _finite_float("GFMController.ipv", ipv)
        v_pcc = _phase_vector("GFMController.v_pcc", v_pcc)
        i1 = _phase_vector("GFMController.i1", i1)
        i2 = _phase_vector("GFMController.i2", i2)
        _validate_bess_supervision_inputs(
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
        )

        p_available = max(vdc_eff * ipv * plant.eta, 0.0)
        p_ref_eff = float(np.clip(self.p_ref, 0.0, p_available))
        p_e = float(np.dot(v_pcc, i2))

        d_theta_dt, d_omega_dt = self.frequency_dynamics.rhs(
            t=t,
            x=[theta, omega],
            p_e=p_e,
            p_ref=p_ref_eff,
        )

        if vdc_eff < plant.v_uvlo:
            v_inv = np.zeros(3)
            p_bridge = 0.0
            idc_inv = 0.0
            m_ctrl = 0.0
        else:
            m_required = 2.0 * self.modulator.v_pk / vdc_eff
            m_ctrl = min(self.m_base, m_required)
            v_inv = self.modulator.modulate(theta, vdc_eff, m_max=m_ctrl)
            p_bridge = float(np.dot(v_inv, i1))
            # Preserve the baseline unidirectional DC-link convention: the
            # inverter absorbs nonnegative current from the DC bus toward AC.
            p_dc = max(p_bridge, 0.0) / plant.eta
            idc_inv = p_dc / max(vdc_eff, plant.dcp.Vmin)

        return ControlOutput(
            v_inv=v_inv,
            idc_inv=idc_inv,
            d_xi_vdc_dt=d_omega_dt,
            d_theta_dt=d_theta_dt,
            p_bridge=p_bridge,
            p_pcc=p_e,
            p_cmd=p_ref_eff,
            m_ctrl=m_ctrl,
        )
