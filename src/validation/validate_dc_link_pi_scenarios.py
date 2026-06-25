"""Validate Task 5.3 base and severe DC-link regulation scenarios.

Both scenarios use the selected GFM point, the accepted minimal BESS PI gains,
and an explicitly enabled BESS:

- base load step: 20%,
- severe load step: 40%.

Each scenario is evaluated with the repository's existing DC-link and frequency
criteria plus mandatory BESS current, power, SoC and SoH limits. Separate JSON
records and one combined summary are written under
``outputs/validation/dc_link_regulation/``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
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
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)


T_END_S = 6.5
LIMIT_ATOL = 1e-8
OUTPUT_DIR = REPO_ROOT / "outputs" / "validation" / "dc_link_regulation"
SUMMARY_OUTPUT = OUTPUT_DIR / "task_5_3_dc_link_pi_validation_summary.json"


@dataclass(frozen=True)
class ScenarioSpec:
    """Fixed Task 5.3 scenario definition."""

    name: str
    label: str
    step_fraction: float
    output_filename: str

    @property
    def step_pct(self) -> float:
        return 100.0 * self.step_fraction


BASE_SCENARIO = ScenarioSpec(
    name="gfm_m80_d1500_bess_pi_base_20pct",
    label="base",
    step_fraction=MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    output_filename="gfm_m80_d1500_bess_pi_base_20pct.json",
)
SEVERE_SCENARIO = ScenarioSpec(
    name="gfm_m80_d1500_bess_pi_severe_40pct",
    label="severe",
    step_fraction=MICROGRID_LOAD_STEP_SEVERE_FRACTION_DEFAULT,
    output_filename="gfm_m80_d1500_bess_pi_severe_40pct.json",
)
SCENARIOS = (BASE_SCENARIO, SEVERE_SCENARIO)


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def build_model(spec: ScenarioSpec) -> MicrogridWithBESSPI:
    """Build one fixed GFM+BESS+PI scenario with BESS explicitly enabled."""
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + spec.step_fraction)
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
        bess_enabled=True,
        load_profile=lambda t: (
            p_pre if t < MICROGRID_LOAD_STEP_TIME_S_DEFAULT else p_post
        ),
    )


def classify_scenario_status(
    *,
    solver_success: bool,
    states_finite: bool,
    dc_criteria_pass: bool,
    frequency_criteria_pass: bool,
    bess_limits_pass: bool,
    bess_active: bool,
) -> str:
    """Return PASS only when all existing criteria and BESS activation hold."""
    return (
        "PASS"
        if all(
            (
                solver_success,
                states_finite,
                dc_criteria_pass,
                frequency_criteria_pass,
                bess_limits_pass,
                bess_active,
            )
        )
        else "FAIL"
    )


def classify_overall_status(records: list[dict[str, Any]]) -> str:
    """Task 5.3 passes only when both required scenarios pass."""
    required_names = {spec.name for spec in SCENARIOS}
    actual_names = {str(record.get("scenario")) for record in records}
    if actual_names != required_names:
        return "FAIL"
    return "PASS" if all(record.get("status") == "PASS" for record in records) else "FAIL"


def _json_ready(record: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            value = None
        clean[key] = value
    return clean


def run_scenario(spec: ScenarioSpec, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    """Simulate, evaluate and save one Task 5.3 scenario."""
    model = build_model(spec)
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
    enabled = np.zeros(n, dtype=bool)

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
        enabled[k] = bool(signal["bess_enabled"])

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
            for values in (
                vdc,
                frequency_hz,
                i_bess,
                p_bess,
                p_ref,
                p_min,
                p_max,
                soc,
                soh,
            )
        )
    )
    current_limit = np.asarray(
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
    bess_active = bool(model.bess_enabled and np.all(enabled))
    bess_limits_pass = bool(
        signals_finite
        and current_limit_pass
        and power_limit_pass
        and soc_limit_pass
        and soh_limit_pass
    )

    status = classify_scenario_status(
        solver_success=bool(solution.success),
        states_finite=states_finite,
        dc_criteria_pass=bool(dc_metrics["vdc_criteria_pass"]),
        frequency_criteria_pass=bool(frequency_metrics["frequency_criteria_pass"]),
        bess_limits_pass=bess_limits_pass,
        bess_active=bess_active,
    )

    post = solution.t >= MICROGRID_LOAD_STEP_TIME_S_DEFAULT
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + spec.step_fraction)
    record: dict[str, Any] = {
        "scenario": spec.name,
        "scenario_label": spec.label,
        "status": status,
        "load_step_fraction": float(spec.step_fraction),
        "load_step_pct": float(spec.step_pct),
        "p_load_pre_step_w": p_pre,
        "p_load_post_step_w": p_post,
        "bess_active": bess_active,
        "Kp_w_per_v": PI_KP_W_PER_V,
        "Ki_w_per_v_s": PI_KI_W_PER_V_S,
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "state_count": int(solution.y.shape[0]),
        "solver_success": bool(solution.success),
        "solver_message": str(solution.message),
        "states_finite": states_finite,
        "signals_finite": signals_finite,
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
        "controller_modified_after_task_5_2": False,
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec.output_filename
    clean = _json_ready(record)
    clean["output_path"] = str(output_path)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(clean, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"scenario={clean['scenario']}")
    print(f"status={clean['status']}")
    print(f"load_step_pct={clean['load_step_pct']}")
    print(f"bess_active={clean['bess_active']}")
    print(f"vdc_criteria_pass={clean['vdc_criteria_pass']}")
    print(f"frequency_criteria_pass={clean['frequency_criteria_pass']}")
    print(f"bess_limits_pass={clean['bess_limits_pass']}")
    print(f"output_path={output_path}")
    return clean


def run_all_scenarios(
    output_dir: Path = OUTPUT_DIR,
    summary_output: Path = SUMMARY_OUTPUT,
) -> dict[str, Any]:
    """Run both required Task 5.3 scenarios and save the combined closure record."""
    records = [run_scenario(spec, output_dir=output_dir) for spec in SCENARIOS]
    overall_status = classify_overall_status(records)
    summary: dict[str, Any] = {
        "task": "5.3",
        "title": "Validacion y cierre de la regulacion del enlace DC",
        "status": overall_status,
        "required_scenario_count": len(SCENARIOS),
        "passed_scenario_count": sum(record["status"] == "PASS" for record in records),
        "Kp_w_per_v": PI_KP_W_PER_V,
        "Ki_w_per_v_s": PI_KI_W_PER_V_S,
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        "bess_active_all_scenarios": bool(all(record["bess_active"] for record in records)),
        "scenarios": records,
    }

    summary_output = Path(summary_output)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary["summary_output_path"] = str(summary_output)
    with summary_output.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, sort_keys=True)
        summary_file.write("\n")

    print(f"task_5_3_status={overall_status}")
    print(f"passed_scenario_count={summary['passed_scenario_count']}")
    print(f"summary_output_path={summary_output}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = run_all_scenarios(
        output_dir=args.output_dir,
        summary_output=args.summary_output,
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
