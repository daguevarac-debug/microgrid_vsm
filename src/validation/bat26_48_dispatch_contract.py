"""BAT26-48 — read-only, pre-optimization contract for battery aging.

This file DOES NOT optimize dispatch, calibrate degradation, or convert a
2p-cell current/capacity into 340-V DC-bus power. Values are explicitly
battery-port quantities. No physical plant or BLAST code is modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal


DefEvidence = Literal["synthetic_blast", "illustrative"]


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a real finite number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class AgingBoundary:
    """Frozen 2p capacity snapshot and SoC for a single scheduling boundary.

    Q_eff = Q_init_case * q_retention. SoH = Q_eff / Q_nom_ref.
    The initial second-life loss is already in Q_init_case; never multiply by
    BLAST qNew(0)=0.7 or by an additional SoH factor.
    """

    q_nom_ref_ah: float
    q_init_case_ah: float
    retention_since_case_start: float
    soc: float
    soc_min: float = 0.10
    soc_max: float = 0.90
    soh_min: float = 0.50
    evidence: DefEvidence = "synthetic_blast"

    def __post_init__(self) -> None:
        for field in ("q_nom_ref_ah", "q_init_case_ah", "retention_since_case_start",
                      "soc", "soc_min", "soc_max", "soh_min"):
            _finite(field, getattr(self, field))
        if not (0 < self.q_init_case_ah <= self.q_nom_ref_ah):
            raise ValueError("initial second-life capacity out of range")
        if not (0 < self.retention_since_case_start <= 1):
            raise ValueError("retention must lie in (0,1] and cannot increase in this model")
        if not (0 <= self.soc_min < self.soc_max <= 1):
            raise ValueError("invalid operational SoC range")
        if not (0 <= self.soh_min <= 1):
            raise ValueError("invalid SoH floor")
        if not (self.soc_min <= self.soc <= self.soc_max):
            raise ValueError("initial SoC is outside allowed range")
        if self.soh + 1e-12 < self.soh_min:
            raise ValueError("SoH is below operational floor")
        if self.evidence not in ("synthetic_blast", "illustrative"):
            raise ValueError("unsupported evidence claim; measurements require separate validation")

    @property
    def q_eff_ah(self) -> float:
        return self.q_init_case_ah * self.retention_since_case_start

    @property
    def soh(self) -> float:
        return self.q_eff_ah / self.q_nom_ref_ah

    @property
    def dischargeable_charge_ah(self) -> float:
        """Charge in Ah to SoC floor, not energy in Wh or kWh."""
        return (self.soc - self.soc_min) * self.q_eff_ah

    @property
    def chargeable_charge_ah(self) -> float:
        return (self.soc_max - self.soc) * self.q_eff_ah

    def soc_after_port_current(self, *, battery_port_current_a: float,
                               duration_s: float) -> float:
        """Coulomb counting with Q frozen at boundary; positive I discharges.

        Reject steps exceeding SoC limits rather than silently clipping.
        Does NOT apply BLAST updates during the fast step.
        """
        current = _finite("battery_port_current_a", battery_port_current_a)
        duration = _finite("duration_s", duration_s)
        if duration <= 0:
            raise ValueError("time step must be positive")
        next_soc = self.soc - current * duration / (3600 * self.q_eff_ah)
        if next_soc < self.soc_min - 1e-12 or next_soc > self.soc_max + 1e-12:
            raise ValueError("requested current violates the SoC boundary")
        return next_soc

    def to_dispatch_boundary(self) -> dict[str, float | str | None]:
        """Versioned interface: power/energy at DC bus deliberately unavailable."""
        return {
            "schema": "BAT26-48/2p-readonly-v1",
            "evidence": self.evidence,
            "q_nom_ref_ah": self.q_nom_ref_ah,
            "q_init_case_ah": self.q_init_case_ah,
            "retention_since_case_start": self.retention_since_case_start,
            "q_eff_ah": self.q_eff_ah,
            "soh": self.soh,
            "soc": self.soc,
            "soc_min": self.soc_min,
            "soc_max": self.soc_max,
            "soh_min": self.soh_min,
            "dischargeable_charge_ah": self.dischargeable_charge_ah,
            "chargeable_charge_ah": self.chargeable_charge_ah,
            "battery_port_i_max_a": None,
            "dc_bus_p_dis_max_kw": None,
            "dc_bus_p_ch_max_kw": None,
            "energy_usable_at_bus_kwh": None,
            "dc_dc_efficiency": None,
            "dispatch_power_ready": "BLOCKED_DC_DC_TOPOLOGY_AND_RATINGS",
        }


@dataclass(frozen=True)
class EconomicScenario:
    """OPTIONAL scenario-only accounting, not a calibrated market price.

    C_wear = (asset_cost - salvage) * ΔQ / (Q_start - Q_EOL).
    This is an assumed linear cost-allocation proxy, not a BLAST law.
    """

    asset_cost_cop: float
    residual_value_cop: float
    q_case_initial_ah: float
    q_retirement_ah: float
    source_label: str = "HYPOTHETICAL_UNCALIBRATED"

    def __post_init__(self) -> None:
        for key in ("asset_cost_cop", "residual_value_cop", "q_case_initial_ah",
                    "q_retirement_ah"):
            _finite(key, getattr(self, key))
        if not (self.asset_cost_cop > 0 and 0 <= self.residual_value_cop < self.asset_cost_cop):
            raise ValueError("net economic cost must be strictly positive")
        if not (0 < self.q_retirement_ah < self.q_case_initial_ah):
            raise ValueError("retirement capacity must be below case initial capacity")
        if self.source_label != "HYPOTHETICAL_UNCALIBRATED":
            raise ValueError("do not claim measured/market-calibrated prices")

    @property
    def assumed_cop_per_lost_ah(self) -> float:
        return ((self.asset_cost_cop - self.residual_value_cop) /
                (self.q_case_initial_ah - self.q_retirement_ah))

    def cost_for_capacity_loss(self, *, q_before_ah: float,
                               q_after_ah: float) -> float:
        before = _finite("q_before_ah", q_before_ah)
        after = _finite("q_after_ah", q_after_ah)
        if not (self.q_retirement_ah <= after <= before <= self.q_case_initial_ah):
            raise ValueError("capacity transition outside the economic scenario")
        return (before - after) * self.assumed_cop_per_lost_ah


def nominal_efc_from_battery_port_throughput(*, throughput_ah: float,
                                             q_reference_ah: float) -> float:
    """Nominal EFC by absolute Ah, not BLAST's internally weighted EFC."""
    ah = _finite("throughput_ah", throughput_ah)
    q = _finite("q_reference_ah", q_reference_ah)
    if ah < 0 or q <= 0:
        raise ValueError("invalid EFC inputs")
    return ah / (2 * q)


def require_verified_dc_port_mapping(_: AgingBoundary) -> None:
    """Fail closed: topology, cell/bank mapping and efficiencies are missing."""
    raise NotImplementedError(
        "BAT26-48 only defines a 2p Ah/SoC contract; a validated DC/DC "
        "series-parallel topology and power/energy mapping are required "
        "before setting DC-bus or AC dispatch limits."
    )
