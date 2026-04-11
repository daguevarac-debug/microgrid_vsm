"""BESS second-life battery package for microgrid thesis.

Public API re-exports for convenience and backward compatibility.
"""

from bess.validators import (
    _ensure_finite,
    _ensure_positive,
    _ensure_fraction,
    _ensure_real_array,
)
from bess.lookup_table import OCVR1C1LookupTable, DEFAULT_TRAN_LOOKUP_TABLE
from bess.capacity import (
    Q_NOM_REF_NISSAN_LEAF_2P_AH,
    derive_soh_init_case,
    derive_q_init_case_ah,
)
from bess.phase1 import SecondLifeBatteryPhase1, ECMSeedParameters
from bess.model import SecondLifeBattery1RC
from bess.characterization import load_ocv_r1c1_from_excel

__all__ = [
    # Validators
    "_ensure_finite",
    "_ensure_positive",
    "_ensure_fraction",
    "_ensure_real_array",
    # Lookup table
    "OCVR1C1LookupTable",
    "DEFAULT_TRAN_LOOKUP_TABLE",
    # Capacity convention helpers
    "Q_NOM_REF_NISSAN_LEAF_2P_AH",
    "derive_soh_init_case",
    "derive_q_init_case_ah",
    # Phase 1 static model
    "SecondLifeBatteryPhase1",
    "ECMSeedParameters",
    # 1RC dynamic model
    "SecondLifeBattery1RC",
    # Characterization loader
    "load_ocv_r1c1_from_excel",
]
