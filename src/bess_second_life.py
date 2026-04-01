"""Backward-compatible shim — imports redirected to bess/ package.

This file exists so that existing scripts using
``from bess_second_life import SecondLifeBattery1RC`` continue to work.
New code should import from ``bess`` directly.
"""

# Re-export everything that was originally in this module.
from bess import (  # noqa: F401
    _ensure_finite,
    _ensure_positive,
    _ensure_fraction,
    _ensure_real_array,
    OCVR1C1LookupTable,
    DEFAULT_TRAN_LOOKUP_TABLE,
    SecondLifeBatteryPhase1,
    ECMSeedParameters,
    SecondLifeBattery1RC,
)
