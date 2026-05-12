# -*- coding: utf-8 -*-
"""Generate the general methodology flow diagram for Objective 1."""

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon


OUTPUT_DIR = Path("outputs") / "figures"
PNG_PATH = OUTPUT_DIR / "metodologia_flujo_general.png"
SVG_PATH = OUTPUT_DIR / "metodologia_flujo_general.svg"

MAIN_X = 50.0
BOX_WIDTH = 56.0
BOX_HEIGHT = 5.2
START_HEIGHT = 4.6
DIAMOND_WIDTH = 48.0
DIAMOND_HEIGHT = 7.2

PROCESS_STEPS = [
    (
        "Inicio",
        "",
        "start",
    ),
    (
        "Datos de entrada",
        "Datasheet FV LONGi LR7-54HJD-500M; parámetros nominales; parámetros BESS-SLB y restricciones",
        "process",
    ),
    (
        "Parametrización y ajuste del modelo",
        "Generador FV con modelo de un diodo y ajuste en condiciones STC",
        "process",
    ),
    (
        "Formulación del modelo dinámico local",
        "FV, bus DC, inversor, filtro LCL, carga y BESS-SLB",
        "process",
    ),
    (
        "Integración del sistema",
        "PV-DC-link-inversor-LCL-carga-BESS",
        "process",
    ),
    (
        "Simulación dinámica local",
        "Condición nominal, perturbaciones y escenarios de comparación",
        "process",
    ),
    (
        "Validación interna por simulación",
        "STC, respuesta dinámica, balance DC, restricciones BESS y sensibilidad",
        "process",
    ),
    (
        "¿El modelo cumple criterios\nde coherencia y validación?",
        "",
        "decision",
    ),
    (
        "Extracción de potencia media en el PCC",
        "",
        "process",
    ),
    (
        "Acople con red de referencia",
        "IEEE 33 nodos o red real de caso de uso",
        "process",
    ),
    (
        "Flujo de carga comparativo",
        "Sin microrred vs. con microrred",
        "process",
    ),
    (
        "Postproceso",
        "Tensiones, pérdidas, nodos críticos y cargabilidad",
        "process",
    ),
    (
        "Análisis comparativo y cierre del Objetivo 1",
        "",
        "process",
    ),
]


def wrap_text(text: str, width: int = 44) -> str:
    if not text:
        return ""
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def draw_process_box(ax, center_x: float, center_y: float, title: str, detail: str) -> None:
    x0 = center_x - BOX_WIDTH / 2
    y0 = center_y - BOX_HEIGHT / 2
    box = FancyBboxPatch(
        (x0, y0),
        BOX_WIDTH,
        BOX_HEIGHT,
        boxstyle="round,pad=0.25,rounding_size=0.8",
        linewidth=1.25,
        edgecolor="#2F3A4A",
        facecolor="#F8FAFC",
    )
    ax.add_patch(box)

    if detail:
        ax.text(
            center_x,
            center_y + 0.95,
            wrap_text(title, width=38),
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="#1F2937",
        )
        ax.text(
            center_x,
            center_y - 1.15,
            wrap_text(detail),
            ha="center",
            va="center",
            fontsize=8.8,
            color="#374151",
            linespacing=1.05,
        )
    else:
        ax.text(
            center_x,
            center_y,
            wrap_text(title, width=40),
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="#1F2937",
        )


def draw_start(ax, center_x: float, center_y: float, title: str) -> None:
    start = Ellipse(
        (center_x, center_y),
        width=26.0,
        height=START_HEIGHT,
        linewidth=1.25,
        edgecolor="#2F3A4A",
        facecolor="#FFFFFF",
    )
    ax.add_patch(start)
    ax.text(
        center_x,
        center_y,
        title,
        ha="center",
        va="center",
        fontsize=10.8,
        fontweight="bold",
        color="#1F2937",
    )


def draw_decision(ax, center_x: float, center_y: float, title: str) -> None:
    points = [
        (center_x, center_y + DIAMOND_HEIGHT / 2),
        (center_x + DIAMOND_WIDTH / 2, center_y),
        (center_x, center_y - DIAMOND_HEIGHT / 2),
        (center_x - DIAMOND_WIDTH / 2, center_y),
    ]
    diamond = Polygon(
        points,
        closed=True,
        linewidth=1.25,
        edgecolor="#2F3A4A",
        facecolor="#EEF2F7",
    )
    ax.add_patch(diamond)
    ax.text(
        center_x,
        center_y,
        title,
        ha="center",
        va="center",
        fontsize=9.4,
        fontweight="bold",
        color="#1F2937",
        linespacing=1.05,
    )


