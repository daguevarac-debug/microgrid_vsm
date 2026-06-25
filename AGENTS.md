# AGENTS.md

## Project overview

This repository contains a thesis model of a photovoltaic microgrid with a
second-life battery system, DC link, averaged inverter, LCL filter, aggregated
three-phase R-L load, grid-following baseline control, and an integrated
classical grid-forming controller. The local dynamic model is coupled to the
IEEE 33-bus system through sequential one-way postprocessing.

Current implemented scope:

- PV array and single-diode model;
- DC-link dynamics;
- averaged inverter source;
- LCL filter;
- balanced aggregated R-L load;
- nominal 3 kW load at 0.95 lagging power factor;
- nominal, +20%, and +40% load scenarios;
- `GridFollowingController` baseline path;
- integrated `GFMController` classical VSG path;
- reduced swing dynamics with dynamic `omega` and `theta`;
- selected integrated GFM point `M = 80`, `D = 1500`;
- BESS-SLB Thevenin 1RC model with first-order degradation;
- SoC, SoH, current, and power supervision;
- BESS coupling to the DC link;
- optional `MicrogridWithBESSPI` external DC-link PI with saturation and
  conditional anti-windup;
- integrated GFM/BESS scenario validation;
- sequential one-way IEEE 33 coupling with active GFM;
- Objective 1 and Objective 2 formal closure documentation.

Not yet implemented:

- final FOVIC or fractional-order strategy;
- final comparison among VSG, FOVIC, droop, and V-f control;
- detailed bidirectional DC/DC converter;
- industrial final BMS logic, thermal model, balancing, and protections;
- complete inner voltage/current loops and Q-V control;
- formal full stability proof and global tuning optimization;
- measured operating profiles and experimental/HIL validation;
- bidirectional dynamic co-simulation with IEEE 33.

## Main engineering intent

This codebase is part of a research thesis. Changes must preserve scientific
traceability, physical consistency, explicit architecture decisions, and future
extensibility.

## Non-negotiable rules

1. Do not change physical equations unless explicitly requested and documented.
2. Do not change sign conventions for power, current, voltage, or control
   signals without updating all diagnostics and validations.
3. Do not silently change the state vector order or reinterpret any state.
4. Do not add a second or nested `solve_ivp` for GFM, BESS, or PI dynamics.
5. Plant, controller, angle, frequency, BESS states, and optional PI state must
   be integrated by one global solver.
6. Do not rename public entrypoints without backward-compatible aliases.
7. Do not remove thesis TODOs unless the corresponding work is actually closed.
8. Do not change the DC-link equation:
   `dVdc/dt = (ipv + i_bess - idc_inv)/Cdc`.
9. Preserve the BESS convention `i_bess > 0` for discharge and `i_bess < 0`
   for charge.
10. Preserve `p_bess_dc = Vdc*i_bess`.
11. Do not remove SoC, SoH, current, or power limits from the BESS path.
12. Do not change LCL equations or parameters without updating
    `docs/model_assumptions.md` and running the protected LCL validation.
13. Do not change load parameters or perturbations without updating the model
    assumptions and load/scenario validations.
14. Preserve the grid-following path as an Objective 1 regression path.
15. `GFMController` is the active controller for integrated GFM campaigns; do
    not replace it silently with an ideal sinusoidal source or grid-following PI.
16. Do not infer the meaning of `x[10]` from vector length. Resolve it from the
    active controller or explicit state layout.
17. In grid-following mode, `x[10] = xi_vdc`.
18. In GFM mode, `x[10] = omega`.
19. `x[11] = theta` in both controller modes.
20. Do not keep both `xi_vdc` and `omega` in the first 12 or 15 states. That
    would define a different hybrid architecture.
21. The optional BESS DC-link PI state may only be appended at `x[15]` in the
    explicit 16-state architecture.
22. GFM initial conditions must use `omega(0) = omega_ref` and
    `theta(0) = theta0`.
23. Dynamic GFM frequency must be derived as `frequency_hz = omega/(2*pi)`.
24. Do not use a fixed nominal frequency trace as a GFM dynamic metric.
25. Frequency metrics are valid only when `controller_state_name == "omega"`
    and `GFMController` is active.
26. Preserve the classical GFM equation:
    `domega/dt = (P_ref - P_e - D*(omega - omega_ref))/M`.
27. Preserve `dtheta/dt = omega`.
28. Use the complete R-L PCC voltage in GFM feedback and calculate
    `P_e = v_pcc^T*i2`.
29. Do not silently change the selected integrated point `M = 80`, `D = 1500`;
    a new point requires a documented tuning decision and rerun of validations.
