"""Centralized model constants for the microgrid electrical layer.

Extracted from:
- pv_model.py
- inverter_source.py
- dclink.py
"""

import warnings

import numpy as np

# ------------------------------
# Physical constants
# ------------------------------
ELEM_CHARGE_C = 1.602176634e-19
BOLTZMANN_J_PER_K = 1.380649e-23
SI_BANDGAP_EV = 1.121
SI_BANDGAP_J = SI_BANDGAP_EV * ELEM_CHARGE_C

# ------------------------------
# PV reference conditions
# ------------------------------
PV_STC_IRRADIANCE_W_PER_M2 = 1000.0
PV_STC_TEMP_C = 25.0
KELVIN_OFFSET = 273.15

# ------------------------------
# PV module default parameters
# ------------------------------
PV_VOC_STC_V_DEFAULT = 50.0
PV_ISC_STC_A_DEFAULT = 14.0
PV_VMP_STC_V_DEFAULT = 42.0
PV_IMP_STC_A_DEFAULT = 13.1
PV_NS_CELLS_DEFAULT = 72
PV_ALPHA_ISC_A_PER_C_DEFAULT = 0.0
PV_BETA_VOC_V_PER_C_DEFAULT = 0.0
PV_DIODE_IDEALITY_DEFAULT = 1.25
PV_RS_OHM_DEFAULT = 0.25
PV_RSH_OHM_DEFAULT = 200.0
PV_ARRAY_SERIES_DEFAULT = 1
PV_ARRAY_PARALLEL_DEFAULT = 1

# ------------------------------
# PV numerical/safety limits
# ------------------------------
PV_NUMERIC_EPS_DEN = 1e-12
PV_NUMERIC_EPS_A = 1e-9
PV_NEWTON_CURRENT_TOL_A = 1e-8
PV_NEWTON_MAX_ITER_DEFAULT = 50
PV_CURVE_POINTS_DEFAULT = 200
PV_CURRENT_MIN_A = 0.0

# ------------------------------
# Inverter source defaults
# ------------------------------
GRID_FREQ_HZ_DEFAULT = 60.0
# Baseline AC setpoint chosen to stay consistent with direct PV-DC coupling limits.
GRID_V_LN_RMS_DEFAULT = 110.0
GRID_THETA0_RAD_DEFAULT = 0.0
INVERTER_MODULATION_INDEX_MAX_DEFAULT = 0.95
INVERTER_VDC_MIN_FOR_NOMINAL_AC_DEFAULT = (
    2.0 * np.sqrt(2.0) * GRID_V_LN_RMS_DEFAULT / INVERTER_MODULATION_INDEX_MAX_DEFAULT
)

# 3-phase electrical angles
THREE_PHASE_120_DEG_RAD = 2.0 * np.pi / 3.0

# ------------------------------
# DC-link defaults
# ------------------------------
DCLINK_CAP_F_DEFAULT = 0.002
DCLINK_VMIN_DEFAULT = 50.0

# ------------------------------
# LCL filter defaults (per phase)
# ------------------------------
LCL_L1_H_DEFAULT = 1e-3
LCL_R1_OHM_DEFAULT = 0.05
LCL_CF_F_DEFAULT = 10e-6
LCL_RD_OHM_DEFAULT = 1e6
LCL_L2_H_DEFAULT = 1e-3
LCL_R2_OHM_DEFAULT = 0.05

# ------------------------------
# VSG defaults
# ------------------------------
VSG_INERTIA_J_DEFAULT = 0.1
VSG_DAMPING_D_DEFAULT = 10.0
VSG_OMEGA_REF_RAD_S_DEFAULT = 2.0 * np.pi * 60.0

# ------------------------------
# FOVIC defaults
# ------------------------------
# Nour (2023), Table 1 - Eq. (23) parameters
FOVIC_K_DC_DEFAULT = 1.0
FOVIC_T_DC_S_DEFAULT = 0.1
FOVIC_T_BESS_S_DEFAULT = 0.1
FOVIC_K_H_DEFAULT = 1.0
FOVIC_MU_DEFAULT = 0.4

# Oustaloup approximation settings (Yu 2023 Sec. III-B1 Eq. (7)-(8))
FOVIC_OUSTALOUP_ORDER_N_DEFAULT = 5
FOVIC_OMEGA_L_RAD_S_DEFAULT = 0.1
FOVIC_OMEGA_H_RAD_S_DEFAULT = 1000.0

# Swing equation parameters for FOVIC formulation (Nour 2023 Eq. (18))
FOVIC_INERTIA_H_DEFAULT = VSG_INERTIA_J_DEFAULT
FOVIC_DAMPING_D_DEFAULT = VSG_DAMPING_D_DEFAULT
FOVIC_SWING_TWO_FACTOR_DEFAULT = 2.0

# Inverter modulation/frequency defaults for FOVIC class wiring
FOVIC_FREQ_HZ_DEFAULT = GRID_FREQ_HZ_DEFAULT
FOVIC_V_LN_RMS_DEFAULT = GRID_V_LN_RMS_DEFAULT
FOVIC_THETA0_RAD_DEFAULT = GRID_THETA0_RAD_DEFAULT
FOVIC_MODULATION_INDEX_MAX_DEFAULT = INVERTER_MODULATION_INDEX_MAX_DEFAULT

