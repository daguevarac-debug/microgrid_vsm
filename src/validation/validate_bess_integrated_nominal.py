"""Validate the nominal integrated PV + DC-link + LCL + BESS baseline case.

Scope:
- Run MicrogridWithBESS with existing simulation defaults.
- Check numerical stability, finite states/signals, physical ranges, and the
  diagnostic BESS-DC-link power identity.
- Do not modify equations, parameters, controllers, or the 1RC BESS model.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from microgrid import MicrogridWithBESS


IDENTITY_RTOL = 1e-9
IDENTITY_ATOL = 1e-9
VOLTAGE_SCALE_REVIEW_THRESHOLD = 20.0


def _signals_over_solution(model: MicrogridWithBESS, t: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    keys = (
        "Vdc",
        "i_bess",
        "p_bess_dc",
        "p_bess_dc_max",
        "soc_bess",
        "vt_bess",
        "soh_bess",
        "p_bridge",
        "p_pcc",
        "p_load",
    )
    signals = {key: np.zeros_like(t, dtype=float) for key in keys}
    for k, tk in enumerate(t):
        sig = model.integrated_signals(float(tk), y[:, k])
        for key in keys:
            signals[key][k] = float(sig[key])
    return signals


def main() -> None:
    model = MicrogridWithBESS()
    t_span = (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT)
    y0 = model.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)

    sol = solve_ivp(
        model.system_dynamics,
        t_span,
        y0,
        max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
        rtol=SIM_SOLVER_RTOL_DEFAULT,
        atol=SIM_SOLVER_ATOL_DEFAULT,
    )

    signals = _signals_over_solution(model, sol.t, sol.y)

    vdc = signals["Vdc"]
    i_bess = signals["i_bess"]
    p_bess_dc = signals["p_bess_dc"]
    p_bess_dc_max = signals["p_bess_dc_max"]
    soc_bess = signals["soc_bess"]
    vt_bess = signals["vt_bess"]
    soh_bess = signals["soh_bess"]
    p_pcc = signals["p_pcc"]
    p_load = signals["p_load"]

    expected_p_bess_dc = vdc * i_bess
    voltage_scale_ratio = vdc / vt_bess
    i_bess_abs_max = float(np.max(np.abs(i_bess)))
    p_bess_abs_max = float(np.max(np.abs(p_bess_dc)))
    soc_min_observed = float(np.min(soc_bess))
    soc_max_observed = float(np.max(soc_bess))
    soh_min_observed = float(np.min(soh_bess))
    soh_max_observed = float(np.max(soh_bess))
    vdc_min = float(np.min(vdc))
    vt_bess_min = float(np.min(vt_bess))

    solver_ok = bool(sol.success)
    states_finite_ok = bool(np.all(np.isfinite(sol.y)))
    signals_finite_ok = bool(all(np.all(np.isfinite(value)) for value in signals.values()))
    vdc_positive_ok = bool(np.all(vdc > 0.0))
    soc_range_ok = bool(np.all((soc_bess >= model.bess.soc_min) & (soc_bess <= model.bess.soc_max)))
    soh_range_ok = bool(np.all((soh_bess >= model.bess.soh_min) & (soh_bess <= 1.0)))
    vt_positive_ok = bool(np.all(vt_bess > 0.0))
    current_limit_ok = bool(np.all(np.abs(i_bess) <= model.i_bess_max + IDENTITY_ATOL))
    power_limit_ok = bool(np.all(np.abs(p_bess_dc) <= model.p_bess_max_w + IDENTITY_ATOL))
    power_limit_signal_ok = bool(
        np.allclose(
            p_bess_dc_max,
            model.p_bess_max_w,
            rtol=IDENTITY_RTOL,
            atol=IDENTITY_ATOL,
        )
    )
    identity_ok = bool(
        np.allclose(
            p_bess_dc,
            expected_p_bess_dc,
            rtol=IDENTITY_RTOL,
            atol=IDENTITY_ATOL,
        )
    )

    hard_checks_ok = bool(
        solver_ok
        and states_finite_ok
        and signals_finite_ok
        and vdc_positive_ok
        and soc_range_ok
        and soh_range_ok
        and vt_positive_ok
        and current_limit_ok
        and power_limit_ok
        and power_limit_signal_ok
        and identity_ok
    )
    scale_review = bool(np.max(voltage_scale_ratio) > VOLTAGE_SCALE_REVIEW_THRESHOLD)

    if not hard_checks_ok:
        status = "FAIL"
        observation = (
            "Fallo del caso nominal integrado: revisar solver, finitud, rangos "
            "operativos o identidad p_bess_dc=Vdc*i_bess."
        )
    elif scale_review:
        status = "REVIEW"
        observation = (
            "La corrida nominal integrada es numericamente estable y coherente; "
            "Vdc/vt_bess es alto. Esto limita la interpretacion fisica hasta "
            "modelar explicitamente el DC/DC ideal o el escalamiento del banco."
        )
    else:
        status = "PASS"
        observation = "Caso nominal integrado estable y fisicamente coherente para el baseline actual."

    print(f"status={status}")
    print(f"solver_success={sol.success}")
    print(f"solver_message={sol.message}")
    print(f"n_steps={sol.t.size}")
    print(f"t_final={float(sol.t[-1]):.6f} s")
    print(f"vdc_min={vdc_min:.6f} V")
    print(f"vdc_max={float(np.max(vdc)):.6f} V")
    print(f"vdc_final={float(vdc[-1]):.6f} V")
    print(f"soc_initial={float(soc_bess[0]):.6f}")
    print(f"soc_final={float(soc_bess[-1]):.6f}")
    print(f"soc_min_observed={soc_min_observed:.6f}")
    print(f"soc_max_observed={soc_max_observed:.6f}")
    print(f"soh_initial={float(soh_bess[0]):.6f}")
    print(f"soh_final={float(soh_bess[-1]):.6f}")
    print(f"soh_min_observed={soh_min_observed:.6f}")
    print(f"soh_max_observed={soh_max_observed:.6f}")
    print(f"i_bess_min={float(np.min(i_bess)):.6f} A")
    print(f"i_bess_max={float(np.max(i_bess)):.6f} A")
    print(f"i_bess_abs_max={i_bess_abs_max:.6f} A")
    print(f"p_bess_dc_min={float(np.min(p_bess_dc)):.6f} W")
    print(f"p_bess_dc_max={float(np.max(p_bess_dc)):.6f} W")
    print(f"p_bess_abs_max={p_bess_abs_max:.6f} W")
    print(f"p_bess_dc_limit={float(model.p_bess_max_w):.6f} W")
    print(f"vt_bess_min={vt_bess_min:.6f} V")
    print(f"p_load_final={float(p_load[-1]):.6f} W")
    print(f"p_pcc_final={float(p_pcc[-1]):.6f} W")
    print(f"voltage_scale_ratio_max={float(np.max(voltage_scale_ratio)):.6f}")
    print(
        "checks="
        f"solver_ok={solver_ok}, states_finite_ok={states_finite_ok}, "
        f"signals_finite_ok={signals_finite_ok}, vdc_positive_ok={vdc_positive_ok}, "
        f"soc_range_ok={soc_range_ok}, soh_range_ok={soh_range_ok}, "
        f"vt_positive_ok={vt_positive_ok}, current_limit_ok={current_limit_ok}, "
        f"power_limit_ok={power_limit_ok}, power_limit_signal_ok={power_limit_signal_ok}, "
        f"identity_ok={identity_ok}"
    )
    print(f"observation={observation}")


if __name__ == "__main__":
    main()
