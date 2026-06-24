# Objetivo 2 — Selección del punto de operación del VSG clásico

## 1. Alcance

Este documento formaliza la selección de una pareja `(M, D)` a partir de los barridos ya ejecutados para el VSG clásico. La decisión no modifica la planta, las ecuaciones del controlador, el vector de estados, el solver ni las métricas vigentes. Tampoco activa FOVIC ni afirma haber encontrado un óptimo global.

La denominación metodológicamente válida es:

```text
punto de operación seleccionado dentro del dominio explorado y refinado
```

La pareja seleccionada se empleó en las validaciones cruzadas de la Tarea 4.3. Los resultados finales se documentan en la Sección 11: el caso base con BESS-SLB fue admisible en los tres escenarios de SoH, mientras que el caso severo sin BESS no cumplió el criterio del enlace DC.

## 2. Resultados de entrada

La selección usa exclusivamente los resultados locales producidos por los ejecutores reproducibles del repositorio:

```text
Exploración ampliada histórica:
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

El **mínimo de la exploración ampliada histórica** es la pareja admisible con menor `max_frequency_drop_hz` dentro de las 42 combinaciones de la exploración ampliada histórica. Su función es diagnóstica, puesto que puede coincidir con los límites superiores de la malla y reflejar una preferencia automática por parámetros extremos.

El **mínimo refinado** es la pareja admisible con menor `max_frequency_drop_hz` dentro de la región acotada `M = 20...40` y `D = 50...100`. Este conjunto representa la evidencia de mayor resolución disponible para la selección.

El **punto equilibrado de referencia** es `(M, D) = (30, 75)`. No se adopta por construcción como solución, sino que permite cuantificar el beneficio del mínimo refinado frente a una pareja interior de la región analizada.

El **punto de operación seleccionado** es el mínimo refinado. Si dos filas presentan exactamente la misma caída máxima de frecuencia, el desempate reproducible favorece primero el menor `M` y después el menor `D`. El desempate no constituye una función objetivo adicional; solo elimina ambigüedad computacional.

## 5. Regla de selección

La regla formal es:

```text
1. Rechazar filas que no usen el criterio DC v2.
2. Filtrar las filas plenamente admisibles.
3. Calcular el mínimo de la exploración ampliada histórica solo como diagnóstico de frontera.
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
| Mínimo de exploración ampliada, solo diagnóstico | 80 | 1500 | 0.0101565401 | Resultado del barrido grueso | Resultado del barrido grueso |
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

## 7. Tratamiento del mínimo extremo de la exploración ampliada

La pareja `(80, 1500)` presenta la menor caída de frecuencia de toda la malla gruesa. Sin embargo, ambos parámetros se encuentran en el límite superior del dominio explorado. Seleccionarla automáticamente equivaldría a convertir la minimización de una única métrica en una preferencia no acotada por inercia y amortiguamiento crecientes.

El mínimo de la exploración ampliada se conserva en el informe para mostrar la dirección de la tendencia, pero no reemplaza el resultado del dominio refinado. Esta restricción evita afirmar que la pareja extrema es físicamente superior sin haber evaluado su costo dinámico, su interacción con el almacenamiento de segunda vida o su comportamiento fuera del escenario base.

## 8. Advertencia de frontera del refinamiento

La pareja `(40, 100)` también se ubica en el borde superior de la segunda malla refinada. Este hecho no invalida la selección dentro del dominio estudiado, pero impide presentarla como un mínimo interior o como un óptimo global. El ejecutor registra por ello:

```text
selected_on_refined_boundary = True
global_optimum_claimed = False
cross_validation_pending = False
severe_no_bess_robustness_confirmed = False
bess_soh_base_validation_pass = True
```