# ------------------------------
# Microgrid operating defaults
# ------------------------------
MICROGRID_PV_VOC_STC_V_DEFAULT = 50.0
MICROGRID_PV_ISC_STC_A_DEFAULT = 14.0
MICROGRID_PV_VMP_STC_V_DEFAULT = 42.0
MICROGRID_PV_IMP_STC_A_DEFAULT = 13.1
MICROGRID_PV_NS_CELLS_DEFAULT = 72
MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT = 0.005
MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT = -0.14
MICROGRID_PV_DIODE_IDEALITY_DEFAULT = 1.25
MICROGRID_PV_RS_OHM_DEFAULT = 0.25
MICROGRID_PV_RSH_OHM_DEFAULT = 200.0
MICROGRID_PV_ARRAY_SERIES_DEFAULT = 8
MICROGRID_PV_ARRAY_PARALLEL_DEFAULT = 1

MICROGRID_ETA_DEFAULT = 0.97
MICROGRID_UVLO_V_DEFAULT = 200.0
MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT = 800.0
MICROGRID_TEMPERATURE_C_DEFAULT = 25.0
MICROGRID_LOAD_STEP_TIME_S_DEFAULT = 0.8
MICROGRID_LOAD_R1_OHM_DEFAULT = 14.4
MICROGRID_LOAD_R2_OHM_DEFAULT = 9.6
# Potencia de referencia VSG por defecto (calculada externamente en Microgrid.__init__)
# Se deja como documentacion del valor esperado @ STC
MICROGRID_P_REF_NOMINAL_W_DEFAULT = (
    MICROGRID_PV_VMP_STC_V_DEFAULT
    * MICROGRID_PV_IMP_STC_A_DEFAULT
    * MICROGRID_PV_ARRAY_SERIES_DEFAULT
    * MICROGRID_PV_ARRAY_PARALLEL_DEFAULT
    * MICROGRID_ETA_DEFAULT
)

# ------------------------------
# BESS coupled-to-DC defaults (first integration step)
# ------------------------------
BESS_COUPLED_KP_DEFAULT = 0.5
BESS_COUPLED_I_MAX_DEFAULT = 66.0
BESS_COUPLED_SOC_INIT_DEFAULT = 0.6
BESS_COUPLED_R0_DEFAULT = 0.000970
BESS_COUPLED_Q_NOM_REF_AH_DEFAULT = 66.0
BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT = 44.1

# ------------------------------
# Simulation defaults
# ------------------------------
SIM_T_START_S_DEFAULT = 0.0
SIM_T_END_S_DEFAULT = 2.0
SIM_VDC0_V_DEFAULT = 340.0
SIM_SOLVER_MAX_STEP_S_DEFAULT = 5e-5
SIM_SOLVER_RTOL_DEFAULT = 1e-6
SIM_SOLVER_ATOL_DEFAULT = 1e-8
SIM_SS_WINDOW_FRACTION = 0.75
PV_CURVE_IRRADIANCE_LEVELS_W_PER_M2 = (1000.0, 800.0, 400.0)


def validate_default_dc_bus_consistency(
    v_ln_rms: float = GRID_V_LN_RMS_DEFAULT,
    m_max: float = INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    vdc0: float = SIM_VDC0_V_DEFAULT,
    context: str = "baseline-defaults",
) -> float:
    """
    Validate baseline DC-link nominal consistency against AC voltage target.

    Returns:
        Minimum required DC-link voltage [V].
    """
    if m_max <= 0.0:
        raise ValueError("INVERTER_MODULATION_INDEX_MAX_DEFAULT must be > 0.")

    v_phase_peak_required = np.sqrt(2.0) * v_ln_rms
    vdc_min_required = 2.0 * v_phase_peak_required / m_max

    if vdc0 < vdc_min_required:
        warnings.warn(
            (
                f"[{context}] DC-link inconsistency: SIM_VDC0_V_DEFAULT={vdc0:.2f} V "
                f"is below required minimum {vdc_min_required:.2f} V for "
                f"GRID_V_LN_RMS_DEFAULT={v_ln_rms:.2f} V and "
                f"INVERTER_MODULATION_INDEX_MAX_DEFAULT={m_max:.3f}."
            ),
            RuntimeWarning,
            stacklevel=2,
        )

    return vdc_min_required


SIM_VDC_MIN_REQUIRED_V_DEFAULT = validate_default_dc_bus_consistency(
    v_ln_rms=GRID_V_LN_RMS_DEFAULT,
    m_max=INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    vdc0=SIM_VDC0_V_DEFAULT,
    context="config",
)

# ------------------------------
# IEEE 33 + microrred defaults
# ------------------------------
IEEE33_VN_KV = 12.66
IEEE33_PCC_BUS_IDX = 17  # base-0 index (Nodo 18)
IEEE33_PCC_BUS_NAME = "Nodo 18"
MICROGRID_PF_DEFAULT = 1.0
MICROGRID_SGEN_NAME = "Microrred_PV_Baseline"
