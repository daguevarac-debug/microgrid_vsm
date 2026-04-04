"""Inverter source models for grid-forming and virtual synchronous operation."""

from dataclasses import dataclass
from numbers import Real
import warnings

import numpy as np

from config import (
    FOVIC_DAMPING_D_DEFAULT,
    FOVIC_FREQ_HZ_DEFAULT,
    FOVIC_INERTIA_H_DEFAULT,
    FOVIC_K_DC_DEFAULT,
    FOVIC_K_H_DEFAULT,
    FOVIC_MODULATION_INDEX_MAX_DEFAULT,
    FOVIC_MU_DEFAULT,
    FOVIC_OUSTALOUP_ORDER_N_DEFAULT,
    FOVIC_OMEGA_H_RAD_S_DEFAULT,
    FOVIC_OMEGA_L_RAD_S_DEFAULT,
    FOVIC_SWING_TWO_FACTOR_DEFAULT,
    FOVIC_T_BESS_S_DEFAULT,
    FOVIC_T_DC_S_DEFAULT,
    FOVIC_THETA0_RAD_DEFAULT,
    FOVIC_V_LN_RMS_DEFAULT,
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


@dataclass
class FOVICInverter:
    """Fractional-order VIC inverter with Oustaloup fractional approximation.

    References:
    - Nour (2023), Sec. 3.2, Eq. (23):
      delta_P_ESS = delta_f * (K_DC/(1 + s*T_DC) + K_H*s^mu) * 1/(1 + s*T_BESS)
    - Yu et al., IEEE TPEL (2023), Sec. III-B1, Eq. (7)-(8):
      Oustaloup approximation of s^mu.
    - Nour (2023), Sec. 3.2, Eq. (18):
      delta_P_M - delta_P_L + delta_P_ESS = (2H*s + D) * delta_f
    """

    f_hz: float = FOVIC_FREQ_HZ_DEFAULT
    v_ln_rms: float = FOVIC_V_LN_RMS_DEFAULT
    theta0: float = FOVIC_THETA0_RAD_DEFAULT
    H: float = FOVIC_INERTIA_H_DEFAULT
    D: float = FOVIC_DAMPING_D_DEFAULT
    K_DC: float = FOVIC_K_DC_DEFAULT
    T_DC: float = FOVIC_T_DC_S_DEFAULT
    T_BESS: float = FOVIC_T_BESS_S_DEFAULT
    K_H: float = FOVIC_K_H_DEFAULT
    mu: float = FOVIC_MU_DEFAULT
    oustaloup_order: int = FOVIC_OUSTALOUP_ORDER_N_DEFAULT
    omega_l: float = FOVIC_OMEGA_L_RAD_S_DEFAULT
    omega_h: float = FOVIC_OMEGA_H_RAD_S_DEFAULT
    swing_two_factor: float = FOVIC_SWING_TWO_FACTOR_DEFAULT

    def __post_init__(self) -> None:
        self.f_hz = _positive_float("FOVICInverter.f_hz", self.f_hz)
        self.v_ln_rms = _positive_float("FOVICInverter.v_ln_rms", self.v_ln_rms)
        self.theta0 = _finite_float("FOVICInverter.theta0", self.theta0)
        self.H = _positive_float("FOVICInverter.H", self.H)
        self.D = _positive_float("FOVICInverter.D", self.D)
        self.K_DC = _finite_float("FOVICInverter.K_DC", self.K_DC)
        self.T_DC = _positive_float("FOVICInverter.T_DC", self.T_DC)
        self.T_BESS = _positive_float("FOVICInverter.T_BESS", self.T_BESS)
        self.K_H = _finite_float("FOVICInverter.K_H", self.K_H)
        self.mu = _finite_float("FOVICInverter.mu", self.mu)
        self.omega_l = _positive_float("FOVICInverter.omega_l", self.omega_l)
        self.omega_h = _positive_float("FOVICInverter.omega_h", self.omega_h)
        self.swing_two_factor = _positive_float(
            "FOVICInverter.swing_two_factor", self.swing_two_factor
        )
        if not isinstance(self.oustaloup_order, int) or self.oustaloup_order <= 0:
            raise ValueError(
                "FOVICInverter.oustaloup_order must be a positive integer."
            )
        if not (0.0 < self.mu < 1.0):
            raise ValueError(f"FOVICInverter.mu must be in (0, 1), got {self.mu}.")
        if self.omega_h <= self.omega_l:
            raise ValueError(
                "FOVICInverter.omega_h must be > omega_l "
                f"(got omega_h={self.omega_h}, omega_l={self.omega_l})."
            )

        (
            self._A_oust,
            self._B_oust,
            self._C_oust,
            self._D_oust,
        ) = self._build_oustaloup_ss()
        self._x_oust = np.zeros(self._A_oust.shape[0], dtype=float)
        self._x_dc = 0.0
        self._x_bess = 0.0

    @property
    def omega_ref(self) -> float:
        return 2.0 * np.pi * self.f_hz

    @property
    def omega(self) -> float:
        return self.omega_ref

    @property
    def v_pk(self) -> float:
        return np.sqrt(2.0) * self.v_ln_rms

    def modulate(
        self,
        theta: float,
        Vdc: float,
        m_max: float = FOVIC_MODULATION_INDEX_MAX_DEFAULT,
    ) -> np.ndarray:
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

    def _build_oustaloup_ss(self):
        """Build Oustaloup ZPK approximation and convert to state-space.

        References:
        - Yu et al. (2023), Sec. III-B1, Eq. (7)-(8)
        - Nour (2023), Sec. 3.1, Eq. (15)
        """
        from scipy import signal

        n = self.oustaloup_order
        q = self.mu
        w_b = self.omega_l
        w_h = self.omega_h

        k_values = np.arange(-n, n + 1, dtype=float)
        ratio = w_h / w_b
        denominator = float(2 * n + 1)

        # Yu (2023) Sec. III-B1 Eq. (8): w_k' definition.
        w_k_prime = w_b * (ratio ** ((k_values + n + (1.0 - q) / 2.0) / denominator))
        # Yu (2023) Sec. III-B1 Eq. (8): w_k definition.
        w_k = w_b * (ratio ** ((k_values + n + (1.0 + q) / 2.0) / denominator))
        # Yu (2023) Sec. III-B1 Eq. (7): K = w_h^q.
        gain = w_h**q

        zeros = -w_k_prime
        poles = -w_k
        a_mat, b_mat, c_mat, d_mat = signal.zpk2ss(zeros, poles, gain)
        return a_mat, b_mat, c_mat, float(d_mat[0, 0])

    def oustaloup_step(self, u: float, dt: float) -> float:
        """Advance Oustaloup SS model by one explicit-Euler step."""
        u = _finite_float("u", u)
        dt = _positive_float("dt", dt)
        x_dot = self._A_oust @ self._x_oust + self._B_oust[:, 0] * u
        self._x_oust = self._x_oust + dt * x_dot
        y = self._C_oust @ self._x_oust + self._D_oust * u
        return float(y[0])

    def compute_delta_P_ESS(self, delta_f: float, dt: float) -> float:
        """Compute FOVIC power term using Eq. (23) cascaded blocks.

        Reference:
        - Nour (2023), Sec. 3.2, Eq. (23)
        """
        delta_f = _finite_float("delta_f", delta_f)
        dt = _positive_float("dt", dt)

        # Fractional block K_H*s^mu (Nour 2023 Eq. (23)); s^mu via Oustaloup.
        frac_out = self.K_H * self.oustaloup_step(delta_f, dt)

        # DC block K_DC/(1 + s*T_DC) (Nour 2023 Eq. (23)).
        dc_dot = (self.K_DC * delta_f - self._x_dc) / self.T_DC
        self._x_dc = self._x_dc + dt * dc_dot
        dc_out = self._x_dc

        # BESS filter 1/(1 + s*T_BESS) (Nour 2023 Eq. (23)).
        pre_bess = dc_out + frac_out
        bess_dot = (pre_bess - self._x_bess) / self.T_BESS
        self._x_bess = self._x_bess + dt * bess_dot
        return self._x_bess

    def calculate_derivatives(self, P_ref, P_elec, omega, theta, delta_f, dt):
        """Compute FOVIC swing derivatives and delta_P_ESS.

        Reference:
        - Nour (2023), Sec. 3.2, Eq. (18):
          delta_P_M - delta_P_L + delta_P_ESS = (2H*s + D)*delta_f
        """
        P_ref = _finite_float("P_ref", P_ref)
        P_elec = _finite_float("P_elec", P_elec)
        omega = _finite_float("omega", omega)
        theta = _finite_float("theta", theta)
        delta_f = _finite_float("delta_f", delta_f)
        dt = _positive_float("dt", dt)

        delta_P_ESS = self.compute_delta_P_ESS(delta_f=delta_f, dt=dt)
        # Nour (2023) Eq. (18): solve for s*delta_f = d(delta_f)/dt.
        d_omega_dt = (
            P_ref - P_elec + delta_P_ESS - self.D * delta_f
        ) / (self.swing_two_factor * self.H)
        d_theta_dt = omega
        return d_omega_dt, d_theta_dt, delta_P_ESS


def validate_nonzero_positive_modulation(m_max: float) -> float:
    """Validate modulation index for internal modulation calls."""
    return _positive_float("m_max", m_max)
