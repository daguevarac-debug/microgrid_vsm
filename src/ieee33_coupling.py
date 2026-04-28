"""One-way sequential coupling: local microgrid dynamics + IEEE 33 postprocessing."""

from numbers import Real
from pathlib import Path

import numpy as np
import pandapower as pp
import pandas as pd
from scipy.integrate import solve_ivp

from config import (
    GRID_THETA0_RAD_DEFAULT,
    IEEE33_PCC_BUS_IDX,
    MICROGRID_PF_DEFAULT,
    MICROGRID_SGEN_NAME,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_SS_WINDOW_FRACTION,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from ieee33_base import construir_red_ieee33
from microgrid import Microgrid, MicrogridWithBESS
from ieee33_plots import plot_ieee33_results
from ieee33_reporting import print_ieee33_report


def _finite_float(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _index_in_range(name: str, index, size: int) -> int:
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError(f"{name} must be an integer index, got {index!r}.")
    if size <= 0:
        raise ValueError(f"{name} validation failed because size must be > 0, got {size!r}.")
    if index < 0 or index >= size:
        raise ValueError(f"{name} must be in [0, {size - 1}] for network size {size}, got {index!r}.")
    return index


class _IEEE33CouplingMixin:
    """Shared IEEE 33 one-way postprocessing helpers."""

    def _init_ieee33_coupling(
        self,
        ruta_txt: str,
        pcc_bus_idx: int = IEEE33_PCC_BUS_IDX,
        output_dir: str | Path | None = None,
    ) -> None:
        self.net = construir_red_ieee33(ruta_txt)
        self.pcc_bus_idx = _index_in_range(
            f"{type(self).__name__}.pcc_bus_idx",
            pcc_bus_idx,
            size=len(self.net.bus),
        )
        if output_dir is None:
            self.output_dir = Path(__file__).resolve().parents[1] / "outputs"
        else:
            self.output_dir = Path(output_dir)

    def flujo_base(self) -> tuple[pd.Series, pd.DataFrame]:
        """Run base load flow on current IEEE 33 network."""
        pp.runpp(self.net)
        return self.net.res_bus["vm_pu"].copy(), self.net.res_line.copy()

    def flujo_con_dg(self, p_ss_kw: float) -> tuple[pd.Series, pd.DataFrame]:
        """Inject average active power as static DG in IEEE 33 and run power flow."""
        p_ss_kw = _finite_float("p_ss_kw", p_ss_kw)
        p_mw = p_ss_kw / 1000.0
        q_mvar = p_mw * np.tan(np.arccos(MICROGRID_PF_DEFAULT))
        print(
            "  Equivalente DG PCC: "
            f"P_eq_mw={p_mw:.6f}, Q_eq_mvar={q_mvar:.6f}, "
            f"fp={MICROGRID_PF_DEFAULT:.3f}, nodo_pcc={self.pcc_bus_idx + 1}"
        )

        gen_idx = pp.create_sgen(
            self.net,
            bus=self.pcc_bus_idx,
            p_mw=p_mw,
            q_mvar=q_mvar,
            name=MICROGRID_SGEN_NAME,
            type="PV",
        )
        pp.runpp(self.net)
        voltajes = self.net.res_bus["vm_pu"].copy()
        estado_lineas = self.net.res_line.copy()
        self.net.sgen.drop(index=gen_idx, inplace=True)
        return voltajes, estado_lineas

    def line_branches(self) -> list[tuple[int, int]]:
        """Return line segment pairs in one-based bus indices."""
        return [
            (int(from_bus) + 1, int(to_bus) + 1)
            for from_bus, to_bus in zip(self.net.line["from_bus"], self.net.line["to_bus"])
        ]

    def reportar(
        self,
        v_base: pd.Series,
        v_mg: pd.Series,
        p_ss_kw: float,
        estado_lineas_base: np.ndarray,
        estado_lineas_mg: np.ndarray,
        etiqueta_estado_lineas: str,
        metrica_lineas: str,
    ) -> None:
        """Imprimir reporte de comparacion sin/con microrred."""
        print_ieee33_report(
            pcc_bus_num=self.pcc_bus_idx + 1,
            p_ss_kw=p_ss_kw,
            v_base=v_base,
            v_mg=v_mg,
            line_metric_base=estado_lineas_base,
            line_metric_mg=estado_lineas_mg,
            line_metric_label=etiqueta_estado_lineas,
            line_metric_key=metrica_lineas,
        )

    def graficar(
        self,
        v_base: pd.Series,
        v_mg: pd.Series,
        datos: dict,
        p_ss_kw: float,
        estado_lineas_base: np.ndarray,
        estado_lineas_mg: np.ndarray,
        etiqueta_estado_lineas: str,
        metrica_lineas: str,
        nodo_pcc: int,
    ) -> None:
        """Graficar resultados sin/con microrred y dinamica local."""
        plot_ieee33_results(
            output_dir=self.output_dir,
            v_base=v_base,
            v_mg=v_mg,
            datos=datos,
            p_ss_kw=p_ss_kw,
            estado_lineas_base=estado_lineas_base,
            estado_lineas_mg=estado_lineas_mg,
            etiqueta_estado_lineas=etiqueta_estado_lineas,
            metrica_lineas=metrica_lineas,
            nodo_pcc=nodo_pcc,
            ramas=self.line_branches(),
        )


class IEEE33MicrogridBaseline(_IEEE33CouplingMixin, Microgrid):
    """PV + DC-link + LCL baseline averaged model with one-way IEEE 33 coupling."""

    def __init__(
        self,
        ruta_txt: str,
        pcc_bus_idx: int = IEEE33_PCC_BUS_IDX,
        irradiance_profile=None,
        temperature_profile=None,
        load_profile=None,
        output_dir: str | Path | None = None,
    ):
        super().__init__(
            irradiance_profile=irradiance_profile,
            temperature_profile=temperature_profile,
            load_profile=load_profile,
        )
        self._init_ieee33_coupling(ruta_txt, pcc_bus_idx=pcc_bus_idx, output_dir=output_dir)

    def simular(self) -> tuple[float, dict]:
        """Run dynamic simulation and return steady-state active power and time series."""
        print("=" * 55)
        print("  PASO 1: Simulacion dinamica LOCAL baseline (sin acople IEEE en tiempo real)")
        print("=" * 55)
        print(f"  P_ref_nominal baseline : {self.P_ref_nominal:.1f} W")

        t_span = (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT)
        y0 = [
            SIM_VDC0_V_DEFAULT,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            GRID_THETA0_RAD_DEFAULT,
        ]
        sol = solve_ivp(
            self.system_dynamics,
            t_span,
            y0,
            max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
            rtol=SIM_SOLVER_RTOL_DEFAULT,
            atol=SIM_SOLVER_ATOL_DEFAULT,
        )

        t = sol.t
        vdc = sol.y[0]
        p_inst = np.array([self.power_signals(tk, sol.y[:, k])[1] for k, tk in enumerate(t)])

        idx_ss = t > (SIM_T_END_S_DEFAULT * SIM_SS_WINDOW_FRACTION)
        p_ss_w = float(p_inst[idx_ss].mean())
        p_ss_kw = p_ss_w / 1000.0
        print(f"  P estado estacionario : {p_ss_w:.1f} W  ->  {p_ss_kw:.4f} kW")

        datos_dinamicos = {
            "t": t,
            "Vdc": vdc,
            "p_inst": p_inst,
            "t_step": self.t_step,
            "P_ss_w": p_ss_w,
            "p_ss_kw": p_ss_kw,
            "nodo_pcc": self.pcc_bus_idx + 1,
        }
        return p_ss_kw, datos_dinamicos


class IEEE33MicrogridWithBESS(_IEEE33CouplingMixin, MicrogridWithBESS):
    """PV + DC-link + LCL + preliminary BESS model with one-way IEEE 33 coupling."""

    def __init__(
        self,
        ruta_txt: str,
        pcc_bus_idx: int = IEEE33_PCC_BUS_IDX,
        irradiance_profile=None,
        temperature_profile=None,
        load_profile=None,
        output_dir: str | Path | None = None,
    ):
        super().__init__(
            irradiance_profile=irradiance_profile,
            temperature_profile=temperature_profile,
            load_profile=load_profile,
        )
        self._init_ieee33_coupling(ruta_txt, pcc_bus_idx=pcc_bus_idx, output_dir=output_dir)

    def simular(self) -> tuple[float, dict]:
        """Run preliminary BESS-coupled simulation and return average PCC active power."""
        print("=" * 55)
        print("  PASO 1: Simulacion dinamica LOCAL")
        print("  PV + DC-link + LCL + BESS preliminar")
        print("  Acople IEEE 33 one-way; NO es GFM/VSG integrado")
        print("=" * 55)
        print(f"  P_ref_nominal baseline : {self.P_ref_nominal:.1f} W")

        t_span = (SIM_T_START_S_DEFAULT, SIM_T_END_S_DEFAULT)
        y0 = self.initial_state_with_bess(vdc0=SIM_VDC0_V_DEFAULT)
        sol = solve_ivp(
            self.system_dynamics,
            t_span,
            y0,
            max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT,
            rtol=SIM_SOLVER_RTOL_DEFAULT,
            atol=SIM_SOLVER_ATOL_DEFAULT,
        )

        t = sol.t
        vdc = sol.y[0]
        p_pcc = np.zeros_like(t)
        i_bess = np.zeros_like(t)
        p_bess_dc = np.zeros_like(t)
        soc_bess = np.zeros_like(t)
        soh_bess = np.zeros_like(t)

        for k, tk in enumerate(t):
            sig = self.integrated_signals(tk, sol.y[:, k])
            p_pcc[k] = sig["p_pcc"]
            i_bess[k] = sig["i_bess"]
            p_bess_dc[k] = sig["p_bess_dc"]
            soc_bess[k] = sig["soc_bess"]
            soh_bess[k] = sig["soh_bess"]

        idx_ss = t > (SIM_T_END_S_DEFAULT * SIM_SS_WINDOW_FRACTION)
        p_ss_w = float(p_pcc[idx_ss].mean())
        p_ss_kw = p_ss_w / 1000.0
        print(f"  P estado estacionario desde p_pcc : {p_ss_w:.1f} W  ->  {p_ss_kw:.4f} kW")
        print("  Nota: la frecuencia del baseline grid-following no se interpreta como metrica GFM/VSG.")

        datos_dinamicos = {
            "t": t,
            "Vdc": vdc,
            "p_inst": p_pcc,
            "p_pcc": p_pcc,
            "i_bess": i_bess,
            "p_bess_dc": p_bess_dc,
            "soc_bess": soc_bess,
            "soh_bess": soh_bess,
            "t_step": self.t_step,
            "P_ss_w": p_ss_w,
            "p_ss_kw": p_ss_kw,
            "nodo_pcc": self.pcc_bus_idx + 1,
            "scope": "PV + DC-link + LCL + BESS preliminar; no GFM/VSG integrado",
        }
        return p_ss_kw, datos_dinamicos


IEEE33Microgrid = IEEE33MicrogridBaseline
