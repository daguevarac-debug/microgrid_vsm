"""Record DC-link energy signals for the selected GFM severe load step.

Scope:
- Reproduce the selected GFM point (M, D) = (80, 1500).
- Apply the severe 40% active-power load step with the BESS connected.
- Save Vdc, load power, PV-source DC power, BESS DC power and BESS current.
- Do not modify plant equations, controller laws or acceptance criteria.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.gfm_controller import GFMController
from microgrid import Microgrid, MicrogridWithBESS


GFM_SELECTED_M = 80.0
GFM_SELECTED_D = 1500.0
SEVERE_T_END_S = 6.5
SCENARIO_NAME = "gfm_selected_load_step_40_with_bess_energy_diagnostic"
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "dclink_energy_diagnostic"
CSV_PATH = OUTPUT_DIR / "gfm_m80_d1500_severe_40pct_energy_signals.csv"
SUMMARY_PATH = OUTPUT_DIR / "gfm_m80_d1500_severe_40pct_energy_summary.json"
CSV_COLUMNS = (
    "time_s",
    "vdc_v",
    "p_load_w",
    "p_source_pv_dc_w",
    "p_bess_dc_w",
    "i_bess_a",
)


def _reference_active_power_w() -> float:
    """Return the same available active-power reference used by GFM tuning."""
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def _build_scenario() -> tuple[MicrogridWithBESS, list[float], dict[str, float]]:
    """Build the selected-GFM severe 40% load-step case with BESS enabled."""
    p_load_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_load_post = float(
        p_load_pre * (1.0 + MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT)
    )
    t_step = float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
    p_ref_w = _reference_active_power_w()

    controller = GFMController(
        p_ref=p_ref_w,
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    model = MicrogridWithBESS(
        controller=controller,
        load_profile=lambda t: p_load_pre if t < t_step else p_load_post,
    )
    initial_state = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
    metadata = {
        "p_ref_w": p_ref_w,
        "p_load_pre_step_w": p_load_pre,
        "p_load_post_step_w": p_load_post,
        "load_step_pct": 100.0 * (p_load_post - p_load_pre) / p_load_pre,
        "t_step_s": t_step,
    }
    return model, initial_state, metadata


def _source_power_w(model: MicrogridWithBESS, t: float, vdc: float) -> float:
    """Return PV power injected into the DC link as Vdc * Ipv."""
    irradiance = float(model.irradiance_profile(t))
    cell_temperature_c = float(model.temperature_profile(t))
    ipv = model.plant.pv_current(
        max(float(vdc), 0.0),
        irradiance,
        cell_temperature_c,
    )
    return float(vdc) * float(ipv)


def _collect_signals(
    model: MicrogridWithBESS,
    t: np.ndarray,
    y: np.ndarray,
) -> dict[str, np.ndarray]:
    """Collect the five requested time-domain signals."""
    signals = {
        "vdc_v": np.zeros_like(t, dtype=float),
        "p_load_w": np.zeros_like(t, dtype=float),
        "p_source_pv_dc_w": np.zeros_like(t, dtype=float),
        "p_bess_dc_w": np.zeros_like(t, dtype=float),
        "i_bess_a": np.zeros_like(t, dtype=float),
    }
    for k, tk in enumerate(t):
        state = y[:, k]
        integrated = model.integrated_signals(float(tk), state)
        vdc = float(integrated["Vdc"])
        signals["vdc_v"][k] = vdc
        signals["p_load_w"][k] = float(integrated["p_load"])
        signals["p_source_pv_dc_w"][k] = _source_power_w(
            model,
            float(tk),
            vdc,
        )
        signals["p_bess_dc_w"][k] = float(integrated["p_bess_dc"])
        signals["i_bess_a"][k] = float(integrated["i_bess"])
    return signals


def _write_csv(
    output_path: Path,
    t: np.ndarray,
    signals: dict[str, np.ndarray],
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for k, tk in enumerate(t):
            writer.writerow(
                {
                    "time_s": float(tk),
                    "vdc_v": float(signals["vdc_v"][k]),
                    "p_load_w": float(signals["p_load_w"][k]),
                    "p_source_pv_dc_w": float(
                        signals["p_source_pv_dc_w"][k]
                    ),
                    "p_bess_dc_w": float(signals["p_bess_dc_w"][k]),
                    "i_bess_a": float(signals["i_bess_a"][k]),
                }
            )


def _write_summary(output_path: Path, summary: dict[str, Any]) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, indent=2, sort_keys=True)
        output_file.write("\n")


def run_diagnostic(
    csv_path: Path = CSV_PATH,
    summary_path: Path = SUMMARY_PATH,
) -> dict[str, Any]:
    """Run the severe case and persist the requested energy signals."""
    model, initial_state, metadata = _build_scenario()
    solution = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, SEVERE_T_END_S),
        initial_state,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )
    signals = _collect_signals(model, solution.t, solution.y)

    states_finite = bool(
        np.all(np.isfinite(solution.t)) and np.all(np.isfinite(solution.y))
    )
    signals_finite = bool(
        all(np.all(np.isfinite(values)) for values in signals.values())
    )
    scenario_configuration_ok = bool(
        model.controller_state_name == "omega"
        and len(initial_state) == 15
        and abs(metadata["load_step_pct"] - 40.0) <= 1e-9
        and SEVERE_T_END_S >= metadata["t_step_s"] + 5.5
    )
    vdc_positive = bool(np.all(signals["vdc_v"] > 0.0))
    bess_power_identity_ok = bool(
        np.allclose(
            signals["p_bess_dc_w"],
            signals["vdc_v"] * signals["i_bess_a"],
            rtol=1e-9,
            atol=1e-8,
        )
    )
    acquisition_ok = bool(
        solution.success
        and states_finite
        and signals_finite
        and scenario_configuration_ok
        and vdc_positive
        and bess_power_identity_ok
    )

    _write_csv(csv_path, solution.t, signals)
    summary: dict[str, Any] = {
        "scenario": SCENARIO_NAME,
        "status": "PASS" if acquisition_ok else "FAIL",
        "scope": "signal_acquisition_only",
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "bess_active": True,
        **metadata,
        "t_start_s": float(SIM_T_START_S_DEFAULT),
        "t_end_s": SEVERE_T_END_S,
        "controller_state_name": model.controller_state_name,
        "state_count": len(initial_state),
        "solver_success": bool(solution.success),
        "solver_message": str(solution.message),
        "states_finite": states_finite,
        "signals_finite": signals_finite,
        "scenario_configuration_ok": scenario_configuration_ok,
        "vdc_positive": vdc_positive,
        "bess_power_identity_ok": bess_power_identity_ok,
        "source_power_definition": "p_source_pv_dc_w = Vdc * Ipv",
        "n_time_points": int(solution.t.size),
        "nfev": int(solution.nfev),
        "csv_columns": list(CSV_COLUMNS),
        "csv_path": str(Path(csv_path)),
        "vdc_min_v": float(np.min(signals["vdc_v"])),
        "vdc_max_v": float(np.max(signals["vdc_v"])),
        "p_load_min_w": float(np.min(signals["p_load_w"])),
        "p_load_max_w": float(np.max(signals["p_load_w"])),
        "p_source_pv_dc_min_w": float(
            np.min(signals["p_source_pv_dc_w"])
        ),
        "p_source_pv_dc_max_w": float(
            np.max(signals["p_source_pv_dc_w"])
        ),
        "p_bess_dc_min_w": float(np.min(signals["p_bess_dc_w"])),
        "p_bess_dc_max_w": float(np.max(signals["p_bess_dc_w"])),
        "i_bess_min_a": float(np.min(signals["i_bess_a"])),
        "i_bess_max_a": float(np.max(signals["i_bess_a"])),
    }
    _write_summary(summary_path, summary)

    print(f"scenario={summary['scenario']}")
    print(f"status={summary['status']}")
    print(f"load_step_pct={summary['load_step_pct']:.6f}")
    print(f"solver_success={summary['solver_success']}")
    print(f"signals_finite={summary['signals_finite']}")
    print(f"csv_path={csv_path}")
    print(f"summary_path={summary_path}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record DC-link energy signals for the selected GFM severe 40% "
            "load-step case with BESS."
        )
    )
    parser.add_argument("--csv-output", type=Path, default=CSV_PATH)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = run_diagnostic(
        csv_path=args.csv_output,
        summary_path=args.summary_output,
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
