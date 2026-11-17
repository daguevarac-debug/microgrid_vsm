"""Phase 3 & Phase 4: Parameterized 190.53V/416V 50Hz Transformer Interface & OpenDSS QSTS Scenarios.

Implements a reproducible, non-destructive analysis of:
1. Phase 3: Electrical step-up interface between the 110 V LN (190.5256 V LL),
   50 Hz inverter side and the 416 V LL, 50 Hz IEEE European LV 906-bus feeder
   under explicit design hypotheses (S_ref = 5 kVA, a = 2.183434) and sensitivity
   ranges for winding connection (YNyn0, Dyn, Ynd) and short-circuit impedance
   (ideal lossless vs z_k = 3%, 4%, 6% and r_k = 1%, 1.5%, 2%).
2. Phase 4: Reproducible power-exchange interface and 24-hour QSTS network scenarios
   at Bus 34 (near) and Bus 822 (far):
   - Case 0: Baseline without DG (`no_dg`);
   - Case 1: 3 kW synthetic PV direct PQ injection (`pv_3kw_direct`);
   - Case 2: 3 kW synthetic PV coupled through the 5 kVA step-up transformer
     hypothesis (`pv_3kw_xfmr_5kva`);
   - Case 3: 3 kW synthetic PV + energy-consistent zero-net-SoC BESS daily shaving
     profile (`pv_bess_hypothesis_direct` and `pv_bess_hypothesis_xfmr_5kva`),
     explicitly labeled as a parameterized bank/dispatch hypothesis because the
     single Leaf 2p cell pair (44.1 Ah at ~3.75 V, ~0.165 kWh) cannot supply kW-scale
     feeder energy without an N_s x N_p pack and DC/DC stage (blocked by BAT26-48).

Strict separation of timescales is enforced: 6.5 s local ODE transients are never
extrapolated to 24 h; the steady-state PCC power mapping is evaluated only at
minute snapshots, while the 24 h QSTS uses 1,440 one-minute steps.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[1]
if str(THIS_FILE.parent) not in sys.path:
    sys.path.insert(0, str(THIS_FILE.parent))

from ieee_europe_lv_906_daily_pv import illustrative_pv_kw
from ieee_europe_lv_906_study import (
    EXPECTED_LINES,
    EXPECTED_LOADS,
    _write_csv,
    verify_dataset,
    write_study_master,
)


V_INV_LN_RMS_V = 110.0
V_INV_LL_RMS_V = 110.0 * math.sqrt(3.0)  # 190.5255888325765 V
V_GRID_LL_RMS_V = 416.0
V_GRID_LN_RMS_V = 416.0 / math.sqrt(3.0)  # 240.1777119828843 V
TURNS_RATIO_STEP_UP = V_GRID_LL_RMS_V / V_INV_LL_RMS_V  # 2.1834337877250865
S_REF_KVA = 5.0
F_NOM_HZ = 50.0


@dataclass(frozen=True)
class TransformerHypothesis:
    """Explicit sensitivity hypothesis for the 190.53 V / 416 V, 50 Hz interface."""

    name: str
    s_nom_kva: float
    v_inv_ll_kv: float
    v_grid_ll_kv: float
    conn_inv: str
    conn_grid: str
    xhl_pct: float
    r_total_pct: float
    hypothesis_note: str

    @property
    def turns_ratio(self) -> float:
        return self.v_grid_ll_kv / self.v_inv_ll_kv

    @property
    def i_nom_inv_a(self) -> float:
        return (self.s_nom_kva * 1000.0) / (math.sqrt(3.0) * self.v_inv_ll_kv * 1000.0)

    @property
    def i_nom_grid_a(self) -> float:
        return (self.s_nom_kva * 1000.0) / (math.sqrt(3.0) * self.v_grid_ll_kv * 1000.0)

    @property
    def z_base_inv_ohm(self) -> float:
        return (self.v_inv_ll_kv * 1000.0) ** 2 / (self.s_nom_kva * 1000.0)

    @property
    def z_base_grid_ohm(self) -> float:
        return (self.v_grid_ll_kv * 1000.0) ** 2 / (self.s_nom_kva * 1000.0)

    @property
    def r_eq_inv_ohm(self) -> float:
        return (self.r_total_pct / 100.0) * self.z_base_inv_ohm

    @property
    def x_eq_inv_ohm(self) -> float:
        return (self.xhl_pct / 100.0) * self.z_base_inv_ohm

    @property
    def r_eq_grid_ohm(self) -> float:
        return (self.r_total_pct / 100.0) * self.z_base_grid_ohm

    @property
    def x_eq_grid_ohm(self) -> float:
        return (self.xhl_pct / 100.0) * self.z_base_grid_ohm

    def regulation_approx_pct(self, s_load_kva: float, pf: float, lagging: bool = True) -> float:
        """ Kapp approximate voltage regulation [%] at load factor beta = S / S_nom."""
        beta = s_load_kva / self.s_nom_kva
        phi = math.acos(pf)
        sin_phi = math.sin(phi) if lagging else -math.sin(phi)
        r_pu = self.r_total_pct / 100.0
        x_pu = self.xhl_pct / 100.0
        term1 = beta * (r_pu * pf + x_pu * sin_phi)
        term2 = 0.5 * (beta**2) * ((x_pu * pf - r_pu * sin_phi) ** 2)
        return 100.0 * (term1 + term2)


TRANSFORMER_SENSITIVITY_CASES: tuple[TransformerHypothesis, ...] = (
    TransformerHypothesis(
        name="H1_YNyn0_zk3p2_r1p2_low_z",
        s_nom_kva=S_REF_KVA,
        v_inv_ll_kv=V_INV_LL_RMS_V / 1000.0,
        v_grid_ll_kv=0.416,
        conn_inv="wye",
        conn_grid="wye",
        xhl_pct=3.0,
        r_total_pct=1.2,
        hypothesis_note="Sensitivity lower-bound impedance (r_k=1.2%, x_k=3.0%, z_k=3.23%), grounded wye-wye",
    ),
    TransformerHypothesis(
        name="H2_YNyn0_zk4p2_r1p5_nominal_hyp",
        s_nom_kva=S_REF_KVA,
        v_inv_ll_kv=V_INV_LL_RMS_V / 1000.0,
        v_grid_ll_kv=0.416,
        conn_inv="wye",
        conn_grid="wye",
        xhl_pct=4.0,
        r_total_pct=1.5,
        hypothesis_note="Reference sensitivity point (r_k=1.5%, x_k=4.0%, z_k=4.27%), grounded wye-wye",
    ),
    TransformerHypothesis(
        name="H3_YNyn0_zk6p3_r2p0_high_z",
        s_nom_kva=S_REF_KVA,
        v_inv_ll_kv=V_INV_LL_RMS_V / 1000.0,
        v_grid_ll_kv=0.416,
        conn_inv="wye",
        conn_grid="wye",
        xhl_pct=6.0,
        r_total_pct=2.0,
        hypothesis_note="Sensitivity upper-bound impedance (r_k=2.0%, x_k=6.0%, z_k=6.32%), grounded wye-wye",
    ),
    TransformerHypothesis(
        name="H4_Dyn_zk4p2_r1p5_unbalance_trap",
        s_nom_kva=S_REF_KVA,
        v_inv_ll_kv=V_INV_LL_RMS_V / 1000.0,
        v_grid_ll_kv=0.416,
        conn_inv="delta",
        conn_grid="wye",
        xhl_pct=4.0,
        r_total_pct=1.5,
        hypothesis_note="Delta (inverter) / grounded-wye (grid): traps zero-sequence circulating current from grid unbalance",
    ),
    TransformerHypothesis(
        name="H5_Ynd_zk4p2_r1p5_zero_seq_isolated",
        s_nom_kva=S_REF_KVA,
        v_inv_ll_kv=V_INV_LL_RMS_V / 1000.0,
        v_grid_ll_kv=0.416,
        conn_inv="wye",
        conn_grid="delta",
        xhl_pct=4.0,
        r_total_pct=1.5,
        hypothesis_note="Grounded-wye (inverter) / ungrounded-delta (grid): blocks zero-sequence current at 416 V PCC",
    ),
)


def synthetic_bess_grid_power_kw(
    minute: int,
    *,
    p_charge_max_kw: float = 1.0,
    p_discharge_max_kw: float = 1.0,
    eta_roundtrip_single_way: float = 0.95,
) -> float:
    """Energy-consistent synthetic BESS daily power profile (positive = discharge to AC).

    - Charges during solar peak 09:00..15:00 (minutes 540..900) with a smooth half-sine
      curve of peak `p_charge_max_kw` (absorbing from PV).
    - Discharges during evening peak 17:00..21:00 (minutes 1020..1260) with a smooth
      half-sine curve scaled by `eta_roundtrip_single_way^2` so that the 24-hour
      internal battery charge returns to its exact initial SoC (Delta SoC_24h = 0).
    """
    if not (0 <= minute < 1440):
        raise ValueError("minute must be in [0, 1439]")
    if 540 < minute < 900:
        return -p_charge_max_kw * math.sin(math.pi * (minute - 540) / 360.0)
    if 1020 < minute < 1260:
        # Charge duration is 360 min; discharge duration is 240 min.
        # Scale peak by (360/240) * eta^2 so int(P_dis/eta) dt == int(eta * |P_ch|) dt.
        p_dis_peak = p_charge_max_kw * (360.0 / 240.0) * (eta_roundtrip_single_way**2)
        p_dis_peak = min(p_dis_peak, p_discharge_max_kw * 1.5)
        return p_dis_peak * math.sin(math.pi * (minute - 1020) / 240.0)
    return 0.0


def _bus_three_phase_pu(dss, bus: str) -> tuple[float, float, float]:
    if dss.Circuit.SetActiveBus(bus) < 0:
        raise ValueError(f"Unknown bus: {bus}")
    nodes = list(dss.Bus.Nodes())
    mags = list(dss.Bus.puVmagAngle()[0::2])
    out = []
    for ph in (1, 2, 3):
        if ph not in nodes:
            raise ValueError(f"Phase {ph} missing at bus {bus}")
        out.append(float(mags[nodes.index(ph)]))
    return (out[0], out[1], out[2])


def _voltage_unbalance_pct(v_abc_pu: tuple[float, float, float]) -> float:
    v_mean = sum(v_abc_pu) / 3.0
    if v_mean <= 0:
        return 0.0
    max_dev = max(abs(v - v_mean) for v in v_abc_pu)
    return 100.0 * max_dev / v_mean


def evaluate_transformer_sensitivity_snapshot(
    dss,
    study_master: Path,
    *,
    minute: int = 720,
    p_der_kw: float = 3.0,
    q_der_kvar: float = 0.0,
) -> list[dict[str, Any]]:
    """Run noon snapshot across all 5 transformer hypotheses at Bus 34 and Bus 822."""
    records: list[dict[str, Any]] = []
    for bus_label, bus_num in (("near_bus_34", "34"), ("far_bus_822", "822")):
        # Also include direct ideal connection at 0.416 kV for baseline comparison
        dss.Basic.ClearAll()
        dss.Text.Command(f'compile "{study_master.resolve().as_posix()}"')
        dss.Text.Command("set controlmode=off")
        dss.Text.Command("set mode=yearly number=1 stepsize=1m")
        dss.Text.Command(
            f"New Generator.DER_VSG phases=3 bus1={bus_num}.1.2.3 kV=0.416 "
            f"conn=wye kW={p_der_kw:.9g} kvar={q_der_kvar:.9g} model=1"
        )
        dss.Solution.Hour(minute // 60)
        dss.Solution.Seconds((minute % 60) * 60)
        dss.Solution.Solve()
        v34 = _bus_three_phase_pu(dss, "34")
        v822 = _bus_three_phase_pu(dss, "822")
        p_load_kw = sum(
            sum(dss.CktElement.Powers()[0::2])
            for name in dss.Loads.AllNames()
            if dss.Circuit.SetActiveElement(f"Load.{name}") >= 0
        )
        p_src_kw = -float(dss.Circuit.TotalPower()[0])
        p_loss_kw = float(dss.Circuit.Losses()[0]) / 1000.0
        records.append({
            "location": bus_label,
            "bus": bus_num,
            "hypothesis": "H0_direct_416v_ideal_pq",
            "conn_inv": "wye",
            "conn_grid": "wye",
            "xhl_pct": 0.0,
            "r_total_pct": 0.0,
            "p_der_cmd_kw": p_der_kw,
            "p_grid_injected_kw": p_der_kw,
            "xfmr_active_loss_w": 0.0,
            "xfmr_reactive_loss_var": 0.0,
            "xfmr_grid_phase_p_kw": [round(p_der_kw / 3.0, 5)] * 3,
            "xfmr_zero_seq_current_grid_a": 0.0,
            "xfmr_pos_seq_current_inv_a": round((p_der_kw * 1000.0) / (math.sqrt(3.0) * V_INV_LL_RMS_V), 4),
            "xfmr_pos_seq_current_grid_a": round((p_der_kw * 1000.0) / (math.sqrt(3.0) * V_GRID_LL_RMS_V), 4),
            "v_inv_abc_pu": [round(v, 6) for v in (v34 if bus_num == "34" else v822)],
            "v_34_abc_pu": [round(v, 6) for v in v34],
            "v_822_abc_pu": [round(v, 6) for v in v822],
            "v_unbalance_pcc_pct": round(_voltage_unbalance_pct(v34 if bus_num == "34" else v822), 5),
            "feeder_total_loss_kw": round(p_loss_kw, 6),
            "feeder_source_import_kw": round(p_src_kw, 6),
            "feeder_load_demand_kw": round(p_load_kw, 6),
        })

        for hyp in TRANSFORMER_SENSITIVITY_CASES:
            dss.Basic.ClearAll()
            dss.Text.Command(f'compile "{study_master.resolve().as_posix()}"')
            dss.Text.Command("set controlmode=off")
            dss.Text.Command("set mode=yearly number=1 stepsize=1m")
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
                f"kV={hyp.v_inv_ll_kv:.10f} conn={hyp.conn_inv} "
                f"kW={p_der_kw:.9g} kvar={q_der_kvar:.9g} model=1"
            )
            dss.Solution.Hour(minute // 60)
            dss.Solution.Seconds((minute % 60) * 60)
            dss.Solution.Solve()
            if not dss.Solution.Converged():
                raise RuntimeError(f"OpenDSS did not converge for {hyp.name} at bus {bus_num}")

            v_inv = _bus_three_phase_pu(dss, "der_lv")
            v34 = _bus_three_phase_pu(dss, "34")
            v822 = _bus_three_phase_pu(dss, "822")

            dss.Circuit.SetActiveElement("Transformer.T_DER")
            powers = dss.CktElement.Powers()
            n_cond = dss.CktElement.NumConductors()
            offset = 2 * n_cond
            grid_phase_p_kw = [-float(powers[offset + 2 * i]) for i in range(3)]
            xfmr_losses_w, xfmr_losses_var = dss.CktElement.Losses()
            seq_i = dss.CktElement.SeqCurrents()
            # seq_i is [I0_w1, I1_w1, I2_w1, I0_w2, I1_w2, I2_w2]

            p_load_kw = sum(
                sum(dss.CktElement.Powers()[0::2])
                for name in dss.Loads.AllNames()
                if dss.Circuit.SetActiveElement(f"Load.{name}") >= 0
            )
            p_src_kw = -float(dss.Circuit.TotalPower()[0])
            p_loss_kw = float(dss.Circuit.Losses()[0]) / 1000.0

            records.append({
                "location": bus_label,
                "bus": bus_num,
                "hypothesis": hyp.name,
                "conn_inv": hyp.conn_inv,
                "conn_grid": hyp.conn_grid,
                "xhl_pct": hyp.xhl_pct,
                "r_total_pct": hyp.r_total_pct,
                "p_der_cmd_kw": p_der_kw,
                "p_grid_injected_kw": round(sum(grid_phase_p_kw), 6),
                "xfmr_active_loss_w": round(float(xfmr_losses_w), 4),
                "xfmr_reactive_loss_var": round(float(xfmr_losses_var), 4),
                "xfmr_grid_phase_p_kw": [round(x, 5) for x in grid_phase_p_kw],
                "xfmr_zero_seq_current_grid_a": round(float(seq_i[3]), 5),
                "xfmr_pos_seq_current_inv_a": round(float(seq_i[1]), 4),
                "xfmr_pos_seq_current_grid_a": round(float(seq_i[4]), 4),
                "v_inv_abc_pu": [round(v, 6) for v in v_inv],
                "v_34_abc_pu": [round(v, 6) for v in v34],
                "v_822_abc_pu": [round(v, 6) for v in v822],
                "v_unbalance_pcc_pct": round(_voltage_unbalance_pct(v34 if bus_num == "34" else v822), 5),
                "feeder_total_loss_kw": round(p_loss_kw, 6),
                "feeder_source_import_kw": round(p_src_kw, 6),
                "feeder_load_demand_kw": round(p_load_kw, 6),
            })
    return records


def run_24h_qsts_scenario(
    dss,
    study_master: Path,
    *,
    scenario_name: str,
    bus_num: str | None,
    use_xfmr_5kva: bool,
    with_bess_profile: bool,
    peak_pv_kw: float = 3.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run a 1,440-minute 24-hour QSTS scenario and collect phase voltages, losses, and energy."""
    dss.Basic.ClearAll()
    dss.Text.Command(f'compile "{study_master.resolve().as_posix()}"')
    if dss.Loads.Count() != EXPECTED_LOADS or dss.Lines.Count() != EXPECTED_LINES:
        raise AssertionError("Unexpected feeder topology")
    dss.Text.Command("set controlmode=off")
    dss.Text.Command("set mode=yearly number=1 stepsize=1m")

    hyp = TRANSFORMER_SENSITIVITY_CASES[1]  # H2_YNyn0_zk4p2_r1p5_nominal_hyp
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
                f"kV={hyp.v_inv_ll_kv:.10f} conn={hyp.conn_inv} kW=0 kvar=0 model=1"
            )
        else:
            dss.Text.Command(
                f"New Generator.DER_VSG phases=3 bus1={bus_num}.1.2.3 "
                f"kV=0.416 conn=wye kW=0 kvar=0 model=1"
            )

    rows: list[dict[str, Any]] = []
    e_cum_bess_net_kwh = 0.0

    for minute in range(1440):
        p_pv = illustrative_pv_kw(minute, peak_pv_kw) if bus_num is not None else 0.0
        p_bess = synthetic_bess_grid_power_kw(minute) if (bus_num is not None and with_bess_profile) else 0.0
        p_der_net = p_pv + p_bess
        e_cum_bess_net_kwh += p_bess / 60.0

        if bus_num is not None:
            dss.Text.Command(f"edit Generator.DER_VSG kW={p_der_net:.9g}")

        dss.Solution.Hour(minute // 60)
        dss.Solution.Seconds((minute % 60) * 60)
        dss.Solution.Solve()
        if not dss.Solution.Converged():
            raise RuntimeError(f"Non-convergence in {scenario_name} at minute={minute}")

        p_load_kw = 0.0
        for load_name in dss.Loads.AllNames():
            dss.Circuit.SetActiveElement(f"Load.{load_name}")
            p_load_kw += sum(dss.CktElement.Powers()[0::2])

        p_source_kw = -float(dss.Circuit.TotalPower()[0])
        p_loss_kw = float(dss.Circuit.Losses()[0]) / 1000.0
        xfmr_loss_kw = 0.0
        if bus_num is not None and use_xfmr_5kva:
            dss.Circuit.SetActiveElement("Transformer.T_DER")
            xfmr_loss_kw = float(dss.CktElement.Losses()[0]) / 1000.0

        lv_pu = []
        for bname in dss.Circuit.AllBusNames():
            if bname.lower() == "der_lv":
                continue
            dss.Circuit.SetActiveBus(bname)
            if 0 < dss.Bus.kVBase() < 1:
                lv_pu.extend(float(v) for v in dss.Bus.puVmagAngle()[0::2] if 0 < v < 2)

        v34 = _bus_three_phase_pu(dss, "34")
        v822 = _bus_three_phase_pu(dss, "822")
        imbalance_kw = p_source_kw + p_der_net - p_load_kw - p_loss_kw
        if abs(imbalance_kw) > max(0.10, 0.005 * max(p_load_kw, 1.0)):
            raise AssertionError(f"Power balance residual {imbalance_kw:+.5f} kW at minute {minute}")

        rows.append({
            "minute": minute,
            "p_pv_kw": round(p_pv, 6),
            "p_bess_kw": round(p_bess, 6),
            "p_der_net_kw": round(p_der_net, 6),
            "p_load_kw": round(p_load_kw, 6),
            "p_source_kw": round(p_source_kw, 6),
            "p_loss_total_kw": round(p_loss_kw, 6),
            "p_loss_xfmr_der_kw": round(xfmr_loss_kw, 6),
            "p_loss_feeder_only_kw": round(p_loss_kw - xfmr_loss_kw, 6),
            "power_balance_residual_kw": round(imbalance_kw, 6),
            "der_penetration_pct": round(100.0 * p_der_net / p_load_kw, 4) if p_load_kw > 0 else 0.0,
            "min_v_lv_pu": round(min(lv_pu), 7),
            "max_v_lv_pu": round(max(lv_pu), 7),
            "v_34_1_pu": round(v34[0], 7),
            "v_34_2_pu": round(v34[1], 7),
            "v_34_3_pu": round(v34[2], 7),
            "v_822_1_pu": round(v822[0], 7),
            "v_822_2_pu": round(v822[1], 7),
            "v_822_3_pu": round(v822[2], 7),
        })

    # Aggregate 24-hour metrics
    e_pv_kwh = sum(r["p_pv_kw"] for r in rows) / 60.0
    e_bess_dis_kwh = sum(max(r["p_bess_kw"], 0.0) for r in rows) / 60.0
    e_bess_ch_kwh = sum(max(-r["p_bess_kw"], 0.0) for r in rows) / 60.0
    e_der_net_kwh = sum(r["p_der_net_kw"] for r in rows) / 60.0
    e_load_kwh = sum(r["p_load_kw"] for r in rows) / 60.0
    e_import_kwh = sum(r["p_source_kw"] for r in rows) / 60.0
    e_loss_total_kwh = sum(r["p_loss_total_kw"] for r in rows) / 60.0
    e_loss_xfmr_kwh = sum(r["p_loss_xfmr_der_kw"] for r in rows) / 60.0
    e_loss_feeder_kwh = sum(r["p_loss_feeder_only_kw"] for r in rows) / 60.0

    # EN 50160 / European LV limits: 230 V +10% / -10% (or 240.18 V base: 1.0 pu = 240.18 V)
    # Note: In the IEEE European LV feeder, Vsource is set at 1.05 pu on 11 kV (so no-load LV is 1.05 pu).
    minutes_above_1p05_pu = sum(1 for r in rows if r["max_v_lv_pu"] > 1.05)
    minutes_above_1p06_pu = sum(1 for r in rows if r["max_v_lv_pu"] > 1.06)
    minutes_above_1p10_pu = sum(1 for r in rows if r["max_v_lv_pu"] > 1.10)
    minutes_below_0p90_pu = sum(1 for r in rows if r["min_v_lv_pu"] < 0.90)

    agg = {
        "scenario": scenario_name,
        "bus": bus_num or "none",
        "use_xfmr_5kva": use_xfmr_5kva,
        "with_bess_profile": with_bess_profile,
        "samples": len(rows),
        "e_pv_synthetic_kwh": round(e_pv_kwh, 6),
        "e_bess_charge_kwh": round(e_bess_ch_kwh, 6),
        "e_bess_discharge_kwh": round(e_bess_dis_kwh, 6),
        "e_bess_net_ac_kwh": round(e_bess_dis_kwh - e_bess_ch_kwh, 6),
        "e_der_net_injected_kwh": round(e_der_net_kwh, 6),
        "e_load_demand_kwh": round(e_load_kwh, 6),
        "e_grid_import_kwh": round(e_import_kwh, 6),
        "e_loss_total_kwh": round(e_loss_total_kwh, 6),
        "e_loss_xfmr_der_kwh": round(e_loss_xfmr_kwh, 6),
        "e_loss_feeder_only_kwh": round(e_loss_feeder_kwh, 6),
        "daily_energy_share_pct": round(100.0 * e_der_net_kwh / e_load_kwh, 4),
        "max_instantaneous_penetration_pct": round(max(r["der_penetration_pct"] for r in rows), 4),
        "min_instantaneous_penetration_pct": round(min(r["der_penetration_pct"] for r in rows), 4),
        "abs_min_lv_pu": round(min(r["min_v_lv_pu"] for r in rows), 7),
        "abs_max_lv_pu": round(max(r["max_v_lv_pu"] for r in rows), 7),
        "v_34_phase1_min_max_pu": [
            round(min(r["v_34_1_pu"] for r in rows), 6),
            round(max(r["v_34_1_pu"] for r in rows), 6),
        ],
        "v_34_phase2_min_max_pu": [
            round(min(r["v_34_2_pu"] for r in rows), 6),
            round(max(r["v_34_2_pu"] for r in rows), 6),
        ],
        "v_34_phase3_min_max_pu": [
            round(min(r["v_34_3_pu"] for r in rows), 6),
            round(max(r["v_34_3_pu"] for r in rows), 6),
        ],
        "v_822_phase1_min_max_pu": [
            round(min(r["v_822_1_pu"] for r in rows), 6),
            round(max(r["v_822_1_pu"] for r in rows), 6),
        ],
        "v_822_phase2_min_max_pu": [
            round(min(r["v_822_2_pu"] for r in rows), 6),
            round(max(r["v_822_2_pu"] for r in rows), 6),
        ],
        "v_822_phase3_min_max_pu": [
            round(min(r["v_822_3_pu"] for r in rows), 6),
            round(max(r["v_822_3_pu"] for r in rows), 6),
        ],
        "minutes_above_1p05_pu": minutes_above_1p05_pu,
        "minutes_above_1p06_pu": minutes_above_1p06_pu,
        "minutes_above_1p10_pu": minutes_above_1p10_pu,
        "minutes_below_0p90_pu": minutes_below_0p90_pu,
        "noon_snapshot": rows[720],
        "evening_peak_snapshot_min1140": rows[1140],
    }
    return agg, rows


def main() -> int:
    data_dir = (REPO_ROOT / "data" / "ieee_europe_lv_906").resolve()
    out_dir = (REPO_ROOT / "outputs" / "analysis" / "ieee_europe_lv_906").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    verify_dataset(data_dir)
    study_master = write_study_master(data_dir)

    import opendssdirect as dss

    # Phase 3: Analytical & OpenDSS sensitivity of the 190.53 V / 416 V, 5 kVA interface
    analytical_hypotheses = []
    for hyp in TRANSFORMER_SENSITIVITY_CASES:
        d = asdict(hyp)
        d.update({
            "turns_ratio_step_up": round(hyp.turns_ratio, 6),
            "i_nom_inv_rms_a": round(hyp.i_nom_inv_a, 4),
            "i_nom_grid_rms_a": round(hyp.i_nom_grid_a, 4),
            "z_base_inv_ohm": round(hyp.z_base_inv_ohm, 5),
            "z_base_grid_ohm": round(hyp.z_base_grid_ohm, 5),
            "r_eq_inv_ohm": round(hyp.r_eq_inv_ohm, 5),
            "x_eq_inv_ohm": round(hyp.x_eq_inv_ohm, 5),
            "r_eq_grid_ohm": round(hyp.r_eq_grid_ohm, 5),
            "x_eq_grid_ohm": round(hyp.x_eq_grid_ohm, 5),
            "regulation_at_3kw_pf1p0_pct": round(hyp.regulation_approx_pct(3.0, 1.0), 4),
            "regulation_at_3p158kva_pf0p95_pct": round(hyp.regulation_approx_pct(3.0 / 0.95, 0.95), 4),
            "regulation_at_5kva_pf0p95_pct": round(hyp.regulation_approx_pct(5.0, 0.95), 4),
        })
        analytical_hypotheses.append(d)

    # Also evaluate sequential one-way coupling from 50 Hz VSG steady-state PCC power (p_ss_kw = 2.852527 kW)
    xfmr_sens_3kw = evaluate_transformer_sensitivity_snapshot(
        dss, study_master, minute=720, p_der_kw=3.0, q_der_kvar=0.0
    )
    xfmr_sens_vsg50_pss = evaluate_transformer_sensitivity_snapshot(
        dss, study_master, minute=720, p_der_kw=2.852527, q_der_kvar=0.0
    )
    _write_csv(out_dir / "transformer_interface_sensitivity_noon.csv", xfmr_sens_3kw)

    # Phase 4: 24-hour QSTS scenarios
    qsts_configs = [
        ("base_no_dg", None, False, False),
        ("pv_near_34_direct", "34", False, False),
        ("pv_far_822_direct", "822", False, False),
        ("pv_near_34_xfmr_5kva", "34", True, False),
        ("pv_far_822_xfmr_5kva", "822", True, False),
        ("pv_bess_near_34_xfmr_5kva", "34", True, True),
        ("pv_bess_far_822_xfmr_5kva", "822", True, True),
    ]
    qsts_summaries: list[dict[str, Any]] = []
    qsts_series: dict[str, list[dict[str, Any]]] = {}

    for name, bus_num, use_xfmr, with_bess in qsts_configs:
        print(f"Running 24h QSTS scenario: {name} ...", flush=True)
        agg, rows = run_24h_qsts_scenario(
            dss,
            study_master,
            scenario_name=name,
            bus_num=bus_num,
            use_xfmr_5kva=use_xfmr,
            with_bess_profile=with_bess,
        )
        qsts_summaries.append(agg)
        qsts_series[name] = rows

    # Compute relative deltas vs base_no_dg
    base_agg = qsts_summaries[0]
    for agg in qsts_summaries:
        agg["delta_feeder_loss_kwh_vs_base"] = round(
            agg["e_loss_feeder_only_kwh"] - base_agg["e_loss_feeder_only_kwh"], 6
        )
        agg["delta_feeder_loss_pct_vs_base"] = round(
            100.0 * (agg["e_loss_feeder_only_kwh"] / base_agg["e_loss_feeder_only_kwh"] - 1.0), 4
        )
        agg["delta_total_loss_kwh_vs_base"] = round(
            agg["e_loss_total_kwh"] - base_agg["e_loss_total_kwh"], 6
        )
        agg["delta_total_loss_pct_vs_base"] = round(
            100.0 * (agg["e_loss_total_kwh"] / base_agg["e_loss_total_kwh"] - 1.0), 4
        )
        agg["delta_grid_import_kwh_vs_base"] = round(
            agg["e_grid_import_kwh"] - base_agg["e_grid_import_kwh"], 6
        )

    # Save QSTS comparison CSV
    csv_qsts_fields = [
        k for k in qsts_summaries[0].keys()
        if not isinstance(qsts_summaries[0][k], (dict, list))
    ]
    with (out_dir / "qsts_24h_scenarios_comparison.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_qsts_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(qsts_summaries)

    # Save consolidated JSON report
    payload = {
        "study": "Phase 3 & Phase 4: Parameterized 190.53V/416V 50Hz Transformer Interface and 24h QSTS Scenarios",
        "timescale_separation_rule": (
            "6.5 s local ODE transients and 24-hour 1-minute QSTS network power flows "
            "are strictly separated. The 6.5 s trajectory is never extrapolated to 24 h. "
            "Steady-state PCC power from the 50 Hz VSG (p_ss_kw = 2.852527 kW) is evaluated "
            "as a one-way static snapshot, while 24 h QSTS uses explicit synthetic profiles."
        ),
        "phase3_transformer_design_hypotheses": {
            "status": "REVIEW_DESIGN_HYPOTHESIS_ONLY",
            "v_inv_ln_rms_v": V_INV_LN_RMS_V,
            "v_inv_ll_rms_v": round(V_INV_LL_RMS_V, 6),
            "v_grid_ln_rms_v": round(V_GRID_LN_RMS_V, 6),
            "v_grid_ll_rms_v": V_GRID_LL_RMS_V,
            "turns_ratio_step_up": round(TURNS_RATIO_STEP_UP, 6),
            "s_ref_kva": S_REF_KVA,
            "frequency_hz": F_NOM_HZ,
            "analytical_cases": analytical_hypotheses,
            "opendss_noon_3kw_sensitivity": xfmr_sens_3kw,
            "opendss_noon_vsg50_pss_2p8525kw_sensitivity": xfmr_sens_vsg50_pss,
            "unbalance_and_winding_findings": (
                "Because the IEEE European LV feeder is unbalanced, connecting a 3-phase "
                "transformer with delta on the inverter side and grounded-wye on the 416 V "
                "grid side (Dyn) creates a zero-sequence sink that draws ~0.542 A of "
                "zero-sequence current from the feeder and skews per-phase grid power "
                "(0.931 / 1.122 / 0.914 kW). Conversely, grounded-wye/grounded-wye (YNyn0) "
                "or grounded-wye/ungrounded-delta (Ynd) keeps phase power injection nearly "
                "balanced (~0.989 kW/phase after ~38.7 W copper loss at 3 kW)."
            ),
        },
        "phase4_qsts_24h_scenarios": {
            "solar_profile_provenance": "Synthetic 06:00-18:00 half-sine (peak 3.0 kW at noon), NOT measured irradiance",
            "bess_profile_provenance": (
                "Energy-consistent synthetic daily shaving hypothesis (charges 09:00-15:00 "
                "up to 1.0 kW, discharges 17:00-21:00 up to 1.354 kW with eta=0.95 per way, "
                "Delta SoC_24h = 0, throughput ~3.82 kWh). Explicitly labeled as a scaled "
                "bank hypothesis; the single 2p Leaf cell pair (~0.165 kWh) remains blocked "
                "by BAT26-48 for kWh-scale feeder dispatch until N_s x N_p is approved."
            ),
            "scenarios": qsts_summaries,
        },
    }
    json_path = out_dir / "phase3_phase4_interface_and_qsts_summary.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved Phase 3 & 4 summary to {json_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
