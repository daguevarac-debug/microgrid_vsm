# IEEE European LV 906-bus — audit against published IEEE 2015 snapshots

**Date:** 2026-11-12. **Status: REVIEW (no published-reference PASS).** GitHub Actions source audit: https://github.com/daguevarac-debug/microgrid_vsm/actions/runs/43301714520 . No modification to the validated IEEE33 case or the GFM/BESS dynamic state vectors.

## Independent reference data

Official IEEE PES repository: https://github.com/ieee-pes-amps/dtf-dev/tree/master/European%20LV%20Test%20Feeder/Additional%20Information/European_LV_CSV

2015 report: *The IEEE European Low Voltage Test Feeder*, Tables II and III. Public transcription: https://studylib.net/doc/26139528/ieee-european-lv-test-feeder---draft . The reference includes three instants at 00:01, 09:26, and 24:00 and source P/Q and voltage extrema per phase.

**Source-data result:** independently downloaded and compared all 55 official IEEE PES load profile CSVs (1,440 samples each, **79,200 comparisons**) with our tshort/OpenDSS mirror: **zero numerical differences** at tolerance 1e-9. Checked all 55 load bus/phase assignments: **zero discrepancies**. IEEE official Transformer.csv states 11kV/0.416kV, 800kVA, XHL=4%, winding resistance=0.4%; the mirror's Transformers.txt does not explicitly encode resistance. Do not presume its OpenDSS default is identical without checking instantiated winding resistances.

## Comparison with the published 2015 report

| Timestamp | IEEE reference source P (kW), A/B/C | Simulated P (kW), A/B/C |
| --- | --- | --- |
| 00:01 | 1.0572 / 0.9270 / 0.8153 | 1.0857 / 0.9353 / 1.0340 |
| 09:26 | 17.9072 / 35.2927 / 6.1837 | 23.4456 / 18.4136 / 6.0528 |
| 24:00 | 3.7201 / 3.6648 / 2.3369 | 1.0663 / 0.9370 / 1.0442 |

**This is NOT agreement with IEEE 2015.** At 09:26 the reference Ptotal is ~59.3836kW vs simulated ~47.9120kW. Maximum observed absolute error across phase P is 16.8791kW; across Q 7.4424kvar. Min bus LV voltage discrepancies reach 6.5444 V (up to 2.665%). The differences must not be described as negligible.

**Time-index diagnosis:** The 24:00 simulation using `Solution.Hour(24)` / `Seconds(0)` appears to wrap to the initial loadshape point. Probing the adjacent time 23:59 produces source P approximately 3.997/3.120/3.427kW, not the published 3.720/3.665/2.337kW. At 09:25 the source produces P approximately 28.812/18.372/13.737kW, while at 09:26 it produces 23.446/18.414/6.053kW; the reference phases differ systematically, not solely by an offset of one minute.

## Previously documented discrepancy

Independent OpenDSS forum users reported that the IEEE 2015 benchmark's published snapshots and shipped OpenDSS profile sets did not match; see https://sourceforge.net/p/electricdss/discussion/861977/thread/f77e272cc5/ and https://sourceforge.net/p/electricdss/discussion/861976/thread/1858322dda/. A 2022 investigation specifically cited several profile revisions. **Our 2026 audit shows current public IEEE PES CSV profiles and tshort mirror match**, so historical profile differences alone do not explain current numerical discrepancies. Possible additional causes include solver version/operating conventions, source/transformer model and profile indexing. These remain hypotheses, not demonstrated root causes.

## Scientific decision

Keep **OpenDSS convergence / internal power balance: PASS** and **IEEE 2015 independent snapshot reproduction: REVIEW**. The 3kW noon injection experiment remains an internally consistent **exploratory network study** with roughly 9.4% instantaneous active-load contribution and location-dependent losses, but it is not yet a validated reproduction of the published 2015 results. In addition, it is not a physical GFM connection; feeder voltage/frequency 416V LL/50Hz differs from 190.5V LL/60Hz local plant.

Do not optimize parameters or silently edit source data to minimize the discrepancy. Before promoting this feeder to the main thesis comparison, document the transformer resistances actually instantiated by OpenDSS, inspect Loadshape timestamps/model conversion, and if necessary reproduce the original IEEE DSS `Master.dss` execution exactly or compare the same input dataset with another independent engine. Preserve version/hash provenance.
