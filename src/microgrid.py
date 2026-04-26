"""Composed dynamic model for the PV + DC-link + LCL baseline system.

Contains:
- HardwarePlant: physical plant layer (PV, DC-link, LCL)
- Microgrid: composed plant + controller for baseline averaged model
"""

from dataclasses import dataclass
from numbers import Real
from pathlib import Path

import numpy as np

from bess.model import SecondLifeBattery1RC
from config import (
    BESS_COUPLED_I_MAX_DEFAULT,
    BESS_COUPLED_KP_DEFAULT,
    BESS_COUPLED_P_MAX_W_DEFAULT,
    BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
    BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
    BESS_COUPLED_R0_DEFAULT,
    BESS_COUPLED_SOC_INIT_DEFAULT,
    BESS_COUPLED_SOC_MAX_DEFAULT,
    BESS_COUPLED_SOC_MIN_DEFAULT,
    DCLINK_CAP_F_DEFAULT,
    DCLINK_VMIN_DEFAULT,
    GRID_FREQ_HZ_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    MICROGRID_ETA_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    MICROGRID_LOAD_R1_OHM_DEFAULT,
    MICROGRID_LOAD_R2_OHM_DEFAULT,
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
    MICROGRID_PV_ARRAY_PARALLEL_DEFAULT,
    MICROGRID_PV_ARRAY_SERIES_DEFAULT,
    MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
    MICROGRID_PV_DIODE_IDEALITY_DEFAULT,
    MICROGRID_PV_IMP_STC_A_DEFAULT,
    MICROGRID_PV_ISC_STC_A_DEFAULT,
    MICROGRID_PV_NS_CELLS_DEFAULT,
    MICROGRID_PV_RSH_OHM_DEFAULT,
    MICROGRID_PV_RS_OHM_DEFAULT,
    MICROGRID_PV_VMP_STC_V_DEFAULT,
    MICROGRID_PV_VOC_STC_V_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    MICROGRID_UVLO_V_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.base import ControlOutput, InverterControllerBase
from controllers.grid_following import GridFollowingController
from dclink import DCLinkParams
from inverter_source import GridFormingInverter, validate_dc_bus_capability
from lcl_filter import LCLFilter
from pv_model import PVArrayParams, PVArraySingleDiode, PVModuleParams


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

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


def _eta_float(name: str, value) -> float:
    out = _finite_float(name, value)
    if out <= 0.0 or out > 1.0:
        raise ValueError(f"{name} must be in (0, 1], got {value!r}.")
    return out


def _fraction_float(name: str, value) -> float:
    out = _finite_float(name, value)
    if out < 0.0 or out >= 1.0:
        raise ValueError(f"{name} must be in [0, 1), got {value!r}.")
    return out


def _validate_profile_callable(name: str, profile) -> None:
    if not callable(profile):
        raise ValueError(f"{name} must be callable(t) -> finite numeric value, got {type(profile).__name__}.")


def _evaluate_profile(name: str, profile, t: float) -> float:
    _validate_profile_callable(name, profile)
    try:
        value = profile(t)
    except Exception as exc:  # pragma: no cover - exception passthrough
        raise ValueError(f"{name} failed at t={t!r}: {exc}") from exc
    return _finite_float(f"{name}(t={t!r})", value)


@dataclass(frozen=True)
class BalancedRLLoad:
    """Balanced three-phase constant-impedance R-L load parameters."""

    p_3ph_w: float
    power_factor: float
    v_ln_rms: float
    f_hz: float
    r_ohm: float
    l_h: float
    q_3ph_var: float

    @classmethod
    def from_active_power(
        cls,
        p_3ph_w: float,
        power_factor: float,
        v_ln_rms: float = GRID_V_LN_RMS_DEFAULT,
        f_hz: float = GRID_FREQ_HZ_DEFAULT,
    ) -> "BalancedRLLoad":
        """Return a balanced inductive R-L load matching P and power factor."""
        p_3ph_w = _positive_float("BalancedRLLoad.p_3ph_w", p_3ph_w)
        power_factor = _eta_float("BalancedRLLoad.power_factor", power_factor)
        v_ln_rms = _positive_float("BalancedRLLoad.v_ln_rms", v_ln_rms)
        f_hz = _positive_float("BalancedRLLoad.f_hz", f_hz)

        phi = float(np.arccos(power_factor))
        z_abs = 3.0 * v_ln_rms**2 * power_factor / p_3ph_w
        r_ohm = z_abs * power_factor
        x_l_ohm = z_abs * np.sin(phi)
        l_h = x_l_ohm / (2.0 * np.pi * f_hz)
        q_3ph_var = p_3ph_w * np.tan(phi)

        return cls(
            p_3ph_w=p_3ph_w,
            power_factor=power_factor,
            v_ln_rms=v_ln_rms,
            f_hz=f_hz,
            r_ohm=float(r_ohm),
            l_h=float(l_h),
            q_3ph_var=float(q_3ph_var),
        )


# ---------------------------------------------------------------------------
# HardwarePlant
# ---------------------------------------------------------------------------

class HardwarePlant:
    """Physical layer: PV source, DC-link and LCL filter dynamics."""

    def __init__(
        self,
        pv: PVArraySingleDiode,
        dcp: DCLinkParams,
        lcl: LCLFilter,
        eta: float,
        v_uvlo: float,
    ):
        if not isinstance(pv, PVArraySingleDiode):
            raise ValueError(f"pv must be PVArraySingleDiode, got {type(pv).__name__}.")
        if not isinstance(dcp, DCLinkParams):
            raise ValueError(f"dcp must be DCLinkParams, got {type(dcp).__name__}.")
        if not isinstance(lcl, LCLFilter):
            raise ValueError(f"lcl must be LCLFilter, got {type(lcl).__name__}.")
        eta = _eta_float("HardwarePlant.eta", eta)
        v_uvlo = _positive_float("HardwarePlant.v_uvlo", v_uvlo)
        self.pv = pv
        self.dcp = dcp
        self.lcl = lcl
        self.eta = eta
        self.v_uvlo = v_uvlo

    def pv_current(self, vdc_eff: float, irradiance: float, cell_temp_c: float) -> float:
        """Return PV array current for current operating point."""
        return self.pv.ipv_from_vpv(vdc_eff, G=irradiance, T_c=cell_temp_c)

    def pcc_voltage(self, i2: np.ndarray, r_load: float) -> np.ndarray:
        """Legacy resistive PCC closure kept for compatibility."""
        return i2 * r_load

    def lcl_derivatives_with_rl_load(
        self,
        v_inv: np.ndarray,
        i1: np.ndarray,
        vc: np.ndarray,
        i2: np.ndarray,
        load: BalancedRLLoad,
    ):
        """Return LCL derivatives and PCC voltage for a balanced R-L load.

        The R-L load is not added as a new state. For each phase,
        v_pcc = R_load*i2 + L_load*di2/dt is substituted into the LCL
        grid-side inductor equation, giving an explicit derivative with
        effective inductance L2 + L_load.
        """
        v_inv = np.asarray(v_inv, dtype=float)
        i1 = np.asarray(i1, dtype=float)
        vc = np.asarray(vc, dtype=float)
        i2 = np.asarray(i2, dtype=float)

        di1dt = (v_inv - vc - self.lcl.R1 * i1) / self.lcl.L1
        dvcdt = (i1 - i2 - vc / self.lcl.Rd) / self.lcl.Cf
        di2dt = (vc - (self.lcl.R2 + load.r_ohm) * i2) / (self.lcl.L2 + load.l_h)
        v_pcc = load.r_ohm * i2 + load.l_h * di2dt

        return di1dt, dvcdt, di2dt, v_pcc

    def dc_link_derivative(self, ipv: float, idc_inv: float, i_bess: float = 0.0) -> float:
        """Return DC-link voltage derivative from current balance.

        Sign convention at the DC-link capacitor:
        - Positive current enters the capacitor (raises Vdc).
        - `ipv > 0` injects from PV to DC bus.
        - `i_bess > 0` injects from BESS to DC bus (battery discharge).
        - `idc_inv > 0` is absorbed by inverter from DC bus to AC side.
        """
        # TODO [MODELO_BESS]: mantener trazabilidad de la convencion de signo
        # del intercambio BESS<->bus DC durante la integracion incremental.
        return (ipv + i_bess - idc_inv) / self.dcp.Cdc

    def lcl_derivatives(
        self,
        v_inv: np.ndarray,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        vc: np.ndarray,
        i2: np.ndarray,
    ):
        """Delegate LCL state derivatives."""
        return self.lcl.calculate_derivatives(v_inv, v_pcc, i1, vc, i2)


# ---------------------------------------------------------------------------
# Microgrid
# ---------------------------------------------------------------------------

class Microgrid:
    """Compose plant and baseline controller for the averaged dynamic model."""

    def __init__(
        self,
        irradiance_profile=None,
        temperature_profile=None,
        load_profile=None,
        controller: InverterControllerBase | None = None,
    ):
        mod = PVModuleParams(
            voc_stc=MICROGRID_PV_VOC_STC_V_DEFAULT,
            isc_stc=MICROGRID_PV_ISC_STC_A_DEFAULT,
            vmp_stc=MICROGRID_PV_VMP_STC_V_DEFAULT,
            imp_stc=MICROGRID_PV_IMP_STC_A_DEFAULT,
            ns_cells=MICROGRID_PV_NS_CELLS_DEFAULT,
            alpha_isc=MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
            beta_voc=MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
            n=MICROGRID_PV_DIODE_IDEALITY_DEFAULT,
            rs=MICROGRID_PV_RS_OHM_DEFAULT,
            rsh=MICROGRID_PV_RSH_OHM_DEFAULT,
        )
        arr = PVArrayParams(
            module=mod,
            modules_in_series=MICROGRID_PV_ARRAY_SERIES_DEFAULT,
            strings_in_parallel=MICROGRID_PV_ARRAY_PARALLEL_DEFAULT,
        )
        self.pv = PVArraySingleDiode(arr)

        self.dcp = DCLinkParams(Cdc=DCLINK_CAP_F_DEFAULT, Vmin=DCLINK_VMIN_DEFAULT)
        self.lcl = LCLFilter()
        self.eta = _eta_float("Microgrid.eta", MICROGRID_ETA_DEFAULT)
        self.v_uvlo = _positive_float("Microgrid.v_uvlo", MICROGRID_UVLO_V_DEFAULT)
        self.t_step = _positive_float("Microgrid.t_step", MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
        self.r_load_1 = _positive_float("Microgrid.r_load_1", MICROGRID_LOAD_R1_OHM_DEFAULT)
        self.r_load_2 = _positive_float("Microgrid.r_load_2", MICROGRID_LOAD_R2_OHM_DEFAULT)
        self.p_load_nominal_w = _positive_float(
            "Microgrid.p_load_nominal_w", MICROGRID_LOAD_P_NOM_W_DEFAULT
        )
        self.load_power_factor = _eta_float(
            "Microgrid.load_power_factor", MICROGRID_LOAD_POWER_FACTOR_DEFAULT
        )
        self.load_step_fraction = _fraction_float(
            "Microgrid.load_step_fraction", MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT
        )
        self.p_load_1_w = self.p_load_nominal_w
        self.p_load_2_w = self.p_load_nominal_w * (1.0 + self.load_step_fraction)

        self.irradiance_profile = irradiance_profile or (lambda t: MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)
        self.temperature_profile = temperature_profile or (lambda t: MICROGRID_TEMPERATURE_C_DEFAULT)
        self.load_profile = load_profile or (lambda t: self.p_load_1_w if t < self.t_step else self.p_load_2_w)
        _validate_profile_callable("Microgrid.irradiance_profile", self.irradiance_profile)
        _validate_profile_callable("Microgrid.temperature_profile", self.temperature_profile)
        _validate_profile_callable("Microgrid.load_profile", self.load_profile)

        self.P_ref_nominal = (
            MICROGRID_PV_VMP_STC_V_DEFAULT
            * MICROGRID_PV_IMP_STC_A_DEFAULT
            * MICROGRID_PV_ARRAY_SERIES_DEFAULT
            * MICROGRID_PV_ARRAY_PARALLEL_DEFAULT
            * MICROGRID_ETA_DEFAULT
        )
        self.vdc_ref = SIM_VDC0_V_DEFAULT

        g0 = _evaluate_profile("Microgrid.irradiance_profile", self.irradiance_profile, 0.0)
        t0 = _evaluate_profile("Microgrid.temperature_profile", self.temperature_profile, 0.0)
        _ = self._load_at_time(0.0)
        ipv_ref = self.pv.ipv_from_vpv(max(self.vdc_ref, 0.0), G=g0, T_c=t0)
        self.p_available_ref = max(self.vdc_ref * ipv_ref * self.eta, 0.0)
        controller_p_ref = min(self.P_ref_nominal, self.p_available_ref)

        if controller is not None and not isinstance(controller, InverterControllerBase):
            raise ValueError(
                f"controller must implement InverterControllerBase, got {type(controller).__name__}."
            )
        self.controller = controller or GridFollowingController(p_ref=controller_p_ref, vdc_ref=self.vdc_ref)
        self.plant = HardwarePlant(self.pv, self.dcp, self.lcl, self.eta, self.v_uvlo)

        self.vdc_min_required = validate_dc_bus_capability(
            vdc0=SIM_VDC0_V_DEFAULT,
            vdc_ref=getattr(self.controller, "vdc_ref", SIM_VDC0_V_DEFAULT),
            v_ln_rms=getattr(self.controller, "modulator", GridFormingInverter()).v_ln_rms,
            m_max=getattr(self.controller, "m_base", INVERTER_MODULATION_INDEX_MAX_DEFAULT),
            strict=False,
            context=type(self.controller).__name__,
        )

        self._last_p_bridge = 0.0
        self._last_p_pcc = 0.0
        self._last_p_cmd = 0.0
        self._last_m_ctrl = 0.0

    def _load_at_time(self, t: float) -> BalancedRLLoad:
        """Evaluate active-power load profile and convert it to R-L parameters."""
        # TODO [PERFIL_DEMANDA]: En baseline, load_profile representa potencia
        # activa agregada equivalente; reemplazar luego con perfil P/Q medido.
        p_load_t = _positive_float(
            f"Microgrid.load_profile(t={t!r})", _evaluate_profile("Microgrid.load_profile", self.load_profile, t)
        )
        return BalancedRLLoad.from_active_power(
            p_3ph_w=p_load_t,
            power_factor=self.load_power_factor,
            v_ln_rms=GRID_V_LN_RMS_DEFAULT,
            f_hz=GRID_FREQ_HZ_DEFAULT,
        )

    def _compute_step_control(self, t: float, Vdc: float, i1: np.ndarray, i2: np.ndarray, xi_vdc: float, theta: float):
        """Evaluate profiles and return instantaneous control variables for one time step."""
        # TODO [PERFIL_IRRADIANCIA]: Reemplazar con interpolador de DataFrame (tiempo vs G en W/m^2).
        G_t = _evaluate_profile("Microgrid.irradiance_profile", self.irradiance_profile, t)
        # TODO [PERFIL_TEMPERATURA]: Reemplazar con interpolador de DataFrame (tiempo vs T_c en C).
        T_c_t = _evaluate_profile("Microgrid.temperature_profile", self.temperature_profile, t)
        load_t = self._load_at_time(t)
        Vdc_eff = max(Vdc, 0.0)
        Ipv = self.plant.pv_current(Vdc_eff, G_t, T_c_t)
        # The baseline controller does not use v_pcc to set v_inv/idc_inv.
        # The true R-L PCC voltage is updated after di2/dt is known.
        v_pcc = self.plant.pcc_voltage(i2, load_t.r_ohm)
        control = self.controller.compute_control(
            t=t,
            theta=theta,
            xi_vdc=xi_vdc,
            vdc_eff=Vdc_eff,
            v_pcc=v_pcc,
            i1=i1,
            i2=i2,
            plant=self.plant,
            ipv=Ipv,
        )
        return Ipv, load_t, control

    def system_dynamics(self, t: float, x):
        """Return ODE derivatives for baseline state vector."""
        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        xi_vdc = x[10]
        theta = x[11]
        Ipv, load_t, control = self._compute_step_control(t, Vdc, i1, i2, xi_vdc, theta)
        di1dt, dvcdt, di2dt, v_pcc = self.plant.lcl_derivatives_with_rl_load(
            control.v_inv, i1, vc, i2, load_t
        )

        # TODO [MODELO_BESS]: en baseline sin BESS activo se usa i_bess=0.0;
        # al integrar almacenamiento, usar dVdc=(Ipv+i_bess-Idc_inv)/Cdc.
        dVdc = self.plant.dc_link_derivative(Ipv, control.idc_inv)
        control.p_pcc = float(np.dot(v_pcc, i2))
        self._last_p_bridge = control.p_bridge
        self._last_p_pcc = control.p_pcc
        self._last_p_cmd = control.p_cmd
        self._last_m_ctrl = control.m_ctrl

        return [
            dVdc,
            di1dt[0],
            di1dt[1],
            di1dt[2],
            dvcdt[0],
            dvcdt[1],
            dvcdt[2],
            di2dt[0],
            di2dt[1],
            di2dt[2],
            control.d_xi_vdc_dt,
            control.d_theta_dt,
        ]

    def power_signals(self, t: float, x):
        """Return p_bridge, p_pcc, idc_inv, p_cmd and m_ctrl for diagnostics."""
        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        xi_vdc = x[10]
        theta = x[11]
        _, load_t, control = self._compute_step_control(t, Vdc, i1, i2, xi_vdc, theta)
        _, _, _, v_pcc = self.plant.lcl_derivatives_with_rl_load(control.v_inv, i1, vc, i2, load_t)
        control.p_pcc = float(np.dot(v_pcc, i2))
        return control.p_bridge, control.p_pcc, control.idc_inv, control.p_cmd, control.m_ctrl


class MicrogridWithBESS(Microgrid):
    """Conservative first-step integration of validated BESS into DC-link dynamics.

    Added BESS states:
    - soc_bess
    - vrc_bess
    - zdeg_bess

    Modeling note:
    - The BESS is coupled through an idealized DC/DC interface that is not
      modeled in detail at this stage.
    - ``i_bess`` is the exchange variable between storage and the DC bus.
    - ``V_t_bess``, SoC, and SoH are used for storage internal dynamics and
      diagnostics.
    - ``V_t_bess`` is an internal battery-model variable (diagnostic), not the
      DC-bus voltage.
    """

    def __init__(
        self,
        irradiance_profile=None,
        temperature_profile=None,
        load_profile=None,
        controller: InverterControllerBase | None = None,
        bess_model: SecondLifeBattery1RC | None = None,
        kp_bess: float = BESS_COUPLED_KP_DEFAULT,
        i_bess_max: float = BESS_COUPLED_I_MAX_DEFAULT,
        p_bess_max_w: float = BESS_COUPLED_P_MAX_W_DEFAULT,
        bess_excel_path: str | Path | None = None,
    ):
        super().__init__(
            irradiance_profile=irradiance_profile,
            temperature_profile=temperature_profile,
            load_profile=load_profile,
            controller=controller,
        )
        self.kp_bess = _positive_float("MicrogridWithBESS.kp_bess", kp_bess)
        self.i_bess_max = _positive_float("MicrogridWithBESS.i_bess_max", i_bess_max)
        self.p_bess_max_w = _positive_float("MicrogridWithBESS.p_bess_max_w", p_bess_max_w)

        if bess_model is not None and not isinstance(bess_model, SecondLifeBattery1RC):
            raise ValueError(
                "bess_model must be SecondLifeBattery1RC when provided, got "
                f"{type(bess_model).__name__}."
            )

        if bess_model is None:
            repo_root = Path(__file__).resolve().parents[1]
            excel_path = Path(bess_excel_path) if bess_excel_path is not None else (repo_root / "OCV_SOC.xlsx")
            self.bess = SecondLifeBattery1RC.from_excel_characterization(
                excel_path=excel_path,
                q_nom_ref_ah=BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
                q_init_case_ah=BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
                r0_nominal_ohm=BESS_COUPLED_R0_DEFAULT,
                r0_soh_sensitivity=1.0,
                k_deg=1.478e-6,
                soh_min=0.50,
                q_eff_min_ah=1e-9,
                soc_initial=BESS_COUPLED_SOC_INIT_DEFAULT,
                soc_min=BESS_COUPLED_SOC_MIN_DEFAULT,
                soc_max=BESS_COUPLED_SOC_MAX_DEFAULT,
            )
        else:
            self.bess = bess_model

        self._last_i_bess = 0.0
        self._last_soc_bess = float(self.bess.soc_initial)
        self._last_soh_bess = float(self.bess.soh_init_case)
        self._last_vt_bess = float(
            self.bess.terminal_voltage(
                soc=self.bess.soc_initial,
                v_rc=0.0,
                i_bess=0.0,
                soh=self.bess.soh_init_case,
            )
        )

    def initial_state_with_bess(self, vdc0: float = SIM_VDC0_V_DEFAULT) -> list[float]:
        """Return baseline initial state augmented with BESS dynamic states."""
        vdc0 = _finite_float("vdc0", vdc0)
        base_state = [
            vdc0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            getattr(getattr(self.controller, "modulator", None), "theta0", 0.0),
        ]
        return base_state + self.bess.initial_state_with_degradation(
            soc=self.bess.soc_initial,
            v_rc=0.0,
            z_deg=0.0,
        )

    def _available_i_bess_max(self, soh_bess: float | None = None) -> float:
        """Return SoH-dependent available BESS current limit."""
        soh_eval = self.bess.soh_init_case if soh_bess is None else _finite_float("soh_bess", soh_bess)
        if soh_eval < 0.0 or soh_eval > 1.0:
            raise ValueError(f"soh_bess must be within [0, 1], got {soh_eval}.")
        i_available = self.i_bess_max * soh_eval
        return min(self.i_bess_max, max(0.0, i_available))

    def _available_p_bess_max_w(self, soh_bess: float | None = None) -> float:
        """Return SoH-dependent available BESS DC power limit."""
        i_available = self._available_i_bess_max(soh_bess)
        p_available = self.vdc_ref * i_available
        return min(self.p_bess_max_w, p_available)

    def _compute_i_bess(self, Vdc: float, soc_bess: float, soh_bess: float | None = None) -> float:
        """Simple proportional DC-link support with SoC, SoH, current and power limits."""
        Vdc = _finite_float("Vdc", Vdc)
        soc_bess = _finite_float("soc_bess", soc_bess)
        i_bess_cmd = self.kp_bess * (self.vdc_ref - Vdc)
        i_limit_available = self._available_i_bess_max(soh_bess)
        i_bess_sat = float(np.clip(i_bess_cmd, -i_limit_available, i_limit_available))

        # Sign convention (battery model): i_bess > 0 discharge, i_bess < 0 charge.
        if soc_bess <= self.bess.soc_min and i_bess_sat > 0.0:
            i_bess_sat = 0.0
        if soc_bess >= self.bess.soc_max and i_bess_sat < 0.0:
            i_bess_sat = 0.0
        if Vdc > 0.0:
            p_limit_available = self._available_p_bess_max_w(soh_bess)
            i_power_limit = p_limit_available / Vdc
            i_bess_sat = float(np.clip(i_bess_sat, -i_power_limit, i_power_limit))
        return i_bess_sat

    def system_dynamics(self, t: float, x):
        """Return ODE derivatives for integrated baseline + BESS state vector."""
        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        xi_vdc = x[10]
        theta = x[11]
        soc_bess = x[12]
        vrc_bess = x[13]
        zdeg_bess = x[14]

        Ipv, load_t, control = self._compute_step_control(t, Vdc, i1, i2, xi_vdc, theta)
        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess = self._compute_i_bess(Vdc=Vdc, soc_bess=soc_bess, soh_bess=soh_bess)
        di1dt, dvcdt, di2dt, v_pcc = self.plant.lcl_derivatives_with_rl_load(
            control.v_inv, i1, vc, i2, load_t
        )
        dVdc = self.plant.dc_link_derivative(Ipv, control.idc_inv, i_bess=i_bess)
        d_bess = self.bess.rhs(
            t=t,
            x=[soc_bess, vrc_bess, zdeg_bess],
            i_bess=i_bess,
            soh=self.bess.soh_init_case,
        )

        vt_bess = self.bess.terminal_voltage(
            soc=soc_bess,
            v_rc=vrc_bess,
            i_bess=i_bess,
            soh=soh_bess,
        )

        self._last_p_bridge = control.p_bridge
        control.p_pcc = float(np.dot(v_pcc, i2))
        self._last_p_pcc = control.p_pcc
        self._last_p_cmd = control.p_cmd
        self._last_m_ctrl = control.m_ctrl
        self._last_i_bess = i_bess
        self._last_soc_bess = soc_bess
        self._last_soh_bess = soh_bess
        self._last_vt_bess = vt_bess

        return [
            dVdc,
            di1dt[0],
            di1dt[1],
            di1dt[2],
            dvcdt[0],
            dvcdt[1],
            dvcdt[2],
            di2dt[0],
            di2dt[1],
            di2dt[2],
            control.d_xi_vdc_dt,
            control.d_theta_dt,
            d_bess[0],
            d_bess[1],
            d_bess[2],
        ]

    def integrated_signals(self, t: float, x) -> dict[str, float]:
        """Return key integrated diagnostics for thesis traceability."""
        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        xi_vdc = x[10]
        theta = x[11]
        soc_bess = x[12]
        vrc_bess = x[13]
        zdeg_bess = x[14]

        _, load_t, control = self._compute_step_control(t, Vdc, i1, i2, xi_vdc, theta)
        _, _, _, v_pcc = self.plant.lcl_derivatives_with_rl_load(control.v_inv, i1, vc, i2, load_t)
        control.p_pcc = float(np.dot(v_pcc, i2))
        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess = self._compute_i_bess(Vdc=Vdc, soc_bess=soc_bess, soh_bess=soh_bess)
        p_bess_dc = float(Vdc) * float(i_bess)
        vt_bess = self.bess.terminal_voltage(
            soc=soc_bess,
            v_rc=vrc_bess,
            i_bess=i_bess,
            soh=soh_bess,
        )
        p_load = float(np.dot(v_pcc, i2))

        return {
            "Vdc": float(Vdc),
            "p_bridge": float(control.p_bridge),
            "p_pcc": float(control.p_pcc),
            "p_load": p_load,
            "i_bess": float(i_bess),
            "p_bess_dc": p_bess_dc,
            "p_bess_dc_max": float(self.p_bess_max_w),
            "i_bess_max_available": float(self._available_i_bess_max(soh_bess)),
            "p_bess_dc_max_available": float(self._available_p_bess_max_w(soh_bess)),
            "soc_bess": float(soc_bess),
            "vt_bess": float(vt_bess),
            "soh_bess": float(soh_bess),
        }
