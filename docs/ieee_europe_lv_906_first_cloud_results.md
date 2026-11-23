# IEEE European LV 906-bus — first cloud numerical evidence

**Execution date:** 2026-11-12. **GitHub Actions:** https://github.com/daguevarac-debug/microgrid_vsm/actions/runs/43299599055 . Source: tshort/OpenDSS public feeder mirror, manifests SHA-256 created at run time. **Context:** PR #53 DRAFT, no merge and no modification of IEEE33 or protected microgrid equations.

## Runtime and checks

OpenDSSDirect 0.9.4 on Python 3.12 (GitHub-hosted Ubuntu). Three local data-adapter/manifest tests passed. The original feeder loaded 905 line elements and 55 loads; the downloaded load shapes have 1,440 points. The no-PV 24-hour load-flow series completed at 1-minute resolution (1,440 samples) without solver or power-balance failures. The faster implementation recompiles only once for the 24-hour no-PV sequence.

These checks support **initial internal reproducibility and numerical consistency**, NOT independent agreement with the official IEEE published voltage/loss files and NOT a GFM dynamical simulation. Baseline reference comparison remains pending.

## Noon snapshot (minute 720, grid-connected; 3 kW three-phase DG)

| Metric | Base without PV | 3 kW DG at bus 34 | 3 kW DG at bus 822 |
| --- | ---: | ---: | ---: |
| Actual demand in simulated circuit, kW | 31.783384 | 31.794813 | 31.831473 |
| Source import, kW | 32.098899 | 29.100769 | 29.103480 |
| Feeder active losses, kW | 0.315472 | 0.305919 | 0.272018 |
| Minimum LV phase voltage, pu | 1.0322357 | 1.0324209 | 1.0330000 |
| Maximum LV phase voltage, pu | 1.0493079 | 1.0493344 | 1.0493341 |
| Voltage at bus 34, phase 1, pu | 1.0460004 | 1.0464026 | 1.0461873 |
| Voltage at bus 822, phase 3, pu | 1.0456032 | 1.0457900 | 1.0469419 |
| 3 kW / simultaneous active demand | — | 9.4355% | 9.4246% |
| Power balance residual, kW | +0.000043 | +0.000037 | -0.000012 |

The bus 34 scenario reduces modeled feeder losses by **3.03%** compared with the identical no-PV instant, while bus 822 reduces them by **13.77%**. The differences between the simulated demand totals are small and result from the OpenDSS operating solution; all power balance residuals are less than 0.00005 kW. Do not use the nominal 3/55 kW 5.45% ratio as a substitute for the measured 9.4% noon active-power share.

## Interpretive boundaries

The generator is a *static* balanced 3-phase PQ element (3 kW, unity power factor) representing PV at a chosen instant, not a measured irradiance-dependent time series and not the battery/VSG source. IEEE European LV is **50 Hz, 416 V LL**, while the protected local inverter remains **60 Hz, about 190.5 V LL**, so no direct coupling or islanded operation is claimed. The source is grid-connected in this test. 3 kW cannot be assumed to supply the whole feeder autonomously.

Next scientific gate: compare all-phase base-case bus voltage/P/Q/losses against the **published IEEE reference outputs** at matching profile timestamp and solver conventions; then justify the physical connection and profile prior to integrating dispatch. Preserve old IEEE33 results for regression.

## Reproducible artifact

The GitHub Actions run uploaded CSV and JSON with dataset checksum manifest as artifact `ieee-europe-lv-906-validation` (available from the workflow run for 30 days). A SHA-256 manifest records the mirror files actually fetched; reproducible results require those exact bytes. The internal results in this document were transcribed from the **successful optimized** GitHub Actions job logs, not independently reconciled with IEEE official expected outputs.
