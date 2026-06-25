"""Confirm that the three protected Objective 1 validations still pass.

This regression runner executes the existing validation scripts unchanged:

- ``validate_lcl_no_unphysical_oscillations.py``;
- ``validate_bess_step3.py``;
- ``validate_bess_soc_operational_limits.py``.

The runner uses the active Python interpreter, captures each process output,
checks both its exit code and its script-specific PASS marker, writes a JSON
summary, and returns a nonzero exit code when any validation does not pass.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


THIS_FILE = Path(__file__).resolve()
VALIDATION_DIR = THIS_FILE.parent
REPO_ROOT = THIS_FILE.parents[2]
OUTPUT_PATH_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "objective1_regression"
    / "objective1_regression_summary.json"
)
OUTPUT_TAIL_LINES = 40


@dataclass(frozen=True)
class ValidationSpec:
    """Definition of one protected Objective 1 validation command."""

    name: str
    script_name: str
    pass_pattern: str

    @property
    def script_path(self) -> Path:
        return VALIDATION_DIR / self.script_name


VALIDATIONS = (
    ValidationSpec(
        name="lcl_no_unphysical_oscillations",
        script_name="validate_lcl_no_unphysical_oscillations.py",
        pass_pattern=r"(?m)^status=PASS\s*$",
    ),
    ValidationSpec(
        name="bess_step3",
        script_name="validate_bess_step3.py",
        pass_pattern=r"(?m)^Overall status:\s*PASS\s*$",
    ),
    ValidationSpec(
        name="bess_soc_operational_limits",
        script_name="validate_bess_soc_operational_limits.py",
        pass_pattern=r"(?m)^status=PASS\s*$",
    ),
)


def _tail(text: str, line_count: int = OUTPUT_TAIL_LINES) -> str:
    """Return a compact final section of captured process output."""
    lines = text.splitlines()
    return "\n".join(lines[-line_count:])


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def run_validation(spec: ValidationSpec) -> dict[str, Any]:
    """Execute one validation and classify it from exit code and PASS marker."""
    script_path = spec.script_path
    if not script_path.is_file():
        return {
            "name": spec.name,
            "script": str(script_path.relative_to(REPO_ROOT)),
            "command": [sys.executable, str(script_path)],
            "returncode": None,
            "pass_marker_found": False,
            "status": "FAIL",
            "passed": False,
            "duration_s": 0.0,
            "stdout_tail": "",
            "stderr_tail": f"Validation script not found: {script_path}",
        }

    command = [sys.executable, str(script_path)]
    environment = os.environ.copy()
    environment.setdefault("MPLBACKEND", "Agg")

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    duration_s = time.perf_counter() - started

    pass_marker_found = bool(re.search(spec.pass_pattern, completed.stdout))
    passed = bool(completed.returncode == 0 and pass_marker_found)
    return {
        "name": spec.name,
        "script": str(script_path.relative_to(REPO_ROOT)),
        "command": command,
        "returncode": int(completed.returncode),
        "pass_marker_found": pass_marker_found,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "duration_s": float(duration_s),
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def run_regression(output_path: Path = OUTPUT_PATH_DEFAULT) -> dict[str, Any]:
    """Run all protected Objective 1 validations and save consolidated evidence."""
    results = [run_validation(spec) for spec in VALIDATIONS]
    overall_pass = bool(
        len(results) == len(VALIDATIONS)
        and all(result["passed"] for result in results)
    )
    report: dict[str, Any] = {
        "task": "Confirmar que las validaciones del Objetivo 1 siguen pasando",
        "status": "PASS" if overall_pass else "FAIL",
        "validation_count": len(results),
        "expected_validation_count": len(VALIDATIONS),
        "all_validations_pass": overall_pass,
        "python_executable": sys.executable,
        "repository_root": str(REPO_ROOT),
        "validations": results,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(output_path)
    clean_report = _json_ready(report)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(clean_report, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    for result in results:
        print(f"validation={result['name']}")
        print(f"script={result['script']}")
        print(f"returncode={result['returncode']}")
        print(f"pass_marker_found={result['pass_marker_found']}")
        print(f"status={result['status']}")
    print(f"overall_status={report['status']}")
    print(f"output_path={output_path}")
    return clean_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_regression(output_path=args.output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
