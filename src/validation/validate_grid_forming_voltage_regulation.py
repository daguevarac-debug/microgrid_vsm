"""Validate isolated GFM three-phase voltage reference synthesis.

Scope:
- Use GridFormingInverter only, without Microgrid, IEEE33 or an external grid.
- Check balanced sinusoidal voltage references in an ideal islanded setting.
- Check that the DC bus voltage limits the achievable voltage peak.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from math import pi, sqrt
from pathlib import Path
import sys

import numpy as np

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from inverter_source import GridFormingInverter


@dataclass(frozen=True)
class VoltageMetrics:
    case_name: str
    vdc: float
    vpk_expected: float
    va_rms: float
    vb_rms: float
    vc_rms: float
    va_peak: float
    vb_peak: float
    vc_peak: float
    v_sum_max_abs: float
    max_rms_relative_error: float
    max_phase_rms_spread: float
    max_peak_excess: float


def _forbidden_imports_absent() -> bool:
    source = THIS_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {"microgrid", "ieee33", "main", "pandapower"}
    forbidden_names = {"GridFollowingController"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_roots:
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_roots:
                return False
            if any(alias.name in forbidden_names for alias in node.names):
                return False
    return True


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def _run_case(
    inverter: GridFormingInverter,
    theta: np.ndarray,
    vdc: float,
    m_max: float,
) -> VoltageMetrics:
    vabc = np.array([inverter.modulate(float(th), Vdc=vdc, m_max=m_max) for th in theta])
    va = vabc[:, 0]
    vb = vabc[:, 1]
    vc = vabc[:, 2]

    va_rms = _rms(va)
    vb_rms = _rms(vb)
    vc_rms = _rms(vc)
    rms_values = np.array([va_rms, vb_rms, vc_rms], dtype=float)
    peaks = np.array(
        [
            float(np.max(np.abs(va))),
            float(np.max(np.abs(vb))),
            float(np.max(np.abs(vc))),
        ],
        dtype=float,
    )
    vpk_expected = min(sqrt(2.0) * inverter.v_ln_rms, m_max * max(vdc, 0.0) / 2.0)
    target_rms = vpk_expected / sqrt(2.0)

    return VoltageMetrics(
        case_name="nominal_vdc" if vdc >= 300.0 else "low_vdc_limited",
        vdc=vdc,
        vpk_expected=vpk_expected,
        va_rms=va_rms,
        vb_rms=vb_rms,
        vc_rms=vc_rms,
        va_peak=float(peaks[0]),
        vb_peak=float(peaks[1]),
        vc_peak=float(peaks[2]),
        v_sum_max_abs=float(np.max(np.abs(va + vb + vc))),
        max_rms_relative_error=float(np.max(np.abs(rms_values - target_rms)) / target_rms),
        max_phase_rms_spread=float((np.max(rms_values) - np.min(rms_values)) / target_rms),
        max_peak_excess=float(np.max(peaks - vpk_expected)),
    )


def _case_passed(metrics: VoltageMetrics) -> bool:
    peak_tol = 1e-9 * max(metrics.vpk_expected, 1.0)
    sum_tol = 1e-6 * max(metrics.vpk_expected, 1.0)
    values = np.array(
        [
            metrics.va_rms,
            metrics.vb_rms,
            metrics.vc_rms,
            metrics.va_peak,
            metrics.vb_peak,
            metrics.vc_peak,
            metrics.v_sum_max_abs,
        ],
        dtype=float,
    )
    return bool(
        np.all(np.isfinite(values))
        and metrics.max_rms_relative_error < 0.01
        and metrics.max_phase_rms_spread < 0.01
        and metrics.max_peak_excess <= peak_tol
        and metrics.v_sum_max_abs < sum_tol
    )


def _print_case(metrics: VoltageMetrics) -> None:
    target_rms = metrics.vpk_expected / sqrt(2.0)
    print(f"\n--- {metrics.case_name} ---")
    print(f"vdc={metrics.vdc:.6f} V")
    print(f"vpk_expected={metrics.vpk_expected:.9f} V")
    print(f"target_rms={target_rms:.9f} V")
    print(f"va_rms={metrics.va_rms:.9f} V")
    print(f"vb_rms={metrics.vb_rms:.9f} V")
    print(f"vc_rms={metrics.vc_rms:.9f} V")
    print(f"va_peak={metrics.va_peak:.9f} V")
    print(f"vb_peak={metrics.vb_peak:.9f} V")
    print(f"vc_peak={metrics.vc_peak:.9f} V")
    print(f"v_sum_max_abs={metrics.v_sum_max_abs:.9e} V")
    print(f"max_rms_relative_error={metrics.max_rms_relative_error:.9e}")
    print(f"max_phase_rms_spread={metrics.max_phase_rms_spread:.9e}")
    print(f"max_peak_excess={metrics.max_peak_excess:.9e} V")
    print(f"status={'PASS' if _case_passed(metrics) else 'FAIL'}")


def main() -> int:
    f_hz = 60.0
    v_ln_rms = 110.0
    theta0 = 0.0
    vdc = 340.0
    vdc_low = 200.0
    m_max = 0.95
    # Avoid duplicating theta=0 and theta=2*pi so RMS estimates are unbiased.
    theta = np.linspace(0.0, 2.0 * pi, 1000, endpoint=False)

    inverter = GridFormingInverter(f_hz=f_hz, v_ln_rms=v_ln_rms, theta0=theta0)
    nominal = _run_case(inverter=inverter, theta=theta, vdc=vdc, m_max=m_max)
    low_vdc = _run_case(inverter=inverter, theta=theta, vdc=vdc_low, m_max=m_max)
    low_vdc_limit_expected = m_max * vdc_low / 2.0
    low_vdc_limit_ok = abs(low_vdc.vpk_expected - low_vdc_limit_expected) <= 1e-12
    forbidden_imports_ok = _forbidden_imports_absent()

    print("Grid-forming isolated voltage reference validation")
    print("Scope: GridFormingInverter only, no external grid or Microgrid coupling.")
    print("\nParameters:")
    print(f"f_hz={f_hz:.6f} Hz")
    print(f"v_ln_rms={v_ln_rms:.6f} V")
    print(f"theta0={theta0:.6f} rad")
    print(f"m_max={m_max:.6f}")

    _print_case(nominal)
    _print_case(low_vdc)

    checks = {
        "nominal balanced voltage reference": _case_passed(nominal),
        "low Vdc peak limited by m_max*Vdc/2": _case_passed(low_vdc) and low_vdc_limit_ok,
        "no forbidden grid imports": forbidden_imports_ok,
    }
    passed = all(checks.values())

    print("\nChecks:")
    for name, ok in checks.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    print(f"\nOverall status: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
