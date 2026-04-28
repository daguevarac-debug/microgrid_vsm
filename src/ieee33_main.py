"""Entry point for one-way sequential IEEE 33 + microgrid coupling."""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from ieee33_coupling import IEEE33MicrogridBaseline, IEEE33MicrogridWithBESS
from ieee33_reporting import select_line_metric


def main() -> None:
    """Run full one-way sequential IEEE 33 study and figures."""
    parser = argparse.ArgumentParser(
        description="Run one-way sequential IEEE 33 + local microgrid coupling."
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Use the historical PV + DC-link + LCL baseline without preliminary BESS coupling.",
    )
    args = parser.parse_args()

    ruta_txt = str(Path(__file__).resolve().parent / "ieee33bus.txt")
    if args.baseline:
        sistema = IEEE33MicrogridBaseline(ruta_txt)
        print("Modo IEEE 33: PV + DC-link + LCL baseline, sin BESS.")
    else:
        sistema = IEEE33MicrogridWithBESS(ruta_txt)
        print("Modo IEEE 33: PV + DC-link + LCL + BESS preliminar.")
        print("Alcance: acople secuencial one-way; NO es GFM/VSG integrado.")

    p_ss_kw, datos = sistema.simular()
    v_base, res_line_base = sistema.flujo_base()
    v_mg, res_line_mg = sistema.flujo_con_dg(p_ss_kw)

    estado_lineas_base, estado_lineas_mg, etiqueta_estado_lineas, metrica_lineas = select_line_metric(
        res_line_base,
        res_line_mg,
    )
    sistema.reportar(
        v_base=v_base,
        v_mg=v_mg,
        p_ss_kw=p_ss_kw,
        estado_lineas_base=estado_lineas_base,
        estado_lineas_mg=estado_lineas_mg,
        etiqueta_estado_lineas=etiqueta_estado_lineas,
        metrica_lineas=metrica_lineas,
    )
    try:
        sistema.graficar(
            v_base=v_base,
            v_mg=v_mg,
            datos=datos,
            p_ss_kw=p_ss_kw,
            estado_lineas_base=estado_lineas_base,
            estado_lineas_mg=estado_lineas_mg,
            etiqueta_estado_lineas=etiqueta_estado_lineas,
            metrica_lineas=metrica_lineas,
            nodo_pcc=sistema.pcc_bus_idx + 1,
        )
    except PermissionError as exc:
        print(f"\n  ADVERTENCIA: no se pudieron guardar las figuras IEEE 33: {exc}")


if __name__ == "__main__":
    main()
