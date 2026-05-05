"""Reporting helpers for one-way sequential IEEE 33 coupling analysis."""

import numpy as np
import pandas as pd


def select_line_metric(
    res_line_base: pd.DataFrame,
    res_line_mg: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, str, str]:
    """Select a robust line metric for side-by-side comparison."""
    if "loading_percent" in res_line_base.columns and "loading_percent" in res_line_mg.columns:
        loading_base = res_line_base["loading_percent"].to_numpy(dtype=float)
        loading_mg = res_line_mg["loading_percent"].to_numpy(dtype=float)
        if np.isfinite(loading_base).any() and np.isfinite(loading_mg).any():
            return loading_base, loading_mg, "Loading (%)", "loading_percent"

    if "i_ka" in res_line_base.columns and "i_ka" in res_line_mg.columns:
        corr_base_a = 1000.0 * res_line_base["i_ka"].to_numpy(dtype=float)
        corr_mg_a = 1000.0 * res_line_mg["i_ka"].to_numpy(dtype=float)
        return corr_base_a, corr_mg_a, "Corriente [A]", "i_ka"

    if "p_from_mw" in res_line_base.columns and "p_from_mw" in res_line_mg.columns:
        p_base_kw = 1000.0 * np.abs(res_line_base["p_from_mw"].to_numpy(dtype=float))
        p_mg_kw = 1000.0 * np.abs(res_line_mg["p_from_mw"].to_numpy(dtype=float))
        return p_base_kw, p_mg_kw, "Potencia activa por linea [kW]", "p_from_mw"

    raise ValueError("No se encontro una metrica valida para comparar el estado de lineas.")


def build_ieee33_comparison_table(
    pcc_bus_num: int,
    p_ss_kw: float,
    v_base: pd.Series,
    v_mg: pd.Series,
    res_line_base: pd.DataFrame,
    res_line_mg: pd.DataFrame,
    line_metric_base: np.ndarray,
    line_metric_mg: np.ndarray,
    line_metric_key: str,
) -> pd.DataFrame:
    """Build quantitative IEEE 33 comparison table for the reporting layer."""
    losses_base_kw = float(res_line_base["pl_mw"].sum() * 1000.0)
    losses_mg_kw = float(res_line_mg["pl_mw"].sum() * 1000.0)
    losses_reduction_kw = losses_base_kw - losses_mg_kw
    losses_reduction_pct = 100.0 * losses_reduction_kw / max(losses_base_kw, 1e-9)
    line_metric_column = (
        "Loading_max_pct" if line_metric_key == "loading_percent" else f"{line_metric_key}_max"
    )

    rows = [
        {
            "Caso": "Sin microrred",
            "Nodo PCC": pcc_bus_num,
            "P_inyectada_kW": 0.0,
            "V_min_pu": float(v_base.min()),
            "Nodo_V_min": int(v_base.idxmin() + 1),
            "V_max_pu": float(v_base.max()),
            "Nodo_V_max": int(v_base.idxmax() + 1),
            "Perdidas_activas_kW": losses_base_kw,
            "Reduccion_perdidas_kW": 0.0,
            "Reduccion_perdidas_pct": 0.0,
            "Nodos_menor_0_95_pu": int((v_base < 0.95).sum()),
            line_metric_column: float(np.max(line_metric_base)),
        },
        {
            "Caso": f"Con microrred nodo {pcc_bus_num}",
            "Nodo PCC": pcc_bus_num,
            "P_inyectada_kW": float(p_ss_kw),
            "V_min_pu": float(v_mg.min()),
            "Nodo_V_min": int(v_mg.idxmin() + 1),
            "V_max_pu": float(v_mg.max()),
            "Nodo_V_max": int(v_mg.idxmax() + 1),
            "Perdidas_activas_kW": losses_mg_kw,
            "Reduccion_perdidas_kW": losses_reduction_kw,
            "Reduccion_perdidas_pct": losses_reduction_pct,
            "Nodos_menor_0_95_pu": int((v_mg < 0.95).sum()),
            line_metric_column: float(np.max(line_metric_mg)),
        },
    ]
    return pd.DataFrame(rows)


def print_ieee33_report(
    pcc_bus_num: int,
    p_ss_kw: float,
    v_base: pd.Series,
    v_mg: pd.Series,
    res_line_base: pd.DataFrame,
    res_line_mg: pd.DataFrame,
    line_metric_base: np.ndarray,
    line_metric_mg: np.ndarray,
    line_metric_label: str,
    line_metric_key: str,
) -> pd.DataFrame:
    """Print static IEEE 33 comparison using one-way sequential coupling."""
    print("\n" + "=" * 55)
    print("  PASO 2: Flujo de carga IEEE 33 - Postproceso estatico (one-way sequential coupling)")
    print("=" * 55)
    print(f"  Baseline conectada en  : Nodo {pcc_bus_num}")
    print(f"  Potencia media inyectada: {p_ss_kw:.4f} kW  ({p_ss_kw*1000:.1f} W)")

    nodo_min_base = v_base.idxmin() + 1
    nodo_min_mg = v_mg.idxmin() + 1
    print(f"\n  SIN baseline  -> Nodo {nodo_min_base}  V_min = {v_base.min():.4f} p.u.")
    print(f"  CON baseline  -> Nodo {nodo_min_mg}  V_min = {v_mg.min():.4f} p.u.")

    mejora_pu = v_mg.min() - v_base.min()
    mejora_pct = 100.0 * mejora_pu / max(v_base.min(), 1e-9)
    print(f"\n  Mejora en V_min : +{mejora_pu:.4f} p.u. ({mejora_pct:.2f} %)")

    nodos_bajo_limite_base = (v_base < 0.95).sum()
    nodos_bajo_limite_mg = (v_mg < 0.95).sum()
    print(
        f"  Nodos < 0.95 p.u.     : {nodos_bajo_limite_base} -> {nodos_bajo_limite_mg} "
        "(sin->con baseline)"
    )
    print(f"  Metrica de lineas usada: {line_metric_key} ({line_metric_label})")
    print(
        f"  Valor maximo en lineas : {line_metric_base.max():.3f} -> "
        f"{line_metric_mg.max():.3f} (sin->con baseline)"
    )
    comparison_table = build_ieee33_comparison_table(
        pcc_bus_num=pcc_bus_num,
        p_ss_kw=p_ss_kw,
        v_base=v_base,
        v_mg=v_mg,
        res_line_base=res_line_base,
        res_line_mg=res_line_mg,
        line_metric_base=line_metric_base,
        line_metric_mg=line_metric_mg,
        line_metric_key=line_metric_key,
    )
    print("\n  Tabla comparativa IEEE 33:")
    print(comparison_table.to_string(index=False))
    print("=" * 55)
    return comparison_table