def draw_down_arrow(ax, top_center_y: float, bottom_center_y: float) -> None:
    start = (MAIN_X, top_center_y - BOX_HEIGHT / 2 - 0.25)
    end = (MAIN_X, bottom_center_y + BOX_HEIGHT / 2 + 0.25)
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=1.25,
        color="#455A64",
    )
    ax.add_patch(arrow)


def draw_arrow_between(ax, start_y: float, end_y: float, start_kind: str, end_kind: str) -> None:
    start_half = DIAMOND_HEIGHT / 2 if start_kind == "decision" else BOX_HEIGHT / 2
    if start_kind == "start":
        start_half = START_HEIGHT / 2
    end_half = DIAMOND_HEIGHT / 2 if end_kind == "decision" else BOX_HEIGHT / 2
    draw_down_arrow(ax, start_y - start_half + BOX_HEIGHT / 2, end_y + end_half - BOX_HEIGHT / 2)


def draw_return_branch(ax, decision_y: float, target_y: float) -> None:
    right_x = MAIN_X + DIAMOND_WIDTH / 2
    return_x = 86.0
    target_top_y = target_y + BOX_HEIGHT / 2

    branch = FancyArrowPatch(
        (right_x, decision_y),
        (return_x, decision_y),
        connectionstyle="angle3,angleA=0,angleB=-90",
        arrowstyle="-",
        linewidth=1.2,
        color="#455A64",
    )
    ax.add_patch(branch)
    branch = FancyArrowPatch(
        (return_x, decision_y),
        (return_x, target_top_y + 0.8),
        arrowstyle="-",
        linewidth=1.2,
        color="#455A64",
    )
    ax.add_patch(branch)
    branch = FancyArrowPatch(
        (return_x, target_top_y + 0.8),
        (MAIN_X + BOX_WIDTH / 2 + 0.25, target_top_y),
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=1.2,
        color="#455A64",
    )
    ax.add_patch(branch)

    ax.text(
        return_x + 1.4,
        decision_y + 0.75,
        "No",
        ha="left",
        va="bottom",
        fontsize=9.2,
        fontweight="bold",
        color="#1F2937",
    )
    ax.text(
        return_x + 1.4,
        (decision_y + target_top_y) / 2,
        "revisar\nparámetros",
        ha="left",
        va="center",
        fontsize=8.3,
        color="#374151",
        linespacing=1.0,
    )


def generate_figure() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.5, 15))
    ax.set_xlim(0, 100)
    ax.set_ylim(-2, 100)
    ax.axis("off")

    y_positions = [96, 88.2, 80.4, 72.6, 64.8, 57.0, 49.2, 40.6, 32.2, 24.6, 17.0, 9.4, 1.8]

    for (title, detail, kind), y in zip(PROCESS_STEPS, y_positions):
        if kind == "start":
            draw_start(ax, MAIN_X, y, title)
        elif kind == "decision":
            draw_decision(ax, MAIN_X, y, title)
        else:
            draw_process_box(ax, MAIN_X, y, title, detail)

    for idx in range(len(PROCESS_STEPS) - 1):
        _, _, start_kind = PROCESS_STEPS[idx]
        _, _, end_kind = PROCESS_STEPS[idx + 1]
        start_y = y_positions[idx]
        end_y = y_positions[idx + 1]

        start_half = START_HEIGHT / 2 if start_kind == "start" else BOX_HEIGHT / 2
        if start_kind == "decision":
            start_half = DIAMOND_HEIGHT / 2
        end_half = DIAMOND_HEIGHT / 2 if end_kind == "decision" else BOX_HEIGHT / 2

        arrow = FancyArrowPatch(
            (MAIN_X, start_y - start_half - 0.35),
            (MAIN_X, end_y + end_half + 0.35),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.25,
            color="#455A64",
        )
        ax.add_patch(arrow)

    decision_y = y_positions[7]
    target_y = y_positions[2]
    draw_return_branch(ax, decision_y, target_y)
    ax.text(
        MAIN_X + 2.1,
        decision_y - DIAMOND_HEIGHT / 2 - 1.4,
        "Sí",
        ha="left",
        va="top",
        fontsize=9.2,
        fontweight="bold",
        color="#1F2937",
    )

    fig.subplots_adjust(left=0.03, right=0.97, top=0.985, bottom=0.02)
    fig.savefig(PNG_PATH, dpi=300, bbox_inches="tight")
    fig.savefig(SVG_PATH, bbox_inches="tight")
    plt.close(fig)

    print(f"Figura guardada: {PNG_PATH.as_posix()}")
    print(f"Figura guardada: {SVG_PATH.as_posix()}")


if __name__ == "__main__":
    generate_figure()
