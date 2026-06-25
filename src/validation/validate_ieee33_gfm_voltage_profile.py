"""Validate IEEE 33 convergence and nodal-voltage coherence with Objective 1.

The historical Objective 1 reference is ``IEEE33MicrogridBaseline``: the same
IEEE 33 feeder coupled one-way to the original grid-following microgrid. The
current case is ``IEEE33MicrogridWithBESS`` with the selected GFM controller.

Coherence does not require identical active-power injections. It requires:

1. both baseline and GFM IEEE 33 power flows to converge;
2. the feeder-only voltage profile to remain unchanged;
3. finite nodal voltages inside the adopted distribution range;
4. the same minimum-voltage bus and a strongly correlated voltage profile;
5. a voltage-rise pattern per injected kW consistent with the Objective 1 case.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController
from ieee33_coupling import IEEE33MicrogridBaseline, IEEE33MicrogridWithBESS


OUTPUT_DIR_DEFAULT = (
    REPO_ROOT / "outputs" / "validation" / "ieee33_gfm_voltage_profile"
)
SUMMARY_JSON_NAME = "summary.json"
NODE_CSV_NAME = "nodal_voltage_comparison.csv"

VOLTAGE_MIN_PU = 0.90
VOLTAGE_MAX_PU = 1.05
BASE_PROFILE_ATOL_PU = 1e-12
PROFILE_CORRELATION_MIN = 0.999
MAX_ABS_PROFILE_DELTA_PU = 0.002
MAX_RMS_PROFILE_DELTA_PU = 0.001
MAX_NORMALIZED_SENSITIVITY_RELATIVE_ERROR = 0.05
VOLTAGE_RISE_TOL_PU = 1e-10


def _finite_array(values: np.ndarray) -> bool:
    return bool(np.all(np.isfinite(np.asarray(values, dtype=float))))


def _pearson_correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size != b.size or a.size < 2:
        return float("nan")
    if np.std(a) <= 0.0 or np.std(b) <= 0.0:
        return 1.0 if np.allclose(a, b) else float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _check(name: str, condition: bool, detail: str) -> dict[str, Any]:
    status = "PASS" if condition else "FAIL"
    print(f"{name}={status} ({detail})")
    return {
        "name": name,
        "status": status,
        "passed": bool(condition),
        "detail": detail,
    }


def _write_node_csv(
    path: Path,
    *,
    v_base_reference: np.ndarray,
    v_objective1: np.ndarray,
    v_gfm: np.ndarray,
    p_objective1_kw: float,
    p_gfm_kw: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        fieldnames = [
            "bus",
            "v_base_pu",
            "v_objective1_pu",
            "v_gfm_pu",
            "delta_gfm_vs_objective1_pu",
            "rise_objective1_pu",
            "rise_gfm_pu",
            "rise_per_kw_objective1_pu_per_kw",
            "rise_per_kw_gfm_pu_per_kw",
        ]
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(v_base_reference.size):
            rise_objective1 = float(v_objective1[index] - v_base_reference[index])
            rise_gfm = float(v_gfm[index] - v_base_reference[index])
            writer.writerow(
                {
                    "bus": index + 1,
                    "v_base_pu": f"{v_base_reference[index]:.12f}",
                    "v_objective1_pu": f"{v_objective1[index]:.12f}",
                    "v_gfm_pu": f"{v_gfm[index]:.12f}",
                    "delta_gfm_vs_objective1_pu": (
                        f"{v_gfm[index] - v_objective1[index]:.12e}"
                    ),
                    "rise_objective1_pu": f"{rise_objective1:.12e}",
                    "rise_gfm_pu": f"{rise_gfm:.12e}",
                    "rise_per_kw_objective1_pu_per_kw": (
                        f"{rise_objective1 / p_objective1_kw:.12e}"
                    ),
                    "rise_per_kw_gfm_pu_per_kw": (
                        f"{rise_gfm / p_gfm_kw:.12e}"
                    ),
                }
            )


def run_validation(output_dir: Path = OUTPUT_DIR_DEFAULT) -> dict[str, Any]:
    ruta_txt = SRC_DIR / "ieee33bus.txt"
    output_dir = Path(output_dir)

    objective1 = IEEE33MicrogridBaseline(
        str(ruta_txt),
        output_dir=output_dir / "objective1",
    )
    gfm = IEEE33MicrogridWithBESS(
        str(ruta_txt),
        output_dir=output_dir / "gfm",
    )

    print("Running Objective 1 baseline dynamic coupling...")
    p_objective1_kw, objective1_data = objective1.simular()
    v_base_objective1, _ = objective1.flujo_base()
    objective1_base_converged = bool(getattr(objective1.net, "converged", False))
    v_objective1, _ = objective1.flujo_con_dg(p_objective1_kw)
    objective1_dg_converged = bool(getattr(objective1.net, "converged", False))

    print("Running current GFM+BESS dynamic coupling...")
    p_gfm_kw, gfm_data = gfm.simular()
    v_base_gfm, _ = gfm.flujo_base()
    gfm_base_converged = bool(getattr(gfm.net, "converged", False))
    v_gfm, _ = gfm.flujo_con_dg(p_gfm_kw)
    gfm_dg_converged = bool(getattr(gfm.net, "converged", False))

    v_base_objective1_arr = v_base_objective1.to_numpy(dtype=float)
    v_base_gfm_arr = v_base_gfm.to_numpy(dtype=float)
    v_objective1_arr = v_objective1.to_numpy(dtype=float)
    v_gfm_arr = v_gfm.to_numpy(dtype=float)

    same_bus_count = bool(
        v_base_objective1_arr.size
        == v_base_gfm_arr.size
        == v_objective1_arr.size
        == v_gfm_arr.size
        == 33
    )
    base_profile_max_abs_delta = float(
        np.max(np.abs(v_base_gfm_arr - v_base_objective1_arr))
    )
    base_profile_unchanged = bool(
        np.allclose(
            v_base_gfm_arr,
            v_base_objective1_arr,
            atol=BASE_PROFILE_ATOL_PU,
            rtol=0.0,
        )
    )

    voltage_profile_delta = v_gfm_arr - v_objective1_arr
    max_abs_profile_delta = float(np.max(np.abs(voltage_profile_delta)))
    rms_profile_delta = float(np.sqrt(np.mean(np.square(voltage_profile_delta))))
    profile_correlation = _pearson_correlation(v_objective1_arr, v_gfm_arr)

    objective1_min_bus = int(np.argmin(v_objective1_arr)) + 1
    gfm_min_bus = int(np.argmin(v_gfm_arr)) + 1
    same_minimum_bus = objective1_min_bus == gfm_min_bus

    objective1_rise = v_objective1_arr - v_base_objective1_arr
    gfm_rise = v_gfm_arr - v_base_gfm_arr
    objective1_voltage_rise_ok = bool(
        np.all(objective1_rise >= -VOLTAGE_RISE_TOL_PU)
    )
    gfm_voltage_rise_ok = bool(np.all(gfm_rise >= -VOLTAGE_RISE_TOL_PU))

    if p_objective1_kw <= 0.0 or p_gfm_kw <= 0.0:
        normalized_sensitivity_relative_error = float("inf")
        sensitivity_correlation = float("nan")
    else:
        # Exclude the slack bus, whose regulated voltage produces a zero rise.
        objective1_sensitivity = objective1_rise[1:] / p_objective1_kw
        gfm_sensitivity = gfm_rise[1:] / p_gfm_kw
        denominator = max(float(np.linalg.norm(objective1_sensitivity)), 1e-15)
        normalized_sensitivity_relative_error = float(
            np.linalg.norm(gfm_sensitivity - objective1_sensitivity) / denominator
        )
        sensitivity_correlation = _pearson_correlation(
            objective1_sensitivity,
            gfm_sensitivity,
        )

    gfm_voltage_range_ok = bool(
        np.min(v_gfm_arr) >= VOLTAGE_MIN_PU
        and np.max(v_gfm_arr) <= VOLTAGE_MAX_PU
    )
    objective1_voltage_range_ok = bool(
        np.min(v_objective1_arr) >= VOLTAGE_MIN_PU
        and np.max(v_objective1_arr) <= VOLTAGE_MAX_PU
    )
    all_voltage_signals_finite = bool(
        _finite_array(v_base_objective1_arr)
        and _finite_array(v_base_gfm_arr)
        and _finite_array(v_objective1_arr)
        and _finite_array(v_gfm_arr)
    )
    gfm_active = bool(
        isinstance(gfm.controller, GFMController)
        and gfm.controller_state_name == "omega"
        and gfm_data.get("controller_class") == "GFMController"
    )

    checks = [
        _check(
            "objective1_base_flow_converged",
            objective1_base_converged,
            str(objective1_base_converged),
        ),
        _check(
            "objective1_dg_flow_converged",
            objective1_dg_converged,
            str(objective1_dg_converged),
        ),
        _check("gfm_base_flow_converged", gfm_base_converged, str(gfm_base_converged)),
        _check("gfm_dg_flow_converged", gfm_dg_converged, str(gfm_dg_converged)),
        _check("gfm_controller_active", gfm_active, type(gfm.controller).__name__),
        _check("same_33_bus_system", same_bus_count, str(v_gfm_arr.size)),
        _check(
            "base_profile_unchanged",
            base_profile_unchanged,
            f"max_abs_delta={base_profile_max_abs_delta:.3e} pu",
        ),
        _check(
            "all_voltage_signals_finite",
            all_voltage_signals_finite,
            "base, Objective 1, and GFM profiles",
        ),
        _check(
            "objective1_voltage_range",
            objective1_voltage_range_ok,
            f"[{np.min(v_objective1_arr):.6f}, {np.max(v_objective1_arr):.6f}] pu",
        ),
        _check(
            "gfm_voltage_range",
            gfm_voltage_range_ok,
            f"[{np.min(v_gfm_arr):.6f}, {np.max(v_gfm_arr):.6f}] pu",
        ),
        _check(
            "same_minimum_voltage_bus",
            same_minimum_bus,
            f"Objective1={objective1_min_bus}, GFM={gfm_min_bus}",
        ),
        _check(
            "profile_correlation",
            bool(
                np.isfinite(profile_correlation)
                and profile_correlation >= PROFILE_CORRELATION_MIN
            ),
            f"correlation={profile_correlation:.12f}",
        ),
        _check(
            "maximum_profile_difference",
            max_abs_profile_delta <= MAX_ABS_PROFILE_DELTA_PU,
            f"max_abs={max_abs_profile_delta:.6e} pu",
        ),
        _check(
            "rms_profile_difference",
            rms_profile_delta <= MAX_RMS_PROFILE_DELTA_PU,
            f"rms={rms_profile_delta:.6e} pu",
        ),
        _check(
            "voltage_rise_direction",
            objective1_voltage_rise_ok and gfm_voltage_rise_ok,
            "DG injection does not reduce nodal voltage beyond tolerance",
        ),
        _check(
            "per_kw_voltage_sensitivity",
            bool(
                np.isfinite(normalized_sensitivity_relative_error)
                and normalized_sensitivity_relative_error
                <= MAX_NORMALIZED_SENSITIVITY_RELATIVE_ERROR
                and np.isfinite(sensitivity_correlation)
                and sensitivity_correlation >= PROFILE_CORRELATION_MIN
            ),
            (
                f"relative_error={normalized_sensitivity_relative_error:.6e}, "
                f"correlation={sensitivity_correlation:.12f}"
            ),
        ),
    ]

    status = "PASS" if all(check["passed"] for check in checks) else "FAIL"
    summary: dict[str, Any] = {
        "task": (
            "Confirmar convergencia IEEE 33 y coherencia del perfil de tension "
            "con el baseline del Objetivo 1"
        ),
        "status": status,
        "reference_case": "IEEE33MicrogridBaseline (Objective 1)",
        "current_case": "IEEE33MicrogridWithBESS with active GFMController",
        "p_objective1_kw": float(p_objective1_kw),
        "p_gfm_kw": float(p_gfm_kw),
        "objective1_min_voltage_pu": float(np.min(v_objective1_arr)),
        "gfm_min_voltage_pu": float(np.min(v_gfm_arr)),
        "objective1_min_voltage_bus": objective1_min_bus,
        "gfm_min_voltage_bus": gfm_min_bus,
        "base_profile_max_abs_delta_pu": base_profile_max_abs_delta,
        "profile_correlation": profile_correlation,
        "max_abs_profile_delta_pu": max_abs_profile_delta,
        "rms_profile_delta_pu": rms_profile_delta,
        "sensitivity_correlation": sensitivity_correlation,
        "normalized_sensitivity_relative_error": (
            normalized_sensitivity_relative_error
        ),
        "thresholds": {
            "voltage_min_pu": VOLTAGE_MIN_PU,
            "voltage_max_pu": VOLTAGE_MAX_PU,
            "profile_correlation_min": PROFILE_CORRELATION_MIN,
            "max_abs_profile_delta_pu": MAX_ABS_PROFILE_DELTA_PU,
            "max_rms_profile_delta_pu": MAX_RMS_PROFILE_DELTA_PU,
            "max_normalized_sensitivity_relative_error": (
                MAX_NORMALIZED_SENSITIVITY_RELATIVE_ERROR
            ),
        },
        "checks": checks,
        "objective1_dynamic_samples": int(len(objective1_data["t"])),
        "gfm_dynamic_samples": int(len(gfm_data["t"])),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    node_csv_path = output_dir / NODE_CSV_NAME
    summary_json_path = output_dir / SUMMARY_JSON_NAME
    _write_node_csv(
        node_csv_path,
        v_base_reference=v_base_objective1_arr,
        v_objective1=v_objective1_arr,
        v_gfm=v_gfm_arr,
        p_objective1_kw=float(p_objective1_kw),
        p_gfm_kw=float(p_gfm_kw),
    )
    with summary_json_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"p_objective1_kw={p_objective1_kw:.12f}")
    print(f"p_gfm_kw={p_gfm_kw:.12f}")
    print(f"objective1_min_voltage_pu={np.min(v_objective1_arr):.12f}")
    print(f"gfm_min_voltage_pu={np.min(v_gfm_arr):.12f}")
    print(f"profile_correlation={profile_correlation:.12f}")
    print(f"max_abs_profile_delta_pu={max_abs_profile_delta:.6e}")
    print(f"overall_status={status}")
    print(f"summary_path={summary_json_path}")
    print(f"node_csv_path={node_csv_path}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_validation(output_dir=args.output_dir)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
