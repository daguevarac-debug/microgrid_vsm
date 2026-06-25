"""Generate the final IEEE 33 GFM figure and update the coupling scope note.

This finalizer performs the two closing actions for the IEEE 33 + active-GFM task:

1. regenerate ``ieee33_microgrid_resultado.png`` with the GFM+BESS case in
   ``outputs/validation/figures_final``;
2. update ``docs/model_assumptions.md`` to state explicitly that the IEEE 33
   coupling remains sequential one-way and is not a dynamic co-simulation.

The documentation update is idempotent. Re-running the script does not duplicate
or alter the note once it is present.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


os.environ.setdefault("MPLBACKEND", "Agg")

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController
from ieee33_coupling import IEEE33MicrogridWithBESS
from ieee33_reporting import select_line_metric


FINAL_FIGURE_DIR = REPO_ROOT / "outputs" / "validation" / "figures_final"
FINAL_FIGURE_PATH = FINAL_FIGURE_DIR / "ieee33_microgrid_resultado.png"
MODEL_ASSUMPTIONS_PATH = REPO_ROOT / "docs" / "model_assumptions.md"

OLD_SCOPE_PARAGRAPH = """El PCC usado es el Nodo 18 del IEEE 33 y el nivel de tension de la red se
mantiene en `12.66 kV`. Este caso tampoco representa un acople dinamico
GFM/VSG integrado al IEEE 33; el bloque GFM/VSG permanece como estructura
minima aislada hasta su integracion explicita en una etapa posterior.
"""

NEW_SCOPE_PARAGRAPH = """El PCC usado es el Nodo 18 del IEEE 33 y el nivel de tension de la red se
mantiene en `12.66 kV`. La microrred local opera ahora con `GFMController`
activo; sin embargo, el acople con el IEEE 33 sigue siendo secuencial one-way.
Primero se resuelve la dinamica local, luego se calcula `p_ss_kw` como promedio
de `p_pcc` en la ventana estacionaria y finalmente se ejecuta un flujo de
potencia estatico en pandapower. El IEEE 33 no retroalimenta estados, tensiones
ni potencias durante la integracion temporal de la microrred. Por tanto, este
caso no constituye co-simulacion dinamica ni un acople bidireccional en tiempo
real; corresponde a postprocesamiento estatico de red con una inyeccion
estacionaria equivalente en el PCC.
"""


def update_model_assumptions() -> str:
    """Insert the active-GFM one-way coupling note exactly once."""
    if not MODEL_ASSUMPTIONS_PATH.is_file():
        raise FileNotFoundError(
            f"Model assumptions file not found: {MODEL_ASSUMPTIONS_PATH}"
        )

    content = MODEL_ASSUMPTIONS_PATH.read_text(encoding="utf-8")
    if NEW_SCOPE_PARAGRAPH in content:
        return "ALREADY_PRESENT"
    if OLD_SCOPE_PARAGRAPH not in content:
        raise RuntimeError(
            "Expected IEEE 33 scope paragraph was not found; documentation was "
            "not modified to avoid an unsafe blind edit."
        )

    updated = content.replace(OLD_SCOPE_PARAGRAPH, NEW_SCOPE_PARAGRAPH, 1)
    MODEL_ASSUMPTIONS_PATH.write_text(updated, encoding="utf-8")
    return "UPDATED"


def generate_final_figure() -> dict[str, object]:
    """Run the active-GFM case and write the final IEEE 33 figure."""
    ruta_txt = SRC_DIR / "ieee33bus.txt"
    system = IEEE33MicrogridWithBESS(
        str(ruta_txt),
        output_dir=FINAL_FIGURE_DIR,
    )
    if not isinstance(system.controller, GFMController):
        raise TypeError(
            "Final IEEE 33 figure requires an active GFMController."
        )

    p_ss_kw, data = system.simular()
    v_base, res_line_base = system.flujo_base()
    base_converged = bool(getattr(system.net, "converged", False))
    v_gfm, res_line_gfm = system.flujo_con_dg(p_ss_kw)
    gfm_converged = bool(getattr(system.net, "converged", False))
    if not base_converged or not gfm_converged:
        raise RuntimeError(
            "IEEE 33 power flow did not converge for the base or active-GFM case."
        )

    (
        line_base,
        line_gfm,
        line_label,
        line_key,
    ) = select_line_metric(res_line_base, res_line_gfm)
    system.graficar(
        v_base=v_base,
        v_mg=v_gfm,
        datos=data,
        p_ss_kw=p_ss_kw,
        estado_lineas_base=line_base,
        estado_lineas_mg=line_gfm,
        etiqueta_estado_lineas=line_label,
        metrica_lineas=line_key,
        nodo_pcc=system.pcc_bus_idx + 1,
    )

    if not FINAL_FIGURE_PATH.is_file():
        raise RuntimeError(f"Expected final figure was not created: {FINAL_FIGURE_PATH}")
    figure_size_bytes = int(FINAL_FIGURE_PATH.stat().st_size)
    if figure_size_bytes <= 0:
        raise RuntimeError(f"Final figure is empty: {FINAL_FIGURE_PATH}")

    return {
        "p_ss_kw": float(p_ss_kw),
        "controller_class": type(system.controller).__name__,
        "controller_state_name": system.controller_state_name,
        "base_flow_converged": base_converged,
        "gfm_flow_converged": gfm_converged,
        "figure_path": str(FINAL_FIGURE_PATH),
        "figure_size_bytes": figure_size_bytes,
    }


def main() -> int:
    try:
        figure = generate_final_figure()
        documentation_status = update_model_assumptions()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print("overall_status=FAIL")
        print(f"error={exc}")
        return 1

    print(f"controller_class={figure['controller_class']}")
    print(f"controller_state_name={figure['controller_state_name']}")
    print(f"p_ss_kw={figure['p_ss_kw']:.12f}")
    print(f"base_flow_converged={figure['base_flow_converged']}")
    print(f"gfm_flow_converged={figure['gfm_flow_converged']}")
    print(f"figure_status=PASS")
    print(f"figure_path={figure['figure_path']}")
    print(f"figure_size_bytes={figure['figure_size_bytes']}")
    print(f"documentation_status={documentation_status}")
    print(f"documentation_path={MODEL_ASSUMPTIONS_PATH}")
    print("coupling_scope=sequential_one_way_not_dynamic_cosimulation")
    print("overall_status=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
