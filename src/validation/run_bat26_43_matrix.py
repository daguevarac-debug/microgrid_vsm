"""BAT26-43: run the existing degraded-BESS test matrix without new physics.

Writes a fresh, uniquely named report directory. In particular, BLAST's
historical results.json is NOT regenerated: its Tests class is discovered by
unittest, not executed through the script's __main__ output writer.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_PARENT = ROOT / "outputs" / "analysis" / "bat26_43_matrix"

# name, test-directory relative to repository, filename, minimum existing test count,
# requires a BLAST-Lite 1.1.0 / Python 3.12.10 installation, use native BLAST Python
GROUPS = (
    ("capacity", "src/validation", "test_aging_capacity_contract.py", 11, False, False),
    ("soc_boundary", "src/validation", "test_soc_variable_capacity_boundary.py", 4, False, False),
    ("snapshot", "src/validation", "test_capacity_snapshot_integration.py", 6, False, False),
    ("signs", "src/validation", "test_bess_sign_coherence.py", 3, False, False),
    ("rc_energy", "src/validation", "test_bess_rc_energy_identity.py", 1, False, False),
    ("dc_energy_limits", "src/validation", "test_bat26_42_energy_and_limits.py", 5, False, False),
    ("dc_link", "src/validation", "test_dclink_dynamics.py", 5, False, False),
    ("dc_dc_separate", "src/validation", "test_dc_dc_adapter.py", 15, False, False),
    ("blast_snapshots", "src/validation", "test_blast_lite_adapter.py", 10, True, False),
    ("blast_efc", "outputs/analysis/bat26_36_efc", "check_efc.py", 7, True, True),
)


def version_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        return None


def blast_python() -> Path | None:
    given = os.environ.get("BLAST_LITE_PYTHON", "").strip()
    if given:
        path = Path(given).expanduser()
    elif os.environ.get("LOCALAPPDATA"):
        path = (Path(os.environ["LOCALAPPDATA"]) / "microgrid_blast_probe_312"
                / "Scripts" / "python.exe")
    else:
        return None
    return path if path.is_file() else None


def main() -> int:
    output = OUT_PARENT / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    native = blast_python()
    metadata_paths = (
        "AGENTS.md", "OCV_SOC.xlsx", "src/bess/model.py",
        "src/bess/aging_capacity.py", "src/bess/blast_lite_adapter.py",
        "src/bess/blast_worker.py", "src/microgrid.py",
        "src/microgrid_bess_pi.py",
        "outputs/analysis/bat26_36_efc/check_efc.py",
        "outputs/analysis/bat26_41_windowed/results.json",
    )
    report = {
        "task": "BAT26-43",
        "status": "IN_PROGRESS",
        "scope": "synthetic/software only; NOT experimental battery or DC/DC validation",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "main_python_version": sys.version.split()[0],
        "blast_python_detected": native is not None,
        "sha256_inputs": {
            name: version_hash(ROOT / name) for name in metadata_paths
        },
        "groups": [],
    }
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if native is not None:
        env["BLAST_LITE_PYTHON"] = str(native)
    total = 0
    for name, folder, pattern, expected, requires_blast, native_python in GROUPS:
        entry = {
            "group": name, "folder": folder, "pattern": pattern,
            "minimum_tests": expected,
        }
        if requires_blast and native is None:
            entry.update(status="NOT_RUN", reason="BLAST Python missing", tests_run=0)
        else:
            executable = native if native_python else Path(sys.executable)
            command = [str(executable), "-B", "-m", "unittest", "discover",
                       "-s", folder, "-p", pattern, "-v"]
            try:
                process = subprocess.run(
                    command, cwd=ROOT, env=env, text=True, capture_output=True,
                    errors="replace", check=False,
                )
                output_text = process.stdout + "\n" + process.stderr
                (output / (name + ".log")).write_text(output_text, encoding="utf-8")
                found = re.search(r"\bRan\s+(\d+)\s+tests?\s+in\b", output_text)
                n_tests = int(found.group(1)) if found else 0
                skipped = re.search(r"\bskipped=(\d+)", output_text)
                has_skips = bool(skipped and int(skipped.group(1)))
                passed = (process.returncode == 0 and n_tests >= expected
                          and not has_skips and re.search(r"(?m)^OK(?:\s|$)", output_text))
                entry.update(
                    status="PASS" if passed else "FAIL",
                    tests_run=n_tests, exit_code=process.returncode,
                    log_file=name + ".log",
                )
                if not passed:
                    entry["reason"] = ("nonzero status, insufficient tests, "
                                       "skips or missing unittest summary")
                if passed:
                    total += n_tests
            except OSError as exc:
                entry.update(status="FAIL", tests_run=0, reason=str(exc))
        report["groups"].append(entry)
        print(f"{name}: {entry['status']} ({entry['tests_run']} tests)", flush=True)

    states = {item["status"] for item in report["groups"]}
    report["tests_passed"] = total
    report["status"] = ("PASS" if states == {"PASS"} else
                        "FAIL" if "FAIL" in states else "INCOMPLETE")
    (output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("BAT26-43:", report["status"], "| passed:", total,
          "| report:", output.relative_to(ROOT))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
