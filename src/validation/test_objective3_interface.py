"""Checks for the neutral boundary and the static adapter; no Colombian data."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_network import load_network, to_pandapower, validate_network
from objective3_main import main

FIXTURE = Path(__file__).parent / "fixtures" / "objective3_synthetic.json"


def test_static_adapter_and_traceability(tmp_path):
    import pandapower as pp

    case = load_network(FIXTURE)
    original = deepcopy(case)
    case["generators"] = [{"id": "test_gen", "bus": "test_pcc", "p_mw": 0.003, "q_mvar": 0.0}]
    net, indices = to_pandapower(case)
    pp.runpp(net)
    assert net.converged
    assert net.sn_mva == case["base_mva"] and net.f_hz == case["frequency_hz"]
    assert net.res_bus.at[indices[case["pcc_bus"]], "vm_pu"] < 1.0
    assert abs(net.res_ext_grid.p_mw.sum() + net.res_sgen.p_mw.sum()
               - net.res_load.p_mw.sum() - net.res_line.pl_mw.sum()) < 1e-8
    assert len(net.sgen) == 1
    assert load_network(FIXTURE) == original
    output = tmp_path / "run"
    assert main([str(FIXTURE), "--output-dir", str(output)]) == 0
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "DATA_CHECKED"
    assert report["synthetic"] and not report["academic_case_validated"]
    assert report["pcc_bus"] == "test_pcc" and len(report["network_sha256"]) == 64
    saved = (output / "summary.json").read_bytes()
    with pytest.raises(FileExistsError):
        main([str(FIXTURE), "--output-dir", str(output)])
    assert (output / "summary.json").read_bytes() == saved


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(schema_version=True),
    lambda c: c.update(synthetic="false"),
    lambda c: c.update(base_mva=0),
    lambda c: c.update(frequency_hz=float("nan")),
    lambda c: c.update(pcc_bus="missing"),
    lambda c: c.update(transformers=[]),
    lambda c: c["buses"].append(c["buses"][0].copy()),
    lambda c: c["buses"].append({"id": "island", "vn_kv": 12.66}),
    lambda c: c["buses"][1].update(vn_kv=0.4),
    lambda c: c["lines"][0].update(to_bus="test_slack"),
    lambda c: c["lines"][0].update(from_bus="missing"),
    lambda c: c["lines"][0].update(r_ohm_per_km=0, x_ohm_per_km=0),
    lambda c: c["lines"][0].update(max_i_ka=-1),
    lambda c: c["loads"][0].update(p_mw=-0.1),
    lambda c: c["loads"][0].update(q_mvar=float("inf")),
    lambda c: c["slack"].update(bus="missing"),
    lambda c: c["slack"].update(vm_pu=True),
])
def test_reject_invalid_or_unsupported_data(mutation):
    case = load_network(FIXTURE)
    mutation(case)
    with pytest.raises(ValueError):
        validate_network(case)


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version": 1, "schema_version": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_network(path)


def test_baseline_requires_explicit_reactive_assumption(tmp_path):
    with pytest.raises(SystemExit):
        main([str(FIXTURE), "--run-baseline", "--output-dir", str(tmp_path / "run")])
    assert not (tmp_path / "run").exists()


def test_one_way_average_units_and_review_preservation(monkeypatch):
    import numpy as np
    from objective3_main import run_baseline
    from validation import validate_gfm_integrated_system as baseline

    def known_local_result(spec, *, p_ref_w, t_end_s):
        assert spec is baseline.STEP_20_BESS_PI_SPEC and t_end_s == 6.5
        assert p_ref_w > 0
        solution = SimpleNamespace(t=np.array([0, 4.875, 5, 6.5]),
                                   y=np.array([[100000, 100000, 2000, 4000]]))
        model = SimpleNamespace(integrated_signals=lambda t, x: {"p_pcc": x[0]})
        return {"status": "REVIEW"}, solution, model

    monkeypatch.setattr(baseline, "run_scenario", known_local_result)
    case = load_network(FIXTURE)
    original = deepcopy(case)
    result = run_baseline(case, q_pcc_mvar=0.001)
    assert case == original
    assert result["p_ss_kw"] == 3.0 and result["ss_sample_count"] == 2
    assert result["local_metrics"]["status"] == "REVIEW"
    before, after = result["base_network"], result["with_microgrid"]
    assert after["slack_p_mw"] == pytest.approx(0.007 + after["line_losses_mw"], abs=1e-8)
    assert before["slack_q_mvar"] - after["slack_q_mvar"] == pytest.approx(0.001, abs=1e-6)
    assert abs(after["active_balance_residual_mw"]) < 1e-8


def test_execution_failure_remains_traceable(tmp_path, monkeypatch):
    import objective3_main

    def failure(*args, **kwargs):
        raise RuntimeError("Test solver failure")

    monkeypatch.setattr(objective3_main, "run_baseline", failure)
    output = tmp_path / "failure"
    with pytest.raises(RuntimeError, match="Test solver failure"):
        main([str(FIXTURE), "--run-baseline", "--q-pcc-mvar", "0", "--output-dir", str(output)])
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "EXECUTION_FAILED"
    assert "Test solver failure" in report["error"]
    assert not report["academic_case_validated"]
