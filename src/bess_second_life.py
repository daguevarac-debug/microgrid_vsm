"""Phase-1 baseline structures for second-life EV battery (BESS-SLB).

Scope of this module:
- Keep only static parameters needed to seed future BESS modeling.
- Do not integrate with microgrid/inverter yet.
- Do not implement full ECM dynamics yet.

Braco (2023) alignment in this phase:
- Uses second-life EV context (Nissan Leaf) and focuses on capacity and
  internal resistance as key characterization outputs.
- This file stores those outputs in a traceable, explicit structure.

Pending for later phases:
- OCV(SoC) map or fitted function.
- RC dynamic branch parameters (R1, C1, ...).
- Dynamic degradation / aging model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


def _ensure_positive(name: str, value: float) -> float:
    out = float(value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


def _ensure_fraction(name: str, value: float) -> float:
    out = float(value)
    if out < 0.0 or out > 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value!r}.")
    return out


@dataclass(frozen=True)
class SecondLifeBatteryPhase1:
    """Static second-life battery parameters for thesis Phase 1.

    Notes:
    - `nominal_capacity_ah` is the rated/new-reference capacity.
    - `soh_initial` is the starting SoH for repurposed operation.
    - `effective_capacity_ah` is derived as nominal_capacity_ah * soh_initial.
    - `internal_resistance_ohm` is the characterized internal resistance
      selected for baseline use (e.g., from Braco-style fast characterization).
    - This class does not implement OCV/RC dynamics.
    """

    nominal_capacity_ah: float
    soh_initial: float
    internal_resistance_ohm: float

    soc_initial: float = 0.5
    soc_min: float = 0.1
    soc_max: float = 0.9

    voltage_min_v: float | None = None
    voltage_max_v: float | None = None
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None

    chemistry: Literal["li_ion_second_life_ev"] = "li_ion_second_life_ev"
    source_reference: str = "Braco et al. (2023), Applied Energy"

    def __post_init__(self) -> None:
        nominal = _ensure_positive("nominal_capacity_ah", self.nominal_capacity_ah)
        soh = _ensure_fraction("soh_initial", self.soh_initial)
        resistance = _ensure_positive("internal_resistance_ohm", self.internal_resistance_ohm)
        soc0 = _ensure_fraction("soc_initial", self.soc_initial)
        soc_min = _ensure_fraction("soc_min", self.soc_min)
        soc_max = _ensure_fraction("soc_max", self.soc_max)

        if soc_min >= soc_max:
            raise ValueError(f"soc_min must be < soc_max, got {soc_min} and {soc_max}.")
        if soc0 < soc_min or soc0 > soc_max:
            raise ValueError(f"soc_initial={soc0} must be within [{soc_min}, {soc_max}].")

        if self.voltage_min_v is not None and self.voltage_max_v is not None:
            v_min = float(self.voltage_min_v)
            v_max = float(self.voltage_max_v)
            if v_min >= v_max:
                raise ValueError(f"voltage_min_v must be < voltage_max_v, got {v_min} and {v_max}.")

        if self.temperature_min_c is not None and self.temperature_max_c is not None:
            t_min = float(self.temperature_min_c)
            t_max = float(self.temperature_max_c)
            if t_min >= t_max:
                raise ValueError(
                    f"temperature_min_c must be < temperature_max_c, got {t_min} and {t_max}."
                )

        object.__setattr__(self, "nominal_capacity_ah", nominal)
        object.__setattr__(self, "soh_initial", soh)
        object.__setattr__(self, "internal_resistance_ohm", resistance)
        object.__setattr__(self, "soc_initial", soc0)
        object.__setattr__(self, "soc_min", soc_min)
        object.__setattr__(self, "soc_max", soc_max)

    @property
    def effective_capacity_ah(self) -> float:
        """Available capacity at initialization (Q_eff = Q_nom * SoH0)."""
        return self.nominal_capacity_ah * self.soh_initial

    @classmethod
    def from_characterization(
        cls,
        nominal_capacity_ah: float,
        measured_available_capacity_ah: float,
        internal_resistance_ohm: float,
        *,
        soc_initial: float = 0.5,
        soc_min: float = 0.1,
        soc_max: float = 0.9,
        voltage_min_v: float | None = None,
        voltage_max_v: float | None = None,
        temperature_min_c: float | None = None,
        temperature_max_c: float | None = None,
        source_reference: str = "Braco et al. (2023), Applied Energy",
    ) -> "SecondLifeBatteryPhase1":
        """Build the phase-1 object from characterization outputs."""
        nominal = _ensure_positive("nominal_capacity_ah", nominal_capacity_ah)
        available = _ensure_positive(
            "measured_available_capacity_ah", measured_available_capacity_ah
        )
        soh_initial = available / nominal
        return cls(
            nominal_capacity_ah=nominal,
            soh_initial=soh_initial,
            internal_resistance_ohm=internal_resistance_ohm,
            soc_initial=soc_initial,
            soc_min=soc_min,
            soc_max=soc_max,
            voltage_min_v=voltage_min_v,
            voltage_max_v=voltage_max_v,
            temperature_min_c=temperature_min_c,
            temperature_max_c=temperature_max_c,
            source_reference=source_reference,
        )

    def to_ecm_seed(self) -> "ECMSeedParameters":
        """Return base parameters ready to initialize a future ECM model."""
        return ECMSeedParameters(
            capacity_ah=self.effective_capacity_ah,
            r0_ohm=self.internal_resistance_ohm,
            soc_initial=self.soc_initial,
            soc_min=self.soc_min,
            soc_max=self.soc_max,
            ocv_soc_curve=None,
            rc_branch_params=None,
            dynamic_degradation_params=None,
        )


@dataclass(frozen=True)
class ECMSeedParameters:
    """Minimal seed for a later ECM implementation (not dynamic yet)."""

    capacity_ah: float
    r0_ohm: float
    soc_initial: float
    soc_min: float
    soc_max: float

    # Phase-2 placeholders:
    # - OCV(SoC): table, polynomial or other fitted relation.
    # - RC branch: e.g., {"r1_ohm": ..., "c1_f": ...}.
    # - Dynamic degradation: time/cycle dependent update law.
    ocv_soc_curve: object | None
    rc_branch_params: object | None
    dynamic_degradation_params: object | None
