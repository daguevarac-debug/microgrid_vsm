# Objetivo 2 — Criterios y protocolo de sintonización

## Estado del documento

Este documento consolida las decisiones cerradas antes de ejecutar cualquier barrido de parámetros del controlador grid-forming/VSG.

```text
Barrido M-D ejecutado antes de este documento: NO
FOVIC integrado en el controlador principal: NO
Estrategia inicial autorizada: VSG clásico
```

Los valores aquí registrados son criterios de diseño y comparación para esta tesis. No se presentan como límites normativos universales.

## 1. Controlador que se sintonizará primero

La primera sintonización corresponde a la dinámica clásica reducida implementada en `GridFormingFrequencyDynamics` y usada por `GFMController`:

```text
dtheta/dt = omega

domega/dt = (
    P_ref_eff
    - P_e
    - D*(omega - omega_ref)
) / M
```

con:

```text
M = inertia_m
D = damping_d
P_e = potencia activa instantánea estimada en el PCC
omega_ref = 2*pi*60 rad/s
```

FOVIC se mantiene como extensión comparativa posterior. El parámetro fraccionario no participa en el primer barrido.

## 2. Escenario base de sintonización

El barrido inicial de `M` y `D` se realizará bajo el escenario moderado ya validado:

| Variable | Valor |
|---|---:|
| Modo de operación | Microrred AC aislada |
| Tipo de carga | Trifásica balanceada R-L |
| Potencia activa antes del escalón | `3000 W` |
| Potencia activa después del escalón | `3600 W` |
| Incremento | `20 %` |
| Instante del escalón | `0.8 s` |
| Factor de potencia | `0.95` atrasado |
| Potencia reactiva antes del escalón | `986.052316 var` |
| Potencia reactiva después del escalón | `1183.262779 var` |

Perfil de carga:

```text
p_load(t) = 3000 W,  t < 0.8 s
p_load(t) = 3600 W,  t >= 0.8 s
```

### Caso principal

La sintonización inicial se ejecutará **sin BESS** para aislar el efecto de `M` y `D` sobre la dinámica del GFM/VSG.

### Variante comparativa

Después de identificar candidatos admisibles, se repetirá el mismo escenario con `MicrogridWithBESS`. En esa etapa se evaluará la interacción con la batería de segunda vida y no solo el desempeño de frecuencia y enlace DC.

### Caso severo posterior

El escalón del `40 %`, de `3000 W` a `4200 W`, se reserva para comprobar la respuesta de los candidatos finales. No se usará para construir la primera malla ni para escoger los parámetros iniciales.

## 3. Horizonte temporal del barrido

El tiempo máximo de recuperación aceptado es `5.0 s` después del escalón y la señal debe permanecer dentro de banda durante `0.50 s`.

El horizonte mínimo matemático requerido es:

```text
t_end_min = t_step + t_recovery_max + dwell
          = 0.8 + 5.0 + 0.5
          = 6.3 s
```

Para dejar margen numérico, las ejecuciones de sintonización usarán:

```text
t_start = 0.0 s
t_step  = 0.8 s
t_end   = 6.5 s
```

Este horizonte extendido se aplicará únicamente al flujo de sintonización. No autoriza cambiar indiscriminadamente `SIM_T_END_S_DEFAULT = 2.0 s` para las validaciones baseline ya existentes.

## 4. Límites de admisibilidad de los parámetros

### Inercia virtual

```text
M > 0
```

El repositorio ya rechaza `M <= 0`.

### Amortiguamiento

```text
D >= 0
```

El valor `D = 0` es matemáticamente admisible y se conserva como referencia sin amortiguamiento. Esto no significa que cumpla las métricas de aceptación.

### Orden fraccionario futuro

En el prototipo existente:

```text
alpha = mu
0 < alpha < 1
```

Los extremos `0` y `1` no son admisibles. Esta condición queda registrada para la futura comparación FOVIC, no para el primer barrido clásico.

## 5. Malla gruesa inicial

### Valores de `M`

```text
M = [2, 5, 10, 20, 40, 80]
```

### Valores de `D`

```text
D = [0, 50, 100, 200, 500, 1000, 1500]
```

### Número de simulaciones clásicas

```text
6 valores de M x 7 valores de D = 42 combinaciones
```

### Malla fraccionaria futura

Cuando FOVIC esté refactorizado, integrado y validado:

```text
alpha = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
```

La malla de `alpha` no se combinará todavía con las 42 parejas `M-D`.

## 6. Preparación de las señales

Para cada simulación se deberán obtener, como mínimo:

```text
t
frequency_hz
Vdc
```

La frecuencia del GFM se calculará mediante:

```text
frequency_hz = omega / (2*pi)
```

Las trazas entregadas a las métricas deberán cumplir:

- una dimensión;
- igual número de muestras;
- al menos dos muestras;
- valores finitos;
- tiempo estrictamente creciente;
- presencia de muestras antes y después de `t_step`.

## 7. Criterios obligatorios de frecuencia

Las métricas se calcularán con `frequency_performance_metrics()`.

### Referencia

```text
f_nominal = 60.0 Hz
```

### Ventana previa

La frecuencia previa al escalón será el promedio de los últimos:

```text
0.10 s antes de t_step
```

Si esa ventana no contiene muestras, se empleará la última muestra disponible antes del escalón.

### Caída máxima

```text
max_frequency_drop_hz <= 0.50 Hz
```

La caída se mide como:

```text
f_pre_step_mean - min(f_post_step)
```

### Recuperación

La frecuencia deberá entrar en:

```text
60.0 +/- 0.10 Hz
```

