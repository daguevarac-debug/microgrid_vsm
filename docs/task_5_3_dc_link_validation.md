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

## Ejecución reproducible

Script:

`src/validation/validate_dc_link_pi_scenarios.py`

Pruebas:

`src/validation/test_validate_dc_link_pi_scenarios.py`

Resultados:

- `outputs/validation/dc_link_regulation/gfm_m80_d1500_bess_pi_base_20pct.json`;
- `outputs/validation/dc_link_regulation/gfm_m80_d1500_bess_pi_severe_40pct.json`;
- `outputs/validation/dc_link_regulation/task_5_3_dc_link_pi_validation_summary.json`.
