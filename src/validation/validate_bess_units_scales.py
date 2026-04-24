"""Validate units and scale coherence for preliminary BESS-DC-link coupling.

Scope:
- Check basic dimensional consistency of diagnostic BESS/DC-link signals.
- Report voltage and power scale ratios for interpretation.
- Do not modify equations, parameters, controllers, or the 1RC BESS model.
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


EPS = 1e-12
IDENTITY_RTOL = 1e-9
VOLTAGE_SCALE_REVIEW_THRESHOLD = 20.0


def main() -> None:
    model = MicrogridWithBESS()
    x0 = model.initial_state_with_bess()
    sig = model.integrated_signals(0.0, x0)

    vdc = float(sig["Vdc"])
    i_bess = float(sig["i_bess"])
    p_bess_dc = float(sig["p_bess_dc"])
    soc_bess = float(sig["soc_bess"])
    vt_bess = float(sig["vt_bess"])
    soh_bess = float(sig["soh_bess"])

    zdeg_bess = float(x0[14])
    q_eff = float(model.bess.effective_capacity_from_z_deg(zdeg_bess))
    r0 = float(model.bess.r0_from_z_deg(zdeg_bess))
    r1 = float(model.bess.r1(soc_bess))
    c1 = float(model.bess.c1(soc_bess))

    expected_p_bess_dc = vdc * i_bess
    p_bess_terminal_same_current = vt_bess * i_bess
    voltage_scale_ratio = vdc / vt_bess if vt_bess != 0.0 else float("inf")
    power_scale_ratio = abs(p_bess_dc) / max(abs(p_bess_terminal_same_current), EPS)

    values = [
        vdc,
        i_bess,
        p_bess_dc,
        soc_bess,
        vt_bess,
        soh_bess,
        q_eff,
        r0,
        r1,
        c1,
        voltage_scale_ratio,
        p_bess_terminal_same_current,
        power_scale_ratio,
    ]
    finite_ok = bool(np.all(np.isfinite(values)))
    positive_scale_ok = bool(vdc > 0.0 and vt_bess > 0.0 and q_eff > 0.0 and r0 > 0.0 and r1 > 0.0 and c1 > 0.0)
    fraction_ok = bool(0.0 <= soc_bess <= 1.0 and 0.0 <= soh_bess <= 1.0)
    identity_ok = bool(
        abs(p_bess_dc - expected_p_bess_dc)
        <= IDENTITY_RTOL * max(1.0, abs(expected_p_bess_dc))
    )
    sign_ok = True
    if i_bess > 0.0:
        sign_ok = p_bess_dc > 0.0
    elif i_bess < 0.0:
        sign_ok = p_bess_dc < 0.0

    hard_fail = not (finite_ok and positive_scale_ok and fraction_ok and identity_ok and sign_ok)
    scale_review = voltage_scale_ratio > VOLTAGE_SCALE_REVIEW_THRESHOLD

    if hard_fail:
        status = "FAIL"
        observation = (
            "Fallo de coherencia basica: revisar finitud, rangos fisicos, "
            "identidad p_bess_dc=Vdc*i_bess o convencion de signos."
        )
    elif scale_review:
        status = "REVIEW"
        observation = (
            "Unidades basicas, signos e identidad consistentes; Vdc/vt_bess es alto. "
            "Advertencia de interpretacion fisica: aun falta representar explicitamente "
            "el convertidor DC/DC ideal o el escalamiento del banco completo."
        )
    else:
        status = "PASS"
        observation = "Unidades basicas, signos, escalas e identidad diagnostica consistentes."

    print(f"status={status}")
    print(f"Vdc={vdc:.6f} V")
    print(f"vt_bess={vt_bess:.6f} V")
    print(f"i_bess={i_bess:.6f} A")
    print(f"p_bess_dc={p_bess_dc:.6f} W")
    print(f"soc_bess={soc_bess:.6f}")
    print(f"soh_bess={soh_bess:.6f}")
    print(f"Q_eff={q_eff:.6f} Ah")
    print(f"R0={r0:.6f} ohm")
    print(f"R1={r1:.6f} ohm")
    print(f"C1={c1:.6f} F")
    print(f"voltage_scale_ratio={voltage_scale_ratio:.6f}")
    print(f"p_bess_terminal_same_current={p_bess_terminal_same_current:.6f} W")
    print(f"power_scale_ratio={power_scale_ratio:.6f}")
    print(
        "checks="
        f"finite_ok={finite_ok}, positive_scale_ok={positive_scale_ok}, "
        f"fraction_ok={fraction_ok}, identity_ok={identity_ok}, sign_ok={sign_ok}"
    )
    print(f"observation={observation}")


if __name__ == "__main__":
    main()
