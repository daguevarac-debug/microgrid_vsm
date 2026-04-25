# AGENTS.md

## Project overview
This repository contains a thesis baseline for a photovoltaic microgrid dynamically coupled in a one-way sequential manner to the IEEE 33-bus distribution system, with a second-life EV battery (BESS-SLB) dynamic model.

Current implemented scope:
- PV array model
- DC-link dynamics
- LCL filter (baseline-documented in `docs/model_assumptions.md` and practically validated in baseline)
- inverter source and baseline control (grid-following PI)
- local dynamic simulation
- sequential one-way coupling to IEEE 33 at the PCC
- **BESS-SLB Thevenin 1RC dynamic model** with OCV/R1/C1 lookup tables
- **First-order degradation model** (z_deg throughput, SoH linear fade, R0 aging)
- **Excel characterization loader** for OCV/R1/C1 from experimental/literature data
- **Phase-1 static battery model** (capacity, SoH, internal resistance)
- **Preliminary BESS-DC-link integration** through `MicrogridWithBESS`
- **BESS operational constraints** for SoC, current, and DC power
- **SoH-dependent available current and support power**
- **SoH scenario comparison** for integrated BESS support
- **Isolated minimal grid-forming frequency dynamics** (`GridFormingFrequencyDynamics`)
- **Reduced swing/VSG-like frequency equation** for the isolated GFM block
- **Isolated GFM validations** for islanded operation, voltage reference, frequency behavior, and load-step response
- **Plant-control interface documentation** for the transition to Objective 2

Not yet implemented:
- Final BESS integration with detailed DC/DC converter and final BMS logic
- full grid-forming controller integrated into `Microgrid`
- final virtual inertia strategy (VSG/FOVIC) for the thesis contribution
- BESS/BMS-constrained virtual inertia control with final GFM/VSG integration

Current partial integration status:
- First-step/conservative BESS coupling to the DC-link exists through `MicrogridWithBESS`.

## Main engineering intent
This codebase is part of a research thesis. Changes must preserve scientific traceability, physical consistency, and future extensibility.

## Non-negotiable rules
1. Do not change physical equations unless explicitly requested.
2. Do not activate, complete, or claim grid-forming functionality unless explicitly requested.
3. Do not rename current public entrypoints/imports without preserving backward-compatible imports.
4. Do not remove TODO comments related to BESS integration, profiles, grid-forming, or future thesis work.
5. Do not introduce overengineering or unnecessary abstractions.
6. Do not silently change the state vector order.
7. Do not silently change sign conventions for power, current, voltage, or control signals.
8. Do not convert the baseline into a different architecture unless explicitly requested.
9. When in doubt, preserve the current baseline behavior.
10. Do not change the DC-link equation `dVdc/dt = (ipv + i_bess - idc_inv)/Cdc` or its sign convention without explicit request.
11. Keep DC-link internal validation criteria documented in `docs/model_assumptions.md`.
12. Do not connect `GridFormingFrequencyDynamics` to `Microgrid.system_dynamics` unless explicitly requested.
13. Do not replace `GridFollowingController` as the baseline controller unless explicitly requested.
14. Do not present isolated GFM validation as full microgrid validation.
15. Do not treat isolated frequency metrics as final thesis performance metrics until the GFM is coupled to the complete plant.
16. Do not change LCL filter parameters or equations without updating `docs/model_assumptions.md` and running `src/validation/validate_lcl_no_unphysical_oscillations.py`.
17. Do not remove SoH-dependent support limits unless explicitly requested.
18. Do not interpret frequency metrics as final support metrics until GFM/VSG is integrated.
19. Do not treat `REVIEW` due to `Vdc/vt_bess` scale as numerical failure.

## BESS-SLB mandatory conventions

### Capacity convention
- `q_nom_ref_ah = 66 Ah` — nominal/reference capacity of Nissan Leaf 2p module.
- `q_init_case_ah` — case-dependent initial available capacity (not universal).
- `soh_init_case = q_init_case_ah / q_nom_ref_ah` — derived initial SoH.
- `Q_eff(0) = q_nom_ref_ah * soh_init_case = q_init_case_ah`.
- Braco (2020, 2021) is the traceability source for 66 Ah/1C reference.
- Tran (2021) is not the source for 66 Ah because it uses 20 Ah LFP cells.

