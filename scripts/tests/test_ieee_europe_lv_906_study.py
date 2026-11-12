"""Fast deterministic tests for the IEEE European LV dataset adapter (no OpenDSS required)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ieee_europe_lv_906_study import LOAD_SHAPE_PATTERN, verify_dataset, write_study_master
from ieee_europe_lv_906_daily_pv import illustrative_pv_kw


class EuropeanLVAdapterTests(unittest.TestCase):
    def test_illustrative_pv_profile_is_explicitly_synthetic(self) -> None:
        self.assertEqual(illustrative_pv_kw(0), 0.0)
        self.assertEqual(illustrative_pv_kw(360), 0.0)
        self.assertAlmostEqual(illustrative_pv_kw(720), 3.0)
        self.assertEqual(illustrative_pv_kw(1080), 0.0)
        self.assertEqual(illustrative_pv_kw(1439), 0.0)
        self.assertAlmostEqual(illustrative_pv_kw(600), illustrative_pv_kw(840))
        with self.assertRaises(ValueError):
            illustrative_pv_kw(1440)

    def test_profile_reference_parsing(self) -> None:
        line = r"New Loadshape.Shape_1 npts=1440 mult=(file=Daily_1min_100profiles\Load_profile_1.txt)"
        self.assertEqual(
            LOAD_SHAPE_PATTERN.findall(line),
            [r"Daily_1min_100profiles\Load_profile_1.txt"],
        )

    def test_study_master_removes_simulation_and_nonphysical_outputs(self) -> None:
        master = """clear
Set DefaultBaseFrequency=50
New circuit.LVTest
Redirect Lines.txt
Redirect Transformers.txt
Redirect Loads.txt
Redirect Monitors.txt
New energymeter.m1 LINE.LINE1 1
Set voltagebases=[11 .416]
Calcvoltagebases
buscoords Buscoords.txt
solve
set mode=yearly number=1440 stepsize=1m
solve
"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Master.dss").write_text(master, encoding="utf-8")
            script = write_study_master(root).read_text(encoding="utf-8").lower()
            self.assertIn("redirect lines.txt", script)
            self.assertIn("set defaultbasefrequency=50", script)
            self.assertNotIn("monitor", script)
            self.assertNotIn("meter", script)
            self.assertNotIn("buscoords", script)
            self.assertNotIn("solve", script)

    def test_sha256_manifest_rejects_mutated_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {}
            for i in range(60):
                name = f"file_{i}.txt"
                data = f"profile {i}\n".encode("ascii")
                (root / name).write_bytes(data)
                files[name] = {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            (root / "source_manifest.json").write_text(json.dumps({"files": files}), encoding="utf-8")
            verify_dataset(root)
            (root / "file_9.txt").write_text("corrupted", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_dataset(root)


if __name__ == "__main__":
    unittest.main()
