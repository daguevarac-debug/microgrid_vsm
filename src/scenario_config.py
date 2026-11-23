"""Modular scenario configuration selector for microgrid, VSG, and BESS-SLB.

Allows defining a simulation scenario from a JSON configuration file or
dictionary, reusing the existing physical modules without changing protected
state layouts, sign conventions, or the global ``solve_ivp`` solver.

Parameter-set separation:
- Constructor defaults: physical constants in ``config.py`` and class defaults.
- Selector reference scenario (``default_scenario_config`` /
  ``default_gfm_bess_pi_scenario.json``): preserves ``Kp=20.0, Ki=200.0`` and
  ``t_end_s=2.0`` for historical selector baseline equivalence.
- Integrated GFM scientific campaign (``integrated_gfm_bess_pi_step20_scenario.json``):
  uses ``Kp=170.0, Ki=10.0`` and ``t_end_s=6.5`` matching Task 5.3 /
  ``validate_gfm_integrated_system.py``.

Note:
    Replacing the BESS lookup table or parameters with experimentally
    characterized data parametrizes ``SecondLifeBattery1RC`` for simulation; it
    does not by itself constitute experimental validation of the microgrid.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Callable

from bess.lookup_table import DEFAULT_TRAN_LOOKUP_TABLE, OCVR1C1LookupTable
from bess.model import SecondLifeBattery1RC
from config import (
    BESS_COUPLED_I_MAX_DEFAULT,
    BESS_COUPLED_KP_DEFAULT,
    BESS_COUPLED_P_MAX_W_DEFAULT,
    BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
    BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
    BESS_COUPLED_R0_DEFAULT,
    BESS_COUPLED_SOC_INIT_DEFAULT,
    BESS_COUPLED_SOC_MAX_DEFAULT,
    BESS_COUPLED_SOC_MIN_DEFAULT,
    GRID_FREQ_HZ_DEFAULT,
    GRID_THETA0_RAD_DEFAULT,
    GRID_V_LN_RMS_DEFAULT,
    INVERTER_MODULATION_INDEX_MAX_DEFAULT,
    MICROGRID_ETA_DEFAULT,
    MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
    MICROGRID_LOAD_P_NOM_W_DEFAULT,
    MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
    MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
    MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
    MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
    MICROGRID_PV_ARRAY_PARALLEL_DEFAULT,
    MICROGRID_PV_ARRAY_SERIES_DEFAULT,
    MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
    MICROGRID_PV_DIODE_IDEALITY_DEFAULT,
    MICROGRID_PV_IMP_STC_A_DEFAULT,
    MICROGRID_PV_ISC_STC_A_DEFAULT,
    MICROGRID_PV_NS_CELLS_DEFAULT,
    MICROGRID_PV_RSH_OHM_DEFAULT,
    MICROGRID_PV_RS_OHM_DEFAULT,
    MICROGRID_PV_VMP_STC_V_DEFAULT,
    MICROGRID_PV_VOC_STC_V_DEFAULT,
    MICROGRID_TEMPERATURE_C_DEFAULT,
    SIM_SOLVER_ATOL_DEFAULT,
    SIM_SOLVER_MAX_STEP_S_DEFAULT,
    SIM_SOLVER_RTOL_DEFAULT,
    SIM_T_END_S_DEFAULT,
    SIM_T_START_S_DEFAULT,
    SIM_VDC0_V_DEFAULT,
)
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from microgrid import Microgrid, MicrogridWithBESS
from microgrid_bess_pi import MicrogridWithBESSPI
from pv_model import PVArrayParams, PVModuleParams

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GFM_M = 80.0
DEFAULT_GFM_D = 1500.0
DEFAULT_BESS_PI_KP_W_PER_V = 20.0
DEFAULT_BESS_PI_KI_W_PER_V_S = 200.0
DEFAULT_BESS_K_DEG = 1.478e-6
DEFAULT_BESS_SOH_MIN = 0.50
DEFAULT_BESS_R0_SOH_SENSITIVITY = 1.0


def default_scenario_config() -> dict[str, Any]:
    """Return a deep copy of the default scenario matching protected defaults."""
    return deepcopy(
        {
            "schema_version": 1,
            "name": "default_gfm_bess_pi",
            "pv": {
                "voc_stc": MICROGRID_PV_VOC_STC_V_DEFAULT,
                "isc_stc": MICROGRID_PV_ISC_STC_A_DEFAULT,
                "vmp_stc": MICROGRID_PV_VMP_STC_V_DEFAULT,
                "imp_stc": MICROGRID_PV_IMP_STC_A_DEFAULT,
                "ns_cells": MICROGRID_PV_NS_CELLS_DEFAULT,
                "alpha_isc": MICROGRID_PV_ALPHA_ISC_A_PER_C_DEFAULT,
                "beta_voc": MICROGRID_PV_BETA_VOC_V_PER_C_DEFAULT,
                "n": MICROGRID_PV_DIODE_IDEALITY_DEFAULT,
                "rs": MICROGRID_PV_RS_OHM_DEFAULT,
                "rsh": MICROGRID_PV_RSH_OHM_DEFAULT,
                "modules_in_series": MICROGRID_PV_ARRAY_SERIES_DEFAULT,
                "strings_in_parallel": MICROGRID_PV_ARRAY_PARALLEL_DEFAULT,
            },
            "environment": {
                "irradiance": {
                    "type": "constant",
                    "value": MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT,
                },
                "temperature_c": {
                    "type": "constant",
                    "value": MICROGRID_TEMPERATURE_C_DEFAULT,
                },
            },
            "load": {
                "p_nominal_w": MICROGRID_LOAD_P_NOM_W_DEFAULT,
                "power_factor": MICROGRID_LOAD_POWER_FACTOR_DEFAULT,
                "step_fraction": MICROGRID_LOAD_STEP_MODERATE_FRACTION_DEFAULT,
                "t_step_s": MICROGRID_LOAD_STEP_TIME_S_DEFAULT,
                "profile": None,
            },
            "vsg": {
                "M": DEFAULT_GFM_M,
                "D": DEFAULT_GFM_D,
                "f_hz": GRID_FREQ_HZ_DEFAULT,
                "v_ln_rms": GRID_V_LN_RMS_DEFAULT,
                "vdc_ref": SIM_VDC0_V_DEFAULT,
                "theta0": GRID_THETA0_RAD_DEFAULT,
                "m_base": INVERTER_MODULATION_INDEX_MAX_DEFAULT,
                "p_ref_w": None,
            },
            "bess": {
                "enabled": True,
                "mode": "with_pi",
                "characterization_source": "excel",
                "excel_path": None,
                "lookup_table": None,
                "q_nom_ref_ah": BESS_COUPLED_Q_NOM_REF_AH_DEFAULT,
                "q_init_case_ah": BESS_COUPLED_Q_INIT_CASE_AH_DEFAULT,
                "r0_nominal_ohm": BESS_COUPLED_R0_DEFAULT,
                "r0_soh_sensitivity": DEFAULT_BESS_R0_SOH_SENSITIVITY,
                "k_deg": DEFAULT_BESS_K_DEG,
                "soh_min": DEFAULT_BESS_SOH_MIN,
                "soc_initial": BESS_COUPLED_SOC_INIT_DEFAULT,
                "soc_min": BESS_COUPLED_SOC_MIN_DEFAULT,
                "soc_max": BESS_COUPLED_SOC_MAX_DEFAULT,
                "i_bess_max_a": BESS_COUPLED_I_MAX_DEFAULT,
                "p_bess_max_w": BESS_COUPLED_P_MAX_W_DEFAULT,
                "kp_bess": BESS_COUPLED_KP_DEFAULT,
                "pi": {
                    "kp_w_per_v": DEFAULT_BESS_PI_KP_W_PER_V,
                    "ki_w_per_v_s": DEFAULT_BESS_PI_KI_W_PER_V_S,
                },
            },
            "simulation": {
                "vdc0_v": SIM_VDC0_V_DEFAULT,
                "t_start_s": SIM_T_START_S_DEFAULT,
                "t_end_s": SIM_T_END_S_DEFAULT,
                "max_step_s": SIM_SOLVER_MAX_STEP_S_DEFAULT,
                "rtol": SIM_SOLVER_RTOL_DEFAULT,
                "atol": SIM_SOLVER_ATOL_DEFAULT,
            },
        }
    )


def _finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number, got {value!r}.")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return out


def _positive_number(name: str, value: Any) -> float:
    out = _finite_number(name, value)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0, got {value!r}.")
    return out


def _nonnegative_number(name: str, value: Any) -> float:
    out = _finite_number(name, value)
    if out < 0.0:
        raise ValueError(f"{name} must be >= 0, got {value!r}.")
    return out


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}.")
    return value


def _nonempty_str(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string, got {value!r}.")
    return value


def _merge_section(defaults: dict[str, Any], overrides: Any, section_name: str) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        raise ValueError(f"{section_name} must be an object, got {type(overrides).__name__}.")
    unknown = set(overrides) - set(defaults)
    if unknown:
        raise ValueError(f"{section_name}: unsupported fields {sorted(unknown)}.")
    merged = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(defaults[key], dict) and value is not None:
            if key in ("irradiance", "temperature_c", "lookup_table", "profile"):
                merged[key] = deepcopy(value)
            else:
                merged[key] = _merge_section(defaults[key], value, f"{section_name}.{key}")
        else:
            merged[key] = deepcopy(value)
    return merged


def _build_profile_callable(
    name: str,
    spec: dict[str, Any],
    *,
    min_value: float | None = None,
) -> Callable[[float], float]:
    if not isinstance(spec, dict) or "type" not in spec:
        raise ValueError(f"{name} must be an object with a 'type' field.")
    kind = spec["type"]
    if kind == "constant":
        if set(spec) != {"type", "value"}:
            raise ValueError(f"{name}: constant profile requires fields {{'type', 'value'}}.")
        val = _finite_number(f"{name}.value", spec["value"])
        if min_value is not None and val < min_value:
            raise ValueError(f"{name}.value must be >= {min_value}, got {val}.")
        return lambda _t, _val=val: _val

    if kind == "step":
        if set(spec) != {"type", "initial", "final", "t_step_s"}:
            raise ValueError(
                f"{name}: step profile requires fields {{'type', 'initial', 'final', 't_step_s'}}."
            )
        v0 = _finite_number(f"{name}.initial", spec["initial"])
        v1 = _finite_number(f"{name}.final", spec["final"])
        t_step = _positive_number(f"{name}.t_step_s", spec["t_step_s"])
        if min_value is not None and (v0 < min_value or v1 < min_value):
            raise ValueError(f"{name}: step values must be >= {min_value}.")
        return lambda t, _v0=v0, _v1=v1, _ts=t_step: _v0 if t < _ts else _v1

    if kind == "piecewise_linear":
        if set(spec) != {"type", "points"}:
            raise ValueError(f"{name}: piecewise_linear profile requires fields {{'type', 'points'}}.")
        pts = spec["points"]
        if not isinstance(pts, list) or len(pts) < 2:
            raise ValueError(f"{name}.points must be a list of at least 2 [t, value] pairs.")
        times: list[float] = []
        values: list[float] = []
        for idx, pair in enumerate(pts):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f"{name}.points[{idx}] must be [t, value].")
            t_i = _finite_number(f"{name}.points[{idx}][0]", pair[0])
            v_i = _finite_number(f"{name}.points[{idx}][1]", pair[1])
            if min_value is not None and v_i < min_value:
                raise ValueError(f"{name}.points[{idx}][1] must be >= {min_value}, got {v_i}.")
            if times and t_i <= times[-1]:
                raise ValueError(f"{name}.points times must be strictly increasing.")
            times.append(t_i)
            values.append(v_i)

        def _interp(t: float, _ts=times, _vs=values) -> float:
            if t <= _ts[0]:
                return _vs[0]
            if t >= _ts[-1]:
                return _vs[-1]
            for j in range(len(_ts) - 1):
                if _ts[j] <= t <= _ts[j + 1]:
                    frac = (t - _ts[j]) / (_ts[j + 1] - _ts[j])
                    return _vs[j] + frac * (_vs[j + 1] - _vs[j])
            return _vs[-1]

        return _interp

    raise ValueError(
        f"{name}: unsupported profile type {kind!r}; expected 'constant', 'step', or 'piecewise_linear'."
    )


def validate_scenario_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a scenario configuration dictionary."""
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario config must be a dict, got {type(raw).__name__}.")
    defaults = default_scenario_config()
    unknown_top = set(raw) - set(defaults)
    if unknown_top:
        raise ValueError(f"Scenario config: unsupported top-level fields {sorted(unknown_top)}.")
    if "schema_version" in raw:
        sv = raw["schema_version"]
        if isinstance(sv, bool) or not isinstance(sv, int) or sv != 1:
            raise ValueError(f"Only schema_version=1 is supported, got {sv!r}.")

    cfg = deepcopy(defaults)
    if "name" in raw:
        cfg["name"] = _nonempty_str("name", raw["name"])
    for sec in ("pv", "environment", "load", "vsg", "bess", "simulation"):
        if sec in raw and raw[sec] is not None:
            cfg[sec] = _merge_section(defaults[sec], raw[sec], sec)

    # Validate environment profiles
    _build_profile_callable("environment.irradiance", cfg["environment"]["irradiance"], min_value=0.0)
    _build_profile_callable("environment.temperature_c", cfg["environment"]["temperature_c"])

    # Validate load
    ld = cfg["load"]
    _positive_number("load.p_nominal_w", ld["p_nominal_w"])
    pf = _positive_number("load.power_factor", ld["power_factor"])
    if pf > 1.0:
        raise ValueError(f"load.power_factor must be in (0, 1], got {pf}.")
    sf = _nonnegative_number("load.step_fraction", ld["step_fraction"])
    if sf >= 1.0:
        raise ValueError(f"load.step_fraction must be in [0, 1), got {sf}.")
    _positive_number("load.t_step_s", ld["t_step_s"])
    if ld["profile"] is not None:
        _build_profile_callable("load.profile", ld["profile"], min_value=1e-9)

    # Validate PV
    pv = cfg["pv"]
    PVArrayParams(
        module=PVModuleParams(
            voc_stc=_positive_number("pv.voc_stc", pv["voc_stc"]),
            isc_stc=_positive_number("pv.isc_stc", pv["isc_stc"]),
            vmp_stc=_positive_number("pv.vmp_stc", pv["vmp_stc"]),
            imp_stc=_positive_number("pv.imp_stc", pv["imp_stc"]),
            ns_cells=_positive_int("pv.ns_cells", pv["ns_cells"]),
            alpha_isc=_finite_number("pv.alpha_isc", pv["alpha_isc"]),
            beta_voc=_finite_number("pv.beta_voc", pv["beta_voc"]),
            n=_positive_number("pv.n", pv["n"]),
            rs=_positive_number("pv.rs", pv["rs"]),
            rsh=_positive_number("pv.rsh", pv["rsh"]),
        ),
        modules_in_series=_positive_int("pv.modules_in_series", pv["modules_in_series"]),
        strings_in_parallel=_positive_int("pv.strings_in_parallel", pv["strings_in_parallel"]),
    )

    # Validate VSG
    vsg = cfg["vsg"]
    _positive_number("vsg.M", vsg["M"])
    _nonnegative_number("vsg.D", vsg["D"])
    _positive_number("vsg.f_hz", vsg["f_hz"])
    _positive_number("vsg.v_ln_rms", vsg["v_ln_rms"])
    _positive_number("vsg.vdc_ref", vsg["vdc_ref"])
    _finite_number("vsg.theta0", vsg["theta0"])
    _positive_number("vsg.m_base", vsg["m_base"])
    if vsg["p_ref_w"] is not None:
        _nonnegative_number("vsg.p_ref_w", vsg["p_ref_w"])

    # Validate BESS
    bess = cfg["bess"]
    if not isinstance(bess["enabled"], bool):
        raise ValueError(f"bess.enabled must be bool, got {bess['enabled']!r}.")
    if bess["mode"] not in ("with_pi", "coupled_proportional", "none"):
        raise ValueError(
            f"bess.mode must be 'with_pi', 'coupled_proportional', or 'none', got {bess['mode']!r}."
        )
    if bess["characterization_source"] not in ("excel", "lookup_table", "default_tran_placeholder"):
        raise ValueError(
            "bess.characterization_source must be 'excel', 'lookup_table', or "
            f"'default_tran_placeholder', got {bess['characterization_source']!r}."
        )
    if bess["characterization_source"] == "lookup_table":
        lt = bess["lookup_table"]
        if not isinstance(lt, dict):
            raise ValueError("bess.lookup_table must be provided when characterization_source='lookup_table'.")
        req_lt = {"soc_data", "ocv_data", "r1_data", "c1_data"}
        allowed_lt = req_lt | {"source_reference"}
        if not req_lt.issubset(lt) or (set(lt) - allowed_lt):
            raise ValueError(
                "bess.lookup_table must contain soc_data, ocv_data, r1_data, c1_data "
                "(and optional source_reference)."
            )
        OCVR1C1LookupTable(
            soc_data=lt["soc_data"],
            ocv_data=lt["ocv_data"],
            r1_data=lt["r1_data"],
            c1_data=lt["c1_data"],
            source_reference=str(lt.get("source_reference", "Custom/Experimental parameterization")),
        )
    elif bess["lookup_table"] is not None:
        raise ValueError("bess.lookup_table may only be set when characterization_source='lookup_table'.")

    soc_min = _finite_number("bess.soc_min", bess["soc_min"])
    soc_max = _finite_number("bess.soc_max", bess["soc_max"])
    soc_init = _finite_number("bess.soc_initial", bess["soc_initial"])
    if not (0.0 <= soc_min < soc_max <= 1.0):
        raise ValueError(f"Require 0 <= soc_min < soc_max <= 1, got [{soc_min}, {soc_max}].")
    if not (soc_min <= soc_init <= soc_max):
        raise ValueError(f"bess.soc_initial ({soc_init}) must lie within [{soc_min}, {soc_max}].")
    _positive_number("bess.q_nom_ref_ah", bess["q_nom_ref_ah"])
    _positive_number("bess.q_init_case_ah", bess["q_init_case_ah"])
    _positive_number("bess.r0_nominal_ohm", bess["r0_nominal_ohm"])
    _nonnegative_number("bess.r0_soh_sensitivity", bess["r0_soh_sensitivity"])
    _nonnegative_number("bess.k_deg", bess["k_deg"])
    soh_min = _positive_number("bess.soh_min", bess["soh_min"])
    if soh_min > 1.0:
        raise ValueError(f"bess.soh_min must be <= 1.0, got {soh_min}.")
    _positive_number("bess.i_bess_max_a", bess["i_bess_max_a"])
    _positive_number("bess.p_bess_max_w", bess["p_bess_max_w"])
    _positive_number("bess.kp_bess", bess["kp_bess"])
    _nonnegative_number("bess.pi.kp_w_per_v", bess["pi"]["kp_w_per_v"])
    _nonnegative_number("bess.pi.ki_w_per_v_s", bess["pi"]["ki_w_per_v_s"])
    if bess["mode"] == "coupled_proportional" and not bess["enabled"]:
        raise ValueError(
            "bess.enabled=False is not supported when bess.mode='coupled_proportional'; "
            "use bess.mode='none' or bess.mode='with_pi'."
        )

    # Validate simulation
    sim = cfg["simulation"]
    _positive_number("simulation.vdc0_v", sim["vdc0_v"])
    t_start = _finite_number("simulation.t_start_s", sim["t_start_s"])
    t_end = _finite_number("simulation.t_end_s", sim["t_end_s"])
    if t_end <= t_start:
        raise ValueError(f"simulation.t_end_s ({t_end}) must be > t_start_s ({t_start}).")
    _positive_number("simulation.max_step_s", sim["max_step_s"])
    _positive_number("simulation.rtol", sim["rtol"])
    _positive_number("simulation.atol", sim["atol"])

    return cfg


