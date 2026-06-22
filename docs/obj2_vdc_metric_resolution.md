# Objetivo 2 — Resolución de la métrica del enlace DC

## 1. Problema detectado

El primer barrido grueso de `42` combinaciones `(M, D)` terminó con:

```text
runs_total = 42
runs_ok = 42
runs_invalid = 0
frequency_criteria_pass = 34
vdc_minimum_voltage_pass = 42
vdc_overshoot_pass respecto a 340 V = 0
candidate_admissible = 0
```

En las `42` ejecuciones se obtuvo:

```text
Vdc_max_post_step = 379.3101 ... 380.2442 V
Vdc_min_post_step = 364.7633 ... 366.9480 V
overshoot respecto a 340 V = 11.5618 ... 11.8365 %
```

El caso sin BESS ya opera cerca de `379.31 V` antes del escalón. Por tanto, comparar el máximo posterior directamente contra `Vdc_ref = 340 V` mezcla dos fenómenos distintos:

1. la diferencia estructural entre el punto de operación natural del modelo y la referencia nominal de inicialización;
2. la excursión dinámica causada por el escalón de carga.

La primera diferencia no es corregible mediante el barrido de `M` y `D`, porque el `GFMController` actual no contiene un lazo dedicado de regulación del enlace DC. Mantenerla como condición de descarte haría que todas las parejas fallaran por una variable que el barrido no puede controlar.

## 2. Decisión metodológica

Se separan explícitamente dos evaluaciones del enlace DC.

### 2.1 Diagnóstico del punto de operación respecto a 340 V

La referencia nominal se conserva:

```text
Vdc_ref = 340.0 V
```

Se seguirá registrando la diferencia entre el punto de operación previo y esta referencia:

```text
vdc_reference_deviation_v = Vdc_pre - Vdc_ref
vdc_reference_deviation_pct = 100*(Vdc_pre - Vdc_ref)/Vdc_ref
```

También se conservarán como diagnósticos de compatibilidad las métricas existentes calculadas respecto a `340 V`:

```text
vdc_overshoot_v
vdc_overshoot_pct
vdc_undershoot_v
vdc_undershoot_pct
vdc_overshoot_pass
```

Estas magnitudes describen la diferencia absoluta frente a la referencia nominal, pero no se usarán para aceptar o rechazar una pareja `(M, D)` mientras el modelo no disponga de un lazo explícito que regule `Vdc` hacia `340 V`.

### 2.2 Excursión dinámica causada por el evento

El valor previo al escalón se calculará como el promedio de los últimos `0.10 s` anteriores a `t_step`, usando la misma regla ya aplicada a la frecuencia:

```text
Vdc_pre = mean(Vdc(t)),  t en [t_step - 0.10 s, t_step)
```

A partir de este punto de operación se registrarán:

```text
vdc_event_max_rise_v = max(max(Vdc_post) - Vdc_pre, 0)
vdc_event_max_drop_v = max(Vdc_pre - min(Vdc_post), 0)

vdc_event_max_abs_deviation_v =
    max(vdc_event_max_rise_v, vdc_event_max_drop_v)

vdc_event_max_abs_deviation_pct =
    100*vdc_event_max_abs_deviation_v/Vdc_pre
```

La excursión dinámica máxima admisible será:

```text
vdc_event_max_abs_deviation_pct <= 5.0 %
```

El límite del `5 %` se aplica ahora a la variación inducida por la perturbación y no a la diferencia estructural entre el punto de operación y la referencia de inicialización.

## 3. Protección absoluta de tensión

Se conserva sin cambios la condición física mínima:

```text
Vdc_min_required = 2*sqrt(2)*110/0.95
                 = 327.5021 V aproximadamente
```

Criterio:

```text
vdc_min_post_step_v >= Vdc_min_required
```

Esta condición evita aceptar una respuesta cuya variación relativa sea pequeña pero cuya tensión resulte insuficiente para sintetizar la tensión AC nominal.

## 4. Nueva regla del enlace DC para sintonización

La aprobación del enlace DC para el barrido de `M` y `D` será:

```text
vdc_criteria_pass =
    vdc_event_deviation_pass
    and vdc_minimum_voltage_pass
```

con:

```text
vdc_event_deviation_pass =
    vdc_event_max_abs_deviation_pct <= 5.0 %
```

La aprobación total de una pareja permanece:

```text
candidate_admissible =
    solver_success
    and states_finite
    and frequency_criteria_pass
    and vdc_criteria_pass
```

## 5. Compatibilidad y trazabilidad

La implementación deberá:

- conservar las claves existentes calculadas respecto a `340 V` para no perder comparabilidad con el primer CSV;
- añadir nombres explícitos para las métricas relativas al evento;
- registrar una versión del criterio en cada fila del barrido;
- no modificar las ecuaciones del controlador, la planta, el vector de estados ni el solver;
- archivar el primer CSV como resultado histórico calculado con el criterio anterior;
- repetir las `42` simulaciones después de validar la implementación corregida.

Versión adoptada para el nuevo barrido:

```text
criteria_version = obj2_vdc_event_relative_v2
vdc_acceptance_basis = max_abs_event_deviation_from_pre_step
```

## 6. Alcance de la decisión

Esta corrección no afirma que el punto de operación de aproximadamente `379 V` sea el punto final deseado para la tesis. La diferencia frente a `340 V` queda registrada como una limitación arquitectónica pendiente de revisar cuando se implemente o seleccione una estrategia explícita de regulación del enlace DC.

La decisión únicamente evita atribuir a `M` y `D` una falla que esos parámetros no pueden corregir en la arquitectura actual.
