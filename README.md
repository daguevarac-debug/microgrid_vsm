# Tesis: Microrred Fotovoltaica + BESS-SLB + GFM

## Descripción general

Este repositorio implementa una microrred fotovoltaica con BESS de segunda vida,
bus DC, inversor, filtro LCL, carga trifásica agregada y control grid-forming
clásico. El sistema incluye simulación dinámica local y acople secuencial
**one-way** al sistema de distribución IEEE de 33 nodos.

El proyecto conserva el baseline grid-following del Objetivo 1 y añade una ruta
GFM/VSG integrada para el Objetivo 2. La prioridad del repositorio es mantener
coherencia física, trazabilidad científica y separación explícita entre lo
implementado, lo validado y el trabajo futuro.

## Alcance actual implementado

### Planta de microrred

- Modelo del arreglo fotovoltaico parametrizado con el módulo de referencia
  **LONGi LR7-54HJD-500M**.
- Ajuste STC del modelo FV de un diodo validado contra datasheet.
- Dinámica del bus DC.
- Fuente inversora promediada, sin conmutación PWM explícita.
- Filtro LCL integrado en coordenadas `abc`.
- Carga agregada AC trifásica balanceada tipo R-L.
- Carga nominal `P_load_nominal = 3 kW`, `fp = 0.95` inductivo.
- Perturbaciones de carga nominal, `+20 %` y `+40 %`.
- Simulación de planta y control mediante un único `solve_ivp` global.

### Controladores disponibles

- `GridFollowingController`: controlador baseline del Objetivo 1 con estado
  integral `xi_vdc`.
- `GFMController`: controlador grid-forming clásico integrado a la planta
  completa.
- Dinámica reducida VSG/swing:

```text
dtheta/dt = omega
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

- Potencia eléctrica realimentada desde el PCC:

```text
P_e = v_pcc^T * i2
```

- Síntesis de tensión trifásica interna a partir de `theta`, `Vdc` y el límite de
  modulación.
- Punto de operación seleccionado para las validaciones integradas:
  `M = 80`, `D = 1500`.
- Limitación de `P_ref` según la potencia neta disponible del PV y el BESS.
- Frecuencia dinámica GFM calculada como `frequency_hz = omega/(2*pi)`.

### BESS-SLB

- Modelo dinámico Thevenin 1RC en `src/bess/model.py`.
- Caracterización OCV/R1/C1 desde `OCV_SOC.xlsx`.
- Degradación de primer orden mediante `z_deg`, SoH, capacidad efectiva y
  resistencia interna.
- Convención de capacidad:
  - `q_nom_ref_ah = 66 Ah`;
  - `soh_init_case = q_init_case_ah/q_nom_ref_ah`.
- Integración BESS-bus DC mediante:

```text
dVdc/dt = (ipv + i_bess - idc_inv)/Cdc
p_bess_dc = Vdc*i_bess
```

- Convención de signos:
  - `i_bess > 0`: descarga hacia el bus DC;
  - `i_bess < 0`: carga desde el bus DC.
- Límites de SoC, corriente y potencia.
- Disponibilidad de soporte dependiente del SoH.
- Supervisión de límites del BESS entregada al `GFMController`.
- Arquitectura `MicrogridWithBESSPI` con PI externo de regulación del bus DC,
  saturación y anti-windup condicional.

### Orden de estados protegido

```text
Grid-following sin BESS, 12 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, xi_vdc, theta]

GFM sin BESS, 12 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta]

Grid-following con BESS, 15 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, xi_vdc, theta,
 soc_bess, vrc_bess, zdeg_bess]

GFM con BESS, 15 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess]

