"""Minimal STC validation for single-diode PV parametrization (LONGi LR7-54HJD-500M)."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from scipy.optimize import minimize

# Allow direct execution from repository root or from this file location.
THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
    MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
    MICROGRID_PV_DIODE_IDEALITY_DEFAULT,
    MICROGRID_PV_IMP_STC_A_DEFAULT,
    MICROGRID_PV_ISC_STC_A_DEFAULT,
    MICROGRID_PV_NS_CELLS_DEFAULT,
    MICROGRID_PV_RSH_OHM_DEFAULT,
    MICROGRID_PV_RS_OHM_DEFAULT,
    MICROGRID_PV_VMP_STC_V_DEFAULT,
    MICROGRID_PV_VOC_STC_V_DEFAULT,
)
from pv_model import PVArrayParams, PVArraySingleDiode, PVModuleParams

# Simple acceptance rule for thesis-level STC fit using datasheet-only parameters.
REASONABLE_MAX_ABS_ERROR_PCT = 3.5


def _build_module_model(n: float, rs: float, rsh: float) -> PVArraySingleDiode:
    module = PVModuleParams(
        voc_stc=MICROGRID_PV_VOC_STC_V_DEFAULT,
        isc_stc=MICROGRID_PV_ISC_STC_A_DEFAULT,
        vmp_stc=MICROGRID_PV_VMP_STC_V_DEFAULT,
        imp_stc=MICROGRID_PV_IMP_STC_A_DEFAULT,
        ns_cells=MICROGRID_PV_NS_CELLS_DEFAULT,
        alpha_isc=MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
        beta_voc=MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
        n=n,
        rs=rs,
        rsh=rsh,
    )
    array = PVArrayParams(module=module, modules_in_series=1, strings_in_parallel=1)
    return PVArraySingleDiode(array)


def _estimate_voc_from_iv(model: PVArraySingleDiode) -> float:
    """Estimate Voc by bisection over I(V) at STC."""
    lo_v = 0.0
    hi_v = MICROGRID_PV_VOC_STC_V_DEFAULT * 1.6
    for _ in range(55):
        mid_v = 0.5 * (lo_v + hi_v)
        if model.ipv_from_vpv(mid_v, G=1000.0, T_c=25.0) > 1e-6:
            lo_v = mid_v
        else:
            hi_v = mid_v
    return 0.5 * (lo_v + hi_v)


def stc_model_points(n: float, rs: float, rsh: float) -> dict[str, float]:
    """Return Voc, Isc, Vmp, Imp predicted by current single-diode model at STC."""
    model = _build_module_model(n=n, rs=rs, rsh=rsh)
    isc_model = float(model.ipv_from_vpv(0.0, G=1000.0, T_c=25.0))
    voc_model = float(_estimate_voc_from_iv(model))

    voltage = np.linspace(0.0, voc_model, 280)
    current = np.array([model.ipv_from_vpv(v, G=1000.0, T_c=25.0) for v in voltage])
    power = voltage * current
    idx_mpp = int(np.argmax(power))

    return {
        "Voc": voc_model,
        "Isc": isc_model,
        "Vmp": float(voltage[idx_mpp]),
        "Imp": float(current[idx_mpp]),
    }


def stc_error_objective(n: float, rs: float, rsh: float) -> float:
    """Simple STC error function using only Voc, Isc, Vmp and Imp."""
    if n <= 0.0 or rs <= 0.0 or rsh <= 0.0:
        return 1e9

    try:
        model = stc_model_points(n=n, rs=rs, rsh=rsh)
    except Exception:
        return 1e9

    voc_ref = MICROGRID_PV_VOC_STC_V_DEFAULT
    isc_ref = MICROGRID_PV_ISC_STC_A_DEFAULT
    vmp_ref = MICROGRID_PV_VMP_STC_V_DEFAULT
    imp_ref = MICROGRID_PV_IMP_STC_A_DEFAULT

    err_voc = (model["Voc"] - voc_ref) / voc_ref
    err_isc = (model["Isc"] - isc_ref) / isc_ref
    err_vmp = (model["Vmp"] - vmp_ref) / vmp_ref
    err_imp = (model["Imp"] - imp_ref) / imp_ref
    return float(err_voc**2 + err_isc**2 + err_vmp**2 + err_imp**2)


def fit_n_rs_rsh_simple(
    n_min: float,
    n_max: float,
    rs_min: float,
    rs_max: float,
    rsh_min: float,
    rsh_max: float,
    x0_n: float,
    x0_rs: float,
    x0_rsh: float,
) -> tuple[float, float, float, float]:
    """Simple deterministic numerical fit (Powell) for n, Rs, Rsh at STC."""

    def objective_transformed(x: np.ndarray) -> float:
        n = float(x[0])
        rs = float(x[1])
        rsh = float(10.0 ** x[2])
        if not (n_min <= n <= n_max and rs_min <= rs <= rs_max and rsh_min <= rsh <= rsh_max):
            return 1e6
        return stc_error_objective(n=n, rs=rs, rsh=rsh)

    x0 = np.array([x0_n, x0_rs, np.log10(x0_rsh)], dtype=float)
    result = minimize(
        objective_transformed,
        x0=x0,
        method="Powell",
        options={"maxiter": 120, "xtol": 1e-4, "ftol": 1e-8, "disp": False},
    )

    n_fit = float(result.x[0])
    rs_fit = float(result.x[1])
    rsh_fit = float(10.0 ** result.x[2])
    err_fit = stc_error_objective(n=n_fit, rs=rs_fit, rsh=rsh_fit)
    return n_fit, rs_fit, rsh_fit, err_fit


def _error_pct(model_value: float, ref_value: float) -> float:
    return 100.0 * (model_value - ref_value) / ref_value


def _errors_pct(points: dict[str, float]) -> dict[str, float]:
    return {
        "Voc": _error_pct(points["Voc"], MICROGRID_PV_VOC_STC_V_DEFAULT),
        "Isc": _error_pct(points["Isc"], MICROGRID_PV_ISC_STC_A_DEFAULT),
        "Vmp": _error_pct(points["Vmp"], MICROGRID_PV_VMP_STC_V_DEFAULT),
        "Imp": _error_pct(points["Imp"], MICROGRID_PV_IMP_STC_A_DEFAULT),
    }


def _max_abs_error_pct(errors_pct: dict[str, float]) -> float:
    return max(abs(v) for v in errors_pct.values())


def _print_case(title: str, n: float, rs: float, rsh: float, obj: float) -> dict[str, float]:
    points = stc_model_points(n=n, rs=rs, rsh=rsh)
    errs = _errors_pct(points)
    print(f"\n=== {title} ===")
    print(f"n = {n:.6f} | Rs = {rs:.6f} ohm | Rsh = {rsh:.2f} ohm | objective = {obj:.8e}")
    print(f"Voc_model = {points['Voc']:.5f} V | error = {errs['Voc']:+.4f} %")
    print(f"Isc_model = {points['Isc']:.5f} A | error = {errs['Isc']:+.4f} %")
    print(f"Vmp_model = {points['Vmp']:.5f} V | error = {errs['Vmp']:+.4f} %")
    print(f"Imp_model = {points['Imp']:.5f} A | error = {errs['Imp']:+.4f} %")
    print(f"max_abs_error = {_max_abs_error_pct(errs):.4f} %")
    return errs


def main() -> None:
    voc_ref = MICROGRID_PV_VOC_STC_V_DEFAULT
    isc_ref = MICROGRID_PV_ISC_STC_A_DEFAULT
    vmp_ref = MICROGRID_PV_VMP_STC_V_DEFAULT
    imp_ref = MICROGRID_PV_IMP_STC_A_DEFAULT

    # Free fit: broad positive bounds, used as baseline comparison.
    n_free, rs_free, rsh_free, obj_free = fit_n_rs_rsh_simple(
        n_min=0.8,
        n_max=2.2,
        rs_min=1e-4,
        rs_max=1.2,
        rsh_min=50.0,
        rsh_max=2e5,
        x0_n=1.25,
        x0_rs=0.25,
        x0_rsh=200.0,
    )

    # Restricted fit for silicon module: 1.0 <= n <= 2.0, Rs>0, Rsh>0 with reasonable upper bound.
    n_rest, rs_rest, rsh_rest, obj_rest = fit_n_rs_rsh_simple(
        n_min=1.0,
        n_max=2.0,
        rs_min=1e-4,
        rs_max=1.2,
        rsh_min=50.0,
        rsh_max=1e4,
        x0_n=max(1.0, min(2.0, MICROGRID_PV_DIODE_IDEALITY_DEFAULT)),
        x0_rs=max(1e-4, MICROGRID_PV_RS_OHM_DEFAULT),
        x0_rsh=min(1e4, max(50.0, MICROGRID_PV_RSH_OHM_DEFAULT)),
    )

    print("=== STC datasheet target (LONGi LR7-54HJD-500M) ===")
    print(f"Voc_ref = {voc_ref:.5f} V | Isc_ref = {isc_ref:.5f} A")
    print(f"Vmp_ref = {vmp_ref:.5f} V | Imp_ref = {imp_ref:.5f} A")
    errs_free = _print_case(
        title="Free fit (broad bounds)",
        n=n_free,
        rs=rs_free,
        rsh=rsh_free,
        obj=obj_free,
    )
    errs_rest = _print_case(
        title="Restricted fit (silicon bounds: 1.0<=n<=2.0, Rsh<=1e4)",
        n=n_rest,
        rs=rs_rest,
        rsh=rsh_rest,
        obj=obj_rest,
    )

    print("\n=== Decision aid for config update ===")
    print(
        f"Restricted-fit reasonable threshold: max_abs_error <= {REASONABLE_MAX_ABS_ERROR_PCT:.2f} %"
    )
    print(f"Free-fit max_abs_error       = {_max_abs_error_pct(errs_free):.4f} %")
    print(f"Restricted-fit max_abs_error = {_max_abs_error_pct(errs_rest):.4f} %")
    if _max_abs_error_pct(errs_rest) <= REASONABLE_MAX_ABS_ERROR_PCT:
        print("Restricted fit is REASONABLE for thesis baseline use.")
    else:
        print("Restricted fit is NOT reasonable under current threshold.")


if __name__ == "__main__":
    main()
