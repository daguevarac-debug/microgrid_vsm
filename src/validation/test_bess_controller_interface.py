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


class RecordingGFMController(GFMController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_bess_inputs = None
        self.last_output = None

    def compute_control(self, *args, **kwargs):
        self.last_bess_inputs = {
            "soc_bess": kwargs.get("soc_bess"),
            "soh_bess": kwargs.get("soh_bess"),
            "i_bess_max_available": kwargs.get("i_bess_max_available"),
            "p_bess_dc_max_available": kwargs.get("p_bess_dc_max_available"),
        }
        self.last_output = super().compute_control(*args, **kwargs)
        return self.last_output


class TestBESSControllerInterface(unittest.TestCase):
    def test_microgrid_with_bess_passes_supervision_values_to_gfm(self) -> None:
        controller = RecordingGFMController(p_ref=0.0, inertia_m=2.0, damping_d=5.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            model = MicrogridWithBESS(controller=controller)

        x0 = model.initial_state_with_bess()
        derivatives = model.system_dynamics(t=0.0, x=x0)
        expected_soh = model.bess.soh_from_z_deg(x0[14])

        self.assertEqual(len(derivatives), 15)
        self.assertAlmostEqual(controller.last_bess_inputs["soc_bess"], x0[12])
        self.assertAlmostEqual(controller.last_bess_inputs["soh_bess"], expected_soh)
        self.assertAlmostEqual(
            controller.last_bess_inputs["i_bess_max_available"],
            model._available_i_bess_max(expected_soh),
        )
        self.assertAlmostEqual(
            controller.last_bess_inputs["p_bess_dc_max_available"],
            model._available_p_bess_max_w(expected_soh),
        )

    def test_soc_at_or_below_min_blocks_bess_support_power(self) -> None:
        controller = RecordingGFMController(p_ref=1000.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            model = MicrogridWithBESS(controller=controller)

        soc_min = model.bess.soc_min
        soh_bess = model.bess.soh_init_case

        blocked_soc_values = (
            soc_min,
            max(0.0, soc_min - 1e-6),
        )

        for soc_bess in blocked_soc_values:
            with self.subTest(soc_bess=soc_bess):
                self.assertAlmostEqual(
                    model._available_p_bess_support_w(
                        soc_bess=soc_bess,
                        soh_bess=soh_bess,
                    ),
                    0.0,
                )

        self.assertGreater(
            model._available_p_bess_support_w(
                soc_bess=soc_min + 1e-6,
                soh_bess=soh_bess,
            ),
            0.0,
        )

    def test_soc_min_blocks_bess_support_without_turning_off_inverter(self) -> None:
        controller = RecordingGFMController(
            p_ref=1e9,
            inertia_m=2.0,
            damping_d=5.0,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            model = MicrogridWithBESS(controller=controller)

        x0 = model.initial_state_with_bess()
        x0[12] = model.bess.soc_min

        derivatives = model.system_dynamics(t=0.0, x=x0)

        self.assertEqual(len(derivatives), 15)
        self.assertAlmostEqual(
            controller.last_bess_inputs["p_bess_dc_max_available"],
            0.0,
        )
        self.assertIsNotNone(controller.last_output)
        self.assertGreater(controller.last_output.m_ctrl, 0.0)
        self.assertGreater(np.linalg.norm(controller.last_output.v_inv), 0.0)
        self.assertGreater(controller.last_output.p_cmd, 0.0)

    def test_lower_soh_reduces_available_inertial_support_power(self) -> None:
        controller = RecordingGFMController(
            p_ref=1e9,
            inertia_m=2.0,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            model = MicrogridWithBESS(controller=controller)

        soc_bess = model.bess.soc_initial
        p_available_new = model._available_p_bess_support_w(
            soc_bess=soc_bess,
            soh_bess=1.0,
        )
        p_available_aged = model._available_p_bess_support_w(
            soc_bess=soc_bess,
            soh_bess=0.5,
        )

        self.assertGreater(p_available_new, p_available_aged)
        self.assertGreater(p_available_aged, 0.0)
        self.assertAlmostEqual(
            controller.frequency_dynamics.inertia_m,
            2.0,
        )

    def test_gfm_rejects_partial_bess_supervision_interface(self) -> None:
        controller = GFMController(p_ref=0.0)
        plant = type(
            "Plant",
            (),
            {"eta": 1.0, "v_uvlo": 100.0, "dcp": type("D", (), {"Vmin": 1.0})()},
        )()
        with self.assertRaisesRegex(ValueError, "must be provided together"):
            controller.compute_control(
                t=0.0,
                theta=0.0,
                xi_vdc=controller.omega_ref,
                vdc_eff=400.0,
                v_pcc=np.zeros(3),
                i1=np.zeros(3),
                i2=np.zeros(3),
                plant=plant,
                ipv=10.0,
                soc_bess=0.6,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
