"""Physical plant layer for PV + DC-link + LCL baseline model."""

import numpy as np

from dclink import DCLinkParams
from lcl_filter import LCLFilter
from pv_model import PVArraySingleDiode


class HardwarePlant:
    """Physical layer: PV source, DC-link and LCL filter dynamics."""

    def __init__(
        self,
        pv: PVArraySingleDiode,
        dcp: DCLinkParams,
        lcl: LCLFilter,
        eta: float,
        v_uvlo: float,
    ):
        self.pv = pv
        self.dcp = dcp
        self.lcl = lcl
        self.eta = eta
        self.v_uvlo = v_uvlo

    def pv_current(self, vdc_eff: float, irradiance: float, cell_temp_c: float) -> float:
        """Return PV array current for current operating point."""
        return self.pv.ipv_from_vpv(vdc_eff, G=irradiance, T_c=cell_temp_c)

    def pcc_voltage(self, i2: np.ndarray, r_load: float) -> np.ndarray:
        """Baseline local AC closure with equivalent resistive load."""
        return i2 * r_load

    def dc_link_derivative(self, ipv: float, idc_inv: float, i_bess: float = 0.0) -> float:
        """Return DC-link voltage derivative from power balance."""
        # TODO [MODELO_BESS]: agregar i_bess cuando se implemente bateria.
        return (ipv + i_bess - idc_inv) / self.dcp.Cdc

    def lcl_derivatives(
        self,
        v_inv: np.ndarray,
        v_pcc: np.ndarray,
        i1: np.ndarray,
        vc: np.ndarray,
        i2: np.ndarray,
    ):
        """Delegate LCL state derivatives."""
        return self.lcl.calculate_derivatives(v_inv, v_pcc, i1, vc, i2)

