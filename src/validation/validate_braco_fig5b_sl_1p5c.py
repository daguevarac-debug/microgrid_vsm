"""External validation wrapper: Braco Fig. 5(b) SL 1.5C 25C."""

from __future__ import annotations

from pathlib import Path

from braco_fig5b_external_common import BracoValidationCase, run_case

CASE = BracoValidationCase(
    case_label="Braco Fig.5(b) SL 1.5C 25C",
    input_curve_filename="5b_SL_1p5C_25C.xlsx",
    discharge_current_a=99.0,
    output_subdir=Path("outputs") / "validation" / "braco_fig5b_sl_1p5c",
)


if __name__ == "__main__":
    raise SystemExit(run_case(CASE))
