"""Representative-instant sensitivity audit: Vmaxpu=1.05 vs Vmaxpu=1.20 in IEEE 906 QSTS (PV+BESS).

Evaluates 5 representative instants (low, medium, high demand; PV peak, BESS charge/discharge)
across `base_no_dg`, `pv_bess_near_34_xfmr_5kva`, and `pv_bess_far_822_xfmr_5kva` with the
5 kVA YNyn0 step-up transformer (H2: r_k=1.5%, x_k=4.0%, P0=0, %imag=0), Vsource=1.05 pu,
and unidirectional QSTS coupling.

Does NOT modify canonical Master.dss, Loads.txt, or PR #57/#58 outputs.
Uses the immutable tshort/OpenDSS commit SHA documented in PR #58.
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
    synthetic_bess_grid_power_kw,
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

REPRESENTATIVE_INSTANTS: tuple[tuple[int, str, str], ...] = (
    (0, "00:01", "demanda_minima_nocturna_sin_der"),
    (565, "09:26", "demanda_maxima_diaria_fv_bess_carga"),
    (720, "12:00", "mediodia_pico_fv_carga_max_bess"),
    (930, "15:30", "tarde_demanda_media_baja_fv_bess_reposo"),
    (1140, "19:00", "pico_vespertino_descarga_max_bess"),
)

SCENARIOS: tuple[tuple[str, str | None, bool, bool], ...] = (
    ("base_no_dg", None, False, False),
    ("pv_bess_near_34_xfmr_5kva", "34", True, True),
    ("pv_bess_far_822_xfmr_5kva", "822", True, True),
)

VMAXPU_CASES: tuple[tuple[str, float | None], ...] = (
    ("vmaxpu_1p05_canonical", None),
    ("vmaxpu_1p20_pure_pq", 1.20),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_single_instant(
    dss,
    study_master: Path,
    *,
    minute: int,
    scenario_name: str,
    bus_num: str | None,
    use_xfmr_5kva: bool,
    with_bess_profile: bool,
    vmaxpu_override: float | None,
    peak_pv_kw: float = 3.0,
) -> dict[str, Any]:
    dss.Basic.ClearAll()
    dss.Text.Command(f'compile "{study_master.resolve().as_posix()}"')
    if dss.Loads.Count() != EXPECTED_LOADS or dss.Lines.Count() != EXPECTED_LINES:
        raise AssertionError("Unexpected feeder topology")

    if vmaxpu_override is not None:
        dss.Text.Command(f"batchedit load..* vmaxpu={vmaxpu_override:.4f}")

    dss.Text.Command("set controlmode=off")
    dss.Text.Command("set mode=yearly number=1 stepsize=1m")

    hyp = TRANSFORMER_SENSITIVITY_CASES[1]  # H2_YNyn0_zk4p2_r1p5_nominal_hyp (P0=0, %imag=0)
    p_pv = illustrative_pv_kw(minute, peak_pv_kw) if bus_num is not None else 0.0
    p_bess = synthetic_bess_grid_power_kw(minute) if (bus_num is not None and with_bess_profile) else 0.0
    p_der_net = p_pv + p_bess

    if bus_num is not None:
        if use_xfmr_5kva:
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
                f"kV={hyp.v_inv_ll_kv:.10f} conn={hyp.conn_inv} kW={p_der_net:.9g} kvar=0 model=1"
            )
        else:
            dss.Text.Command(
                f"New Generator.DER_VSG phases=3 bus1={bus_num}.1.2.3 "
                f"kV=0.416 conn=wye kW={p_der_net:.9g} kvar=0 model=1"
            )

    dss.Solution.Hour(minute // 60)
    dss.Solution.Seconds((minute % 60) * 60)
    dss.Solution.Solve()
    if not dss.Solution.Converged():
        raise RuntimeError(f"Non-convergence in {scenario_name} minute={minute} vmaxpu={vmaxpu_override}")

    p_load_kw = 0.0
    q_load_kvar = 0.0
    n_over_vmax = 0
    n_under_vmin = 0
    v_eff_vmaxpu = 1.05 if vmaxpu_override is None else float(vmaxpu_override)
    v_eff_vminpu = 0.95

    for load_name in dss.Loads.AllNames():
        dss.Loads.Name(load_name)
        v_nom_v = dss.Loads.kV() * 1000.0
        dss.Circuit.SetActiveElement(f"Load.{load_name}")
        pwrs = dss.CktElement.Powers()
        p_load_kw += sum(pwrs[0::2])
        q_load_kvar += sum(pwrs[1::2])
        v_mag_v = float(dss.CktElement.VoltagesMagAng()[0])
        v_pu_load = v_mag_v / v_nom_v
        if v_pu_load > v_eff_vmaxpu:
            n_over_vmax += 1
        elif v_pu_load < v_eff_vminpu:
            n_under_vmin += 1

    total_p = dss.Circuit.TotalPower()
    p_source_kw = -float(total_p[0])
    q_source_kvar = -float(total_p[1])
    losses = dss.Circuit.Losses()
    p_loss_total_kw = float(losses[0]) / 1000.0
    q_loss_total_kvar = float(losses[1]) / 1000.0

    xfmr_loss_kw = 0.0
    xfmr_loss_kvar = 0.0
    if bus_num is not None and use_xfmr_5kva:
        dss.Circuit.SetActiveElement("Transformer.T_DER")
        xl = dss.CktElement.Losses()
        xfmr_loss_kw = float(xl[0]) / 1000.0
        xfmr_loss_kvar = float(xl[1]) / 1000.0

    lv_pu = []
    for bname in dss.Circuit.AllBusNames():
        if bname.lower() == "der_lv":
            continue
        dss.Circuit.SetActiveBus(bname)
        if 0 < dss.Bus.kVBase() < 1:
            lv_pu.extend(float(v) for v in dss.Bus.puVmagAngle()[0::2] if 0 < v < 2)

    v34 = _bus_three_phase_pu(dss, "34")
    v822 = _bus_three_phase_pu(dss, "822")
    imbalance_kw = p_source_kw + p_der_net - p_load_kw - p_loss_total_kw
    if abs(imbalance_kw) > max(0.10, 0.005 * max(p_load_kw, 1.0)):
        raise AssertionError(f"Power balance residual {imbalance_kw:+.6f} kW")

    return {
        "minute": minute,
        "scenario": scenario_name,
        "bus": bus_num or "none",
        "vmaxpu_effective": v_eff_vmaxpu,
        "p_pv_kw": round(p_pv, 6),
        "p_bess_kw": round(p_bess, 6),
        "p_der_net_kw": round(p_der_net, 6),
        "p_load_kw": round(p_load_kw, 6),
        "q_load_kvar": round(q_load_kvar, 6),
        "p_source_kw": round(p_source_kw, 6),
        "q_source_kvar": round(q_source_kvar, 6),
        "p_loss_total_kw": round(p_loss_total_kw, 6),
        "q_loss_total_kvar": round(q_loss_total_kvar, 6),
        "p_loss_xfmr_der_kw": round(xfmr_loss_kw, 6),
        "p_loss_feeder_only_kw": round(p_loss_total_kw - xfmr_loss_kw, 6),
        "power_balance_residual_kw": round(imbalance_kw, 6),
        "min_v_lv_pu": round(min(lv_pu), 7),
        "max_v_lv_pu": round(max(lv_pu), 7),
        "v_34_min_pu": round(min(v34), 7),
        "v_34_max_pu": round(max(v34), 7),
        "v_822_min_pu": round(min(v822), 7),
        "v_822_max_pu": round(max(v822), 7),
        "loads_over_vmaxpu_count": n_over_vmax,
        "loads_under_vminpu_count": n_under_vmin,
        "loads_outside_pq_pct": round(100.0 * (n_over_vmax + n_under_vmin) / EXPECTED_LOADS, 2),
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

    t0 = time.perf_counter()
    data_dir = args.data_dir.resolve()
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.download or not (data_dir / "source_manifest.json").is_file():
        fetch_dataset(data_dir, args.source_ref)
    verify_dataset(data_dir)
    manifest = json.loads((data_dir / "source_manifest.json").read_text(encoding="utf-8"))
    study_master = write_study_master(data_dir)

    rows: list[dict[str, Any]] = []
    indexed: dict[tuple[str, int, str], dict[str, Any]] = {}
    for vlabel, vval in VMAXPU_CASES:
        for minute, hhmm, regime in REPRESENTATIVE_INSTANTS:
            for sc_name, bus_num, use_xfmr, with_bess in SCENARIOS:
                rec = run_single_instant(
                    dss,
                    study_master,
                    minute=minute,
                    scenario_name=sc_name,
                    bus_num=bus_num,
                    use_xfmr_5kva=use_xfmr,
                    with_bess_profile=with_bess,
                    vmaxpu_override=vval,
                )
                rec["vmaxpu_case"] = vlabel
                rec["time_label"] = hhmm
                rec["regime"] = regime
                rows.append(rec)
                indexed[(vlabel, minute, sc_name)] = rec

    # Build paired comparisons: (a) 1.20 vs 1.05 per scenario/minute; (b) Bus 34 vs Bus 822 vs base
    comparisons: list[dict[str, Any]] = []
    location_summary: list[dict[str, Any]] = []

    for minute, hhmm, regime in REPRESENTATIVE_INSTANTS:
        for sc_name, _, _, _ in SCENARIOS:
            r05 = indexed[("vmaxpu_1p05_canonical", minute, sc_name)]
            r20 = indexed[("vmaxpu_1p20_pure_pq", minute, sc_name)]
            comparisons.append({
                "minute": minute,
                "time_label": hhmm,
                "scenario": sc_name,
                "dp_load_kw": round(r20["p_load_kw"] - r05["p_load_kw"], 6),
                "dp_load_pct": round(100.0 * (r20["p_load_kw"] - r05["p_load_kw"]) / r05["p_load_kw"], 4),
                "dq_load_kvar": round(r20["q_load_kvar"] - r05["q_load_kvar"], 6),
                "dp_source_kw": round(r20["p_source_kw"] - r05["p_source_kw"], 6),
                "dp_source_pct": round(100.0 * (r20["p_source_kw"] - r05["p_source_kw"]) / r05["p_source_kw"], 4),
                "dp_loss_feeder_kw": round(r20["p_loss_feeder_only_kw"] - r05["p_loss_feeder_only_kw"], 6),
                "dp_loss_feeder_pct": round(100.0 * (r20["p_loss_feeder_only_kw"] - r05["p_loss_feeder_only_kw"]) / r05["p_loss_feeder_only_kw"], 4),
                "dp_loss_total_kw": round(r20["p_loss_total_kw"] - r05["p_loss_total_kw"], 6),
                "dp_loss_total_pct": round(100.0 * (r20["p_loss_total_kw"] - r05["p_loss_total_kw"]) / r05["p_loss_total_kw"], 4),
                "dv_min_pu": round(r20["min_v_lv_pu"] - r05["min_v_lv_pu"], 7),
                "dv_max_pu": round(r20["max_v_lv_pu"] - r05["max_v_lv_pu"], 7),
                "outside_pq_1p05_pct": r05["loads_outside_pq_pct"],
                "outside_pq_1p20_pct": r20["loads_outside_pq_pct"],
            })

        for vlabel, _ in VMAXPU_CASES:
            b = indexed[(vlabel, minute, "base_no_dg")]
            n34 = indexed[(vlabel, minute, "pv_bess_near_34_xfmr_5kva")]
            f822 = indexed[(vlabel, minute, "pv_bess_far_822_xfmr_5kva")]
            location_summary.append({
                "minute": minute,
                "time_label": hhmm,
                "vmaxpu_case": vlabel,
                "p_der_net_kw": n34["p_der_net_kw"],
                "delta_load_34_vs_base_kw": round(n34["p_load_kw"] - b["p_load_kw"], 6),
                "delta_load_822_vs_base_kw": round(f822["p_load_kw"] - b["p_load_kw"], 6),
                "delta_feeder_loss_34_vs_base_pct": round(100.0 * (n34["p_loss_feeder_only_kw"] - b["p_loss_feeder_only_kw"]) / b["p_loss_feeder_only_kw"], 4),
                "delta_feeder_loss_822_vs_base_pct": round(100.0 * (f822["p_loss_feeder_only_kw"] - b["p_loss_feeder_only_kw"]) / b["p_loss_feeder_only_kw"], 4),
                "delta_total_loss_34_vs_base_pct": round(100.0 * (n34["p_loss_total_kw"] - b["p_loss_total_kw"]) / b["p_loss_total_kw"], 4),
                "delta_total_loss_822_vs_base_pct": round(100.0 * (f822["p_loss_total_kw"] - b["p_loss_total_kw"]) / b["p_loss_total_kw"], 4),
                "delta_source_34_vs_base_kw": round(n34["p_source_kw"] - b["p_source_kw"], 6),
                "delta_source_822_vs_base_kw": round(f822["p_source_kw"] - b["p_source_kw"], 6),
                "source_advantage_822_over_34_kw": round(n34["p_source_kw"] - f822["p_source_kw"], 6),
                "feeder_loss_saving_822_over_34_kw": round(n34["p_loss_feeder_only_kw"] - f822["p_loss_feeder_only_kw"], 6),
            })

    wall_s = round(time.perf_counter() - t0, 3)

    csv_path = out_dir / "vmaxpu_qsts_representative_instants.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    payload = {
        "provenance": {
            "source_ref_pinned": manifest.get("source_ref", args.source_ref),
            "origin": manifest.get("origin"),
            "manifest_sha256": _sha256(data_dir / "source_manifest.json"),
            "python_version": platform.python_version(),
            "opendssdirect_version": getattr(dss, "__version__", "unknown"),
            "dss_python_version": getattr(dss_py, "__version__", "unknown"),
            "hypotheses": {
                "transformer_5kva": "H2_YNyn0_zk4p2_r1p5_nominal_hyp (r_k=1.5%, x_k=4.0%, P0=0, %imag=0)",
                "substation_head_pu": 1.05,
                "coupling": "unidirectional_QSTS_no_dynamic_feedback",
                "solves_executed": len(rows),
                "wall_s": wall_s,
            },
        },
        "model_effect_1p20_vs_1p05": comparisons,
        "location_effect_34_vs_822": location_summary,
        "raw_snapshots": rows,
    }
    json_path = out_dir / "vmaxpu_qsts_representative_summary.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Completed {len(rows)} OpenDSS solves in {wall_s}s -> {json_path}")


if __name__ == "__main__":
    main()
