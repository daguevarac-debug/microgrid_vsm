"""Capacity conventions for second-life BESS parameterization.

Traceability note:
- Braco (2020, 2021) reports a Nissan Leaf 2p module nominal reference
  capacity of 66 Ah and defines C-rate from that reference.
- Tran (2021) is not the source for 66 Ah; that work uses 20 Ah LFP cells.
"""

from __future__ import annotations

from bess.validators import _ensure_fraction, _ensure_positive

# Braco (2020, 2021): Nissan Leaf 2p module nominal reference capacity.
Q_NOM_REF_NISSAN_LEAF_2P_AH = 66.0


def derive_soh_init_case(q_init_case_ah: float, q_nom_ref_ah: float) -> float:
    """Return case-specific initial SoH from capacities.

    SoH is always derived as:
    - soh_init_case = q_init_case_ah / q_nom_ref_ah
    """
    q_init = _ensure_positive("q_init_case_ah", q_init_case_ah)
    q_nom_ref = _ensure_positive("q_nom_ref_ah", q_nom_ref_ah)
    return _ensure_fraction("soh_init_case", q_init / q_nom_ref)


def derive_q_init_case_ah(soh_init_case: float, q_nom_ref_ah: float) -> float:
    """Return case-specific initial available capacity from SoH and reference."""
    soh = _ensure_fraction("soh_init_case", soh_init_case)
    q_nom_ref = _ensure_positive("q_nom_ref_ah", q_nom_ref_ah)
    return _ensure_positive("q_init_case_ah", q_nom_ref * soh)

