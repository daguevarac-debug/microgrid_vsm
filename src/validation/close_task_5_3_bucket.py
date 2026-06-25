"""Formally close the Task 5.3 bucket from the severe 40% scenario only.

The bucket is CLOSED only when the severe GFM+BESS+PI scenario simultaneously
meets:

- the existing frequency criteria;
- the existing DC-link criteria;
- the mandatory BESS current, power, SoC and SoH restrictions;
- numerical validity and explicit BESS activation.

Any failed or missing condition leaves the bucket OPEN. No controller or plant
parameter is modified by this closure script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.validate_dc_link_pi_scenarios import (
    OUTPUT_DIR,
    SEVERE_SCENARIO,
    run_scenario,
)


OUTPUT_PATH = OUTPUT_DIR / "task_5_3_bucket_closure.json"


REQUIRED_CHECKS = (
    "solver_success",
    "states_finite",
    "signals_finite",
    "bess_active",
    "frequency_criteria_pass",
    "vdc_criteria_pass",
    "current_limit_pass",
    "power_limit_pass",
    "soc_limit_pass",
    "soh_limit_pass",
    "bess_limits_pass",
)


def classify_bucket(record: dict[str, Any]) -> tuple[str, list[str]]:
    """Return CLOSED only for the valid severe 40% scenario and all checks true."""
    failed: list[str] = []

    if record.get("scenario") != SEVERE_SCENARIO.name:
        failed.append("severe_scenario_identity")
    try:
        load_step_pct = float(record.get("load_step_pct"))
    except (TypeError, ValueError):
        load_step_pct = float("nan")
    if abs(load_step_pct - 40.0) > 1e-9:
        failed.append("severe_load_step_40pct")

    for check in REQUIRED_CHECKS:
        if record.get(check) is not True:
            failed.append(check)

    return ("CLOSED" if not failed else "OPEN", failed)


def build_closure_report(severe_record: dict[str, Any]) -> dict[str, Any]:
    """Create the formal bucket decision with an auditable condition matrix."""
    bucket_status, failed_checks = classify_bucket(severe_record)
    conditions = {
        "severe_scenario_40pct": bool(
            severe_record.get("scenario") == SEVERE_SCENARIO.name
            and abs(float(severe_record.get("load_step_pct", 0.0)) - 40.0) <= 1e-9
        ),
        "frequency_pass": severe_record.get("frequency_criteria_pass") is True,
        "dc_link_pass": severe_record.get("vdc_criteria_pass") is True,
        "bess_restrictions_pass": severe_record.get("bess_limits_pass") is True,
        "bess_active": severe_record.get("bess_active") is True,
        "numerical_validity": bool(
            severe_record.get("solver_success") is True
            and severe_record.get("states_finite") is True
            and severe_record.get("signals_finite") is True
        ),
    }
    return {
        "task": "5.3",
        "bucket": "dc_link_regulation",
        "bucket_status": bucket_status,
        "closure_rule": (
            "CLOSED only if the severe 40% scenario passes frequency, DC-link "
            "and all BESS operating restrictions"
        ),
        "conditions": conditions,
        "failed_checks": failed_checks,
        "severe_scenario": severe_record,
        "controller_modified_during_closure": False,
    }


def run_bucket_closure(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Rerun the severe scenario, evaluate the closure gate and save JSON."""
    severe_record = run_scenario(SEVERE_SCENARIO, output_dir=Path(output_path).parent)
    report = build_closure_report(severe_record)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(output_path)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(report, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"scenario={severe_record['scenario']}")
    print(f"frequency_pass={report['conditions']['frequency_pass']}")
    print(f"dc_link_pass={report['conditions']['dc_link_pass']}")
    print(
        "bess_restrictions_pass="
        f"{report['conditions']['bess_restrictions_pass']}"
    )
    print(f"task_5_3_bucket_status={report['bucket_status']}")
    print(f"failed_checks={','.join(report['failed_checks'])}")
    print(f"output_path={output_path}")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_bucket_closure(output_path=args.output)
    return 0 if report["bucket_status"] == "CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
