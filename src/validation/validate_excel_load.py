"""Validate Excel characterization loading for BESS 1RC model.

Scope:
- Verify that OCV/R1/C1 data loads correctly from OCV_SOC.xlsx.
- Verify lookup interpolation works at expected SoC points.
- Print summary for quick smoke-test verification.
"""

from pathlib import Path
import sys

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess.model import SecondLifeBattery1RC

REPO_ROOT = SRC_DIR.parent
EXCEL_PATH = REPO_ROOT / "OCV_SOC.xlsx"
Q_NOM = 66.0  # Ah - capacidad nominal de referencia del par 2p Nissan Leaf
SOH_INITIAL = 44.1 / 66.0  # segunda vida: capacidad disponible inicial segun Braco


def main() -> int:
    model = SecondLifeBattery1RC.from_excel_characterization(
        excel_path=EXCEL_PATH,
        q_nom_ah=Q_NOM,
        soh_initial=SOH_INITIAL,
        r0_nominal_ohm=0.000970,
    )

    print("Excel cargado correctamente.")
    print(f"  Puntos OCV-SoC: {len(model.lookup_table_1rc.soc_data)}")
    print(f"  OCV a SoC=0.50: {model.ocv(0.50):.4f} V")
    print(f"  R1 a SoC=0.50:  {model.r1(0.50):.6f} Ohm")
    print(f"  C1 a SoC=0.50:  {model.c1(0.50):.1f} F")
    print(f"  Q_eff inicial:  {model.effective_capacity_from_z_deg(0.0):.2f} Ah")
    print(f"  R0 inicial:     {model.r0_from_z_deg(0.0):.6f} Ohm")

    # Basic assertions
    assert len(model.lookup_table_1rc.soc_data) >= 2, "Must have at least 2 SoC points."
    assert model.ocv(0.50) > 0.0, "OCV must be positive."
    assert model.r1(0.50) > 0.0, "R1 must be positive."
    assert model.c1(0.50) > 0.0, "C1 must be positive."

    print("\nOverall status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
