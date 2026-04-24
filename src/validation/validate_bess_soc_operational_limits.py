"""Validate conservative SoC operational limits for integrated BESS support.

Scope:
- Check MicrogridWithBESS uses the configured operational SoC window.
- Check discharge and charge blocking at the lower/upper SoC limits.
- Do not modify equations, controllers, sign conventions, or BESS 1RC physics.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    BESS_COUPLED_SOC_INIT_DEFAULT,
    BESS_COUPLED_SOC_MAX_DEFAULT,
    BESS_COUPLED_SOC_MIN_DEFAULT,
)
from microgrid import MicrogridWithBESS


TOL = 1e-12


def main() -> None:
    model = MicrogridWithBESS()
    soc_min = float(model.bess.soc_min)
    soc_max = float(model.bess.soc_max)
    soc_initial = float(model.bess.soc_initial)
    soc_mid = 0.5 * (soc_min + soc_max)

    vdc_low = model.vdc_ref - 1.0
    vdc_high = model.vdc_ref + 1.0

    i_discharge_blocked = model._compute_i_bess(Vdc=vdc_low, soc_bess=soc_min)
    i_charge_blocked = model._compute_i_bess(Vdc=vdc_high, soc_bess=soc_max)
    i_discharge_mid = model._compute_i_bess(Vdc=vdc_low, soc_bess=soc_mid)
    i_charge_mid = model._compute_i_bess(Vdc=vdc_high, soc_bess=soc_mid)

    limits_ok = bool(
        np.isclose(soc_min, BESS_COUPLED_SOC_MIN_DEFAULT, rtol=0.0, atol=TOL)
        and np.isclose(soc_max, BESS_COUPLED_SOC_MAX_DEFAULT, rtol=0.0, atol=TOL)
    )
    initial_ok = bool(
        np.isclose(soc_initial, BESS_COUPLED_SOC_INIT_DEFAULT, rtol=0.0, atol=TOL)
        and soc_min <= soc_initial <= soc_max
    )
    discharge_block_ok = bool(np.isclose(i_discharge_blocked, 0.0, rtol=0.0, atol=TOL))
    charge_block_ok = bool(np.isclose(i_charge_blocked, 0.0, rtol=0.0, atol=TOL))
    mid_discharge_ok = bool(i_discharge_mid > 0.0)
    mid_charge_ok = bool(i_charge_mid < 0.0)
    finite_ok = bool(
        np.all(
            np.isfinite(
                [
                    soc_min,
                    soc_max,
                    soc_initial,
                    i_discharge_blocked,
                    i_charge_blocked,
                    i_discharge_mid,
                    i_charge_mid,
                ]
            )
        )
    )

    checks_ok = bool(
        finite_ok
        and limits_ok
        and initial_ok
        and discharge_block_ok
        and charge_block_ok
        and mid_discharge_ok
        and mid_charge_ok
    )
    status = "PASS" if checks_ok else "FAIL"
    observation = (
        "Limites operativos de SoC aplicados de forma conservadora."
        if checks_ok
        else "Revisar configuracion de limites de SoC o bloqueo de i_bess."
    )

    print(f"status={status}")
    print(f"soc_min={soc_min:.6f}")
    print(f"soc_max={soc_max:.6f}")
    print(f"soc_initial={soc_initial:.6f}")
    print(f"i_discharge_blocked_at_soc_min={i_discharge_blocked:.12f} A")
    print(f"i_charge_blocked_at_soc_max={i_charge_blocked:.12f} A")
    print(f"i_discharge_mid_soc={i_discharge_mid:.12f} A")
    print(f"i_charge_mid_soc={i_charge_mid:.12f} A")
    print(
        "checks="
        f"finite_ok={finite_ok}, limits_ok={limits_ok}, initial_ok={initial_ok}, "
        f"discharge_block_ok={discharge_block_ok}, charge_block_ok={charge_block_ok}, "
        f"mid_discharge_ok={mid_discharge_ok}, mid_charge_ok={mid_charge_ok}"
    )
    print(f"observation={observation}")


if __name__ == "__main__":
    main()
