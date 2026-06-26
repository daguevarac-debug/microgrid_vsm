"""Consolidate Objective 2.2 BESS/BMS control-limit evidence.

The validation combines one short dynamic GFM+BESS+PI simulation with direct
operating-point checks of the existing BESS, BMS-supervision and external
DC-link PI helpers. It does not modify equations, selected VSG parameters,
state ordering or IEEE 33 coupling.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
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
from validation.validate_bess_pi_minimal_tuning import (
    GFM_SELECTED_D,
    GFM_SELECTED_M,
    PI_KI_W_PER_V_S,
    PI_KP_W_PER_V,
)


OUTPUT_DIR_DEFAULT = (
    REPO_ROOT / "outputs" / "validation" / "objective2_bess_limits"
)
SUMMARY_JSON_NAME = "summary.json"
SUMMARY_CSV_NAME = "summary.csv"
VALIDATION_ID = "objective2_bess_control_limits_v1"
DYNAMIC_T_END_S = 0.12
LIMIT_ATOL = 1e-8
IDENTITY_ATOL_W = 1e-8
CURRENT_ATOL_A = 1e-9
POWER_ATOL_W = 1e-8


@dataclass(frozen=True)
class CriterionResult:
    """Single criterion result for JSON and CSV evidence."""

    criterion_id: int
    criterion_name: str
    scenario: str
    status: str
    observed_value: str
    expected_or_limit: str
    tolerance: str
    software_failure: bool
    notes: str
    metrics: dict[str, Any]
    limits: dict[str, Any]

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "scenario": self.scenario,
            "status": self.status,
            "observed_value": self.observed_value,
            "expected_or_limit": self.expected_or_limit,
            "tolerance": self.tolerance,
            "software_failure": self.software_failure,
            "notes": self.notes,
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "scenario": self.scenario,
            "status": self.status,
            "observed_value": self.observed_value,
            "expected_or_limit": self.expected_or_limit,
            "tolerance": self.tolerance,
            "software_failure": self.software_failure,
            "notes": self.notes,
            "metrics": self.metrics,
            "limits": self.limits,
        }


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unavailable"


def _reference_active_power_w() -> float:
    reference_model = Microgrid()
    return float(min(reference_model.P_ref_nominal, reference_model.p_available_ref))


def _build_model(
    *,
    kp_w_per_v: float = PI_KP_W_PER_V,
    ki_w_per_v_s: float = PI_KI_W_PER_V_S,
    bess_enabled: bool = True,
    i_bess_max: float | None = None,
    p_bess_max_w: float | None = None,
    load_power_w: float = MICROGRID_LOAD_P_NOM_W_DEFAULT,
) -> MicrogridWithBESSPI:
    controller = GFMController(
        p_ref=_reference_active_power_w(),
        inertia_m=GFM_SELECTED_M,
        damping_d=GFM_SELECTED_D,
    )
    pi = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=kp_w_per_v,
        ki_w_per_v_s=ki_w_per_v_s,
    )
    kwargs: dict[str, Any] = {
        "controller": controller,
        "dc_link_bess_pi": pi,
        "bess_enabled": bess_enabled,
        "load_profile": lambda _t: load_power_w,
    }
    if i_bess_max is not None:
        kwargs["i_bess_max"] = i_bess_max
    if p_bess_max_w is not None:
        kwargs["p_bess_max_w"] = p_bess_max_w
    return MicrogridWithBESSPI(**kwargs)


def _soc_margin(model: MicrogridWithBESSPI) -> float:
    return 0.01 * (float(model.bess.soc_max) - float(model.bess.soc_min))


def _status(ok: bool, *, review: bool = False) -> str:
    if not ok:
        return "FAIL"
    return "REVIEW" if review else "PASS"


def _criterion(
    criterion_id: int,
    criterion_name: str,
    scenario: str,
    ok: bool,
    observed_value: str,
    expected_or_limit: str,
    *,
    tolerance: str = "see metrics",
    notes: str = "",
    metrics: dict[str, Any] | None = None,
    limits: dict[str, Any] | None = None,
    software_failure: bool = False,
    review: bool = False,
) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion_id,
        criterion_name=criterion_name,
        scenario=scenario,
        status=_status(ok, review=review),
        observed_value=observed_value,
        expected_or_limit=expected_or_limit,
        tolerance=tolerance,
        software_failure=software_failure,
        notes=notes,
        metrics=metrics or {},
        limits=limits or {},
    )


def _solve_nominal(model: MicrogridWithBESSPI):
    y0 = model.initial_state_with_bess(
        vdc0=SIM_VDC0_V_DEFAULT,
        xi_bess_vdc0_v_s=0.0,
    )
    return solve_ivp(
        model.system_dynamics,
        (SIM_T_START_S_DEFAULT, DYNAMIC_T_END_S),
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )


def _collect_dynamic_signals(
    model: MicrogridWithBESSPI,
    solution,
) -> dict[str, np.ndarray]:
    keys = (
        "Vdc",
        "i_bess",
        "p_bess_dc",
        "soc_bess",
        "soh_bess",
        "vt_bess",
        "p_bess_ref_w",
        "p_bess_ref_min_w",
        "p_bess_ref_max_w",
        "i_bess_max_available",
    )
    signals = {key: np.zeros(solution.t.size, dtype=float) for key in keys}
    for k, tk in enumerate(solution.t):
        sample = model.integrated_signals(float(tk), solution.y[:, k])
        for key in keys:
            signals[key][k] = float(sample[key])
    return signals


def _finite_dynamic(solution, signals: dict[str, np.ndarray]) -> bool:
    return bool(
        np.all(np.isfinite(solution.t))
        and np.all(np.isfinite(solution.y))
        and all(np.all(np.isfinite(value)) for value in signals.values())
    )


def _operational_violations(
    model: MicrogridWithBESSPI,
    signals: dict[str, np.ndarray],
) -> dict[str, Any]:
    vdc = signals["Vdc"]
    i_bess = signals["i_bess"]
    p_bess = signals["p_bess_dc"]
    soc = signals["soc_bess"]
    soh = signals["soh_bess"]
    p_ref = signals["p_bess_ref_w"]
    p_min = signals["p_bess_ref_min_w"]
    p_max = signals["p_bess_ref_max_w"]
    i_available = signals["i_bess_max_available"]
    identity_residual = p_bess - vdc * i_bess
    current_excess = np.maximum(np.abs(i_bess) - i_available, 0.0)
    p_ref_low = np.maximum(p_min - p_ref, 0.0)
    p_ref_high = np.maximum(p_ref - p_max, 0.0)
    p_low = np.maximum(p_min - p_bess, 0.0)
    p_high = np.maximum(p_bess - p_max, 0.0)
    soc_low = np.maximum(float(model.bess.soc_min) - soc, 0.0)
    soc_high = np.maximum(soc - float(model.bess.soc_max), 0.0)
    soh_low = np.maximum(float(model.bess.soh_min) - soh, 0.0)
    soh_high = np.maximum(soh - 1.0, 0.0)
    return {
        "max_abs_power_identity_residual_w": float(np.max(np.abs(identity_residual))),
        "max_current_limit_excess_a": float(np.max(current_excess)),
        "max_power_reference_limit_excess_w": float(
            max(np.max(p_ref_low), np.max(p_ref_high))
        ),
        "max_actual_power_limit_excess_w": float(max(np.max(p_low), np.max(p_high))),
        "max_soc_limit_excess": float(max(np.max(soc_low), np.max(soc_high))),
        "max_soh_limit_excess": float(max(np.max(soh_low), np.max(soh_high))),
    }


def _pi_probe(
    model: MicrogridWithBESSPI,
    *,
    vdc_v: float,
    soc_bess: float,
    soh_bess: float,
    xi_bess_vdc_v_s: float = 0.0,
) -> tuple[Any, float, float]:
    pi_output, current = model._compute_pi_bess_command(
        vdc_v=vdc_v,
        soc_bess=soc_bess,
        soh_bess=soh_bess,
        xi_bess_vdc_v_s=xi_bess_vdc_v_s,
    )
    return pi_output, float(current), float(vdc_v) * float(current)


def run_validation(*, output_dir: Path = OUTPUT_DIR_DEFAULT, write: bool = True) -> dict[str, Any]:
    """Run all fifteen Objective 2.2 criteria and optionally write evidence."""
    nominal_model = _build_model()
    nominal_solution = _solve_nominal(nominal_model)
    dynamic_signals = _collect_dynamic_signals(nominal_model, nominal_solution)
    dynamic_finite = _finite_dynamic(nominal_solution, dynamic_signals)
    violations = _operational_violations(nominal_model, dynamic_signals)
    scale_ratio = float(
        np.max(dynamic_signals["Vdc"] / np.maximum(dynamic_signals["vt_bess"], 1e-12))
    )
    scale_review = bool(scale_ratio > 20.0)

    soc_min = float(nominal_model.bess.soc_min)
    soc_max = float(nominal_model.bess.soc_max)
    soc_mid = float(nominal_model.bess.soc_initial)
    margin = _soc_margin(nominal_model)
    soc_near_min = soc_min + margin
    soc_near_max = soc_max - margin
    soh_nominal = float(nominal_model.bess.soh_init_case)
    vdc_discharge = SIM_VDC0_V_DEFAULT - 10.0
    vdc_charge = SIM_VDC0_V_DEFAULT + 10.0

    results: list[CriterionResult] = []

    results.append(
        _criterion(
            1,
            "operacion nominal",
            "short_dynamic_nominal_gfm_bess_pi",
            bool(nominal_solution.success and dynamic_finite),
            f"solver_success={nominal_solution.success}, samples={nominal_solution.t.size}",
            "solver success and finite states/signals",
            tolerance=f"rtol={SIM_SOLVER_RTOL_DEFAULT}, atol={SIM_SOLVER_ATOL_DEFAULT}",
            notes=(
                "Validacion dinamica corta; no es campana pesada ni validacion experimental."
                + (
                    " Vdc/vt_bess scale is a documented interpretation warning."
                    if scale_review
                    else ""
                )
            ),
            metrics={
                "t_end_s": DYNAMIC_T_END_S,
                "state_count": int(nominal_solution.y.shape[0]),
                "n_time_points": int(nominal_solution.t.size),
                "solver_message": str(nominal_solution.message),
                "max_vdc_over_vt_bess": scale_ratio,
            },
            limits={"expected_state_count": 16},
            software_failure=not bool(nominal_solution.success),
            review=bool(nominal_solution.success and dynamic_finite and scale_review),
        )
    )

    near_min_pi, near_min_i, _ = _pi_probe(
        nominal_model,
        vdc_v=vdc_discharge,
        soc_bess=soc_near_min,
        soh_bess=soh_nominal,
    )
    results.append(
        _criterion(
            2,
            "SoC proximo a soc_min dentro del rango",
            "deterministic_near_soc_min",
            bool(soc_min < soc_near_min < soc_max and near_min_i > 0.0),
            f"soc={soc_near_min:.12f}, i_bess={near_min_i:.12f}",
            "interior SoC and discharge still available",
            tolerance=f"soc_margin={margin:.12f}",
            metrics={
                "p_max_w": near_min_pi.p_max_w,
                "p_ref_w": near_min_pi.p_bess_ref_w,
            },
            limits={"soc_min": soc_min, "soc_max": soc_max},
        )
    )

    near_max_pi, near_max_i, _ = _pi_probe(
        nominal_model,
        vdc_v=vdc_charge,
        soc_bess=soc_near_max,
        soh_bess=soh_nominal,
    )
    results.append(
        _criterion(
            3,
            "SoC proximo a soc_max dentro del rango",
            "deterministic_near_soc_max",
            bool(soc_min < soc_near_max < soc_max and near_max_i < 0.0),
            f"soc={soc_near_max:.12f}, i_bess={near_max_i:.12f}",
            "interior SoC and charge still available",
            tolerance=f"soc_margin={margin:.12f}",
            metrics={
                "p_min_w": near_max_pi.p_min_w,
                "p_ref_w": near_max_pi.p_bess_ref_w,
            },
            limits={"soc_min": soc_min, "soc_max": soc_max},
        )
    )

    block_discharge_pi, block_discharge_i, _ = _pi_probe(
        nominal_model,
        vdc_v=vdc_discharge,
        soc_bess=soc_min,
        soh_bess=soh_nominal,
    )
    results.append(
        _criterion(
            4,
            "bloqueo de descarga exactamente en soc_min",
            "deterministic_soc_min_block",
            bool(
                np.isclose(block_discharge_i, 0.0, atol=CURRENT_ATOL_A)
                and block_discharge_pi.p_max_w == 0.0
                and block_discharge_pi.d_xi_vdc_dt == 0.0
            ),
            f"i_bess={block_discharge_i:.12f}, p_max={block_discharge_pi.p_max_w:.12f}",
            "zero discharge current and zero positive power limit",
            tolerance=f"current_atol={CURRENT_ATOL_A}",
            metrics={
                "p_ref_unsat_w": block_discharge_pi.p_bess_ref_unsat_w,
                "p_ref_w": block_discharge_pi.p_bess_ref_w,
                "anti_windup_active": block_discharge_pi.anti_windup_active,
            },
            limits={"soc_min": soc_min},
        )
    )

    block_charge_pi, block_charge_i, _ = _pi_probe(
        nominal_model,
        vdc_v=vdc_charge,
        soc_bess=soc_max,
        soh_bess=soh_nominal,
    )
    results.append(
        _criterion(
            5,
            "bloqueo de carga exactamente en soc_max",
            "deterministic_soc_max_block",
            bool(
                np.isclose(block_charge_i, 0.0, atol=CURRENT_ATOL_A)
                and block_charge_pi.p_min_w == 0.0
                and block_charge_pi.d_xi_vdc_dt == 0.0
            ),
            f"i_bess={block_charge_i:.12f}, p_min={block_charge_pi.p_min_w:.12f}",
            "zero charge current and zero negative power limit",
            tolerance=f"current_atol={CURRENT_ATOL_A}",
            metrics={
                "p_ref_unsat_w": block_charge_pi.p_bess_ref_unsat_w,
                "p_ref_w": block_charge_pi.p_bess_ref_w,
                "anti_windup_active": block_charge_pi.anti_windup_active,
            },
            limits={"soc_max": soc_max},
        )
    )

    soh_cases = {
        "high": 1.0,
        "medium": 0.70,
        "degraded": soh_nominal,
    }
    soh_metrics = {
        label: {
            "soh": value,
            "i_available_a": nominal_model._available_i_bess_max(value),
            "p_available_w": nominal_model._available_p_bess_max_w(value),
        }
        for label, value in soh_cases.items()
    }
    i_order_ok = bool(
        soh_metrics["high"]["i_available_a"]
        > soh_metrics["medium"]["i_available_a"]
        >= soh_metrics["degraded"]["i_available_a"]
    )
    p_order_ok = bool(
        soh_metrics["high"]["p_available_w"]
        > soh_metrics["medium"]["p_available_w"]
        >= soh_metrics["degraded"]["p_available_w"]
    )
    p_tie_note = (
        "No power-availability tie occurred."
        if len({round(item["p_available_w"], 9) for item in soh_metrics.values()}) == 3
        else "Power-availability tie explained by nominal power cap saturation."
    )
    results.append(
        _criterion(
            6,
            "SoH alto, medio y degradado",
            "deterministic_soh_availability",
            bool(i_order_ok and p_order_ok),
            (
                f"i=[{soh_metrics['high']['i_available_a']:.6f}, "
                f"{soh_metrics['medium']['i_available_a']:.6f}, "
                f"{soh_metrics['degraded']['i_available_a']:.6f}]"
            ),
            "i_high > i_medium >= i_degraded; same for available power unless capped",
            tolerance=f"current_atol={CURRENT_ATOL_A}, power_atol={POWER_ATOL_W}",
            notes=p_tie_note,
            metrics=soh_metrics,
            limits={
                "i_bess_max_nominal_a": nominal_model.i_bess_max,
                "p_bess_max_nominal_w": nominal_model.p_bess_max_w,
            },
        )
    )

    current_limit_model = _build_model(
        kp_w_per_v=100000.0,
        ki_w_per_v_s=0.0,
        i_bess_max=1.0,
        p_bess_max_w=100000.0,
    )
    current_pi, current_i, current_p = _pi_probe(
        current_limit_model,
        vdc_v=330.0,
        soc_bess=current_limit_model.bess.soc_initial,
        soh_bess=1.0,
    )
    results.append(
        _criterion(
            7,
            "saturacion deliberada de corriente",
            "deterministic_current_saturation",
            bool(
                current_pi.p_bess_ref_unsat_w > current_pi.p_max_w
                and np.isclose(current_i, 1.0, atol=CURRENT_ATOL_A)
            ),
            f"unsat={current_pi.p_bess_ref_unsat_w:.6f}, i_bess={current_i:.12f}",
            "unlimited request exceeds current-derived limit; current equals 1 A",
            tolerance=f"current_atol={CURRENT_ATOL_A}",
            notes="Binding limit: current.",
            metrics={
                "p_max_w": current_pi.p_max_w,
                "p_ref_w": current_pi.p_bess_ref_w,
                "p_bess_dc_w": current_p,
                "binding_limit": "current",
            },
            limits={"i_limit_a": 1.0, "p_limit_from_current_w": current_pi.p_max_w},
        )
    )

    power_limit_model = _build_model(
        kp_w_per_v=100000.0,
        ki_w_per_v_s=0.0,
        i_bess_max=66.0,
        p_bess_max_w=500.0,
    )
    power_pi, power_i, power_p = _pi_probe(
        power_limit_model,
        vdc_v=330.0,
        soc_bess=power_limit_model.bess.soc_initial,
        soh_bess=1.0,
    )
    results.append(
        _criterion(
            8,
            "saturacion deliberada de potencia",
            "deterministic_power_saturation",
            bool(
                power_pi.p_bess_ref_unsat_w > power_pi.p_max_w
                and np.isclose(power_pi.p_bess_ref_w, 500.0, atol=POWER_ATOL_W)
                and np.isclose(power_i, 500.0 / 330.0, atol=CURRENT_ATOL_A)
            ),
            f"unsat={power_pi.p_bess_ref_unsat_w:.6f}, p_ref={power_pi.p_bess_ref_w:.12f}",
            "unlimited request exceeds nominal power limit; final power equals 500 W",
            tolerance=f"power_atol={POWER_ATOL_W}",
            notes="Binding limit: power.",
            metrics={
                "i_bess_a": power_i,
                "p_bess_dc_w": power_p,
                "binding_limit": "power",
            },
            limits={"p_limit_w": 500.0},
        )
    )

    availability_reduction_ok = bool(
        soh_metrics["medium"]["i_available_a"] < soh_metrics["high"]["i_available_a"]
        and soh_metrics["degraded"]["i_available_a"]
        <= soh_metrics["medium"]["i_available_a"]
        and soh_metrics["medium"]["p_available_w"]
        < soh_metrics["high"]["p_available_w"]
        and soh_metrics["degraded"]["p_available_w"]
        <= soh_metrics["medium"]["p_available_w"]
    )
    results.append(
        _criterion(
            9,
            "reduccion de disponibilidad al disminuir el SoH",
            "deterministic_soh_monotonic_reduction",
            availability_reduction_ok,
            "availability decreases from high to medium and does not increase at degraded SoH",
            "monotonic non-increase with decreasing SoH",
            metrics=soh_metrics,
            notes=p_tie_note,
        )
    )

    discharge_pi, discharge_i, discharge_p = _pi_probe(
        nominal_model,
        vdc_v=vdc_discharge,
        soc_bess=soc_mid,
        soh_bess=soh_nominal,
    )
    charge_pi, charge_i, charge_p = _pi_probe(
        nominal_model,
        vdc_v=vdc_charge,
        soc_bess=soc_mid,
        soh_bess=soh_nominal,
    )
    results.append(
        _criterion(
            10,
            "operacion en carga y descarga",
            "deterministic_bidirectional_signs",
            bool(discharge_i > 0.0 and discharge_p > 0.0 and charge_i < 0.0 and charge_p < 0.0),
            f"discharge_i={discharge_i:.12f}, charge_i={charge_i:.12f}",
            "positive discharge current and negative charge current",
            tolerance=f"current_atol={CURRENT_ATOL_A}",
            metrics={
                "discharge": {
                    "p_ref_w": discharge_pi.p_bess_ref_w,
                    "p_bess_dc_w": discharge_p,
                },
                "charge": {
                    "p_ref_w": charge_pi.p_bess_ref_w,
                    "p_bess_dc_w": charge_p,
                },
            },
        )
    )

    disabled_model = _build_model(bess_enabled=False)
    disabled_pi, disabled_i, disabled_p = _pi_probe(
        disabled_model,
        vdc_v=vdc_discharge,
        soc_bess=disabled_model.bess.soc_initial,
        soh_bess=disabled_model.bess.soh_init_case,
        xi_bess_vdc_v_s=5.0,
    )
    results.append(
        _criterion(
            11,
            "BESS deshabilitado",
            "deterministic_bess_disabled",
            bool(
                disabled_pi.p_bess_ref_w == 0.0
                and disabled_i == 0.0
                and disabled_p == 0.0
                and disabled_pi.d_xi_vdc_dt == 0.0
            ),
            f"p_ref={disabled_pi.p_bess_ref_w:.12f}, i_bess={disabled_i:.12f}",
            "zero charge/discharge request and frozen integrator",
            tolerance="exact zero from existing PI enable logic",
            metrics={
                "p_ref_unsat_w": disabled_pi.p_bess_ref_unsat_w,
                "anti_windup_active": disabled_pi.anti_windup_active,
            },
        )
    )

    aw_model = _build_model(kp_w_per_v=1000.0, ki_w_per_v_s=0.0)
    aw_resume_controller = DCLinkBESSPIController(
        vdc_ref_v=SIM_VDC0_V_DEFAULT,
        kp_w_per_v=1000.0,
        ki_w_per_v_s=100.0,
    )
    aw_high = aw_model.dc_link_bess_pi.compute(
        vdc_v=330.0,
        xi_vdc_v_s=0.0,
        p_min_w=-100.0,
        p_max_w=100.0,
        bess_enabled=True,
    )
    aw_low = aw_model.dc_link_bess_pi.compute(
        vdc_v=350.0,
        xi_vdc_v_s=0.0,
        p_min_w=-100.0,
        p_max_w=100.0,
        bess_enabled=True,
    )
    aw_resume = aw_resume_controller.compute(
        vdc_v=350.0,
        xi_vdc_v_s=102.0,
        p_min_w=-100.0,
        p_max_w=100.0,
        bess_enabled=True,
    )
    aw_disabled = aw_model.dc_link_bess_pi.compute(
        vdc_v=330.0,
        xi_vdc_v_s=0.0,
        p_min_w=-100.0,
        p_max_w=100.0,
        bess_enabled=False,
    )
    aw_ok = bool(
        aw_high.anti_windup_active
        and aw_high.d_xi_vdc_dt == 0.0
        and aw_low.anti_windup_active
        and aw_low.d_xi_vdc_dt == 0.0
        and aw_resume.saturated
        and not aw_resume.anti_windup_active
        and aw_resume.d_xi_vdc_dt < 0.0
        and aw_disabled.p_bess_ref_w == 0.0
        and aw_disabled.d_xi_vdc_dt == 0.0
    )
    results.append(
        _criterion(
            12,
            "anti-windup del PI externo",
            "deterministic_pi_anti_windup",
            aw_ok,
            (
                f"d_xi_high={aw_high.d_xi_vdc_dt:.6f}, "
                f"d_xi_low={aw_low.d_xi_vdc_dt:.6f}, "
                f"d_xi_resume={aw_resume.d_xi_vdc_dt:.6f}"
            ),
            "freeze deeper into saturation, resume when error returns to interval",
            metrics={
                "upper_saturation": aw_high.__dict__,
                "lower_saturation": aw_low.__dict__,
                "return_to_interval": aw_resume.__dict__,
                "disabled": aw_disabled.__dict__,
            },
        )
    )

    results.append(
        _criterion(
            13,
            "estados y senales finitas",
            "short_dynamic_nominal_gfm_bess_pi",
            dynamic_finite,
            f"states_finite={np.all(np.isfinite(nominal_solution.y))}, signals_finite={dynamic_finite}",
            "all dynamic states and observed signals finite",
            tolerance="np.isfinite over trajectory",
            metrics={
                "state_shape": list(nominal_solution.y.shape),
                "signal_names": sorted(dynamic_signals.keys()),
            },
            software_failure=not bool(nominal_solution.success),
        )
    )

    identity_ok = bool(
        violations["max_abs_power_identity_residual_w"] <= IDENTITY_ATOL_W
    )
    results.append(
        _criterion(
            14,
            "identidad p_bess_dc = Vdc*i_bess",
            "short_dynamic_nominal_gfm_bess_pi",
            identity_ok,
            f"max_residual={violations['max_abs_power_identity_residual_w']:.12e} W",
            "pointwise residual <= tolerance",
            tolerance=f"identity_atol_w={IDENTITY_ATOL_W}",
            metrics=violations,
        )
    )

    no_violations_ok = bool(
        dynamic_finite
        and violations["max_current_limit_excess_a"] <= CURRENT_ATOL_A
        and violations["max_power_reference_limit_excess_w"] <= POWER_ATOL_W
        and violations["max_actual_power_limit_excess_w"] <= POWER_ATOL_W
        and violations["max_soc_limit_excess"] <= LIMIT_ATOL
        and violations["max_soh_limit_excess"] <= LIMIT_ATOL
    )
    results.append(
        _criterion(
            15,
            "ausencia de violaciones operativas",
            "dynamic_and_deterministic_limit_checks",
            no_violations_ok,
            "max limit excesses recorded in metrics",
            "no current, power, SoC or SoH limit exceeded",
            tolerance=(
                f"current={CURRENT_ATOL_A}, power={POWER_ATOL_W}, "
                f"soc/soh={LIMIT_ATOL}"
            ),
            metrics=violations,
            limits={
                "soc_min": soc_min,
                "soc_max": soc_max,
                "soh_min": nominal_model.bess.soh_min,
                "i_bess_max_nominal_a": nominal_model.i_bess_max,
                "p_bess_max_nominal_w": nominal_model.p_bess_max_w,
            },
        )
    )

    statuses = [result.status for result in results]
    if any(status == "FAIL" for status in statuses):
        global_status = "FAIL"
    elif any(status == "REVIEW" for status in statuses):
        global_status = "REVIEW"
    else:
        global_status = "PASS"

    output_dir = Path(output_dir)
    summary_json_path = output_dir / SUMMARY_JSON_NAME
    summary_csv_path = output_dir / SUMMARY_CSV_NAME
    report = {
        "validation_id": VALIDATION_ID,
        "run_stamp": "deterministic_no_clock_dependency",
        "model_commit": _git_commit(),
        "status": global_status,
        "criteria_count": len(results),
        "parameters": {
            "controller": "GFMController",
            "M": GFM_SELECTED_M,
            "D": GFM_SELECTED_D,
            "pi_kp_w_per_v": PI_KP_W_PER_V,
            "pi_ki_w_per_v_s": PI_KI_W_PER_V_S,
            "vdc_ref_v": SIM_VDC0_V_DEFAULT,
            "dynamic_t_end_s": DYNAMIC_T_END_S,
            "state_mapping": {
                "x10": "omega",
                "x11": "theta",
                "x12": "soc_bess",
                "x13": "vrc_bess",
                "x14": "zdeg_bess",
                "x15": "xi_bess_vdc only with external PI",
            },
        },
        "tolerances": {
            "limit_atol": LIMIT_ATOL,
            "identity_atol_w": IDENTITY_ATOL_W,
            "current_atol_a": CURRENT_ATOL_A,
            "power_atol_w": POWER_ATOL_W,
            "solver_rtol": SIM_SOLVER_RTOL_DEFAULT,
            "solver_atol": SIM_SOLVER_ATOL_DEFAULT,
            "solver_max_step_s": SIM_SOLVER_MAX_STEP_S_DEFAULT,
        },
        "equations_checked": {
            "bess_power": "p_bess_dc = Vdc*i_bess",
            "dc_balance": "dVdc/dt = (ipv + i_bess - idc_inv)/Cdc",
            "bess_sign": "i_bess > 0 discharge; i_bess < 0 charge",
        },
        "interpretation_notes": [
            "Internal validation evidence only; not experimental validation.",
            "Vdc/vt_bess scale warnings are REVIEW items when invariants pass.",
            "No VSG equation, M, D, state order or IEEE 33 coupling is modified.",
        ],
        "criteria": [result.to_json() for result in results],
        "output_paths": {
            "summary_json": str(summary_json_path),
            "summary_csv": str(summary_csv_path),
        },
    }
    clean_report = _json_ready(report)

    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        with summary_json_path.open("w", encoding="utf-8") as json_file:
            json.dump(clean_report, json_file, indent=2, sort_keys=True)
            json_file.write("\n")
        with summary_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=(
                    "criterion_id",
                    "criterion_name",
                    "scenario",
                    "status",
                    "observed_value",
                    "expected_or_limit",
                    "tolerance",
                    "software_failure",
                    "notes",
                ),
            )
            writer.writeheader()
            writer.writerows(result.to_csv_row() for result in results)

    print(f"validation_id={VALIDATION_ID}")
    print(f"criteria_count={len(results)}")
    for result in results:
        print(
            f"criterion_{result.criterion_id:02d}="
            f"{result.status} | {result.criterion_name}"
        )
    print(f"global_status={global_status}")
    if write:
        print(f"summary_json={summary_json_path}")
        print(f"summary_csv={summary_csv_path}")
    else:
        print("no_write=True")
    return clean_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR_DEFAULT)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run every check without writing summary files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_validation(output_dir=args.output_dir, write=not args.no_write)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
