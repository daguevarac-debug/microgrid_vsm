# Objetivo 2 — Selección actualizada del punto de operación del VSG clásico

## 1. Motivo de la actualización

La selección anterior de `(M, D) = (40, 100)` se obtuvo restringiendo la
decisión a una región refinada derivada de la exploración histórica de 42
casos. Después de corregir la Tarea 4.2, esa secuencia dejó de representar la
cadena formal iniciada por el barrido `3 x 3`.

Esta actualización no modifica las ecuaciones del VSG, el escenario base, el
solver ni las métricas. Corrige la procedencia de los datos usados para escoger
el punto de operación.

## 2. Entradas formales

La cadena vigente utiliza:

```text
Barrido inicial:
outputs/validation/gfm_tuning/sensitivity_runs_initial_3x3.csv

Primer refinamiento anidado:
outputs/validation/gfm_tuning/refinement_compliant_iter1_m20-80_d200-1500.csv
```

Ambos archivos deben declarar:

```text
scenario = load_step_20_no_bess
criteria_version = obj2_vdc_event_relative_v2
vdc_acceptance_basis = max_abs_event_deviation_from_pre_step
```

## 3. Cadena de exploración

### Etapa inicial

```text
M = [2, 20, 80]
D = [0, 200, 1500]
9 ejecuciones
6 candidatos admisibles
```

Mejor candidato admisible:

```text
M = 80
D = 1500
max_frequency_drop_hz = 0.0101565401 Hz
```

### Refinamiento formal 1

```text
M = [20, 50, 80]
D = [200, 850, 1500]
9 ejecuciones
9 candidatos admisibles
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

La regla reproducible es:

```text
1. Validar escenario y versión de criterios.
2. Validar que cada etapa tenga máximo 3 valores de M y 3 de D.
3. Validar que cada etapa sea una malla cartesiana completa.
4. Validar que cada refinamiento esté contenido en la etapa anterior.
5. Filtrar candidatos plenamente admisibles.
6. Seleccionar argmin(max_frequency_drop_hz) en la última etapa formal.
7. Resolver empates exactos mediante menor M y luego menor D.
8. No afirmar optimalidad global.
```

## 5. Resultado actualizado

La pareja seleccionada dentro de la cadena formal es:

```text
M* = 80
D* = 1500
```

El punto anterior `(40, 100)` deja de ser la selección formal vigente. Sus
resultados no se eliminan: se conservan como evidencia histórica de una región
alternativa y de las validaciones que se ejecutaron con esa parametrización.

## 6. Advertencia de frontera

`(80, 1500)` coincide con el límite superior de ambos ejes en el barrido inicial
y en el primer refinamiento. Esto muestra una tendencia de la función objetivo
hacia valores crecientes de `M` y `D`.

La conclusión válida es:

```text
punto seleccionado dentro del dominio formal explorado y refinado
```

No es válido afirmar:

```text
óptimo global
parámetros físicamente superiores
mejor compromiso técnico-económico
```

El criterio vigente no penaliza el aumento de inercia virtual ni de
amortiguamiento. Una selección interior requeriría definir previamente otra
función objetivo o restricciones adicionales.

## 7. Estado de la validación cruzada

Las validaciones severa sin BESS y BESS-SoH existentes fueron ejecutadas con:

```text
M = 40
D = 100
```

No pueden transferirse automáticamente al nuevo punto. Por tanto, el estado
actual es:

```text
selection_changed_from_previous = True
cross_validation_pending = True
severe_no_bess_robustness_confirmed = pendiente
bess_soh_base_validation_pass = pendiente
```

La siguiente subtarea debe repetir las validaciones de la Tarea 4.3 con
`(M, D) = (80, 1500)` y conservar los resultados anteriores como históricos.

## 8. Implementación reproducible

El selector se ejecuta con:

```text
python src/validation/select_gfm_operating_point.py
```

También acepta varios refinamientos en orden cronológico:

```text
python src/validation/select_gfm_operating_point.py \
  --initial <initial.csv> \
  --refinement <refinement_1.csv> \
  --refinement <refinement_2.csv>
```

El resumen JSON se genera bajo `outputs/validation/gfm_tuning/` y no se incorpora
a Git.


## 9. Evidencia histórica de la selección anterior

La validación cruzada ya ejecutada con `(M, D) = (40, 100)` se conserva como
antecedente y no como resultado del nuevo punto.

### Escalón severo del 40 % sin BESS

```text
estado global = REVIEW
criterio de frecuencia = PASS
caída máxima de frecuencia = 0.1250844722 Hz
desviación máxima del evento DC = 17.2627428065 %
Vdc mínima posterior = 313.8409278465 V
criterio del enlace DC = FAIL
```

### Escenario base del 20 % con BESS-SLB

Los tres escenarios de SoH evaluados fueron admisibles:

```text
SoH = 1.00
SoH = 0.70
SoH nominal = 0.668182
estado global común = PASS
caída máxima de frecuencia = 0.0062308681 Hz
desviación máxima del evento DC = 0.9021555526 %
Vdc mínima posterior = 341.6935084071 V
```

Estos valores no se atribuyen a `(80, 1500)` hasta repetir las simulaciones.
