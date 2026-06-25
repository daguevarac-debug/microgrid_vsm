"""Validate DC-link and BESS physical invariants without changing sign conventions.

The checks are intentionally independent from performance acceptance. They verify:

1. ``dVdc/dt = (ipv + i_bess - idc_inv) / Cdc`` pointwise;
2. ``p_bess_dc = Vdc * i_bess`` pointwise;
3. BESS SoC remains inside ``[soc_min, soc_max]``;
4. positive BESS current means discharge/support and negative current means charge.

Two dynamic 20% load-step simulations are used: selected GFM without BESS and
the accepted selected-GFM+BESS-PI architecture. Separate charge/discharge probes
exercise both BESS current signs even when one sign is not reached by the nominal
dynamic trajectory.
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
from microgrid import Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
)
from validation.validate_dc_link_pi_scenarios import (
    BASE_SCENARIO as ACCEPTED_BESS_PI_BASE_SCENARIO,
    T_END_S,
    build_model as build_accepted_bess_pi_model,
)


OUTPUT_PATH_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "validation"
    / "physical_invariants"
    / "gfm_physical_invariants_summary.json"
)
N_EVALUATION_POINTS_DEFAULT = 1001
ABS_TOL_DVDC = 1e-9
REL_TOL_DVDC = 1e-10
ABS_TOL_POWER_W = 1e-8
REL_TOL_POWER = 1e-10
ABS_TOL_CURRENT_A = 1e-10
SOC_TOL = 1e-10


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def build_no_bess_model() -> Microgrid:
    """Build the selected GFM under the same 20% step used by the BESS case."""
    p_pre = float(MICROGRID_LOAD_P_NOM_W_DEFAULT)
    p_post = p_pre * (1.0 + MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT)
    controller = GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    return Microgrid(
        controller=controller,
        load_profile=lambda t: (
            p_pre if t < MICROGRID_LOAD_STEP_TIME_S_DEFAULT else p_post
        ),
    )


def build_bess_pi_model() -> MicrogridWithBESSPI:
    """Build the accepted selected-GFM+BESS-PI 20% scenario."""
    model = build_accepted_bess_pi_model(ACCEPTED_BESS_PI_BASE_SCENARIO)
    if not isinstance(model, MicrogridWithBESSPI):
        raise TypeError("Accepted builder did not return MicrogridWithBESSPI.")
    if not model.bess_enabled:
        raise ValueError("BESS must be enabled for physical-invariant validation.")
    return model


def _solve_model(
    model: Microgrid,
    *,
    n_evaluation_points: int,
):
    if n_evaluation_points < 3:
        raise ValueError("n_evaluation_points must be >= 3.")
    t_eval = np.linspace(
        float(SIM_T_START_S_DEFAULT),
        float(T_END_S),
        int(n_evaluation_points),
    )
    if isinstance(model, MicrogridWithBESSPI):
        initial_state = model.initial_state_with_bess(
            vdc0=SIM_VDC0_V_DEFAULT,
            xi_bess_vdc0_v_s=0.0,
        )
    else:
        initial_state = model.initial_state(vdc0=SIM_VDC0_V_DEFAULT)

    return solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, T_END_S),
        initial_state,
        t_eval=t_eval,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )


def _scaled_tolerance(
    actual: np.ndarray,
    expected: np.ndarray,
    *,
    abs_tol: float,
    rel_tol: float,
) -> np.ndarray:
    scale = np.maximum.reduce(
        (
            np.abs(actual),
            np.abs(expected),
            np.ones_like(actual),
        )
    )
    return abs_tol + rel_tol * scale


def _no_bess_point_values(
    model: Microgrid,
    t: float,
    x: np.ndarray,
) -> tuple[float, float, float, float]:
    vdc = float(x[0])
    i1 = np.asarray(x[1:4], dtype=float)
    vc = np.asarray(x[4:7], dtype=float)
    i2 = np.asarray(x[7:10], dtype=float)
    controller_state = float(x[10])
    theta = float(x[11])

    ipv, _, control = model._compute_step_control(
        t=float(t),
        Vdc=vdc,
        i1=i1,
        i2=i2,
        controller_state=controller_state,
        theta=theta,
        vc=vc,
    )
    rhs_dvdc = float(model.system_dynamics(float(t), x)[0])
    expected_dvdc = (
        float(ipv) + 0.0 - float(control.idc_inv)
    ) / float(model.dcp.Cdc)
    return rhs_dvdc, expected_dvdc, float(ipv), float(control.idc_inv)


def validate_no_bess_dc_balance(
    model: Microgrid,
    solution,
) -> dict[str, Any]:
    """Check the DC balance with the invariant specialization i_bess = 0."""
    actual = np.zeros(solution.t.size, dtype=float)
    expected = np.zeros(solution.t.size, dtype=float)
    ipv = np.zeros(solution.t.size, dtype=float)
    idc_inv = np.zeros(solution.t.size, dtype=float)

    for k, tk in enumerate(solution.t):
        values = _no_bess_point_values(model, float(tk), solution.y[:, k])
        actual[k], expected[k], ipv[k], idc_inv[k] = values

    residual = actual - expected
    tolerance = _scaled_tolerance(
        actual,
        expected,
        abs_tol=ABS_TOL_DVDC,
        rel_tol=REL_TOL_DVDC,
    )
    balance_pass = bool(np.all(np.abs(residual) <= tolerance))
    finite_pass = bool(
        np.all(np.isfinite(actual))
        and np.all(np.isfinite(expected))
        and np.all(np.isfinite(ipv))
        and np.all(np.isfinite(idc_inv))
    )

    return {
        "equation": "dVdc_dt = (ipv + 0 - idc_inv) / Cdc",
        "sign_convention_preserved": True,
        "sample_count": int(solution.t.size),
        "signals_finite": finite_pass,
        "max_abs_dc_balance_residual_v_per_s": float(np.max(np.abs(residual))),
        "max_allowed_dc_balance_residual_v_per_s": float(np.max(tolerance)),
        "dc_balance_pass": bool(balance_pass and finite_pass),
        "ipv_min_a": float(np.min(ipv)),
        "ipv_max_a": float(np.max(ipv)),
        "idc_inv_min_a": float(np.min(idc_inv)),
        "idc_inv_max_a": float(np.max(idc_inv)),
    }


def _bess_pi_point_values(
    model: MicrogridWithBESSPI,
    t: float,
    x: np.ndarray,
) -> tuple[float, float, float, float, float, float, float]:
    vdc = float(x[0])
    i1 = np.asarray(x[1:4], dtype=float)
    vc = np.asarray(x[4:7], dtype=float)
    i2 = np.asarray(x[7:10], dtype=float)
    controller_state = float(x[10])
    theta = float(x[11])
    soc_bess = float(x[12])
    zdeg_bess = float(x[14])
    xi_bess_vdc = float(x[15])

    soh_bess = float(model.bess.soh_from_z_deg(zdeg_bess))
    i_bess_max_available = float(model._available_i_bess_max(soh_bess))
    _, i_bess = model._compute_pi_bess_command(
        vdc_v=vdc,
        soc_bess=soc_bess,
        soh_bess=soh_bess,
        xi_bess_vdc_v_s=xi_bess_vdc,
    )
    p_bess_expected = vdc * float(i_bess)
    _, p_discharge_max_w, _, _ = model._operating_power_limits(
        vdc_v=vdc,
        soc_bess=soc_bess,
        soh_bess=soh_bess,
    )
    ipv, _, control = model._compute_step_control(
        t=float(t),
        Vdc=vdc,
        i1=i1,
        i2=i2,
        controller_state=controller_state,
        theta=theta,
        vc=vc,
        soc_bess=soc_bess,
        soh_bess=soh_bess,
        i_bess_max_available=i_bess_max_available,
        p_bess_dc_max_available=float(p_discharge_max_w),
        p_bess_dc_actual=p_bess_expected,
    )

    rhs_dvdc = float(model.system_dynamics(float(t), x)[0])
    expected_dvdc = (
        float(ipv) + float(i_bess) - float(control.idc_inv)
    ) / float(model.dcp.Cdc)
    signal = model.integrated_signals(float(t), x)
    p_bess_reported = float(signal["p_bess_dc"])
    i_bess_reported = float(signal["i_bess"])
    return (
        rhs_dvdc,
        expected_dvdc,
        float(i_bess),
        i_bess_reported,
        p_bess_expected,
        p_bess_reported,
        float(ipv),
    )


def validate_bess_pi_invariants(
    model: MicrogridWithBESSPI,
    solution,
) -> dict[str, Any]:
    """Check DC balance, BESS power identity, and SoC bounds pointwise."""
    n = solution.t.size
    actual_dvdc = np.zeros(n, dtype=float)
    expected_dvdc = np.zeros(n, dtype=float)
    i_bess_expected = np.zeros(n, dtype=float)
    i_bess_reported = np.zeros(n, dtype=float)
    p_bess_expected = np.zeros(n, dtype=float)
    p_bess_reported = np.zeros(n, dtype=float)
    ipv = np.zeros(n, dtype=float)

    for k, tk in enumerate(solution.t):
        values = _bess_pi_point_values(model, float(tk), solution.y[:, k])
        (
            actual_dvdc[k],
            expected_dvdc[k],
            i_bess_expected[k],
            i_bess_reported[k],
            p_bess_expected[k],
            p_bess_reported[k],
            ipv[k],
        ) = values

    dc_residual = actual_dvdc - expected_dvdc
    dc_tolerance = _scaled_tolerance(
        actual_dvdc,
        expected_dvdc,
        abs_tol=ABS_TOL_DVDC,
        rel_tol=REL_TOL_DVDC,
    )
    power_residual = p_bess_reported - p_bess_expected
    power_tolerance = _scaled_tolerance(
        p_bess_reported,
        p_bess_expected,
        abs_tol=ABS_TOL_POWER_W,
        rel_tol=REL_TOL_POWER,
    )
    current_residual = i_bess_reported - i_bess_expected
    current_tolerance = _scaled_tolerance(
        i_bess_reported,
        i_bess_expected,
        abs_tol=ABS_TOL_CURRENT_A,
        rel_tol=REL_TOL_POWER,
    )

    soc = np.asarray(solution.y[12], dtype=float)
    soc_min_allowed = float(model.bess.soc_min)
    soc_max_allowed = float(model.bess.soc_max)
    soc_bounds_pass = bool(
        np.all(soc >= soc_min_allowed - SOC_TOL)
        and np.all(soc <= soc_max_allowed + SOC_TOL)
    )
    finite_pass = bool(
        all(
            np.all(np.isfinite(values))
            for values in (
                actual_dvdc,
                expected_dvdc,
                i_bess_expected,
                i_bess_reported,
                p_bess_expected,
                p_bess_reported,
                ipv,
                soc,
            )
        )
    )
    dc_balance_pass = bool(
        finite_pass and np.all(np.abs(dc_residual) <= dc_tolerance)
    )
    power_identity_pass = bool(
        finite_pass and np.all(np.abs(power_residual) <= power_tolerance)
    )
    current_coherence_pass = bool(
        finite_pass and np.all(np.abs(current_residual) <= current_tolerance)
    )

    return {
        "dc_balance_equation": "dVdc_dt = (ipv + i_bess - idc_inv) / Cdc",
        "bess_power_equation": "p_bess_dc = Vdc * i_bess",
        "sign_convention": (
            "i_bess > 0 injects into DC bus (discharge); "
            "i_bess < 0 absorbs from DC bus (charge)"
        ),
        "sample_count": int(n),
        "signals_finite": finite_pass,
        "max_abs_dc_balance_residual_v_per_s": float(np.max(np.abs(dc_residual))),
        "max_allowed_dc_balance_residual_v_per_s": float(np.max(dc_tolerance)),
        "dc_balance_pass": dc_balance_pass,
        "max_abs_bess_power_identity_residual_w": float(
            np.max(np.abs(power_residual))
        ),
        "max_allowed_bess_power_identity_residual_w": float(
            np.max(power_tolerance)
        ),
        "bess_power_identity_pass": power_identity_pass,
        "max_abs_bess_current_reconstruction_residual_a": float(
            np.max(np.abs(current_residual))
        ),
        "bess_current_coherence_pass": current_coherence_pass,
        "soc_min_allowed": soc_min_allowed,
        "soc_max_allowed": soc_max_allowed,
        "soc_min_observed": float(np.min(soc)),
        "soc_max_observed": float(np.max(soc)),
        "soc_final": float(soc[-1]),
        "soc_bounds_pass": soc_bounds_pass,
        "i_bess_min_a": float(np.min(i_bess_reported)),
        "i_bess_max_a": float(np.max(i_bess_reported)),
        "p_bess_dc_min_w": float(np.min(p_bess_reported)),
        "p_bess_dc_max_w": float(np.max(p_bess_reported)),
        "all_dynamic_invariants_pass": bool(
            dc_balance_pass
            and power_identity_pass
            and current_coherence_pass
            and soc_bounds_pass
        ),
    }


def _sign_probe(
    model: MicrogridWithBESSPI,
    *,
    vdc_v: float,
    expected_mode: str,
) -> dict[str, Any]:
    """Exercise one current sign and verify its DC-link and SoC directions."""
    x = model.initial_state_with_bess(
        vdc0=vdc_v,
        xi_bess_vdc0_v_s=0.0,
    )
    soc = float(x[12])
    v_rc = float(x[13])
    z_deg = float(x[14])
    soh = float(model.bess.soh_from_z_deg(z_deg))
    _, i_bess = model._compute_pi_bess_command(
        vdc_v=vdc_v,
        soc_bess=soc,
        soh_bess=soh,
        xi_bess_vdc_v_s=0.0,
    )
    p_bess = float(vdc_v) * float(i_bess)
    d_bess = model.bess.rhs(
        t=0.0,
        x=[soc, v_rc, z_deg],
        i_bess=float(i_bess),
        soh=model.bess.soh_init_case,
    )

    dvdc_without_bess = (0.0 + 0.0 - 0.0) / float(model.dcp.Cdc)
    dvdc_with_bess = (0.0 + float(i_bess) - 0.0) / float(model.dcp.Cdc)
    contribution = dvdc_with_bess - dvdc_without_bess
    expected_contribution = float(i_bess) / float(model.dcp.Cdc)

    if expected_mode == "discharge":
        sign_pass = bool(i_bess > 0.0 and p_bess > 0.0 and d_bess[0] < 0.0)
    elif expected_mode == "charge":
        sign_pass = bool(i_bess < 0.0 and p_bess < 0.0 and d_bess[0] > 0.0)
    else:
        raise ValueError(f"Unsupported expected_mode={expected_mode!r}.")

    contribution_pass = bool(
        np.isclose(
            contribution,
            expected_contribution,
            atol=ABS_TOL_DVDC,
            rtol=REL_TOL_DVDC,
        )
    )
    power_identity_pass = bool(
        np.isclose(
            p_bess,
            float(vdc_v) * float(i_bess),
            atol=ABS_TOL_POWER_W,
            rtol=REL_TOL_POWER,
        )
    )
    return {
        "expected_mode": expected_mode,
        "vdc_probe_v": float(vdc_v),
        "i_bess_a": float(i_bess),
        "p_bess_dc_w": p_bess,
        "d_soc_dt_per_s": float(d_bess[0]),
        "dc_link_bess_contribution_v_per_s": float(contribution),
        "expected_dc_link_bess_contribution_v_per_s": float(
            expected_contribution
        ),
        "current_and_soc_sign_pass": sign_pass,
        "dc_link_contribution_sign_pass": contribution_pass,
        "power_identity_pass": power_identity_pass,
        "probe_pass": bool(sign_pass and contribution_pass and power_identity_pass),
    }


def validate_sign_convention(model: MicrogridWithBESSPI) -> dict[str, Any]:
    """Verify both charge and discharge directions around the DC reference."""
    vdc_ref = float(model.dc_link_bess_pi.vdc_ref_v)
    discharge = _sign_probe(
        model,
        vdc_v=vdc_ref - 1.0,
        expected_mode="discharge",
    )
    charge = _sign_probe(
        model,
        vdc_v=vdc_ref + 1.0,
        expected_mode="charge",
    )
    return {
        "reference_vdc_v": vdc_ref,
        "discharge_probe": discharge,
        "charge_probe": charge,
        "both_signs_pass": bool(discharge["probe_pass"] and charge["probe_pass"]),
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def run_validation(
    *,
    output_path: Path = OUTPUT_PATH_DEFAULT,
    n_evaluation_points: int = N_EVALUATION_POINTS_DEFAULT,
) -> dict[str, Any]:
    """Run dynamic and static physical-invariant checks and save JSON evidence."""
    no_bess_model = build_no_bess_model()
    bess_pi_model = build_bess_pi_model()

    no_bess_solution = _solve_model(
        no_bess_model,
        n_evaluation_points=n_evaluation_points,
    )
    bess_pi_solution = _solve_model(
        bess_pi_model,
        n_evaluation_points=n_evaluation_points,
    )

    no_bess_checks = validate_no_bess_dc_balance(
        no_bess_model,
        no_bess_solution,
    )
    bess_pi_checks = validate_bess_pi_invariants(
        bess_pi_model,
        bess_pi_solution,
    )
    sign_checks = validate_sign_convention(bess_pi_model)

    solver_checks_pass = bool(
        no_bess_solution.success
        and bess_pi_solution.success
        and np.all(np.isfinite(no_bess_solution.y))
        and np.all(np.isfinite(bess_pi_solution.y))
    )
    invariants_pass = bool(
        no_bess_checks["dc_balance_pass"]
        and bess_pi_checks["all_dynamic_invariants_pass"]
        and sign_checks["both_signs_pass"]
    )
    status = "PASS" if solver_checks_pass and invariants_pass else "FAIL"

    report: dict[str, Any] = {
        "task": "Verificar invariantes fisicos del balance DC y BESS",
        "status": status,
        "solver_checks_pass": solver_checks_pass,
        "invariants_pass": invariants_pass,
        "controller": {
            "class": "GFMController",
            "M": float(GFM_SELECTED_M),
            "D": float(GFM_SELECTED_D),
        },
        "equations_verified": {
            "dc_balance": "dVdc_dt = (ipv + i_bess - idc_inv) / Cdc",
            "bess_power": "p_bess_dc = Vdc * i_bess",
            "soc_bounds": "soc_min <= SoC <= soc_max",
        },
        "no_bess_20pct": {
            "solver_success": bool(no_bess_solution.success),
            "solver_message": str(no_bess_solution.message),
            **no_bess_checks,
        },
        "bess_pi_20pct": {
            "solver_success": bool(bess_pi_solution.success),
            "solver_message": str(bess_pi_solution.message),
            **bess_pi_checks,
        },
        "sign_convention_probes": sign_checks,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(output_path)
    clean_report = _json_ready(report)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(clean_report, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"no_bess_dc_balance_pass={no_bess_checks['dc_balance_pass']}")
    print(f"bess_dc_balance_pass={bess_pi_checks['dc_balance_pass']}")
    print(
        "bess_power_identity_pass="
        f"{bess_pi_checks['bess_power_identity_pass']}"
    )
    print(f"soc_bounds_pass={bess_pi_checks['soc_bounds_pass']}")
    print(f"charge_discharge_signs_pass={sign_checks['both_signs_pass']}")
    print(f"overall_status={status}")
    print(f"output_path={output_path}")
    return clean_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH_DEFAULT)
    parser.add_argument(
        "--points",
        type=int,
        default=N_EVALUATION_POINTS_DEFAULT,
        help="Number of equally spaced points used for pointwise invariant checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_validation(
        output_path=args.output,
        n_evaluation_points=args.points,
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
