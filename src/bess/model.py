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
     Q_nom is the nominal reference capacity and Q_eff(0) is case-dependent.
     We parameterize each case with q_init_case_ah and derive
     soh_init_case = q_init_case_ah / q_nom_ref_ah.

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

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from bess.capacity import derive_q_init_case_ah, derive_soh_init_case
from bess.lookup_table import OCVR1C1LookupTable, DEFAULT_TRAN_LOOKUP_TABLE
from bess.validators import _ensure_finite, _ensure_fraction, _ensure_positive


@dataclass(kw_only=True)
class SecondLifeBattery1RC:
    """Power-system level Thevenin 1RC model for second-life BESS.

    State vector definition (for ODE solvers):
    x[0] = SoC
    x[1] = V_rc

    Capacity convention:
    - `q_nom_ref_ah`: nominal reference capacity.
    - `q_init_case_ah`: initial available capacity for a specific case.
    - `soh_init_case`: derived as q_init_case_ah / q_nom_ref_ah.

    Traceability:
    - Braco (2020, 2021) reports the 66 Ah nominal reference for Nissan Leaf 2p.
    - Tran (2021) uses 20 Ah LFP cells and is not the source for 66 Ah.
    """

    r0_nominal_ohm: float
    q_nom_ref_ah: float | None = None
    q_init_case_ah: float | None = None
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
    # Simple compatibility bridge for legacy arguments.
    q_nom_ah: float | None = None
    soh_initial: float | None = None
    # Canonical derived value.
    soh_init_case: float = field(init=False)

    def _normalize_capacity_inputs(self) -> tuple[float, float, float]:
        """Normalize canonical/legacy capacity inputs into canonical values."""
        q_nom_ref = self.q_nom_ref_ah
        q_nom_legacy = self.q_nom_ah
        q_init_case = self.q_init_case_ah
        soh_legacy = self.soh_initial

        if q_nom_ref is None and q_nom_legacy is None:
            raise ValueError(
                "Capacity input missing: provide q_nom_ref_ah (canonical) "
                "or q_nom_ah (legacy)."
            )

        if q_nom_ref is None:
            q_nom_ref = _ensure_positive("q_nom_ah", q_nom_legacy)
        else:
            q_nom_ref = _ensure_positive("q_nom_ref_ah", q_nom_ref)
            if q_nom_legacy is not None:
                q_nom_legacy_eval = _ensure_positive("q_nom_ah", q_nom_legacy)
                if not np.isclose(q_nom_ref, q_nom_legacy_eval, rtol=0.0, atol=1e-12):
                    raise ValueError(
                        "Inconsistent q_nom_ref_ah and q_nom_ah values: "
                        f"{q_nom_ref} vs {q_nom_legacy_eval}."
                    )

        if q_init_case is None and soh_legacy is None:
            raise ValueError(
                "Capacity input missing: provide q_init_case_ah (canonical) "
                "or soh_initial (legacy)."
            )

        if q_init_case is None:
            q_init_case = derive_q_init_case_ah(
                soh_init_case=_ensure_fraction("soh_initial", soh_legacy),
                q_nom_ref_ah=q_nom_ref,
            )
        else:
            q_init_case = _ensure_positive("q_init_case_ah", q_init_case)

        soh_init_case = derive_soh_init_case(
            q_init_case_ah=q_init_case,
            q_nom_ref_ah=q_nom_ref,
        )
        if soh_legacy is not None:
            soh_legacy_eval = _ensure_fraction("soh_initial", soh_legacy)
            if not np.isclose(soh_init_case, soh_legacy_eval, rtol=0.0, atol=1e-12):
                raise ValueError(
                    "Inconsistent q_init_case_ah and soh_initial values: "
                    f"{soh_init_case} vs {soh_legacy_eval}."
                )

        return q_nom_ref, q_init_case, soh_init_case

    def __post_init__(self) -> None:
        q_nom_ref_ah, q_init_case_ah, soh_init_case = self._normalize_capacity_inputs()
        self.q_nom_ref_ah = q_nom_ref_ah
        self.q_init_case_ah = q_init_case_ah
        self.soh_init_case = soh_init_case
        # Legacy read aliases preserved for compatibility.
        self.q_nom_ah = q_nom_ref_ah
        self.soh_initial = soh_init_case

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
        if self.soh_init_case < self.soh_min:
            raise ValueError(
                f"soh_init_case={self.soh_init_case} must be >= soh_min={self.soh_min}."
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
        *args,
        q_nom_ref_ah: float | None = None,
        q_init_case_ah: float | None = None,
        r0_nominal_ohm: float | None = None,
        q_nom_ah: float | None = None,
        soh_initial: float | None = None,
        k_deg: float = 1.478e-6,
        r0_soh_sensitivity: float = 1.0,
        soh_min: float = 0.50,
        q_eff_min_ah: float = 1e-9,
        soc_initial: float = 0.5,
        soc_min: float = 0.1,
        soc_max: float = 0.9,
        source_reference: str = "Braco et al. (2021) / Tran et al. (2021)",
    ) -> "SecondLifeBattery1RC":
        """Build the model by loading OCV/R1/C1 from Excel.

        Capacity convention:
        - Canonical: q_nom_ref_ah + q_init_case_ah.
        - Legacy bridge: q_nom_ah + soh_initial.
        - Initial SoH is always derived as q_init_case_ah / q_nom_ref_ah.
        """
        from bess.characterization import load_ocv_r1c1_from_excel

        if args:
            if len(args) != 3:
                raise TypeError(
                    "from_excel_characterization positional bridge expects exactly "
                    "3 args: q_nom_ah, soh_initial, r0_nominal_ohm."
                )
            if any(
                value is not None
                for value in (
                    q_nom_ref_ah,
                    q_init_case_ah,
                    q_nom_ah,
                    soh_initial,
                    r0_nominal_ohm,
                )
            ):
                raise TypeError(
                    "Cannot mix positional legacy capacity args with keyword "
                    "capacity args in from_excel_characterization."
                )
            q_nom_ah, soh_initial, r0_nominal_ohm = args

        if r0_nominal_ohm is None:
            raise TypeError("r0_nominal_ohm is required.")

        q_nom_for_loader = q_nom_ref_ah if q_nom_ref_ah is not None else q_nom_ah
        if q_nom_for_loader is None:
            raise ValueError(
                "Capacity input missing: provide q_nom_ref_ah (canonical) "
                "or q_nom_ah (legacy)."
            )
        q_nom_for_loader = _ensure_positive("q_nom_ref_ah", q_nom_for_loader)

        _ = source_reference
        table = load_ocv_r1c1_from_excel(
            path=excel_path,
            q_nom_ah=q_nom_for_loader,
        )

        return cls(
            q_nom_ref_ah=q_nom_ref_ah,
            q_init_case_ah=q_init_case_ah,
            q_nom_ah=q_nom_ah,
            soh_initial=soh_initial,
            r0_nominal_ohm=r0_nominal_ohm,
            lookup_table_1rc=table,
            k_deg=k_deg,
            r0_soh_sensitivity=r0_soh_sensitivity,
            soh_min=soh_min,
            q_eff_min_ah=q_eff_min_ah,
            soc_initial=soc_initial,
            soc_min=soc_min,
            soc_max=soc_max,
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
        soh_eval = self.soh_init_case if soh is None else _ensure_fraction("soh", soh)
        return max(self.q_eff_min_ah, self.q_nom_ref_ah * soh_eval)

    def soh_from_z_deg(self, z_deg: float) -> float:
        """Return SoH(z_deg) from first-order empirical linear fade law.

        Equation (empirical law proposed for this work):
        - SoH = max(soh_min, soh_init_case - k_deg * z_deg)

        Notes:
        - Uses throughput state z_deg as continuous-time synthesis of literature
          concepts (charge throughput / equivalent full cycles).
        - This intentionally targets the pre-knee linear aging region.
        """
        z_eval = _ensure_finite("z_deg", z_deg)
        if z_eval < 0.0:
            raise ValueError(f"z_deg must be >= 0, got {z_eval}.")
        return max(self.soh_min, self.soh_init_case - self.k_deg * z_eval)

    def effective_capacity_from_z_deg(self, z_deg: float) -> float:
        """Return Q_eff(z_deg) with strict positivity guarantee.

        Equation (definition-level relation):
        - Q_eff = max(q_eff_min_ah, q_nom_ref_ah * SoH(z_deg))
        """
        soh_eval = self.soh_from_z_deg(z_deg)
        return max(self.q_eff_min_ah, self.q_nom_ref_ah * soh_eval)

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

    # Fix: SoC event stop - step3 validation.
    def soc_min_event(self, t: float, x) -> float:
        """Stop event: return 0 when SoC reaches soc_min."""
        return float(x[0]) - self.soc_min

    # Fix: SoC event stop - step3 validation.
    soc_min_event.terminal = True
    # Fix: SoC event stop - step3 validation.
    soc_min_event.direction = -1
