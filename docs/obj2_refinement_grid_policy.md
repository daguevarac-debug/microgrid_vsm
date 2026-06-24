# Objetivo 2 — Política de refinamiento acotado del barrido

## 1. Propósito

El barrido inicial formal y cada refinamiento se limitan a:

```text
máximo 3 valores de M
máximo 3 valores de D
máximo 3 x 3 = 9 simulaciones por ejecución
```

La campaña histórica de `6 x 7 = 42` combinaciones se conserva como evidencia de
sensibilidad, pero no forma parte de la cadena formal de selección.

## 2. Barrido inicial formal

La malla inicial ejecutada fue:

```text
M = [2, 20, 80]
D = [0, 200, 1500]
```

Los nueve casos terminaron correctamente y seis fueron admisibles. El menor
valor de `max_frequency_drop_hz` apareció en la esquina superior:

```text
M = 80
D = 1500
max_frequency_drop_hz = 0.0101565401 Hz
```

## 3. Primer refinamiento formal

Para estudiar con mayor resolución la región indicada por el barrido inicial se
redujeron ambos intervalos y se evaluaron extremos y punto medio:

```text
M = [20, 50, 80]
D = [200, 850, 1500]
```

Este refinamiento:

- contiene nueve combinaciones;
- permanece dentro del dominio inicial;
- reduce el intervalo de `M` de `[2, 80]` a `[20, 80]`;
- reduce el intervalo de `D` de `[0, 1500]` a `[200, 1500]`;
- usa el mismo escenario, solver, métricas y criterio DC v2.

Los nueve candidatos fueron admisibles. El mínimo volvió a aparecer en:

```text
M = 80
D = 1500
max_frequency_drop_hz = 0.0101565401 Hz
```

## 4. Tratamiento de refinamientos históricos

Las mallas:

```text
M = [10, 20, 40], D = [50, 100, 200]
M = [20, 30, 40], D = [50, 75, 100]
```

fueron ejecutadas antes de corregir el barrido inicial. Se conservan como
estudios históricos de una región práctica identificada mediante la campaña de
42 casos, pero no se presentan como refinamientos derivados del barrido inicial
formal.

## 5. Reglas de validación

El selector formal debe:

- rechazar más de tres valores únicos por parámetro;
- rechazar más de nueve combinaciones por etapa;
- exigir una malla cartesiana completa;
- mantener `M > 0` y `D >= 0`;
- exigir que cada refinamiento permanezca dentro del intervalo anterior;
- exigir que al menos uno de los dos intervalos se reduzca;
- reutilizar el escenario `load_step_20_no_bess`;
- reutilizar `obj2_vdc_event_relative_v2`;
- seleccionar únicamente dentro de la última malla formal.

## 6. Alcance de la conclusión

El resultado en `(80, 1500)` se encuentra en la frontera superior de la región
estudiada. Por tanto:

```text
seleccionado dentro del dominio formal = sí
óptimo global demostrado = no
```

La función objetivo vigente minimiza únicamente la caída máxima de frecuencia
entre candidatos plenamente admisibles. Como no incluye una penalización por
inercia virtual, amortiguamiento, esfuerzo de control o costo físico, la
preferencia por la esquina superior debe documentarse como una limitación del
criterio de selección.
