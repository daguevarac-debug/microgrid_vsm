"""Validate one minimal BESS DC-link PI tuning candidate.

This is deliberately not an optimization or parameter sweep. The single pair
(Kp, Ki) = (170 W/V, 10 W/(V*s)) is evaluated in the selected GFM severe 40%
load-step scenario against the repository's existing DC-link and frequency
criteria plus mandatory BESS operating limits.
"""

from __future__ import annotations

import argparse
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
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from tuning_metrics import dc_link_performance_metrics, frequency_performance_metrics


GFM_SELECTED_M = 80.0
GFM_SELECTED_D = 1500.0
PI_KP_W_PER_V = 170.0
PI_KI_W_PER_V_S = 10.0
T_END_S = 6.5
SCENARIO_NAME = "gfm_m80_d1500_bess_pi_minimal_tuning_severe_40pct"
OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "dc_link_regulation"
    / "gfm_m80_d1500_bess_pi_minimal_tuning.json"
)
LIMIT_ATOL = 1e-8


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def build_model() -> MicrogridWithBESSPI:
    """Build the only candidate admitted by this minimal tuning step."""
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT)
    controller = GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=PI_KP_W_PER_V,
        ki_w_per_v_s=PI_KI_W_PER_V_S,
    )
    return MicrogridWithBESSPI(
        controller=controller,
        dc_link_bess_pi=pi,
        load_profile=lambda t: (
            p_pre if t < MICROGRID_LOAD_STEP_TIME_S_DEFAULT else p_post
        ),
    )


def classify_status(
    *,
    solver_success: bool,
    states_finite: bool,
    dc_criteria_pass: bool,
    frequency_criteria_pass: bool,
    bess_limits_pass: bool,
) -> str:
    return (
        "PASS"
        if all(
            (
                solver_success,
                states_finite,
                dc_criteria_pass,
                frequency_criteria_pass,
                bess_limits_pass,
            )
        )
        else "FAIL"
    )


