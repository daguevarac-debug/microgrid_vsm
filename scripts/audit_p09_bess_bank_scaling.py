"""Reproducible P-09 dimensional and scaling audit of the 48x2s2p BESS bank.

Audits the exact algebraic transformations across:
  - single pouch cell (1s1p, half of a Leaf 2p pair)
  - reference Leaf 2p cell-pair (1s2p, Braco 2020/2023 reference)
  - Leaf 2s2p module (2 series 2p pairs)
  - full BAT26-53 bank (48 series 2s2p modules = 96s x 1p of 2p units)
  - DC/DC coupling to the 340 V DC link in MicrogridWithBESSDCDC

Does not modify any protected physical equations or parameters (AGENTS.md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.dc_dc_adapter import convert_power  # noqa: E402
from config import (  # noqa: E402
    BESS_COUPLED_I_MAX_DEFAULT,
    BESS_COUPLED_P_MAX_W_DEFAULT,
    BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
    BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
    BESS_COUPLED_R0_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid_bess_dcdc import (  # noqa: E402
    BAT26_53_CELL_PAIRS_PER_MODULE,
    BAT26_53_LEAF_MODULES_SERIES,
    BAT26_53_N_PARALLEL_STRINGS,
    BAT26_53_N_SERIES_2P_UNITS,
    default_bat26_53_dcdc_parameters,
)
from validation.compare_bess_soh_scenarios import _build_bess_for_soh, _nominal_soh  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "outputs" / "audit_p05_p09" / "p09_bess_scaling_audit.json"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    soh_nom = float(_nominal_soh())
    bess = _build_bess_for_soh(soh_nom)
    dcdc = default_bat26_53_dcdc_parameters()

    # Base 2p unit parameters at nominal case (SoC=0.60, SoH=44.1/66.0).
    soc_ref = 0.60
    v_nom_2p = 3.75
    q_nom_2p = float(BESS_COUPLED_Q_NOM_REF_AH_DEFAULT)
    q_case_2p = float(BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT)
    r0_nom_2p = float(BESS_COUPLED_R0_DEFAULT)
    r0_case_2p = float(bess.r0(soh_nom))
    r1_2p = float(bess.r1(soc_ref))
    c1_2p = float(bess.c1(soc_ref))
    tau_rc_2p = r1_2p * c1_2p
    i_max_nom_2p = float(BESS_COUPLED_I_MAX_DEFAULT)
    i_max_avail_2p = i_max_nom_2p * soh_nom

    n_s_mod = BAT26_53_CELL_PAIRS_PER_MODULE       # 2
    n_mod_bank = BAT26_53_LEAF_MODULES_SERIES      # 48
    n_s_bank = BAT26_53_N_SERIES_2P_UNITS          # 96
    n_p_bank = BAT26_53_N_PARALLEL_STRINGS         # 1

    # Hierarchy scaling table (homogeneous ideal scaling).
    def scale_level(name: str, ns_from_2p: float, np_from_2p: float) -> dict[str, Any]:
        # ns_from_2p: series multiplier relative to 2p unit; np_from_2p: parallel multiplier relative to 2p unit
        v_nom = v_nom_2p * ns_from_2p
        v_min = dcdc.unit_voltage_min_v * ns_from_2p
        v_max = dcdc.unit_voltage_max_v * ns_from_2p
        q_nom = q_nom_2p * np_from_2p
        q_case = q_case_2p * np_from_2p
        i_nom = i_max_nom_2p * np_from_2p
        i_avail = i_max_avail_2p * np_from_2p
        r0_nom = r0_nom_2p * (ns_from_2p / np_from_2p)
        r0_case = r0_case_2p * (ns_from_2p / np_from_2p)
        r1 = r1_2p * (ns_from_2p / np_from_2p)
        c1 = c1_2p * (np_from_2p / ns_from_2p)
        tau = r1 * c1
        e_nom_kwh = (v_nom * q_nom) / 1000.0
        e_case_kwh = (v_nom * q_case) / 1000.0
        e_usable_80_kwh = e_case_kwh * (bess.soc_max - bess.soc_min)
        p_1c_nom_kw = (v_nom * i_nom) / 1000.0
        p_1c_avail_kw = (v_nom * i_avail) / 1000.0
        return {
            "level": name,
            "ns_rel_2p": ns_from_2p,
            "np_rel_2p": np_from_2p,
            "v_nom_v": round(v_nom, 4),
            "v_min_v": round(v_min, 4),
            "v_max_v": round(v_max, 4),
            "q_nom_ah": round(q_nom, 4),
            "q_case_ah": round(q_case, 4),
            "i_max_nom_a": round(i_nom, 4),
            "i_max_avail_a": round(i_avail, 4),
            "r0_nom_ohm": round(r0_nom, 6),
            "r0_case_ohm": round(r0_case, 6),
            "r1_at_soc06_ohm": round(r1, 6),
            "c1_at_soc06_f": round(c1, 4),
            "tau_rc_s": round(tau, 6),
            "e_nom_kwh": round(e_nom_kwh, 4),
            "e_case_kwh": round(e_case_kwh, 4),
            "e_usable_soc_window_kwh": round(e_usable_80_kwh, 4),
            "p_1c_nom_kw": round(p_1c_nom_kw, 4),
            "p_1c_avail_kw": round(p_1c_avail_kw, 4),
        }

    hierarchy = [
        scale_level("single_pouch_cell_1s1p", 1.0, 0.5),
        scale_level("leaf_cell_pair_2p_ref", 1.0, 1.0),
        scale_level("leaf_module_2s2p", float(n_s_mod), 1.0),
        scale_level("leaf_bank_48x2s2p_96s1p", float(n_s_bank), float(n_p_bank)),
    ]

    # Check OCV(SoC) envelope across SoC in [0.10, 0.90] using the loaded Excel table.
    soc_grid = [0.10, 0.20, 0.40, 0.50, 0.60, 0.80, 0.90]
    envelope = []
    for soc in soc_grid:
        ocv_u = float(bess.ocv(soc))
        v_bank_oc = n_s_bank * ocv_u
        res_dis = convert_power(
            parameters=dcdc,
            bus_power_request_w=3000.0,
            bus_voltage_v=SIM_VDC0_V_DEFAULT,
            ocv_v=ocv_u,
            vrc_v=0.0,
            r0_ohm=r0_case_2p,
            soc=soc,
            soc_min=bess.soc_min,
            soc_max=bess.soc_max,
            unit_discharge_available_a=i_max_avail_2p,
            unit_charge_available_a=i_max_avail_2p,
        )
        res_ch = convert_power(
            parameters=dcdc,
            bus_power_request_w=-3000.0,
            bus_voltage_v=SIM_VDC0_V_DEFAULT,
            ocv_v=ocv_u,
            vrc_v=0.0,
            r0_ohm=r0_case_2p,
            soc=soc,
            soc_min=bess.soc_min,
            soc_max=bess.soc_max,
            unit_discharge_available_a=i_max_avail_2p,
            unit_charge_available_a=i_max_avail_2p,
        )
        envelope.append({
            "soc": soc,
            "ocv_unit_v": round(ocv_u, 5),
            "v_bank_oc_v": round(v_bank_oc, 3),
            "v_bank_over_vdc_ref": round(v_bank_oc / SIM_VDC0_V_DEFAULT, 4),
            "mode_rel_to_340v": "buck_on_discharge" if v_bank_oc > SIM_VDC0_V_DEFAULT else "boost_on_discharge",
            "bus_discharge_limit_w": round(res_dis.bus_discharge_limit_w, 2),
            "bus_charge_limit_w": round(res_ch.bus_charge_limit_w, 2),
            "i_bank_at_3kw_dis_a": round(res_dis.unit_current_a * n_p_bank, 4),
            "i_bus_at_3kw_dis_a": round(res_dis.bus_current_a, 4),
            "p_loss_at_3kw_dis_w": round(res_dis.loss_power_w, 4),
            "power_balance_err_w": float(abs(res_dis.bank_power_w - n_s_bank * n_p_bank * res_dis.unit_voltage_v * res_dis.unit_current_a)),
        })

    # Dimensional invariant checks.
    tau_values = [h["tau_rc_s"] for h in hierarchy]
    max_tau_err = float(max(tau_values) - min(tau_values))
    max_p_err = float(max(e["power_balance_err_w"] for e in envelope))
    v_bank_min_oc = min(e["v_bank_oc_v"] for e in envelope)
    v_bank_max_oc = max(e["v_bank_oc_v"] for e in envelope)
    spans_vdc_ref = bool(v_bank_min_oc < SIM_VDC0_V_DEFAULT < v_bank_max_oc)

    # Compare MicrogridWithBESSPI (unscaled 2p direct) vs MicrogridWithBESSDCDC (48x2s2p).
    v_unit_soc06 = float(bess.ocv(0.60))
    scale_ratio_legacy_2p = float(SIM_VDC0_V_DEFAULT / v_unit_soc06)
    scale_ratio_dcdc_48x2s2p = float(SIM_VDC0_V_DEFAULT / (n_s_bank * v_unit_soc06))

    # Heterogeneity sensitivity (analytical worst-case weakest-link derating for series string).
    # If 96 series units have mean SoH = 0.6682 but weakest unit has SoH_min_cell in {0.60, 0.55, 0.50}:
    heterogeneity_bounds = []
    for soh_weak in (0.668182, 0.60, 0.55, 0.50):
        q_weak_ah = q_nom_2p * soh_weak
        e_eff_kwh = (n_s_bank * v_nom_2p * q_weak_ah) / 1000.0
        loss_pct = (1.0 - soh_weak / soh_nom) * 100.0
        heterogeneity_bounds.append({
            "weakest_unit_soh": round(soh_weak, 6),
            "string_usable_capacity_ah": round(q_weak_ah, 3),
            "string_nominal_energy_kwh": round(e_eff_kwh, 3),
            "usable_capacity_derating_vs_homogeneous_pct": round(loss_pct, 2),
        })

    report = {
        "soh_nominal_case": soh_nom,
        "vdc_ref_v": float(SIM_VDC0_V_DEFAULT),
        "p_bus_max_configured_w": float(BESS_COUPLED_P_MAX_W_DEFAULT),
        "n_modules_series": n_mod_bank,
        "n_series_2p_units": n_s_bank,
        "n_parallel_strings": n_p_bank,
        "hierarchy_scaling": hierarchy,
        "soc_envelope_48x2s2p": envelope,
        "dimensional_invariants": {
            "tau_rc_invariant_across_all_levels": bool(max_tau_err < 1e-6),
            "max_tau_rc_discrepancy_s": max_tau_err,
            "max_power_balance_error_w": max_p_err,
            "v_bank_oc_min_v": v_bank_min_oc,
            "v_bank_oc_max_v": v_bank_max_oc,
            "v_bank_spans_vdc_ref_340v": spans_vdc_ref,
            "legacy_bess_pi_vdc_over_vunit_ratio": round(scale_ratio_legacy_2p, 3),
            "dcdc_48x2s2p_vdc_over_vbank_ratio": round(scale_ratio_dcdc_48x2s2p, 4),
            "bus_power_limit_binds_before_bank_1c_limit_at_soc06": bool(
                BESS_COUPLED_P_MAX_W_DEFAULT < hierarchy[-1]["p_1c_avail_kw"] * 1000.0 * dcdc.eta_discharge
            ),
            "bank_1c_avail_bus_power_at_soc06_w": round(
                n_s_bank * v_unit_soc06 * i_max_avail_2p * dcdc.eta_discharge, 2
            ),
        },
        "series_string_weakest_link_heterogeneity_illustration": heterogeneity_bounds,
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dimensional_invariants": report["dimensional_invariants"],
        "bank_summary": hierarchy[-1],
        "heterogeneity_illustration": heterogeneity_bounds,
    }, indent=2))


if __name__ == "__main__":
    main()
