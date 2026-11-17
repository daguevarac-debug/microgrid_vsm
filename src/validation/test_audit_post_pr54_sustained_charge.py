"""Minimal sustained-charge dynamic verification for MicrogridWithBESSDCDC (post-PR #54 audit).

This standalone test complements the 13 scenarios in ``validate_bess_dcdc_50hz.py``
(which only cover sustained discharge or brief pre-step transient negative current)
by verifying sustained battery charging under a -40% load step (3000 W -> 1800 W) at 50 Hz.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import (  # noqa: E402
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from validation.validate_bess_dcdc_50hz import _build_dcdc_model  # noqa: E402


class TestSustainedChargePostPR54Audit(unittest.TestCase):
    def test_sustained_charge_load_drop_50hz_balances(self) -> None:
        t_step_s = 0.8
        t_end_s = 2.5
        p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
        p_post = 0.60 * p_pre  # -40% load step (3000 W -> 1800 W)
        eta_ch = 0.95
        soc0 = 0.60

        model = _build_dcdc_model(
            freq_hz=50.0,
            soc_initial=soc0,
            eta_discharge=0.95,
            eta_charge=eta_ch,
            bess_enabled=True,
            load_profile=lambda t: p_pre if t < t_step_s else p_post,
        )
        x0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)

        t_grid = np.linspace(0.0, t_end_s, int(round(t_end_s / 5e-4)) + 1)
        sol_dense = solve_ivp(
            model.system_dynamics,
            (0.0, t_end_s),
            x0,
            method="RK45",
            max_step=5e-5,
            rtol=1e-6,
            atol=1e-8,
            t_eval=t_grid,
        )
        self.assertTrue(sol_dense.success, msg=sol_dense.message)

        n = len(t_grid)
        i_bank = np.empty(n)
        i_bus = np.empty(n)
        i_unit = np.empty(n)
        p_bank = np.empty(n)
        p_bus = np.empty(n)
        p_loss = np.empty(n)
        p_pv = np.empty(n)
        p_inv_dc = np.empty(n)

        for k, tk in enumerate(t_grid):
            sig = model.integrated_signals(float(tk), sol_dense.y[:, k])
            i_bank[k] = float(sig["i_bess_bank_a"])
            i_bus[k] = float(sig["i_bess_bus_a"])
            i_unit[k] = float(sig["i_bess_unit_a"])
            p_bank[k] = float(sig["p_bess_bank_w"])
            p_bus[k] = float(sig["p_bess_bus_w"])
            p_loss[k] = float(sig["p_dcdc_loss_w"])
            vdc_k = float(sol_dense.y[0, k])
            g_t = float(model.irradiance_profile(float(tk)))
            t_c = float(model.temperature_profile(float(tk)))
            p_pv[k] = vdc_k * float(model.plant.pv_current(max(vdc_k, 0.0), g_t, t_c))
            p_inv_dc[k] = float(sig["p_inv_dc_w"])

        ss = (t_grid >= 1.5) & (t_grid <= t_end_s)
        post = t_grid >= t_step_s

        # 1. Sustained charging currents and power in steady-state window
        self.assertLess(float(np.mean(i_bank[ss])), -1.0)
        self.assertLess(float(np.mean(i_bus[ss])), -1.0)
        self.assertLess(float(np.mean(p_bank[ss])), -100.0)
        self.assertLess(float(np.mean(p_bus[ss])), -100.0)
        self.assertGreater(float(np.mean(p_loss[ss])), 0.0)
        self.assertAlmostEqual(
            float(np.mean(p_bank[ss])) / float(np.mean(p_bus[ss])),
            eta_ch,
            places=6,
        )

        # 2. Net SoC increase and Coulomb counting consistency
        soc_arr = sol_dense.y[12]
        soh_arr = np.array([model._bess_soh(float(z)) for z in sol_dense.y[14]])
        q_eff_arr = model.bess.q_nom_ah * soh_arr
        soc_post0 = float(soc_arr[post][0])
        soc_final = float(soc_arr[-1])
        self.assertGreater(soc_final, soc0)
        self.assertGreater(soc_final, soc_post0)

        dsoc_ode = soc_final - soc_post0
        dsoc_int = float(np.trapezoid(-i_unit[post] / (3600.0 * q_eff_arr[post]), t_grid[post]))
        self.assertLess(abs(dsoc_ode - dsoc_int), 1e-7)

        # 3. DC/DC converter and DC-bus energy balances
        e_bank = float(np.trapezoid(p_bank[post], t_grid[post]))
        e_bus = float(np.trapezoid(p_bus[post], t_grid[post]))
        e_loss = float(np.trapezoid(p_loss[post], t_grid[post]))
        self.assertLess(abs(e_bank - e_bus - e_loss), 1e-9)

        vdc_post = sol_dense.y[0, post]
        de_cdc = 0.5 * model.plant.dcp.Cdc * float(vdc_post[-1] ** 2 - vdc_post[0] ** 2)
        e_cdc_net = float(np.trapezoid(p_pv[post] + p_bus[post] - p_inv_dc[post], t_grid[post]))
        self.assertLess(abs(de_cdc - e_cdc_net), 0.1)


if __name__ == "__main__":
    unittest.main()
