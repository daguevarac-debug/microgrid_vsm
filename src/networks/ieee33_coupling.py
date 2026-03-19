"""One-way sequential coupling: local microgrid dynamics + IEEE 33 postprocessing."""

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
from models.microgrid import Microgrid
from plots.ieee33_plots import graficar_resultados_ieee33
from simulation.ieee33_reporting import reportar_ieee33


class IEEE33MicrogridBaseline(Microgrid):
    """PV + DC-link + LCL baseline averaged model with one-way IEEE 33 coupling."""

    def __init__(
        self,
        ruta_txt: str,
        pcc_bus_idx: int = IEEE33_PCC_BUS_IDX,
        irradiance_profile=None,
        temperature_profile=None,
        load_profile=None,
    ):
        super().__init__(
            irradiance_profile=irradiance_profile,
            temperature_profile=temperature_profile,
            load_profile=load_profile,
        )
        self.net = construir_red_ieee33(ruta_txt)
        self.pcc_bus_idx = pcc_bus_idx
        self.output_dir = Path(__file__).resolve().parent.parent

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

    def flujo_base(self) -> tuple[pd.Series, pd.DataFrame]:
        """Run base load flow on current IEEE 33 network."""
        pp.runpp(self.net)
        return self.net.res_bus["vm_pu"].copy(), self.net.res_line.copy()

    def flujo_con_dg(self, p_ss_kw: float) -> tuple[pd.Series, pd.DataFrame]:
        """Inject average active power as static DG in IEEE 33 and run power flow."""
        p_mw = p_ss_kw / 1000.0
        q_mvar = p_mw * np.tan(np.arccos(MICROGRID_PF_DEFAULT))

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
        """Imprimir reporte de comparacion sin/con baseline."""
        reportar_ieee33(
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
        """Graficar resultados sin/con baseline y dinamica local."""
        graficar_resultados_ieee33(
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


IEEE33Microgrid = IEEE33MicrogridBaseline