### Protected physics equations
These equations are validated and must not be modified:
- `V_t = OCV(SoC) - i * R0(SoH) - V_rc` (terminal voltage)
- `dV_rc/dt = -V_rc/(R1*C1) + i/C1` (RC branch dynamics)
- `dSoC/dt = -i/(3600*Q_eff)` (coulomb counting)
- `dz_deg/dt = |i|/3600` (throughput state)
- `SoH = max(soh_min, SoH_0 - k_deg*z_deg)` (linear fade law)
- `Q_eff = Q_nom * SoH` (effective capacity)
- `R0 = R0_nom * (1 + k_R*(1-SoH))` (resistance aging)

### Sign convention
- `i_bess > 0` → discharge
- `i_bess < 0` → charge

- `p_bess_dc = Vdc * i_bess`
- `p_bess_dc > 0` means BESS delivers power to the DC bus.
- `p_bess_dc < 0` means BESS absorbs power from the DC bus.

### Operational support limits
- `i_bess_max_nominal = 66 A` as 1C nominal reference.
- `p_bess_dc_max_nominal = 22440 W`.
- `i_bess_max_available = i_bess_max_nominal * SoH`.
- `p_bess_dc_max_available = min(p_bess_dc_max_nominal, Vdc_ref*i_bess_max_available)`.
- `REVIEW` due to `Vdc/vt_bess` scale is an interpretative scale warning, not numerical failure.

## Preferred workflow
Before making edits:
1. Inspect the relevant files.
2. Propose a short plan.
3. Explain which files will be changed.
4. Make conservative edits.
5. Summarize regression risks after the change.

## Refactoring policy
Use conservative refactoring only.

Preferred refactoring goals:
- reduce conceptual weight
- separate responsibilities clearly
- keep plotting separate from physical modeling
- keep reporting separate from simulation logic
- keep controllers separate from plant models
- preserve compatibility wrappers
- improve names only when helpful and safe

Avoid:
- aggressive rewrites
- unnecessary package nesting
- splitting cohesive scientific code just to reduce line count
- changing equations during cleanup

## Baseline validation checklist
After any non-trivial edit, verify:
- state vector order is unchanged
- physical equations are unchanged unless requested
- control signal flow is unchanged unless requested
- public imports still work
- main baseline execution path still makes sense
- BESS validation scripts pass

## Public compatibility expectations
These public entrypoints should remain stable unless explicitly changed:
- `from microgrid import Microgrid`
- `from ieee33_coupling import IEEE33Microgrid`
- `from bess.model import SecondLifeBattery1RC`
- `from bess.characterization import load_ocv_r1c1_from_excel`
- `from bess import SecondLifeBattery1RC` (re-export via __init__)
- `from bess_second_life import SecondLifeBattery1RC` (backward-compat shim)
- `from bess_characterization import load_ocv_r1c1_from_excel` (backward-compat shim)

If internal modules are reorganized, preserve these imports (or provide compatibility aliases).

## Repository intent by area

### `config.py`
Single source of truth for core constants unless explicitly refactored.

### `controllers/`
Contains control logic only. Keep controller behavior separate from plant physics.
- `grid_following.py` — baseline grid-following PI controller.
- `grid_forming.py` — isolated minimal GFM frequency dynamics for Activity 1.3; not connected to `Microgrid.system_dynamics` yet.

### `docs/`
Contains traceability and thesis-scope documentation.
- `model_assumptions.md` — baseline model assumptions and internal validation criteria.
- `grid_forming_minimal_structure.md` — mathematical structure of the minimal GFM block.
- `grid_forming_plant_control_interface.md` — plant-control interface for transition to Objective 2.

