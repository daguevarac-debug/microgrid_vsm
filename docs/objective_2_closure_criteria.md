# Criterio formal de cierre del Objetivo 2

## Propósito del documento

Este documento define el criterio formal de terminado del Objetivo 2 para el
estado actual de la tesis. El objetivo se considera cerrado cuando existe una
estrategia grid-forming clásica implementada en la planta completa de la
microrred, integrada con el BESS-SLB y sus restricciones operativas, acompañada
de evidencia reproducible de validación dinámica y de acople secuencial con el
sistema IEEE 33.

El cierre corresponde a la arquitectura VSG clásica seleccionada para esta
etapa. No equivale a una validación experimental, a un diseño industrial final,
a una demostración formal completa de estabilidad ni a la implementación de una
estrategia fraccionaria FOVIC.

## Qué significa "implementado"

En este repositorio, "implementado" significa que la lógica de control está
conectada a la planta eléctrica y participa en el mismo sistema de ecuaciones
diferenciales que el PV, el bus DC, el filtro LCL, la carga y, cuando aplica, el
BESS. No se considera suficiente una ecuación aislada o una simulación separada
del controlador.

El alcance implementado del Objetivo 2 incluye:

- `GFMController` como controlador grid-forming clásico compatible con la
  interfaz `InverterControllerBase`;
- dinámica reducida VSG/swing:
  `domega/dt = (P_ref - P_e - D*(omega - omega_ref))/M`;
- evolución angular `dtheta/dt = omega`;
- síntesis de tensión trifásica interna a partir de `theta`, `Vdc` y el límite de
  modulación;
- realimentación de potencia activa mediante
  `P_e = v_pcc^T i2`, usando la tensión completa del PCC para la carga R-L;
- integración de `omega` y `theta` en el mismo `solve_ivp` global de la planta;
- selección trazable del punto clásico `M = 80` y `D = 1500` para las campañas
  integradas;
- limitación de la referencia activa por la potencia neta disponible del PV y
  del BESS;
- supervisión del BESS mediante SoC, SoH, corriente disponible y potencia
  disponible;
- arquitectura opcional `MicrogridWithBESSPI` para regulación externa del bus DC
  mediante PI, con saturación y anti-windup condicional;
- acople del caso GFM+BESS con el IEEE 33 mediante el procedimiento secuencial
  one-way ya definido para la tesis.

## Orden protegido de estados

La integración no añade un segundo solucionador ni cambia silenciosamente el
significado de los estados. El orden vigente es:

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

