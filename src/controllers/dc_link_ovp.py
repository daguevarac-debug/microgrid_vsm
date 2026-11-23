"""Decoupled, stateless averaged DC-link overvoltage protection (OVP) controller.

This module implements the optional averaged duty-cycle braking chopper law
for Objective 2 pending item P-07.

IMPORTANT SCIENTIFIC & ARCHITECTURAL NOTES:
1. All default thresholds (V_warn=357 V, V_on=374 V, V_hard=391 V, R_dump=25 ohm)
   are preliminary simulation hypotheses relative to Vdc_nom=340 V, NOT
   certified commercial hardware ratings.
2. The duty-cycle law ``D(Vdc) in [0, 1]`` is an averaged continuous model;
   its activation transition is NOT a physical PWM switching frequency.
3. No stateful latches, timers, or thermal energy accumulators are mutated
   inside ``solve_ivp`` RHS evaluations. Latching emergency hysteresis and
   thermal-energy trips require a hybrid event architecture and remain pending.
4. Optional ``pv_isolation_enabled`` provides a memoryless simulation
   abstraction (``i_pv_eff = 0`` while ``Vdc >= V_hard``) for testing power
   reduction; it is NOT a validated physical DC breaker model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DCLinkOVPParameters:
    """Parameters for the optional averaged DC-link OVP chopper.

    Disabled by default (``enabled=False``) to preserve baseline regressions.
    """

    enabled: bool = False
    v_warn_v: float = 357.0
    v_on_v: float = 374.0
    v_hard_v: float = 391.0
    r_dump_ohm: float = 25.0
    pv_isolation_enabled: bool = False

    def __post_init__(self) -> None:
        if not np.isfinite(self.v_warn_v) or self.v_warn_v <= 0.0:
            raise ValueError(f"v_warn_v must be > 0 and finite, got {self.v_warn_v!r}.")
        if not np.isfinite(self.v_on_v) or self.v_on_v <= 0.0:
            raise ValueError(f"v_on_v must be > 0 and finite, got {self.v_on_v!r}.")
        if not np.isfinite(self.v_hard_v) or self.v_hard_v <= self.v_on_v:
            raise ValueError(
                f"v_hard_v ({self.v_hard_v!r}) must be > v_on_v ({self.v_on_v!r})."
            )
        if not np.isfinite(self.r_dump_ohm) or self.r_dump_ohm <= 0.0:
            raise ValueError(f"r_dump_ohm must be > 0 and finite, got {self.r_dump_ohm!r}.")


@dataclass(frozen=True)
class DCLinkOVPOutput:
    """Stateless instantaneous OVP evaluation at a given DC-link voltage."""

    enabled: bool
    ovp_warn: bool
    chopper_active: bool
    duty_cycle: float
    i_dump_a: float
    p_dump_w: float
    hard_threshold_reached: bool
    pv_isolated_abstraction: bool


class DCLinkOVPController:
    """Stateless averaged OVP controller for DC-link braking chopper."""

    def __init__(self, params: DCLinkOVPParameters | None = None) -> None:
        self.params = params if params is not None else DCLinkOVPParameters()

    def compute(self, vdc_v: float) -> DCLinkOVPOutput:
        """Compute instantaneous averaged chopper current leaving the DC bus."""
        vdc = float(vdc_v)
        if not self.params.enabled or not np.isfinite(vdc) or vdc <= 0.0:
            return DCLinkOVPOutput(
                enabled=bool(self.params.enabled),
                ovp_warn=False,
                chopper_active=False,
                duty_cycle=0.0,
                i_dump_a=0.0,
                p_dump_w=0.0,
                hard_threshold_reached=False,
                pv_isolated_abstraction=False,
            )

        ovp_warn = vdc >= self.params.v_warn_v
        if vdc <= self.params.v_on_v:
            duty = 0.0
        elif vdc >= self.params.v_hard_v:
            duty = 1.0
        else:
            duty = (vdc - self.params.v_on_v) / (self.params.v_hard_v - self.params.v_on_v)

        chopper_active = duty > 0.0
        i_dump_a = (duty * vdc / self.params.r_dump_ohm) if chopper_active else 0.0
        p_dump_w = vdc * i_dump_a
        hard_reached = vdc >= self.params.v_hard_v
        pv_isolated = bool(self.params.pv_isolation_enabled and hard_reached)

        return DCLinkOVPOutput(
            enabled=True,
            ovp_warn=bool(ovp_warn),
            chopper_active=bool(chopper_active),
            duty_cycle=float(duty),
            i_dump_a=float(i_dump_a),
            p_dump_w=float(p_dump_w),
            hard_threshold_reached=bool(hard_reached),
            pv_isolated_abstraction=pv_isolated,
        )
