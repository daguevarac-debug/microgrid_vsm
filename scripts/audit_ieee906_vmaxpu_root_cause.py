"""Diagnostic audit of the 9.54% IEEE European LV (906-bus) 2015 reference discrepancy.

Identifies and quantifies the effect of OpenDSS default Load Vmaxpu=1.05 on
loads declared at kV=0.23 (230 V LN) when the feeder operates at 1.05 pu of
416 V LL (252 V LN). Uses an immutable tshort/OpenDSS commit SHA for provenance
and never modifies canonical Master.dss, Loads.txt, or PR #57 QSTS outputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ieee_europe_lv_906_reference import REFERENCE  # noqa: E402
from ieee_europe_lv_906_study import fetch_dataset, verify_dataset, write_study_master  # noqa: E402

IMMUTABLE_OPENDSS_REF = "5005c668a72d20775f4c2d060feebb2866ba1d38"
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "ieee_europe_lv_906"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "audit_pending_review"

DIAGNOSTIC_VARIANTS = [
    ("canonical_vmaxpu_1p05", []),
    ("pure_pq_vmaxpu_1p10", ["batchedit load..* vmaxpu=1.10"]),
    ("pure_pq_vmaxpu_1p20", ["batchedit load..* vmaxpu=1.20"]),
    ("pure_pq_vmaxpu_1p20_tol1e8", ["batchedit load..* vmaxpu=1.20", "set tolerance=1e-8"]),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_audit(data_dir: Path, output_dir: Path, *, source_ref: str = IMMUTABLE_OPENDSS_REF, download: bool = False) -> dict:
    import opendssdirect as dss
    import dss as dss_py

    data_dir = data_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if download or not (data_dir / "source_manifest.json").is_file():
        fetch_dataset(data_dir, source_ref)
    verify_dataset(data_dir)
    manifest = json.loads((data_dir / "source_manifest.json").read_text(encoding="utf-8"))
    master = write_study_master(data_dir)

    summary_variants: dict[str, dict] = {}
    rows: list[dict] = []
    for vname, cmds in DIAGNOSTIC_VARIANTS:
        max_rel: dict[str, float] = {}
        max_abs: dict[str, float] = {}
        for minute, ref in REFERENCE.items():
            dss.Basic.ClearAll()
            dss.Text.Command(f'compile "{master.as_posix()}"')
            for cmd in cmds:
                dss.Text.Command(cmd)
            dss.Text.Command("set mode=yearly number=1 stepsize=1m")
            dss.Solution.Hour(minute // 60)
            dss.Solution.Seconds((minute % 60) * 60)
            dss.Solution.Solve()
            if not dss.Solution.Converged():
                raise RuntimeError(f"Non-convergence in {vname} at minute={minute}")

            dss.Circuit.SetActiveElement("Transformer.TR1")
            xfmr = dss.CktElement.Powers()
            offset = 2 * dss.CktElement.NumConductors()
            lv_p = tuple(-float(xfmr[offset + 2 * i]) for i in range(3))
            lv_q = tuple(-float(xfmr[offset + 2 * i + 1]) for i in range(3))

            pv: dict[int, list[float]] = {1: [], 2: [], 3: []}
            for bus_name in dss.Circuit.AllBusNames():
                dss.Circuit.SetActiveBus(bus_name)
                if 0 < dss.Bus.kVBase() < 1:
                    for node, mag in zip(dss.Bus.Nodes(), dss.Bus.VMagAngle()[::2]):
                        if node in pv and 0 < mag < 500:
                            pv[node].append(float(mag))
            sim = {
                "transformer_lv_p_kw": lv_p,
                "transformer_lv_q_kvar": lv_q,
                "max_v_volt": tuple(max(pv[k]) for k in (1, 2, 3)),
                "min_v_volt": tuple(min(pv[k]) for k in (1, 2, 3)),
            }
            for metric, expected in ref.items():
                for idx, phase in enumerate("ABC"):
                    actual = sim[metric][idx]
                    err = actual - expected[idx]
                    rel = 100.0 * err / expected[idx]
                    max_abs[metric] = max(max_abs.get(metric, 0.0), abs(err))
                    max_rel[metric] = max(max_rel.get(metric, 0.0), abs(rel))
                    rows.append({
                        "variant": vname,
                        "minute": minute,
                        "phase": phase,
                        "metric": metric,
                        "ieee_2015_ref": expected[idx],
                        "simulated": round(actual, 8),
                        "signed_error": round(err, 8),
                        "rel_error_percent": round(rel, 6),
                    })
        summary_variants[vname] = {
            "commands": cmds,
            "max_abs_error": {k: round(v, 6) for k, v in max_abs.items()},
            "max_rel_error_percent": {k: round(v, 5) for k, v in max_rel.items()},
        }

    # Preserve compact JSON schema plus provenance metadata
    provenance = {
        "source_ref_pinned": manifest.get("source_ref", source_ref),
        "origin": manifest.get("origin"),
        "manifest_sha256": _sha256(data_dir / "source_manifest.json"),
        "core_files_sha256": {
            fn: manifest["files"][fn]["sha256"]
            for fn in ("Master.dss", "Transformers.txt", "Loads.txt", "LoadShapes.txt", "LineCode.txt", "Lines.txt")
        },
        "python_version": platform.python_version(),
        "opendssdirect_version": getattr(dss, "__version__", "unknown"),
        "dss_python_version": getattr(dss_py, "__version__", "unknown"),
        "note": "Diagnostic-only Vmaxpu sweep; canonical Master.dss and PR #57 QSTS outputs remain untouched.",
    }

    csv_path = output_dir / "ieee906_vmaxpu_root_cause.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    json_path = output_dir / "ieee906_vmaxpu_root_cause.json"
    payload = {"provenance": provenance, "variants": summary_variants}
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-ref", default=IMMUTABLE_OPENDSS_REF)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()

    payload = run_audit(args.data_dir, args.output_dir, source_ref=args.source_ref, download=args.download)
    print(json.dumps(payload["variants"], indent=2))


if __name__ == "__main__":
    main()