30. Keep BESS supervision inputs to `GFMController` consistent: SoC, SoH,
    available current, available power, and signed actual BESS DC power.
31. Charging power must reduce net available GFM active power; discharging power
    may increase support only within available limits.
32. Do not treat a `REVIEW` result as a software failure when the solver,
    states, and physical invariants pass.
33. The integrated 40% load-step `REVIEW` is a documented DC-link performance
    limitation, not evidence of a broken controller.
34. Preserve Objective 1 regressions when changing Objective 2 code.
35. IEEE 33 coupling remains sequential one-way. Do not describe it as dynamic
    co-simulation or bidirectional feedback.
36. `p_ss_kw` for IEEE 33 must remain the mean of `p_pcc` over the configured
    steady-state window.
37. Do not move physical logic into plotting or reporting modules.
38. Do not present FOVIC, detailed DC/DC, final BMS, or experimental validation
    as implemented.

## Protected state vector mappings

These state orders are protected until an explicit architecture change is
approved.

```text
Grid-following without BESS, 12 states:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, xi_vdc, theta]

GFM without BESS, 12 states:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta]

Grid-following with BESS, 15 states:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, xi_vdc, theta,
 soc_bess, vrc_bess, zdeg_bess]

GFM with BESS, 15 states:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess]

GFM with BESS and external DC-link PI, 16 states:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
```

Additional protections:

- `x[0:10]` retains the same plant meaning in all modes.
- BESS states remain at `x[12]`, `x[13]`, and `x[14]`.
- `MicrogridWithBESSPI.bess_pi_state_index` remains `15`.
- `MicrogridWithBESSPI.state_count_with_bess_pi` remains `16`.
- The PI state is appended; it does not shift any protected plant, GFM, or BESS
  state.
- Initialization, dynamics, diagnostics, documentation, and validation must be
  updated together for any approved state-layout change.

## GFM controller protections

`GFMController` is the implemented classical VSG controller for Objective 2.
It must remain compatible with `InverterControllerBase` and return the standard
`ControlOutput` fields.

Protected behavior:

- `controller_state_name = "omega"`;
- `initial_controller_state()` returns `omega_ref`;
- `d_xi_vdc_dt` in the compatibility output carries `domega/dt` in GFM mode;
- `d_theta_dt` carries `omega`;
- `p_pcc`/`P_e` is calculated from complete PCC voltage and output current;
- active-power reference is limited by net DC-side availability;
- UVLO preserves zero bridge power and zero inverter DC current below threshold;
- DC current remains unidirectional from DC to AC in the current averaged
  baseline convention.

The implemented VSG controller is not the final FOVIC contribution.

## Dynamic frequency metric rules

For GFM simulations:

- `omega = x[10]` [rad/s];
- `frequency_hz = omega/(2*pi)` [Hz];
- nominal frequency is `omega_ref/(2*pi)`;
- frequency nadir, peak, deviation, RoCoF, and settling metrics must be calculated
  from the dynamic `omega` trajectory;
- pre-event and post-event windows must be stated explicitly;
- a metric is invalid if the controller is not GFM-active or if the state mapping
  is not `omega`;
- frequency criteria and DC-link criteria must be reported separately;
- a scenario may be `REVIEW` when execution passes but one design criterion does
  not.

## BESS-SLB mandatory conventions

### Capacity convention

- `q_nom_ref_ah = 66 Ah`.
- `q_init_case_ah` is case-dependent.
- `soh_init_case = q_init_case_ah/q_nom_ref_ah`.
- `Q_eff(0) = q_init_case_ah`.
- Braco (2020, 2021) supports the 66 Ah/1C reference.
- Tran (2021) is not the source for the 66 Ah reference.

### Protected battery equations

```text
V_t = OCV(SoC) - i*R0(SoH) - V_rc
dV_rc/dt = -V_rc/(R1*C1) + i/C1
dSoC/dt = -i/(3600*Q_eff)
dz_deg/dt = |i|/3600
SoH = max(soh_min, SoH_0 - k_deg*z_deg)
Q_eff = Q_nom*SoH
R0 = R0_nom*(1 + k_R*(1-SoH))
```

### Operational limits

- `soc_min = 0.10`.
- `soc_max = 0.90`.
- `i_bess_max_nominal = 66 A`.
- `p_bess_dc_max_nominal = 22440 W`.
- `i_bess_max_available = i_bess_max_nominal*SoH`.
- `p_bess_dc_max_available = min(p_bess_dc_max_nominal,
  Vdc_ref*i_bess_max_available)`.
- Discharge is blocked at the lower SoC boundary.
- Charge is blocked at the upper SoC boundary.

A `REVIEW` caused only by `Vdc/vt_bess` scale is an interpretation warning, not
numerical failure.

