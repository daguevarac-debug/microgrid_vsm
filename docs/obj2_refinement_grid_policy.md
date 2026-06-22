# Objetivo 2 — Política de refinamiento acotado del barrido

## 1. Motivación

El barrido grueso de `42` combinaciones `(M, D)` fue útil para identificar la región admisible, pero cada simulación tarda aproximadamente un minuto. Repetir mallas extensas durante el refinamiento elevaría innecesariamente el tiempo de ejecución.

La región prometedora identificada es:

```text
M = 10 ... 40
D = 50 ... 200
```

## 2. Límite por iteración

A partir de esta etapa, cada ejecución de refinamiento queda limitada a:

```text
máximo 3 valores de M
máximo 3 valores de D
máximo 3 x 3 = 9 simulaciones por iteración
```

El barrido grueso histórico de `42` casos se conserva como resultado de exploración inicial. Esta política aplica a las iteraciones posteriores de refinamiento y no invalida ese resultado.

## 3. Primera malla de refinamiento

La primera iteración usará:

```text
M = [10, 20, 40]
D = [50, 100, 200]
```

Esto produce nueve combinaciones dentro de la región ya identificada como admisible.

## 4. Mayor resolución mediante bisección

Cuando una iteración requiera mayor resolución, no se ampliará el número de puntos por eje. En su lugar se reducirá el intervalo prometedor y se evaluarán sus extremos y punto medio:

```text
x_mid = (x_low + x_high)/2
valores = [x_low, x_mid, x_high]
```

Ejemplo para inercia:

```text
intervalo inicial: [10, 40]
tripleta: [10, 25, 40]

si el subrango prometedor es [10, 25]:
nueva tripleta: [10, 17.5, 25]
```

El mismo procedimiento se aplica de forma independiente a `D`.

## 5. Reglas de validación

El ejecutor de refinamiento deberá:

- rechazar más de tres valores únicos de `M`;
- rechazar más de tres valores únicos de `D`;
- mantener `M > 0`;
- mantener `D >= 0`;
- rechazar intervalos con límite superior menor o igual al inferior;
- generar exactamente extremos y punto medio cuando se use un rango;
- permitir menos de tres valores cuando la comprobación lo requiera;
- reutilizar el mismo escenario, solver, métricas y criterio DC v2 del barrido validado.

## 6. Alcance

Esta política no modifica:

- las ecuaciones del VSG;
- las métricas de aceptación;
- el escenario de carga;
- el horizonte de `6.5 s`;
- el barrido grueso histórico;
- la futura evaluación con BESS-SLB.

Su único propósito es controlar el costo computacional del refinamiento y mantener cada iteración en un máximo de nueve simulaciones.