def load_scenario_config(path: str | Path) -> dict[str, Any]:
    """Load and validate a scenario JSON file, rejecting duplicate keys."""
    def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"Duplicate JSON key: {k!r}")
            out[k] = v
        return out

    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_keys)
    return validate_scenario_config(raw)


def _build_bess_model(bess_cfg: dict[str, Any]) -> SecondLifeBattery1RC:
    src = bess_cfg["characterization_source"]
    common_kwargs = {
        "q_nom_ref_ah": float(bess_cfg["q_nom_ref_ah"]),
        "q_init_case_ah": float(bess_cfg["q_init_case_ah"]),
        "r0_nominal_ohm": float(bess_cfg["r0_nominal_ohm"]),
        "r0_soh_sensitivity": float(bess_cfg["r0_soh_sensitivity"]),
        "k_deg": float(bess_cfg["k_deg"]),
        "soh_min": float(bess_cfg["soh_min"]),
        "q_eff_min_ah": 1e-9,
        "soc_initial": float(bess_cfg["soc_initial"]),
        "soc_min": float(bess_cfg["soc_min"]),
        "soc_max": float(bess_cfg["soc_max"]),
    }
    if src == "excel":
        excel_path = (
            Path(bess_cfg["excel_path"])
            if bess_cfg["excel_path"] is not None
            else (REPO_ROOT / "OCV_SOC.xlsx")
        )
        return SecondLifeBattery1RC.from_excel_characterization(
            excel_path=excel_path,
            **common_kwargs,
        )
    if src == "lookup_table":
        lt = bess_cfg["lookup_table"]
        table = OCVR1C1LookupTable(
            soc_data=lt["soc_data"],
            ocv_data=lt["ocv_data"],
            r1_data=lt["r1_data"],
            c1_data=lt["c1_data"],
            source_reference=str(lt.get("source_reference", "Custom/Experimental parameterization")),
        )
        return SecondLifeBattery1RC(lookup_table_1rc=table, **common_kwargs)
    return SecondLifeBattery1RC(lookup_table_1rc=DEFAULT_TRAN_LOOKUP_TABLE, **common_kwargs)


