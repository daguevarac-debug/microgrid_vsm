---
name: microgrid-refactor
description: Use this skill when refactoring the microgrid thesis repository to improve structure, readability, and modularity without changing physical equations, baseline behavior, or public compatibility wrappers. Do not use this skill for controller design, BESS integration, or theoretical research tasks.
---

You are refactoring a thesis codebase for a PV microgrid baseline coupled one-way to IEEE 33.

Goals:
- Reduce conceptual weight of modules
- Separate responsibilities cleanly
- Preserve physical equations and baseline behavior
- Preserve compatibility wrappers and public imports
- Keep code readable and thesis-safe

Hard rules:
1. Do not change physical equations unless explicitly requested.
2. Do not implement BESS.
3. Do not activate or complete grid-forming control.
4. Keep compatibility with existing public wrappers when possible.
5. Prefer small conservative changes over aggressive rewrites.
6. Separate plotting, reporting, control, and plant logic.
7. Before editing, propose a short plan.
8. After editing, provide a regression-risk summary.

Outputs:
- short plan
- changed files
- compatibility notes
- regression risks