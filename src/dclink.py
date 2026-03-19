"""DC-link parameter container and load current helper functions."""

from dataclasses import dataclass

from config import DCLINK_VMIN_DEFAULT


@dataclass
class DCLinkParams:
    Cdc: float
    Vmin: float = DCLINK_VMIN_DEFAULT


def i_load_const_power(Vdc: float, P: float, Vmin: float = DCLINK_VMIN_DEFAULT) -> float:
    """Constant-power DC load: I = P / V."""
    Veff = max(Vdc, Vmin)
    return P / Veff


def i_load_resistor(Vdc: float, R: float) -> float:
    """Resistive DC load: I = V / R."""
    return Vdc / R
