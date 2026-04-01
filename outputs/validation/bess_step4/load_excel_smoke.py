from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bess_second_life import SecondLifeBattery1RC

EXCEL_PATH = Path(__file__).resolve().parents[3] / "OCV_SOC.xlsx"
Q_NOM = 66.0  # Ah - capacidad nominal de referencia del par 2p Nissan Leaf
SOH_INITIAL = 44.1 / 66.0  # segunda vida: capacidad disponible inicial segun Braco

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
