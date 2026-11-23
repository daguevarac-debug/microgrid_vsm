"""Isolated numerical Proof-of-Concept (PoC) for P-07 DC-bus OVP sizing.

Evaluates DC-link energy balance, hysteresis vs. duty-cycle regulated chopper,
BESS-available non-interference, emergency trip behavior (inverter-only vs. PV
isolation), and parametric R_dump / thermal sensitivity without modifying `src/`.

Outputs are written strictly to `outputs/research_p07_ovp_poc/`.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (  # noqa: E402
    BESS_COUPLED_I_MAX_DEFAULT,
    BESS_COUPLED_P_MAX_W_DEFAULT,
    BESS_COUPLED_SOC_MAX_DEFAULT,
    DCLINK_CAP_F_DEFAULT,
    MICROGRID_ETA_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
    MICROGRID_PV_ARRAY_PARALLEL_DEFAULT,
    MICROGRID_PV_ARRAY_SERIES_DEFAULT,
    MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
    MICROGRID_PV_DIODE_IDEALITY_DEFAULT,
    MICROGRID_PV_IMP_STC_A_DEFAULT,
    MICROGRID_PV_ISC_STC_A_DEFAULT,
    MICROGRID_PV_NS_CELLS_DEFAULT,
    MICROGRID_PV_RS_OHM_DEFAULT,
    MICROGRID_PV_RSH_OHM_DEFAULT,
    MICROGRID_PV_VMP_STC_V_DEFAULT,
    MICROGRID_PV_VOC_STC_V_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    MICROGRID_UVLO_V_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from pv_model import PVArrayParams, PVArraySingleDiode, PVModuleParams  # noqa: E402

OUT_DIR = REPO_ROOT / "outputs" / "research_p07_ovp_poc"

# Design hypothesis thresholds (not certified commercial ratings)
VDC_NOM_V = float(SIM_VDC0_V_DEFAULT)  # 340.0 V
VDC_WARN_V = 357.0  # +5 %
VDC_CHOPPER_OFF_V = 363.8  # +7 % hysteresis reset
VDC_CHOPPER_ON_V = 374.0  # +10 % chopper activation
VDC_OVP_HARD_V = 391.0  # +15 % hard OVP trip


def build_repo_pv_array() -> PVArraySingleDiode:
    mod = PVModuleParams(
        voc_stc=float(MICROGRID_PV_VOC_STC_V_DEFAULT),
        isc_stc=float(MICROGRID_PV_ISC_STC_A_DEFAULT),
        vmp_stc=float(MICROGRID_PV_VMP_STC_V_DEFAULT),
        imp_stc=float(MICROGRID_PV_IMP_STC_A_DEFAULT),
        ns_cells=int(MICROGRID_PV_NS_CELLS_DEFAULT),
        alpha_isc=float(MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT),
        beta_voc=float(MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT),
        n=float(MICROGRID_PV_DIODE_IDEALITY_DEFAULT),
        rs=float(MICROGRID_PV_RS_OHM_DEFAULT),
        rsh=float(MICROGRID_PV_RSH_OHM_DEFAULT),
    )
    arr = PVArrayParams(
        module=mod,
        modules_in_series=int(MICROGRID_PV_ARRAY_SERIES_DEFAULT),
        strings_in_parallel=int(MICROGRID_PV_ARRAY_PARALLEL_DEFAULT),
    )
    return PVArraySingleDiode(arr)


def simulate_dc_bus_poc(
    label: str,
    *,
    pv: PVArraySingleDiode,
    mode: str,
    soc_initial: float = 0.90,
    bess_available: bool = False,
    g_w_m2: float = float(MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT),
    tc_c: float = float(MICROGRID_TEMPERATURE_C_DEFAULT),
    p_load_pre_w: float = float(MICROGRID_LOAD_P_NOM_W_DEFAULT),
    p_load_post_w: float = 0.2 * float(MICROGRID_LOAD_P_NOM_W_DEFAULT),
    t_step_s: float = 0.5,
    t_end_s: float = 1.2,
    dt_s: float = 5e-5,
    r_dump_ohm: float = 25.0,
    v_on_v: float = VDC_CHOPPER_ON_V,
    v_off_v: float = VDC_CHOPPER_OFF_V,
    v_hard_v: float = VDC_OVP_HARD_V,
    kp_bess_w_v: float = 250.0,
    ki_bess_w_vs: float = 1500.0,
) -> dict:
    """Integrate DC-link energy balance with RK4 and exact discrete switching."""
    cdc = float(DCLINK_CAP_F_DEFAULT)
    eta_inv = float(MICROGRID_ETA_DEFAULT)
    v_uvlo = float(MICROGRID_UVLO_V_DEFAULT)
    p_bess_max = min(
        float(BESS_COUPLED_P_MAX_W_DEFAULT),
        VDC_NOM_V * float(BESS_COUPLED_I_MAX_DEFAULT),
    )

    n_steps = int(round(t_end_s / dt_s))
    vdc = VDC_NOM_V
    xi_bess = 0.0
    chopper_on = False
    pv_isolated = False
    inv_tripped = False
    n_switchings = 0
    prev_active = False

    # Accumulators (trapezoidal / step-consistent energy balance)
    e_pv_j = 0.0
    e_bess_j = 0.0
    e_inv_j = 0.0
    e_dump_j = 0.0
    e_cap_0 = 0.5 * cdc * vdc * vdc

    vdc_max = vdc
    vdc_min = vdc
    vdc_post_max = 0.0
    t_above_357 = 0.0
    t_above_363_8 = 0.0
    t_above_374 = 0.0
    t_above_391 = 0.0
    p_dump_max = 0.0
    i_dump_max = 0.0
    i_dump_sq_int = 0.0
    duty_max = 0.0
    i_bess_min = 0.0

    def eval_duty_and_trip(v_val: float, ch_state: bool, pv_iso: bool, inv_trip: bool):
        if mode == "no_protection":
            return 0.0, False, pv_iso, inv_trip
        if mode == "hysteresis_chopper":
            new_ch = ch_state
            if not ch_state and v_val >= v_on_v:
                new_ch = True
            elif ch_state and v_val <= v_off_v:
                new_ch = False
            return (1.0 if new_ch else 0.0), new_ch, pv_iso, inv_trip
        if mode == "regulated_chopper":
            if v_val <= v_on_v:
                d = 0.0
            elif v_val >= v_hard_v:
                d = 1.0
            else:
                d = (v_val - v_on_v) / (v_hard_v - v_on_v)
            return float(d), (d > 0.0), pv_iso, inv_trip
        if mode == "emergency_inv_only":
            new_inv = inv_trip or (v_val >= v_hard_v)
            return 0.0, False, False, new_inv
        if mode == "emergency_pv_isolation":
            new_pv = pv_iso or (v_val >= v_hard_v)
            return 0.0, False, new_pv, False
        raise ValueError(f"Unknown mode: {mode}")

    def eval_currents(t_val: float, v_val: float, xi_val: float, duty: float, pv_iso: bool, inv_trip: bool):
        p_load = p_load_pre_w if t_val < t_step_s else p_load_post_w
        ipv = 0.0 if pv_iso else float(pv.ipv_from_vpv(max(v_val, 0.0), G=g_w_m2, T_c=tc_c))

        if inv_trip or v_val < v_uvlo:
            idc_inv = 0.0
        else:
            idc_inv = (p_load / eta_inv) / max(v_val, 50.0)

        if bess_available and soc_initial < float(BESS_COUPLED_SOC_MAX_DEFAULT):
            err_v = VDC_NOM_V - v_val
            p_raw = kp_bess_w_v * err_v + ki_bess_w_vs * xi_val
            p_bess = float(np.clip(p_raw, -p_bess_max, p_bess_max))
            i_bess = p_bess / max(v_val, 50.0)
            saturated_high = p_raw > p_bess_max and err_v > 0.0
            saturated_low = p_raw < -p_bess_max and err_v < 0.0
            dxi_dt = 0.0 if (saturated_high or saturated_low) else err_v
        else:
            i_bess = 0.0
            dxi_dt = 0.0

        i_dump = (duty * v_val / r_dump_ohm) if duty > 0.0 else 0.0
        dv_dt = (ipv + i_bess - idc_inv - i_dump) / cdc
        return dv_dt, dxi_dt, ipv, i_bess, idc_inv, i_dump

    for k in range(n_steps):
        t = k * dt_s
        duty, chopper_on, pv_isolated, inv_tripped = eval_duty_and_trip(
            vdc, chopper_on, pv_isolated, inv_tripped
        )
        is_active = duty > 0.0
        if is_active != prev_active:
            n_switchings += 1
            prev_active = is_active

        # RK4 integration with held discrete mode during dt_s
        k1_v, k1_xi, ipv1, ib1, iinv1, id1 = eval_currents(t, vdc, xi_bess, duty, pv_isolated, inv_tripped)
        k2_v, k2_xi, ipv2, ib2, iinv2, id2 = eval_currents(
            t + 0.5 * dt_s, vdc + 0.5 * dt_s * k1_v, xi_bess + 0.5 * dt_s * k1_xi, duty, pv_isolated, inv_tripped
        )
        k3_v, k3_xi, ipv3, ib3, iinv3, id3 = eval_currents(
            t + 0.5 * dt_s, vdc + 0.5 * dt_s * k2_v, xi_bess + 0.5 * dt_s * k2_xi, duty, pv_isolated, inv_tripped
        )
        k4_v, k4_xi, ipv4, ib4, iinv4, id4 = eval_currents(
            t + dt_s, vdc + dt_s * k3_v, xi_bess + dt_s * k3_xi, duty, pv_isolated, inv_tripped
        )

        # RK4-consistent power integration (weights 1, 2, 2, 1 / 6)
        v1 = vdc
        v2 = vdc + 0.5 * dt_s * k1_v
        v3 = vdc + 0.5 * dt_s * k2_v
        v4 = vdc + dt_s * k3_v

        p_pv_avg = (v1 * ipv1 + 2.0 * v2 * ipv2 + 2.0 * v3 * ipv3 + v4 * ipv4) / 6.0
        p_bess_avg = (v1 * ib1 + 2.0 * v2 * ib2 + 2.0 * v3 * ib3 + v4 * ib4) / 6.0
        p_inv_avg = (v1 * iinv1 + 2.0 * v2 * iinv2 + 2.0 * v3 * iinv3 + v4 * iinv4) / 6.0
        p_dump_avg = (v1 * id1 + 2.0 * v2 * id2 + 2.0 * v3 * id3 + v4 * id4) / 6.0
        i_dump_sq_avg = (id1 * id1 + 2.0 * id2 * id2 + 2.0 * id3 * id3 + id4 * id4) / 6.0

        e_pv_j += p_pv_avg * dt_s
        e_bess_j += p_bess_avg * dt_s
        e_inv_j += p_inv_avg * dt_s
        e_dump_j += p_dump_avg * dt_s
        i_dump_sq_int += i_dump_sq_avg * dt_s

        vdc = vdc + (dt_s / 6.0) * (k1_v + 2.0 * k2_v + 2.0 * k3_v + k4_v)
        xi_bess = xi_bess + (dt_s / 6.0) * (k1_xi + 2.0 * k2_xi + 2.0 * k3_xi + k4_xi)

        vdc_max = max(vdc_max, vdc)
        vdc_min = min(vdc_min, vdc)
        if t >= t_step_s:
            vdc_post_max = max(vdc_post_max, vdc)
        if vdc >= VDC_WARN_V:
            t_above_357 += dt_s
        if vdc >= VDC_CHOPPER_OFF_V:
            t_above_363_8 += dt_s
        if vdc >= VDC_CHOPPER_ON_V:
            t_above_374 += dt_s
        if vdc >= VDC_OVP_HARD_V:
            t_above_391 += dt_s

        p_dump_inst = v1 * id1
        p_dump_max = max(p_dump_max, p_dump_inst)
        i_dump_max = max(i_dump_max, id1)
        duty_max = max(duty_max, duty)
        i_bess_min = min(i_bess_min, ib1)

    e_cap_end = 0.5 * cdc * vdc * vdc
    delta_e_cap = e_cap_end - e_cap_0
    e_residual_j = (e_pv_j + e_bess_j - e_inv_j - e_dump_j) - delta_e_cap
    e_total_scale = max(e_pv_j + abs(e_bess_j), 1.0)

    return {
        "label": label,
        "mode": mode,
        "bess_available": bess_available,
        "soc_initial": soc_initial,
        "g_w_m2": g_w_m2,
        "tc_c": tc_c,
        "r_dump_ohm": r_dump_ohm,
        "v_on_v": v_on_v,
        "v_off_v": v_off_v,
        "t_end_s": t_end_s,
        "vdc_max_v": round(vdc_max, 4),
        "vdc_post_max_v": round(vdc_post_max, 4),
        "vdc_min_v": round(vdc_min, 4),
        "vdc_final_v": round(vdc, 4),
        "t_above_357_s": round(t_above_357, 4),
        "t_above_363_8_s": round(t_above_363_8, 4),
        "t_above_374_s": round(t_above_374, 4),
        "t_above_391_s": round(t_above_391, 4),
        "p_dump_max_w": round(p_dump_max, 2),
        "i_dump_max_a": round(i_dump_max, 3),
        "i_dump_rms_a": round(float(np.sqrt(i_dump_sq_int / t_end_s)), 3),
        "duty_max": round(duty_max, 4),
        "e_dump_j": round(e_dump_j, 3),
        "n_switchings": int(n_switchings),
        "i_bess_min_a": round(i_bess_min, 4),
        "e_pv_j": round(e_pv_j, 3),
        "e_bess_j": round(e_bess_j, 3),
        "e_inv_j": round(e_inv_j, 3),
        "delta_e_cap_j": round(delta_e_cap, 3),
        "energy_balance_residual_j": round(e_residual_j, 6),
        "energy_balance_rel_err": float(abs(e_residual_j) / e_total_scale),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pv = build_repo_pv_array()

    # 1. Core comparison on -80% load rejection at SoC=0.90 (t=0..1.2s)
    core_cases = [
        simulate_dc_bus_poc("no_protection_socmax_m80pct", pv=pv, mode="no_protection"),
        simulate_dc_bus_poc("hysteresis_chopper_socmax_m80pct", pv=pv, mode="hysteresis_chopper"),
        simulate_dc_bus_poc(
            "hysteresis_tight_band_chattering_check",
            pv=pv,
            mode="hysteresis_chopper",
            v_on_v=374.0,
            v_off_v=373.5,
        ),
        simulate_dc_bus_poc("regulated_chopper_socmax_m80pct", pv=pv, mode="regulated_chopper"),
        simulate_dc_bus_poc(
            "regulated_chopper_bess_active_soc060",
            pv=pv,
            mode="regulated_chopper",
            soc_initial=0.60,
            bess_available=True,
        ),
        simulate_dc_bus_poc(
            "hysteresis_chopper_bess_active_soc060",
            pv=pv,
            mode="hysteresis_chopper",
            soc_initial=0.60,
            bess_available=True,
        ),
    ]

    # 2. Emergency Level 3 trip check (100% load rejection at G=1000, Tc=25)
    emergency_cases = [
        simulate_dc_bus_poc(
            "emergency_trip_inverter_only_g1000",
            pv=pv,
            mode="emergency_inv_only",
            g_w_m2=1000.0,
            p_load_post_w=0.0,
        ),
        simulate_dc_bus_poc(
            "emergency_trip_pv_isolation_g1000",
            pv=pv,
            mode="emergency_pv_isolation",
            g_w_m2=1000.0,
            p_load_post_w=0.0,
        ),
    ]

    # 3. Parametric sensitivity on R_dump and environmental extremes (G=1000, Tc=0/25/45, -100% load)
    sensitivity_cases = []
    for r_ohm in (15.0, 20.0, 25.0, 28.0, 35.0):
        sensitivity_cases.append(
            simulate_dc_bus_poc(
                f"sens_regulated_r{int(r_ohm)}_g1000_m100pct",
                pv=pv,
                mode="regulated_chopper",
                g_w_m2=1000.0,
                tc_c=25.0,
                p_load_post_w=0.0,
                r_dump_ohm=r_ohm,
            )
        )
    for tc_val in (0.0, 25.0, 45.0):
        sensitivity_cases.append(
            simulate_dc_bus_poc(
                f"sens_regulated_r25_g1000_tc{int(tc_val)}_m100pct",
                pv=pv,
                mode="regulated_chopper",
                g_w_m2=1000.0,
                tc_c=tc_val,
                p_load_post_w=0.0,
                r_dump_ohm=25.0,
            )
        )

    # 4. Prolonged surplus & thermal sensitivity (10s, 60s, 600s scaling from 10s steady-state)
    prolonged_10s = simulate_dc_bus_poc(
        "prolonged_10s_regulated_r25_g800_m80pct",
        pv=pv,
        mode="regulated_chopper",
        g_w_m2=800.0,
        tc_c=25.0,
        p_load_post_w=600.0,
        t_end_s=10.0,
    )
    # Steady-state dump power from last second
    p_ss_est_w = (prolonged_10s["e_dump_j"] - simulate_dc_bus_poc(
        "prolonged_9s_ref", pv=pv, mode="regulated_chopper", g_w_m2=800.0, tc_c=25.0, p_load_post_w=600.0, t_end_s=9.0
    )["e_dump_j"])
    thermal_table = []
    for dur_s in (0.7, 10.0, 60.0, 600.0):
        e_est_kj = (prolonged_10s["e_dump_j"] if dur_s == 10.0 else (
            core_cases[3]["e_dump_j"] if dur_s == 0.7 else prolonged_10s["e_dump_j"] + (dur_s - 10.0) * p_ss_est_w
        )) / 1000.0
        thermal_table.append({
            "duration_s": dur_s,
            "p_dump_ss_w": round(p_ss_est_w, 2),
            "e_dump_kj": round(e_est_kj, 3),
            "delta_T_C_at_50J_K": round((e_est_kj * 1000.0) / 50.0, 2),
            "delta_T_C_at_100J_K": round((e_est_kj * 1000.0) / 100.0, 2),
            "delta_T_C_at_250J_K": round((e_est_kj * 1000.0) / 250.0, 2),
            "delta_T_C_at_500J_K": round((e_est_kj * 1000.0) / 500.0, 2),
        })

    all_runs = core_cases + emergency_cases + sensitivity_cases + [prolonged_10s]
    payload = {
        "core_cases": core_cases,
        "emergency_cases": emergency_cases,
        "sensitivity_cases": sensitivity_cases,
        "prolonged_10s": prolonged_10s,
        "thermal_parametric_table": thermal_table,
    }
    (OUT_DIR / "poc_p07_results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    csv_path = OUT_DIR / "poc_p07_summary.csv"
    fieldnames = list(all_runs[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_runs)

    print("CORE CASES:")
    for r in core_cases:
        print(
            f"  {r['label']}: Vmax={r['vdc_post_max_v']} V, Vfin={r['vdc_final_v']} V, "
            f"Edump={r['e_dump_j']} J, Pmax={r['p_dump_max_w']} W, sw={r['n_switchings']}, "
            f"rel_err={r['energy_balance_rel_err']:.2e}"
        )
    print("EMERGENCY CASES:")
    for r in emergency_cases:
        print(f"  {r['label']}: Vmax={r['vdc_post_max_v']} V, Vfin={r['vdc_final_v']} V")
    print("SENSITIVITY CASES:")
    for r in sensitivity_cases:
        print(
            f"  {r['label']}: Vmax={r['vdc_post_max_v']} V, Vfin={r['vdc_final_v']} V, "
            f"Imax={r['i_dump_max_a']} A, Dmax={r['duty_max']}"
        )
    print("THERMAL TABLE:")
    for row in thermal_table:
        print(f"  {row}")


if __name__ == "__main__":
    main()
