"""Illustrative 24-hour 3-kW PV profile on the IEEE European LV feeder.

The solar curve is a synthetic half-sine, NOT measured irradiance or PVGIS.
Both locations use exactly the same feeder load profiles and the same PV curve.
This is a grid-connected QSTS comparison, NOT dynamic VSG or islanding.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from ieee_europe_lv_906_study import (
    _snapshot,
    _write_csv,
    verify_dataset,
    write_study_master,
)


def illustrative_pv_kw(minute: int, peak_kw: float = 3.0) -> float:
    """Zero outside 06:00–18:00; 3 kW at noon; no weather claim."""
    if not (0 <= minute < 1440):
        raise ValueError("Minute must be in [0, 1439]")
    if not 360 < minute < 1080:
        return 0.0
    return peak_kw * math.sin(math.pi * (minute - 360) / 720)


def _baseline_rows(path: Path) -> dict[int, dict[str, float]]:
    if not path.is_file():
        raise FileNotFoundError("Run the complete 1440-minute baseline first")
    with path.open(newline="", encoding="utf-8") as stream:
        input_rows = list(csv.DictReader(stream))
    if len(input_rows) != 1440:
        raise ValueError("Baseline must have all 1440 one-minute snapshots")
    rows = {}
    for row in input_rows:
        minute = int(row["minute"])
        if minute in rows:
            raise AssertionError("Duplicate baseline minute")
        rows[minute] = {k: float(value) if value not in ("", None) else float("nan")
                        for k, value in row.items()
                        if k not in ("minute", "pv_bus_phases")}
    if sorted(rows) != list(range(1440)):
        raise AssertionError("Baseline missing one or more minutes")
    return rows


def _run_case(dss, study_master: Path, bus_phase: str, peak_kw: float) -> list[dict]:
    results = []
    for minute in range(1440):
        p_pv = illustrative_pv_kw(minute, peak_kw)
        results.append(_snapshot(
            dss, study_master, minute, p_pv, bus_phase,
            initialize=(minute == 0),
            create_pv_if_zero=(minute == 0),
            reuse_pv=(minute > 0),
        ))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ieee_europe_lv_906"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/analysis/ieee_europe_lv_906"))
    parser.add_argument("--peak-pv-kw", type=float, default=3.0)
    args = parser.parse_args()
    if not math.isfinite(args.peak_pv_kw) or args.peak_pv_kw <= 0:
        parser.error("Peak PV must be finite and strictly positive")
    args.data_dir = args.data_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    verify_dataset(args.data_dir)
    study_master = write_study_master(args.data_dir)
    reference = _baseline_rows(args.output_dir / "baseline_24h.csv")

    import opendssdirect as dss

    summary = {
        "analysis": "Illustrative 24-hour grid-connected QSTS, not GFM",
        "solar_source": "Synthetic 06:00–18:00 half-sine, NOT measured irradiance",
        "peak_pv_kw": args.peak_pv_kw,
        "profiles": {},
    }
    for case, phase_bus in (("near", "34.1.2.3"), ("far", "822.1.2.3")):
        rows = _run_case(dss, study_master, phase_bus, args.peak_pv_kw)
        _write_csv(args.output_dir / f"daily_pv_{case}.csv", rows)
        # Every row is one minute, so the energy time step is 1/60 h.
        e_pv_kwh = sum(r["pv_kw"] for r in rows) / 60.0
        e_loss_baseline = sum(reference[i]["p_loss_kw"] for i in range(1440)) / 60.0
        e_loss_case = sum(r["p_loss_kw"] for r in rows) / 60.0
        e_import_baseline = sum(reference[i]["p_source_kw"] for i in range(1440)) / 60.0
        e_import_case = sum(r["p_source_kw"] for r in rows) / 60.0
        delta_v_min = [
            r["min_v_lv_pu"] - reference[i]["min_v_lv_pu"]
            for i, r in enumerate(rows)
        ]
        summary["profiles"][case] = {
            "bus": phase_bus,
            "samples": len(rows),
            "synthetic_pv_energy_kwh": round(e_pv_kwh, 6),
            "feeder_loss_energy_baseline_kwh": round(e_loss_baseline, 6),
            "feeder_loss_energy_case_kwh": round(e_loss_case, 6),
            "loss_energy_change_percent": round(
                100 * (e_loss_case / e_loss_baseline - 1), 5
            ),
            "grid_import_baseline_kwh": round(e_import_baseline, 6),
            "grid_import_case_kwh": round(e_import_case, 6),
            "max_increase_min_lv_pu": round(max(delta_v_min), 7),
            "min_increase_min_lv_pu": round(min(delta_v_min), 7),
            "absolute_min_lv_pu": round(min(r["min_v_lv_pu"] for r in rows), 7),
            "absolute_max_lv_pu": round(max(r["max_v_lv_pu"] for r in rows), 7),
            "noon": rows[720],
        }
        if abs(rows[720]["pv_kw"] - args.peak_pv_kw) > 1e-6:
            raise AssertionError("PV noon peak mismatch")
        # A blocked case must fail rather than silently produce charts.
        if e_loss_baseline <= 0 or not math.isfinite(e_loss_case):
            raise ValueError("Invalid feeder loss energy")

    (args.output_dir / "daily_pv_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
