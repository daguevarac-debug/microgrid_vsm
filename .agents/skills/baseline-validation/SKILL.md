---
name: baseline-validation
description: Use this skill when validating that a refactor, cleanup, or architectural reorganization did not change the baseline dynamic behavior, state ordering, public imports, or expected execution flow of the PV microgrid thesis repository. Do not use this skill for creating new features.
---

Validate the repository conservatively after refactors or structural edits.

Project context:
- This repository contains a thesis baseline for a PV microgrid coupled one-way to IEEE 33.
- The main purpose of this skill is to detect regression risks after cleanup or reorganization.
- The baseline behavior must remain stable unless a change was explicitly requested.

Validation goals:
- Confirm state vector order is unchanged
- Confirm key physical equations are unchanged
- Confirm control signal flow is unchanged
- Confirm public imports still work
- Distinguish dependency issues from actual regression risks

Hard rules:
1. Do not implement new features.
2. Do not propose architectural rewrites unless explicitly asked.
3. Focus on validation, not redesign.
4. Treat missing external dependencies separately from functional regressions.
5. Be explicit when something is only partially verified.

Checklist:
1. Check state vector order in the main dynamic model.
2. Check that derivative return order is unchanged.
3. Check that control law expressions and signal flow are unchanged.
4. Check that key public imports remain compatible.
5. Check entrypoints still make sense (`main.py`, `ieee33_microgrid.py`).
6. Flag files that deserve manual inspection.
7. Report dependency limitations separately.

Output format:
- state vector: OK / Review / Risk
- equations: OK / Review / Risk
- control flow: OK / Review / Risk
- public imports: OK / Review / Risk
- entrypoints: OK / Review / Risk
- dependency limits
- files to inspect manually
- possible regressions