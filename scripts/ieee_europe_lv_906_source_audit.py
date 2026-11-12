"""Audit source parity between public IEEE PES CSV and OpenDSS mirror.

The IEEE PES dataset is independent from the tshort/OpenDSS mirror.
Do NOT silently replace mismatching profiles: report exact differences first.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request

IEEE_REPO = "https://raw.githubusercontent.com/ieee-pes-amps/dtf-dev/master"
IEEE_ROOT = "European LV Test Feeder/Additional Information/European_LV_CSV"


def _read_official(relative: str) -> tuple[bytes, str]:
    full_path = quote(f"{IEEE_ROOT}/{relative}", safe="/")
    uri = f"{IEEE_REPO}/{full_path}"
    with urlopen(Request(uri, headers={"User-Agent": "microgrid_vsm-source-audit/1.0"}), timeout=50) as r:
        data = r.read()
    if not data:
        raise ValueError(f"Empty official IEEE source: {uri}")
    return data, uri


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data/ieee_europe_lv_906"))
    p.add_argument("--output-dir", type=Path, default=Path("outputs/analysis/ieee_europe_lv_906"))
    args = p.parse_args()
    data_dir, out_dir = args.data_dir.resolve(), args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for i in range(1, 56):
        remote_raw, origin = _read_official(f"Load Profiles/Load_profile_{i}.csv")
        src = list(csv.DictReader(io.StringIO(remote_raw.decode("utf-8-sig"))))
        official = [float(row["mult"]) for row in src]
        local_path = data_dir / "Daily_1min_100profiles" / f"Load_profile_{i}.txt"
        mirror_raw = local_path.read_bytes()
        mirror = [float(s) for s in mirror_raw.decode("utf-8-sig").splitlines() if s.strip()]
        if len(official) != 1440 or len(mirror) != 1440:
            raise AssertionError(f"Profile {i} incomplete: {len(official)}, {len(mirror)}")
        differing = [(j + 1, official[j] - mirror[j]) for j in range(1440)
                     if abs(official[j] - mirror[j]) > 1e-9]
        records.append({
            "profile": i,
            "different_samples": len(differing),
            "max_abs_difference_kw_multiplier": max((abs(item[1]) for item in differing), default=0),
            "first_diff_minute": differing[0][0] if differing else None,
            "official_sha256": hashlib.sha256(remote_raw).hexdigest(),
            "mirror_sha256": hashlib.sha256(mirror_raw).hexdigest(),
            "official_url": origin,
        })

    transformer_raw, xf_origin = _read_official("Transformer.csv")
    text = transformer_raw.decode("utf-8-sig")
    xf_rows = list(csv.DictReader(line for line in text.splitlines() if not line.lstrip().startswith("#")))
    if len(xf_rows) != 1:
        raise AssertionError("Official IEEE transformer metadata changed unexpectedly")

    loads_raw, loads_origin = _read_official("Loads.csv")
    official_loads = list(csv.DictReader(
        line for line in loads_raw.decode("utf-8-sig").splitlines()
        if not line.lstrip().startswith("#")
    ))
    load_mismatches = []
    dss_text = (data_dir / "Loads.txt").read_text(encoding="utf-8-sig")
    for row in official_loads:
        name = row["Name"].strip()
        match = re.search(rf"^New Load\.{re.escape(name)}\s+[^\r\n]+",
                          dss_text, re.IGNORECASE | re.MULTILINE)
        if not match:
            load_mismatches.append(f"Missing {name} in mirror")
            continue
        found = re.search(r"Bus1=([0-9]+)\.([123])", match.group(0), re.IGNORECASE)
        if not found or found.group(1) != row["Bus"].strip() or found.group(2) != str("ABC".index(row["phases"].strip().upper()) + 1):
            load_mismatches.append(f"Different bus/phase for {name}")

    payload = {
        "official_repo": IEEE_REPO,
        "files_checked": 55,
        "samples_per_file": 1440,
        "profiles_with_differences": [
            {k: v for k, v in r.items() if k not in ("official_sha256", "mirror_sha256", "official_url")}
            for r in records if r["different_samples"]
        ],
        "total_differing_samples": sum(r["different_samples"] for r in records),
        "official_transformer": xf_rows[0],
        "official_transformer_source": xf_origin,
        "official_loads_source": loads_origin,
        "load_phase_bus_mismatches": load_mismatches,
        "comparison_rows": records,
        "note": "This only tests public source parity, not IEEE published solution agreement.",
    }
    (out_dir / "source_parity_ieee_pes_vs_mirror.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in payload.items() if k != "comparison_rows"}, indent=2))


if __name__ == "__main__":
    main()
