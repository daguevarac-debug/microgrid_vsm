"""Automated tests for modular scenario configuration selector (Step 1)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.integrate import solve_ivp

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import Microgrid
from microgrid_bess_pi import MicrogridWithBESSPI
from scenario_config import (
    build_microgrid_from_config,
    default_scenario_config,
    load_scenario_config,
    validate_scenario_config,
)


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "default_gfm_bess_pi_scenario.json"


def _build_direct_reference():
    probe = Microgrid()
    p_ref = min(probe.P_ref_nominal, probe.p_available_ref)
    ctrl = GFMController(inertia_m=80.0, damping_d=1500.0, p_ref=p_ref)
    pi = DCLinkBESSPIController(vdc_ref_v=340.0, kp_w_per_v=20.0, ki_w_per_v_s=200.0)
    model = MicrogridWithBESSPI(controller=ctrl, dc_link_bess_pi=pi, bess_enabled=True)
    y0 = model.initial_state_with_bess(vdc0=340.0)
    return model, y0


def test_default_fixture_matches_direct_construction_exactly():
    cfg = load_scenario_config(FIXTURE_PATH)
    model_cfg, y0_cfg, sim_cfg = build_microgrid_from_config(cfg)
    model_ref, y0_ref = _build_direct_reference()

    assert len(y0_cfg) == 16
    assert model_cfg.controller_state_name == "omega"
    np.testing.assert_allclose(y0_cfg, y0_ref, rtol=0.0, atol=0.0)

    rhs_cfg = np.asarray(model_cfg.system_dynamics(0.0, y0_cfg), dtype=float)
    rhs_ref = np.asarray(model_ref.system_dynamics(0.0, y0_ref), dtype=float)
    np.testing.assert_allclose(rhs_cfg, rhs_ref, rtol=0.0, atol=0.0)

    sol_cfg = solve_ivp(
        model_cfg.system_dynamics,
        (0.0, 0.1),
        y0_cfg,
        max_step=sim_cfg["max_step_s"],
        rtol=sim_cfg["rtol"],
        atol=sim_cfg["atol"],
    )
    sol_ref = solve_ivp(
        model_ref.system_dynamics,
        (0.0, 0.1),
        y0_ref,
        max_step=5e-5,
        rtol=1e-6,
        atol=1e-8,
    )
    assert sol_cfg.success and sol_ref.success
    assert sol_cfg.y.shape == sol_ref.y.shape
    np.testing.assert_allclose(sol_cfg.y, sol_ref.y, rtol=0.0, atol=0.0)


def test_custom_pv_env_load_vsg_and_bess_lookup_table_change_behavior():
    cfg = default_scenario_config()
    cfg["name"] = "custom_experimental_bess_test"
    cfg["pv"]["strings_in_parallel"] = 2
    cfg["environment"]["irradiance"] = {
        "type": "piecewise_linear",
        "points": [[0.0, 950.0], [0.5, 650.0]],
    }
    cfg["environment"]["temperature_c"] = {"type": "constant", "value": 30.0}
    cfg["load"]["p_nominal_w"] = 4000.0
    cfg["vsg"]["M"] = 40.0
    cfg["vsg"]["D"] = 800.0
    cfg["bess"].update(
        {
            "characterization_source": "lookup_table",
            "q_nom_ref_ah": 60.0,
            "q_init_case_ah": 48.0,
            "r0_nominal_ohm": 0.0025,
            "r0_soh_sensitivity": 1.5,
            "k_deg": 2.0e-6,
            "soc_initial": 0.75,
            "soc_min": 0.15,
            "soc_max": 0.85,
            "lookup_table": {
                "soc_data": [0.0, 0.5, 1.0],
                "ocv_data": [3.2, 3.6, 4.1],
                "r1_data": [0.015, 0.012, 0.014],
                "c1_data": [2000.0, 2500.0, 2200.0],
                "source_reference": "Lab HPPC synthetic test fixture",
            },
        }
    )

    model, y0, _ = build_microgrid_from_config(cfg)
    model_def, y0_def, _ = build_microgrid_from_config(default_scenario_config())

    assert len(y0) == 16
    assert model.bess.q_nom_ref_ah == pytest.approx(60.0)
    assert model.bess.soh_init_case == pytest.approx(0.80)
    assert model.bess.soc_min == pytest.approx(0.15)
    assert model.bess.soc_max == pytest.approx(0.85)
    assert model.controller.frequency_dynamics.inertia_m == pytest.approx(40.0)
    assert model.controller.frequency_dynamics.damping_d == pytest.approx(800.0)
    assert model.P_ref_nominal > model_def.P_ref_nominal
    assert model.bess.terminal_voltage(0.75, 0.0, 0.0, 0.80) != pytest.approx(
        model_def.bess.terminal_voltage(0.75, 0.0, 0.0, 0.80)
    )
    assert not np.allclose(
        model.system_dynamics(0.1, y0),
        model_def.system_dynamics(0.1, y0_def),
    )


def test_bess_modes_preserve_protected_state_counts():
    for mode, expected_len in (("none", 12), ("coupled_proportional", 15), ("with_pi", 16)):
        cfg = default_scenario_config()
        cfg["bess"]["mode"] = mode
        model, y0, _ = build_microgrid_from_config(cfg)
        assert len(y0) == expected_len
        assert model.controller_state_name == "omega"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda c: c.update({"schema_version": 2}),
        lambda c: c.update({"unknown_key": 1}),
        lambda c: c["bess"].update({"soc_initial": 0.95}),
        lambda c: c["bess"].update({"soc_min": 0.8, "soc_max": 0.2}),
        lambda c: c["bess"].update({"mode": "invalid_mode"}),
        lambda c: c["vsg"].update({"M": True}),
        lambda c: c["environment"]["irradiance"].update({"value": -10.0}),
        lambda c: c["simulation"].update({"t_end_s": 0.0}),
        lambda c: c["bess"].update(
            {
                "characterization_source": "lookup_table",
                "lookup_table": {
                    "soc_data": [0.5, 0.2, 1.0],
                    "ocv_data": [3.2, 3.5, 4.0],
                    "r1_data": [0.01, 0.01, 0.01],
                    "c1_data": [1000.0, 1000.0, 1000.0],
                },
            }
        ),
        lambda c: c["bess"].update({"mode": "coupled_proportional", "enabled": False}),
    ],
)
def test_invalid_configs_are_rejected(mutator):
    cfg = default_scenario_config()
    mutator(cfg)
    with pytest.raises(ValueError):
        validate_scenario_config(cfg)


def test_duplicate_json_keys_rejected(tmp_path: Path):
    bad_json = tmp_path / "dup.json"
    bad_json.write_text('{"schema_version": 1, "name": "a", "name": "b"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_scenario_config(bad_json)


def test_default_selector_and_integrated_gfm_scenarios_remain_distinct():
    default_cfg = load_scenario_config(FIXTURE_PATH)
    integrated_path = FIXTURE_PATH.parent / "integrated_gfm_bess_pi_step20_scenario.json"
    integrated_cfg = load_scenario_config(integrated_path)

    # Preserve historical selector defaults (Kp=20, Ki=200, t_end=2.0 s)
    assert default_cfg["bess"]["pi"]["kp_w_per_v"] == pytest.approx(20.0)
    assert default_cfg["bess"]["pi"]["ki_w_per_v_s"] == pytest.approx(200.0)
    assert default_cfg["simulation"]["t_end_s"] == pytest.approx(2.0)

    # Integrated GFM campaign uses Task 5.3 gains (Kp=170, Ki=10, t_end=6.5 s)
    assert integrated_cfg["bess"]["pi"]["kp_w_per_v"] == pytest.approx(170.0)
    assert integrated_cfg["bess"]["pi"]["ki_w_per_v_s"] == pytest.approx(10.0)
    assert integrated_cfg["simulation"]["t_end_s"] == pytest.approx(6.5)

    # Verify bit-for-bit equivalence of integrated fixture against Task 5.3 build_model
    from validation.validate_dc_link_pi_scenarios import BASE_SCENARIO, T_END_S, build_model

    model_cfg, y0_cfg, sim_cfg = build_microgrid_from_config(integrated_cfg)
    model_task53 = build_model(BASE_SCENARIO)
    y0_task53 = model_task53.initial_state_with_bess(vdc0=340.0)

    assert sim_cfg["t_end_s"] == pytest.approx(T_END_S)
    np.testing.assert_allclose(y0_cfg, y0_task53, rtol=0.0, atol=0.0)
    for t_eval in (0.0, 0.79, 0.81):
        rhs_cfg = np.asarray(model_cfg.system_dynamics(t_eval, y0_cfg), dtype=float)
        rhs_task53 = np.asarray(model_task53.system_dynamics(t_eval, y0_task53), dtype=float)
        np.testing.assert_allclose(rhs_cfg, rhs_task53, rtol=0.0, atol=0.0)

