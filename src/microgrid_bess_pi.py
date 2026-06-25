"""Explicit GFM/BESS architecture with external DC-link PI regulation.

The PI power reference is limited by the existing BESS current, power, SoC and
SoH constraints before conversion to DC current. Conditional anti-windup is
implemented in ``DCLinkBESSPIController``. The VSG equations and parameters are
not modified.

State mapping:

    [Vdc, i1abc, vcabc, i2abc, controller_state, theta,
     soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]

The first 15 states preserve ``MicrogridWithBESS`` exactly; the external PI
integral is appended at x[15] and integrated by the same global solver.
"""

from __future__ import annotations

import numpy as np

from controllers.dc_link_bess_pi import DCLinkBESSPIController, DCLinkBESSPIOutput
from microgrid import MicrogridWithBESS, _finite_float


class MicrogridWithBESSPI(MicrogridWithBESS):
    """Microgrid+BESS model driven by a limited external DC-link PI."""

    bess_pi_state_index = 15
    state_count_with_bess_pi = 16

    def __init__(
        self,
        *,
        dc_link_bess_pi: DCLinkBESSPIController,
        bess_enabled: bool = True,
        **kwargs,
    ) -> None:
        if not isinstance(dc_link_bess_pi, DCLinkBESSPIController):
            raise ValueError(
                "dc_link_bess_pi must be DCLinkBESSPIController, got "
                f"{type(dc_link_bess_pi).__name__}."
            )
        if not isinstance(bess_enabled, bool):
            raise ValueError(f"bess_enabled must be bool, got {bess_enabled!r}.")
        super().__init__(**kwargs)
        self.dc_link_bess_pi = dc_link_bess_pi
        self.bess_enabled = bess_enabled

    def set_bess_enabled(self, enabled: bool) -> None:
        """Enable or disable all BESS charge/discharge commands explicitly."""
        if not isinstance(enabled, bool):
            raise ValueError(f"enabled must be bool, got {enabled!r}.")
        self.bess_enabled = enabled

    def initial_state_with_bess(
        self,
        vdc0: float = 340.0,
        *,
        xi_bess_vdc0_v_s: float = 0.0,
    ) -> list[float]:
        """Return the protected 15-state vector plus the external PI integral."""
        xi0 = _finite_float("xi_bess_vdc0_v_s", xi_bess_vdc0_v_s)
        return super().initial_state_with_bess(vdc0=vdc0) + [xi0]

    def _operating_power_limits(
        self,
        *,
        vdc_v: float,
        soc_bess: float,
        soh_bess: float,
    ) -> tuple[float, float, bool, bool]:
        """Return signed charge/discharge limits from existing BESS constraints."""
        vdc = _finite_float("vdc_v", vdc_v)
        soc = _finite_float("soc_bess", soc_bess)
        soh = _finite_float("soh_bess", soh_bess)
        if soc < 0.0 or soc > 1.0:
            raise ValueError(f"soc_bess must be within [0, 1], got {soc!r}.")
        if soh < 0.0 or soh > 1.0:
            raise ValueError(f"soh_bess must be within [0, 1], got {soh!r}.")

        effective_enabled = bool(self.bess_enabled and vdc > 0.0)
        if not effective_enabled:
            return 0.0, 0.0, False, False

        i_limit_available = self._available_i_bess_max(soh)
        p_limit_from_current = max(vdc, 0.0) * i_limit_available
        p_limit_available = min(
            self._available_p_bess_max_w(soh),
            p_limit_from_current,
        )
        p_limit_available = max(float(p_limit_available), 0.0)

        discharge_available = bool(
            soc > self.bess.soc_min and p_limit_available > 0.0
        )
        charge_available = bool(
            soc < self.bess.soc_max and p_limit_available > 0.0
        )
        p_min_w = -p_limit_available if charge_available else 0.0
        p_max_w = p_limit_available if discharge_available else 0.0
        return p_min_w, p_max_w, charge_available, discharge_available

    def _compute_pi_bess_command(
        self,
        *,
        vdc_v: float,
        soc_bess: float,
        soh_bess: float,
        xi_bess_vdc_v_s: float,
    ) -> tuple[DCLinkBESSPIOutput, float]:
        """Limit the PI power request and convert it to signed BESS current."""
        vdc = _finite_float("vdc_v", vdc_v)
        soc = _finite_float("soc_bess", soc_bess)
        soh = _finite_float("soh_bess", soh_bess)
        p_min_w, p_max_w, _, _ = self._operating_power_limits(
            vdc_v=vdc,
            soc_bess=soc,
            soh_bess=soh,
        )
        effective_enabled = bool(self.bess_enabled and vdc > 0.0)
        pi_output = self.dc_link_bess_pi.compute(
            vdc_v=vdc,
            xi_vdc_v_s=xi_bess_vdc_v_s,
            p_min_w=p_min_w,
            p_max_w=p_max_w,
            bess_enabled=effective_enabled,
        )

        if not effective_enabled:
            return pi_output, 0.0

        voltage_for_conversion = max(vdc, self.plant.dcp.Vmin)
        i_bess = pi_output.p_bess_ref_w / voltage_for_conversion

        # Numerical safety: reapply the same mandatory current and power limits.
        i_limit_available = self._available_i_bess_max(soh)
        p_limit_available = self._available_p_bess_max_w(soh)
        i_power_limit = p_limit_available / voltage_for_conversion
        i_limit = min(i_limit_available, i_power_limit)
        i_bess = float(np.clip(i_bess, -i_limit, i_limit))

        if soc <= self.bess.soc_min and i_bess > 0.0:
            i_bess = 0.0
        if soc >= self.bess.soc_max and i_bess < 0.0:
            i_bess = 0.0
        return pi_output, i_bess

    def system_dynamics(self, t: float, x):
        """Return derivatives for the explicit 16-state PI+BESS architecture."""
        if len(x) != self.state_count_with_bess_pi:
            raise ValueError(
                "MicrogridWithBESSPI state must contain 16 values with "
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

        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess_max_available = self._available_i_bess_max(soh_bess)
        pi_output, i_bess = self._compute_pi_bess_command(
            vdc_v=Vdc,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            xi_bess_vdc_v_s=xi_bess_vdc,
        )
        p_bess_dc_actual = float(Vdc) * float(i_bess)
        _, p_discharge_max_w, _, _ = self._operating_power_limits(
            vdc_v=Vdc,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
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
            i_bess_max_available=(
                i_bess_max_available if self.bess_enabled else 0.0
            ),
            p_bess_dc_max_available=p_discharge_max_w,
            p_bess_dc_actual=p_bess_dc_actual,
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
            i_bess=i_bess,
        )
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
            pi_output.d_xi_vdc_dt,
        ]

    def integrated_signals(self, t: float, x) -> dict[str, float | bool]:
        """Return plant, BESS, saturation and anti-windup diagnostics."""
        if len(x) != self.state_count_with_bess_pi:
            raise ValueError(
                "MicrogridWithBESSPI state must contain 16 values with "
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

        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess_max_available = self._available_i_bess_max(soh_bess)
        p_min_w, p_max_w, charge_available, discharge_available = (
            self._operating_power_limits(
                vdc_v=Vdc,
                soc_bess=soc_bess,
                soh_bess=soh_bess,
            )
        )
        pi_output, i_bess = self._compute_pi_bess_command(
            vdc_v=Vdc,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            xi_bess_vdc_v_s=xi_bess_vdc,
        )
        p_bess_dc_actual = float(Vdc) * float(i_bess)
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
            i_bess_max_available=(
                i_bess_max_available if self.bess_enabled else 0.0
            ),
            p_bess_dc_max_available=p_max_w,
            p_bess_dc_actual=p_bess_dc_actual,
        )
        _, _, _, v_pcc = self.plant.lcl_derivatives_with_rl_load(
            control.v_inv,
            i1,
            vc,
            i2,
            load_t,
        )
        p_load = float(np.dot(v_pcc, i2))
        vt_bess = self.bess.terminal_voltage(
            soc=soc_bess,
            v_rc=vrc_bess,
            i_bess=i_bess,
            soh=soh_bess,
        )

        return {
            "Vdc": float(Vdc),
            "p_bridge": float(control.p_bridge),
            "p_pcc": float(p_load),
            "p_load": p_load,
            "i_bess": float(i_bess),
            "p_bess_dc": p_bess_dc_actual,
            "p_bess_ref_unsat_w": float(pi_output.p_bess_ref_unsat_w),
            "p_bess_ref_w": float(pi_output.p_bess_ref_w),
            "p_bess_ref_min_w": float(p_min_w),
            "p_bess_ref_max_w": float(p_max_w),
            "vdc_error_v": float(pi_output.vdc_error_v),
            "xi_bess_vdc_v_s": float(xi_bess_vdc),
            "d_xi_bess_vdc_dt": float(pi_output.d_xi_vdc_dt),
            "pi_saturated": bool(pi_output.saturated),
            "anti_windup_active": bool(pi_output.anti_windup_active),
            "bess_enabled": bool(self.bess_enabled),
            "bess_charge_available": bool(charge_available),
            "bess_discharge_available": bool(discharge_available),
            "p_bess_dc_max": float(self.p_bess_max_w),
            "i_bess_max_available": float(i_bess_max_available),
            "p_bess_dc_max_available": float(p_max_w),
            "soc_bess": float(soc_bess),
            "vt_bess": float(vt_bess),
            "soh_bess": float(soh_bess),
        }
