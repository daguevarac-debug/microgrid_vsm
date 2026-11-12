"""IEEE European LV 906-bus benchmark: reproducible OpenDSS snapshot and baseline.

This study is separate from the local VSG solver and does not imply dynamic
co-simulation. Reference data are downloaded from the public OpenDSS mirror.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

SOURCE_BASE = "https://raw.githubusercontent.com/tshort/OpenDSS"
SOURCE_SUBDIR = "Distrib/IEEETestCases/LVTestCase"
CORE_FILES = (
    "Master.dss", "LineCode.txt", "LoadShapes.txt",
    "Lines.txt", "Transformers.txt", "Loads.txt",
)
LOAD_SHAPE_PATTERN = re.compile(r"file\s*=\s*([^\s)]+)", flags=re.IGNORECASE)
THREE_PHASE_CANDIDATES = ("34.1.2.3", "822.1.2.3")
EXPECTED_LINES = 905
EXPECTED_LOADS = 55


def _source_url(source_ref: str, relative_path: str) -> str:
    safe_path = quote(relative_path.replace("\\", "/"), safe="/")
    return f"{SOURCE_BASE}/{quote(source_ref, safe='')}/{SOURCE_SUBDIR}/{safe_path}"


def _download_file(target_dir: Path, source_ref: str, relative_path: str) -> None:
    target = target_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    req = Request(_source_url(source_ref, relative_path), headers={"User-Agent": "microgrid_vsm-ieee-eu-lv/1.0"})
    with urlopen(req, timeout=60) as response:
        data = response.read()
    if not data:
        raise ValueError(f"Source returned empty data: {relative_path}")
    target.write_bytes(data)


def fetch_dataset(target_dir: Path, source_ref: str) -> None:
    """Fetch only files used by the 55 original load shapes; retain their paths."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in CORE_FILES:
        _download_file(target_dir, source_ref, filename)

    shapes = (target_dir / "LoadShapes.txt").read_text(encoding="utf-8-sig", errors="replace")
    shape_files = sorted({
        match.replace("\\", "/")
        for match in LOAD_SHAPE_PATTERN.findall(shapes)
    })
    if len(shape_files) != EXPECTED_LOADS:
        raise AssertionError(f"Expected 55 unique load profiles, found {len(shape_files)}")
    for rel in shape_files:
        relative = Path(rel)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe profile path: {rel}")
        _download_file(target_dir, source_ref, rel)

    manifest = {
        "origin": f"{SOURCE_BASE}/{source_ref}/{SOURCE_SUBDIR}",
        "source_ref": source_ref,
        "note": "Public OpenDSS mirror; SHA-256 pins downloaded bytes, not an upstream release.",
        "files": {},
    }
    for path in sorted(target_dir.rglob("*")):
        if path.is_file() and path.name not in ("source_manifest.json", "_study_master.dss"):
            rel = path.relative_to(target_dir).as_posix()
            manifest["files"][rel] = {
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    (target_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def verify_dataset(target_dir: Path) -> None:
    manifest_path = target_dir / "source_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}; run --download")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, meta in manifest["files"].items():
        path = target_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing benchmark file: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != meta["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {name}")
    if len(manifest["files"]) < 60:
        raise ValueError("Incomplete IEEE European LV feeder download")


def write_study_master(target_dir: Path) -> Path:
    """Avoid the original Master's built-in 1440-step simulation and output files."""
    original = (target_dir / "Master.dss").read_text(encoding="utf-8-sig", errors="replace")
    lines = []
    for line in original.splitlines():
        stripped = line.strip().lower()
        if stripped == "solve":
            break
        if stripped.startswith(("redirect monitors", "new energymeter.", "buscoords ")):
            continue
        lines.append(line)
    required = ("redirect lines.txt", "redirect loads.txt", "redirect transformers.txt")
    code = "\n".join(lines).lower()
    if any(entry not in code for entry in required):
        raise ValueError("Unexpected upstream Master.dss structure; inspect manually")
    study = target_dir / "_study_master.dss"
    study.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return study


def _get_bus_phase_voltage(dss, bus_phase: str) -> float:
    bus, phase_str = bus_phase.split(".")
    phase = int(phase_str)
    if dss.Circuit.SetActiveBus(bus) < 0:
        raise ValueError(f"Bus not in benchmark: {bus}")
    nodes = dss.Bus.Nodes()
    if phase not in nodes:
        raise ValueError(f"Phase {phase} not found at bus {bus}; available={nodes}")
    phase_index = nodes.index(phase)
    pu_mag_angle = dss.Bus.puVmagAngle()
    return float(pu_mag_angle[2 * phase_index])


def _snapshot(dss, study_master: Path, minute: int, pv_kw: float, pv_bus_phases: str) -> dict:
    dss.Basic.ClearAll()
    dss.Text.Command(f'compile "{study_master.resolve().as_posix()}"')
    if dss.Loads.Count() != EXPECTED_LOADS or dss.Lines.Count() != EXPECTED_LINES:
        raise AssertionError(
            f"Invalid topology: {dss.Loads.Count()} loads, {dss.Lines.Count()} lines"
        )
    # Preserve a three-phase DER interface; phase-specific loads remain unbalanced.
    bus_name, *phases = pv_bus_phases.split(".")
    if phases != ["1", "2", "3"]:
        raise ValueError("The preliminary VSG interface requires phases 1, 2, 3")
    for phase in phases:
        _get_bus_phase_voltage(dss, f"{bus_name}.{phase}")

    dss.Text.Command("set controlmode=off")
    dss.Text.Command("set mode=yearly number=1 stepsize=1m")
    if pv_kw > 0:
        dss.Text.Command(
            f"new Generator.PV_3KW phases=3 bus1={pv_bus_phases} "
            f"kV=0.416 conn=wye kW={pv_kw:.9g} kvar=0 model=1"
        )
    dss.Solution.Hour(minute // 60)
    dss.Solution.Seconds((minute % 60) * 60)
    dss.Solution.Solve()
    if not dss.Solution.Converged():
        raise RuntimeError(f"OpenDSS did not converge at minute={minute}, PV={pv_kw}")

    p_load_kw = 0.0
    for load_name in dss.Loads.AllNames():
        dss.Circuit.SetActiveElement(f"Load.{load_name}")
        p_load_kw += sum(dss.CktElement.Powers()[0::2])

    p_source_kw = -float(dss.Circuit.TotalPower()[0])
    p_loss_kw = float(dss.Circuit.Losses()[0]) / 1000.0
    lv_pu = []
    for name in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(name)
        if 0 < dss.Bus.kVBase() < 1:
            lv_pu.extend(float(v) for v in dss.Bus.puVmagAngle()[0::2] if 0 < v < 2)
    if not lv_pu:
        raise AssertionError("No valid LV phase voltages were obtained")

    # Generator output is an explicit commanded setpoint; require power balance.
    imbalance_kw = p_source_kw + pv_kw - p_load_kw - p_loss_kw
    if abs(imbalance_kw) > max(0.10, 0.005 * max(p_load_kw, 1.0)):
        raise AssertionError(
            f"Power balance inconsistency ({imbalance_kw:+.4f} kW); "
            "check phase model, generator and source signs"
        )

    return {
        "minute": minute,
        "pv_bus_phases": pv_bus_phases if pv_kw else "",
        "pv_kw": round(pv_kw, 6),
        "p_load_kw": round(p_load_kw, 6),
        "p_source_kw": round(p_source_kw, 6),
        "p_loss_kw": round(p_loss_kw, 6),
        "power_balance_kw": round(imbalance_kw, 6),
        "min_v_lv_pu": round(min(lv_pu), 7),
        "max_v_lv_pu": round(max(lv_pu), 7),
        "v_near_34_1_pu": round(_get_bus_phase_voltage(dss, "34.1"), 7),
        "v_far_822_3_pu": round(_get_bus_phase_voltage(dss, "822.3"), 7),
        "pv_vs_load_percent": round(100.0 * pv_kw / p_load_kw, 4) if p_load_kw > 0 else None,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/ieee_europe_lv_906"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/analysis/ieee_europe_lv_906"))
    parser.add_argument("--download", action="store_true", help="Fetch public benchmark (55 load profiles).")
    parser.add_argument("--source-ref", default="master", help="Public tshort/OpenDSS ref to fetch and hash.")
    parser.add_argument("--minute", type=int, default=720, help="Snapshot at 0..1439 min (default noon).")
    parser.add_argument("--pv-kw", type=float, default=3.0, help="Static three-phase DG injection at snapshot.")
    parser.add_argument("--baseline-step", type=int, default=60, help="Sampling of 24h baseline; 1 for all minutes.")
    args = parser.parse_args()
    if not (0 <= args.minute < 1440):
        parser.error("--minute must lie in [0,1439]")
    if not (0 < args.baseline_step <= 1440):
        parser.error("--baseline-step must lie in [1,1440]")
    if not math.isfinite(args.pv_kw) or args.pv_kw <= 0:
        parser.error("--pv-kw must be finite and positive")
    if args.download:
        fetch_dataset(args.data_dir, args.source_ref)
    verify_dataset(args.data_dir)
    study_master = write_study_master(args.data_dir)

    try:
        import opendssdirect as dss
    except ImportError as exc:
        raise SystemExit("Missing dependency: python -m pip install opendssdirect.py") from exc

    baseline = [
        _snapshot(dss, study_master, minute, 0, "822.1.2.3")
        for minute in range(0, 1440, args.baseline_step)
    ]
    _write_csv(args.output_dir / "baseline_24h.csv", baseline)

    scenarios = [
        dict(case="base", **_snapshot(dss, study_master, args.minute, 0, "822.1.2.3")),
        dict(case="PV_near", **_snapshot(dss, study_master, args.minute, args.pv_kw, "34.1.2.3")),
        dict(case="PV_far", **_snapshot(dss, study_master, args.minute, args.pv_kw, "822.1.2.3")),
    ]
    _write_csv(args.output_dir / "snapshot_pv_comparison.csv", scenarios)

    summary = {
        "feeder": "IEEE European LV 906-bus (OpenDSS)",
        "mode": "Grid-connected quasi-static power flow; no islanded VSG co-simulation",
        "frequency_hz": 50,
        "nominal_v_ll": 416,
        "loads_count": EXPECTED_LOADS,
        "lines_count": EXPECTED_LINES,
        "pv_model": "Static balanced three-phase unity-PF DG at selected minute; not a 24h irradiance profile",
        "source_manifest": str((args.data_dir / "source_manifest.json").resolve()),
        "baseline_samples": len(baseline),
        "snapshot": scenarios,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
