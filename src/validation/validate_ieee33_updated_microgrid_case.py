"""Validate IEEE 33 base vs microgrid with active GFM and BESS."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import SIM_SS_WINDOW_FRACTION, SIM_T_END_S_DEFAULT
from controllers.gfm_controller import GFMController
from ieee33_coupling import IEEE33MicrogridWithBESS
from ieee33_reporting import select_line_metric


def _finite(values) -> bool:
    return bool(np.all(np.isfinite(np.asarray(values, dtype=float))))


def _check(label: str, condition: bool, detail: str) -> bool:
    print(f"  [{'OK' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    repo_root = SRC_DIR.parent
    output_dir = repo_root / "outputs" / "validation" / "ieee33_updated_microgrid"
    summary_path = output_dir / "summary_metrics.csv"
    system = IEEE33MicrogridWithBESS(
        str(SRC_DIR / "ieee33bus.txt"),
        output_dir=output_dir,
    )

    print("=" * 72)
    print("Validacion IEEE 33: caso base vs microrred con BESS y GFM activo")
    print("Acople secuencial one-way; inyeccion calculada desde p_pcc estacionario")
    print("=" * 72)

    p_ss_kw, data = system.simular()
    v_base, lines_base = system.flujo_base()
    base_converged = bool(getattr(system.net, "converged", False))
    v_mg, lines_mg = system.flujo_con_dg(p_ss_kw)
    mg_converged = bool(getattr(system.net, "converged", False))

    t = np.asarray(data["t"], dtype=float)
    p_pcc = np.asarray(data["p_pcc"], dtype=float)
    ss_mask = t > (SIM_T_END_S_DEFAULT * SIM_SS_WINDOW_FRACTION)
    p_ss_kw_expected = float(np.mean(p_pcc[ss_mask]) / 1000.0)
    p_average_ok = bool(np.isclose(p_ss_kw, p_ss_kw_expected, atol=1e-12, rtol=1e-12))

    v_base_arr = v_base.to_numpy(dtype=float)
    v_mg_arr = v_mg.to_numpy(dtype=float)
    delta_v = v_mg_arr - v_base_arr
    line_base, line_mg, line_label, line_key = select_line_metric(lines_base, lines_mg)

    dynamics = system.controller.frequency_dynamics
    summary = pd.DataFrame(
        [
            {"metric": "p_ss_kw", "value": p_ss_kw, "unit": "kW"},
            {"metric": "p_ss_kw_from_p_pcc", "value": p_ss_kw_expected, "unit": "kW"},
            {"metric": "p_ss_kw_residual", "value": p_ss_kw - p_ss_kw_expected, "unit": "kW"},
            {"metric": "gfm_inertia_m", "value": dynamics.inertia_m, "unit": "model"},
            {"metric": "gfm_damping_d", "value": dynamics.damping_d, "unit": "model"},
            {"metric": "v_min_base", "value": float(v_base.min()), "unit": "pu"},
            {"metric": "v_min_with_microgrid", "value": float(v_mg.min()), "unit": "pu"},
            {"metric": "delta_v_abs_max", "value": float(np.max(np.abs(delta_v))), "unit": "pu"},
            {"metric": f"line_base_max_{line_key}", "value": float(np.max(line_base)), "unit": line_label},
            {"metric": f"line_with_microgrid_max_{line_key}", "value": float(np.max(line_mg)), "unit": line_label},
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)

    gfm_active = bool(
        isinstance(system.controller, GFMController)
        and system.controller_state_name == "omega"
        and data.get("controller_class") == "GFMController"
    )
    traceable = bool(
        data.get("p_ss_source") == "mean(p_pcc[steady_state_window])"
        and int(data.get("ss_sample_count", -1)) == int(np.count_nonzero(ss_mask))
    )
    checks = [
        _check("GFMController activo", gfm_active, type(system.controller).__name__),
        _check("ventana estacionaria no vacia", bool(np.any(ss_mask)), str(np.count_nonzero(ss_mask))),
        _check("p_ss_kw promedio de p_pcc", p_average_ok, f"residual={p_ss_kw - p_ss_kw_expected:.3e} kW"),
        _check("fuente p_ss trazable", traceable, str(data.get("p_ss_source"))),
        _check("flujo base converge", base_converged, str(base_converged)),
        _check("flujo con microrred converge", mg_converged, str(mg_converged)),
        _check("p_ss_kw finito", np.isfinite(p_ss_kw), f"{p_ss_kw:.6f}"),
        _check("tensiones base finitas", _finite(v_base_arr), str(len(v_base_arr))),
        _check("tensiones microrred finitas", _finite(v_mg_arr), str(len(v_mg_arr))),
        _check("metricas de linea finitas", _finite(line_base) and _finite(line_mg), line_key),
    ]

    print(f"p_ss_kw={p_ss_kw:.12f}")
    print(f"p_ss_kw_recomputed={p_ss_kw_expected:.12f}")
    print(f"summary_path={summary_path}")
    status = "PASS" if all(checks) else "FAIL"
    print(f"status: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
