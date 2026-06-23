# Objetivo 2 — Selección del punto de operación del VSG clásico

## 1. Alcance

Este documento formaliza la selección de una pareja `(M, D)` a partir de los barridos ya ejecutados para el VSG clásico. La decisión no modifica la planta, las ecuaciones del controlador, el vector de estados, el solver ni las métricas vigentes. Tampoco activa FOVIC ni afirma haber encontrado un óptimo global.

La denominación metodológicamente válida es:

```text
punto de operación seleccionado dentro del dominio explorado y refinado
```

La pareja seleccionada se empleará en las validaciones cruzadas posteriores de la Tarea 4.3. En consecuencia, su adopción permanece condicionada a las pruebas con perturbación severa y BESS-SLB.

## 2. Resultados de entrada

La selección usa exclusivamente los resultados locales producidos por los ejecutores reproducibles del repositorio:

```text
Barrido grueso:
outputs/validation/gfm_tuning/sensitivity_runs_v2_event_relative.csv

Segundo refinamiento:
outputs/validation/gfm_tuning/refinement_iter2_m20-40_d50-100.csv
```

Los dos archivos deben declarar:

```text
criteria_version = obj2_vdc_event_relative_v2
vdc_acceptance_basis = max_abs_event_deviation_from_pre_step
```

Esta verificación impide combinar resultados calculados con la regla anterior del enlace DC y resultados evaluados con el criterio vigente.

## 3. Conjunto admisible

Una fila entra al proceso de selección únicamente cuando cumple simultáneamente:

```text
solver_success
and states_finite
and frequency_criteria_pass
and vdc_criteria_pass
and candidate_admissible
```

Por tanto, la selección no compensa una violación de frecuencia con una mejor respuesta de tensión, ni admite una combinación numéricamente inválida. Tampoco emplea una suma ponderada entre magnitudes de unidades diferentes.

## 4. Definiciones comparativas

El **mínimo grueso** es la pareja admisible con menor `max_frequency_drop_hz` dentro de las 42 combinaciones iniciales. Su función es diagnóstica, puesto que puede coincidir con los límites superiores de la malla y reflejar una preferencia automática por parámetros extremos.

El **mínimo refinado** es la pareja admisible con menor `max_frequency_drop_hz` dentro de la región acotada `M = 20...40` y `D = 50...100`. Este conjunto representa la evidencia de mayor resolución disponible para la selección.

El **punto equilibrado de referencia** es `(M, D) = (30, 75)`. No se adopta por construcción como solución, sino que permite cuantificar el beneficio del mínimo refinado frente a una pareja interior de la región analizada.

El **punto de operación seleccionado** es el mínimo refinado. Si dos filas presentan exactamente la misma caída máxima de frecuencia, el desempate reproducible favorece primero el menor `M` y después el menor `D`. El desempate no constituye una función objetivo adicional; solo elimina ambigüedad computacional.

## 5. Regla de selección

La regla formal es:

```text
1. Rechazar filas que no usen el criterio DC v2.
2. Filtrar las filas plenamente admisibles.
3. Calcular el mínimo grueso solo como diagnóstico de frontera.
4. Restringir la decisión al conjunto refinado admisible.
5. Seleccionar argmin(max_frequency_drop_hz) en el conjunto refinado.
6. Resolver empates exactos mediante menor M y luego menor D.
7. Registrar expresamente que no se afirma optimalidad global.
8. Mantener la selección condicionada a la validación cruzada posterior.
```

Esta regla hace que la trazabilidad de la decisión dependa de datos reproducibles y no de inspección visual de las curvas.

## 6. Resultado con los datos disponibles

El segundo refinamiento contiene nueve combinaciones y las nueve son admisibles. Los puntos relevantes son:

| Papel metodológico | M | D | Caída máxima de frecuencia [Hz] | Desviación máxima del evento DC [%] | Vdc mínima posterior [V] |
|---|---:|---:|---:|---:|---:|
| Mínimo grueso, solo diagnóstico | 80 | 1500 | 0.0101565401 | Resultado del barrido grueso | Resultado del barrido grueso |
| Referencia equilibrada interior | 30 | 75 | 0.0459252153 | 3.8329316 | 364.787345 |
| Referencia con igual M y menor D | 40 | 50 | 0.0353277149 | Resultado del refinamiento | Resultado del refinamiento |
| Mínimo refinado y punto seleccionado | 40 | 100 | 0.0344426647 | 3.8334871 | 364.781099 |

La pareja resultante es:

```text
M* = 40
D* = 100
```

Su caída máxima de frecuencia es `0.0114825506 Hz` menor que la del punto equilibrado `(30, 75)`, lo cual corresponde a una reducción relativa aproximada de `25.0027 %`. Frente a `(40, 50)`, el incremento de amortiguamiento hasta `D = 100` reduce la caída en apenas `0.0008850502 Hz`, equivalente a `2.5053 %`. Por ello, los datos muestran que el efecto adicional de `D` dentro del extremo superior de `M` es pequeño y no estrictamente monótono, puesto que `(40, 75)` presenta una caída ligeramente mayor que `(40, 50)`.

La decisión no se fundamenta en atribuir un beneficio amplio a `D = 100`. Se fundamenta en que `(40, 100)` es el mínimo reproducible dentro del conjunto refinado admisible, mientras la respuesta del enlace DC permanece prácticamente invariante entre los candidatos considerados.

## 7. Tratamiento del mínimo grueso extremo

La pareja `(80, 1500)` presenta la menor caída de frecuencia de toda la malla gruesa. Sin embargo, ambos parámetros se encuentran en el límite superior del dominio explorado. Seleccionarla automáticamente equivaldría a convertir la minimización de una única métrica en una preferencia no acotada por inercia y amortiguamiento crecientes.

El mínimo grueso se conserva en el informe para mostrar la dirección de la tendencia, pero no reemplaza el resultado del dominio refinado. Esta restricción evita afirmar que la pareja extrema es físicamente superior sin haber evaluado su costo dinámico, su interacción con el almacenamiento de segunda vida o su comportamiento fuera del escenario base.

## 8. Advertencia de frontera del refinamiento

La pareja `(40, 100)` también se ubica en el borde superior de la segunda malla refinada. Este hecho no invalida la selección dentro del dominio estudiado, pero impide presentarla como un mínimo interior o como un óptimo global. El ejecutor registra por ello:

```text
selected_on_refined_boundary = True
global_optimum_claimed = False
cross_validation_pending = True
```

La Tarea 4.3 no continuará ampliando la malla por defecto. La evidencia posterior deberá determinar si la pareja conserva su conveniencia al introducir la perturbación del `40 %` y los escenarios BESS-SLB. Una falla en esas comprobaciones obligará a reconsiderar el punto equilibrado u otra pareja admisible ya evaluada.

## 9. Implementación reproducible

El archivo `src/validation/select_gfm_operating_point.py` carga los dos CSV, valida la versión de los criterios, reproduce la regla anterior y genera un resumen local en JSON. El archivo de salida se guarda bajo `outputs/` y no debe incorporarse a Git.

Ejecución prevista:

```text
python src/validation/select_gfm_operating_point.py
```

El resultado esperado con los CSV indicados es:

```text
selected_operating_point = M=40, D=100
selection_scope = selected_within_explored_and_refined_domain
global_optimum_claimed = False
cross_validation_pending = True
```

## 10. Estado de cierre de esta subtarea

La selección queda formalizada como `(M*, D*) = (40, 100)` para iniciar la validación cruzada. Este cierre no valida todavía el escalón severo, no incorpora la batería de segunda vida y no constituye el cierre completo de la Tarea 4.3.
