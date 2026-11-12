# IEEE European Low Voltage 906-bus feeder — reproducible feasibility study

**Status:** initial implementation / execution pending. Branch \`feat/ieee-europe-lv-906-benchmark\`; target \`feat/blast-aging-adapter\`. No changes to the protected plant/controller equations or IEEE 33 evidence.

## Research decision and boundary

The original IEEE European LV feeder is adopted **as a grid-connected, three-phase, unbalanced power-flow benchmark**, not as a fully islanded microgrid. This is a targeted answer to DIR-05 (make the network power injection representative). Its 906 LV buses, 905 line sections, 55 single-phase loads, 416 V LL and 50 Hz can be directly compared with original reference test data. The nominal load sum is 55 kW at 1 kW per connection; actual load at a selected instant MUST come from the one-minute time series. The 3 kW / 55 kW = 5.45% ratio is a **nominal-scale orientation only**.

The existing dynamic 12/15/16-state GFM/VSG model remains **60 Hz, 110 V line-to-neutral (about 190.5 V LL), Vdc 340 V and 3 kW nominal load**. It is not electrically compatible with direct connection to this 50 Hz, 416 V LL feeder without an explicitly modeled frequency/voltage architecture. The new OpenDSS snapshots therefore use a *balanced three-phase constant-P generator* at a network bus, NOT a VSG dynamic connection and NOT a validation of the second-life BESS pack or DC/DC converter. The 906-node feeder cannot be island-supplied by a 3 kW PV system at the feeder's regular load levels.

## Independent reference sources

1. IEEE, *European Low Voltage Test Feeder* (2015), official public benchmark with one-minute 24-hour load profiles, static and dynamic time-series reference results: https://ieee-pes-data-sharing.org/datasets/detail/4e38bf3e-d4b3-480c-83e4-167b7bf5dece
2. Public OpenDSS mirror used for deterministic scripted acquisition: https://github.com/tshort/OpenDSS/tree/master/Distrib/IEEETestCases/LVTestCase
3. M. A. Khan and B. Hayes, *A Reduced Electrically-Equivalent Model of the IEEE European Low Voltage Test Feeder*, 906-to-116-bus comparison and downloadable model: https://doi.org/10.21227/0d2n-j565 ; https://doi.org/10.36227/techrxiv.16785832.v1
4. OpenDSS Generator definition, three-phase generator kV refers to line-line voltage: https://dss-extensions.org/dss-format/Generator.html

Keep downloaded files and SHA-256 manifest. The source mirror uses \`master\` by default; the manifest hashes the actual obtained bytes. A future validated release should pin an immutable upstream commit and log the OpenDSSDirect package version.

## Files and execution

\`scripts/ieee_europe_lv_906_study.py\` downloads the main OpenDSS file set plus exactly the 55 referenced minute-by-minute load shape files. To avoid generating unwanted energy-meter demand-interval files or running 1,440 steps on import, it derives an analysis-only \`_study_master.dss\` from the original \`Master.dss\` **up to the first Solve**, omitting only monitors, meter and coordinates. Network, transformer, line codes, loads and load shapes remain unchanged. This stripped script is a computational adapter and must not be presented as the original IEEE file.

On Windows PowerShell, from the project root:

\`\`\`powershell
Set-Location "G:\OneDrive - Universidad Nacional de Colombia\microgrid_vsm"
git fetch origin
git switch --track origin/feat/ieee-europe-lv-906-benchmark
py -3.12 -m pip install "opendssdirect.py"
py -3.12 scripts/ieee_europe_lv_906_study.py --download --minute 720 --pv-kw 3 --baseline-step 60
\`\`\`

If the branch already exists locally, use \`git switch feat/ieee-europe-lv-906-benchmark\`. If the working tree has unrelated modifications, inspect \`git status --short\` before switching; do not reset or discard changes.

For all **1,440 baseline minutes** after the initial hourly smoke-test:

\`\`\`powershell
py -3.12 scripts/ieee_europe_lv_906_study.py --minute 720 --pv-kw 3 --baseline-step 1
\`\`\`

The script saves under \`outputs/analysis/ieee_europe_lv_906/\`:

- \`baseline_24h.csv\`: baseline voltage, P demand, feeder import, and losses at each sampled minute, no PV.
- \`snapshot_pv_comparison.csv\`: same-minute comparison \`base\`, \`PV_near\` (bus 34, 3ph) and \`PV_far\` (bus 822, 3ph).
- \`run_summary.json\`: model boundary, assumptions and numerical snapshot evidence.

Download hashes reside in \`data/ieee_europe_lv_906/source_manifest.json\`. Source files and generated results are ignored by Git; publish only vetted summaries and explicitly licensed reference assets if needed.

## Scientific acceptance criteria (do not label PASS prematurely)

**Data provenance.** Reproducibly fetch all file dependencies, verify SHA-256 manifest, topology of 905 lines and 55 loads, and source frequency/voltage. Audit the original line length units and transformer rating. If compilation changes commands in the source or omits physical elements, investigate before accepting a result.

**Baseline equivalence.** Run at least one original IEEE time stamp and compare *per-phase bus voltages, feeder P/Q and losses* with IEEE reference outputs. The public 116-bus reduction can be used later as a second independent baseline, but should not be assumed identical without a checked source model and operating point. Record numerical tolerances and reasons (different solver conventions, control modes), not post-hoc arbitrary PASS limits.

**Representativeness.** For each experiment report \`P_PV/P_load(t)\` and ideally energy share over a documented profile, rather than solely \`3/55\`. Compare voltages by phase at buses 34 and 822, min/max voltage over LV phases, losses and source import. Test against the original no-PV feeder at exactly the same minute and load shapes. Validate power balance including the 3 kW source.

**Three-phase compatibility.** Loads are single-phase and unbalanced; the introduced PV is a balanced 3-phase PQ injection. This **does not** imply a physical 416 V/50 Hz VSG inverter model. To couple to the existing 190.5 V LL/60 Hz VSG, decide explicitly whether to rescale the plant to 50 Hz and add a voltage conversion stage, or to keep separate grid-connected QSTS and an islanded local ~3 kW test rig.

**Future optimization.** After 906-bus reference is validated, assess the 116-bus equivalent for repeated optimization studies. Keep the original 906-bus snapshots as truth. Never claim co-simulation or experimental validation from a static OpenDSS generator.

## Regression and safety

Leave all \`src/ieee33_*\`, \`src/microgrid.py\`, \`src/bess/\`, \`src/controllers/\`, \`src/config.py\` and the protected state-vector conventions untouched. No merge into \`main\`. Ensure \`git status --short\` shows only intended files before opening/merging a PR. The director's decision about feeder scale and isolated-operation interface remains pending until comparison results exist.

**First acceptance checkpoint:** download/verify source files, obtain a converged no-PV baseline, demonstrate signed power balance, and produce the same-minute near/far 3 kW PV comparison. If any step fails, report it as BLOCKED with logs rather than invent voltage or loss figures.
