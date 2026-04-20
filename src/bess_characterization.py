"""LEGACY SHIM - do not use in new code.

Backward-compatible shim redirected to ``bess.characterization``.
"""

from bess.characterization import load_ocv_r1c1_from_excel  # noqa: F401

__all__ = ["load_ocv_r1c1_from_excel"]