def run_validation(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Run the single minimal candidate and save a reproducible JSON record."""
    model = build_model()
    initial_state = model.initial_state_with_bess(
        vdc0=SIM_VDC0_V_DEFAULT,
        xi_bess_vdc0_v_s=0.0,
    )
    solution = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, T_END_S),
        initial_state,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    n = solution.t.size
    vdc = solution.y[0]
    frequency_hz = solution.y[10] / (2.0 * np.pi)
    i_bess = np.zeros(n, dtype=float)
    p_bess = np.zeros(n, dtype=float)
    p_ref = np.zeros(n, dtype=float)
    p_min = np.zeros(n, dtype=float)
    p_max = np.zeros(n, dtype=float)
    soc = np.zeros(n, dtype=float)
    soh = np.zeros(n, dtype=float)
    saturated = np.zeros(n, dtype=bool)
    anti_windup = np.zeros(n, dtype=bool)

    for k, tk in enumerate(solution.t):
        signal = model.integrated_signals(float(tk), solution.y[:, k])
        i_bess[k] = float(signal["i_bess"])
        p_bess[k] = float(signal["p_bess_dc"])
        p_ref[k] = float(signal["p_bess_ref_w"])
        p_min[k] = float(signal["p_bess_ref_min_w"])
        p_max[k] = float(signal["p_bess_ref_max_w"])
        soc[k] = float(signal["soc_bess"])
        soh[k] = float(signal["soh_bess"])
        saturated[k] = bool(signal["pi_saturated"])
        anti_windup[k] = bool(signal["anti_windup_active"])

    dc_metrics = dc_link_performance_metrics(
        solution.t,
        vdc,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )
    frequency_metrics = frequency_performance_metrics(
        solution.t,
        frequency_hz,
        MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    )

    states_finite = bool(np.all(np.isfinite(solution.y)))
    signals_finite = bool(
        all(
            np.all(np.isfinite(values))
            for values in (vdc, frequency_hz, i_bess, p_bess, p_ref, p_min, p_max, soc, soh)
        )
    )
    current_limit = np.array(
        [model._available_i_bess_max(value) for value in soh], dtype=float
    )
    current_limit_pass = bool(np.all(np.abs(i_bess) <= current_limit + LIMIT_ATOL))
    power_limit_pass = bool(
        np.all(p_ref >= p_min - LIMIT_ATOL)
        and np.all(p_ref <= p_max + LIMIT_ATOL)
        and np.all(p_bess >= p_min - LIMIT_ATOL)
        and np.all(p_bess <= p_max + LIMIT_ATOL)
    )
    soc_limit_pass = bool(
        np.all(soc >= model.bess.soc_min - LIMIT_ATOL)
        and np.all(soc <= model.bess.soc_max + LIMIT_ATOL)
    )
    soh_limit_pass = bool(
        np.all(soh >= model.bess.soh_min - LIMIT_ATOL)
        and np.all(soh <= 1.0 + LIMIT_ATOL)
    )
    bess_limits_pass = bool(
        signals_finite
        and current_limit_pass
        and power_limit_pass
        and soc_limit_pass
        and soh_limit_pass
    )

    status = classify_status(
        solver_success=bool(solution.success),
        states_finite=states_finite,
        dc_criteria_pass=bool(dc_metrics["vdc_criteria_pass"]),
        frequency_criteria_pass=bool(frequency_metrics["frequency_criteria_pass"]),
        bess_limits_pass=bess_limits_pass,
    )

    post = solution.t >= MICROGRID_LOAD_STEP_TIME_S_DEFAULT
    result: dict[str, Any] = {
        "scenario": SCENARIO_NAME,
        "status": status,
        "selection_method": "single_candidate_minimal_adjustment",
        "candidate_count": 1,
        "Kp_w_per_v": PI_KP_W_PER_V,
        "Ki_w_per_v_s": PI_KI_W_PER_V_S,
        "Kp_basis": "340 V * legacy 0.5 A/V = 170 W/V",
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "solver_success": bool(solution.success),
        "solver_message": str(solution.message),
        "states_finite": states_finite,
        "signals_finite": signals_finite,
        "state_count": int(solution.y.shape[0]),
        "t_step_s": float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT),
        "t_end_s": T_END_S,
        **dc_metrics,
        **frequency_metrics,
        "vdc_final_v": float(vdc[-1]),
        "vdc_final_reference_error_v": float(SIM_VDC0_V_DEFAULT - vdc[-1]),
        "i_bess_min_post_step_a": float(np.min(i_bess[post])),
        "i_bess_max_post_step_a": float(np.max(i_bess[post])),
        "p_bess_min_post_step_w": float(np.min(p_bess[post])),
        "p_bess_max_post_step_w": float(np.max(p_bess[post])),
        "soc_min_observed": float(np.min(soc)),
        "soc_max_observed": float(np.max(soc)),
        "soh_min_observed": float(np.min(soh)),
        "current_limit_pass": current_limit_pass,
        "power_limit_pass": power_limit_pass,
        "soc_limit_pass": soc_limit_pass,
        "soh_limit_pass": soh_limit_pass,
        "bess_limits_pass": bess_limits_pass,
        "pi_saturation_fraction": float(np.mean(saturated)),
        "anti_windup_fraction": float(np.mean(anti_windup)),
        "controller_modified_beyond_pi": False,
        "broad_optimization_performed": False,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"scenario={result['scenario']}")
    print(f"status={result['status']}")
    print(f"Kp_w_per_v={result['Kp_w_per_v']}")
    print(f"Ki_w_per_v_s={result['Ki_w_per_v_s']}")
    print(f"vdc_criteria_pass={result['vdc_criteria_pass']}")
    print(f"frequency_criteria_pass={result['frequency_criteria_pass']}")
    print(f"bess_limits_pass={result['bess_limits_pass']}")
    print(f"vdc_final_v={result['vdc_final_v']:.6f}")
    print(f"output_path={output_path}")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_validation(output_path=args.output)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