GFM con BESS y PI de Vdc, 16 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
```

En GFM, `x[10] = omega`; en grid-following, `x[10] = xi_vdc`.
`x[11] = theta` se conserva en ambos modos.

### Acople IEEE 33

- PCC en el nodo 18 de la red IEEE 33 a `12.66 kV`.
- `IEEE33MicrogridWithBESS` usa `GFMController` activo.
- `p_ss_kw` se calcula como el promedio de `p_pcc` en la ventana estacionaria.
- Esa potencia se inyecta como `sgen` estático en pandapower.
- El flujo base y el flujo con microrred convergen.
- El perfil nodal con GFM conserva coherencia con el baseline del Objetivo 1.
- La figura final está en:
  `outputs/validation/figures_final/ieee33_microgrid_resultado.png`.

El acople sigue siendo secuencial one-way. El IEEE 33 no retroalimenta la
simulación temporal de la microrred y no existe co-simulación dinámica.

## Estado de validación

### Modelo FV

- Ajuste STC frente a datasheet: `PASS`.
- Errores reportados:
  - `Vmpp = -0.2423 %`;
  - `Impp = -3.0904 %`;
  - `Isc = -0.0000 %`.

### BESS-SLB

| Validación | Resultado | Estado |
| --- | --- | --- |
| Braco Fig. 5(b), SL 0.5C | MAPE `6.4201 %` | PASS |
| Braco Fig. 5(b), SL 1C | MAPE `8.1716 %` | PASS |
| Braco Fig. 5(b), SL 1.5C | MAPE `9.3351 %` | PASS |
| Step-2 1RC | dinámica SoC/Vrc/Vterminal | PASS |
| Step-3 degradación | z_deg/SoH/Q_eff/R0 | PASS |
| Límites operativos | SoC/corriente/potencia/SoH | PASS |
| Unidades y escala Vdc/vt_bess | advertencia interpretativa | REVIEW |

Un `REVIEW` por la relación `Vdc/vt_bess` no es una falla numérica. Indica que
el convertidor DC/DC y el escalamiento completo del banco aún son idealizados.

### GFM integrado

Resultados de `validate_gfm_integrated_system.py`:

| Escenario | Estado |
| --- | --- |
| Operación estacionaria | PASS |
| Escalón de carga 20 % | PASS |
| Escalón de carga 40 % | REVIEW |
| BESS frente a no BESS | PASS |

El caso del 40 % queda en `REVIEW` porque el enlace DC no cumple el umbral
adoptado para esa perturbación severa sin BESS. La simulación, el controlador y
la respuesta de frecuencia son válidos.

Validaciones adicionales:

- invariantes físicos DC/BESS: `PASS`;
- regresión de validaciones del Objetivo 1: `PASS`;
- activación GFM en IEEE 33: `PASS`;
- promedio estacionario de `p_pcc`: `PASS`;
- convergencia y perfil nodal IEEE 33: `PASS`.

## Puntos de entrada principales

```bash
# Baseline local grid-following
python src/main.py
python src/main.py --with-bess
python src/main.py --compare-bess

# Acople IEEE 33 con GFM+BESS activo
python src/ieee33_main.py

# Validación integrada GFM
python src/validation/validate_gfm_integrated_system.py
python src/validation/validate_physical_invariants.py
python src/validation/validate_obj1_regression.py

# Validación IEEE 33 con GFM
python src/validation/validate_ieee33_gfm_pcc_average.py
python src/validation/validate_ieee33_gfm_voltage_profile.py

# Validaciones BESS principales
python src/validation/validate_bess_step2.py
python src/validation/validate_bess_step3.py
python src/validation/validate_bess_soc_operational_limits.py
python src/validation/compare_bess_soh_scenarios.py

# Validaciones baseline
python src/validation/validate_pv_stc_fit.py
python src/validation/validate_lcl_no_unphysical_oscillations.py
python src/validation/validate_microgrid_rl_load.py
python src/validation/validate_islanded_operation_scenarios.py
```

## Documentación de cierre

- Cierre formal del Objetivo 1:
  `docs/objective_1_closure_criteria.md`.
- Cierre formal del Objetivo 2:
  `docs/objective_2_closure_criteria.md`.
- Supuestos y limitaciones:
  `docs/model_assumptions.md`.
- Estructura GFM:
  `docs/grid_forming_minimal_structure.md`.
- Interfaz planta-control:
  `docs/grid_forming_plant_control_interface.md`.

## Funcionalidades no implementadas aún

- Estrategia FOVIC u otra formulación de orden fraccionario.
- Comparación final entre VSG, FOVIC, droop y control V-f.
- Optimización global de `M`, `D` y ganancias del PI.
- Demostración formal completa de estabilidad.
- Control reactivo `Q-V` y lazos internos detallados de tensión/corriente.
- Convertidor bidireccional DC/DC detallado.
- BMS industrial final con térmica, protecciones y estimación avanzada.
- Perfiles reales medidos de irradiancia, temperatura y demanda.
- Modelo ZIP completo, desbalance, motores, armónicos y cargas no lineales.
- Validación experimental, HIL o prototipo físico.
- Co-simulación dinámica bidireccional con IEEE 33.

## Alcance académico

El Objetivo 2 queda cerrado para una arquitectura VSG clásica integrada y
validada internamente. Este cierre no debe presentarse como validación
experimental ni como implementación final de FOVIC. El resultado global
`REVIEW` de la campaña integrada se mantiene trazado por el caso severo del
40 %, sin convertirlo en un error de software.

## Instrucciones básicas

1. Crear y activar un entorno virtual de Python.
2. Instalar `numpy`, `scipy`, `matplotlib`, `pandas`, `openpyxl` y `pandapower`.
3. Ejecutar los comandos desde la raíz del repositorio.

## Notas de ingeniería

- No cambiar ecuaciones físicas ni convenciones de signos sin justificación.
- No cambiar silenciosamente el orden de estados.
- Mantener un único solucionador global para planta, GFM y BESS.
- Conservar el baseline grid-following como ruta de regresión.
- No interpretar el acople IEEE 33 como co-simulación dinámica.
- No presentar código futuro como contribución implementada.