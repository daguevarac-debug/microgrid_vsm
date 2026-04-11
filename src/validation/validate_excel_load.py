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
from bess.capacity import Q_NOM_REF_NISSAN_LEAF_2P_AH

REPO_ROOT = SRC_DIR.parent
EXCEL_PATH = REPO_ROOT / "OCV_SOC.xlsx"
# Braco (2020, 2021): nominal reference for Nissan Leaf 2p.
Q_NOM_REF_AH = Q_NOM_REF_NISSAN_LEAF_2P_AH
# Case-specific initial available capacity (example case only).
Q_INIT_CASE_AH = 44.1


def main() -> int:
    model = SecondLifeBattery1RC.from_excel_characterization(
        excel_path=EXCEL_PATH,
        q_nom_ref_ah=Q_NOM_REF_AH,
        q_init_case_ah=Q_INIT_CASE_AH,
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
