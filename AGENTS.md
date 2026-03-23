# AGENTS.md

## Project overview
This repository contains a thesis baseline for a photovoltaic microgrid dynamically coupled in a one-way sequential manner to the IEEE 33-bus distribution system.

Current implemented scope:
- PV array model
- DC-link dynamics
- LCL filter
- inverter source and baseline control
- local dynamic simulation
- sequential one-way coupling to IEEE 33 at the PCC

Not yet implemented:
- BESS integration
- operational second-life battery model
- full grid-forming controller
- active virtual inertia control for final thesis contribution

## Main engineering intent
This codebase is part of a research thesis. Changes must preserve scientific traceability, physical consistency, and future extensibility.

The current goal is to maintain a clean, modular, and trustworthy baseline before adding grid-forming and BESS features.

## Non-negotiable rules
1. Do not change physical equations unless explicitly requested.
2. Do not implement BESS unless explicitly requested.
3. Do not activate, complete, or claim grid-forming functionality unless explicitly requested.
4. Do not rename current public entrypoints/imports without preserving backward-compatible imports.
5. Do not remove TODO comments related to BESS, profiles, grid-forming, or future thesis work.
6. Do not introduce overengineering or unnecessary abstractions.
7. Do not silently change the state vector order.
8. Do not silently change sign conventions for power, current, voltage, or control signals.
9. Do not convert the baseline into a different architecture unless explicitly requested.
10. When in doubt, preserve the current baseline behavior.

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

## Public compatibility expectations
These public entrypoints should remain stable unless explicitly changed:
- `from microgrid import Microgrid`
- `from ieee33_coupling import IEEE33Microgrid`

If internal modules are reorganized, preserve these imports (or provide compatibility aliases).

## Style guidance
- Prefer clear, technical names.
- Prefer small functions with single responsibility.
- Use short docstrings when helpful.
- Use type hints where practical.
- Keep comments technical and useful.
- Preserve scientific readability over software cleverness.

## Thesis-specific caution
Do not present scaffold code as a completed contribution.
Do not describe baseline grid-following behavior as grid-forming.
Do not imply BESS support if it is not implemented.
Be precise about what is implemented vs. what is planned.

## Repository intent by area

### `config.py`
Single source of truth for core constants unless explicitly refactored.

### `controllers/`
Contains control logic only. Keep controller behavior separate from plant physics.

### `microgrid.py`
Contains physical plant composition and state-space/dynamic assembly for baseline dynamics.

### `ieee33_coupling.py`
Contains IEEE 33 coupling and network-side integration.

### `ieee33_plots.py`
Contains visualization only. Avoid putting physical logic here.

### `main.py` and `ieee33_main.py`
Contain run entrypoints for local baseline and IEEE33 one-way study.

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
