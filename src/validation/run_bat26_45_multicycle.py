"""BAT26-45: synthetic long-horizon second-life Nissan Leaf BLAST aging.

Run with the audited BLAST Python 3.12.10, not the microgrid interpreter.
One daily window represents a SoC 0.5 -> 0.1 -> 0.9 -> 0.5 excursion
(0.8 nominal EFC), followed by rest to 24 h. The calendar comparator
uses the same time grid, boundaries, temperature, and initial BLAST state.
The original BLAST implementation and its source hashes are mandatory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from bess.aging_capacity import CapacitySnapshot

NOMINAL_AH = 66.0
INITIAL_CASE_AH = 44.1
MIN_SOH = 0.50
TEMPERATURE_C = 25.0
C_RATE = 0.5
DAY_S = 86400.0
ACTIVE_END_S = 3.2 * 3600.0
KEY_TIMES_S = (0.0, 0.8 * 3600.0, 2.4 * 3600.0, ACTIVE_END_S)
KEY_SOC = (0.5, 0.1, 0.9, 0.5)
CHECKPOINTS = (0, 1, 10, 50, 100, 250, 500, 750, 1000)
OUT_PARENT = REPO / "outputs" / "analysis" / "bat26_45_multicycle"
EXPECTED_HASHES = {
    "Leaf": "258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844",
    "BatteryDegradationModel": "1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f",
}


def daily_profile(cycle_number: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """24 h absolute timestamps and a fully closed, continuous SoC cycle."""
    if cycle_number < 1:
        raise ValueError("cycle_number must be >= 1")
    active_t = np.linspace(0.0, ACTIVE_END_S, 97)
    rest_t = np.linspace(ACTIVE_END_S, DAY_S, 33)[1:]
    relative_t = np.concatenate((active_t, rest_t))
    active_soc = np.interp(active_t, KEY_TIMES_S, KEY_SOC)
    soc = np.concatenate((active_soc, np.full(len(rest_t), 0.5)))
    absolute_t = relative_t + (cycle_number - 1) * DAY_S
    temperature = np.full(len(absolute_t), TEMPERATURE_C)
    if (len(soc) != 129 or not np.all(np.diff(absolute_t) > 0)
            or not np.isclose(soc[0], soc[-1])
            or not np.isclose(soc[0], 0.5)
            or not np.isclose(np.min(soc), 0.1)
            or not np.isclose(np.max(soc), 0.9)
            or not np.isclose(np.sum(np.abs(np.diff(soc))), 1.6, atol=1e-12)):
        raise RuntimeError("synthetic profile violates SoC/continuity/EFC contract")
    return absolute_t, soc, temperature


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_original_blast():
    if sys.version_info[:3] != (3, 12, 10):
        raise RuntimeError("BAT26-45 requires exact BLAST Python 3.12.10")
    if importlib.metadata.version("BLAST-Lite") != "1.1.0":
        raise RuntimeError("BAT26-45 requires BLAST-Lite 1.1.0")
    from blast.models.degradation_model import BatteryDegradationModel
    from blast.models.lmo_gr_NissanLeaf66Ah_2ndLife_2020 import (
        Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery as Battery,
    )
    paths = {
        "Leaf": Path(inspect.getfile(Battery)),
        "BatteryDegradationModel": Path(inspect.getfile(BatteryDegradationModel)),
    }
    observed = {name: _sha(path) for name, path in paths.items()}
    if observed != EXPECTED_HASHES:
        raise RuntimeError(f"BLAST SHA mismatch: {observed}")
    return Battery, observed


def _record(cycle: int, cycling, calendar, *, q0_cycling: float,
            q0_calendar: float, cumulative_ah: float) -> dict:
    q_cycle = float(cycling.outputs["q"][-1])
    q_rest = float(calendar.outputs["q"][-1])
    snap_cycle = CapacitySnapshot(NOMINAL_AH, INITIAL_CASE_AH, q_cycle / q0_cycling)
    snap_rest = CapacitySnapshot(NOMINAL_AH, INITIAL_CASE_AH, q_rest / q0_calendar)
    return {
        "cycles": cycle,
        "elapsed_days": float(cycle),
        "nominal_efc_from_soc": cycle * 0.8,
        "efc_blast": float(cycling.stressors["efc"][-1]),
        "efc_from_case_throughput": cumulative_ah / (2.0 * INITIAL_CASE_AH),
        "synthetic_throughput_ah": cumulative_ah,
        "q_blast_cycling": q_cycle,
        "q_blast_calendar": q_rest,
        "soh_cycling": snap_cycle.soh,
        "soh_calendar": snap_rest.soh,
        "soh_cycling_pct": snap_cycle.soh * 100.0,
        "soh_calendar_pct": snap_rest.soh * 100.0,
        "soh_calendar_minus_cycling_pp": (snap_rest.soh - snap_cycle.soh) * 100.0,
        "qeff_cycling_ah": snap_cycle.q_eff_ah,
        "qeff_calendar_ah": snap_rest.q_eff_ah,
        "calendar_loss_cycling": float(cycling.states["qLoss_t"][-1]),
        "cycle_loss_cycling": float(cycling.states["qLoss_EFC"][-1]),
        "calendar_loss_rest": float(calendar.states["qLoss_t"][-1]),
        "cycle_loss_rest": float(calendar.states["qLoss_EFC"][-1]),
        "qnew_cycling_blast": float(cycling.outputs["qNew"][-1]),
        "qnew_calendar_blast": float(calendar.outputs["qNew"][-1]),
    }


def _check_state(previous: dict, current: dict) -> None:
    for name in ("soh_cycling", "soh_calendar", "q_blast_cycling",
                 "q_blast_calendar"):
        if not (np.isfinite(current[name]) and 0 < current[name] <= previous[name] + 1e-10):
            raise RuntimeError(f"invalid BLAST aging state: {name}")
    if current["efc_blast"] + 1e-12 < previous["efc_blast"]:
        raise RuntimeError("BLAST internal EFC decreased")
    if current["cycle_loss_rest"] > 1e-10:
        raise RuntimeError("calendar reference generated artificial cycling loss")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _plots(out: Path, rows: list[dict]) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [row["cycles"] for row in rows]
    sohc = [row["soh_cycling_pct"] for row in rows]
    sohr = [row["soh_calendar_pct"] for row in rows]
    qcy = [row["qeff_cycling_ah"] for row in rows]
    qre = [row["qeff_calendar_ah"] for row in rows]
    files = []

    for zoom, filename in ((False, "soh_vs_cycles_full.png"),
                           (True, "soh_vs_cycles_zoom.png")):
        fig, ax = plt.subplots(figsize=(11, 6.2))
        ax.plot(xs, sohc, linewidth=2, label="Perfil diario de ciclos")
        ax.plot(xs, sohr, linewidth=2, label="Referencia en reposo")
        ax.axhline(MIN_SOH * 100, linestyle="--", color="gray",
                   label="Límite de operación SoH = 50 %")
        if zoom:
            lower = max(0.0, min(min(sohc), min(sohr)) - 0.5)
            upper = min(100.0, max(max(sohc), max(sohr)) + 1.0)
            ax.set_ylim(lower, upper)
        else:
            ax.set_ylim(0.0, 100.0)
        ax.set_xlabel("Ciclos diarios completos (0.8 EFC nominales/ciclo)")
        ax.set_ylabel("SoH del caso de tesis (%)")
        ax.set_title("Nissan Leaf segunda vida — BLAST-Lite original; 25 °C")
        ax.grid(alpha=0.25)
        ax.legend()
        if zoom:
            ax.text(0.02, 0.02, "Escala vertical ampliada", transform=ax.transAxes,
                    fontsize=9)
        fig.tight_layout()
        fig.savefig(out / filename, dpi=180)
        plt.close(fig)
        files.append(filename)

    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.plot(xs, qcy, linewidth=2, label="Perfil diario de ciclos")
    ax.plot(xs, qre, linewidth=2, label="Referencia en reposo")
    ax.axhline(MIN_SOH * NOMINAL_AH, linestyle="--", color="gray",
               label="Capacidad al SoH mínimo del 50 %")
    ax.set_xlabel("Ciclos diarios completos (0.8 EFC nominales/ciclo)")
    ax.set_ylabel("Capacidad efectiva estimada (Ah)")
    ax.set_title("Retención de capacidad — caso inicial 44.1 Ah")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "capacity_vs_cycles.png", dpi=180)
    plt.close(fig)
    files.append("capacity_vs_cycles.png")
    return files


def _sensitivity(Battery, n_cycles: int, reference: dict) -> dict:
    """Compare one 24h update/day with active+rest updates/day at same boundaries."""
    if not n_cycles:
        return {"status": "NOT_RUN", "reason": "disabled"}
    model = Battery()
    idx = 96  # active-phase endpoint at 3.2h; two windows share one sample
    for day in range(1, n_cycles + 1):
        t, soc, temp = daily_profile(day)
        model.update_battery_state(t[:idx+1], soc[:idx+1], temp[:idx+1])
        model.update_battery_state(t[idx:], soc[idx:], temp[idx:])
    q_split = float(model.outputs["q"][-1])
    q_whole = float(reference["q_blast_cycling"])
    efc_split = float(model.stressors["efc"][-1])
    return {
        "status": "DIAGNOSTIC",
        "cycles": n_cycles,
        "partitions": ["one_24h_window_per_day", "active_plus_rest_two_windows_per_day"],
        "q_one_window": q_whole,
        "q_two_windows": q_split,
        "delta_soh_pp_two_minus_one": (q_split - q_whole)
        * INITIAL_CASE_AH / NOMINAL_AH * 100.0,
        "efc_one_window": float(reference["efc_blast"]),
        "efc_two_windows": efc_split,
        "efc_difference_two_minus_one": efc_split - float(reference["efc_blast"]),
        "interpretation": "Numerical window sensitivity; no experimental tolerance established.",
    }


def _args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=1000,
                        help="Maximum complete daily cycles, typically 100 or 1000.")
    parser.add_argument("--sensitivity-cycles", type=int, default=100,
                        help="Audited 1-window vs 2-window comparison (default 100).")
    return parser.parse_args()


def main() -> int:
    args = _args()
    if not 1 <= args.cycles <= 1000:
        raise SystemExit("--cycles must be between 1 and 1000")
    if not 0 <= args.sensitivity_cycles <= args.cycles:
        raise SystemExit("--sensitivity-cycles must be 0..--cycles")

    Battery, audited_hashes = _verify_original_blast()
    out = OUT_PARENT / datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    cycling = Battery()
    calendar = Battery()
    q0_cycling = float(cycling.outputs["q"][-1])
    q0_calendar = float(calendar.outputs["q"][-1])
    assert q0_cycling == q0_calendar == 1.0
    assert cycling.cap == calendar.cap == 66
    assert cycling.cap_2ndLife == calendar.cap_2ndLife == 46
    assert np.isclose(cycling.outputs["qNew"][-1], 0.7)

    rows = [_record(0, cycling, calendar, q0_cycling=q0_cycling,
                    q0_calendar=q0_calendar, cumulative_ah=0.0)]
    sensitivity_reference = None
    throughput_ah = 0.0
    exception = None
    threshold_day = None
    for day in range(1, args.cycles + 1):
        try:
            t, soc, temp = daily_profile(day)
            q_effective_before = rows[-1]["qeff_cycling_ah"]
            # Ideal 0.5C of *available* capacity, constant within each day.
            # BLAST itself uses only SoC and temperature, not this DC/2p current.
            reference_halfcycle_a = C_RATE * q_effective_before
            assert reference_halfcycle_a > 0
            cycling.update_battery_state(t, soc, temp)
            calendar.update_battery_state(t, np.full_like(soc, 0.5), temp)
            throughput_ah += 1.6 * q_effective_before
            row = _record(day, cycling, calendar, q0_cycling=q0_cycling,
                          q0_calendar=q0_calendar, cumulative_ah=throughput_ah)
            _check_state(rows[-1], row)
            rows.append(row)
            if day == args.sensitivity_cycles:
                sensitivity_reference = row
            if day in CHECKPOINTS:
                print(
                    f"cycle={day} | SoH={row['soh_cycling_pct']:.8f}%"
                    f" | resting={row['soh_calendar_pct']:.8f}%"
                    f" | BLAST_EFC={row['efc_blast']:.6f}", flush=True)
            if row["soh_cycling"] < MIN_SOH or row["soh_calendar"] < MIN_SOH:
                threshold_day = day
                print(f"SoH minimum crossed on cycle {day}; stopping", flush=True)
                break
        except Exception as exc:
            exception = f"cycle {day}: {type(exc).__name__}: {exc}"
            print(exception, file=sys.stderr, flush=True)
            break

    csv_path = out / "cycle_history.csv"
    _write_csv(csv_path, rows)
    figure_error = None
    try:
        figures = _plots(out, rows)
    except Exception as exc:
        figures = []
        figure_error = f"{type(exc).__name__}: {exc}"

    try:
        sensitivity = (_sensitivity(Battery, args.sensitivity_cycles,
                                    sensitivity_reference)
                       if sensitivity_reference is not None
                       else {"status": "NOT_RUN",
                             "reason": "checkpoint was not reached"})
    except Exception as exc:
        sensitivity = {"status": "FAIL", "error": str(exc)}

    reached_requested_cycles = rows[-1]["cycles"] == args.cycles
    status = ("FAIL" if exception or figure_error or sensitivity["status"] == "FAIL"
              else "LIMIT_REACHED" if threshold_day is not None
              else "PASS" if reached_requested_cycles else "INCOMPLETE")
    report = {
        "task": "BAT26-45",
        "status": status,
        "scope": "synthetic first-order BLAST; NOT experimental 2p or DC/DC validation",
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
            capture_output=True, check=False).stdout.strip(),
        "python_version": sys.version.split()[0],
        "blast_lite_version": importlib.metadata.version("BLAST-Lite"),
        "original_hashes": audited_hashes,
        "inputs_sha256": {name: _sha(REPO / name) for name in (
            "src/validation/run_bat26_45_multicycle.py", "src/bess/aging_capacity.py",
        )},
        "scenario": {
            "initial_case_ah": INITIAL_CASE_AH,
            "nominal_ref_ah": NOMINAL_AH,
            "initial_soh_pct": 100.0 * INITIAL_CASE_AH / NOMINAL_AH,
            "soh_operational_minimum_pct": MIN_SOH * 100.0,
            "cell_temperature_c_synthetic": TEMPERATURE_C,
            "soc_path_per_day": list(KEY_SOC) + [0.5],
            "rate_c_relative_to_start_day_capacity": C_RATE,
            "active_hours_per_day": 3.2,
            "rest_hours_per_day": 20.8,
            "cycles_per_day": 1,
            "nominal_efc_per_cycle": 0.8,
            "calendar_baseline": "SoC=0.5, 25C, matching time grid and daily windows",
            "blast_stressors": "SoC and temperature; current not fed to native BLAST",
            "interpretation": "Qeff=44.1Ah*(q/q0). BLAST qNew*66Ah is NOT initial thesis capacity.",
        },
        "requested_cycles": args.cycles,
        "completed_cycles": rows[-1]["cycles"],
        "threshold_cycle": threshold_day,
        "exception": exception,
        "figure_error": figure_error,
        "sensitivity": sensitivity,
        "checkpoints": [row for row in rows if row["cycles"] in CHECKPOINTS],
        "final": rows[-1],
        "history_csv": csv_path.name,
        "figures": figures,
        "caveats": [
            "Calendar comparator vs cycling mixes differences in SoC stress and cycling; not a pure mechanistic decomposition.",
            "BLAST EFC depends on starting q and may differ from 0.8 per daily cycle.",
            "One-day window size affects original BLAST evolution; sensitivity is diagnostic only.",
            "Fixed SoC limits imply declining Ah throughput as capacity fades.",
            "T=25C and current are synthetic, not measured 2p/pack operation.",
            "No microgrid transient or DC/DC physics is simulated by this runner.",
            "Model transfer from original BLAST 46Ah/46.2Ah second-life reference to 44.1Ah thesis case is a hypothesis.",
        ],
    }
    summary = out / "summary.json"
    summary.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                  allow_nan=False) + "\n", encoding="utf-8")
    print(f"BAT26-45: {status} | {rows[-1]['cycles']} cycles | {out.relative_to(REPO)}",
          flush=True)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
