"""Validate IEEE 33 PCC consistency without running dynamic simulation."""

from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import IEEE33_PCC_BUS_IDX, IEEE33_PCC_BUS_NAME, IEEE33_VN_KV
from ieee33_base import construir_red_ieee33
from ieee33_coupling import IEEE33MicrogridWithBESS


def _check(label: str, condition: bool, detail: str) -> bool:
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label}: {detail}")
    return condition


def main() -> int:
    repo_root = SRC_DIR.parent
    ruta_txt = SRC_DIR / "ieee33bus.txt"
    net = construir_red_ieee33(str(ruta_txt))
    sistema = IEEE33MicrogridWithBESS(str(ruta_txt), output_dir=repo_root / "outputs")

    pcc_bus_idx = IEEE33_PCC_BUS_IDX
    pcc_bus_number = pcc_bus_idx + 1
    pcc_bus_name = str(net.bus.loc[pcc_bus_idx, "name"]) if pcc_bus_idx in net.bus.index else "<missing>"
    vn_kv = float(net.bus.loc[pcc_bus_idx, "vn_kv"]) if pcc_bus_idx in net.bus.index else float("nan")

    checks = [
        _check("IEEE33_PCC_BUS_IDX", IEEE33_PCC_BUS_IDX == 17, str(IEEE33_PCC_BUS_IDX)),
        _check("IEEE33_PCC_BUS_NAME", IEEE33_PCC_BUS_NAME == "Nodo 18", IEEE33_PCC_BUS_NAME),
        _check("PCC index exists in net.bus", pcc_bus_idx in net.bus.index, str(pcc_bus_idx)),
        _check("net.bus PCC name", pcc_bus_name == "Nodo 18", pcc_bus_name),
        _check("net.bus PCC vn_kv", vn_kv == IEEE33_VN_KV, f"{vn_kv:.2f} kV"),
        _check("IEEE33_VN_KV", IEEE33_VN_KV == 12.66, f"{IEEE33_VN_KV:.2f} kV"),
        _check("reported PCC bus number", pcc_bus_number == 18, str(pcc_bus_number)),
        _check(
            "IEEE33MicrogridWithBESS pcc_bus_idx",
            sistema.pcc_bus_idx == IEEE33_PCC_BUS_IDX,
            str(sistema.pcc_bus_idx),
        ),
    ]

    print("\nIEEE 33 PCC consistency")
    print(f"  pcc_bus_idx    : {pcc_bus_idx}")
    print(f"  pcc_bus_number : {pcc_bus_number}")
    print(f"  pcc_bus_name   : {pcc_bus_name}")
    print(f"  vn_kv          : {vn_kv:.2f}")

    if all(checks):
        print("  status         : PASS")
        return 0

    print("  status         : FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
