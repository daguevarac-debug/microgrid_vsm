# Tarea 5.3 — Validación y cierre de la regulación del enlace DC

## Alcance

Esta tarea valida la arquitectura cerrada en la Tarea 5.2 sin modificar nuevamente el controlador. Se mantienen:

- `Kp = 170 W/V`;
- `Ki = 10 W/(V*s)`;
- `M = 80`;
- `D = 1500`;
- BESS explícitamente habilitado;
- límites de corriente, potencia, SoC y SoH;
- saturación y anti-windup.

## Escenarios obligatorios

Se evalúan exactamente dos escenarios:

1. Escenario base: escalón de carga del 20 %.
2. Escenario severo: escalón de carga del 40 %.

En ambos casos la carga inicial es 3000 W, el escalón ocurre en `t = 0.8 s`, el horizonte es 6.5 s y se usa la arquitectura GFM+BESS+PI de 16 estados.

## Criterios de aceptación

Cada escenario obtiene `PASS` únicamente si se cumplen simultáneamente:

- integración numérica exitosa;
- estados y señales finitos;
- criterios existentes del enlace DC;
- criterios existentes de frecuencia;
- límites de corriente, potencia, SoC y SoH;
- BESS activo durante la simulación.

La tarea completa obtiene `PASS` solo si los dos escenarios obligatorios pasan.

## Confirmación de frecuencia — Actividad 2.3

La frecuencia de cada escenario se vuelve a comprobar con la definición canónica de la Actividad 2.3:

- punto seleccionado `(M, D) = (80, 1500)`;
- caída máxima respecto al promedio preescalón;
- desviación absoluta máxima respecto a 60 Hz;
- recuperación a `60 ± 0.10 Hz` en máximo 5.0 s;
- permanencia continua de 0.50 s;
- coherencia entre las métricas reportadas y sus banderas de aceptación.

No se acepta un alias alternativo de la métrica canónica `max_frequency_abs_deviation_hz`.

## Confirmación de Vdc — Tarea 4.1

Se comprueban explícitamente:

- desviación máxima del evento menor o igual al 5 % respecto al punto preescalón;
- tensión mínima posterior al escalón mayor o igual a la tensión físicamente requerida;
- recuperación dentro de la banda del evento en máximo 5.0 s;
- permanencia continua dentro de banda durante 0.50 s.

Para el tiempo de recuperación de `Vdc`, se aplica el horizonte común de 5.0 s y la permanencia de 0.50 s definidos en la Tarea 4.1 sobre la banda vigente de aceptación del evento de ±5 %. Esta interpretación se registra explícitamente y no modifica los criterios ni el controlador.

## Descarga efectiva, límites y SoH

El escenario severo del 40 % se repite con la arquitectura corregida para:

- `SoH = 1.00`;
- `SoH = 0.70`;
- SoH nominal del modelo.

Cada caso debe presentar descarga positiva del BESS después del escalón, potencia media post-escalón positiva y cumplimiento simultáneo de los límites dinámicos de corriente y potencia, además de los rangos de SoC y SoH y los criterios de frecuencia y `Vdc`.

La comparación final enfrenta el caso anterior GFM sin soporte BESS contra el caso corregido PI+BESS con SoH nominal, manteniendo igual escalón, horizonte, `M` y `D`. La figura comparte el eje temporal e incluye `Vdc`, frecuencia y potencia del BESS.

Los resultados numéricos, criterios, limitaciones y archivos generados se consolidan en:

`docs/dc_link_regulation_validation.md`

## Ejecución reproducible

Validación de escenarios:

`src/validation/validate_dc_link_pi_scenarios.py`

Cierre de frecuencia y `Vdc`:

`src/validation/validate_task_5_3_frequency_vdc_closure.py`

Descarga, límites, SoH y comparación:

`src/validation/validate_dc_link_bess_soh_support.py`

Pruebas:

- `src/validation/test_validate_dc_link_pi_scenarios.py`;
- `src/validation/test_validate_task_5_3_frequency_vdc_closure.py`;
- `src/validation/test_validate_dc_link_bess_soh_support.py`.

Resultados:

- `outputs/validation/dc_link_regulation/gfm_m80_d1500_bess_pi_base_20pct.json`;
- `outputs/validation/dc_link_regulation/gfm_m80_d1500_bess_pi_severe_40pct.json`;
- `outputs/validation/dc_link_regulation/task_5_3_dc_link_pi_validation_summary.json`;
- `outputs/validation/dc_link_regulation/task_5_3_frequency_vdc_closure.json`;
- `outputs/validation/dc_link_regulation/task_5_3_bess_soh_support_summary.json`;
- `outputs/validation/dc_link_regulation/task_5_3_bess_soh_support_summary.csv`;
- `outputs/validation/dc_link_regulation/task_5_3_no_support_vs_bess_pi.csv`;
- `outputs/validation/dc_link_regulation/task_5_3_no_support_vs_bess_pi.png`.
