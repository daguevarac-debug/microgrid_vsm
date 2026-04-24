# AGENTS.md

## Project overview
This repository contains a thesis baseline for a photovoltaic microgrid dynamically coupled in a one-way sequential manner to the IEEE 33-bus distribution system, with a second-life EV battery (BESS-SLB) dynamic model.

Current implemented scope:
- PV array model
- DC-link dynamics
- LCL filter
- inverter source and baseline control (grid-following PI)
- local dynamic simulation
- sequential one-way coupling to IEEE 33 at the PCC
- **BESS-SLB Thevenin 1RC dynamic model** with OCV/R1/C1 lookup tables
- **First-order degradation model** (z_deg throughput, SoH linear fade, R0 aging)
- **Excel characterization loader** for OCV/R1/C1 from experimental/literature data
- **Phase-1 static battery model** (capacity, SoH, internal resistance)

Not yet implemented:
- Full BESS + PV + inverter integration beyond first-step coupling
- full grid-forming controller
- active virtual inertia control for final thesis contribution

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

### `bess_second_life.py` and `bess_characterization.py` (shims)
Backward-compatible import shims. New code should import from `bess.*` directly.

## How to run validations
From the repository root:
```bash
python src/validation/validate_bess_step2.py          # 1RC dynamic
python src/validation/validate_bess_step3.py          # degradation
python src/validation/validate_excel_load.py           # Excel loading
python src/main.py                                     # local PV microgrid
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
Be precise about what is implemented vs. what is planned.

## Style guidance
- Prefer clear, technical names.
- Prefer small functions with single responsibility.
- Use short docstrings when helpful.
- Use type hints where practical.
- Keep comments technical and useful.
- Preserve scientific readability over software cleverness.
