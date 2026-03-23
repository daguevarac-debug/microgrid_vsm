"""Controller interface for inverter control strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from microgrid import ControlOutput

if TYPE_CHECKING:
    from microgrid import HardwarePlant


class InverterControllerBase(ABC):
    """Interface for baseline inverter controllers."""

    @abstractmethod
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

