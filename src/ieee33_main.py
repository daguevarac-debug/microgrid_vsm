"""Entry point for sequential one-way IEEE 33 + microgrid coupling."""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from ieee33_coupling import IEEE33MicrogridBaseline, IEEE33MicrogridWithBESS
from ieee33_reporting import select_line_metric


def main() -> None:
    """Run the IEEE 33 one-way study with baseline or active GFM+BESS."""
    parser = argparse.ArgumentParser(
        description="Run sequential one-way IEEE 33 + local microgrid coupling."
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help=(
            "Use the historical grid-following PV + DC-link + LCL baseline "
            "without BESS."
        ),
    )
    args = parser.parse_args()

    ruta_txt = str(Path(__file__).resolve().parent / "ieee33bus.txt")
    if args.baseline:
        sistema = IEEE33MicrogridBaseline(ruta_txt)
        print("Modo IEEE 33: baseline grid-following, sin BESS.")
    else:
        sistema = IEEE33MicrogridWithBESS(ruta_txt)
        print("Modo IEEE 33: PV + DC-link + LCL + BESS con GFM activo.")
        print(
            "Alcance: acople secuencial one-way y flujo de potencia estatico; "
            "no es co-simulacion dinamica."
        )

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
        res_line_base=res_line_base,
        res_line_mg=res_line_mg,
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