### `bess/` (BESS-SLB package)
Contains the second-life battery model:
- `validators.py` — input validation helpers
- `capacity.py` — capacity convention helpers (`q_nom_ref_ah`, `q_init_case_ah`, `soh_init_case`)
- `lookup_table.py` — OCV/R1/C1 lookup table dataclass and placeholder
- `phase1.py` — static Phase-1 battery model and ECM seed
- `model.py` — **core 1RC dynamic Thevenin model with degradation** (main module)
- `characterization.py` — Excel loader for OCV/R1/C1 experimental data
- `__init__.py` — public re-exports

### `microgrid.py`
Contains physical plant composition and state-space/dynamic assembly for baseline dynamics.

### `ieee33_coupling.py`
Contains IEEE 33 coupling and network-side integration.

### `ieee33_plots.py`
Contains visualization only. Avoid putting physical logic here.

### `main.py` and `ieee33_main.py`
Contain run entrypoints for local baseline and IEEE33 one-way study.

### `validation/`
Contains validation scripts:
- `validate_bess_step2.py` — 1RC dynamic validation (SoC, V_rc, V_terminal)
- `validate_bess_step3.py` — degradation validation (z_deg, SoH, Q_eff, R0)
- `validate_excel_load.py` — Excel characterization loading smoke test
- `validate_lcl_no_unphysical_oscillations.py` — practical check of no non-physical oscillations in LCL states
- `test_grid_forming_frequency_dynamics.py` — isolated GFM unit checks
- `validate_grid_forming_islanded_operation.py` — isolated islanded GFM operation
- `validate_grid_forming_voltage_regulation.py` — isolated three-phase voltage reference and Vdc limitation
- `validate_grid_forming_frequency_behavior.py` — isolated frequency behavior for active-power scenarios
- `validate_grid_forming_step_response.py` — isolated load-step frequency response

### `bess_second_life.py` and `bess_characterization.py` (shims)
Backward-compatible import shims. New code should import from `bess.*` directly.

## How to run validations
From the repository root:
```bash
python src/validation/validate_bess_step2.py          # 1RC dynamic
python src/validation/validate_bess_step3.py          # degradation
python src/validation/validate_excel_load.py           # Excel loading
python src/validation/validate_bess_power_exchange.py
python src/validation/validate_bess_units_scales.py
python src/validation/validate_bess_integrated_nominal.py
python src/validation/validate_bess_soc_operational_limits.py
python src/validation/compare_bess_soh_scenarios.py
python src/validation/validate_lcl_no_unphysical_oscillations.py  # practical LCL check
python src/validation/test_grid_forming_frequency_dynamics.py
python src/validation/validate_grid_forming_islanded_operation.py
python src/validation/validate_grid_forming_voltage_regulation.py
python src/validation/validate_grid_forming_frequency_behavior.py
python src/validation/validate_grid_forming_step_response.py
python src/main.py                                     # local PV microgrid
python src/main.py --with-bess                         # local PV microgrid with preliminary BESS coupling
python src/main.py --compare-bess                      # no-BESS vs preliminary BESS comparison
python src/ieee33_main.py                              # IEEE 33 coupling
```

## When asked to validate a change
Report using:
- OK
- Review
- Risk

And identify:
- changed files
- compatibility impact
- possible regression points
- whether baseline behavior should be manually checked

## Default behavior
If a request is ambiguous, choose the most conservative interpretation and avoid changing physics or thesis scope.

## Thesis-specific caution
Do not present scaffold code as a completed contribution.
Do not describe baseline grid-following behavior as grid-forming.
Do not imply full BESS+PV+inverter integration when only preliminary DC-link coupling is implemented.
The current GFM work is an isolated minimal model suitable as a base for Objective 2.
It is not the final VSG/FOVIC controller.
It is not yet coupled with the complete PV+BESS+DC-link+LCL+PCC plant.
Be precise about what is implemented vs. what is planned.

## Style guidance
- Prefer clear, technical names.
- Prefer small functions with single responsibility.
- Use short docstrings when helpful.
- Use type hints where practical.
- Keep comments technical and useful.
- Preserve scientific readability over software cleverness.
