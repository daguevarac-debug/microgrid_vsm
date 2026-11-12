"""Compare the unmodified OpenDSS European LV feeder with IEEE 2015 Table II/III.

Reference: IEEE European Low Voltage Test Feeder, 19 May 2015, Tables II-III.
OpenDSS profile sample 1 is queried at zero-based minute 0; sample 1440 at minute 1439.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ieee_europe_lv_906_study import (
    EXPECTED_LINES,
    EXPECTED_LOADS,
    verify_dataset,
    write_study_master,
)

# IEEE 2015 published OpenDSS results. Values transcribed from
# "The IEEE European Low Voltage Test Feeder", Tables II and III.
# In-source provenance: https://studylib.net/doc/26139528/ieee-european-lv-test-feeder---draft
REFERENCE = {
    0: {
        "transformer_lv_p_kw": (1.0572, 0.9270, 0.8153),
        "transformer_lv_q_kvar": (0.3475, 0.3044, 0.2678),
        "max_v_volt": (252.165, 252.166, 252.169),
        "min_v_volt": (251.909, 251.946, 252.023),
    },
    565: {
        "transformer_lv_p_kw": (17.9072, 35.2927, 6.1837),
        "transformer_lv_q_kvar": (5.4897, 11.5328, 2.0971),
        "max_v_volt": (251.901, 251.443, 254.730),
        "min_v_volt": (245.577, 238.367, 251.952),
    },
    1439: {
        "transformer_lv_p_kw": (3.7201, 3.6648, 2.3369),
        "transformer_lv_q_kvar": (1.2189, 1.2048, 0.7678),
        "max_v_volt": (252.113, 252.105, 252.134),
        "min_v_volt": (251.080, 251.109, 251.805),
    },
}


def _reference_snapshot(dss, master: Path, minute: int) -> dict:
    dss.Basic.ClearAll()
    dss.Text.Command(f'compile "{master.resolve().as_posix()}"')
    if dss.Loads.Count() != EXPECTED_LOADS or dss.Lines.Count() != EXPECTED_LINES:
        raise AssertionError("Unexpected original feeder topology")
    dss.Text.Command("set mode=yearly number=1 stepsize=1m")
    dss.Solution.Hour(minute // 60)
    dss.Solution.Seconds((minute % 60) * 60)
    dss.Solution.Solve()
    if not dss.Solution.Converged():
        raise RuntimeError(f"Nonconverged IEEE reference minute={minute}")

    if dss.Circuit.SetActiveElement("Vsource.Source") < 0:
        raise RuntimeError("Missing substation source element Vsource.Source")
    source_powers = dss.CktElement.Powers()
    if len(source_powers) < 6:
        raise RuntimeError("Source missing three-phase power data")
    source_p = tuple(-float(source_powers[2*i]) for i in range(3))
    source_q = tuple(-float(source_powers[2*i + 1]) for i in range(3))

    # IEEE reference says "substation"; a delta-wye transformer mixes
    # primary-phase powers. Inspect LV secondary powers separately.
    if dss.Circuit.SetActiveElement("Transformer.TR1") < 0:
        raise RuntimeError("Missing Transformer.TR1")
    xfmr = dss.CktElement.Powers()
    # Count the physical conductors INCLUDING the neutral. Do not
    # assume 3 conductors per terminal for a grounded-wye transformer.
    offset = 2 * dss.CktElement.NumConductors()
    if len(xfmr) < offset + 6:
        raise RuntimeError("Transformer.TR1 missing its three-phase secondary")
    transformer_lv_p = tuple(-float(xfmr[offset + 2*i]) for i in range(3))
    transformer_lv_q = tuple(-float(xfmr[offset + 2*i + 1]) for i in range(3))

    phase_voltages: dict[int, list[float]] = {1: [], 2: [], 3: []}
    for busname in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(busname)
        if 0 < dss.Bus.kVBase() < 1:
            nodes = dss.Bus.Nodes()
            mags = dss.Bus.VMagAngle()[::2]
            for node, mag in zip(nodes, mags):
                if node in phase_voltages and 0 < mag < 500:
                    phase_voltages[node].append(float(mag))
    if any(not values for values in phase_voltages.values()):
        raise AssertionError("Missing phase voltage observations")

    return {
        "p_source_kw": source_p,
        "q_source_kvar": source_q,
        "transformer_lv_p_kw": transformer_lv_p,
        "transformer_lv_q_kvar": transformer_lv_q,
        "max_v_volt": tuple(max(phase_voltages[k]) for k in (1, 2, 3)),
        "min_v_volt": tuple(min(phase_voltages[k]) for k in (1, 2, 3)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ieee_europe_lv_906"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/analysis/ieee_europe_lv_906"))
    args = parser.parse_args()
    args.data_dir = args.data_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    verify_dataset(args.data_dir)
    master = write_study_master(args.data_dir)
    import opendssdirect as dss

    rows = []
    for minute, reference in REFERENCE.items():
        simulated = _reference_snapshot(dss, master, minute)
        for metric, expected in reference.items():
            for phase_idx, phase_name in enumerate("ABC"):
                actual = simulated[metric][phase_idx]
                ref = expected[phase_idx]
                rows.append({
                    "minute": minute,
                    "phase": phase_name,
                    "metric": metric,
                    "ieee_2015_reference": ref,
                    "opendss_simulated": round(actual, 8),
                    "signed_error": round(actual - ref, 8),
                    "relative_error_percent": round(100 * (actual - ref) / ref, 5),
                })
    for minute in REFERENCE:
        subset = [r for r in rows if r["minute"] == minute]
        substation_p = _reference_snapshot(dss, master, minute)
        print(f"IEEE snapshot minute={minute}:")
        print(f"  transformer_lv_p_kw={substation_p['transformer_lv_p_kw']} "
              f"transformer_lv_q_kvar={substation_p['transformer_lv_q_kvar']}")
        for metric in ("transformer_lv_p_kw", "transformer_lv_q_kvar", "min_v_volt", "max_v_volt"):
            values = [r for r in subset if r["metric"] == metric]
            expected = [r["ieee_2015_reference"] for r in values]
            actual = [r["opendss_simulated"] for r in values]
            print(f"  {metric}: reference={expected} simulated={actual}")
    # Probe neighboring timestamps without changing parameters; OpenDSS
    # yearly loadshapes may wrap at exactly 24:00.
    for probe_minute in (0, 2, 565, 567, 1438, 1439):
        sample = _reference_snapshot(dss, master, probe_minute)
        print(f"Timeline probe minute={probe_minute}: "
              f"MV_P={[round(v,4) for v in sample['p_source_kw']]} "
              f"LV_P={[round(v,4) for v in sample['transformer_lv_p_kw']]} "
              f"LV_Q={[round(v,4) for v in sample['transformer_lv_q_kvar']]}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "ieee_2015_reference_check.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {}
    for metric in ("transformer_lv_p_kw", "transformer_lv_q_kvar", "max_v_volt", "min_v_volt"):
        subset = [r for r in rows if r["metric"] == metric]
        summary[metric] = {
            "max_abs_error": round(max(abs(r["signed_error"]) for r in subset), 6),
            "max_rel_error_percent": round(max(abs(r["relative_error_percent"]) for r in subset), 4),
        }
    payload = {
        "reference": "IEEE European LV Test Feeder, 19 May 2015, Tables II-III",
        "snapshot_minutes": list(REFERENCE),
        "phase_a_b_c": "Transformer.TR1 LV winding powers, LV bus min/max voltage",
        "published_times": {"0": "00:01", "565": "09:26", "1439": "24:00"},
        "benchmark_comparison": summary,
        "comparison_csv": str(path),
        "note": "Inspect alignment, transformer terminals, and profile revisions before interpreting discrepancies.",
    }
    (args.output_dir / "ieee_2015_reference_summary.json").write_text(
        json.dumps(payload, indent=2)+"\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
