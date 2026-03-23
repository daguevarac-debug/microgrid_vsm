"""Scaffold-only placeholder for future grid-forming VSG control."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from controllers.base import ControlOutput, InverterControllerBase

if TYPE_CHECKING:
    from microgrid import HardwarePlant


class GridFormingVSGController(InverterControllerBase):
    """Scaffold placeholder for future VSG controller (not active in baseline)."""

    def __init__(self):
        pass

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
        del t, theta, xi_vdc, vdc_eff, v_pcc, i1, i2, plant, ipv
        raise NotImplementedError("GridFormingVSGController is scaffold-only in baseline mode.")
