"""Read-only sensitivity audit: original IEEE 906-bus reference discrepancies.

Each option is a diagnostic branch: never silently adopt a variant as the
physical feeder. Power measurements are on the LV transformer terminal.
"""
from __future__ import annotations

import json
from pathlib import Path

from ieee_europe_lv_906_study import verify_dataset, write_study_master
from ieee_europe_lv_906_reference import REFERENCE

# The original Master.dss uses loadshape UseActual=no; the original
# transformer file leaves resistance unspecified (OpenDSS default).
OPTIONS = {
    "original": (),
    "profiles_useactual_yes": ("batchedit loadshape..* useactual=yes",),
    "transformer_r_0p1_each": ("edit Transformer.TR1 %Rs=[0.1 0.1]",),
    "transformer_r_0p4_each": ("edit Transformer.TR1 %Rs=[0.4 0.4]",),
    "r0p4_and_useactual_yes": (
        "edit Transformer.TR1 %Rs=[0.4 0.4]",
        "batchedit loadshape..* useactual=yes",
    ),
}


def snapshot(dss, master: Path, minute: int, commands: tuple[str, ...]) -> tuple[float, ...]:
    dss.Basic.ClearAll()
    dss.Text.Command(f'compile "{master.resolve().as_posix()}"')
    for cmd in commands:
        dss.Text.Command(cmd)
    dss.Text.Command("set mode=yearly number=1 stepsize=1m")
    dss.Solution.Hour(minute // 60)
    dss.Solution.Seconds((minute % 60) * 60)
    dss.Solution.Solve()
    if not dss.Solution.Converged():
        raise RuntimeError(f"Non-convergence at minute {minute}: {commands}")
    if dss.Circuit.SetActiveElement("Transformer.TR1") < 0:
        raise RuntimeError("Missing TR1")
    values = dss.CktElement.Powers()
    offset = 2 * dss.CktElement.NumConductors()
    return tuple(-float(values[offset + 2*i]) for i in range(3))


def main() -> None:
    import opendssdirect as dss

    root = Path("data/ieee_europe_lv_906").resolve()
    output = Path("outputs/analysis/ieee_europe_lv_906").resolve()
    verify_dataset(root)
    master = write_study_master(root)
    result = {}
    for variant, commands in OPTIONS.items():
        errors = []
        points = {}
        for minute, original in REFERENCE.items():
            expected = original["transformer_lv_p_kw"]
            actual = snapshot(dss, master, minute, commands)
            points[str(minute)] = {
                "reference_lv_phase_p_kw": expected,
                "simulated_lv_phase_p_kw": [round(v, 7) for v in actual],
            }
            errors.extend(abs((p-e)/e)*100 for p,e in zip(actual, expected))
        result[variant] = {
            "commands": commands,
            "max_phase_p_error_percent": round(max(errors), 4),
            "mean_phase_p_error_percent": round(sum(errors)/len(errors), 4),
            "samples": points,
        }
    output.mkdir(parents=True, exist_ok=True)
    (output / "ieee_reference_sensitivity.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: {x:y for x,y in v.items() if x!="samples"}
                      for k,v in result.items()}, indent=2))


if __name__ == "__main__":
    main()
