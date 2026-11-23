"""BAT26-50: fail-closed checks without requiring unavailable Codex result files."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation.build_bat26_50_figures import (
    CHECKPOINTS, BAT45_FIELDS, BAT46_FIELDS, _read_csv, _read_json,
    _verify_bat45, _verify_bat46,
)


class Bat2650FigureContracts(unittest.TestCase):
    def test_declared_source_fields_and_checkpoints(self):
        self.assertEqual(CHECKPOINTS, (0, 100, 500, 1000))
        self.assertIn("efc_from_case_throughput", BAT45_FIELDS)
        self.assertIn("nominal_efc_from_soc", BAT45_FIELDS)
        self.assertIn("efc_blast", BAT45_FIELDS)
        self.assertIn("terminal_energy_Wh_modelled", BAT46_FIELDS)

    def test_bat45_truncated_series_cannot_be_plotted(self):
        with self.assertRaisesRegex(ValueError, "original full"):
            _verify_bat45([{
                "cycles": 1000.0,
            }], {"final": {}})

    def test_bat46_missing_checkpoint_cannot_be_plotted(self):
        with self.assertRaisesRegex(ValueError, "exactly checkpoints"):
            _verify_bat46([], {"battery_port": []}, {})

    def test_missing_csv_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                _read_csv(Path(folder) / "does-not-exist.csv", BAT45_FIELDS)

    def test_source_summary_must_be_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "summary.json"
            p.write_text(json.dumps({"task": "BAT26-45", "status": "REVIEW"}),
                         encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-PASS"):
                _read_json(p, "BAT26-45")
            p.write_text(json.dumps({"task": "BAT26-46", "status": "PASS"}),
                         encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected task"):
                _read_json(p, "BAT26-45")

    def test_source_csv_schema_not_silently_inferred(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "cycle_history.csv"
            p.write_text("cycles,soh_cycling_pct\n0,66.8\n",
                         encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                _read_csv(p, BAT45_FIELDS)


if __name__ == "__main__":
    unittest.main()
