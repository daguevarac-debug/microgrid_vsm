"""Validate diagnostic BESS-DC-link power exchange signal.

Scope:
- Check p_bess_dc = Vdc * i_bess for the preliminary DC-link coupling.
- Check sign coherence with the existing BESS current convention.
- Do not change parameters, controllers, or physical equations.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from microgrid import MicrogridWithBESS


TOL = 1e-9


def _check_case(model: MicrogridWithBESS, name: str, vdc0: float) -> tuple[bool, str]:
    x0 = model.initial_state_with_bess(vdc0=vdc0)
    sig = model.integrated_signals(0.0, x0)

    vdc = float(sig["Vdc"])
    i_bess = float(sig["i_bess"])
    p_bess_dc = float(sig["p_bess_dc"])
    expected = vdc * i_bess

    finite_ok = np.all(np.isfinite([vdc, i_bess, p_bess_dc]))
    identity_ok = abs(p_bess_dc - expected) <= TOL * max(1.0, abs(expected))
    sign_ok = True
    if i_bess > 0.0:
        sign_ok = p_bess_dc > 0.0
    elif i_bess < 0.0:
        sign_ok = p_bess_dc < 0.0

    passed = bool(finite_ok and identity_ok and sign_ok)
    details = (
        f"{name}: Vdc={vdc:.6f} V, i_bess={i_bess:.6f} A, "
        f"p_bess_dc={p_bess_dc:.6f} W, expected={expected:.6f} W, "
        f"finite_ok={finite_ok}, identity_ok={identity_ok}, sign_ok={sign_ok}"
    )
    return passed, details


def main() -> None:
    model = MicrogridWithBESS()
    cases = [
        ("discharge_to_dc_bus", model.vdc_ref - 1.0),
        ("charge_from_dc_bus", model.vdc_ref + 1.0),
    ]
    results = [_check_case(model, name, vdc0) for name, vdc0 in cases]

    passed = all(result[0] for result in results)
    print("PASS" if passed else "REVIEW")
    for _, details in results:
        print(details)


if __name__ == "__main__":
    main()
