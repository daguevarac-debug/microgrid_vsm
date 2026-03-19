"""Composed dynamic model for the PV + DC-link + LCL baseline system."""

import numpy as np

from config import (
    DCLINK_CAP_F_DEFAULT,
    DCLINK_VMIN_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    MICROGRID_ETA_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_R1_OHM_DEFAULT,
    MICROGRID_LOAD_R2_OHM_DEFAULT,
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
from controllers.base import InverterControllerBase
from controllers.grid_following import GridFollowingController
from dclink import DCLinkParams
from inverter_source import GridFormingInverter, validate_dc_bus_capability
from lcl_filter import LCLFilter
from models.plant import HardwarePlant
from pv_model import PVArrayParams, PVArraySingleDiode, PVModuleParams


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
        self.eta = MICROGRID_ETA_DEFAULT
        self.v_uvlo = MICROGRID_UVLO_V_DEFAULT
        self.t_step = MICROGRID_LOAD_STEP_TIME_S_DEFAULT
        self.r_load_1 = MICROGRID_LOAD_R1_OHM_DEFAULT
        self.r_load_2 = MICROGRID_LOAD_R2_OHM_DEFAULT

        self.irradiance_profile = irradiance_profile or (lambda t: MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT)
        self.temperature_profile = temperature_profile or (lambda t: MICROGRID_TEMPERATURE_C_DEFAULT)
        self.load_profile = load_profile or (lambda t: self.r_load_1 if t < self.t_step else self.r_load_2)

        self.P_ref_nominal = (
            MICROGRID_PV_VMP_STC_V_DEFAULT
            * MICROGRID_PV_IMP_STC_A_DEFAULT
            * MICROGRID_PV_ARRAY_SERIES_DEFAULT
            * MICROGRID_PV_ARRAY_PARALLEL_DEFAULT
            * MICROGRID_ETA_DEFAULT
        )
        self.vdc_ref = SIM_VDC0_V_DEFAULT

        g0 = float(self.irradiance_profile(0.0))
        t0 = float(self.temperature_profile(0.0))
        ipv_ref = self.pv.ipv_from_vpv(max(self.vdc_ref, 0.0), G=g0, T_c=t0)
        self.p_available_ref = max(self.vdc_ref * ipv_ref * self.eta, 0.0)
        controller_p_ref = min(self.P_ref_nominal, self.p_available_ref)

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

    def system_dynamics(self, t: float, x):
        """Return ODE derivatives for baseline state vector."""
        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        xi_vdc = x[10]
        theta = x[11]

        # TODO [PERFIL_IRRADIANCIA]: Reemplazar con interpolador de DataFrame (tiempo vs G en W/m^2).
        G_t = self.irradiance_profile(t)
        # TODO [PERFIL_TEMPERATURA]: Reemplazar con interpolador de DataFrame (tiempo vs T_c en C).
        T_c_t = self.temperature_profile(t)
        # TODO [PERFIL_DEMANDA]: En baseline, load_profile representa carga local equivalente (no IEEE acoplado).
        r_load_t = self.load_profile(t)

        Vdc_eff = max(Vdc, 0.0)
        Ipv = self.plant.pv_current(Vdc_eff, G_t, T_c_t)
        v_pcc = self.plant.pcc_voltage(i2, r_load_t)
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
        di1dt, dvcdt, di2dt = self.plant.lcl_derivatives(control.v_inv, v_pcc, i1, vc, i2)

        # TODO [MODELO_BESS]: El balance DC pasara a dVdc=(Ipv+i_bess-Idc_inv)/Cdc cuando se integre bateria.
        dVdc = self.plant.dc_link_derivative(Ipv, control.idc_inv)
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
        i2 = np.array([x[7], x[8], x[9]])
        xi_vdc = x[10]
        theta = x[11]

        G_t = self.irradiance_profile(t)
        T_c_t = self.temperature_profile(t)
        r_load_t = self.load_profile(t)

        Vdc_eff = max(Vdc, 0.0)
        Ipv = self.plant.pv_current(Vdc_eff, G_t, T_c_t)
        v_pcc = self.plant.pcc_voltage(i2, r_load_t)
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
        return control.p_bridge, control.p_pcc, control.idc_inv, control.p_cmd, control.m_ctrl

