# Texto de tesis: cierre formal de la Actividad 2.3

## Ubicación en el documento

Incorporar esta subsección al cierre de la sección de selección y validación cruzada del punto de operación grid-forming, después de presentar los resultados del punto `(M, D) = (40, 100)` y antes de iniciar la actividad siguiente.

## Criterio de cierre

La Actividad 2.3 verifica que la métrica de desviación absoluta de frecuencia registrada en los escenarios de validación cruzada sea semántica y numéricamente coherente con los criterios definidos en la Tarea 4.1.

El nombre canónico implementado es:

```text
max_frequency_abs_deviation_hz
```

El nombre `max_abs_frequency_deviation_hz` no forma parte del contrato actual de resultados y se considera un alias no canónico.

La métrica se define respecto de la frecuencia nominal:

```text
max_frequency_abs_deviation_hz
    = max_{t >= t_step} |f(t) - 60 Hz|
```

Esta magnitud no reemplaza la caída máxima de frecuencia, cuya referencia es el promedio previo al evento:

```text
max_frequency_drop_hz
    = max(f_pre - min(f_post), 0)
```

Por tanto, ambas métricas pueden tomar valores diferentes sin constituir una inconsistencia. La primera mide la distancia respecto de `60 Hz`; la segunda mide la caída inducida por el evento respecto del punto de operación previo.

## Criterios de la Tarea 4.1

Los criterios de aceptación aplicados de forma uniforme fueron:

| Criterio | Límite |
|---|---:|
| Caída máxima de frecuencia | `<= 0.50 Hz` |
| Banda de recuperación | `60 +/- 0.10 Hz` |
| Tiempo máximo de recuperación | `<= 5.0 s` |
| Permanencia continua en banda | `0.50 s` |

La señal previa se calcula con la ventana de `0.10 s` anterior al escalón. La simulación de validación cruzada se extendió hasta `6.5 s`, por lo que cubre el escalón en `0.8 s`, el tiempo máximo de recuperación y la permanencia exigida.

## Resultados de validación cruzada

| Escenario | Estado global | `max_frequency_abs_deviation_hz` [Hz] | `max_frequency_drop_hz` [Hz] | Recuperación [s] | Criterio de frecuencia |
|---|---:|---:|---:|---:|---:|
| Escalón severo `+40 %`, sin BESS | `REVIEW` | `0.072433777958` | `0.125084472162` | `3.504242465e-07` | `PASS` |
| SoH `1.00`, BESS activo | `PASS` | `0.058048662064` | `0.006230868121` | `7.768602121e-06` | `PASS` |
| SoH `0.70`, BESS activo | `PASS` | `0.058048662064` | `0.006230868121` | `7.768602121e-06` | `PASS` |
| SoH nominal `0.668182`, BESS activo | `PASS` | `0.058048662064` | `0.006230868121` | `7.768602121e-06` | `PASS` |

En todos los casos, la desviación absoluta máxima fue inferior a `0.10 Hz`. En consecuencia, los extremos de la traza posterior al escalón permanecieron dentro de la banda de recuperación de la Tarea 4.1. Los tiempos de recuperación próximos a cero son coherentes con esta condición: el algoritmo identifica como inicio de recuperación la primera muestra posterior al evento que puede sostener una permanencia continua de `0.50 s` dentro de la banda. La diferencia residual respecto de cero corresponde al mallado temporal adaptativo del solucionador.

El escenario severo también cumple el límite de caída máxima de `0.50 Hz`. Su estado global permanece en `REVIEW` exclusivamente porque el enlace DC no cumple el criterio adoptado; no existe una falla de aceptación en frecuencia.

## Decisión formal

La Actividad 2.3 se considera cerrada con estado:

```text
activity_2_3_status = PASS
frequency_metric_contract = max_frequency_abs_deviation_hz
all_frequency_metrics_coherent = True
all_frequency_criteria_pass = True
severe_no_bess_global_status = REVIEW
severe_no_bess_review_cause = DC-link criterion
```

El cierre confirma la coherencia de las métricas de frecuencia y la aplicación uniforme de los criterios de la Tarea 4.1. No demuestra robustez global del caso severo, no corrige la falla del enlace DC y no constituye evidencia de soporte del BESS por descarga, dado que en los escenarios de SoH el almacenamiento permaneció en modo de carga o absorción.

## Verificación reproducible

La comprobación se ejecuta sobre los resultados existentes, sin repetir las simulaciones dinámicas:

```text
python src/validation/validate_activity_2_3_frequency_metric.py
```

El reporte local se guarda en:

```text
outputs/validation/activity_2_3_frequency_metric/activity_2_3_frequency_metric_closure.json
```

Este archivo es un artefacto local de validación y no debe incorporarse al control de versiones.
