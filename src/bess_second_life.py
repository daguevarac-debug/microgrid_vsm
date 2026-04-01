"""Second-life EV battery baseline + 1RC dynamic model for microgrid studies.

This module keeps compatibility with the original Phase-1 static structures and
adds a power-system oriented Thevenin 1RC dynamic model ready for solve_ivp.

Mathematical and bibliographic traceability notes (thesis transparency):

1) Terminal voltage equation used in code:
   V_t = OCV(SoC) - i_bess * R0 - V_rc
   - Literature status: consistent with Thevenin ECM terminal equation reported
     by Tran et al. (2021) in discrete-time formulation (Eq. (1)).
   - Implementation status here: same algebraic relation evaluated in continuous
     simulation (time-domain ODE integration framework).

2) RC branch dynamic equation used in code:
   dV_rc/dt = -V_rc / (R1 * C1) + i_bess / C1
   - Literature status: continuous-time form consistent with the discrete-time
     RC update reported by Tran et al. (2021) (Eq. (2)).
   - Implementation status here: explicit continuous-time ODE for solve_ivp.

3) SoC dynamic equation used in code:
   dSoC/dt = -i_bess / (3600 * Q_eff)
   - Literature status: standard coulomb-counting relation broadly used in BESS
     modeling; used here as synthesis for system-level simulation.

4) Effective capacity relation used in code:
   Q_eff = Q_nom * SoH
   - Literature status: direct consequence of SoH definition by remaining
     capacity; consistent with Braco and Tran framing.
   - Capacity convention used in this repository:
     Q_nom is the new/reference nominal capacity, while second-life available
     capacity at t=0 is Q_eff(0) = Q_nom * SoH_0.
     Example: Q_nom=66.0 Ah and SoH_0=44.1/66.0 imply Q_eff(0)≈44.1 Ah.

5) Degradation throughput state (implemented in Step-3 dynamic mode):
   dz_deg/dt = |i_bess|
   - Literature status: synthesis based on charge-throughput / equivalent-full-
     cycle concepts; not claimed as a textual equation copied from Braco.

6) Linear SoH fade law (implemented as first-order approximation):
   SoH = SoH_0 - k_deg * z_deg
   - Literature status: empirical law proposed for reduced-order studies,
     motivated by early-life near-linear trends reported by Braco.

7) R0 degradation law implemented in this module:
   R0 = R0_init * (1 + k_R * (1 - SoH))
   - Literature status: empirical simplified law proposed here; consistent with
     the observed aging trend (resistance increase as SoH decreases), but not a
     literal equation copied from Tran/Braco.

Important:
- Lookup arrays included here are explicit placeholders for integration and
  testing only. Replace them with identified/literature values before studies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from numbers import Real
from typing import Literal, Sequence

import numpy as np


def _ensure_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _ensure_positive(name: str, value: float) -> float:
    out = _ensure_finite(name, value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


def _ensure_fraction(name: str, value: float) -> float:
    out = _ensure_finite(name, value)
    if out < 0.0 or out > 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value!r}.")
    return out


def _ensure_real_array(name: str, data: Sequence[float]) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D sequence, got shape {arr.shape}.")
    if arr.size < 2:
        raise ValueError(f"{name} must contain at least 2 points, got {arr.size}.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values.")
    return arr


@dataclass(frozen=True)
class OCVR1C1LookupTable:
    """Lookup tables for 1RC parameters vs SoC (Tran, 2021 style source).

    Arrays are placeholders and must be replaced with identified data before
    reporting scientific results.
    """

    soc_data: Sequence[float]
    ocv_data: Sequence[float]
    r1_data: Sequence[float]
    c1_data: Sequence[float]
    source_reference: str = "Tran et al. (2021)"

    def __post_init__(self) -> None:
        soc = _ensure_real_array("soc_data", self.soc_data)
        ocv = _ensure_real_array("ocv_data", self.ocv_data)
        r1 = _ensure_real_array("r1_data", self.r1_data)
        c1 = _ensure_real_array("c1_data", self.c1_data)

        n = soc.size
        if ocv.size != n or r1.size != n or c1.size != n:
            raise ValueError(
                "ocv_data, r1_data and c1_data must match soc_data length "
                f"({n}), got ocv={ocv.size}, r1={r1.size}, c1={c1.size}."
            )

        if np.any(np.diff(soc) <= 0.0):
            raise ValueError("soc_data must be strictly increasing (monotonic).")
        if soc[0] < 0.0 or soc[-1] > 1.0:
            raise ValueError(
                f"soc_data must stay within [0, 1], got min={soc[0]} and max={soc[-1]}."
            )

        if np.any(r1 <= 0.0):
            raise ValueError("r1_data must be > 0 for all SoC points.")
        if np.any(c1 <= 0.0):
            raise ValueError("c1_data must be > 0 for all SoC points.")

        object.__setattr__(self, "soc_data", soc)
        object.__setattr__(self, "ocv_data", ocv)
        object.__setattr__(self, "r1_data", r1)
        object.__setattr__(self, "c1_data", c1)


# Placeholder lookup table for integration tests and scaffold wiring only.
# Replace these arrays with identified values from literature/experiments.
DEFAULT_TRAN_LOOKUP_TABLE = OCVR1C1LookupTable(
    soc_data=[0.0, 0.25, 0.5, 0.75, 1.0],
    ocv_data=[3.0, 3.2, 3.4, 3.6, 3.8],
    r1_data=[0.02, 0.018, 0.016, 0.017, 0.019],
    c1_data=[1800.0, 2200.0, 2600.0, 2300.0, 2000.0],
)


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

    def to_ecm_seed(
        self, lookup_table_1rc: OCVR1C1LookupTable | None = None
    ) -> "ECMSeedParameters":
        """Return base parameters ready to initialize a 1RC ECM model.

        Compatibility note:
        - Existing calls without arguments still work.
        - Optional lookup table wires OCV/R1/C1 maps when available.
        """
        return ECMSeedParameters(
            capacity_ah=self.effective_capacity_ah,
            r0_ohm=self.internal_resistance_ohm,
            soc_initial=self.soc_initial,
            soc_min=self.soc_min,
            soc_max=self.soc_max,
            ocv_soc_curve=lookup_table_1rc.ocv_data if lookup_table_1rc else None,
            rc_branch_params=(
                {
                    "soc_data": lookup_table_1rc.soc_data,
                    "r1_data": lookup_table_1rc.r1_data,
                    "c1_data": lookup_table_1rc.c1_data,
                    "source_reference": lookup_table_1rc.source_reference,
                }
                if lookup_table_1rc
                else None
            ),
            dynamic_degradation_params=None,
            lookup_table_1rc=lookup_table_1rc,
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
    lookup_table_1rc: OCVR1C1LookupTable | None = None


@dataclass
class SecondLifeBattery1RC:
    """Power-system level Thevenin 1RC model for second-life BESS.

    State vector definition (for ODE solvers):
    x[0] = SoC
    x[1] = V_rc

    Capacity convention:
    - `q_nom_ah`: nominal/new-reference capacity.
    - `soh_initial`: second-life available-capacity fraction at initialization.
    - Initial usable capacity is Q_eff(0) = q_nom_ah * soh_initial.
    """

    q_nom_ah: float
    soh_initial: float
    r0_nominal_ohm: float
    r0_soh_sensitivity: float = 0.0
    k_deg: float = 0.0
    soh_min: float = 0.5
    q_eff_min_ah: float = 1e-9
    lookup_table_1rc: OCVR1C1LookupTable = DEFAULT_TRAN_LOOKUP_TABLE
    soc_initial: float = 0.5
    soc_min: float = 0.1
    soc_max: float = 0.9
    source_braco: str = "Braco et al. (2023), Applied Energy"
    source_tran: str = "Tran et al. (2021)"

    def __post_init__(self) -> None:
        self.q_nom_ah = _ensure_positive("q_nom_ah", self.q_nom_ah)
        self.soh_initial = _ensure_fraction("soh_initial", self.soh_initial)
        self.r0_nominal_ohm = _ensure_positive("r0_nominal_ohm", self.r0_nominal_ohm)
        self.r0_soh_sensitivity = _ensure_finite(
            "r0_soh_sensitivity", self.r0_soh_sensitivity
        )
        self.k_deg = _ensure_finite("k_deg", self.k_deg)
        self.soh_min = _ensure_fraction("soh_min", self.soh_min)
        self.q_eff_min_ah = _ensure_positive("q_eff_min_ah", self.q_eff_min_ah)
        self.soc_initial = _ensure_fraction("soc_initial", self.soc_initial)
        self.soc_min = _ensure_fraction("soc_min", self.soc_min)
        self.soc_max = _ensure_fraction("soc_max", self.soc_max)
        if self.k_deg < 0.0:
            raise ValueError(f"k_deg must be >= 0, got {self.k_deg}.")

        if self.soc_min >= self.soc_max:
            raise ValueError(
                f"soc_min must be < soc_max, got {self.soc_min} and {self.soc_max}."
            )
        if self.soc_initial < self.soc_min or self.soc_initial > self.soc_max:
            raise ValueError(
                f"soc_initial={self.soc_initial} must be within [{self.soc_min}, {self.soc_max}]."
            )
        if self.soh_initial < self.soh_min:
            raise ValueError(
                f"soh_initial={self.soh_initial} must be >= soh_min={self.soh_min}."
            )
        if not isinstance(self.lookup_table_1rc, OCVR1C1LookupTable):
            raise ValueError(
                "lookup_table_1rc must be OCVR1C1LookupTable, got "
                f"{type(self.lookup_table_1rc).__name__}."
            )

    @classmethod
    def from_excel_characterization(
        cls,
        excel_path: str | Path,
        q_nom_ah: float,
        soh_initial: float,
        r0_nominal_ohm: float,
        *,
        k_deg: float = 1.478e-6,
        r0_soh_sensitivity: float = 1.0,
        soh_min: float = 0.50,
        q_eff_min_ah: float = 1e-9,
        soc_initial: float = 0.5,
        soc_min: float = 0.1,
        soc_max: float = 0.9,
        source_reference: str = "Braco et al. (2021) / Tran et al. (2021)",
    ) -> "SecondLifeBattery1RC":
        """Construye el modelo cargando OCV/R1/C1 desde Excel.

        Fuente: bess_characterization.load_ocv_r1c1_from_excel()
        k_deg por defecto: Braco (2021) Tabla IV, 1.478e-6 [Ah]^-1.
        Convención de capacidad:
        - `q_nom_ah` es la capacidad nominal de referencia.
        - `soh_initial` representa la fracción de capacidad disponible en
          segunda vida al inicio de la simulación.
        """
        from bess_characterization import load_ocv_r1c1_from_excel

        _ = source_reference
        table = load_ocv_r1c1_from_excel(
            path=excel_path,
            q_nom_ah=q_nom_ah,
        )

        return cls(
            q_nom_ah=q_nom_ah,  # Fuente: Braco (2021) / Tran (2021)
            soh_initial=soh_initial,  # Fuente: Braco (2021) / Tran (2021)
            r0_nominal_ohm=r0_nominal_ohm,  # Fuente: Braco (2021) / Tran (2021)
            lookup_table_1rc=table,  # Fuente: Braco (2021) / Tran (2021)
            k_deg=k_deg,  # Fuente: Braco (2021) / Tran (2021)
            r0_soh_sensitivity=r0_soh_sensitivity,  # Fuente: Braco (2021) / Tran (2021)
            soh_min=soh_min,  # Fuente: Braco (2021) / Tran (2021)
            q_eff_min_ah=q_eff_min_ah,  # Fuente: Braco (2021) / Tran (2021)
            soc_initial=soc_initial,  # Fuente: Braco (2021) / Tran (2021)
            soc_min=soc_min,  # Fuente: Braco (2021) / Tran (2021)
            soc_max=soc_max,  # Fuente: Braco (2021) / Tran (2021)
            source_braco="Braco et al. (2021)",
            source_tran="Tran et al. (2021)",
        )

    def _soc_lookup(self, soc: float) -> float:
        """Saturate SoC only for parameter lookup robustness."""
        return float(np.clip(_ensure_finite("soc", soc), 0.0, 1.0))

    def effective_capacity_ah(self, soh: float | None = None) -> float:
        """Return effective capacity Q_eff = Q_nom * SoH.

        Traceability:
        - Consistent with SoH-by-capacity definition used in Braco/Tran context.
        - This is a direct definition-level relation, not a fitted dynamic law.
        """
        soh_eval = self.soh_initial if soh is None else _ensure_fraction("soh", soh)
        return max(self.q_eff_min_ah, self.q_nom_ah * soh_eval)

    def soh_from_z_deg(self, z_deg: float) -> float:
        """Return SoH(z_deg) from first-order empirical linear fade law.

        Equation (empirical law proposed for this work):
        - SoH = max(soh_min, soh_initial - k_deg * z_deg)

        Notes:
        - Uses throughput state z_deg as continuous-time synthesis of literature
          concepts (charge throughput / equivalent full cycles).
        - This intentionally targets the pre-knee linear aging region.
        """
        z_eval = _ensure_finite("z_deg", z_deg)
        if z_eval < 0.0:
            raise ValueError(f"z_deg must be >= 0, got {z_eval}.")
        return max(self.soh_min, self.soh_initial - self.k_deg * z_eval)

    def effective_capacity_from_z_deg(self, z_deg: float) -> float:
        """Return Q_eff(z_deg) with strict positivity guarantee.

        Equation (definition-level relation):
        - Q_eff = max(q_eff_min_ah, q_nom_ah * SoH(z_deg))
        """
        soh_eval = self.soh_from_z_deg(z_deg)
        return max(self.q_eff_min_ah, self.q_nom_ah * soh_eval)

    def r0_from_z_deg(self, z_deg: float) -> float:
        """Return R0(z_deg) via SoH(z_deg) in the same empirical R0 law."""
        soh_eval = self.soh_from_z_deg(z_deg)
        return self.r0(soh_eval)

    def ocv(self, soc: float) -> float:
        """Return OCV(SoC) by lookup interpolation.

        Traceability:
        - OCV(SoC) dependence is explicit in ECM literature (Tran et al., 2021).
        - The numerical map here comes from a table/interpolator representation.
        """
        soc_eval = self._soc_lookup(soc)
        table = self.lookup_table_1rc
        return float(np.interp(soc_eval, table.soc_data, table.ocv_data))

    def r1(self, soc: float) -> float:
        """Return R1(SoC) by lookup interpolation.

        Traceability:
        - SoC dependence of RC branch parameters follows Tran-style ECM mapping.
        - Implemented as table interpolation for system-level simulation use.
        """
        soc_eval = self._soc_lookup(soc)
        table = self.lookup_table_1rc
        return float(np.interp(soc_eval, table.soc_data, table.r1_data))

    def c1(self, soc: float) -> float:
        """Return C1(SoC) by lookup interpolation.

        Traceability:
        - SoC dependence of RC branch parameters follows Tran-style ECM mapping.
        - Implemented as table interpolation for system-level simulation use.
        """
        soc_eval = self._soc_lookup(soc)
        table = self.lookup_table_1rc
        return float(np.interp(soc_eval, table.soc_data, table.c1_data))

    def r0(self, soh: float) -> float:
        """Return R0(SoH) from a simplified empirical degradation law.

        R0(SoH) = R0_nominal * (1 + k_soh * (1 - SoH))

        Traceability:
        - This relation is an empirical law proposed here for reduced-order
          aging sensitivity studies.
        - It is inspired by literature trends (resistance increases with aging)
          reported by Braco/Tran, but it is not a textual equation copied from
          those sources.
        """
        soh_eval = _ensure_fraction("soh", soh)
        factor = 1.0 + self.r0_soh_sensitivity * (1.0 - soh_eval)
        if factor <= 0.0:
            raise ValueError(
                "r0_soh_sensitivity yields non-positive scaling factor for current SoH."
            )
        return self.r0_nominal_ohm * factor

    def rhs(self, t: float, x, i_bess: float, soh: float) -> list[float]:
        """Continuous-time Thevenin 1RC ODE right-hand side for solve_ivp.

        State:
        - Compatible mode A (Step-2): x = [SoC, V_rc], uses external `soh`.
        - Compatible mode B (Step-3): x = [SoC, V_rc, z_deg], computes SoH(z_deg)
          algebraically and ignores external `soh` as dynamic driver.

        Equations implemented:
        - dSoC/dt = -i_bess / (3600 * Q_eff)  (coulomb-counting synthesis)
        - dV_rc/dt = -V_rc / (R1 * C1) + i_bess / C1
        - dz_deg/dt = |i_bess| / 3600

        Traceability:
        - Terminal voltage relation used with this state model is consistent
          with Tran et al. (2021), Eq. (1), reported in discrete form.
        - RC branch ODE is the continuous-time form associated with Tran et al.
          (2021), Eq. (2), reported in discrete form.
        """
        _ = _ensure_finite("t", t)
        i_eval = _ensure_finite("i_bess", i_bess)
        _ensure_fraction("soh", soh)
        x_len = len(x)
        if x_len not in (2, 3):
            raise ValueError(
                f"State x must have length 2 [soc, v_rc] or 3 [soc, v_rc, z_deg], got {x_len}."
            )

        soc = _ensure_finite("x[0] (soc)", x[0])
        v_rc = _ensure_finite("x[1] (v_rc)", x[1])

        if x_len == 3:
            z_deg = _ensure_finite("x[2] (z_deg)", x[2])
            if z_deg < 0.0:
                raise ValueError(f"x[2] (z_deg) must be >= 0, got {z_deg}.")
            q_eff = self.effective_capacity_from_z_deg(z_deg)
        else:
            q_eff = self.effective_capacity_ah(soh=soh)
        r1_eval = self.r1(soc)
        c1_eval = self.c1(soc)

        dsoc_dt = -i_eval / (3600.0 * q_eff)
        dvrc_dt = -(v_rc / (r1_eval * c1_eval)) + (i_eval / c1_eval)
        if x_len == 3:
            dzdeg_dt = abs(i_eval) / 3600.0
            return [dsoc_dt, dvrc_dt, dzdeg_dt]
        return [dsoc_dt, dvrc_dt]

    def terminal_voltage(self, soc: float, v_rc: float, i_bess: float, soh: float) -> float:
        """Return terminal voltage from the Thevenin ECM algebraic relation.

        Equation:
        - V_t = OCV(SoC) - i_bess * R0(SoH) - V_rc

        Traceability:
        - Consistent with Tran et al. (2021), Eq. (1), commonly expressed in
          discrete-time ECM form.
        """
        v_rc_eval = _ensure_finite("v_rc", v_rc)
        i_eval = _ensure_finite("i_bess", i_bess)
        return self.ocv(soc) - i_eval * self.r0(soh) - v_rc_eval

    def initial_state(self, soc: float | None = None, v_rc: float = 0.0) -> list[float]:
        """Return default initial state [SoC0, Vrc0]."""
        soc0 = self.soc_initial if soc is None else _ensure_finite("soc", soc)
        return [soc0, _ensure_finite("v_rc", v_rc)]

    def initial_state_with_degradation(
        self, soc: float | None = None, v_rc: float = 0.0, z_deg: float = 0.0
    ) -> list[float]:
        """Return default Step-3 initial state [SoC0, Vrc0, z_deg0].

        Traceability:
        - z_deg is the throughput state used for first-order degradation
          synthesis (continuous-time representation of throughput concepts).
        """
        soc0 = self.soc_initial if soc is None else _ensure_finite("soc", soc)
        z0 = _ensure_finite("z_deg", z_deg)
        if z0 < 0.0:
            raise ValueError(f"z_deg must be >= 0, got {z0}.")
        return [soc0, _ensure_finite("v_rc", v_rc), z0]

    # Fix: SoC event stop — step3 validation.
    def soc_min_event(self, t: float, x) -> float:
        """Evento de parada: retorna 0 cuando SoC alcanza soc_min.
        Usar con solve_ivp events= para detener la integración en el límite.
        Convención: solve_ivp para la integración cuando este valor cruza cero
        de positivo a negativo.
        """
        return float(x[0]) - self.soc_min

    # Fix: SoC event stop — step3 validation.
    soc_min_event.terminal = True
    # Fix: SoC event stop — step3 validation.
    soc_min_event.direction = -1
