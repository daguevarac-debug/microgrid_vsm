"""Non-invasive 16-state GFM + BESS + bidirectional DC/DC interface architecture.

This module closes the physical bank-to-DC-bus gap documented in BAT26-48 and
Phase 2 without modifying any protected equations or state-vector mappings in
``microgrid.py`` or ``microgrid_bess_pi.py``.

Approved parametric bank topology (BAT26-53):
- 48 Nissan Leaf 2s2p modules connected in series -> ``n_series = 96`` 2p
  cell-pairs in series, ``n_parallel = 1``.
- Nominal bank voltage: ``96 * 3.75 V = 360.0 V`` (``48 * 7.5 V``), spanning
  below and above the independent ``340.0 V`` DC link across ``SoC in [0.10, 0.90]``.
- Nominal reference capacity: ``66.0 Ah``; case initial capacity: ``44.1 Ah``
  (``SoH_0 = 44.1 / 66.0 = 0.668182``).

Reuses ``bess.dc_dc_adapter.convert_power`` algebraically inside the same global
16-state ``solve_ivp`` integration:
- Physical battery string current ``i_bank = n_parallel * i_unit`` drives the
  1RC states (``soc_bess``, ``vrc_bess``, ``zdeg_bess``).
- DC-bus current ``i_bus = p_bus / Vdc`` enters ``dVdc/dt = (ipv + i_bus - idc_inv)/Cdc``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np

from bess.dc_dc_adapter import DCDCParameters, DCDCResult, convert_power
from controllers.dc_link_bess_pi import DCLinkBESSPIOutput
from microgrid import _finite_float
from microgrid_bess_pi import MicrogridWithBESSPI


BAT26_53_LEAF_MODULES_SERIES = 48
BAT26_53_CELL_PAIRS_PER_MODULE = 2  # 2s2p module = 2 cell-pairs (2p) in series
BAT26_53_N_SERIES_2P_UNITS = BAT26_53_LEAF_MODULES_SERIES * BAT26_53_CELL_PAIRS_PER_MODULE  # 96
BAT26_53_N_PARALLEL_STRINGS = 1


def default_bat26_53_dcdc_parameters(
    *,
    eta_discharge: float = 0.95,
    eta_charge: float = 0.95,
    unit_voltage_min_v: float = 2.50,
    unit_voltage_max_v: float = 4.20,
    unit_discharge_max_a: float = 66.0,
    unit_charge_max_a: float = 66.0,
    bus_current_max_a: float = 66.0,
    bus_power_max_w: float = 22440.0,
) -> DCDCParameters:
    """Return parameterized bidirectional DC/DC specs for the 48s 2s2p Leaf bank."""
    return DCDCParameters(
        n_series=BAT26_53_N_SERIES_2P_UNITS,
        n_parallel=BAT26_53_N_PARALLEL_STRINGS,
        eta_discharge=eta_discharge,
        eta_charge=eta_charge,
        unit_voltage_min_v=unit_voltage_min_v,
        unit_voltage_max_v=unit_voltage_max_v,
        unit_discharge_max_a=unit_discharge_max_a,
        unit_charge_max_a=unit_charge_max_a,
        bus_current_max_a=bus_current_max_a,
        bus_power_max_w=bus_power_max_w,
    )


@dataclass(frozen=True)
class CoupledDCDCState:
    """Complete instantaneous electrical coupling across bank, DC/DC, and DC bus."""

    pi_output: DCLinkBESSPIOutput
    dcdc_result: DCDCResult
    v_bank_v: float
    i_bank_a: float
    i_bus_a: float
    p_bank_w: float
    p_bus_w: float
    p_loss_w: float
    efficiency_instant: float


class MicrogridWithBESSDCDC(MicrogridWithBESSPI):
    """16-state GFM+BESS+PI microgrid coupled through a bidirectional DC/DC stage."""

    def __init__(
        self,
        *,
        dcdc_parameters: DCDCParameters | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        if dcdc_parameters is None:
            dcdc_parameters = default_bat26_53_dcdc_parameters(
                unit_discharge_max_a=float(self.i_bess_max),
                unit_charge_max_a=float(self.i_bess_max),
                bus_current_max_a=float(self.i_bess_max),
                bus_power_max_w=float(self.p_bess_max_w),
            )
        if not isinstance(dcdc_parameters, DCDCParameters):
            raise ValueError(
                "dcdc_parameters must be DCDCParameters, got "
                f"{type(dcdc_parameters).__name__}."
            )
        self.dcdc_parameters = dcdc_parameters

    def _evaluate_dcdc_coupling(
        self,
        *,
        vdc_v: float,
        soc_bess: float,
        vrc_bess: float,
        soh_bess: float,
        xi_bess_vdc_v_s: float,
    ) -> CoupledDCDCState:
        """Compute PI power request, DC/DC limits, physical bank current, and bus current."""
        vdc = _finite_float("vdc_v", vdc_v)
        soc = _finite_float("soc_bess", soc_bess)
        vrc = _finite_float("vrc_bess", vrc_bess)
        soh = _finite_float("soh_bess", soh_bess)

        effective_enabled = bool(self.bess_enabled and vdc > 0.0)
        ocv_v = float(self.bess.ocv(soc))
        r0_ohm = float(self.bess.r0(soh))
        i_unit_avail = float(self._available_i_bess_max(soh))
        vbus_eval = vdc

        if not effective_enabled:
            pi_output = self.dc_link_bess_pi.compute(
                vdc_v=vdc,
                xi_vdc_v_s=xi_bess_vdc_v_s,
                p_min_w=0.0,
                p_max_w=0.0,
                bess_enabled=False,
            )
            e_unit = ocv_v - vrc
            zero_res = DCDCResult(
                unit_current_a=0.0,
                bus_current_a=0.0,
                unit_voltage_v=e_unit,
                bank_power_w=0.0,
                bus_power_w=0.0,
                loss_power_w=0.0,
                saturated=False,
                bus_charge_limit_w=0.0,
                bus_discharge_limit_w=0.0,
                protection_status="disabled",
            )
            return CoupledDCDCState(
                pi_output=pi_output,
                dcdc_result=zero_res,
                v_bank_v=self.dcdc_parameters.n_series * e_unit,
                i_bank_a=0.0,
                i_bus_a=0.0,
                p_bank_w=0.0,
                p_bus_w=0.0,
                p_loss_w=0.0,
                efficiency_instant=1.0,
            )

        # 1. Probe exact bus-side admissible limits from the DC/DC + bank state.
        probe = convert_power(
            parameters=self.dcdc_parameters,
            bus_power_request_w=0.0,
            bus_voltage_v=vbus_eval,
            ocv_v=ocv_v,
            vrc_v=vrc,
            r0_ohm=r0_ohm,
            soc=soc,
            soc_min=self.bess.soc_min,
            soc_max=self.bess.soc_max,
            unit_discharge_available_a=i_unit_avail,
            unit_charge_available_a=i_unit_avail,
        )
        inherited_limit = self._available_p_bess_max_w(soh)
        p_min_w = max(float(probe.bus_charge_limit_w), -inherited_limit)
        p_max_w = min(float(probe.bus_discharge_limit_w), inherited_limit)

        # 2. Compute external PI command bounded by DC/DC bus-side limits.
        pi_output = self.dc_link_bess_pi.compute(
            vdc_v=vdc,
            xi_vdc_v_s=xi_bess_vdc_v_s,
            p_min_w=p_min_w,
            p_max_w=p_max_w,
            bess_enabled=True,
        )

        # 3. Solve exact 1RC + DC/DC power conversion at the requested bus power.
        dcdc = convert_power(
            parameters=self.dcdc_parameters,
            bus_power_request_w=pi_output.p_bess_ref_w,
            bus_voltage_v=vbus_eval,
            ocv_v=ocv_v,
            vrc_v=vrc,
            r0_ohm=r0_ohm,
            soc=soc,
            soc_min=self.bess.soc_min,
            soc_max=self.bess.soc_max,
            unit_discharge_available_a=i_unit_avail,
            unit_charge_available_a=i_unit_avail,
        )
        dcdc = replace(dcdc, bus_charge_limit_w=p_min_w, bus_discharge_limit_w=p_max_w)

        v_bank = float(self.dcdc_parameters.n_series * dcdc.unit_voltage_v)
        i_bank = float(self.dcdc_parameters.n_parallel * dcdc.unit_current_a)
        i_bus = float(dcdc.bus_power_w / vdc) if vdc > 0.0 else 0.0
        if dcdc.bus_power_w > 0.0 and dcdc.bank_power_w > 0.0:
            eta_inst = float(dcdc.bus_power_w / dcdc.bank_power_w)
        elif dcdc.bus_power_w < 0.0 and dcdc.bus_power_w != 0.0:
            eta_inst = float(dcdc.bank_power_w / dcdc.bus_power_w)
        else:
            eta_inst = 1.0

        return CoupledDCDCState(
            pi_output=pi_output,
            dcdc_result=dcdc,
            v_bank_v=v_bank,
            i_bank_a=i_bank,
            i_bus_a=i_bus,
            p_bank_w=float(dcdc.bank_power_w),
            p_bus_w=float(dcdc.bus_power_w),
            p_loss_w=float(dcdc.loss_power_w),
            efficiency_instant=eta_inst,
        )

    def system_dynamics(self, t: float, x):
        """Return derivatives for the 16-state GFM+BESS+DC/DC architecture."""
        if len(x) != self.state_count_with_bess_pi:
            raise ValueError(
                "MicrogridWithBESSDCDC state must contain 16 values with "
                "xi_bess_vdc at x[15]."
            )

        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        controller_state = x[10]
        theta = x[11]
        soc_bess = x[12]
        vrc_bess = x[13]
        zdeg_bess = x[14]
        xi_bess_vdc = x[self.bess_pi_state_index]

        soh_bess = self._bess_soh(zdeg_bess)
        coupled = self._evaluate_dcdc_coupling(
            vdc_v=Vdc,
            soc_bess=soc_bess,
            vrc_bess=vrc_bess,
            soh_bess=soh_bess,
            xi_bess_vdc_v_s=xi_bess_vdc,
        )
        i_bus = coupled.i_bus_a
        i_unit = coupled.dcdc_result.unit_current_a
        p_bus = coupled.p_bus_w
        p_discharge_max_w = float(coupled.dcdc_result.bus_discharge_limit_w)
        i_bus_max_avail = (
            p_discharge_max_w / float(Vdc)
            if self.bess_enabled and Vdc > 0.0
            else 0.0
        )

        Ipv, load_t, control = self._compute_step_control(
            t,
            Vdc,
            i1,
            i2,
            controller_state,
            theta,
            vc=vc,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bus_max_avail,
            p_bess_dc_max_available=p_discharge_max_w,
            p_bess_dc_actual=p_bus,
        )
        di1dt, dvcdt, di2dt, v_pcc = self.plant.lcl_derivatives_with_rl_load(
            control.v_inv,
            i1,
            vc,
            i2,
            load_t,
        )
        dVdc = self.plant.dc_link_derivative(
            Ipv,
            control.idc_inv,
            i_bess=i_bus,
        )
        d_bess = self.bess.rhs(
            t=t,
            x=[soc_bess, vrc_bess, zdeg_bess],
            i_bess=i_unit,
            soh=soh_bess,
            capacity_snapshot=self._capacity_snapshot,
        )

        self._last_p_bridge = control.p_bridge
        control.p_pcc = float(np.dot(v_pcc, i2))
        self._last_p_pcc = control.p_pcc
        self._last_p_cmd = control.p_cmd
        self._last_m_ctrl = control.m_ctrl
        self._last_i_bess = i_unit
        self._last_soc_bess = soc_bess
        self._last_soh_bess = soh_bess
        self._last_vt_bess = coupled.dcdc_result.unit_voltage_v

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
            coupled.pi_output.d_xi_vdc_dt,
        ]

    def integrated_signals(self, t: float, x) -> dict[str, float | bool | str]:
        """Return plant, bank, DC/DC, bus, saturation, and anti-windup diagnostics."""
        if len(x) != self.state_count_with_bess_pi:
            raise ValueError(
                "MicrogridWithBESSDCDC state must contain 16 values with "
                "xi_bess_vdc at x[15]."
            )

        Vdc = x[0]
        i1 = np.array([x[1], x[2], x[3]])
        vc = np.array([x[4], x[5], x[6]])
        i2 = np.array([x[7], x[8], x[9]])
        controller_state = x[10]
        theta = x[11]
        soc_bess = x[12]
        vrc_bess = x[13]
        zdeg_bess = x[14]
        xi_bess_vdc = x[self.bess_pi_state_index]

        soh_bess = self._bess_soh(zdeg_bess)
        coupled = self._evaluate_dcdc_coupling(
            vdc_v=Vdc,
            soc_bess=soc_bess,
            vrc_bess=vrc_bess,
            soh_bess=soh_bess,
            xi_bess_vdc_v_s=xi_bess_vdc,
        )
        dcdc = coupled.dcdc_result
        pi_output = coupled.pi_output
        p_discharge_max_w = float(dcdc.bus_discharge_limit_w)
        p_charge_min_w = float(dcdc.bus_charge_limit_w)
        i_bus_max_avail = (
            p_discharge_max_w / float(Vdc)
            if self.bess_enabled and Vdc > 0.0
            else 0.0
        )

        _, load_t, control = self._compute_step_control(
            t,
            Vdc,
            i1,
            i2,
            controller_state,
            theta,
            vc=vc,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bus_max_avail,
            p_bess_dc_max_available=p_discharge_max_w,
            p_bess_dc_actual=coupled.p_bus_w,
        )
        _, _, _, v_pcc = self.plant.lcl_derivatives_with_rl_load(
            control.v_inv,
            i1,
            vc,
            i2,
            load_t,
        )
        p_load = float(np.dot(v_pcc, i2))

        return {
            "Vdc": float(Vdc),
            "p_inv_dc_w": float(control.idc_inv * Vdc),
            "p_bridge": float(control.p_bridge),
            "p_pcc": float(p_load),
            "p_load": p_load,
            # Legacy compatibility key (bus current) + explicit bank/bus separation
            "i_bess": float(coupled.i_bus_a),
            "p_bess_dc": float(coupled.p_bus_w),
            "i_bess_bus_a": float(coupled.i_bus_a),
            "i_bess_bank_a": float(coupled.i_bank_a),
            "i_bess_unit_a": float(dcdc.unit_current_a),
            "v_bess_unit_v": float(dcdc.unit_voltage_v),
            "v_bess_bank_v": float(coupled.v_bank_v),
            "p_bess_bank_w": float(coupled.p_bank_w),
            "p_bess_bus_w": float(coupled.p_bus_w),
            "p_dcdc_loss_w": float(coupled.p_loss_w),
            "dcdc_efficiency": float(coupled.efficiency_instant),
            "dcdc_saturated": bool(dcdc.saturated),
            "dcdc_protection_status": str(dcdc.protection_status),
            "p_bess_ref_unsat_w": float(pi_output.p_bess_ref_unsat_w),
            "p_bess_ref_w": float(pi_output.p_bess_ref_w),
            "p_bess_ref_min_w": p_charge_min_w,
            "p_bess_ref_max_w": p_discharge_max_w,
            "vdc_error_v": float(pi_output.vdc_error_v),
            "xi_bess_vdc_v_s": float(xi_bess_vdc),
            "d_xi_bess_vdc_dt": float(pi_output.d_xi_vdc_dt),
            "pi_saturated": bool(pi_output.saturated),
            "anti_windup_active": bool(pi_output.anti_windup_active),
            "bess_enabled": bool(self.bess_enabled),
            "bess_charge_available": bool(
                self.bess_enabled and soc_bess < self.bess.soc_max and p_charge_min_w < 0.0
            ),
            "bess_discharge_available": bool(
                self.bess_enabled and soc_bess > self.bess.soc_min and p_discharge_max_w > 0.0
            ),
            "p_bess_dc_max": float(self.dcdc_parameters.bus_power_max_w),
            "i_bess_max_available": float(i_bus_max_avail),
            "p_bess_dc_max_available": p_discharge_max_w,
            "soc_bess": float(soc_bess),
            "vt_bess": float(dcdc.unit_voltage_v),
            "soh_bess": float(soh_bess),
        }
