"""BAT26-46: fixed-SoH operational contrasts at four BAT26-45 checkpoints.

The 1RC 60-minute comparison uses the SAME positive battery-port current at
every SoH level. It is not a 340-V DC-bus/2p converter model. A separate
6.5-second GFM comparison reuses the repository's protected 15-state validator.
BLAST is not rerun; published BAT26-45 capacities are rounded scenario inputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.compare_bess_soh_scenarios import (
    _build_bess_for_soh, _simulate_gfm_soh_case,
)
from config import BESS_COUPLED_Q_NOM_REF_AH_DEFAULT

# Rounded outputs reported from BAT26-45 (not experimental measurements).
# Use exact BLAST cycle_history.csv for a future precision/sensitivity study.
BAT45_ROUNDED_CAPACITIES = (
    (0, 44.100),
    (100, 42.273),
    (500, 39.038),
    (1000, 35.854),
)
BATTERY_PORT_I_A = 8.0    # positive = discharge; explicitly synthetic 2p current
DURATION_S = 3600.0
OUT_PARENT = ROOT / "outputs" / "analysis" / "bat26_46_soh_levels"


def _git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _scenario_valid() -> None:
    cases = BAT45_ROUNDED_CAPACITIES
    nominal = float(BESS_COUPLED_Q_NOM_REF_AH_DEFAULT)
    if (len(cases) != 4 or [c[0] for c in cases] != [0, 100, 500, 1000]
            or not all(0.5 <= q / nominal <= 1.0 for _, q in cases)
            or not all(a[1] > b[1] for a, b in zip(cases, cases[1:]))
            or not np.isclose(cases[0][1], 44.1)):
        raise ValueError("BAT26-45 capacity checkpoint inputs are inconsistent")


def _one_hour_port_current(cycle: int, capacity_ah: float):
    """Discharge each independently initialized 1RC model at constant 8 A."""
    nominal = float(BESS_COUPLED_Q_NOM_REF_AH_DEFAULT)
    model = _build_bess_for_soh(capacity_ah / nominal)
    x0 = model.initial_state_with_degradation(
        soc=model.soc_initial, v_rc=0.0, z_deg=0.0,
    )
    t = np.linspace(0.0, DURATION_S, 121)
    solution = solve_ivp(
        lambda ts, x: model.rhs(
            t=ts, x=x, i_bess=BATTERY_PORT_I_A,
            soh=model.soh_from_z_deg(float(x[2])),
        ),
        (0.0, DURATION_S),
        x0,
        t_eval=t,
        max_step=60.0,
        rtol=1e-9,
        atol=1e-11,
    )
    if not solution.success or solution.y.shape != (3, t.size):
        raise RuntimeError(f"1RC solver unsuccessful at cycle {cycle}: {solution.message}")
    soc, vrc, zdeg = solution.y
    soh = np.asarray([model.soh_from_z_deg(float(x)) for x in zdeg])
    v_terminal = np.asarray([
        model.terminal_voltage(
            soc=float(s), v_rc=float(v), i_bess=BATTERY_PORT_I_A,
            soh=float(h),
        )
        for s, v, h in zip(soc, vrc, soh)
    ])
    limits_ok = bool(
        np.all(np.isfinite(solution.y))
        and np.all(np.isfinite(v_terminal))
        and np.all(v_terminal > 0)
        and np.all(soc >= model.soc_min - 1e-8)
        and np.all(soc <= model.soc_max + 1e-8)
        and np.all(soh >= model.soh_min)
        and np.all(soh <= 1.0)
    )
    q_initial = model.effective_capacity_ah(soh=model.soh_init_case)
    coulomb_approx = BATTERY_PORT_I_A * DURATION_S / (3600.0 * q_initial)
    coherent_coulomb = abs(
        (float(soc[0]) - float(soc[-1])) - coulomb_approx
    ) < 1e-4
    current_allowed = BATTERY_PORT_I_A <= 66.0 * model.soh_init_case
    if not (limits_ok and coherent_coulomb and current_allowed):
        raise RuntimeError(f"1RC state/current contract failed at cycle {cycle}")
    row = {
        "checkpoint_cycles": cycle,
        "qeff_at_checkpoint_ah": q_initial,
        "soh_at_checkpoint_pct": 100.0 * model.soh_init_case,
        "battery_port_current_a": BATTERY_PORT_I_A,
        "soc_initial": float(soc[0]),
        "soc_final": float(soc[-1]),
        "delta_soc_pp": 100.0 * (float(soc[-1]) - float(soc[0])),
        "q_eff_after_1h_ah": model.effective_capacity_ah(
            soh=float(soh[-1])
        ),
        "ideal_usable_ah_soc_0p6_to_0p1": (0.6 - model.soc_min) * q_initial,
        "ideal_autonomy_h_at_8a_soc_0p6_to_0p1":
            (0.6 - model.soc_min) * q_initial / BATTERY_PORT_I_A,
        "terminal_energy_Wh_modelled": float(
            np.trapezoid(v_terminal * BATTERY_PORT_I_A, t) / 3600.0
        ),
        "terminal_voltage_min_v": float(np.min(v_terminal)),
        "terminal_voltage_max_v": float(np.max(v_terminal)),
        "checks": {
            "solver_success": bool(solution.success),
            "finite_states_and_positive_terminal_voltage": limits_ok,
            "charge_conservation": coherent_coulomb,
            "within_soh_dependent_current_limit": current_allowed,
        },
    }
    return row, t, soc


def _gfm_case(cycle: int, capacity_ah: float) -> dict:
    nominal = float(BESS_COUPLED_Q_NOM_REF_AH_DEFAULT)
    result, _ = _simulate_gfm_soh_case(
        label=f"BAT26-45_{cycle}_cycles", soh_case=capacity_ah / nominal,
    )
    keys = (
        "status", "hard_checks_ok", "scenario_configuration_ok", "M", "D",
        "soh_initial", "q_init_case_ah", "p_load_pre_step_w",
        "p_load_post_step_w", "load_step_pct", "i_bess_max_available_initial",
        "p_bess_dc_max_available_initial", "i_bess_peak_abs_a",
        "p_bess_peak_abs_w", "bess_energy_throughput_wh", "soc_swing",
        "max_frequency_drop_hz", "vdc_event_max_abs_deviation_pct",
        "bess_exchange_mode", "bess_discharge_observed",
        "frequency_criteria_pass", "vdc_criteria_pass", "review_reasons",
        "observations",
    )
    return {"checkpoint_cycles": cycle,
            **{k: result[k] for k in keys if k in result}}


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        columns = list(rows[0].keys())
        if "checks" in columns:
            columns.remove("checks")
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _plots(out: Path, rows: list[dict], traces) -> list[str]:
    fig, ax = plt.subplots(figsize=(10, 6))
    for cycle, t, soc in traces:
        ax.plot(t / 60.0, 100.0 * soc, label=f"{cycle} ciclos")
    ax.set(xlabel="Tiempo (min)", ylabel="SoC (%)",
           title="SoC durante 1 h: igual corriente sintética de 8 A")
    ax.grid(alpha=.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "soc_same_current.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    cycles = [item["checkpoint_cycles"] for item in rows]
    available = [item["ideal_usable_ah_soc_0p6_to_0p1"] for item in rows]
    ax.plot(cycles, available, marker="o")
    ax.set(xlabel="Ciclos sintéticos acumulados en BAT26-45",
           ylabel="Carga utilizable ideal hasta SoC 10 % (Ah)",
           title="Menor reserva de carga a igual SoC inicial")
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(out / "available_charge_vs_cycles.png", dpi=180)
    plt.close(fig)
    return ["soc_same_current.png", "available_charge_vs_cycles.png"]


def main() -> int:
    _scenario_valid()
    out = OUT_PARENT / datetime.now(timezone.utc).strftime(
        "run_%Y%m%dT%H%M%S_%fZ",
    )
    out.mkdir(parents=True, exist_ok=False)
    rows, gfm, traces = [], [], []
    error = None
    try:
        for cycle, capacity in BAT45_ROUNDED_CAPACITIES:
            r, t, soc = _one_hour_port_current(cycle, capacity)
            rows.append(r)
            traces.append((cycle, t, soc))
            gfm_row = _gfm_case(cycle, capacity)
            gfm.append(gfm_row)
            print(f"{cycle} cycles: SoH={r['soh_at_checkpoint_pct']:.4f}%"
                  f" | SoC final={r['soc_final']:.6f}"
                  f" | GFM={gfm_row.get('status')}", flush=True)
        if not all(item.get("hard_checks_ok") for item in gfm):
            raise RuntimeError("integrated GFM invariant failure in at least one case")
        if not all(gfm[i]["i_bess_max_available_initial"] >
                   gfm[i+1]["i_bess_max_available_initial"]
                   for i in range(len(gfm)-1)):
            raise RuntimeError("GFM current availability is not SoH-monotonic")
        if not all(rows[i]["soc_final"] > rows[i+1]["soc_final"]
                   for i in range(len(rows)-1)):
            raise RuntimeError("SoC discharge vs capacity is not monotonic")
        _csv(out / "comparison.csv", rows)
        plots = _plots(out, rows, traces)
    except Exception as exc:
        plots = []
        error = f"{type(exc).__name__}: {exc}"
    status = (
        "FAIL" if error or len(rows) != 4 or len(gfm) != 4 else
        "REVIEW" if any(item.get("status") == "REVIEW" for item in gfm) else
        "PASS"
    )
    source = ROOT / "src" / "validation" / "run_bat26_46_soh_levels.py"
    report = {
        "task": "BAT26-46",
        "status": status,
        "simulation_scope": "four 1RC battery-port one-hour tests plus four "
                            "6.5s selected-GFM 15-state transients",
        "source_profile": "rounded Qeff outputs from BAT26-45 report",
        "source_bat45_pr": 41,
        "no_new_blast_execution": True,
        "git_head": _git_head(),
        "python_version": sys.version.split()[0],
        "script_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "same_operating_conditions": {
            "current_a_all_1rc": BATTERY_PORT_I_A,
            "duration_s_all_1rc": DURATION_S,
            "soc_start_all": rows[0]["soc_initial"] if rows else None,
            "same_GFM_M_D_and_load_step_pct": "see selected GFM records",
        },
        "battery_port": rows,
        "gfm_selected": gfm,
        "plots": plots,
        "error": error,
        "limitations": [
            "Inputs are BAT26-45 rounded checkpoints, not raw BLAST history.",
            "Constant 8 A is a synthetic 2p battery-port current, not DC-bus current.",
            "1RC terminal energy is indicative and not pack/AC deliverable energy.",
            "The 6.5s GFM path uses existing 15-state architecture without external PI.",
            "SoH levels are independent initial conditions, not history replay.",
            "R0(SoH), OCV/R1/C1 parameters and DC/DC interface are uncalibrated.",
            "No experimental evidence, thermal model, or IEEE33 dynamic feedback.",
        ],
    }
    (out / "summary.json").write_text(json.dumps(
        report, ensure_ascii=False, indent=2, allow_nan=False,
    ) + "\n", encoding="utf-8")
    print(f"BAT26-46 {status} | {out.relative_to(ROOT)}", flush=True)
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
