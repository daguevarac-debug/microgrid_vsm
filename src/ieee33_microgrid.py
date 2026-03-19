"""Compatibility facade for one-way sequential IEEE 33 + microgrid coupling."""

from pathlib import Path

from networks.ieee33_coupling import IEEE33Microgrid, IEEE33MicrogridBaseline
from plots.ieee33_plots import graficar_topologia_ieee33, ieee33_manual_coordinates
from simulation.ieee33_reporting import extraer_metrica_lineas


def _coordenadas_ieee33_manual() -> dict[int, tuple[float, float]]:
    """Alias de compatibilidad para nombre previo."""
    return ieee33_manual_coordinates()


def main() -> None:
    """Run full one-way sequential baseline study and figures."""
    ruta_txt = str(Path(__file__).resolve().parent / "ieee33bus.txt")
    sistema = IEEE33MicrogridBaseline(ruta_txt)

    p_ss_kw, datos = sistema.simular()
    v_base, res_line_base = sistema.flujo_base()
    v_mg, res_line_mg = sistema.flujo_con_dg(p_ss_kw)

    estado_lineas_base, estado_lineas_mg, etiqueta_estado_lineas, metrica_lineas = extraer_metrica_lineas(
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


if __name__ == "__main__":
    main()

