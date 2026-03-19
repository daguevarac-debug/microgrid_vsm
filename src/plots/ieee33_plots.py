"""Plotting helpers for one-way sequential IEEE 33 + microgrid analysis."""

from pathlib import Path

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def ieee33_manual_coordinates() -> dict[int, tuple[float, float]]:
    """Manual coordinates inspired by the classic IEEE 33-bus single-line layout."""
    pos = {n: (n - 1, 0.0) for n in range(1, 19)}
    pos.update(
        {
            19: (1, -1),
            20: (2, -1),
            21: (3, -1),
            22: (4, -1),
            23: (2, 1),
            24: (3, 1),
            25: (4, 1),
            26: (5, 1),
            27: (6, 1),
            28: (7, 1),
            29: (8, 1),
            30: (9, 1),
            31: (10, 1),
            32: (11, 1),
            33: (12, 1),
        }
    )
    return pos


def plot_ieee33_topology(
    ax: plt.Axes,
    ramas: list[tuple[int, int]],
    nodo_pcc: int = 18,
    p_ss_kw: float = 0.0,
) -> None:
    """Draw a simplified IEEE 33 one-line diagram with highlighted PCC."""
    pos = ieee33_manual_coordinates()

    for n_from, n_to in ramas:
        if n_from in pos and n_to in pos:
            x1, y1 = pos[n_from]
            x2, y2 = pos[n_to]
            ax.plot([x1, x2], [y1, y2], color="black", linewidth=1.4, zorder=1)

    for nodo in range(1, 34):
        x, y = pos[nodo]
        ax.scatter(x, y, s=52, facecolor="white", edgecolor="black", linewidth=1.1, zorder=3)
        dy = 0.12 if y <= 0 else 0.1
        ax.text(x, y + dy, f"{nodo}", ha="center", va="bottom", fontsize=8)

    x_pcc, y_pcc = pos[nodo_pcc]
    ax.scatter(
        x_pcc,
        y_pcc,
        s=120,
        facecolor="#ffdd57",
        edgecolor="#c62828",
        linewidth=1.8,
        zorder=4,
    )
    ax.text(
        x_pcc + 0.25,
        y_pcc - 0.22,
        "PCC / Microrred",
        color="#c62828",
        fontsize=9,
        fontweight="bold",
    )

    if abs(p_ss_kw) > 1e-9:
        ax.annotate(
            "Baseline DG",
            xy=(x_pcc, y_pcc + 0.02),
            xytext=(x_pcc, y_pcc + 0.72),
            textcoords="data",
            ha="center",
            va="bottom",
            fontsize=9,
            color="green",
            arrowprops={"arrowstyle": "-|>", "color": "green", "lw": 1.7},
        )

    ax.set_title("Sistema IEEE 33 nodos con punto de acople de la microrred", fontsize=11)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.8, 17.8)
    ax.set_ylim(-1.5, 1.6)
    ax.axis("off")


def graficar_topologia_ieee33(
    ax: plt.Axes,
    ramas: list[tuple[int, int]],
    nodo_pcc: int = 18,
    p_ss_kw: float = 0.0,
) -> None:
    """Alias publico en espanol para compatibilidad."""
    plot_ieee33_topology(ax=ax, ramas=ramas, nodo_pcc=nodo_pcc, p_ss_kw=p_ss_kw)


