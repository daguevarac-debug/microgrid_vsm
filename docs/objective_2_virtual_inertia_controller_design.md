# Objective 2.1: Classical VSG-BESS Controller Design

## Purpose

This document consolidates Activity 2.1 of Specific Objective 2: the design
description of the implemented virtual-inertia controller for the PV microgrid
with second-life BESS support. It is a technical consolidation of the current
implemented architecture and should be read together with:

- `docs/grid_forming_minimal_structure.md`
- `docs/grid_forming_plant_control_interface.md`
- `docs/model_assumptions.md`
- `docs/objective_2_closure_criteria.md`

The selected strategy is a classical grid-forming/VSG controller. It is not the
final FOVIC strategy. Therefore:

```text
alpha = no aplicable para la estrategia VSG clasica seleccionada.
```

No fractional-order state, Oustaloup approximation, FOVIC comparison, or new
controller family is introduced by this design document.

## Complete Architecture

The implemented local microgrid model is composed of:

- PV array represented by the single-diode model.
- DC link represented by the capacitor voltage state `Vdc`.
- Second-life BESS represented by a Thevenin 1RC model with first-order
  degradation.
- Simplified BMS supervision layer for SoC, SoH, current availability and power
  availability.
- Classical GFM/VSG controller implemented by `GFMController`.
- Averaged inverter voltage source with modulation and UVLO limits.
- LCL filter in `abc` coordinates.
- PCC with complete R-L load voltage feedback.
- Balanced three-phase aggregated R-L load.
- Optional external DC-link PI controller implemented by `MicrogridWithBESSPI`.

All dynamic states are integrated by one global ODE solve. There is no nested or
secondary `solve_ivp` for GFM, BESS, or PI dynamics.

The energy path is:

```text
PV -> DC link -> averaged inverter -> LCL filter -> PCC -> R-L load
```

The BESS is coupled bidirectionally to the DC link through the signed exchange
current `i_bess`. The implemented sign convention is protected:

```text
i_bess > 0: discharge, BESS injects into the DC bus
i_bess < 0: charge, BESS absorbs from the DC bus
p_bess_dc = Vdc*i_bess
```

The BMS layer is simplified. It limits current and power from SoC and SoH and
blocks charge/discharge at the configured SoC boundaries. It is not an
industrial BMS, and the BESS coupling is not a detailed bidirectional DC/DC
converter model.

## Implemented Equations

### VSG Angular Dynamics

In GFM mode, the protected controller state is:

```text
x[10] = omega
x[11] = theta
```

The implemented reduced VSG dynamics are:

```text
dtheta/dt = omega
```

```text
domega/dt = (P_ref_eff - P_e - D*(omega - omega_ref))/M
```

where `M = 80` [W*s^2/rad] and `D = 1500` [W*s/rad] are the selected
integrated VSG point for the current campaigns. The dynamic frequency metric is:

```text
frequency_hz = omega/(2*pi)
```

### Electrical Power Feedback

The active electrical power used by the VSG is calculated from the complete PCC
voltage and the filter output current:

```text
P_e = v_pcc^T*i2
```

For the R-L load closure:

```text
v_pcc = R_load*i2 + L_load*di2/dt
```

This is the feedback used in the integrated GFM path. It must not be silently
replaced by the legacy purely resistive approximation.

### DC Availability and Effective Active-Power Reference

The nominal active-power reference is limited by net DC-side availability:

```text
P_pv_dc_available = max(Vdc*ipv, 0)
P_dc_net_available = P_pv_dc_available + P_bess_dc_actual
P_net_ac_available = max(eta*P_dc_net_available, 0)
P_ref_eff = min(P_ref, P_net_ac_available)
```

When the BESS charges, `P_bess_dc_actual < 0` and the net available GFM active
power is reduced. When the BESS discharges, positive support is allowed only
inside the available SoC, SoH, current and power limits.

### Three-Phase Voltage Synthesis

The inverter synthesizes an internal balanced voltage from `theta`:

```text
v_a = Vpk*sin(theta)
v_b = Vpk*sin(theta - 2*pi/3)
v_c = Vpk*sin(theta + 2*pi/3)
```

The required modulation index is:

```text
m_required = 2*Vpk/Vdc
m_ctrl = min(m_base, m_required)
```

The voltage source is averaged. PWM switching, switching harmonics and detailed
inner current/voltage loops are outside the implemented scope.

### UVLO and Inverter DC Current

If the effective DC-link voltage is below UVLO:

```text
v_inv = [0, 0, 0]
p_bridge = 0
idc_inv = 0
m_ctrl = 0
```

Otherwise:

```text
p_bridge = v_inv^T*i1
p_dc = max(p_bridge, 0)/eta
idc_inv = p_dc/max(Vdc, Vmin)
```

