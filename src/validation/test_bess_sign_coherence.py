from __future__ import annotations

import sys
import unittest
import warnings
from pathlib import Path

import numpy as np

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS


class TestBESSSignCoherence(unittest.TestCase):
    """Verify the BESS sign convention through the GFM support path."""

    def setUp(self) -> None:
        controller = GFMController(
            p_ref=1e9,
            inertia_m=2.0,
            damping_d=5.0,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            self.model = MicrogridWithBESS(controller=controller)

    def test_additional_gfm_power_request_preserves_discharge_sign(self) -> None:
        model = self.model
        vdc = model.vdc_ref - 1.0
        x = model.initial_state_with_bess(vdc0=vdc)

        i1 = np.zeros(3)
        i2 = np.zeros(3)
        controller_state = x[10]
        theta = x[11]
        soc_bess = x[12]
        vrc_bess = x[13]
        zdeg_bess = x[14]

        soh_bess = model.bess.soh_from_z_deg(zdeg_bess)
        i_bess_max_available = model._available_i_bess_max(soh_bess)
        p_bess_dc_max_available = model._available_p_bess_support_w(
            soc_bess=soc_bess,
            soh_bess=soh_bess,
        )

        ipv, _, control = model._compute_step_control(
            t=0.0,
            Vdc=vdc,
            i1=i1,
            i2=i2,
            controller_state=controller_state,
            theta=theta,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
        )

        p_pv_ac_available = max(vdc * ipv * model.plant.eta, 0.0)
        i_bess = model._compute_i_bess(
            Vdc=vdc,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
        )
        p_bess_dc = vdc * i_bess

        d_bess = model.bess.rhs(
            t=0.0,
            x=[soc_bess, vrc_bess, zdeg_bess],
            i_bess=i_bess,
            soh=model.bess.soh_init_case,
        )

        dvdc_without_bess = model.plant.dc_link_derivative(
            ipv=ipv,
            idc_inv=control.idc_inv,
            i_bess=0.0,
        )
        dvdc_with_bess = model.plant.dc_link_derivative(
            ipv=ipv,
            idc_inv=control.idc_inv,
            i_bess=i_bess,
        )

        self.assertGreater(control.p_cmd, p_pv_ac_available)
        self.assertGreater(i_bess, 0.0)
        self.assertGreater(p_bess_dc, 0.0)
        self.assertLess(d_bess[0], 0.0)
        self.assertGreater(dvdc_with_bess, dvdc_without_bess)


if __name__ == "__main__":
    unittest.main(verbosity=2)
