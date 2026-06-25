"""Explicit GFM/BESS architecture with an external DC-link PI regulator.

This module connects the unsaturated power reference produced by
``DCLinkBESSPIController`` to the BESS DC-current command while leaving the VSG
controller and its parameters unchanged.

State mapping when this explicit architecture is used:

    [Vdc, i1abc, vcabc, i2abc, controller_state, theta,
     soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]

The first 15 positions preserve ``MicrogridWithBESS`` exactly. The external PI
integral state is appended at x[15] and is integrated by the same global solver.
Anti-windup and explicit BESS enable/disable logic are intentionally deferred to
later Task 5.2 subtasks. Existing SoC, SoH, current and power limits remain in
force because they are mandatory plant-operation constraints.
"""

from __future__ import annotations

import numpy as np

from controllers.dc_link_bess_pi import DCLinkBESSPIController, DCLinkBESSPIOutput
from microgrid import MicrogridWithBESS, _finite_float


class MicrogridWithBESSPI(MicrogridWithBESS):
    """Microgrid+BESS model driven by an external DC-link PI power reference."""

    bess_pi_state_index = 15
    state_count_with_bess_pi = 16

    def __init__(self, *, dc_link_bess_pi: DCLinkBESSPIController, **kwargs) -> None:
        if not isinstance(dc_link_bess_pi, DCLinkBESSPIController):
            raise ValueError(
                "dc_link_bess_pi must be DCLinkBESSPIController, got "
                f"{type(dc_link_bess_pi).__name__}."
            )
        super().__init__(**kwargs)
        self.dc_link_bess_pi = dc_link_bess_pi

    def initial_state_with_bess(
        self,
        vdc0: float = 340.0,
        *,
        xi_bess_vdc0_v_s: float = 0.0,
    ) -> list[float]:
        """Return the protected 15-state vector plus the external PI integral."""
        xi0 = _finite_float("xi_bess_vdc0_v_s", xi_bess_vdc0_v_s)
        return super().initial_state_with_bess(vdc0=vdc0) + [xi0]

    def _compute_pi_bess_command(
        self,
        *,
        vdc_v: float,
        soc_bess: float,
        soh_bess: float,
        xi_bess_vdc_v_s: float,
    ) -> tuple[DCLinkBESSPIOutput, float]:
        """Convert PI power reference to BESS current using existing limits."""
        vdc = _finite_float("vdc_v", vdc_v)
        soc = _finite_float("soc_bess", soc_bess)
        soh = _finite_float("soh_bess", soh_bess)
        pi_output = self.dc_link_bess_pi.compute(
            vdc_v=vdc,
            xi_vdc_v_s=xi_bess_vdc_v_s,
        )

        if vdc <= 0.0:
            return pi_output, 0.0

        voltage_for_conversion = max(vdc, self.plant.dcp.Vmin)
        i_bess_cmd = pi_output.p_bess_ref_unsat_w / voltage_for_conversion

        i_limit_available = self._available_i_bess_max(soh)
        i_bess = float(np.clip(i_bess_cmd, -i_limit_available, i_limit_available))

        # Preserve the existing repository sign convention and SoC gates.
        if soc <= self.bess.soc_min and i_bess > 0.0:
            i_bess = 0.0
        if soc >= self.bess.soc_max and i_bess < 0.0:
            i_bess = 0.0

        p_limit_available = self._available_p_bess_max_w(soh)
        i_power_limit = p_limit_available / voltage_for_conversion
        i_bess = float(np.clip(i_bess, -i_power_limit, i_power_limit))
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
        p_bess_dc_max_available = self._available_p_bess_support_w(
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
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
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

    def integrated_signals(self, t: float, x) -> dict[str, float]:
        """Return base diagnostics plus the external PI command signals."""
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
        p_bess_dc_max_available = self._available_p_bess_support_w(
            soc_bess=soc_bess,
            soh_bess=soh_bess,
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
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
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
            "vdc_error_v": float(pi_output.vdc_error_v),
            "xi_bess_vdc_v_s": float(xi_bess_vdc),
            "p_bess_dc_max": float(self.p_bess_max_w),
            "i_bess_max_available": float(i_bess_max_available),
            "p_bess_dc_max_available": float(p_bess_dc_max_available),
            "soc_bess": float(soc_bess),
            "vt_bess": float(vt_bess),
            "soh_bess": float(soh_bess),
        }