GFM con BESS y PI externo de Vdc, 16 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
```

En modo GFM, `x[10] = omega`; en modo grid-following, `x[10] = xi_vdc`.
`x[11] = theta` se conserva en ambos modos. Los estados del BESS permanecen en
`x[12:15]` y el estado integral del PI externo se añade únicamente en `x[15]`.

## Qué significa "validado"

Para este cierre, "validado" significa que el comportamiento implementado fue
sometido a pruebas internas reproducibles de consistencia física, estabilidad
numérica práctica, respuesta dinámica y regresión. No significa validación
experimental ni certificación de desempeño.

La validación del Objetivo 2 incluye:

- pruebas unitarias del controlador y del mapeo de estados;
- operación estacionaria con GFM activo;
- escalón de carga moderado del 20 %;
- escalón severo del 40 % como caso de estrés;
- comparación con y sin BESS bajo el mismo perfil de carga;
- verificación de estados finitos y finalización correcta del solucionador;
- verificación de frecuencia dinámica mediante `frequency_hz = omega/(2*pi)`;
- verificación del balance físico del bus DC;
- verificación de `p_bess_dc = Vdc*i_bess`;
- verificación de límites de SoC, corriente y potencia del BESS;
- regresión de las validaciones protegidas del Objetivo 1;
- convergencia del flujo IEEE 33 y coherencia del perfil de tensión nodal;
- trazabilidad de `p_ss_kw` como promedio de `p_pcc` en la ventana estacionaria.

## Resultado de las campañas integradas

La campaña consolidada de `validate_gfm_integrated_system.py` registra:

| Escenario | Estado | Interpretación |
| --- | --- | --- |
| Operación estacionaria | PASS | GFM activo, solución finita y criterios estacionarios cumplidos. |
| Escalón de carga 20 % | PASS | Criterios de frecuencia y enlace DC cumplidos. |
| Escalón de carga 40 % | REVIEW | Simulación y frecuencia válidas; el enlace DC no cumple el umbral adoptado para el caso severo sin BESS. |
| BESS frente a no BESS | PASS | Comparación ejecutada con GFM activo y perfil equivalente. |

El estado global `REVIEW` no representa un error de implementación. Se debe al
criterio de tensión del enlace DC en el escalón severo del 40 %, donde la energía
disponible en el capacitor y la potencia de entrada no sostienen el mismo nivel
de tensión bajo la perturbación adoptada.

Las verificaciones adicionales relevantes quedaron en `PASS`:

- invariantes físicos del bus DC y del BESS;
- regresión de las validaciones del Objetivo 1;
- activación de `GFMController` en `IEEE33MicrogridWithBESS`;
- cálculo de `p_ss_kw` desde el promedio estacionario de `p_pcc`;
- convergencia de los flujos IEEE 33;
- coherencia del perfil de tensión respecto al baseline del Objetivo 1.

## Evidencia reproducible

Los elementos principales de evidencia son:

- `src/controllers/gfm_controller.py`;
- `src/controllers/grid_forming.py`;
- `src/controllers/dc_link_bess_pi.py`;
- `src/microgrid.py`;
- `src/microgrid_bess_pi.py`;
- `src/ieee33_coupling.py`;
- `src/validation/validate_gfm_integrated_system.py`;
- `src/validation/validate_physical_invariants.py`;
- `src/validation/validate_obj1_regression.py`;
- `src/validation/validate_ieee33_gfm_pcc_average.py`;
- `src/validation/validate_ieee33_gfm_voltage_profile.py`;
- `outputs/validation/gfm_integrated/summary.csv`;
- `outputs/validation/figures_final/ieee33_microgrid_resultado.png`;
- `docs/grid_forming_minimal_structure.md`;
- `docs/grid_forming_plant_control_interface.md`;
- `docs/model_assumptions.md`.

Comandos principales de reproducción:

```bash
python src/validation/validate_gfm_integrated_system.py
python src/validation/validate_physical_invariants.py
python src/validation/validate_obj1_regression.py
python src/validation/validate_ieee33_gfm_pcc_average.py
python src/validation/validate_ieee33_gfm_voltage_profile.py
```

## Qué queda para trabajo futuro

El cierre del Objetivo 2 no incluye:

- implementación final de FOVIC o de un controlador de orden fraccionario;
- comparación definitiva entre VSG clásico, FOVIC, droop y control V-f;
- optimización multiobjetivo o sintonía global de `M`, `D` y ganancias del PI;
- demostración formal completa de estabilidad de pequeña o gran señal;
- lazos internos detallados de corriente y tensión del convertidor;
- control reactivo `Q-V`, droop reactivo o regulación de tensión avanzada;
- convertidor bidireccional DC/DC detallado para el BESS;
- BMS industrial final con térmica, protecciones, balanceo y estimadores;
- modelos de carga medidos, ZIP completos, desbalance, motores o armónicos;
- perfiles reales de irradiancia, temperatura y demanda;
- validación experimental o hardware-in-the-loop;
- co-simulación dinámica bidireccional con el IEEE 33.

El acople IEEE 33 permanece como postprocesamiento secuencial one-way: primero se
simula la dinámica local, luego se calcula la potencia estacionaria en el PCC y
finalmente se ejecuta un flujo de potencia estático.

## Criterio formal de cierre

El Objetivo 2 se considera formalmente cerrado para el alcance actual porque:

1. existe un controlador GFM clásico integrado a la planta completa;
2. `omega` y `theta` se integran con los estados físicos en un único solucionador;
3. el BESS participa bajo límites de SoC, SoH, corriente y potencia;
4. existe una arquitectura PI explícita para soporte del enlace DC;
5. los escenarios integrados y los invariantes físicos tienen evidencia
   reproducible;
6. las validaciones del Objetivo 1 continúan pasando;
7. el caso IEEE 33 con GFM converge y mantiene coherencia con el baseline;
8. las limitaciones y los resultados `REVIEW` están documentados sin presentarlos
   como fallos ni como desempeño experimental.

Por tanto, el Objetivo 2 queda cerrado en su formulación e integración VSG
clásica. Las extensiones FOVIC, el hardware detallado, la optimización final y la
validación experimental permanecen como trabajo posterior.