# Interfaz planta-control del inversor grid-forming

## Estado actual

La interfaz planta-control descrita en este documento ya está implementada en
`GFMController` y conectada al modelo dinámico de la microrred. El controlador
participa en el mismo `solve_ivp` global que la planta, el filtro LCL, la carga y,
cuando aplica, el BESS.

El baseline grid-following se conserva como ruta de regresión del Objetivo 1. La
ruta GFM usa `omega` como estado de control en `x[10]` y `theta` en `x[11]`.

## Entradas y referencias de control

### `P_ref` [W]

Referencia nominal de potencia activa. En ejecución se transforma en una
referencia efectiva limitada por disponibilidad energética:

```text
P_ref_eff = min(P_ref, P_net_ac_available)
```

La dinámica GFM usa:

```text
domega/dt = (P_ref_eff - P_e - D*(omega - omega_ref))/M
```

### `v_ln_rms` [V RMS fase-neutro]

Referencia de amplitud de tensión AC usada por el modulador trifásico.

### `m_base` / `m_ctrl` [-]

Límite e índice efectivo de modulación. La tensión sintetizable queda restringida
por `Vdc` y por el valor máximo permitido.

### `v_inv_abc` [V]

Señal manipulada directa entregada por el controlador a la planta. Se calcula a
partir de `theta`, la referencia de tensión, `Vdc` y el índice de modulación.

`idc_inv` no es una entrada manipulable independiente. Se deriva de la potencia
del puente y del bus DC.

## Mediciones de planta usadas por el controlador

`GFMController.compute_control()` recibe:

- `Vdc` [V];
- `v_pcc_abc` [V];
- `i1_abc` [A];
- `i2_abc` [A];
- `ipv` [A].

La potencia eléctrica realimentada se calcula como:

```text
P_e = v_pcc^T*i2
```

`v_pcc` debe ser la tensión completa de la carga R-L:

```text
v_pcc = R_load*i2 + L_load*di2/dt
```

No debe reemplazarse silenciosamente por la aproximación resistiva
`R_load*i2` en la ruta GFM integrada.

## Estados y mapeo protegido

### Sin BESS

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta]
```

### Con BESS

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess]
```

### Con BESS y PI externo de Vdc

```text
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
```

Reglas:

- `x[10] = omega` en GFM;
- `x[11] = theta`;
- `x[12] = soc_bess`;
- `x[13] = vrc_bess`;
- `x[14] = zdeg_bess`;
- `x[15] = xi_bess_vdc` solo en `MicrogridWithBESSPI`;
- todos los estados se integran con un único solucionador global.

## Dinámica interna del GFM

```text
dtheta/dt = omega
```

```text
domega/dt = (P_ref_eff - P_e - D*(omega - omega_ref))/M
```

Parámetros principales:

- `omega_ref = 2*pi*f_nom`;
- `theta0`;
- `P_ref`;
- `v_ln_rms`;
- `M` / `inertia_m`;
- `D` / `damping_d`;
- `m_base`.

La campaña integrada adoptó:

```text
M = 80
D = 1500
```

## Disponibilidad energética del lado DC

El controlador limita la referencia activa usando:

```text
P_pv_dc_available = max(Vdc*ipv, 0)
P_dc_net_available = P_pv_dc_available + P_bess_dc_actual
P_net_ac_available = max(eta*P_dc_net_available, 0)
P_ref_eff = min(P_ref, P_net_ac_available)
```

Cuando no hay BESS, `P_bess_dc_actual = 0`. Cuando el BESS carga,
`P_bess_dc_actual < 0` y reduce la potencia disponible. Cuando descarga, su aporte
positivo se limita por la disponibilidad operacional.

## Interfaz de supervisión BESS/BMS

Cuando la ruta BESS está activa, los siguientes datos deben suministrarse en
conjunto:

- `soc_bess` [-];
- `soh_bess` [-];
- `i_bess_max_available` [A];
- `p_bess_dc_max_available` [W];
- `p_bess_dc_actual` [W].

El controlador no sustituye al BMS. Usa estas señales para limitar la potencia
inercial disponible sin modificar la inercia virtual nominal `M`.

Convenciones protegidas:

```text
i_bess > 0  -> descarga
p_bess_dc > 0 -> potencia entregada al bus DC
i_bess < 0  -> carga
p_bess_dc < 0 -> potencia absorbida del bus DC
```

## PI externo de regulación del bus DC

`MicrogridWithBESSPI` añade una capa externa de regulación de `Vdc` mediante
`DCLinkBESSPIController`.

La interfaz del PI usa:

- `Vdc`;
- `Vdc_ref`;
- `xi_bess_vdc`;
- límites firmados de potencia de carga y descarga;
- señal explícita `bess_enabled`.

La salida es una referencia firmada de potencia BESS, posteriormente convertida
a corriente y limitada otra vez por corriente, potencia, SoC y SoH.

El anti-windup condicional evita seguir integrando cuando la salida está saturada
y el error empuja en la misma dirección de saturación.

Esta capa no modifica:

- `dtheta/dt`;
- `domega/dt`;
- `M`;
- `D`;
- el orden de los primeros 15 estados.

## Salidas observables

### Señales de planta y control

- `v_inv_abc` [V];
- `idc_inv` [A];
- `p_bridge` [W];
- `p_pcc` [W];
- `p_cmd` / `P_ref_eff` [W];
- `m_ctrl` [-].

### Estados y métricas GFM

- `theta` [rad];
- `omega` [rad/s];
- `frequency_hz = omega/(2*pi)` [Hz];
- desviación respecto a frecuencia nominal;
- nadir o máximo de frecuencia;
- RoCoF, cuando se calcula con una ventana y método documentados;
- tiempo de recuperación o asentamiento, según el criterio del escenario.

Las métricas de frecuencia son válidas como métricas dinámicas solo cuando
`GFMController` está activo y `x[10]` representa `omega`.

### Señales BESS

- `i_bess` [A];
- `p_bess_dc` [W];
- `soc_bess` [-];
- `soh_bess` [-];
- `vt_bess` [V];
- límites disponibles de corriente y potencia;
- estado de saturación y anti-windup para la arquitectura PI.

## Relación con IEEE 33

La interfaz local termina en la potencia activa del PCC. Para el estudio IEEE 33:

1. se simula la microrred local con GFM activo;
2. se calcula `p_ss_kw` como promedio de `p_pcc` en la ventana estacionaria;
3. se inyecta esa potencia como `sgen` estático en el nodo 18;
4. se ejecuta el flujo de potencia pandapower.

El IEEE 33 no entrega retroalimentación dinámica al controlador. Este acople no
es co-simulación en tiempo real.

## Validación de la interfaz

La coherencia de la interfaz está respaldada por:

- `validate_gfm_integrated_system.py`;
- `validate_physical_invariants.py`;
- `validate_ieee33_gfm_pcc_average.py`;
- `validate_ieee33_gfm_voltage_profile.py`;
- pruebas unitarias de mapeo de estados y dinámica GFM;
- regresión del Objetivo 1 mediante `validate_obj1_regression.py`.

## Alcance pendiente

No están implementados en esta interfaz:

- `Q_ref` y control Q-V;
- droop reactivo;
- lazos internos detallados de corriente y tensión;
- FOVIC o parámetros fraccionarios;
- convertidor DC/DC detallado;
- BMS industrial final;
- co-simulación dinámica con red externa;
- validación experimental.

La interfaz actual corresponde a una arquitectura VSG clásica integrada y
suficiente para el cierre formal del Objetivo 2, con las limitaciones anteriores
declaradas explícitamente.