from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController


class TestGFMController(unittest.TestCase):
    """Unit checks for the minimum GFM controller frequency response."""

    def setUp(self) -> None:
        self.plant = SimpleNamespace(
            eta=1.0,
            v_uvlo=100.0,
            dcp=SimpleNamespace(Vmin=1.0),
        )
        self.vdc_eff = 400.0
        self.ipv = 10.0
        self.i1 = np.zeros(3)

    @staticmethod
    def _pcc_vectors_for_power(power_w: float) -> tuple[np.ndarray, np.ndarray]:
        """Return finite phase vectors whose dot product equals power_w."""
        v_pcc = np.full(3, 100.0)
        i2 = np.full(3, power_w / 300.0)
        return v_pcc, i2

    def _compute_output(
        self,
        controller: GFMController,
        omega: float,
        p_e: float,
        *,
        bess_supervision: dict[str, float] | None = None,
    ):
        v_pcc, i2 = self._pcc_vectors_for_power(p_e)
        return controller.compute_control(
            t=0.0,
            theta=0.0,
            xi_vdc=omega,
            vdc_eff=self.vdc_eff,
            v_pcc=v_pcc,
            i1=self.i1,
            i2=i2,
            plant=self.plant,
            ipv=self.ipv,
            **(bess_supervision or {}),
        )

    @staticmethod
    def _bess_supervision(
        p_bess_dc_max_available: float,
        p_bess_dc_actual: float | None = None,
        soh_bess: float = 0.80,
    ) -> dict[str, float]:
        inputs = {
            "soc_bess": 0.60,
            "soh_bess": soh_bess,
            "i_bess_max_available": 20.0,
            "p_bess_dc_max_available": p_bess_dc_max_available,
        }
        if p_bess_dc_actual is not None:
            inputs["p_bess_dc_actual"] = p_bess_dc_actual
        return inputs

    def test_power_equilibrium_gives_zero_frequency_derivative(self) -> None:
        controller = GFMController(
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=1000.0,
        )

        self.assertAlmostEqual(output.p_pcc, 1000.0)
        self.assertAlmostEqual(output.p_cmd, 1000.0)
        self.assertAlmostEqual(output.d_xi_vdc_dt, 0.0)

    def test_excess_electrical_power_causes_frequency_drop(self) -> None:
        controller = GFMController(
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=1200.0,
        )

        self.assertLess(output.d_xi_vdc_dt, 0.0)

    def test_positive_damping_recovers_frequency_below_reference(self) -> None:
        controller = GFMController(
            p_ref=1000.0,
            inertia_m=2.0,
            damping_d=5.0,
        )
        omega = controller.omega_ref - 1.0

        output = self._compute_output(
            controller=controller,
            omega=omega,
            p_e=1000.0,
        )

        expected_domega_dt = controller.frequency_dynamics.damping_d / controller.frequency_dynamics.inertia_m
        self.assertGreater(output.d_xi_vdc_dt, 0.0)
        self.assertAlmostEqual(output.d_xi_vdc_dt, expected_domega_dt)

    def test_without_bess_reference_is_limited_to_available_pv_power(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=5000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
        )

        self.assertAlmostEqual(output.p_cmd, 3600.0)

    def test_bess_dc_limit_is_converted_to_ac_and_added_to_pv(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=5000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=1000.0,
                p_bess_dc_actual=1000.0,
            ),
        )

        self.assertAlmostEqual(output.p_cmd, 4500.0)

    def test_nominal_reference_remains_upper_bound_with_bess(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=4000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=1000.0,
                p_bess_dc_actual=1000.0,
            ),
        )

        self.assertAlmostEqual(output.p_cmd, 4000.0)

    def test_soh_degrades_support_power_without_changing_inertia(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(
            p_ref=5000.0,
            inertia_m=2.0,
        )

        high_soh_output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=1000.0,
                p_bess_dc_actual=1000.0,
                soh_bess=1.0,
            ),
        )
        low_soh_output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=500.0,
                p_bess_dc_actual=1000.0,
                soh_bess=0.5,
            ),
        )

        self.assertAlmostEqual(high_soh_output.p_cmd, 4500.0)
        self.assertAlmostEqual(low_soh_output.p_cmd, 4050.0)
        self.assertLess(low_soh_output.p_cmd, high_soh_output.p_cmd)
        self.assertAlmostEqual(
            controller.frequency_dynamics.inertia_m,
            2.0,
        )

    def test_zero_bess_power_limit_matches_pv_only_case(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=5000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(0.0),
        )

        self.assertAlmostEqual(output.p_cmd, 3600.0)

    def test_signed_bess_charge_reduces_net_available_power(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=5000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=1000.0,
                p_bess_dc_actual=-500.0,
            ),
        )

        self.assertAlmostEqual(output.p_cmd, 3150.0)

    def test_positive_bess_discharge_is_limited_by_bms_power(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=5000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=1000.0,
                p_bess_dc_actual=1500.0,
            ),
        )

        self.assertAlmostEqual(output.p_cmd, 4500.0)

    def test_zero_signed_bess_power_matches_pv_only_case(self) -> None:
        self.plant.eta = 0.90
        controller = GFMController(p_ref=5000.0)

        output = self._compute_output(
            controller=controller,
            omega=controller.omega_ref,
            p_e=0.0,
            bess_supervision=self._bess_supervision(
                p_bess_dc_max_available=1000.0,
                p_bess_dc_actual=0.0,
            ),
        )

        self.assertAlmostEqual(output.p_cmd, 3600.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