def build_microgrid_from_config(
    config: dict[str, Any],
) -> tuple[Microgrid, list[float], dict[str, Any]]:
    """Build the configured microgrid model, initial state vector, and solver settings."""
    cfg = validate_scenario_config(config)
    pv_cfg = cfg["pv"]
    pv_params = PVArrayParams(
        module=PVModuleParams(
            voc_stc=float(pv_cfg["voc_stc"]),
            isc_stc=float(pv_cfg["isc_stc"]),
            vmp_stc=float(pv_cfg["vmp_stc"]),
            imp_stc=float(pv_cfg["imp_stc"]),
            ns_cells=int(pv_cfg["ns_cells"]),
            alpha_isc=float(pv_cfg["alpha_isc"]),
            beta_voc=float(pv_cfg["beta_voc"]),
            n=float(pv_cfg["n"]),
            rs=float(pv_cfg["rs"]),
            rsh=float(pv_cfg["rsh"]),
        ),
        modules_in_series=int(pv_cfg["modules_in_series"]),
        strings_in_parallel=int(pv_cfg["strings_in_parallel"]),
    )

    irradiance_profile = _build_profile_callable(
        "environment.irradiance", cfg["environment"]["irradiance"], min_value=0.0
    )
    temperature_profile = _build_profile_callable(
        "environment.temperature_c", cfg["environment"]["temperature_c"]
    )
    load_cfg = cfg["load"]
    load_profile = (
        _build_profile_callable("load.profile", load_cfg["profile"], min_value=1e-9)
        if load_cfg["profile"] is not None
        else None
    )

    vsg_cfg = cfg["vsg"]
    if vsg_cfg["p_ref_w"] is not None:
        p_ref_w = float(vsg_cfg["p_ref_w"])
    else:
        p_ref_nominal = (
            pv_params.module.vmp_stc
            * pv_params.module.imp_stc
            * pv_params.modules_in_series
            * pv_params.strings_in_parallel
            * MICROGRID_ETA_DEFAULT
        )
        # Match Microgrid.__init__ reference power resolution at t=0.
        probe = Microgrid(
            irradiance_profile=irradiance_profile,
            temperature_profile=temperature_profile,
            pv_params=pv_params,
            vdc_ref=float(vsg_cfg["vdc_ref"]),
            grid_f_hz=float(vsg_cfg["f_hz"]),
            grid_v_ln_rms=float(vsg_cfg["v_ln_rms"]),
        )
        p_ref_w = min(p_ref_nominal, probe.p_available_ref)

    controller = GFMController(
        inertia_m=float(vsg_cfg["M"]),
        damping_d=float(vsg_cfg["D"]),
        f_hz=float(vsg_cfg["f_hz"]),
        v_ln_rms=float(vsg_cfg["v_ln_rms"]),
        theta0=float(vsg_cfg["theta0"]),
        p_ref=p_ref_w,
        m_base=float(vsg_cfg["m_base"]),
    )

    common_mg_kwargs = {
        "irradiance_profile": irradiance_profile,
        "temperature_profile": temperature_profile,
        "load_profile": load_profile,
        "controller": controller,
        "pv_params": pv_params,
        "p_load_nominal_w": float(load_cfg["p_nominal_w"]),
        "load_power_factor": float(load_cfg["power_factor"]),
        "load_step_fraction": float(load_cfg["step_fraction"]),
        "t_step": float(load_cfg["t_step_s"]),
        "vdc_ref": float(vsg_cfg["vdc_ref"]),
        "grid_f_hz": float(vsg_cfg["f_hz"]),
        "grid_v_ln_rms": float(vsg_cfg["v_ln_rms"]),
    }

    bess_cfg = cfg["bess"]
    sim_cfg = cfg["simulation"]
    vdc0 = float(sim_cfg["vdc0_v"])

    if bess_cfg["mode"] == "none":
        model = Microgrid(**common_mg_kwargs)
        y0 = model.initial_state(vdc0=vdc0)
    elif bess_cfg["mode"] == "coupled_proportional":
        bess_model = _build_bess_model(bess_cfg)
        model = MicrogridWithBESS(
            bess_model=bess_model,
            kp_bess=float(bess_cfg["kp_bess"]),
            i_bess_max=float(bess_cfg["i_bess_max_a"]),
            p_bess_max_w=float(bess_cfg["p_bess_max_w"]),
            **common_mg_kwargs,
        )
        y0 = model.initial_state_with_bess(vdc0=vdc0)
    else:
        bess_model = _build_bess_model(bess_cfg)
        dc_link_pi = DCLinkBESSPIController(
            vdc_ref_v=float(vsg_cfg["vdc_ref"]),
            kp_w_per_v=float(bess_cfg["pi"]["kp_w_per_v"]),
            ki_w_per_v_s=float(bess_cfg["pi"]["ki_w_per_v_s"]),
        )
        model = MicrogridWithBESSPI(
            dc_link_bess_pi=dc_link_pi,
            bess_enabled=bool(bess_cfg["enabled"]),
            bess_model=bess_model,
            kp_bess=float(bess_cfg["kp_bess"]),
            i_bess_max=float(bess_cfg["i_bess_max_a"]),
            p_bess_max_w=float(bess_cfg["p_bess_max_w"]),
            **common_mg_kwargs,
        )
        y0 = model.initial_state_with_bess(vdc0=vdc0)

    sim_settings = {
        "t_start_s": float(sim_cfg["t_start_s"]),
        "t_end_s": float(sim_cfg["t_end_s"]),
        "max_step_s": float(sim_cfg["max_step_s"]),
        "rtol": float(sim_cfg["rtol"]),
        "atol": float(sim_cfg["atol"]),
    }
    return model, y0, sim_settings