en un tiempo máximo de:

```text
5.0 s después del escalón
```

Además, deberá permanecer continuamente dentro de esa banda durante:

```text
0.50 s
```

No se considerará recuperada una señal que solo cruce momentáneamente la banda.

### Aprobación de frecuencia

```text
frequency_criteria_pass =
    frequency_drop_pass
    and frequency_recovery_pass
```

## 8. Criterios obligatorios del enlace DC

Las métricas se calcularán con `dc_link_performance_metrics()`.

### Referencia

```text
Vdc_ref = 340.0 V
```

### Sobreoscilación positiva

```text
vdc_overshoot_pct <= 5.0 %
```

Equivalente a un máximo de referencia de:

```text
340*(1 + 0.05) = 357.0 V
```

La métrica se calcula respecto de `Vdc_ref`, no respecto de la tensión previa al escalón.

### Tensión mínima físicamente viable

Para `110 V RMS` fase-neutro y un índice máximo de modulación de `0.95`:

```text
Vdc_min_required = 2*sqrt(2)*110/0.95
                 = 327.5021 V aproximadamente
```

Criterio:

```text
vdc_min_post_step >= Vdc_min_required
```

### Aprobación del enlace DC

```text
vdc_criteria_pass =
    vdc_overshoot_pass
    and vdc_minimum_voltage_pass
```

## 9. Validez numérica obligatoria

Una combinación se descartará antes de evaluar su desempeño si ocurre cualquiera de estas condiciones:

- `solve_ivp` no termina correctamente;
- el vector de estados contiene `NaN` o `Inf`;
- las señales de frecuencia o `Vdc` no son finitas;
- el tiempo no es estrictamente creciente;
- no existen muestras suficientes antes o después del escalón;
- se produce una excepción durante la construcción del controlador o el cálculo de las métricas.

Una falla numérica no se interpretará como un valor grande de la métrica: se registrará explícitamente como combinación inválida.

## 10. Regla de aceptación de una pareja `M-D`

Para el barrido inicial sin BESS, una combinación será **admisible** únicamente cuando cumpla simultáneamente:

```text
solver_success
and states_finite
and frequency_criteria_pass
and vdc_criteria_pass
```

En forma expandida:

```text
max_frequency_drop_hz <= 0.50 Hz
frequency_recovery_time_s <= 5.0 s
permanencia en banda >= 0.50 s
vdc_overshoot_pct <= 5.0 %
vdc_min_post_step >= 327.5021 V aproximadamente
```

Cumplir estos límites no convierte automáticamente una combinación en la solución final. El barrido grueso identificará el conjunto admisible y permitirá definir un refinamiento local sin escoger parámetros a simple vista.

No se adoptará en esta etapa una suma ponderada arbitraria que mezcle métricas con unidades distintas.

## 11. Evaluación posterior con BESS-SLB

Cuando una combinación se repita con BESS, cumplir frecuencia y enlace DC será necesario pero no suficiente.

Se registrarán mediante `bess_stress_metrics()`:

```text
i_bess_peak_abs_a
i_bess_rms_a
i_bess_max_discharge_a
i_bess_max_charge_a
p_bess_peak_abs_w
p_bess_max_discharge_w
p_bess_max_charge_w
bess_energy_throughput_wh
soc_min
soc_max
soc_swing
```

También deberán respetarse los límites implementados de:

- SoC;
- SoH;
- corriente disponible;
- potencia disponible;
- tensión terminal positiva.

No se añadirán umbrales electroquímicos nuevos sin soporte del modelo de batería, la caracterización de los módulos o las restricciones verificadas del BMS.

## 12. Información mínima que deberá guardar el barrido

Cada fila de resultados deberá identificar, como mínimo:

```text
M
D
scenario
solver_success
states_finite
max_frequency_drop_hz
frequency_recovery_time_s
frequency_drop_pass
frequency_recovery_pass
frequency_criteria_pass
vdc_max_post_step_v
vdc_min_post_step_v
vdc_overshoot_pct
vdc_min_margin_v
vdc_overshoot_pass
vdc_minimum_voltage_pass
vdc_criteria_pass
candidate_admissible
error_message
```

La variante con BESS añadirá las métricas de esfuerzo listadas en la sección anterior.

## 13. Secuencia autorizada

```text
1. Consolidar y fusionar este documento.
2. Implementar un ejecutor reproducible para una sola pareja M-D.
3. Verificar el ejecutor con uno o pocos casos conocidos.
4. Ejecutar las 42 combinaciones del barrido grueso.
5. Identificar el conjunto admisible.
6. Definir y ejecutar un refinamiento local.
7. Repetir candidatos con BESS-SLB.
8. Verificar candidatos finales con el escalón del 40 %.
9. Considerar FOVIC únicamente después de validar el VSG clásico.
```

No se ejecutará el barrido completo antes de que este documento se encuentre fusionado en `main`.

## 14. Trazabilidad

Este documento consolida las decisiones desarrolladas en:

- `docs/bucket4_task4_1_tuning_criteria.md`;
- `docs/bucket4_task4_2_base_tuning_scenario.md`;
- `docs/bucket4_task4_3_parameter_bounds.md`;
- `docs/obj2_scope.md`;
- `docs/fovic_reuse_evaluation.md`;
- `src/config.py`;
- `src/tuning_metrics.py`.

## 15. Alcance del cambio

La creación de este documento no modifica:

- ecuaciones del controlador;
- valores predeterminados de `GFMController`;
- parámetros eléctricos;
- vector de estados;
- integración FOVIC;
- comportamiento de las simulaciones existentes.
