"""Validate a neutral network, optionally exercising the existing Obj. 1-2 baseline.

This is an interface rehearsal, not an academically validated Colombian case.
Network results are static one-way postprocessing of local microgrid dynamics.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import subprocess
import sys

from study_network import load_network, to_pandapower


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_baseline(case: dict, *, q_pcc_mvar: float) -> dict:
    """Reuse the accepted 16-state 20% BESS PI scenario and its existing metrics."""
    import numpy as np
    import pandapower as pp
    from config import GRID_FREQ_HZ_DEFAULT, SIM_SS_WINDOW_FRACTION
    from microgrid import Microgrid
    from validation.validate_gfm_integrated_system import (
        STEP_20_BESS_PI_SPEC, T_END_S_DEFAULT, run_scenario,
    )

    net, indices = to_pandapower(case)
    if not math.isclose(case["frequency_hz"], GRID_FREQ_HZ_DEFAULT, rel_tol=1e-9):
        raise ValueError("Network frequency must match the protected local baseline")
    if type(q_pcc_mvar) not in (int, float) or not math.isfinite(q_pcc_mvar):
        raise ValueError("q_pcc_mvar must be an explicit finite static assumption")
    reference = Microgrid()
    metrics, solution, model = run_scenario(
        STEP_20_BESS_PI_SPEC,
        p_ref_w=min(reference.P_ref_nominal, reference.p_available_ref),
        t_end_s=T_END_S_DEFAULT,
    )
    if metrics["status"] == "FAIL":
        raise RuntimeError(f"Local baseline failed: {metrics}")
    p_pcc = np.array([model.integrated_signals(float(t), solution.y[:, k])["p_pcc"]
                      for k, t in enumerate(solution.t)])
    start = T_END_S_DEFAULT * SIM_SS_WINDOW_FRACTION
    mask = solution.t > start
    if not mask.any() or not np.isfinite(p_pcc).all():
        raise RuntimeError("Missing or nonfinite PCC samples")
    p_ss_kw = float(p_pcc[mask].mean() / 1000.0)

    def power_flow():
        pp.runpp(net)
        if not net.converged or not np.isfinite(net.res_bus.vm_pu).all():
            raise RuntimeError("Network power flow did not produce finite converged voltages")
        return {
            "converged": bool(net.converged),
            "bus_vm_pu": {bus: float(net.res_bus.at[index, "vm_pu"])
                          for bus, index in indices.items()},
            "line_loading_percent": dict(zip(
                net.line.name, net.res_line.loading_percent.astype(float))),
            "line_losses_mw": float(net.res_line.pl_mw.sum()),
            "slack_p_mw": float(net.res_ext_grid.p_mw.sum()),
            "slack_q_mvar": float(net.res_ext_grid.q_mvar.sum()),
            "active_balance_residual_mw": float(
                net.res_ext_grid.p_mw.sum() + net.res_sgen.p_mw.sum()
                - net.res_load.p_mw.sum() - net.res_line.pl_mw.sum()),
            "reactive_balance_residual_mvar": float(
                net.res_ext_grid.q_mvar.sum() + net.res_sgen.q_mvar.sum()
                - net.res_load.q_mvar.sum() - net.res_line.ql_mvar.sum()),
        }

    base = power_flow()
    pp.create_sgen(net, bus=indices[case["pcc_bus"]], p_mw=p_ss_kw / 1000.0,
                   q_mvar=q_pcc_mvar, name="Obj1-2 equivalent PCC injection")
    return {
        "local_metrics": metrics,
        "p_ss_kw": p_ss_kw,
        "p_ss_source": "arithmetic mean(p_pcc[t > ss_window_start_s])",
        "ss_window_start_s": start,
        "ss_window_end_s": T_END_S_DEFAULT,
        "ss_sample_count": int(mask.sum()),
        "q_pcc_mvar": q_pcc_mvar,
        "q_pcc_source": "user-specified static assumption; not a Q-V controller",
        "base_network": base,
        "with_microgrid": power_flow(),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="Neutral schema v1 JSON, not an external export")
    parser.add_argument("--run-baseline", action="store_true", help="Run existing 6.5 s GFM+BESS PI scenario")
    parser.add_argument("--q-pcc-mvar", type=float, help="Explicit static reactive injection assumption")
    parser.add_argument("--output-dir", type=Path, help="New directory; existing paths are never overwritten")
    args = parser.parse_args(argv)
    if args.run_baseline != (args.q_pcc_mvar is not None):
        parser.error("--run-baseline requires --q-pcc-mvar, used only with that option")
    case = load_network(args.case)
    # ponytail: one immutable directory per run; add a results index only for real campaigns.
    output = args.output_dir or REPO_ROOT / "outputs" / "objective3" / datetime.now(
        timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    canonical = json.dumps(case, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    (output / "network.json").write_text(canonical + "\n", encoding="utf-8")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=False)
    state = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=REPO_ROOT,
                           capture_output=True, text=True, check=False)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "source_changes": state.stdout.splitlines() if state.returncode == 0 else None,
        "python": sys.version,
        "input_path": str(args.case.resolve()),
        "network_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "synthetic": case["synthetic"],
        "pcc_bus": case["pcc_bus"],
        "status": "DATA_CHECKED",
        "academic_case_validated": False,
        "scope": "Interface rehearsal; local dynamics then static one-way network postprocessing",
    }
    try:
        if args.run_baseline:
            report["dependencies"] = {name: version(name) for name in
                                      ("numpy", "scipy", "pandas", "pandapower", "openpyxl")}
            report["results"] = run_baseline(case, q_pcc_mvar=args.q_pcc_mvar)
            report["status"] = "BASELINE_EXECUTED"
    except Exception as exc:
        report.update(status="EXECUTION_FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (output / "summary.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"status={report['status']} academic_case_validated=False output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
