"""Isolated, non-invasive comparison of the unchanged PV Newton current kernel.

Reference: PR #57 head 740a704f60976427d75c2cbc3f9be3406afdbe74.
No protected source files, scenarios, or scientific evidence are modified.
Use --profile-only on the exact PR #57 Python stack, then --compare in the
common Numba-compatible stack. All variants use the same SciPy solver.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import math
import os
import platform
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import scipy
from scipy.integrate import solve_ivp

import pv_model as pv_source
from config import PV_NEWTON_MAX_ITER_DEFAULT
from controllers.gfm_controller import GFMController
from microgrid import Microgrid

try:
    import numba
    from numba import njit
except ImportError:
    numba = None
    njit = None

try:
    from pv_kernel_rust import PvKernel
except ImportError:
    PvKernel = None

# Array ordering is deliberately documented and identical to Rust.
PARAM_NAMES = (
    "modules_in_series", "strings_in_parallel", "voc_stc", "isc_stc",
    "imp_stc", "ns_cells", "alpha_isc", "ideality_n", "rs", "rsh",
    "elementary_charge", "boltzmann", "bandgap_j", "kelvin_offset",
    "stc_irradiance", "stc_temperature", "current_min",
    "epsilon_denominator", "epsilon_current", "newton_tolerance",
)


def params_from_model(model: Microgrid) -> np.ndarray:
    pv = model.pv
    m = pv.p.module
    return np.asarray((
        pv.p.modules_in_series, pv.p.strings_in_parallel,
        m.voc_stc, m.isc_stc, m.imp_stc, m.ns_cells, m.alpha_isc, m.n,
        m.rs, m.rsh, pv.q, pv.k, pv.Eg,
        pv_source.KELVIN_OFFSET, pv_source.PV_STC_IRRADIANCE_W_PER_M2,
        pv_source.PV_STC_TEMP_C, pv_source.PV_CURRENT_MIN_A,
        pv_source.PV_NUMERIC_EPS_DEN, pv_source.PV_NUMERIC_EPS_A,
        pv_source.PV_NEWTON_CURRENT_TOL_A,
    ), dtype=np.float64)


if njit is not None:
    @njit(cache=True)
    def numba_current(vpv, g, tc, p, max_iter):
        vmod = vpv / p[0]
        iph = (g / p[14]) * (p[3] + p[6] * (tc - p[15]))
        stc_kelvin = p[15] + p[13]
        vt_stc = p[11] * stc_kelvin / p[10]
        denom = math.exp(p[2] / (p[7] * p[5] * vt_stc)) - 1.0
        io_stc = p[3] / max(denom, p[17])
        kelvin = tc + p[13]
        io = io_stc * (kelvin / stc_kelvin) ** 3 * math.exp(
            (p[12] / (p[7] * p[11])) * (1.0 / stc_kelvin - 1.0 / kelvin)
        )
        vt = p[11] * kelvin / p[10]
        current = max((g / p[14]) * p[4], p[16])
        a = p[7] * p[5] * vt
        for _ in range(max_iter):
            exp_term = math.exp((vmod + current * p[8]) / max(a, p[18]))
            f = iph - io * (exp_term - 1.0) - (vmod + current * p[8]) / p[9] - current
            df = -io * exp_term * (p[8] / max(a, p[18])) - p[8] / p[9] - 1.0
            change = -f / min(df, -p[17])
            new_current = max(current + change, p[16])
            if abs(new_current - current) < p[19]:
                current = new_current
                break
            current = new_current
        return current * p[1]

    @njit(cache=True)
    def numba_noop():
        return 1.0


def new_model():
    # The protected GFM architecture, plant equations, M and D are unchanged.
    return Microgrid(controller=GFMController(
        p_ref=3000.0, inertia_m=80.0, damping_d=1500.0
    ))


def make_functions():
    baseline = new_model()
    p = params_from_model(baseline)
    calls = {"python": baseline.pv.ipv_from_vpv}
    if numba is not None:
        numba_current(340.0, 800.0, 25.0, p, PV_NEWTON_MAX_ITER_DEFAULT)
        calls["numba"] = lambda v, g, tc: numba_current(
            v, g, tc, p, PV_NEWTON_MAX_ITER_DEFAULT
        )
    if PvKernel is not None:
        kernel = PvKernel(p.tolist(), PV_NEWTON_MAX_ITER_DEFAULT)
        calls["rust"] = kernel.current
        calls["rust_noop"] = kernel.noop
    return calls, p


def new_dcdc16_model():
    from controllers.dc_link_bess_pi import DCLinkBESSPIController
    from microgrid_bess_dcdc import (
        MicrogridWithBESSDCDC, default_bat26_53_dcdc_parameters,
    )
    from validation.compare_bess_soh_scenarios import _build_bess_for_soh, _nominal_soh

    bess = _build_bess_for_soh(_nominal_soh())
    bess.soc_initial = 0.60
    return MicrogridWithBESSDCDC(
        controller=GFMController(f_hz=50.0, inertia_m=80.0, damping_d=1500.0),
        dc_link_bess_pi=DCLinkBESSPIController(
            vdc_ref_v=340.0, kp_w_per_v=160.0, ki_w_per_v_s=400.0,
        ),
        bess_enabled=True, bess_model=bess,
        dcdc_parameters=default_bat26_53_dcdc_parameters(),
        load_frequency_hz=50.0,
    )


def simulation(kind, calls, scenario="gfm12"):
    model = new_model() if scenario == "gfm12" else new_dcdc16_model()
    if kind != "python":
        # Per-instance experimental override only; repository implementation
        # remains untouched, including its original Python public method.
        model.pv.ipv_from_vpv = lambda Vpv, G, T_c: calls[kind](Vpv, G, T_c)
    t_points = np.linspace(0.0, 0.05, 11)
    solution = solve_ivp(
        model.system_dynamics, (0.0, 0.05),
        model.initial_state() if scenario == "gfm12" else model.initial_state_with_bess(),
        method="RK45", rtol=1e-6, atol=1e-8, max_step=5e-5,
        t_eval=t_points,
    )
    if not solution.success or not np.isfinite(solution.y).all():
        raise AssertionError(f"{kind}: SciPy solver failed: {solution.message}")
    return solution


def profile_python(target: Path):
    calls, p = make_functions()
    profiler = cProfile.Profile()
    profiler.enable()
    solution = simulation("python", calls)
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(45)
    target.write_text(stream.getvalue(), encoding="utf-8")
    chosen = []
    for (filename, line, name), (cc, nc, own_time, cumulative, _) in stats.stats.items():
        if any(key in filename for key in ("pv_model.py", "microgrid.py", "lcl_filter.py", "gfm_controller.py")):
            chosen.append({
                "module": Path(filename).name, "function": name,
                "calls": nc, "self_s": own_time, "cumulative_s": cumulative,
            })
    chosen.sort(key=lambda x: -x["cumulative_s"])
    return {
        "profile_output": str(target), "nfev": solution.nfev,
        "functions": chosen[:20], "param_names": PARAM_NAMES,
        "note": "cProfile is intrusive; use wall clock for end-to-end speedups.",
    }


def median_ns(fn, iterations, repeats=5):
    fn()  # warm-up; outside measurement
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            fn()
        samples.append((time.perf_counter_ns() - start) / iterations)
    return {"median_ns": statistics.median(samples), "runs_ns": samples}


def compare_all(target: Path):
    if numba is None or PvKernel is None:
        raise RuntimeError("Comparison requires installed Numba and the PyO3 Rust extension.")
    calls, p = make_functions()
    grid = [(v, g, tc) for v in (0., 220., 340., 450., 550.)
            for g in (0., 100., 600., 1000.)
            for tc in (0., 25., 45.)]
    numerical = {}
    for kind in ("numba", "rust"):
        differences = []
        for args in grid:
            ref = calls["python"](*args)
            measured = calls[kind](*args)
            if not (math.isfinite(ref) and math.isfinite(measured)):
                raise AssertionError(f"Nonfinite comparison {kind}: {args}")
            differences.append(abs(ref - measured))
        numerical[kind] = {"max_abs_A": max(differences), "cases": len(grid)}
        if max(differences) > 1e-9:
            raise AssertionError(f"{kind}: PV equivalent-current tolerance failed")
    micro = {}
    values = [(340. + i % 11, 700. + i % 9 * 25., 25. + i % 5)
              for i in range(1000)]
    for kind in ("python", "numba", "rust"):
        fn = calls[kind]
        micro[kind] = median_ns(
            lambda: [fn(*values[i]) for i in range(1000)], 3, repeats=7
        )
        micro[kind]["median_ns_per_call"] = micro[kind]["median_ns"] / 1000
    noop = {
        "python": median_ns(lambda: 1.0, 25000),
        "numba": median_ns(numba_noop, 25000),
        "rust": median_ns(calls["rust_noop"], 25000),
    }

    trajectories, runs = {}, {}
    reference = simulation("python", calls)
    for kind in ("python", "numba", "rust"):
        durations = []
        for _ in range(3):
            start = time.perf_counter()
            got = simulation(kind, calls)
            durations.append(time.perf_counter() - start)
        err = np.abs(got.y - reference.y)
        trajectories[kind] = {
            "max_abs_all_states": float(np.max(err)),
            "max_abs_vdc_V": float(np.max(err[0])),
            "max_abs_frequency_Hz": float(np.max(err[10]) / (2 * np.pi)),
            "nfev": got.nfev,
            "state_count": len(got.y),
            "time_points": len(got.t),
        }
        if not np.allclose(got.y, reference.y, rtol=2e-9, atol=2e-7):
            raise AssertionError(f"{kind}: GFM/SciPy trajectory tolerance failed")
        runs[kind] = {"median_s": statistics.median(durations), "runs_s": durations}

    dcdc_reference = simulation("python", calls, scenario="dcdc16")
    dcdc_runs, dcdc_trajectories = {}, {}
    for kind in ("python", "numba", "rust"):
        durations = []
        for _ in range(3):
            start = time.perf_counter()
            got = simulation(kind, calls, scenario="dcdc16")
            durations.append(time.perf_counter() - start)
        errors = np.abs(got.y - dcdc_reference.y)
        dcdc_trajectories[kind] = {
            "max_abs_all_states": float(np.max(errors)),
            "max_abs_vdc_V": float(np.max(errors[0])),
            "max_abs_frequency_Hz": float(np.max(errors[10]) / (2 * np.pi)),
            "max_abs_soc": float(np.max(errors[12])),
            "nfev": got.nfev, "state_count": len(got.y),
            "time_points": len(got.t),
        }
        if len(got.y) != 16 or not np.allclose(
            got.y, dcdc_reference.y, rtol=2e-9, atol=2e-7
        ):
            raise AssertionError(f"{kind}: GFM+BESS+DC/DC 16-state tolerance failed")
        dcdc_runs[kind] = {
            "median_s": statistics.median(durations), "runs_s": durations,
        }

    data = {
        "pv_scalar_equivalence": numerical,
        "pv_microbenchmark": micro,
        "interoperability_noop": noop,
        "scipy_gfm_trajectory": trajectories,
        "scipy_gfm_runtime": runs,
        "scipy_dcdc_trajectory": dcdc_trajectories,
        "scipy_dcdc_runtime": dcdc_runs,
        "speedups": {
            kind: {
                "pv_kernel": micro["python"]["median_ns"] / micro[kind]["median_ns"],
                "full_scipy": runs["python"]["median_s"] / runs[kind]["median_s"],
                "dcdc16_scipy": dcdc_runs["python"]["median_s"] / dcdc_runs[kind]["median_s"],
            } for kind in ("numba", "rust")
        },
        "interpretation": "All speedups are within the same comparative environment. "
        "The 0.05 s GFM 12-state and GFM+BESS+DC/DC 16-state runs are numerical "
        "benchmarks, not the full 6.5 s PR57 validation campaign.",
    }
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("work/python_rust_perf"))
    args = parser.parse_args()
    if args.profile_only == args.compare:
        parser.error("Choose exactly one of --profile-only and --compare")
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "reference_pr": 57,
        "reference_head_sha": "740a704f60976427d75c2cbc3f9be3406afdbe74",
        "checkout_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__, "scipy": scipy.__version__,
        "numba": None if numba is None else numba.__version__,
        "rust_extension_present": PvKernel is not None,
        "cpu": platform.processor(),
    }
    label = "reference" if args.profile_only else "comparative"
    (args.output / f"{label}_environment.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    if args.profile_only:
        output = profile_python(args.output / "reference_cprofile.txt")
        (args.output / "reference_profile.json").write_text(
            json.dumps(output, indent=2), encoding="utf-8"
        )
        print(json.dumps({"environment": metadata, "profile": output}, indent=2))
    else:
        output = compare_all(args.output / "comparison.json")
        print(json.dumps({"environment": metadata, "comparison": output}, indent=2))


if __name__ == "__main__":
    main()
