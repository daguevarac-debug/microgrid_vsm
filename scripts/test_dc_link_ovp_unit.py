"""Fast unit tests for DCLinkOVPController and MicrogridWithBESSDCDC OVP wiring."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from controllers.dc_link_ovp import DCLinkOVPController, DCLinkOVPParameters  # noqa: E402


def main() -> None:
    # 1. Default disabled
    ctrl_off = DCLinkOVPController()
    out_off = ctrl_off.compute(410.0)
    assert out_off.enabled is False
    assert out_off.i_dump_a == 0.0
    assert out_off.duty_cycle == 0.0
    assert out_off.pv_isolated_abstraction is False

    # 2. Enabled averaged duty cycle bounds [0, 1]
    ctrl_on = DCLinkOVPController(
        DCLinkOVPParameters(enabled=True, v_warn_v=357.0, v_on_v=374.0, v_hard_v=391.0, r_dump_ohm=25.0)
    )
    assert ctrl_on.compute(350.0).ovp_warn is False
    out_warn = ctrl_on.compute(360.0)
    assert out_warn.ovp_warn is True and out_warn.chopper_active is False and out_warn.i_dump_a == 0.0

    out_mid = ctrl_on.compute(382.5)
    assert abs(out_mid.duty_cycle - 0.5) < 1e-12
    assert abs(out_mid.i_dump_a - (0.5 * 382.5 / 25.0)) < 1e-12
    assert out_mid.hard_threshold_reached is False

    out_hard = ctrl_on.compute(400.0)
    assert out_hard.duty_cycle == 1.0
    assert out_hard.hard_threshold_reached is True
    assert out_hard.pv_isolated_abstraction is False

    # 3. Stateless PV isolation simulation abstraction
    ctrl_iso = DCLinkOVPController(
        DCLinkOVPParameters(enabled=True, pv_isolation_enabled=True)
    )
    assert ctrl_iso.compute(390.9).pv_isolated_abstraction is False
    assert ctrl_iso.compute(391.0).pv_isolated_abstraction is True
    print("test_dc_link_ovp_unit=PASS")


if __name__ == "__main__":
    main()
