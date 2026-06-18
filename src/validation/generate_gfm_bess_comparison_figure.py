"""Generate the final diagnostic comparison for GFM operation with and without BESS."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]
REPO_ROOT = THIS_FILE.parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.gfm_controller import GFMController
from main import run_bess_comparison
from microgrid import Microgrid


OUTPUT_PATH = REPO_ROOT / "outputs" / "gfm_bess_comparison.png"


def _baseline_pv_power(base: dict[str, np.ndarray]) -> np.ndarray:
    """Reconstruct baseline PV-side DC power for the comparison figure."""
    reference_model = Microgrid()
    p_ref = min(reference_model.P_ref_nominal, reference_model.p_available_ref)
    model = Microgrid(controller=GFMController(p_ref=p_ref))

    p_pv_dc = np.zeros_like(base["t"])
    for k, tk in enumerate(base["t"]):
        irradiance = float(model.irradiance_profile(float(tk)))
        temperature_c = float(model.temperature_profile(float(tk)))
        vdc = max(float(base["vdc"][k]), 0.0)
        ipv = model.plant.pv_current(vdc, irradiance, temperature_c)
        p_pv_dc[k] = vdc * float(ipv)
    return p_pv_dc


def save_gfm_bess_comparison_figure() -> Path:
    """Save a five-panel diagnostic figure for both GFM comparison cases."""
    comparison = run_bess_comparison()
    base = comparison["baseline"]
    bess = comparison["with_bess"]
    p_pv_dc_base = _baseline_pv_power(base)
    t_step = Microgrid().t_step

    fig, axes = plt.subplots(5, 1, figsize=(10, 11), sharex=True)

    axes[0].plot(base["t"], base["vdc"], label="Vdc sin BESS")
    axes[0].plot(bess["t"], bess["Vdc"], label="Vdc con BESS")
    axes[0].set_ylabel("V")

    axes[1].plot(base["t"], base["frequency_hz"], label="f sin BESS")
    axes[1].plot(bess["t"], bess["frequency_hz"], label="f con BESS")
    axes[1].set_ylabel("Hz")

    axes[2].plot(base["t"], p_pv_dc_base / 1000.0, label="p_pv_dc sin BESS")
    axes[2].plot(bess["t"], bess["p_pv_dc"] / 1000.0, label="p_pv_dc con BESS")
    axes[2].set_ylabel("kW")

    axes[3].plot(base["t"], np.zeros_like(base["t"]), label="p_bess_dc sin BESS")
    axes[3].plot(bess["t"], bess["p_bess_dc"] / 1000.0, label="p_bess_dc con BESS")
    axes[3].set_ylabel("kW")

    axes[4].plot(base["t"], np.zeros_like(base["t"]), label="i_bess sin BESS")
    axes[4].plot(bess["t"], bess["i_bess"], label="i_bess con BESS")
    axes[4].set_xlabel("t [s]")
    axes[4].set_ylabel("A")

    for axis in axes:
        axis.axvline(t_step, linestyle="--", alpha=0.7)
        axis.grid(True)
        axis.legend(loc="best")

    fig.suptitle("Comparacion diagnostica GFM: sin BESS vs con BESS")
    fig.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


def main() -> None:
    output_path = save_gfm_bess_comparison_figure()
    comparison = run_bess_comparison()
    base_span_hz = float(np.ptp(comparison["baseline"]["frequency_hz"]))
    bess_span_hz = float(np.ptp(comparison["with_bess"]["frequency_hz"]))

    print(f"figure_path={output_path}")
    print(f"frequency_span_without_bess_hz={base_span_hz:.9f}")
    print(f"frequency_span_with_bess_hz={bess_span_hz:.9f}")
    print(f"frequency_dynamic_without_bess={base_span_hz > 1e-9}")
    print(f"frequency_dynamic_with_bess={bess_span_hz > 1e-9}")


if __name__ == "__main__":
    main()
