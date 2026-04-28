"""Validate IEEE 33 base vs updated preliminary-BESS microgrid case."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ieee33_coupling import IEEE33MicrogridWithBESS
from ieee33_reporting import select_line_metric


def _finite_array(values) -> bool:
    return bool(np.all(np.isfinite(np.asarray(values, dtype=float))))


def _check(label: str, condition: bool, detail: str) -> bool:
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label}: {detail}")
    return condition


def main() -> int:
    repo_root = SRC_DIR.parent
    output_dir = repo_root / "outputs" / "validation" / "ieee33_updated_microgrid"
    summary_path = output_dir / "summary_metrics.csv"

    ruta_txt = SRC_DIR / "ieee33bus.txt"
    sistema = IEEE33MicrogridWithBESS(str(ruta_txt), output_dir=output_dir)

    print("=" * 72)
    print("Validacion IEEE 33: caso base vs microrred actualizada con BESS preliminar")
    print("Acople: secuencial one-way; no GFM/VSG integrado")
    print("=" * 72)

    p_ss_kw, datos = sistema.simular()
    v_base, res_line_base = sistema.flujo_base()
    base_converged = bool(getattr(sistema.net, "converged", False))
    v_mg, res_line_mg = sistema.flujo_con_dg(p_ss_kw)
    mg_converged = bool(getattr(sistema.net, "converged", False))

    v_base_arr = v_base.to_numpy(dtype=float)
    v_mg_arr = v_mg.to_numpy(dtype=float)
    delta_v = v_mg_arr - v_base_arr
    delta_v_abs_max = float(np.max(np.abs(delta_v))) if delta_v.size else float("nan")

    v_min_base = float(v_base.min())
    v_min_mg = float(v_mg.min())
    node_min_base = int(v_base.idxmin()) + 1
    node_min_mg = int(v_mg.idxmin()) + 1
    delta_v_min = v_min_mg - v_min_base

    line_base, line_mg, line_label, line_key = select_line_metric(res_line_base, res_line_mg)
    line_base_max = float(np.max(line_base))
    line_mg_max = float(np.max(line_mg))
    line_delta_max = line_mg_max - line_base_max

    summary = pd.DataFrame(
        [
            {"metric": "p_ss_kw", "value": float(p_ss_kw), "unit": "kW"},
            {"metric": "v_min_base", "value": v_min_base, "unit": "pu"},
            {"metric": "node_min_base", "value": node_min_base, "unit": "bus"},
            {"metric": "v_min_with_microgrid", "value": v_min_mg, "unit": "pu"},
            {"metric": "node_min_with_microgrid", "value": node_min_mg, "unit": "bus"},
            {"metric": "delta_v_min", "value": delta_v_min, "unit": "pu"},
            {"metric": "delta_v_abs_max", "value": delta_v_abs_max, "unit": "pu"},
            {"metric": f"line_base_max_{line_key}", "value": line_base_max, "unit": line_label},
            {"metric": f"line_with_microgrid_max_{line_key}", "value": line_mg_max, "unit": line_label},
            {"metric": f"line_delta_max_{line_key}", "value": line_delta_max, "unit": line_label},
        ]
    )
    summary_saved = False
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary.to_csv(summary_path, index=False)
        summary_saved = True
    except PermissionError as exc:
        print(f"\nADVERTENCIA: no se pudo guardar el CSV de resumen: {exc}")

    print("\nMetricas principales")
    print(f"  p_ss_kw                         : {p_ss_kw:.6f} kW")
    print(f"  V_min base                      : {v_min_base:.6f} pu (Nodo {node_min_base})")
    print(f"  V_min con microrred             : {v_min_mg:.6f} pu (Nodo {node_min_mg})")
    print(f"  Delta V_min                     : {delta_v_min:.6f} pu")
    print(f"  Delta nodal max absoluto        : {delta_v_abs_max:.6f} pu")
    print(f"  Metrica lineas                  : {line_key} ({line_label})")
    print(f"  Max lineas base                 : {line_base_max:.6f}")
    print(f"  Max lineas con microrred        : {line_mg_max:.6f}")
    print(f"  Delta max lineas                : {line_delta_max:.6f}")
    if summary_saved:
        print(f"  CSV resumen                     : {summary_path}")
    else:
        print("  CSV resumen                     : no guardado por permisos")

    same_bus_count = len(v_base_arr) == len(v_mg_arr)
    one_way_traceable = np.isfinite(p_ss_kw) and "p_pcc" in datos and len(datos["p_pcc"]) == len(datos["t"])

    checks = [
        _check("flujo base converge", base_converged, str(base_converged)),
        _check("flujo con microrred converge", mg_converged, str(mg_converged)),
        _check("p_ss_kw finito", np.isfinite(p_ss_kw), f"{p_ss_kw:.6f}"),
        _check("tensiones base finitas", _finite_array(v_base_arr), f"{len(v_base_arr)} buses"),
        _check("tensiones con microrred finitas", _finite_array(v_mg_arr), f"{len(v_mg_arr)} buses"),
        _check("numero de buses comparados coincide", same_bus_count, f"{len(v_base_arr)} vs {len(v_mg_arr)}"),
        _check("V_min base finita", np.isfinite(v_min_base), f"{v_min_base:.6f}"),
        _check("V_min con microrred finita", np.isfinite(v_min_mg), f"{v_min_mg:.6f}"),
        _check("metricas de linea base finitas", _finite_array(line_base), line_key),
        _check("metricas de linea con microrred finitas", _finite_array(line_mg), line_key),
        _check("acople one-way trazable", one_way_traceable, "p_ss_kw escalar desde p_pcc -> flujo_con_dg"),
    ]

    if all(checks):
        print("\nstatus: PASS")
        return 0

    print("\nstatus: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
