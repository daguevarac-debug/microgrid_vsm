"""Simulator-independent, balanced distribution case (JSON-compatible dictionaries).

Version 1 deliberately covers connected lines, PQ loads/generators and one slack.
See docs/objective_3_preparation.md for units, signs and unsupported equipment.
"""

import json
import math
from pathlib import Path


def _fields(record: dict, expected: str, label: str) -> None:
    if not isinstance(record, dict) or set(record) != set(expected.split()):
        raise ValueError(f"{label}: expected exactly these fields: {expected}")


def _number(record: dict, key: str, *, positive=False, nonnegative=False) -> float:
    value = record[key]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{key}: expected a finite number")
    if (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError(f"{key}: value outside supported range")
    return value


def _text(value, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: expected a nonempty string")


def validate_network(case: dict) -> None:
    """Reject ambiguous units, unsupported fields/elements and disconnected buses."""
    _fields(case, "schema_version name provenance synthetic base_mva frequency_hz "
            "pcc_bus buses lines loads generators slack", "network")
    if type(case["schema_version"]) is not int or case["schema_version"] != 1:
        raise ValueError("Only schema_version=1 is supported")
    _text(case["name"], "name")
    _text(case["provenance"], "provenance")
    if type(case["synthetic"]) is not bool:
        raise ValueError("synthetic must be explicitly true or false")
    _number(case, "base_mva", positive=True)
    _number(case, "frequency_hz", positive=True)
    schemas = {
        "buses": "id vn_kv",
        "lines": "id from_bus to_bus length_km r_ohm_per_km x_ohm_per_km c_nf_per_km max_i_ka",
        "loads": "id bus p_mw q_mvar",
        "generators": "id bus p_mw q_mvar",
    }
    tables = {}
    for table, fields in schemas.items():
        if not isinstance(case[table], list):
            raise ValueError(f"{table}: expected a list")
        rows = {}
        for row in case[table]:
            _fields(row, fields, table)
            _text(row["id"], f"{table}.id")
            if row["id"] in rows:
                raise ValueError(f"{table}: duplicate id {row['id']}")
            rows[row["id"]] = row
        tables[table] = rows
    buses = tables["buses"]
    if not buses:
        raise ValueError("At least one bus is required")

    def bus_reference(value):
        _text(value, "bus reference")
        if value not in buses:
            raise ValueError(f"Unknown bus: {value}")

    bus_reference(case["pcc_bus"])
    for bus in buses.values():
        _number(bus, "vn_kv", positive=True)
    _fields(case["slack"], "bus vm_pu va_degree", "slack")
    bus_reference(case["slack"]["bus"])
    _number(case["slack"], "vm_pu", positive=True)
    _number(case["slack"], "va_degree")
    neighbours = {bus: set() for bus in buses}
    for line in tables["lines"].values():
        a, b = line["from_bus"], line["to_bus"]
        bus_reference(a)
        bus_reference(b)
        if a == b:
            raise ValueError("Self-loop lines are not supported")
        if not math.isclose(buses[a]["vn_kv"], buses[b]["vn_kv"], rel_tol=1e-9):
            raise ValueError("A line cannot join different voltage levels; adapt transformers explicitly")
        for key in ("length_km", "max_i_ka"):
            _number(line, key, positive=True)
        for key in ("r_ohm_per_km", "x_ohm_per_km", "c_nf_per_km"):
            _number(line, key, nonnegative=True)
        if line["r_ohm_per_km"] + line["x_ohm_per_km"] == 0:
            raise ValueError("Zero-impedance lines are not supported")
        neighbours[a].add(b)
        neighbours[b].add(a)
    for table in ("loads", "generators"):
        for row in tables[table].values():
            bus_reference(row["bus"])
            _number(row, "p_mw", nonnegative=True)
            _number(row, "q_mvar")
    visited, pending = set(), [case["slack"]["bus"]]
    while pending:
        bus = pending.pop()
        if bus not in visited:
            visited.add(bus)
            pending.extend(neighbours[bus] - visited)
    if visited != set(buses):
        raise ValueError(f"Buses disconnected from slack: {sorted(set(buses) - visited)}")


def load_network(path: str | Path) -> dict:
    """Read the neutral format; external PowerFactory/pandapower imports are future work."""
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    case = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
    validate_network(case)
    return case


def to_pandapower(case: dict):
    """Build a fresh solver network without changing the neutral input."""
    validate_network(case)
    import pandapower as pp

    net = pp.create_empty_network(sn_mva=case["base_mva"], f_hz=case["frequency_hz"])
    bus_indices = {
        row["id"]: pp.create_bus(net, vn_kv=row["vn_kv"], name=row["id"])
        for row in case["buses"]
    }
    slack = case["slack"]
    pp.create_ext_grid(net, bus=bus_indices[slack["bus"]],
                       vm_pu=slack["vm_pu"], va_degree=slack["va_degree"])
    for line in case["lines"]:
        values = {key: value for key, value in line.items()
                  if key not in ("id", "from_bus", "to_bus")}
        pp.create_line_from_parameters(net, from_bus=bus_indices[line["from_bus"]],
                                       to_bus=bus_indices[line["to_bus"]], name=line["id"], **values)
    for table, create in (("loads", pp.create_load), ("generators", pp.create_sgen)):
        for row in case[table]:
            create(net, bus=bus_indices[row["bus"]], name=row["id"],
                   p_mw=row["p_mw"], q_mvar=row["q_mvar"])
    return net, bus_indices
