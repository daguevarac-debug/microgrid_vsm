"""24-hour QSTS campaign (1,440 min) with Vmaxpu=1.20 for the 4 PV-only scenarios.

Runs exclusively the 4 remaining PV-only scenarios (5,760 OpenDSS solves total):
- pv_near_34_direct
- pv_far_822_direct
- pv_near_34_xfmr_5kva
- pv_far_822_xfmr_5kva

Reuses the 3 previously validated Vmaxpu=1.20 scenarios (`base_no_dg`,
`pv_bess_near_34_xfmr_5kva`, `pv_bess_far_822_xfmr_5kva`) from
`outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_vs_pr57.json`
without re-running them, and consolidates the complete 7-scenario comparison
against PR #57 (`Vmaxpu=1.05`).

Does NOT modify Master.dss, canonical IEEE files, or prior validation artifacts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ieee_europe_lv_906_daily_pv import illustrative_pv_kw  # noqa: E402
from ieee_europe_lv_906_interface_and_qsts import (  # noqa: E402
    TRANSFORMER_SENSITIVITY_CASES,
    _bus_three_phase_pu,
)
from ieee_europe_lv_906_study import (  # noqa: E402
    EXPECTED_LINES,
    EXPECTED_LOADS,
    fetch_dataset,
    verify_dataset,
    write_study_master,
)

IMMUTABLE_OPENDSS_REF = "5005c668a72d20775f4c2d060feebb2866ba1d38"
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "ieee_europe_lv_906"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "experiment_vmaxpu_qsts_sensitivity"
PRIOR_3SC_JSON = DEFAULT_OUTPUT_DIR / "qsts_24h_vmaxpu1p20_vs_pr57.json"
PR57_CSV_PATH = REPO_ROOT / "outputs" / "analysis" / "ieee_europe_lv_906" / "qsts_24h_scenarios_comparison.csv"

PV_ONLY_SCENARIOS: tuple[tuple[str, str, bool], ...] = (
    ("pv_near_34_direct", "34", False),
    ("pv_far_822_direct", "822", False),
    ("pv_near_34_xfmr_5kva", "34", True),
    ("pv_far_822_xfmr_5kva", "822", True),
)

ALL_7_ORDER: tuple[str, ...] = (
    "base_no_dg",
    "pv_near_34_direct",
    "pv_far_822_direct",
    "pv_near_34_xfmr_5kva",
    "pv_far_822_xfmr_5kva",
    "pv_bess_near_34_xfmr_5kva",
    "pv_bess_far_822_xfmr_5kva",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_24h_pv_only_vmaxpu1p20(
    dss,
    study_master: Path,
    *,
    scenario_name: str,
    bus_num: str,
    use_xfmr_5kva: bool,
    peak_pv_kw: float = 3.0,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    dss.Basic.ClearAll()
    dss.Text.Command(f'compile "{study_master.resolve().as_posix()}"')
    if dss.Loads.Count() != EXPECTED_LOADS or dss.Lines.Count() != EXPECTED_LINES:
        raise AssertionError("Unexpected feeder topology")

    # Apply pure constant-PQ bound strictly in memory (Master.dss untouched)
    dss.Text.Command("batchedit load..* vmaxpu=1.20")
    dss.Text.Command("set controlmode=off")
    dss.Text.Command("set mode=yearly number=1 stepsize=1m")

    if use_xfmr_5kva:
        hyp = TRANSFORMER_SENSITIVITY_CASES[1]  # H2_YNyn0_zk4p2_r1p5_nominal_hyp (P0=0, %imag=0)
        r_half = hyp.r_total_pct / 2.0
        dss.Text.Command(
            f"New Transformer.T_DER phases=3 windings=2 "
            f"buses=[DER_LV.1.2.3 {bus_num}.1.2.3] "
            f"conns=[{hyp.conn_inv} {hyp.conn_grid}] "
            f"kVs=[{hyp.v_inv_ll_kv:.10f} {hyp.v_grid_ll_kv:.6f}] "
            f"kVAs=[{hyp.s_nom_kva:.4f} {hyp.s_nom_kva:.4f}] "
            f"XHL={hyp.xhl_pct:.4f} %Rs=[{r_half:.4f} {r_half:.4f}] %noloadloss=0 %imag=0"
        )
        dss.Text.Command(f"Set voltagebases=[11 0.416 {hyp.v_inv_ll_kv:.10f}]")
        dss.Text.Command("Calcvoltagebases")
        dss.Text.Command(
            f"New Generator.DER_VSG phases=3 bus1=DER_LV.1.2.3 "
            f"kV={hyp.v_inv_ll_kv:.10f} conn={hyp.conn_inv} kW=0 kvar=0 model=1"
        )
    else:
        dss.Text.Command(
            f"New Generator.DER_VSG phases=3 bus1={bus_num}.1.2.3 "
            f"kV=0.416 conn=wye kW=0 kvar=0 model=1"
        )

    all_loads = list(dss.Loads.AllNames())
    lv_buses: list[str] = []
    for bname in dss.Circuit.AllBusNames():
        if bname.lower() == "der_lv":
            continue
        dss.Circuit.SetActiveBus(bname)
        if 0 < dss.Bus.kVBase() < 1:
            lv_buses.append(bname)

    e_pv = e_load = e_import = e_loss_total = e_loss_xfmr = e_loss_feeder = 0.0
    max_pen = -1e9
    min_pen = 1e9
    abs_min_v = 1e9
    abs_max_v = -1e9
    min_above_1p05 = min_above_1p06 = min_above_1p10 = min_below_0p90 = 0
    max_imbalance = 0.0
    max_loads_outside_pq = 0
    v34_min = [1e9, 1e9, 1e9]
    v34_max = [-1e9, -1e9, -1e9]
    v822_min = [1e9, 1e9, 1e9]
    v822_max = [-1e9, -1e9, -1e9]
    noon_snap: dict[str, Any] | None = None
    eve_snap: dict[str, Any] | None = None

    for minute in range(1440):
        p_pv = illustrative_pv_kw(minute, peak_pv_kw)
        p_der_net = p_pv
        dss.Text.Command(f"edit Generator.DER_VSG kW={p_der_net:.9g}")

        dss.Solution.Hour(minute // 60)
        dss.Solution.Seconds((minute % 60) * 60)
        dss.Solution.Solve()
        if not dss.Solution.Converged():
            raise RuntimeError(f"Non-convergence in {scenario_name} at minute={minute}")

        p_load_kw = 0.0
        outside_pq = 0
        for lname in all_loads:
            dss.Circuit.SetActiveElement(f"Load.{lname}")
            p_load_kw += sum(dss.CktElement.Powers()[0::2])
            v_mag_v = float(dss.CktElement.VoltagesMagAng()[0])
            v_pu_load = v_mag_v / 230.0
            if v_pu_load > 1.20 or v_pu_load < 0.95:
                outside_pq += 1
        if outside_pq > max_loads_outside_pq:
            max_loads_outside_pq = outside_pq

        p_source_kw = -float(dss.Circuit.TotalPower()[0])
        p_loss_total_kw = float(dss.Circuit.Losses()[0]) / 1000.0
        xfmr_loss_kw = 0.0
        if use_xfmr_5kva:
            dss.Circuit.SetActiveElement("Transformer.T_DER")
            xfmr_loss_kw = float(dss.CktElement.Losses()[0]) / 1000.0
        feeder_loss_kw = p_loss_total_kw - xfmr_loss_kw

        imbalance_kw = p_source_kw + p_der_net - p_load_kw - p_loss_total_kw
        if abs(imbalance_kw) > max(0.10, 0.005 * max(p_load_kw, 1.0)):
            raise AssertionError(f"Power balance residual {imbalance_kw:+.6f} kW at minute {minute}")
        if abs(imbalance_kw) > max_imbalance:
            max_imbalance = abs(imbalance_kw)

        cur_min_v = 1e9
        cur_max_v = -1e9
        for bname in lv_buses:
            dss.Circuit.SetActiveBus(bname)
            for v in dss.Bus.puVmagAngle()[0::2]:
                if 0 < v < 2:
                    if v < cur_min_v:
                        cur_min_v = v
                    if v > cur_max_v:
                        cur_max_v = v

        if cur_min_v < abs_min_v:
            abs_min_v = cur_min_v
        if cur_max_v > abs_max_v:
            abs_max_v = cur_max_v
        if cur_max_v > 1.05:
            min_above_1p05 += 1
        if cur_max_v > 1.06:
            min_above_1p06 += 1
        if cur_max_v > 1.10:
            min_above_1p10 += 1
        if cur_min_v < 0.90:
            min_below_0p90 += 1

        v34 = _bus_three_phase_pu(dss, "34")
        v822 = _bus_three_phase_pu(dss, "822")
        for i in range(3):
            v34_min[i] = min(v34_min[i], v34[i])
            v34_max[i] = max(v34_max[i], v34[i])
            v822_min[i] = min(v822_min[i], v822[i])
            v822_max[i] = max(v822_max[i], v822[i])

        pen = 100.0 * p_der_net / p_load_kw if p_load_kw > 0 else 0.0
        max_pen = max(max_pen, pen)
        min_pen = min(min_pen, pen)

        e_pv += p_pv / 60.0
        e_load += p_load_kw / 60.0
        e_import += p_source_kw / 60.0
        e_loss_total += p_loss_total_kw / 60.0
        e_loss_xfmr += xfmr_loss_kw / 60.0
        e_loss_feeder += feeder_loss_kw / 60.0

        if minute in (720, 1140):
            snap = {
                "minute": minute,
                "p_der_net_kw": round(p_der_net, 6),
                "p_load_kw": round(p_load_kw, 6),
                "p_source_kw": round(p_source_kw, 6),
                "p_loss_total_kw": round(p_loss_total_kw, 6),
                "p_loss_xfmr_der_kw": round(xfmr_loss_kw, 6),
                "p_loss_feeder_only_kw": round(feeder_loss_kw, 6),
                "min_v_lv_pu": round(cur_min_v, 7),
                "max_v_lv_pu": round(cur_max_v, 7),
            }
            if minute == 720:
                noon_snap = snap
            else:
                eve_snap = snap

    wall_s = round(time.perf_counter() - t0, 3)
    return {
        "scenario": scenario_name,
        "bus": bus_num,
        "use_xfmr_5kva": use_xfmr_5kva,
        "with_bess_profile": False,
        "vmaxpu": 1.20,
        "samples": 1440,
        "wall_s": wall_s,
        "e_pv_synthetic_kwh": round(e_pv, 6),
        "e_bess_charge_kwh": 0.0,
        "e_bess_discharge_kwh": 0.0,
        "e_bess_net_ac_kwh": 0.0,
        "e_der_net_injected_kwh": round(e_pv, 6),
        "e_load_demand_kwh": round(e_load, 6),
        "e_grid_import_kwh": round(e_import, 6),
        "e_loss_total_kwh": round(e_loss_total, 6),
        "e_loss_xfmr_der_kwh": round(e_loss_xfmr, 6),
        "e_loss_feeder_only_kwh": round(e_loss_feeder, 6),
        "daily_energy_share_pct": round(100.0 * e_pv / e_load, 4),
        "max_instantaneous_penetration_pct": round(max_pen, 4),
        "min_instantaneous_penetration_pct": round(min_pen, 4),
        "abs_min_lv_pu": round(abs_min_v, 7),
        "abs_max_lv_pu": round(abs_max_v, 7),
        "minutes_above_1p05_pu": min_above_1p05,
        "minutes_above_1p06_pu": min_above_1p06,
        "minutes_above_1p10_pu": min_above_1p10,
        "minutes_below_0p90_pu": min_below_0p90,
        "max_power_balance_residual_kw": round(max_imbalance, 6),
        "max_loads_outside_pq_count": max_loads_outside_pq,
        "v_34_min_max_pu": [[round(v34_min[i], 6), round(v34_max[i], 6)] for i in range(3)],
        "v_822_min_max_pu": [[round(v822_min[i], 6), round(v822_max[i], 6)] for i in range(3)],
        "noon_snapshot": noon_snap,
        "evening_peak_snapshot_min1140": eve_snap,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-ref", default=IMMUTABLE_OPENDSS_REF)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()

    import opendssdirect as dss
    import dss as dss_py

    t_total = time.perf_counter()
    data_dir = args.data_dir.resolve()
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.download or not (data_dir / "source_manifest.json").is_file():
        fetch_dataset(data_dir, args.source_ref)
    verify_dataset(data_dir)
    manifest = json.loads((data_dir / "source_manifest.json").read_text(encoding="utf-8"))
    study_master = write_study_master(data_dir)

    # Load 3 already-validated Vmaxpu=1.20 scenarios without re-running them
    prior_payload = json.loads(PRIOR_3SC_JSON.read_text(encoding="utf-8"))
    by_name: dict[str, dict[str, Any]] = {
        s["scenario"]: s for s in prior_payload["scenarios_24h_vmaxpu1p20"]
    }
    base = by_name["base_no_dg"]

    # Run ONLY the 4 remaining PV-only scenarios (5,760 solves)
    new_pv_only: list[dict[str, Any]] = []
    for sc_name, bus_num, use_xfmr in PV_ONLY_SCENARIOS:
        r = run_24h_pv_only_vmaxpu1p20(
            dss,
            study_master,
            scenario_name=sc_name,
            bus_num=bus_num,
            use_xfmr_5kva=use_xfmr,
        )
        r["delta_feeder_loss_kwh_vs_base"] = round(r["e_loss_feeder_only_kwh"] - base["e_loss_feeder_only_kwh"], 6)
        r["delta_feeder_loss_pct_vs_base"] = round(
            100.0 * (r["e_loss_feeder_only_kwh"] - base["e_loss_feeder_only_kwh"]) / base["e_loss_feeder_only_kwh"], 4
        )
        r["delta_total_loss_kwh_vs_base"] = round(r["e_loss_total_kwh"] - base["e_loss_total_kwh"], 6)
        r["delta_total_loss_pct_vs_base"] = round(
            100.0 * (r["e_loss_total_kwh"] - base["e_loss_total_kwh"]) / base["e_loss_total_kwh"], 4
        )
        r["delta_grid_import_kwh_vs_base"] = round(r["e_grid_import_kwh"] - base["e_grid_import_kwh"], 6)
        r["delta_load_demand_kwh_vs_base"] = round(r["e_load_demand_kwh"] - base["e_load_demand_kwh"], 6)
        new_pv_only.append(r)
        by_name[sc_name] = r

    all7_1p20 = [by_name[name] for name in ALL_7_ORDER]

    # Load all 7 PR #57 Vmaxpu=1.05 scenarios for direct contrast
    pr57_rows: dict[str, dict[str, Any]] = {}
    with PR57_CSV_PATH.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pr57_rows[row["scenario"]] = row

    paired_rows: list[dict[str, Any]] = []
    for r in all7_1p20:
        sc = r["scenario"]
        p57 = pr57_rows[sc]
        paired_rows.append({
            "scenario": sc,
            "bus": r["bus"],
            "use_xfmr_5kva": r["use_xfmr_5kva"],
            "with_bess_profile": r["with_bess_profile"],
            "e_der_net_kwh": r["e_der_net_injected_kwh"],
            "e_load_1p05_kwh": float(p57["e_load_demand_kwh"]),
            "e_load_1p20_kwh": r["e_load_demand_kwh"],
            "delta_e_load_1p20_vs_1p05_pct": round(
                100.0 * (r["e_load_demand_kwh"] - float(p57["e_load_demand_kwh"])) / float(p57["e_load_demand_kwh"]), 4
            ),
            "e_import_1p05_kwh": float(p57["e_grid_import_kwh"]),
            "e_import_1p20_kwh": r["e_grid_import_kwh"],
            "delta_e_import_1p20_vs_1p05_pct": round(
                100.0 * (r["e_grid_import_kwh"] - float(p57["e_grid_import_kwh"])) / float(p57["e_grid_import_kwh"]), 4
            ),
            "e_loss_feeder_1p05_kwh": float(p57["e_loss_feeder_only_kwh"]),
            "e_loss_feeder_1p20_kwh": r["e_loss_feeder_only_kwh"],
            "delta_e_loss_feeder_1p20_vs_1p05_pct": round(
                100.0 * (r["e_loss_feeder_only_kwh"] - float(p57["e_loss_feeder_only_kwh"])) / float(p57["e_loss_feeder_only_kwh"]), 4
            ),
            "e_loss_xfmr_1p05_kwh": float(p57["e_loss_xfmr_der_kwh"]),
            "e_loss_xfmr_1p20_kwh": r["e_loss_xfmr_der_kwh"],
            "e_loss_total_1p05_kwh": float(p57["e_loss_total_kwh"]),
            "e_loss_total_1p20_kwh": r["e_loss_total_kwh"],
            "delta_e_loss_total_1p20_vs_1p05_pct": round(
                100.0 * (r["e_loss_total_kwh"] - float(p57["e_loss_total_kwh"])) / float(p57["e_loss_total_kwh"]), 4
            ),
            "delta_feeder_vs_base_1p05_pct": float(p57["delta_feeder_loss_pct_vs_base"]),
            "delta_feeder_vs_base_1p20_pct": r["delta_feeder_loss_pct_vs_base"],
            "delta_total_vs_base_1p05_pct": float(p57["delta_total_loss_pct_vs_base"]),
            "delta_total_vs_base_1p20_pct": r["delta_total_loss_pct_vs_base"],
            "abs_min_lv_1p05_pu": float(p57["abs_min_lv_pu"]),
            "abs_min_lv_1p20_pu": r["abs_min_lv_pu"],
            "abs_max_lv_1p05_pu": float(p57["abs_max_lv_pu"]),
            "abs_max_lv_1p20_pu": r["abs_max_lv_pu"],
            "min_above_1p05_1p05": int(p57["minutes_above_1p05_pu"]),
            "min_above_1p05_1p20": r["minutes_above_1p05_pu"],
            "min_above_1p06_1p05": int(p57["minutes_above_1p06_pu"]),
            "min_above_1p06_1p20": r["minutes_above_1p06_pu"],
        })

    wall_total_s = round(time.perf_counter() - t_total, 3)

    # Save consolidated 7-scenario Vmaxpu=1.20 CSV
    csv_fields = [
        "scenario", "bus", "use_xfmr_5kva", "with_bess_profile", "vmaxpu", "samples", "wall_s",
        "e_pv_synthetic_kwh", "e_bess_charge_kwh", "e_bess_discharge_kwh", "e_bess_net_ac_kwh",
        "e_der_net_injected_kwh", "e_load_demand_kwh", "e_grid_import_kwh",
        "e_loss_total_kwh", "e_loss_xfmr_der_kwh", "e_loss_feeder_only_kwh",
        "daily_energy_share_pct", "max_instantaneous_penetration_pct", "min_instantaneous_penetration_pct",
        "abs_min_lv_pu", "abs_max_lv_pu",
        "minutes_above_1p05_pu", "minutes_above_1p06_pu", "minutes_above_1p10_pu", "minutes_below_0p90_pu",
        "delta_feeder_loss_kwh_vs_base", "delta_feeder_loss_pct_vs_base",
        "delta_total_loss_kwh_vs_base", "delta_total_loss_pct_vs_base",
        "delta_grid_import_kwh_vs_base", "delta_load_demand_kwh_vs_base",
        "max_power_balance_residual_kw", "max_loads_outside_pq_count",
    ]
    all7_csv = out_dir / "qsts_24h_vmaxpu1p20_all7_comparison.csv"
    with all7_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields, lineterminator="\n")
        writer.writeheader()
        for r in all7_1p20:
            writer.writerow({k: r[k] for k in csv_fields})

    # Save paired side-by-side 1.05 vs 1.20 CSV for all 7 scenarios
    paired_csv = out_dir / "qsts_24h_all7_paired_1p05_vs_1p20.csv"
    with paired_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(paired_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired_rows)

    payload = {
        "provenance": {
            "source_ref_pinned": manifest.get("source_ref", args.source_ref),
            "origin": manifest.get("origin"),
            "manifest_sha256": _sha256(data_dir / "source_manifest.json"),
            "prior_3sc_vmaxpu1p20_json": str(PRIOR_3SC_JSON.relative_to(REPO_ROOT)),
            "prior_3sc_vmaxpu1p20_sha256": _sha256(PRIOR_3SC_JSON),
            "pr57_reference_csv": str(PR57_CSV_PATH.relative_to(REPO_ROOT)),
            "pr57_reference_csv_sha256": _sha256(PR57_CSV_PATH),
            "python_version": platform.python_version(),
            "opendssdirect_version": getattr(dss, "__version__", "unknown"),
            "dss_python_version": getattr(dss_py, "__version__", "unknown"),
            "hypotheses": {
                "vmaxpu_override": 1.20,
                "pv_peak_kw": 3.0,
                "transformer_5kva_when_enabled": "H2_YNyn0_zk4p2_r1p5_nominal_hyp (r_k=1.5%, x_k=4.0%, P0=0, %imag=0)",
                "substation_head_pu": 1.05,
                "coupling": "unidirectional_QSTS_no_dynamic_feedback",
                "new_scenarios_executed": [s[0] for s in PV_ONLY_SCENARIOS],
                "reused_scenarios_from_pr59": ["base_no_dg", "pv_bess_near_34_xfmr_5kva", "pv_bess_far_822_xfmr_5kva"],
                "new_solves_executed": 4 * 1440,
                "wall_new_4sc_s": wall_total_s,
            },
        },
        "new_pv_only_4sc_vmaxpu1p20": new_pv_only,
        "all7_paired_1p05_vs_1p20": paired_rows,
    }
    all7_json = out_dir / "qsts_24h_all7_vmaxpu1p20_vs_pr57.json"
    all7_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Completed 4 PV-only scenarios (5,760 solves) in {wall_total_s}s -> {all7_json}")


if __name__ == "__main__":
    main()
