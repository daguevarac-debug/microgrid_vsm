"""Algebraic, balanced-bank DC/DC interface; no battery or converter dynamics.

Positive current and power mean battery discharge toward the DC bus. Parameters
and operating limits must be supplied by the caller; no cell data is assumed.
All series units and parallel strings are assumed identical and balanced.
"""

from dataclasses import dataclass
from math import isclose, isfinite, sqrt
from numbers import Real


def _real(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


@dataclass(frozen=True, kw_only=True)
class DCDCParameters:
    n_series: int
    n_parallel: int
    eta_discharge: float
    eta_charge: float
    unit_voltage_min_v: float
    unit_voltage_max_v: float
    unit_discharge_max_a: float
    unit_charge_max_a: float
    bus_current_max_a: float
    bus_power_max_w: float

    def __post_init__(self) -> None:
        for name in ("n_series", "n_parallel"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("eta_discharge", "eta_charge"):
            if not 0 < _real(name, getattr(self, name)) <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        for name in ("unit_voltage_min_v", "unit_voltage_max_v",
                     "unit_discharge_max_a", "unit_charge_max_a",
                     "bus_current_max_a", "bus_power_max_w"):
            if _real(name, getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.unit_voltage_min_v >= self.unit_voltage_max_v:
            raise ValueError("unit voltage limits must be ordered")


@dataclass(frozen=True)
class DCDCResult:
    unit_current_a: float
    bus_current_a: float
    unit_voltage_v: float
    bank_power_w: float
    bus_power_w: float
    loss_power_w: float
    saturated: bool
    bus_charge_limit_w: float = 0.0
    bus_discharge_limit_w: float = 0.0
    protection_status: str = "ok"


def convert_power(*, parameters: DCDCParameters, bus_power_request_w: float,
                  bus_voltage_v: float, ocv_v: float, vrc_v: float,
                  r0_ohm: float, soc: float, soc_min: float,
                  soc_max: float, unit_discharge_available_a: float | None = None,
                  unit_charge_available_a: float | None = None) -> DCDCResult:
    """Limit bus power and solve the low-current 1RC root at this instant.

    Unit current and voltage limits apply per reference unit; bus limits apply
    to the whole converter. SoC limits block discharge/charge at the boundary.
    Available currents are external per-unit limits (e.g. SoH supervision),
    capped by configured limits; None retains the original fixed-limit mode.
    When voltage protection is active, zero exchange is commanded, but the
    returned voltage remains out of range and the caller must handle the event.
    No corrective current or automatic recovery is provided.
    """
    if not isinstance(parameters, DCDCParameters):
        raise ValueError("parameters must be DCDCParameters")
    p = parameters
    request = _real("bus_power_request_w", bus_power_request_w)
    vbus = _real("bus_voltage_v", bus_voltage_v)
    ocv = _real("ocv_v", ocv_v)
    vrc = _real("vrc_v", vrc_v)
    resistance = _real("r0_ohm", r0_ohm)
    soc, soc_min, soc_max = (_real(n, v) for n, v in
                             (("soc", soc), ("soc_min", soc_min), ("soc_max", soc_max)))
    if resistance < 0:
        raise ValueError("R0 must be nonnegative")
    if not 0 <= soc_min < soc_max <= 1 or not 0 <= soc <= 1:
        raise ValueError("SoC and operational bounds must be within [0, 1]")
    available = []
    for name, value, maximum in (
        ("unit_discharge_available_a", unit_discharge_available_a, p.unit_discharge_max_a),
        ("unit_charge_available_a", unit_charge_available_a, p.unit_charge_max_a),
    ):
        limit = maximum if value is None else _real(name, value)
        if limit < 0:
            raise ValueError(f"{name} must be nonnegative")
        available.append(min(limit, maximum))
    e = ocv - vrc
    if not isfinite(e):
        raise ValueError("zero-current unit voltage exceeds numerical range")
    if vbus <= 0 or ocv <= 0 or not p.unit_voltage_min_v <= e <= p.unit_voltage_max_v:
        status = ("bus_voltage_nonpositive" if vbus <= 0 else
                  "ocv_nonpositive" if ocv <= 0 else
                  "unit_undervoltage" if e < p.unit_voltage_min_v else "unit_overvoltage")
        return DCDCResult(0.0, 0.0, e, 0.0, 0.0, 0.0, request != 0.0,
                          0.0, 0.0, status)

    # Restrict discharge to the monotone low-current side of the power parabola.
    discharge = available[0] if soc > soc_min else 0.0
    charge = available[1] if soc < soc_max else 0.0
    if resistance:
        discharge = min(discharge, (e - p.unit_voltage_min_v) / resistance,
                        e / (2 * resistance))
        charge = min(charge, (p.unit_voltage_max_v - e) / resistance)
    count = p.n_series * p.n_parallel
    max_dis = count * (e - resistance * discharge) * discharge * p.eta_discharge
    max_ch = count * (e + resistance * charge) * charge / p.eta_charge
    bus_limit = min(p.bus_power_max_w, vbus * p.bus_current_max_a)
    values = (e, max_dis, max_ch, bus_limit)
    if not all(isfinite(v) for v in values):
        raise ValueError("operating limits overflow")
    charge_limit = -min(max_ch, bus_limit)
    discharge_limit = min(max_dis, bus_limit)
    actual = max(charge_limit, min(request, discharge_limit))
    bank = actual / p.eta_discharge if actual >= 0 else actual * p.eta_charge
    unit_power = bank / count
    discriminant = e * e - 4 * resistance * unit_power
    if not isfinite(discriminant):
        raise ValueError("power balance exceeds numerical range")
    # Tiny negative roundoff at maximum-power boundary is not an infeasible request.
    tolerance = 1e-14 * e * e
    if discriminant < -tolerance:
        raise ValueError("infeasible power balance: negative discriminant")
    current = 2 * unit_power / (e + sqrt(max(0.0, discriminant)))
    voltage = e - resistance * current
    calculated_bank = count * voltage * current
    if not all(isfinite(v) for v in (current, voltage, calculated_bank, actual / vbus)):
        raise ValueError("power conversion exceeds numerical range")
    if not isclose(calculated_bank, bank, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("power balance could not be resolved accurately")
    return DCDCResult(current, actual / vbus, voltage, bank, actual,
                      bank - actual, actual != request, charge_limit, discharge_limit)
