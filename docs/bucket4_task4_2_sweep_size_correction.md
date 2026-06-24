# Bucket 4 — Corrección del tamaño del barrido de la Tarea 4.2

## Hallazgo

El checklist de la Tarea 4.2 limita el barrido inicial a un máximo de tres
valores por parámetro. La implementación histórica usaba seis valores de `M` y
siete de `D`, para un total de 42 simulaciones.

La campaña histórica no contiene un error numérico. El incumplimiento era
metodológico: se presentaba como barrido inicial una malla mayor que la
autorizada.

## Corrección

El modo predeterminado de `tune_gfm_parameters.py` queda limitado a:

```text
M = [2, 20, 80]
D = [0, 200, 1500]
3 x 3 = 9 simulaciones
```

El ejecutor rechaza más de tres valores únicos de `M` o `D`.

La campaña histórica se conserva mediante:

```text
python src/validation/tune_gfm_parameters.py --extended-grid
```

Ese modo reproduce `6 x 7 = 42` combinaciones y se identifica como exploración
ampliada histórica, no como barrido inicial formal.

## Alcance

La corrección no modifica:

- ecuaciones del VSG;
- criterios de frecuencia o enlace DC;
- escenario de carga del 20 %;
- horizonte de 6.5 s;
- resultados históricos;
- punto de operación seleccionado.

La selección debe revisarse en una subtarea posterior usando la secuencia
formal `3 x 3` más refinamientos acotados.
## Ejecución del barrido formal 3 x 3

El barrido corregido se ejecutó con el escenario base de la Tarea 4.1:

```text
M = [2, 20, 80]
D = [0, 200, 1500]
carga = 3000 -> 3600 W
factor de potencia = 0.95 atrasado
t_step = 0.8 s
t_end = 6.5 s
BESS = no
```

Resumen de ejecución:

```text
runs_total = 9
runs_ok = 9
runs_invalid = 0
candidates_admissible = 6
```

Resultados:

| M | D | Caída máxima de frecuencia [Hz] | Recuperación [s] | Desviación máxima del evento DC [%] | Vdc mínima [V] | Frecuencia | Vdc | Admisible |
|---:|---:|---:|---:|---:|---:|---|---|---|
| 2 | 0 | 0.4345231213 | no recupera | 3.4905894886 | 366.948023 | FAIL | PASS | No |
| 2 | 200 | 0.1868753951 | 0.0319301597 | 3.8318726277 | 364.779568 | PASS | PASS | Sí |
| 2 | 1500 | 0.0428435400 | 0.0000066166 | 3.8350705563 | 364.763307 | PASS | PASS | Sí |
| 20 | 0 | 0.0469544981 | no recupera | 3.7961177013 | 364.997972 | FAIL | PASS | No |
| 20 | 200 | 0.0491463787 | 0.0000007382 | 3.8337620753 | 364.772441 | PASS | PASS | Sí |
| 20 | 1500 | 0.0219426903 | 0.0000010660 | 3.8350705563 | 364.763307 | PASS | PASS | Sí |
| 80 | 0 | 0.0118163473 | no recupera | 3.8251592151 | 364.822145 | FAIL | PASS | No |
| 80 | 200 | 0.0172208857 | 0.0000063002 | 3.8344059571 | 364.771404 | PASS | PASS | Sí |
| 80 | 1500 | 0.0101565401 | 0.0000050604 | 3.8350776972 | 364.763280 | PASS | PASS | Sí |

## Interpretación

Los nueve casos terminaron correctamente y los criterios del enlace DC se
cumplieron en toda la malla. Los tres casos con `D = 0` no cumplieron el
criterio de recuperación de frecuencia, aunque su caída máxima permaneciera
por debajo de `0.50 Hz`. Esto confirma que una caída pequeña no es suficiente:
la recuperación y la permanencia en banda también son obligatorias.

Seis combinaciones fueron plenamente admisibles. El menor valor de
`max_frequency_drop_hz` dentro de la malla inicial formal apareció en:

```text
M = 80
D = 1500
max_frequency_drop_hz = 0.0101565401 Hz
```

Este punto está en el límite superior de ambos ejes. Por tanto, se conserva
únicamente como diagnóstico de dirección para el refinamiento y no se presenta
como óptimo global ni reemplaza automáticamente el punto `(40, 100)`
seleccionado previamente.

La revisión de la secuencia de refinamientos y de la selección final se
realizará en una subtarea posterior. Esta corrección solo demuestra que el
barrido inicial formal cumple el límite de `3 x 3`.

## Artefactos locales

La evidencia numérica se generó en:

```text
outputs/validation/gfm_tuning/sensitivity_runs_initial_3x3.csv
outputs/validation/gfm_tuning/initial_3x3_console.log
```

Estos archivos permanecen bajo `outputs/` y no se incorporan a Git.