def plot_ieee33_results(
    output_dir: Path,
    v_base: pd.Series,
    v_mg: pd.Series,
    datos: dict,
    p_ss_kw: float,
    estado_lineas_base: np.ndarray,
    estado_lineas_mg: np.ndarray,
    etiqueta_estado_lineas: str,
    metrica_lineas: str,
    nodo_pcc: int,
    ramas: list[tuple[int, int]],
) -> None:
    """Plot thesis-grade summary figures for one-way sequential coupling."""
    nodos = v_base.index + 1
    pcc_bus_num = nodo_pcc
    delta_v = v_mg.to_numpy() - v_base.to_numpy()

    fig_a = plt.figure(figsize=(14, 9))
    fig_a.suptitle(
        "Acople secuencial one-way: IEEE 33 + PV + DC-link + LCL baseline averaged model",
        fontsize=13,
        fontweight="bold",
    )
    gs_a = gridspec.GridSpec(2, 2, figure=fig_a, height_ratios=[1.2, 1.0], hspace=0.4, wspace=0.35)

    ax_top = fig_a.add_subplot(gs_a[0, :])
    plot_ieee33_topology(ax=ax_top, ramas=ramas, nodo_pcc=pcc_bus_num, p_ss_kw=p_ss_kw)

    ax1 = fig_a.add_subplot(gs_a[1, 0])
    ax1.plot(nodos, v_base, "b-o", markersize=4, label="Sin baseline")
    ax1.plot(
        nodos,
        v_mg,
        "g-s",
        markersize=4,
        label=f"Con baseline ({p_ss_kw:.2f} kW en nodo {pcc_bus_num})",
    )
    ax1.axhline(0.95, color="r", linestyle="--", linewidth=1.2, label="Limite inferior (0.95 p.u.)")
    ax1.axvline(pcc_bus_num, color="black", linestyle=":", linewidth=1.5, label=f"PCC - Nodo {pcc_bus_num}")
    ax1.fill_between(nodos, v_base, v_mg, alpha=0.15, color="green", label="Mejora de voltaje")
    ax1.set_title("Perfil de voltaje sin y con baseline")
    ax1.set_xlabel("Numero de nodo")
    ax1.set_ylabel("Voltaje (p.u.)")
    ax1.set_xticks(range(1, 34, 2))
    ax1.grid(True, alpha=0.4)
    ax1.legend(fontsize=8, loc="lower left")

    ax_delta = fig_a.add_subplot(gs_a[1, 1])
    colores = np.where(delta_v >= 0.0, "#2e7d32", "#c62828")
    ax_delta.bar(nodos, delta_v, color=colores, width=0.75, edgecolor="black", linewidth=0.3)
    ax_delta.axhline(0.0, color="black", linestyle="--", linewidth=1.0)
    ax_delta.axvline(
        pcc_bus_num,
        color="black",
        linestyle=":",
        linewidth=1.2,
        label=f"PCC - Nodo {pcc_bus_num}",
    )
    ax_delta.set_title("Mejora de voltaje por nodo")
    ax_delta.set_xlabel("Numero de nodo")
    ax_delta.set_ylabel("Delta V (p.u.)")
    ax_delta.set_xticks(range(1, 34, 2))
    ax_delta.grid(True, alpha=0.35)
    ax_delta.legend(fontsize=8, loc="best")

    ruta_figura_a = output_dir / "ieee33_microgrid_resultado.png"
    fig_a.savefig(ruta_figura_a, dpi=180, bbox_inches="tight")

    fig_b = plt.figure(figsize=(15, 4.8))
    fig_b.suptitle(
        f"Dinamica local baseline y estado de lineas IEEE 33 (PCC: nodo {pcc_bus_num})",
        fontsize=12,
        fontweight="bold",
    )
    gs_b = gridspec.GridSpec(1, 3, figure=fig_b, wspace=0.35)

    ax2 = fig_b.add_subplot(gs_b[0, 0])
    ax2.plot(datos["t"], datos["Vdc"], "b-", linewidth=1)
    ax2.axvline(datos["t_step"], color="orange", linestyle="--", label="Escalon de carga")
    ax2.set_title("Bus DC del baseline - Vdc(t)")
    ax2.set_xlabel("t [s]")
    ax2.set_ylabel("Vdc [V]")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.4)

    ax3 = fig_b.add_subplot(gs_b[0, 1])
    ax3.plot(datos["t"], datos["p_inst"] / 1000.0, "g-", linewidth=1)
    ax3.axvline(datos["t_step"], color="orange", linestyle="--", label="Escalon de carga")
    ax3.axhline(
        p_ss_kw,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"P_ss = {p_ss_kw:.3f} kW (potencia media inyectada al IEEE 33)",
    )
    ax3.set_title("Potencia activa del baseline - P(t)")
    ax3.set_xlabel("t [s]")
    ax3.set_ylabel("P [kW]")
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.4)

    ax4 = fig_b.add_subplot(gs_b[0, 2])
    idx_lineas = np.arange(1, len(estado_lineas_base) + 1)
    ax4.plot(idx_lineas, estado_lineas_base, "b-o", markersize=3.5, linewidth=1.1, label="Sin baseline")
    ax4.plot(idx_lineas, estado_lineas_mg, "g-s", markersize=3.5, linewidth=1.1, label="Con baseline")
    if metrica_lineas == "loading_percent":
        ax4.axhline(100.0, color="r", linestyle="--", linewidth=1.0, label="Limite termico (100%)")
    ax4.set_title("Estado electrico de lineas: sin y con baseline")
    ax4.set_xlabel("Indice de linea / tramo")
    ax4.set_ylabel(etiqueta_estado_lineas)
    ax4.grid(True, alpha=0.4)
    ax4.legend(fontsize=8, loc="best")

    ruta_figura_b = output_dir / "ieee33_microgrid_dinamica_lineas.png"
    fig_b.savefig(ruta_figura_b, dpi=180, bbox_inches="tight")

    print("\n  Figura guardada: ieee33_microgrid_resultado.png")
    print("  Figura guardada: ieee33_microgrid_dinamica_lineas.png")
    plt.show()


def graficar_resultados_ieee33(
    output_dir: Path,
    v_base: pd.Series,
    v_mg: pd.Series,
    datos: dict,
    p_ss_kw: float,
    estado_lineas_base: np.ndarray,
    estado_lineas_mg: np.ndarray,
    etiqueta_estado_lineas: str,
    metrica_lineas: str,
    nodo_pcc: int,
    ramas: list[tuple[int, int]],
) -> None:
    """Alias publico en espanol para compatibilidad."""
    plot_ieee33_results(
        output_dir=output_dir,
        v_base=v_base,
        v_mg=v_mg,
        datos=datos,
        p_ss_kw=p_ss_kw,
        estado_lineas_base=estado_lineas_base,
        estado_lineas_mg=estado_lineas_mg,
        etiqueta_estado_lineas=etiqueta_estado_lineas,
        metrica_lineas=metrica_lineas,
        nodo_pcc=nodo_pcc,
        ramas=ramas,
    )

