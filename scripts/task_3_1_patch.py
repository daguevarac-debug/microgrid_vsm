from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected block not found in {path}:\n{old}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/controllers/base.py",
    '''    @abstractmethod
    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
    ) -> ControlOutput:
        """Return control action and auxiliary powers for integration/postprocessing."""
''',
    '''    @abstractmethod
    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
        *,
        soc_bess: float | None = None,
        soh_bess: float | None = None,
        i_bess_max_available: float | None = None,
        p_bess_dc_max_available: float | None = None,
    ) -> ControlOutput:
        """Return control action and auxiliary powers for integration/postprocessing.

        BESS supervision inputs are optional for controller modes and plant
        configurations without storage. When storage is active, the four values
        must be supplied together by ``MicrogridWithBESS``.
        """
''',
)

replace_once(
    "src/controllers/grid_following.py",
    '''    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
    ) -> ControlOutput:
        del t
''',
    '''    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
        *,
        soc_bess: float | None = None,
        soh_bess: float | None = None,
        i_bess_max_available: float | None = None,
        p_bess_dc_max_available: float | None = None,
    ) -> ControlOutput:
        del t, soc_bess, soh_bess, i_bess_max_available, p_bess_dc_max_available
''',
)

replace_once(
    "src/controllers/gfm_controller.py",
    '''def _phase_vector(name: str, value) -> np.ndarray:
    out = np.asarray(value, dtype=float)
    if out.shape != (3,) or not np.isfinite(out).all():
        raise ValueError(f"{name} must be a finite 3-element vector, got shape {out.shape}.")
    return out


class GFMController(InverterControllerBase):
''',
    '''def _phase_vector(name: str, value) -> np.ndarray:
    out = np.asarray(value, dtype=float)
    if out.shape != (3,) or not np.isfinite(out).all():
        raise ValueError(f"{name} must be a finite 3-element vector, got shape {out.shape}.")
    return out


def _validate_bess_supervision_inputs(
    soc_bess: float | None,
    soh_bess: float | None,
    i_bess_max_available: float | None,
    p_bess_dc_max_available: float | None,
) -> None:
    """Validate the optional BESS/BMS interface without applying limits yet."""
    values = {
        "soc_bess": soc_bess,
        "soh_bess": soh_bess,
        "i_bess_max_available": i_bess_max_available,
        "p_bess_dc_max_available": p_bess_dc_max_available,
    }
    if all(value is None for value in values.values()):
        return

    missing = [name for name, value in values.items() if value is None]
    if missing:
        raise ValueError(
            "BESS supervision inputs must be provided together; missing: "
            + ", ".join(missing)
            + "."
        )

    soc = _finite_float("GFMController.soc_bess", soc_bess)
    soh = _finite_float("GFMController.soh_bess", soh_bess)
    if not 0.0 <= soc <= 1.0:
        raise ValueError(f"GFMController.soc_bess must be within [0, 1], got {soc}.")
    if not 0.0 <= soh <= 1.0:
        raise ValueError(f"GFMController.soh_bess must be within [0, 1], got {soh}.")
    _nonnegative_float("GFMController.i_bess_max_available", i_bess_max_available)
    _nonnegative_float("GFMController.p_bess_dc_max_available", p_bess_dc_max_available)


class GFMController(InverterControllerBase):
''',
)

replace_once(
    "src/controllers/gfm_controller.py",
    '''    The supplied ``v_pcc`` must be the complete R-L PCC voltage when the class
    is fully integrated. The legacy resistive approximation is not sufficient
    for the final GFM active-power feedback.
    """
''',
    '''    The supplied ``v_pcc`` must be the complete R-L PCC voltage when the class
    is fully integrated. The legacy resistive approximation is not sufficient
    for the final GFM active-power feedback.

    The optional BESS supervision values are transported through this interface
    for Activity 2.2. This subtask validates their contract but deliberately does
    not yet use them to modify ``p_ref_eff``.
    """
''',
)

replace_once(
    "src/controllers/gfm_controller.py",
    '''    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
    ) -> ControlOutput:
        """Return GFM voltage synthesis, power exchange and angular derivatives."""
''',
    '''    def compute_control(
        self,
        t: float,
        theta: float,
        xi_vdc: float,
        vdc_eff: float,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        i2: np.ndarray,
        plant: HardwarePlant,
        ipv: float,
        *,
        soc_bess: float | None = None,
        soh_bess: float | None = None,
        i_bess_max_available: float | None = None,
        p_bess_dc_max_available: float | None = None,
    ) -> ControlOutput:
        """Return GFM voltage synthesis, power exchange and angular derivatives."""
''',
)

