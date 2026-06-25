"""Validate active GFM coupling and the IEEE 33 steady-state PCC average."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import SIM_SS_WINDOW_FRACTION, SIM_T_END_S_DEFAULT
from controllers.gfm_controller import GFMController
from ieee33_coupling import (
    IEEE33_GFM_DAMPING_D_DEFAULT,
    IEEE33_GFM_INERTIA_M_DEFAULT,
    IEEE33MicrogridWithBESS,
)


ATOL_KW = 1e-12
RTOL_KW = 1e-12


def _check(name: str, condition: bool, detail: str) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"{name}={status} ({detail})")
    return condition


def main() -> int:
    repo_root = SRC_DIR.parent
    ruta_txt = SRC_DIR / "ieee33bus.txt"
    output_dir = repo_root / "outputs" / "validation" / "ieee33_gfm_pcc_average"

    system = IEEE33MicrogridWithBESS(
        str(ruta_txt),
        output_dir=output_dir,
    )
    p_ss_kw, data = system.simular()

    t = np.asarray(data["t"], dtype=float)
    p_pcc = np.asarray(data["p_pcc"], dtype=float)
    frequency_hz = np.asarray(data["frequency_hz"], dtype=float)
    ss_window_start_s = SIM_T_END_S_DEFAULT * SIM_SS_WINDOW_FRACTION
    ss_mask = t > ss_window_start_s

    p_ss_kw_expected = float(np.mean(p_pcc[ss_mask]) / 1000.0)
    p_ss_match = bool(
        np.isclose(p_ss_kw, p_ss_kw_expected, atol=ATOL_KW, rtol=RTOL_KW)
        and np.isclose(
            float(data["p_ss_kw"]),
            p_ss_kw_expected,
            atol=ATOL_KW,
            rtol=RTOL_KW,
        )
        and np.isclose(
            float(data["P_ss_w"]),
            1000.0 * p_ss_kw_expected,
            atol=1000.0 * ATOL_KW,
            rtol=RTOL_KW,
        )
    )

    dynamics = system.controller.frequency_dynamics
    checks = [
        _check(
            "gfm_controller_active",
            isinstance(system.controller, GFMController),
            type(system.controller).__name__,
        ),
        _check(
            "gfm_state_mapping",
            system.controller_state_name == "omega",
            system.controller_state_name,
        ),
        _check(
            "selected_gfm_parameters",
            bool(
                np.isclose(
                    dynamics.inertia_m,
                    IEEE33_GFM_INERTIA_M_DEFAULT,
                )
                and np.isclose(
                    dynamics.damping_d,
                    IEEE33_GFM_DAMPING_D_DEFAULT,
                )
            ),
            f"M={dynamics.inertia_m}, D={dynamics.damping_d}",
        ),
        _check(
            "signals_finite",
            bool(
                np.all(np.isfinite(t))
                and np.all(np.isfinite(p_pcc))
                and np.all(np.isfinite(frequency_hz))
            ),
            f"samples={t.size}",
        ),
        _check(
            "steady_state_window_nonempty",
            bool(np.any(ss_mask)),
            f"samples={np.count_nonzero(ss_mask)}",
        ),
        _check(
            "p_ss_kw_from_p_pcc_mean",
            p_ss_match,
            f"returned={p_ss_kw:.12f}, recomputed={p_ss_kw_expected:.12f}",
        ),
        _check(
            "p_ss_source_traceable",
            data.get("p_ss_source") == "mean(p_pcc[steady_state_window])",
            str(data.get("p_ss_source")),
        ),
        _check(
            "stationary_sample_count_traceable",
            int(data.get("ss_sample_count", -1)) == int(np.count_nonzero(ss_mask)),
            str(data.get("ss_sample_count")),
        ),
    ]

    status = "PASS" if all(checks) else "FAIL"
    print(f"p_ss_kw={p_ss_kw:.12f}")
    print(f"p_ss_kw_recomputed={p_ss_kw_expected:.12f}")
    print(f"p_ss_kw_residual={p_ss_kw - p_ss_kw_expected:.3e}")
    print(f"overall_status={status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
