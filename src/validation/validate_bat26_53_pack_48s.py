"""BAT26-53 light invariants for the approved Leaf 48-module reference.

Run: python src/validation/validate_bat26_53_pack_48s.py
No BLAST worker, solve_ivp, physical-model modification or heavy simulation.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bess.dc_dc_adapter import convert_power
from bess.leaf_48module_pack import Leaf48ModulePack


def _eq(actual: float, expected: float, name: str, *, atol: float = 1e-9) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-11, abs_tol=atol):
        raise AssertionError(f"{name}: {actual} != {expected}")


def run() -> dict[str, object]:
    pack = Leaf48ModulePack()
    snapshot = pack.capacity()
    assert (pack.n_modules_series, pack.n_2p_series, pack.n_parallel_strings) == (48, 96, 1)
    assert pack.n_physical_cells == 192
    _eq(pack.nominal_voltage_v, 360.0, "Vnom")
    _eq(pack.minimum_voltage_v, 240.0, "Vmin Braco")
    _eq(pack.maximum_voltage_v, 398.4, "Vmax Braco")
    _eq(snapshot.q_nom_ref_ah, 66.0, "Qref")
    _eq(snapshot.q_eff_ah, 44.1, "Qeff MUST NOT multiply in series")
    _eq(snapshot.soh, 44.1 / 66.0, "SoH")
    _eq(pack.ideal_nominal_energy_kwh(), 15.876, "Eideal nominal")
    _eq(pack.ideal_soc_window_energy_kwh(), 12.7008, "Eideal SoC window")

    # Reuse the verified BAT26-45 Qeff checkpoint; do not rerun BLAST.
    aged_q_ah = 35.853796
    aged_retention = aged_q_ah / 44.1
    aged_snapshot = pack.capacity(retention_since_case_start=aged_retention)
    _eq(aged_snapshot.q_eff_ah, aged_q_ah, "Qeff aged")
    _eq(pack.ideal_nominal_energy_kwh(retention_since_case_start=aged_retention),
        360.0 * aged_q_ah / 1000.0, "Eideal aged")

    _eq(pack.ideal_discharge_current_a(
        bus_discharge_power_w=3000.0, efficiency=1.0, pack_voltage_v=360.0),
        3000.0 / 360.0, "Ipack ideal")
    _eq(pack.ideal_discharge_current_a(
        bus_discharge_power_w=3000.0, efficiency=0.95, pack_voltage_v=360.0),
        3000.0 / (0.95 * 360.0), "Ipack hypothetical efficiency")

    # ONLY hypothetical fixture values, NOT measured or approved converter ratings.
    p = pack.converter_parameters(
        eta_discharge=0.95, eta_charge=0.95,
        unit_discharge_max_a=10.0, unit_charge_max_a=10.0,
        bus_current_max_a=20.0, bus_power_max_w=5000.0,
    )
    assert (p.n_series, p.n_parallel) == (96, 1)
    _eq(p.unit_voltage_min_v, 2.5, "2p Vmin")
    _eq(p.unit_voltage_max_v, 4.15, "2p Vmax")
    common = dict(
        parameters=p, bus_voltage_v=340.0, ocv_v=3.75, vrc_v=0.0,
        r0_ohm=0.000970, soc_min=0.1, soc_max=0.9,
    )
    dis = convert_power(bus_power_request_w=3000.0, soc=0.6, **common)
    assert dis.protection_status == "ok" and not dis.saturated
    assert dis.unit_current_a > 0
    _eq(dis.bus_power_w, 3000.0, "Pbus discharge")
    _eq(dis.bank_power_w, 3000.0 / 0.95, "Ppack discharge")
    _eq(dis.bus_current_a, 3000.0 / 340.0, "Ibus discharge")
    _eq(dis.loss_power_w, dis.bank_power_w - dis.bus_power_w, "loss discharge")
    _eq(dis.bank_power_w, pack.n_2p_series * dis.unit_voltage_v * dis.unit_current_a,
        "2p-to-pack power conservation", atol=1e-8)
    ch = convert_power(bus_power_request_w=-2000.0, soc=0.6, **common)
    assert ch.protection_status == "ok" and not ch.saturated
    assert ch.unit_current_a < 0
    _eq(ch.bus_power_w, -2000.0, "Pbus charge")
    _eq(ch.bank_power_w, -1900.0, "Ppack charge")
    _eq(ch.bus_current_a, -2000.0 / 340.0, "Ibus charge")
    _eq(ch.loss_power_w, 100.0, "loss charge")
    lower = convert_power(bus_power_request_w=500.0, soc=0.1, **common)
    upper = convert_power(bus_power_request_w=-500.0, soc=0.9, **common)
    assert lower.saturated and upper.saturated
    _eq(lower.bus_power_w, 0.0, "SoC min blocks discharge")
    _eq(upper.bus_power_w, 0.0, "SoC max blocks charge")

    for invalid in [
        {"n_modules_series": 24},
        {"n_modules_series": 48.0},
        {"n_parallel_strings": True},
        {"q_nom_ref_ah": 44.1},
        {"soc_min": 0.9, "soc_max": 0.1},
        {"module_v_min": 8.4},
    ]:
        try:
            Leaf48ModulePack(**invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid pack accepted: {invalid}")

    for invalid in [
        {"bus_discharge_power_w": 3000, "efficiency": 1.1, "pack_voltage_v": 360},
        {"bus_discharge_power_w": 3000, "efficiency": .95, "pack_voltage_v": 450},
    ]:
        try:
            pack.ideal_discharge_current_a(**invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid current probe accepted: {invalid}")

    return {
        "status": "PASS — arithmetic only, NOT measured hardware validation",
        "topology": "48 modules 2s2p; 96 2p units in series; 1 string",
        "nominal_voltage_v": pack.nominal_voltage_v,
        "voltage_range_v": [pack.minimum_voltage_v, pack.maximum_voltage_v],
        "capacity_case_ah": snapshot.q_eff_ah,
        "soh_initial": snapshot.soh,
        "ideal_energy_kwh": pack.ideal_nominal_energy_kwh(),
        "ideal_soc_window_kwh": pack.ideal_soc_window_energy_kwh(),
        "hypothetical_converter_fixture": {
            "eta": 0.95, "bus_power_w": dis.bus_power_w,
            "battery_power_w": dis.bank_power_w,
            "battery_current_a": dis.unit_current_a,
            "bus_current_a": dis.bus_current_a,
            "label": "TEST FIXTURE ONLY — no converter/BMS ratings approved",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