The current averaged baseline convention keeps the inverter DC current
unidirectional from DC to AC.

### DC-Link Balance

The protected DC-link equation is:

```text
dVdc/dt = (ipv + i_bess - idc_inv)/Cdc
```

`ipv` injects current from the PV source, `i_bess` is positive for BESS
discharge, and `idc_inv` is current absorbed by the inverter from the DC bus.

### BESS Thevenin 1RC Model

The BESS internal model is:

```text
V_t = OCV(SoC) - i_bess*R0(SoH) - V_rc
dV_rc/dt = -V_rc/(R1*C1) + i_bess/C1
dSoC/dt = -i_bess/(3600*Q_eff)
dz_deg/dt = |i_bess|/3600
SoH = max(soh_min, SoH_0 - k_deg*z_deg)
Q_eff = Q_nom*SoH
R0 = R0_nom*(1 + k_R*(1 - SoH))
```

The capacity convention is:

```text
q_nom_ref_ah = 66 Ah
soh_init_case = q_init_case_ah/q_nom_ref_ah
Q_eff(0) = q_init_case_ah
```

### BESS Availability and Directional Limits

The implemented operating limits are:

```text
soc_min = 0.10
soc_max = 0.90
i_bess_max_nominal = 66 A
p_bess_dc_max_nominal = 22440 W
i_bess_max_available = i_bess_max_nominal*SoH
p_bess_dc_max_available = min(p_bess_dc_max_nominal,
                              Vdc_ref*i_bess_max_available)
```

Operational blocking:

```text
if soc_bess <= soc_min and i_bess > 0: i_bess = 0
if soc_bess >= soc_max and i_bess < 0: i_bess = 0
```

The implemented 15-state BESS coupling uses a proportional DC-link support law
and then applies current, SoC and power constraints. The explicit 16-state PI
architecture replaces the proportional BESS command with a signed PI power
request, then applies the same physical constraints before conversion to
current.

### Optional External DC-Link PI and Anti-Windup

`MicrogridWithBESSPI` appends only one state:

```text
x[15] = xi_bess_vdc
```

The PI equations are:

```text
e_vdc = Vdc_ref - Vdc
P_bess_ref_unsat = kp*e_vdc + ki*xi_bess_vdc
P_bess_ref = sat(P_bess_ref_unsat, P_min, P_max)
i_bess = P_bess_ref/max(Vdc, Vmin)
```

where `P_min <= 0` is the available charging limit and `P_max >= 0` is the
available discharging limit. If `bess_enabled=False`, both limits are forced to
zero.

Conditional anti-windup freezes the integrator when saturation is active and the
voltage error would push the command farther into the active limit:

```text
dxi_bess_vdc/dt = 0       if anti_windup_active
dxi_bess_vdc/dt = e_vdc   otherwise
```

The PI does not modify `dtheta/dt`, `domega/dt`, `M`, `D`, or the first 15
states.

## Protected State Orders

### Grid-Following Without BESS, 12 States

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, xi_vdc, theta]
```

### GFM Without BESS, 12 States

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta]
```

### Grid-Following With BESS, 15 States

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, xi_vdc, theta,
 soc_bess, vrc_bess, zdeg_bess]
```

### GFM With BESS, 15 States

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess]
```

