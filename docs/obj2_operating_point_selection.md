# Objetivo 2 — Selección y validación cruzada del punto de operación del VSG clásico

## 1. Motivo de la actualización

La selección anterior `(M, D) = (40, 100)` provenía de una región refinada
identificada mediante la exploración histórica de `42` casos. Después de
corregir la Tarea 4.2, la selección formal debe comenzar en el barrido inicial
`3 x 3` y continuar únicamente mediante refinamientos anidados de máximo
`3 x 3`.

Esta actualización no modifica las ecuaciones del VSG, la planta, el solver,
el escenario base ni las métricas de aceptación.

## 2. Entradas formales de selección

```text
Barrido inicial:
outputs/validation/gfm_tuning/sensitivity_runs_initial_3x3.csv

Primer refinamiento anidado:
outputs/validation/gfm_tuning/refinement_compliant_iter1_m20-80_d200-1500.csv
```

Los dos archivos usan:

```text
scenario = load_step_20_no_bess
criteria_version = obj2_vdc_event_relative_v2
vdc_acceptance_basis = max_abs_event_deviation_from_pre_step
```

## 3. Cadena formal de exploración

### 3.1 Barrido inicial

```text
M = [2, 20, 80]
D = [0, 200, 1500]
ejecuciones = 9
candidatos admisibles = 6
```

Mejor candidato admisible:

```text
M = 80
D = 1500
max_frequency_drop_hz = 0.0101565401 Hz
```

### 3.2 Primer refinamiento

```text
M = [20, 50, 80]
D = [200, 850, 1500]
ejecuciones = 9
candidatos admisibles = 9
```

Mejor candidato admisible:

```text
M = 80
D = 1500
max_frequency_drop_hz = 0.0101565401 Hz
frequency_recovery_time_s = 0.0000050604 s
vdc_event_max_abs_deviation_pct = 3.8350776972 %
vdc_min_post_step_v = 364.7632802561 V
```

## 4. Regla de selección

```text
1. Validar escenario y versión de criterios.
2. Limitar cada etapa a tres valores de M y tres valores de D.
3. Exigir una malla cartesiana completa.
4. Exigir que cada refinamiento permanezca dentro de la etapa anterior.
5. Exigir que al menos uno de los intervalos se reduzca.
6. Filtrar candidatos plenamente admisibles.
7. Seleccionar argmin(max_frequency_drop_hz) en la última etapa formal.
8. Resolver empates exactos mediante menor M y luego menor D.
9. No afirmar optimalidad global.
```

## 5. Punto seleccionado

```text
M* = 80
D* = 1500
```

La pareja anterior `(40, 100)` deja de ser la selección formal vigente. Sus
resultados se conservan como evidencia histórica.

## 6. Advertencia de frontera

`(80, 1500)` coincide con el límite superior de ambos ejes en el barrido
inicial y en el refinamiento. La función objetivo vigente minimiza la caída
máxima de frecuencia, pero no penaliza el aumento de inercia virtual,
amortiguamiento, esfuerzo de control ni costo físico.

La denominación válida es:

```text
punto seleccionado dentro del dominio formal explorado y refinado
```

No se afirma que sea un óptimo global ni el mejor compromiso técnico-económico.

## 7. Validación cruzada ejecutada con `(80, 1500)`

Los resultados locales se generaron en:

```text
Escenario severo sin BESS:
outputs/validation/gfm_tuning/selected_m80_d1500_severe_40pct.json

Escenarios BESS-SoH:
outputs/validation/gfm_bess_soh_scenarios/
gfm_m80_d1500_bess_soh_scenarios_summary.csv

Cierre de coherencia de frecuencia:
outputs/validation/activity_2_3_frequency_metric/
activity_2_3_frequency_metric_closure_m80_d1500.json
```

Estos archivos permanecen bajo `outputs/` y no se incorporan a Git.

## 8. Escalón severo del 40 % sin BESS

La integración fue numéricamente válida:

```text
solver_success = True
states_finite = True
scenario_configuration_ok = True
```

Resultado:

| Métrica | Valor |
|---|---:|
| Estado global | `REVIEW` |
| Robustez severa confirmada | `False` |
| Caída máxima de frecuencia | `0.0251256386 Hz` |
| Desviación máxima absoluta de frecuencia | `0.0224076271 Hz` |
| Tiempo de recuperación | `6.8230e-07 s` |
| Criterio de frecuencia | `PASS` |
| Desviación máxima del evento DC | `17.2538826185 %` |
| `Vdc` mínima posterior | `313.8643954759 V` |
| Criterio del enlace DC | `FAIL` |

