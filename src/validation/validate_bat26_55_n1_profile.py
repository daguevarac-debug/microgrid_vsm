"""Execute BAT26-55 N1 with a preconditioned charge-to-discharge profile.

The DC/DC ratings and efficiencies are hypothetical validation fixtures. The
plant, Leaf ECM, GFM controller, limits, BLAST capacity snapshot and 15-state
layout are reused without modification.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.integrate import solve_ivp

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bess.leaf_48module_pack import Leaf48ModulePack
from config import BESS_COUPLED_R0_DEFAULT
from controllers.gfm_controller import GFMController
from microgrid import MicrogridWithBESS
from validation.validate_bat26_55_pack_bus_gfm import fixture_parameters
from validation.validate_bat26_55_pack_bus_gfm import build_battery


T_END_S = 1.20
SAMPLE_DT_S = 5e-4
MAX_STEP_S = 5e-5
RTOL = 1e-6
ATOL = 1e-9
MIN_WINDOW_S = 0.10
SOC0 = 0.60
QEFF_AH = 44.1
P_REF_W = 4000.0
M = 80.0
D = 1500.0
ETA_DCDC = 0.95
UNIT_CURRENT_LIMIT_A = 10.0
BUS_CURRENT_LIMIT_A = 20.0
BUS_POWER_LIMIT_W = 5000.0
OUTPUT_DEFAULT = ROOT / "outputs" / "validation" / "bat26_55_n1_profile.json"


def irradiance_profile(t: float) -> float:
    """800 W/m² precondition, solar surplus, then reduced irradiance."""
    if t < 0.40:
        return 800.0
    if t < 0.80:
        return 1000.0
    return 400.0


def load_profile(t: float) -> float:
    """Nominal precondition, -20% load, then the existing +40% load case."""
    if t < 0.40:
        return 3000.0
    if t < 0.80:
        return 2400.0
    return 4200.0


def longest_window(mask: np.ndarray, t: np.ndarray, start_s: float,
                   end_s: float) -> dict[str, float | None]:
    indices = np.flatnonzero((t >= start_s) & (t < end_s) & mask)
    if indices.size == 0:
        return {"duration_s": 0.0, "start_s": None, "end_s": None}
    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    selected = max(groups, key=len)
    return {
        "duration_s": float(t[selected[-1]] - t[selected[0]]),
        "start_s": float(t[selected[0]]),
        "end_s": float(t[selected[-1]]),
    }


def run_n1(output_path: Path = OUTPUT_DEFAULT) -> dict[str, object]:
    pack = Leaf48ModulePack(q_init_case_ah=QEFF_AH)
    battery = build_battery(QEFF_AH)
    params = fixture_parameters(
        pack,
        unit_current_a=UNIT_CURRENT_LIMIT_A,
        bus_current_a=BUS_CURRENT_LIMIT_A,
        bus_power_w=BUS_POWER_LIMIT_W,
    )
    model = MicrogridWithBESS(
        controller=GFMController(p_ref=P_REF_W, inertia_m=M, damping_d=D),
        bess_model=battery,
        irradiance_profile=irradiance_profile,
        load_profile=load_profile,
        leaf_pack=pack,
        dcdc_parameters=params,
        capacity_snapshot=pack.capacity(),
        aging_mode="blast",
        blast_profile_kind="synthetic",
    )

    t_eval = np.linspace(0.0, T_END_S, round(T_END_S / SAMPLE_DT_S) + 1)
    started = time.perf_counter()
    solution = solve_ivp(
        model.system_dynamics,
        (0.0, T_END_S),
        model.initial_state_with_bess(),
        method="RK45",
        rtol=RTOL,
        atol=ATOL,
        max_step=MAX_STEP_S,
        t_eval=t_eval,
    )
    elapsed_s = time.perf_counter() - started

    signals = [model.integrated_signals(float(t), solution.y[:, k])
               for k, t in enumerate(solution.t)]
    def values(name: str) -> np.ndarray:
        return np.asarray([float(row[name]) for row in signals], dtype=float)

    vdc = values("Vdc")
    i_pack = values("i_pack")
    i_bus = values("i_bus")
    p_pack = values("p_pack")
    p_bus = values("p_bus")
    loss = values("p_dcdc_loss")
    v_pack = values("v_pack")
    soc = values("soc_bess")
    soh = values("soh_bess")
    frequency = solution.y[10] / (2.0 * math.pi)
    saturation = {
        name: values(name) > 0.5 for name in (
            "dcdc_saturated", "dcdc_supervision_saturated",
            "dcdc_adapter_saturated", "dcdc_soc_blocked",
        )
    }
    protection_statuses = sorted({str(row["dcdc_protection_status"]) for row in signals})

    # Discard the initial 50 ms in the first active phase and the first 50 ms
    # after the second input change. Both required windows must persist beyond
    # those transition intervals.
    charge_mask = (i_pack < 0.0) & (i_bus < 0.0) & (p_bus < 0.0)
    discharge_mask = (i_pack > 0.0) & (i_bus > 0.0) & (p_bus > 0.0)
    charge_window = longest_window(charge_mask, solution.t, 0.45, 0.80)
    discharge_window = longest_window(discharge_mask, solution.t, 0.85, 1.20)

    power_residual = p_pack - p_bus - loss
    power_tolerance = 1e-8 + 1e-10 * np.maximum.reduce(
        (np.abs(p_pack), np.abs(p_bus), np.abs(loss), np.ones_like(loss))
    )
    bus_power_residual = p_bus - vdc * i_bus
    bus_power_tolerance = 1e-8 + 1e-10 * np.maximum.reduce(
        (np.abs(p_bus), np.abs(vdc * i_bus), np.ones_like(p_bus))
    )
    energy_pack_wh = float(np.trapezoid(p_pack, solution.t) / 3600.0)
    energy_bus_wh = float(np.trapezoid(p_bus, solution.t) / 3600.0)
    energy_loss_wh = float(np.trapezoid(loss, solution.t) / 3600.0)
    energy_residual_wh = energy_pack_wh - energy_bus_wh - energy_loss_wh
    absolute_transferred_energy_wh = float(
        np.trapezoid(np.abs(p_pack) + np.abs(p_bus), solution.t) / 3600.0
    )
    finite = bool(
        np.all(np.isfinite(solution.y))
        and all(np.all(np.isfinite(values(name))) for name in (
            "Vdc", "i_pack", "i_bus", "p_pack", "p_bus", "p_dcdc_loss",
            "v_pack", "soc_bess", "soh_bess",
        ))
        and np.all(np.isfinite(frequency))
    )
    max_i_pack = float(np.max(np.abs(i_pack)))
    max_i_bus = float(np.max(np.abs(i_bus)))
    max_p_bus = float(np.max(np.abs(p_bus)))
    max_i_pack_allowed = min(params.unit_discharge_max_a,
                             model._available_i_bess_max(float(np.min(soh))))
    checks = {
        "solver_success": bool(solution.success),
        "finite_states_signals": finite,
        "state_count_15": bool(solution.y.shape[0] == 15),
        "vdc_positive": bool(np.all(vdc > 0.0)),
        "soc_in_bounds": bool(np.all(soc >= pack.soc_min - 1e-9)
                               and np.all(soc <= pack.soc_max + 1e-9)),
        "pack_voltage_in_envelope": bool(np.all(v_pack >= pack.minimum_voltage_v)
                                         and np.all(v_pack <= pack.maximum_voltage_v)),
        "pack_current_within_limits": bool(max_i_pack <= max_i_pack_allowed + 1e-8),
        "bus_current_within_limit": bool(max_i_bus <= params.bus_current_max_a + 1e-8),
        "bus_power_within_limit": bool(max_p_bus <= params.bus_power_max_w + 1e-8),
        "converter_losses_nonnegative": bool(np.all(loss >= -1e-12)),
        "power_balance_residual_within_tolerance": bool(
            np.all(np.abs(power_residual) <= power_tolerance)
        ),
        "bus_power_identity_within_tolerance": bool(
            np.all(np.abs(bus_power_residual) <= bus_power_tolerance)
        ),
        "integrated_energy_balance_within_0p1pct": bool(
            absolute_transferred_energy_wh > 0.0
            and abs(energy_residual_wh) <= 0.001 * absolute_transferred_energy_wh
        ),
        "charge_window_at_least_0p10_s": bool(charge_window["duration_s"] >= MIN_WINDOW_S),
        "discharge_window_at_least_0p10_s": bool(discharge_window["duration_s"] >= MIN_WINDOW_S),
        "no_adapter_protection_trip": protection_statuses == ["ok"],
    }
    report: dict[str, object] = {
        "task": "BAT26-55 N1 optional Leaf pack–DC/DC–GFM integrated profile",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": "internal numerical validation; not measured hardware or HIL",
        "profile": {
            "segments": [
                {"start_s": 0.0, "end_s": 0.4, "irradiance_W_m2": 800.0, "load_W": 3000.0,
                 "role": "precondition"},
                {"start_s": 0.4, "end_s": 0.8, "irradiance_W_m2": 1000.0, "load_W": 2400.0,
                 "role": "charge-favoring surplus"},
                {"start_s": 0.8, "end_s": 1.2, "irradiance_W_m2": 400.0, "load_W": 4200.0,
                 "role": "discharge-favoring deficit"},
            ],
            "input_changes_at_s": [0.4, 0.8],
            "continuous_sign_windows_required_s": MIN_WINDOW_S,
            "evaluated_charge_window": charge_window,
            "evaluated_discharge_window": discharge_window,
        },
        "model": {
            "controller": "GFMController", "M": M, "D": D, "p_ref_W": P_REF_W,
            "state_count": int(solution.y.shape[0]), "state_mapping": "GFM+BESS 15-state",
            "qeff_initial_Ah": QEFF_AH, "soc_initial": SOC0,
            "capacity_snapshot_soh": float(pack.capacity().soh),
            "aging_mode": "BLAST synthetic with initial capacity snapshot",
            "frequency_definition": "omega / (2*pi)",
        },
        "converter_hypotheses_only": {
            "eta_charge": ETA_DCDC, "eta_discharge": ETA_DCDC,
            "unit_current_limit_A": UNIT_CURRENT_LIMIT_A,
            "bus_current_limit_A": BUS_CURRENT_LIMIT_A,
            "bus_power_limit_W": BUS_POWER_LIMIT_W,
        },
        "solver": {
            "method": "RK45", "rtol": RTOL, "atol": ATOL,
            "max_step_s": MAX_STEP_S, "sample_dt_s": SAMPLE_DT_S,
            "nfev": int(solution.nfev), "elapsed_s": elapsed_s,
            "success": bool(solution.success), "message": str(solution.message),
        },
        "metrics": {
            "soc_min": float(np.min(soc)), "soc_max": float(np.max(soc)),
            "soc_final": float(soc[-1]), "soh_initial": float(soh[0]),
            "soh_final": float(soh[-1]), "Vdc_min_V": float(np.min(vdc)),
            "Vdc_max_V": float(np.max(vdc)), "frequency_min_Hz": float(np.min(frequency)),
            "frequency_max_Hz": float(np.max(frequency)),
            "I_pack_max_abs_A": max_i_pack, "I_pack_allowed_max_A": max_i_pack_allowed,
            "I_bus_max_abs_A": max_i_bus, "P_bus_min_W": float(np.min(p_bus)),
            "P_bus_max_W": float(np.max(p_bus)), "P_bus_abs_max_W": max_p_bus,
            "V_pack_min_V": float(np.min(v_pack)), "V_pack_max_V": float(np.max(v_pack)),
            "converter_loss_max_W": float(np.max(loss)),
            "energy_pack_signed_Wh": energy_pack_wh,
            "energy_bus_signed_Wh": energy_bus_wh,
            "energy_loss_Wh": energy_loss_wh,
            "energy_balance_residual_Wh": energy_residual_wh,
            "absolute_transferred_energy_Wh": absolute_transferred_energy_wh,
            "max_abs_power_balance_residual_W": float(np.max(np.abs(power_residual))),
            "max_abs_bus_power_identity_residual_W": float(np.max(np.abs(bus_power_residual))),
            "saturation_fractions": {key: float(np.mean(flag)) for key, flag in saturation.items()},
            "protection_statuses": protection_statuses,
        },
        "checks": checks,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"output_path={output_path}")
    return report


if __name__ == "__main__":
    result = run_n1()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
