"""Backward-compatible shim — imports redirected to bess.characterization.

This file exists so that existing scripts using
``from bess_characterization import load_ocv_r1c1_from_excel`` continue to work.
New code should import from ``bess.characterization`` directly.
"""

from bess.characterization import load_ocv_r1c1_from_excel  # noqa: F401

__all__ = ["load_ocv_r1c1_from_excel"]