La Tarea 4.3 no amplió la malla por defecto. La validación cruzada mostró que la pareja conserva admisibilidad en el escenario base con BESS-SLB, pero no cumple el criterio del enlace DC bajo el escalón severo sin BESS. Este resultado no justifica por sí solo escoger otra pareja `(M, D)`, porque el caso severo también presenta un déficit de potencia activa.

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
cross_validation_pending = False
severe_no_bess_robustness_confirmed = False
bess_soh_base_validation_pass = True
```

## 10. Estado de cierre de esta subtarea

La selección permanece formalizada como `(M*, D*) = (40, 100)` dentro del dominio explorado y refinado. La validación cruzada ya fue ejecutada y no confirma robustez conjunta para todos los escenarios: el punto cumple el caso base con BESS-SLB en los tres SoH, pero no cumple el criterio del enlace DC en el escalón severo sin BESS. Por ello, la pareja no debe presentarse como robusta frente a toda perturbación ni como solución global.

## 11. Resultado de la validación cruzada de la Tarea 4.3

### 11.1 Escalón severo del 40 % sin BESS

El punto `(M, D) = (40, 100)` se evaluó con una carga trifásica balanceada que aumenta de `3000 W` a `4200 W` en `t = 0.8 s`, factor de potencia `0.95` atrasado y horizonte de `6.5 s`.

La integración fue numéricamente válida y la respuesta de frecuencia cumplió los criterios vigentes. Sin embargo, el enlace DC no fue admisible:

| Métrica | Resultado |
|---|---:|
| Estado global | `REVIEW` |
| Caída máxima de frecuencia | `0.1250844722 Hz` |
| Desviación máxima absoluta de frecuencia | `0.0724337780 Hz` |
| Criterio de frecuencia | `PASS` |
| Desviación máxima del evento DC | `17.2627428065 %` |
| `Vdc` mínima posterior | `313.8409278465 V` |
| `Vdc` mínima requerida | `327.5020881285 V` |
| Criterio del enlace DC | `FAIL` |

El resultado no demuestra que otra pareja `(M, D)` resuelva el problema. La carga posterior al escalón, `4200 W`, supera la potencia activa de referencia disponible, aproximadamente `3678.20 W`. Por tanto, la caída del enlace DC puede estar dominada por el déficit de potencia de la fuente y no exclusivamente por la sintonización del GFM.

La conclusión metodológica es:

```text
frequency robust, DC link not admissible in severe no-BESS scenario
```

### 11.2 Escenario base del 20 % con BESS-SLB

La simulación completa de 15 estados se ejecutó con el mismo punto `(M, D) = (40, 100)`, carga de `3000 W` a `3600 W`, escalón en `t = 0.8 s`, factor de potencia `0.95` y horizonte de `6.5 s`.

Se evaluaron tres condiciones de salud:

| Escenario | SoH inicial | Capacidad inicial [Ah] | Límite inicial de corriente [A] | Límite inicial de potencia DC [W] |
|---|---:|---:|---:|---:|
| SoH nuevo | `1.000000` | `66.0` | `66.0` | `22440` |
| SoH 0.70 | `0.700000` | `46.2` | `46.2` | `15708` |
| SoH nominal | `0.668182` | `44.1` | `44.1` | `14994` |

Los tres casos resultaron numéricamente válidos y cumplieron los criterios de frecuencia, enlace DC y límites implementados del BESS:

| Métrica | Resultado común |
|---|---:|
| Estado global | `PASS` |
| Caída máxima de frecuencia | `0.0062308681 Hz` |
| Desviación máxima del evento DC | `0.9021555526 %` |
| `Vdc` mínima posterior | `341.6935084071 V` |
| Corriente máxima absoluta del BESS | `2.4021059173 A` |
| Potencia máxima absoluta del BESS | `828.2562375425 W` |
| Energía intercambiada posterior al escalón | `0.4594847687 Wh` |

La variación de SoC aumentó al disminuir la capacidad disponible:

| Escenario | Variación de SoC |
|---|---:|
| SoH 1.00 | `2.03742e-05` |
| SoH 0.70 | `2.91060e-05` |
| SoH nominal | `3.04920e-05` |

La respuesta de frecuencia y del enlace DC fue idéntica entre los tres escenarios porque la corriente y la potencia demandadas permanecieron muy por debajo de los límites dependientes del SoH. En consecuencia, esta prueba valida la operación dentro de los límites implementados, pero no fuerza una saturación que permita diferenciar dinámicamente los tres niveles de degradación.

### 11.3 Sentido del intercambio del BESS

En los tres escenarios, la corriente y la potencia del BESS permanecieron negativas después del escalón. De acuerdo con la convención del repositorio:

```text
i_bess > 0  -> descarga
i_bess < 0  -> carga o absorción
```

El diagnóstico reproducible fue:

```text
bess_exchange_mode = charge_only
bess_discharge_observed = False
bess_charge_observed = True
```

Por tanto, el `PASS` no constituye evidencia de soporte inercial por descarga. La conclusión válida es que el GFM opera de forma admisible con el BESS-SLB conectado y con límites dependientes del SoH, mientras el almacenamiento permanece en modo de carga o absorción durante el evento.

### 11.4 Conclusión de la validación cruzada

El punto `(40, 100)` conserva admisibilidad en el escenario base con BESS-SLB para los tres SoH considerados, pero no confirma robustez conjunta bajo el escalón severo sin almacenamiento. La selección continúa siendo válida únicamente como punto de operación escogido dentro del dominio explorado y refinado.

No se afirma:

- optimalidad global;
- robustez frente a cualquier perturbación;
- soporte inercial por descarga del BESS;
- que una nueva sintonización de `M` y `D` elimine el déficit de potencia del caso severo.
