"""LEGACY SHIM - do not use in new code.

Backward-compatible shim redirected to the ``bess`` package.
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