### GFM With BESS and External DC-Link PI, 16 States

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
```

The BESS states remain `x[12]`, `x[13]`, and `x[14]`. The PI state is appended
only at `x[15]` and only in the explicit 16-state architecture.

## Variable Table

| Symbol | Code name | Unit | Nature | Related equation |
| --- | --- | --- | --- | --- |
| `Vdc` | `Vdc`, `x[0]` | V | State | `dVdc/dt = (ipv+i_bess-idc_inv)/Cdc` |
| `i1_abc` | `i1`, `x[1:4]` | A | State | LCL input inductor dynamics |
| `vc_abc` | `vc`, `x[4:7]` | V | State | LCL capacitor dynamics |
| `i2_abc` | `i2`, `x[7:10]` | A | State | LCL output/load current dynamics |
| `omega` | `omega`, `x[10]` in GFM | rad/s | State | `domega/dt = (P_ref_eff-P_e-D*(omega-omega_ref))/M` |
| `xi_vdc` | `xi_vdc`, `x[10]` in grid-following | V*s | State | Objective 1 grid-following path |
| `theta` | `theta`, `x[11]` | rad | State | `dtheta/dt = omega` |
| `SoC` | `soc_bess`, `x[12]` | - | State | `dSoC/dt = -i_bess/(3600*Q_eff)` |
| `V_rc` | `vrc_bess`, `x[13]` | V | State | `dV_rc/dt = -V_rc/(R1*C1)+i_bess/C1` |
| `z_deg` | `zdeg_bess`, `x[14]` | Ah | State | `dz_deg/dt = |i_bess|/3600` |
| `xi_BESS` | `xi_bess_vdc`, `x[15]` | V*s | State | External PI anti-windup |
| `P_e` | `p_e`, `p_pcc` | W | Signal | `P_e = v_pcc^T*i2` |
| `P_ref` | `p_ref` | W | Parameter | Nominal active-power command |
| `P_ref_eff` | `p_ref_eff`, `p_cmd` | W | Signal | `min(P_ref, P_net_ac_available)` |
| `M` | `inertia_m` | W*s^2/rad | Parameter | VSG swing denominator |
| `D` | `damping_d` | W*s/rad | Parameter | Damping term `D*(omega-omega_ref)` |
| `omega_ref` | `omega_ref` | rad/s | Parameter | Nominal angular frequency |
| `f` | `frequency_hz` | Hz | Signal | `omega/(2*pi)` |
| `v_pcc_abc` | `v_pcc` | V | Signal | `R_load*i2 + L_load*di2/dt` |
| `v_inv_abc` | `v_inv` | V | Signal | Three-phase synthesis from `theta` |
| `m` | `m_ctrl` | - | Signal | `min(m_base, 2*Vpk/Vdc)` |
| `m_base` | `m_base` | - | Parameter | Modulation limit |
| `Vuvlo` | `v_uvlo` | V | Parameter | UVLO zero-output threshold |
| `ipv` | `Ipv`, `ipv` | A | Signal | PV current into DC bus |
| `idc_inv` | `idc_inv` | A | Signal | Inverter DC current draw |
| `i_bess` | `i_bess` | A | Signal | Positive discharge, negative charge |
| `p_bess_dc` | `p_bess_dc_actual` | W | Signal | `Vdc*i_bess` |
| `SoH` | `soh_bess` | - | Signal | `max(soh_min, SoH_0-k_deg*z_deg)` |
| `Q_eff` | `effective_capacity_*` | Ah | Signal | `Q_nom*SoH` |
| `R0` | `r0(soh)` | ohm | Signal | `R0_nom*(1+k_R*(1-SoH))` |
| `R1`, `C1` | `r1(soc)`, `c1(soc)` | ohm, F | Signal | 1RC branch dynamics |
| `V_t` | `vt_bess` | V | Signal | `OCV(SoC)-i_bess*R0-V_rc` |
| `i_max` | `i_bess_max_available` | A | Signal | `i_bess_max_nominal*SoH` |
| `P_max` | `p_bess_dc_max_available` | W | Signal | `min(p_nom, Vdc_ref*i_max)` |
| `e_vdc` | `vdc_error_v` | V | Signal | `Vdc_ref - Vdc` |
| `P_BESS,ref` | `p_bess_ref_w` | W | Signal | External PI saturated output |
| `Cdc` | `Cdc` | F | Parameter | DC-link capacitance |
| `eta` | `eta` | - | Parameter | DC/AC averaged efficiency |

## Relation Between `M` and Conventional Inertia `H`

The implemented VSG equation uses active power in W and angular frequency in
rad/s:

```text
domega/dt = (P_ref_eff - P_e - D*(omega - omega_ref))/M
```

Therefore `M` is not directly equivalent to the conventional synchronous-machine
inertia constant `H`. A conventional conversion can be stated only after a power
base is explicitly declared:

```text
M = 2*H*S_base/omega_ref
```

with:

- `M` in W*s^2/rad for the implemented equation;
- `H` in seconds;
- `S_base` in VA or W under the adopted per-unit/base convention;
- `omega_ref` in rad/s.

Dimensionally, `2*H*S_base/omega_ref` gives `s*W/(rad/s) = W*s^2/rad`, matching
the `M` unit required by the implemented equation.

This relation is conditional on a declared `S_base`. This document does not
declare a new `S_base`, so `H` cannot be obtained numerically from the current
selected `M = 80`.

## Scope and Limitations

This design supports internal, reproducible validation of the implemented
classical VSG-BESS architecture. It does not claim:

- experimental validation;
- hardware-in-the-loop validation;
- final FOVIC implementation;
- final comparison among VSG, FOVIC, droop and V-f control;
- detailed bidirectional DC/DC converter modeling;
- industrial final BMS logic;
- detailed inner voltage/current loops;
- complete Q-V control;
- global tuning optimization;
- full formal stability proof;
- measured operating profiles;
- dynamic bidirectional co-simulation with IEEE 33.

The IEEE 33 coupling remains sequential one-way postprocessing: the local
microgrid dynamics are simulated first, `p_pcc` is averaged in the configured
steady-state window, and that scalar is injected as a static `sgen` in the
network power-flow case.
