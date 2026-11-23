"""BAT26-47: original BLAST 100-day partition sensitivity (1 / 2 / 4 windows).

Uses EXACT SAME 129 sampled profile points, time coverage and battery model.
A difference between partitions is a numerical-sensitivity diagnostic; the
script deliberately has no ungrounded physical convergence threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.run_bat26_45_multicycle import (
    INITIAL_CASE_AH, NOMINAL_AH, daily_profile, _verify_original_blast,
)

OUT_PARENT = ROOT / "outputs" / "analysis" / "bat26_47_blast_partition"
PARTITIONS = {
    1: ((0, 128),),
    2: ((0, 96), (96, 128)),
    4: ((0, 24), (24, 72), (72, 96), (96, 128)),
}


def check_partition(partition: tuple[tuple[int, int], ...],
                    n_points: int = 129) -> None:
    if not partition or partition[0][0] != 0 or partition[-1][1] != n_points - 1:
        raise ValueError("partition does not cover whole daily profile")
    if any(b <= a for a, b in partition):
        raise ValueError("empty or reversed BLAST window")
    if any(prev[1] != curr[0] for prev, curr in zip(partition, partition[1:])):
        raise ValueError("partition has a gap or duplicated physical interval")
    covered = sum(b - a for a, b in partition)
    if covered != n_points - 1:
        raise ValueError("partition does not cover each physical interval once")


def run_partition(Battery, days: int, partition: tuple[tuple[int, int], ...]) -> dict:
    check_partition(partition)
    battery = Battery()
    q0 = float(battery.outputs["q"][-1])
    last_end = None
    for day in range(1, days + 1):
        t, soc, temp = daily_profile(day)
        if last_end is not None and (float(t[0]), float(soc[0]),
                                    float(temp[0])) != last_end:
            raise RuntimeError("BLAST day boundaries are not continuous")
        for a, b in partition:
            battery.update_battery_state(t[a:b + 1], soc[a:b + 1], temp[a:b + 1])
        last_end = (float(t[-1]), float(soc[-1]), float(temp[-1]))

    q = float(battery.outputs["q"][-1])
    soh = INITIAL_CASE_AH / NOMINAL_AH * q / q0
    result = {
        "days": days,
        "number_windows_per_day": len(partition),
        "total_windows": days * len(partition),
        "q0": q0,
        "q_final": q,
        "soh_final_pct": 100.0 * soh,
        "qeff_final_ah": INITIAL_CASE_AH * q / q0,
        "efc_blast": float(battery.stressors["efc"][-1]),
        "nominal_efc": days * 0.8,
        "calendar_loss": float(battery.states["qLoss_t"][-1]),
        "cycle_loss": float(battery.states["qLoss_EFC"][-1]),
        "physical_segments_per_day": 128,
        "soh_operational_limit_pct": 50.0,
    }
    if not (0.5 <= soh <= INITIAL_CASE_AH / NOMINAL_AH
            and np.isfinite(result["efc_blast"])
            and result["efc_blast"] >= 0.0):
        raise RuntimeError("unexpected BLAST result outside model domain")
    return result


def _arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    opts = _arguments()
    if not 1 <= opts.days <= 100:
        raise SystemExit("BAT26-47 audit duration must be 1..100 days")
    Battery, hashes = _verify_original_blast()
    out = OUT_PARENT / datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ"
    )
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "task": "BAT26-47", "component": "BLAST_partition_sensitivity",
        "status": "IN_PROGRESS",
        "physical_validation": "NOT_EVALUABLE",
        "convergence_claim": "NOT_ESTABLISHED_NO_PHYSICAL_TOLERANCE",
        "python_version": sys.version.split()[0],
        "original_blast_sha256": hashes,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=False,
        ).stdout.strip(),
        "same_input_data_all_cases": True,
        "profile_kind": "synthetic, SoC 0.5->0.1->0.9->0.5, 25C, 24h/day",
        "days": opts.days, "results": [], "comparisons": [],
        "error": None,
    }
    try:
        for n in (1, 2, 4):
            entry = run_partition(Battery, opts.days, PARTITIONS[n])
            report["results"].append(entry)
            print(f"{n} window/day: SoH={entry['soh_final_pct']:.8f}% "
                  f"EFC={entry['efc_blast']:.7f}", flush=True)
        baseline = report["results"][0]
        report["comparisons"] = [{
            "window_count": entry["number_windows_per_day"],
            "delta_soh_pp_vs_1window":
                entry["soh_final_pct"] - baseline["soh_final_pct"],
            "delta_efc_vs_1window": entry["efc_blast"] - baseline["efc_blast"],
            "delta_qeff_ah_vs_1window":
                entry["qeff_final_ah"] - baseline["qeff_final_ah"],
        } for entry in report["results"][1:]]
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = f"{type(exc).__name__}: {exc}"
    (out / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"BAT26-47 BLAST {report['status']} | {out.relative_to(ROOT)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