replace_once(
    "src/controllers/gfm_controller.py",
    '''        v_pcc = _phase_vector("GFMController.v_pcc", v_pcc)
        i1 = _phase_vector("GFMController.i1", i1)
        i2 = _phase_vector("GFMController.i2", i2)

        p_available = max(vdc_eff * ipv * plant.eta, 0.0)
''',
    '''        v_pcc = _phase_vector("GFMController.v_pcc", v_pcc)
        i1 = _phase_vector("GFMController.i1", i1)
        i2 = _phase_vector("GFMController.i2", i2)
        _validate_bess_supervision_inputs(
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
        )

        p_available = max(vdc_eff * ipv * plant.eta, 0.0)
''',
)

replace_once(
    "src/microgrid.py",
    '''    def _compute_step_control(
        self,
        t: float,
        Vdc: float,
        i1: np.ndarray,
        i2: np.ndarray,
        controller_state: float,
        theta: float,
    ):
''',
    '''    def _compute_step_control(
        self,
        t: float,
        Vdc: float,
        i1: np.ndarray,
        i2: np.ndarray,
        controller_state: float,
        theta: float,
        *,
        soc_bess: float | None = None,
        soh_bess: float | None = None,
        i_bess_max_available: float | None = None,
        p_bess_dc_max_available: float | None = None,
    ):
''',
)

replace_once(
    "src/microgrid.py",
    '''            plant=self.plant,
            ipv=Ipv,
        )
''',
    '''            plant=self.plant,
            ipv=Ipv,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
        )
''',
)

replace_once(
    "src/microgrid.py",
    '''        Ipv, load_t, control = self._compute_step_control(
            t, Vdc, i1, i2, controller_state, theta
        )
        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess = self._compute_i_bess(Vdc=Vdc, soc_bess=soc_bess, soh_bess=soh_bess)
''',
    '''        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess_max_available = self._available_i_bess_max(soh_bess)
        p_bess_dc_max_available = self._available_p_bess_max_w(soh_bess)
        Ipv, load_t, control = self._compute_step_control(
            t,
            Vdc,
            i1,
            i2,
            controller_state,
            theta,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
        )
        i_bess = self._compute_i_bess(Vdc=Vdc, soc_bess=soc_bess, soh_bess=soh_bess)
''',
)

replace_once(
    "src/microgrid.py",
    '''        _, load_t, control = self._compute_step_control(
            t, Vdc, i1, i2, controller_state, theta
        )
        _, _, _, v_pcc = self.plant.lcl_derivatives_with_rl_load(control.v_inv, i1, vc, i2, load_t)
        control.p_pcc = float(np.dot(v_pcc, i2))
        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess = self._compute_i_bess(Vdc=Vdc, soc_bess=soc_bess, soh_bess=soh_bess)
''',
    '''        soh_bess = self.bess.soh_from_z_deg(zdeg_bess)
        i_bess_max_available = self._available_i_bess_max(soh_bess)
        p_bess_dc_max_available = self._available_p_bess_max_w(soh_bess)
        _, load_t, control = self._compute_step_control(
            t,
            Vdc,
            i1,
            i2,
            controller_state,
            theta,
            soc_bess=soc_bess,
            soh_bess=soh_bess,
            i_bess_max_available=i_bess_max_available,
            p_bess_dc_max_available=p_bess_dc_max_available,
        )
        _, _, _, v_pcc = self.plant.lcl_derivatives_with_rl_load(control.v_inv, i1, vc, i2, load_t)
        control.p_pcc = float(np.dot(v_pcc, i2))
        i_bess = self._compute_i_bess(Vdc=Vdc, soc_bess=soc_bess, soh_bess=soh_bess)
''',
)

replace_once(
    "src/microgrid.py",
    '''            "i_bess_max_available": float(self._available_i_bess_max(soh_bess)),
            "p_bess_dc_max_available": float(self._available_p_bess_max_w(soh_bess)),
''',
    '''            "i_bess_max_available": float(i_bess_max_available),
            "p_bess_dc_max_available": float(p_bess_dc_max_available),
''',
)

Path("src/validation/test_bess_controller_interface.py").write_text(
    '''from __future__ import annotations

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

    def compute_control(self, *args, **kwargs):
        self.last_bess_inputs = {
            "soc_bess": kwargs.get("soc_bess"),
            "soh_bess": kwargs.get("soh_bess"),
            "i_bess_max_available": kwargs.get("i_bess_max_available"),
            "p_bess_dc_max_available": kwargs.get("p_bess_dc_max_available"),
        }
        return super().compute_control(*args, **kwargs)


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
''',
    encoding="utf-8",
)
