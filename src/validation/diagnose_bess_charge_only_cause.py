"""Diagnose the cause of the selected-GFM BESS ``charge_only`` behavior.

This diagnostic reproduces the nominal-SoH GFM+BESS case used by the SoH
comparison and separates three hypotheses:
1. sign error,
2. incorrect activation/blocking,
3. operating-point/reference behavior under proportional-only DC-link support.

No plant equation, controller law, state mapping or limit is modified.
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
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
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
T_END_S = 6.5
ATOL = 1e-8
SCENARIO_NAME = "gfm_selected_nominal_soh_charge_only_diagnostic"
OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "dclink_energy_diagnostic"
    / "gfm_m80_d1500_charge_only_cause.json"
)


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def _build_case() -> tuple[MicrogridWithBESS, list[float], dict[str, float]]:
    """Build the nominal-SoH selected-GFM case that reported charge_only."""
    p_load_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_load_post = float(
        p_load_pre * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
    )
    t_step = float(MICROGRID_LOAD_STEP_TIME_S_DEFAULT)
    controller = GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    model = MicrogridWithBESS(
        controller=controller,
        load_profile=lambda t: p_load_pre if t < t_step else p_load_post,
    )
    initial_state = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
    metadata = {
        "p_load_pre_step_w": p_load_pre,
        "p_load_post_step_w": p_load_post,
        "load_step_pct": 100.0 * (p_load_post - p_load_pre) / p_load_pre,
        "t_step_s": t_step,
    }
    return model, initial_state, metadata


def _exchange_mode(current_a: np.ndarray, atol: float = ATOL) -> str:
    current = np.asarray(current_a, dtype=float)
    discharge = bool(np.any(current > atol))
    charge = bool(np.any(current < -atol))
    if discharge and charge:
        return "bidirectional"
    if discharge:
        return "discharge_only"
    if charge:
        return "charge_only"
    return "idle"


def _determine_root_cause(
    *,
    sign_coherence_ok: bool,
    unexplained_discharge_blocking: bool,
    exchange_mode: str,
    vdc_above_ref_fraction: float,
    integral_dc_link_state_present: bool,
) -> str:
    """Classify the dominant cause without changing the implemented control."""
    if not sign_coherence_ok:
        return "sign_error"
    if unexplained_discharge_blocking:
        return "incorrect_activation_or_blocking"
    if exchange_mode == "charge_only" and vdc_above_ref_fraction > 0.5:
        if not integral_dc_link_state_present:
            return "vdc_operating_point_above_reference_with_proportional_only_support"
        return "vdc_operating_point_above_reference"
    if exchange_mode != "charge_only":
        return "charge_only_not_reproduced"
    return "inconclusive"


def run_diagnostic(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    model, initial_state, metadata = _build_case()
    solution = solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, T_END_S),
        initial_state,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    n = solution.t.size
    vdc = np.zeros(n, dtype=float)
    current = np.zeros(n, dtype=float)
    power = np.zeros(n, dtype=float)
    soc = np.zeros(n, dtype=float)
    i_available = np.zeros(n, dtype=float)
    p_available = np.zeros(n, dtype=float)

    for k, tk in enumerate(solution.t):
        signal = model.integrated_signals(float(tk), solution.y[:, k])
        vdc[k] = float(signal["Vdc"])
        current[k] = float(signal["i_bess"])
        power[k] = float(signal["p_bess_dc"])
        soc[k] = float(signal["soc_bess"])
        i_available[k] = float(signal["i_bess_max_available"])
        p_available[k] = float(signal["p_bess_dc_max_available"])

    raw_current_command = model.kp_bess * (model.vdc_ref - vdc)
    post = solution.t >= metadata["t_step_s"]
    requested_discharge = post & (raw_current_command > ATOL)
    delivered_discharge = current > ATOL
    blocked_discharge = requested_discharge & ~delivered_discharge
    legitimate_soc_block = soc <= model.bess.soc_min + ATOL
    legitimate_limit_block = (i_available <= ATOL) | (p_available <= ATOL)
    unexplained_block = blocked_discharge & ~legitimate_soc_block & ~legitimate_limit_block

    sign_coherence_ok = bool(
        np.all(current * raw_current_command >= -ATOL)
        and np.allclose(power, vdc * current, rtol=1e-9, atol=ATOL)
    )
    exchange_mode = _exchange_mode(current[post])
    post_count = int(np.count_nonzero(post))
    vdc_above_ref_fraction = float(
        np.count_nonzero(post & (vdc > model.vdc_ref + ATOL)) / max(post_count, 1)
    )
    vdc_below_ref_fraction = float(
        np.count_nonzero(post & (vdc < model.vdc_ref - ATOL)) / max(post_count, 1)
    )
    discharge_request_count = int(np.count_nonzero(requested_discharge))
    discharge_delivery_count = int(
        np.count_nonzero(requested_discharge & delivered_discharge)
    )
    unexplained_block_count = int(np.count_nonzero(unexplained_block))

    integral_dc_link_state_present = model.controller_state_name == "xi_vdc"
    proportional_bess_vdc_support_present = bool(model.kp_bess > 0.0)
    root_cause = _determine_root_cause(
        sign_coherence_ok=sign_coherence_ok,
        unexplained_discharge_blocking=bool(unexplained_block_count),
        exchange_mode=exchange_mode,
        vdc_above_ref_fraction=vdc_above_ref_fraction,
        integral_dc_link_state_present=integral_dc_link_state_present,
    )

    diagnostic_ok = bool(
        solution.success
        and np.all(np.isfinite(solution.y))
        and sign_coherence_ok
        and unexplained_block_count == 0
    )
    result: dict[str, Any] = {
        "scenario": SCENARIO_NAME,
        "status": "PASS" if diagnostic_ok else "FAIL",
        "scope": "charge_only_root_cause_diagnostic",
        "M": GFM_SELECTED_M,
        "D": GFM_SELECTED_D,
        **metadata,
        "solver_success": bool(solution.success),
        "controller_state_name": model.controller_state_name,
        "vdc_ref_v": float(model.vdc_ref),
        "kp_bess_a_per_v": float(model.kp_bess),
        "exchange_mode_post_step": exchange_mode,
        "sign_coherence_ok": sign_coherence_ok,
        "bess_power_identity_ok": bool(
            np.allclose(power, vdc * current, rtol=1e-9, atol=ATOL)
        ),
        "discharge_request_count": discharge_request_count,
        "discharge_delivery_count": discharge_delivery_count,
        "unexplained_discharge_block_count": unexplained_block_count,
        "incorrect_activation_or_blocking_detected": bool(unexplained_block_count),
        "vdc_above_ref_fraction_post_step": vdc_above_ref_fraction,
        "vdc_below_ref_fraction_post_step": vdc_below_ref_fraction,
        "vdc_min_post_step_v": float(np.min(vdc[post])),
        "vdc_max_post_step_v": float(np.max(vdc[post])),
        "i_bess_min_post_step_a": float(np.min(current[post])),
        "i_bess_max_post_step_a": float(np.max(current[post])),
        "proportional_bess_vdc_support_present": proportional_bess_vdc_support_present,
        "integral_dc_link_state_present": integral_dc_link_state_present,
        "dedicated_gfm_dc_link_regulation_present": integral_dc_link_state_present,
        "root_cause": root_cause,
        "conclusion": (
            "No sign error or unexplained activation block was detected. "
            "The charge_only result is produced when Vdc remains mainly above "
            "the fixed Vdc reference, so the proportional BESS law commands "
            "charging. The GFM state is omega and no integral DC-link state is present."
            if root_cause
            == "vdc_operating_point_above_reference_with_proportional_only_support"
            else "See root_cause and diagnostic fields."
        ),
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"scenario={result['scenario']}")
    print(f"status={result['status']}")
    print(f"exchange_mode_post_step={result['exchange_mode_post_step']}")
    print(f"sign_coherence_ok={result['sign_coherence_ok']}")
    print(
        "incorrect_activation_or_blocking_detected="
        f"{result['incorrect_activation_or_blocking_detected']}"
    )
    print(f"integral_dc_link_state_present={result['integral_dc_link_state_present']}")
    print(f"root_cause={result['root_cause']}")
    print(f"output_path={output_path}")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_diagnostic(output_path=args.output)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
