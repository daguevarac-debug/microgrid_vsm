"""OCV/R1/C1 lookup table dataclass for 1RC Thevenin ECM parameters vs SoC.

Traceability: Tran et al. (2021) style parameter mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from bess.validators import _ensure_real_array


@dataclass(frozen=True)
class OCVR1C1LookupTable:
    """Lookup tables for 1RC parameters vs SoC (Tran, 2021 style source).

    Arrays are placeholders and must be replaced with identified data before
    reporting scientific results.
    """

    soc_data: Sequence[float]
    ocv_data: Sequence[float]
    r1_data: Sequence[float]
    c1_data: Sequence[float]
    source_reference: str = "Tran et al. (2021)"

    def __post_init__(self) -> None:
        soc = _ensure_real_array("soc_data", self.soc_data)
        ocv = _ensure_real_array("ocv_data", self.ocv_data)
        r1 = _ensure_real_array("r1_data", self.r1_data)
        c1 = _ensure_real_array("c1_data", self.c1_data)

        n = soc.size
        if ocv.size != n or r1.size != n or c1.size != n:
            raise ValueError(
                "ocv_data, r1_data and c1_data must match soc_data length "
                f"({n}), got ocv={ocv.size}, r1={r1.size}, c1={c1.size}."
            )

        if np.any(np.diff(soc) <= 0.0):
            raise ValueError("soc_data must be strictly increasing (monotonic).")
        if soc[0] < 0.0 or soc[-1] > 1.0:
            raise ValueError(
                f"soc_data must stay within [0, 1], got min={soc[0]} and max={soc[-1]}."
            )

        if np.any(r1 <= 0.0):
            raise ValueError("r1_data must be > 0 for all SoC points.")
        if np.any(c1 <= 0.0):
            raise ValueError("c1_data must be > 0 for all SoC points.")

        object.__setattr__(self, "soc_data", soc)
        object.__setattr__(self, "ocv_data", ocv)
        object.__setattr__(self, "r1_data", r1)
        object.__setattr__(self, "c1_data", c1)


# Placeholder lookup table for integration tests and scaffold wiring only.
# Replace these arrays with identified values from literature/experiments.
DEFAULT_TRAN_LOOKUP_TABLE = OCVR1C1LookupTable(
    soc_data=[0.0, 0.25, 0.5, 0.75, 1.0],
    ocv_data=[3.0, 3.2, 3.4, 3.6, 3.8],
    r1_data=[0.02, 0.018, 0.016, 0.017, 0.019],
    c1_data=[1800.0, 2200.0, 2600.0, 2300.0, 2000.0],
)
