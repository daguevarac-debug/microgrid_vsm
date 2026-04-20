"""External validation wrapper: Braco Fig. 5(b) SL 0.5C 25C."""

from __future__ import annotations

from pathlib import Path
import sys

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation.braco_fig5b_external_common import BracoValidationCase, run_case

CASE = BracoValidationCase(
    case_label="Braco Fig.5(b) SL 0.5C 25C",
    input_curve_filename="5b_SL_0p5C_25C.xlsx",
    discharge_current_a=33.0,
    output_subdir=Path("outputs") / "validation" / "braco_fig5b_sl_0p5c",
)


if __name__ == "__main__":
    raise SystemExit(run_case(CASE))
