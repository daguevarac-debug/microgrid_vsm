from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController
from microgrid import Microgrid


class TestGFMPCCFeedback(unittest.TestCase):
    """Check that GFM swing dynamics receive the complete R-L PCC power."""

    def test_complete_rl_pcc_voltage_drives_frequency_derivative(self) -> None:
        controller = GFMController(
            p_ref=3000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )
        model = Microgrid(controller=controller)

        vdc = 340.0
        i1 = np.array([1.0, -0.5, -0.5])
        vc = np.array([120.0, -60.0, -60.0])
        i2 = np.array([2.0, -1.0, -1.0])
        omega = controller.omega_ref
        theta = 0.0

        _, load, control = model._compute_step_control(
            0.0,
            vdc,
            i1,
            vc,
            i2,
            omega,
            theta,
        )

        di2dt = (
            vc - (model.lcl.R2 + load.r_ohm) * i2
        ) / (model.lcl.L2 + load.l_h)
        v_pcc_complete = load.r_ohm * i2 + load.l_h * di2dt
        p_e_complete = float(np.dot(v_pcc_complete, i2))
        p_e_resistive_only = float(np.dot(load.r_ohm * i2, i2))

        expected_domega = (
            control.p_cmd
            - p_e_complete
            - controller.frequency_dynamics.damping_d
            * (omega - controller.omega_ref)
        ) / controller.frequency_dynamics.inertia_m

        self.assertNotAlmostEqual(p_e_complete, p_e_resistive_only)
        self.assertAlmostEqual(control.p_pcc, p_e_complete)
        self.assertAlmostEqual(control.d_xi_vdc_dt, expected_domega)


if __name__ == "__main__":
    unittest.main(verbosity=2)
