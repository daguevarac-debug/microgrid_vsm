"""Read-only 48x(2s2p) Nissan Leaf pack scale for thesis BAT26-53.

48 modules in series = 96 two-cell parallel units (2p) in series,
one string and 192 physical cells. Ah is NOT multiplied by 48 or 96.

Braco et al. (2021) doi:10.1109/TIA.2021.3075180, Table I
Braco et al. (2023) doi:10.1016/j.apenergy.2022.120235, Table 1

The selected voltage envelope is from Braco (2021); the distinct
upper bound in Castillo-Martinez et al. (2022) is not mixed into it.
This file has no new battery/convertor ODE or approved hardware rating.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite

from bess.aging_capacity import CapacitySnapshot
from bess.dc_dc_adapter import DCDCParameters


def _finite_positive(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be finite real")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


@dataclass(frozen=True, kw_only=True)
class Leaf48ModulePack:
    """Approved homogeneous 48-module series scenario, not measured hardware.

    Voltage envelope from Braco 2021: 5.0--8.3 V per 2s2p module.
    Q is capacity of ONE 2p unit and of ONE series string.
    """

    n_modules_series: int = 48
    series_2p_units_per_module: int = 2
    n_parallel_strings: int = 1
    module_v_nominal: float = 7.5
    module_v_min: float = 5.0
    module_v_max: float = 8.3
    q_nom_ref_ah: float = 66.0
    q_init_case_ah: float = 44.1
    soc_min: float = 0.10
    soc_max: float = 0.90
    vdc_nominal_v: float = 340.0

    def __post_init__(self) -> None:
        for name in ("n_modules_series", "series_2p_units_per_module", "n_parallel_strings"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if (self.n_modules_series != 48 or self.series_2p_units_per_module != 2
                or self.n_parallel_strings != 1):
            raise ValueError("BAT26-53 approved exactly 48 modules 2s2p in one string")
        for field in ("module_v_nominal", "module_v_min", "module_v_max",
                      "q_nom_ref_ah", "q_init_case_ah", "vdc_nominal_v"):
            _finite_positive(field, getattr(self, field))
        if not self.module_v_min < self.module_v_nominal < self.module_v_max:
            raise ValueError("module voltage envelope must include nominal voltage")
        if not 0.0 <= self.soc_min < self.soc_max <= 1.0:
            raise ValueError("SoC bounds must satisfy 0 <= min < max <= 1")
        if not isclose(self.q_nom_ref_ah, 66.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("Leaf 2p nominal reference must remain 66 Ah")
        if self.q_init_case_ah > self.q_nom_ref_ah:
            raise ValueError("second-life scenario capacity exceeds nominal reference")

    @property
    def n_2p_series(self) -> int:
        return self.n_modules_series * self.series_2p_units_per_module

    @property
    def n_physical_cells(self) -> int:
        return self.n_2p_series * 2 * self.n_parallel_strings

    @property
    def nominal_voltage_v(self) -> float:
        return self.n_modules_series * self.module_v_nominal

    @property
    def minimum_voltage_v(self) -> float:
        return self.n_modules_series * self.module_v_min

    @property
    def maximum_voltage_v(self) -> float:
        return self.n_modules_series * self.module_v_max

    def capacity(self, *, retention_since_case_start: float = 1.0) -> CapacitySnapshot:
        """Slow-window Qeff in Ah. In series Qeff is NOT multiplied by Ns."""
        return CapacitySnapshot(
            q_nom_ref_ah=self.q_nom_ref_ah,
            q_init_case_ah=self.q_init_case_ah,
            retention_since_case_start=retention_since_case_start,
        )

    def ideal_nominal_energy_kwh(self, *, retention_since_case_start: float = 1.0) -> float:
        """Vnom*Qeff approximation; NOT measured terminal/bus energy."""
        return (self.nominal_voltage_v * self.capacity(
            retention_since_case_start=retention_since_case_start).q_eff_ah / 1000.0)

    def ideal_soc_window_energy_kwh(self, *, retention_since_case_start: float = 1.0) -> float:
        return self.ideal_nominal_energy_kwh(
            retention_since_case_start=retention_since_case_start
        ) * (self.soc_max - self.soc_min)

    def ideal_discharge_current_a(self, *, bus_discharge_power_w: float,
                                  efficiency: float, pack_voltage_v: float) -> float:
        """Current estimate Pbus/(eta*Vpack); not a feasible-current guarantee."""
        power = _finite_positive("bus_discharge_power_w", bus_discharge_power_w)
        voltage = _finite_positive("pack_voltage_v", pack_voltage_v)
        eff = _finite_positive("efficiency", efficiency)
        if eff > 1.0:
            raise ValueError("efficiency must not exceed unity")
        if not self.minimum_voltage_v <= voltage <= self.maximum_voltage_v:
            raise ValueError("pack voltage is outside the selected literature envelope")
        return power / (eff * voltage)

    def converter_parameters(self, *, eta_discharge: float, eta_charge: float,
                             unit_discharge_max_a: float, unit_charge_max_a: float,
                             bus_current_max_a: float, bus_power_max_w: float) -> DCDCParameters:
        """Configure EXISTING algebraic adapter; all ratings must be supplied.

        The parameters are hypotheses, never certified by this class.
        """
        return DCDCParameters(
            n_series=self.n_2p_series,
            n_parallel=self.n_parallel_strings,
            eta_discharge=eta_discharge,
            eta_charge=eta_charge,
            unit_voltage_min_v=self.module_v_min / self.series_2p_units_per_module,
            unit_voltage_max_v=self.module_v_max / self.series_2p_units_per_module,
            unit_discharge_max_a=unit_discharge_max_a,
            unit_charge_max_a=unit_charge_max_a,
            bus_current_max_a=bus_current_max_a,
            bus_power_max_w=bus_power_max_w,
        )