Frente a `(40, 100)`, la caída máxima de frecuencia disminuyó aproximadamente
`79.9131 %`. Sin embargo, la desviación del enlace DC solo cambió cerca de
`0.00886` puntos porcentuales y la `Vdc` mínima aumentó aproximadamente
`0.02347 V`.

El resultado confirma que la nueva sintonización mejora la respuesta de
frecuencia, pero no resuelve el déficit energético del escenario severo sin
BESS.

## 9. Escenario base del 20 % con BESS-SLB

Se evaluaron tres condiciones iniciales:

| Escenario | SoH inicial | Capacidad inicial [Ah] | Estado |
|---|---:|---:|---|
| SoH nuevo | `1.000000` | `66.0` | `PASS` |
| SoH 0.70 | `0.700000` | `46.2` | `PASS` |
| SoH nominal | `0.668182` | `44.1` | `PASS` |

Resultados comunes:

| Métrica | Valor |
|---|---:|
| Caída máxima de frecuencia | `0.0029747821 Hz` |
| Desviación máxima absoluta de frecuencia | `0.0038709704 Hz` |
| Tiempo de recuperación | `1.1808e-06 s` |
| Criterio de frecuencia | `PASS` |
| Desviación máxima del evento DC | `0.9022808857 %` |
| `Vdc` mínima posterior | `341.6906381719 V` |
| Criterio del enlace DC | `PASS` |
| Corriente pico absoluta del BESS | `2.4008590829 A` |
| Potencia pico absoluta del BESS | `827.8203368618 W` |
| Energía intercambiada | `0.4581650334 Wh` |
| Límite de corriente | `PASS` |
| Límite de potencia | `PASS` |

La caída de frecuencia disminuyó aproximadamente `52.2573 %` frente al caso
BESS-SoH ejecutado con `(40, 100)`.

La variación de SoC aumentó al reducir la capacidad disponible:

| Escenario | Variación de SoC |
|---|---:|
| SoH 1.00 | `2.0315968e-05` |
| SoH 0.70 | `2.9022817e-05` |
| SoH nominal | `3.0404852e-05` |

Las respuestas de frecuencia, enlace DC, corriente y potencia fueron idénticas
entre los tres SoH porque la demanda permaneció muy por debajo de los límites
dependientes de degradación.

En todos los casos:

```text
bess_exchange_mode = charge_only
bess_discharge_observed = False
```

Por tanto, la prueba confirma admisibilidad dentro de los límites implementados,
pero no demuestra soporte por descarga ni diferenciación dinámica bajo
saturación.

## 10. Cierre de coherencia de frecuencia

La Actividad 2.3 comprobó los cuatro registros correspondientes a
`(M, D) = (80, 1500)`:

```text
status = PASS
all_frequency_metrics_coherent = True
all_frequency_criteria_pass = True
all_selected_point_records_match = True
all_post_step_traces_within_recovery_band = True
```

La métrica canónica permanece como:

```text
max_frequency_abs_deviation_hz
```

## 11. Estado final

```text
selection_changed_from_previous = True
cross_validation_matches_selected = True
cross_validation_pending = False
severe_no_bess_robustness_confirmed = False
bess_soh_base_validation_pass = True
activity_2_3_frequency_metric_closure_pass = True
global_optimum_claimed = False
```

La validación cruzada está cerrada para el punto formal `(80, 1500)`. El estado
global no es completamente robusto porque el caso severo sin BESS continúa en
`REVIEW` debido al criterio del enlace DC.

## 12. Implementación reproducible

Selección:

```text
python src/validation/select_gfm_operating_point.py
```

Escenario severo:

```text
python src/validation/validate_islanded_operation_scenarios.py \
  --gfm-selected-severe
```

Comparación BESS-SoH:

```text
python src/validation/compare_bess_soh_scenarios.py \
  --gfm-selected
```

Cierre de frecuencia:

```text
python src/validation/validate_activity_2_3_frequency_metric.py
```

## 13. Evidencia histórica de `(40, 100)`

La selección anterior produjo:

```text
Escenario severo sin BESS:
estado = REVIEW
caída máxima de frecuencia = 0.1250844722 Hz
desviación máxima del evento DC = 17.2627428065 %
Vdc mínima posterior = 313.8409278465 V

Escenario base con BESS-SLB:
estado común de los tres SoH = PASS
caída máxima de frecuencia = 0.0062308681 Hz
desviación máxima del evento DC = 0.9021555526 %
Vdc mínima posterior = 341.6935084071 V
```

Estos datos permanecen como comparación histórica y no se atribuyen al punto
formal vigente.
