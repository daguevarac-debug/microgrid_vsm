"""Single-diode photovoltaic array model and parameter containers."""

from dataclasses import dataclass
from numbers import Real

import numpy as np

from config import (
    BOLTZMANN_J_PER_K,
    ELEM_CHARGE_C,
    KELVIN_OFFSET,
    PV_ALPHA_ISC_A_PER_C_DEFAULT,
    PV_ARRAY_PARALLEL_DEFAULT,
    PV_ARRAY_SERIES_DEFAULT,
    PV_BETA_VOC_V_PER_C_DEFAULT,
    PV_CURVE_POINTS_DEFAULT,
    PV_CURRENT_MIN_A,
    PV_DIODE_IDEALITY_DEFAULT,
    PV_NEWTON_CURRENT_TOL_A,
    PV_NEWTON_MAX_ITER_DEFAULT,
    PV_NUMERIC_EPS_A,
    PV_NUMERIC_EPS_DEN,
    PV_RSH_OHM_DEFAULT,
    PV_RS_OHM_DEFAULT,
    PV_STC_IRRADIANCE_W_PER_M2,
    PV_STC_TEMP_C,
    SI_BANDGAP_EV,
)


def _finite_float(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _positive_float(name: str, value) -> float:
    out = _finite_float(name, value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


def _positive_int(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a positive integer, got {value!r}.")
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return value


@dataclass
class PVModuleParams:
    voc_stc: float
    isc_stc: float
    vmp_stc: float
    imp_stc: float
    ns_cells: int
    alpha_isc: float = PV_ALPHA_ISC_A_PER_C_DEFAULT
    beta_voc: float = PV_BETA_VOC_V_PER_C_DEFAULT
    n: float = PV_DIODE_IDEALITY_DEFAULT
    rs: float = PV_RS_OHM_DEFAULT
    rsh: float = PV_RSH_OHM_DEFAULT

    def __post_init__(self) -> None:
        self.voc_stc = _positive_float("PVModuleParams.voc_stc", self.voc_stc)
        self.isc_stc = _positive_float("PVModuleParams.isc_stc", self.isc_stc)
        self.vmp_stc = _positive_float("PVModuleParams.vmp_stc", self.vmp_stc)
        self.imp_stc = _positive_float("PVModuleParams.imp_stc", self.imp_stc)
        self.ns_cells = _positive_int("PVModuleParams.ns_cells", self.ns_cells)
        self.alpha_isc = _finite_float("PVModuleParams.alpha_isc", self.alpha_isc)
        self.beta_voc = _finite_float("PVModuleParams.beta_voc", self.beta_voc)
        self.n = _positive_float("PVModuleParams.n", self.n)
        self.rs = _positive_float("PVModuleParams.rs", self.rs)
        self.rsh = _positive_float("PVModuleParams.rsh", self.rsh)


@dataclass
class PVArrayParams:
    module: PVModuleParams
    modules_in_series: int = PV_ARRAY_SERIES_DEFAULT
    strings_in_parallel: int = PV_ARRAY_PARALLEL_DEFAULT

    def __post_init__(self) -> None:
        if not isinstance(self.module, PVModuleParams):
            raise ValueError(
                f"PVArrayParams.module must be PVModuleParams, got {type(self.module).__name__}."
            )
        self.modules_in_series = _positive_int(
            "PVArrayParams.modules_in_series", self.modules_in_series
        )
        self.strings_in_parallel = _positive_int(
            "PVArrayParams.strings_in_parallel", self.strings_in_parallel
        )


class PVArraySingleDiode:
    """PV array model that computes I-V and P-V characteristics."""

    q = ELEM_CHARGE_C
    k = BOLTZMANN_J_PER_K
    Eg_eV = SI_BANDGAP_EV
    Eg = Eg_eV * q

    def __init__(self, params: PVArrayParams):
        if not isinstance(params, PVArrayParams):
            raise ValueError(f"params must be PVArrayParams, got {type(params).__name__}.")
        self.p = params

    def _thermal_voltage(self, T_c: float) -> float:
        T_c = _finite_float("T_c", T_c)
        T_k = T_c + KELVIN_OFFSET
        return self.k * T_k / self.q

    def _photocurrent(self, G: float, T_c: float) -> float:
        G = _finite_float("G", G)
        T_c = _finite_float("T_c", T_c)
        return (G / PV_STC_IRRADIANCE_W_PER_M2) * (
            self.p.module.isc_stc + self.p.module.alpha_isc * (T_c - PV_STC_TEMP_C)
        )

    def _sat_current_stc_approx(self) -> float:
        m = self.p.module
        Vt = self._thermal_voltage(PV_STC_TEMP_C)
        denom = np.exp(m.voc_stc / (m.n * m.ns_cells * Vt)) - 1.0
        return m.isc_stc / max(denom, PV_NUMERIC_EPS_DEN)

    def _sat_current(self, T_c: float) -> float:
        T_stc_k = PV_STC_TEMP_C + KELVIN_OFFSET
        T_k = T_c + KELVIN_OFFSET
        io_stc = self._sat_current_stc_approx()
        m = self.p.module
        return io_stc * (T_k / T_stc_k) ** 3 * np.exp(
            (self.Eg / (m.n * self.k)) * (1.0 / T_stc_k - 1.0 / T_k)
        )

    def ipv_from_vpv(
        self,
        Vpv: float,
        G: float,
        T_c: float,
        max_iter: int = PV_NEWTON_MAX_ITER_DEFAULT,
    ) -> float:
        Vpv = _finite_float("Vpv", Vpv)
        G = _finite_float("G", G)
        T_c = _finite_float("T_c", T_c)
        max_iter = _positive_int("max_iter", max_iter)
        arr = self.p
        m = arr.module

        V_mod = Vpv / arr.modules_in_series
        Iph = self._photocurrent(G, T_c)
        Io = self._sat_current(T_c)
        Vt = self._thermal_voltage(T_c)

        I = (G / PV_STC_IRRADIANCE_W_PER_M2) * m.imp_stc
        I = max(I, PV_CURRENT_MIN_A)

        a = m.n * m.ns_cells * Vt

        for _ in range(max_iter):
            exp_term = np.exp((V_mod + I * m.rs) / max(a, PV_NUMERIC_EPS_A))
            f = Iph - Io * (exp_term - 1.0) - (V_mod + I * m.rs) / m.rsh - I
            df = -Io * exp_term * (m.rs / max(a, PV_NUMERIC_EPS_A)) - (m.rs / m.rsh) - 1.0

            dI = -f / min(df, -PV_NUMERIC_EPS_DEN)
            I_new = I + dI

            if I_new < PV_CURRENT_MIN_A:
                I_new = PV_CURRENT_MIN_A

            if abs(I_new - I) < PV_NEWTON_CURRENT_TOL_A:
                I = I_new
                break
            I = I_new

        return I * arr.strings_in_parallel

    def pv_curve(self, G: float, T_c: float, num: int = PV_CURVE_POINTS_DEFAULT):
        G = _finite_float("G", G)
        T_c = _finite_float("T_c", T_c)
        num = _positive_int("num", num)
        arr = self.p
        m = arr.module

        Voc_mod = m.voc_stc + m.beta_voc * (T_c - PV_STC_TEMP_C)
        Voc_arr = max(Voc_mod, PV_CURRENT_MIN_A) * arr.modules_in_series

        V = np.linspace(PV_CURRENT_MIN_A, Voc_arr, num)
        I = np.array([self.ipv_from_vpv(v, G, T_c) for v in V])
        P = V * I
        return V, I, P