## External DC-link PI protections

`MicrogridWithBESSPI` appends `xi_bess_vdc` at `x[15]`.

- The PI produces a signed BESS power reference.
- The reference is limited by SoC, SoH, current, and power constraints.
- Conversion from power to current uses the protected BESS sign convention.
- Conditional anti-windup must prevent integration deeper into saturation.
- `bess_enabled=False` must force zero charge/discharge request.
- The PI must not modify the VSG equations or the protected `M` and `D` values.

## IEEE 33 coupling rules

- PCC bus index is 17, corresponding to bus 18.
- Nominal network voltage is 12.66 kV.
- The local microgrid is simulated first.
- `p_ss_kw` is the arithmetic mean of `p_pcc` in the steady-state window.
- That scalar is injected as a static `sgen` for pandapower.
- The IEEE 33 network does not provide dynamic feedback to the local ODE.
- Voltage-profile and line-loading results are static network postprocessing.
- Final GFM figure path:
  `outputs/validation/figures_final/ieee33_microgrid_resultado.png`.

## Preferred workflow

Before making edits:

1. inspect relevant implementation and validation files;
2. identify the active controller and state layout;
3. state which files will change;
4. make conservative edits;
5. run only the validations relevant to the change;
6. report compatibility and regression risks.

For documentation-only changes, do not rerun heavy simulations unless the
content depends on a new numerical result.

## Required validation groups

### Objective 1 regression

```bash
python src/validation/validate_obj1_regression.py
```

This consolidates:

- `validate_lcl_no_unphysical_oscillations.py`;
- `validate_bess_step3.py`;
- `validate_bess_soc_operational_limits.py`.

### Integrated GFM

```bash
python src/validation/validate_gfm_integrated_system.py
python src/validation/validate_physical_invariants.py
```

### IEEE 33 with GFM

```bash
python src/validation/validate_ieee33_gfm_pcc_average.py
python src/validation/validate_ieee33_gfm_voltage_profile.py
```

### Baseline and BESS validations

```bash
python src/validation/validate_pv_stc_fit.py
python src/validation/validate_microgrid_rl_load.py
python src/validation/validate_islanded_operation_scenarios.py
python src/validation/validate_bess_step2.py
python src/validation/validate_bess_step3.py
python src/validation/validate_bess_soc_operational_limits.py
```

## Public compatibility expectations

Preserve these imports:

- `from microgrid import Microgrid`;
- `from microgrid import MicrogridWithBESS`;
- `from microgrid_bess_pi import MicrogridWithBESSPI`;
- `from controllers.gfm_controller import GFMController`;
- `from ieee33_coupling import IEEE33Microgrid`;
- `from ieee33_coupling import IEEE33MicrogridWithBESS`;
- `from bess.model import SecondLifeBattery1RC`;
- `from bess import SecondLifeBattery1RC`;
- backward-compatible BESS characterization shims.

## Repository responsibilities

- `src/config.py`: central numerical constants.
- `src/microgrid.py`: physical plant composition and 12/15-state assembly.
- `src/microgrid_bess_pi.py`: explicit 16-state BESS PI architecture.
- `src/controllers/grid_following.py`: Objective 1 baseline controller.
- `src/controllers/grid_forming.py`: reduced swing-frequency dynamics.
- `src/controllers/gfm_controller.py`: integrated classical GFM controller.
- `src/controllers/dc_link_bess_pi.py`: external BESS DC-link PI.
- `src/ieee33_coupling.py`: sequential one-way network coupling.
- `src/ieee33_plots.py`: visualization only.
- `src/validation/`: reproducible internal evidence.
- `docs/model_assumptions.md`: assumptions and limitations.
- `docs/objective_1_closure_criteria.md`: Objective 1 closure.
- `docs/objective_2_closure_criteria.md`: Objective 2 closure.
- `docs/grid_forming_minimal_structure.md`: implemented GFM structure.
- `docs/grid_forming_plant_control_interface.md`: current plant-control interface.

## Thesis-specific caution

- Do not present internal validation as experimental validation.
- Do not present the 40% `REVIEW` as a software failure.
- Do not present VSG classical integration as FOVIC.
- Do not present the preliminary BESS/DC-link interface as a detailed DC/DC
  converter.
- Do not present the simplified supervision layer as a commercial BMS.
- Do not present IEEE 33 postprocessing as dynamic co-simulation.
- Be explicit about what is implemented, validated, limited, and future work.

## Style guidance

- Prefer clear technical names.
- Use type hints where practical.
- Keep comments concise and physically meaningful.
- Keep control separate from plant physics.
- Keep plotting and reporting separate from dynamics.
- Preserve scientific readability over software cleverness.