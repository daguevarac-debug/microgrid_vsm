"""IEEE 33-bus static network builder and standalone load-flow runner."""

import os

import matplotlib.pyplot as plt
import pandapower as pp
import pandas as pd
from config import IEEE33_VN_KV


def construir_red_ieee33(ruta_txt: str) -> pp.pandapowerNet:
    """Construye la red IEEE 33 en pandapower sin ejecutar flujo de carga."""
    nombres_columnas = ["from", "to", "P", "Q", "rohm", "xohm", "maxi"]
    df = pd.read_csv(ruta_txt, sep=" ", header=None, names=nombres_columnas)

    net = pp.create_empty_network()

    for i in range(33):
        pp.create_bus(net, vn_kv=IEEE33_VN_KV, name=f"Nodo {i+1}")

    pp.create_ext_grid(net, bus=0, vm_pu=1.0, name="Red Principal")

    for _, row in df.iterrows():
        from_bus = int(row["from"]) - 1
        to_bus = int(row["to"]) - 1

        pp.create_load(net, bus=to_bus, p_mw=row["P"] / 1000.0, q_mvar=row["Q"] / 1000.0)

        pp.create_line_from_parameters(
            net,
            from_bus=from_bus,
            to_bus=to_bus,
            length_km=1.0,
            r_ohm_per_km=row["rohm"],
            x_ohm_per_km=row["xohm"],
            c_nf_per_km=0,
            max_i_ka=row["maxi"] / 1000.0,
        )

    return net


if __name__ == "__main__":
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_txt = os.path.join(directorio_actual, "ieee33bus.txt")

    net = construir_red_ieee33(ruta_txt)
    pp.runpp(net)

    nodo_peor_voltaje = net.res_bus.vm_pu.idxmin() + 1
    voltaje_minimo = net.res_bus.vm_pu.min()

    print("\n--- RESULTADOS DEL FLUJO DE CARGA ---")
    print(f"El nodo con el peor voltaje es el Nodo {nodo_peor_voltaje}")
    print(f"Voltaje en ese nodo: {voltaje_minimo:.4f} p.u.")

    plt.figure(figsize=(10, 5))
    plt.plot(net.res_bus.index + 1, net.res_bus.vm_pu, marker="o", linestyle="-", color="b")
    plt.axhline(y=0.95, color="r", linestyle="--", label="Limite inferior permitido (0.95 p.u.)")
    plt.title("Perfil de Voltaje - IEEE 33 Nodos (Sin Microrred)")
    plt.xlabel("Numero de Nodo")
    plt.ylabel("Voltaje (p.u.)")
    plt.xticks(range(1, 34))
    plt.grid(True)
    plt.legend()
    plt.show()
