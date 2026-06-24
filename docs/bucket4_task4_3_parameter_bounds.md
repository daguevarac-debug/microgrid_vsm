# Bucket 4 — Tarea 4.3: límites de parámetros y rangos de barrido

## Propósito

Esta tarea fija dos tipos de límites distintos:

1. **límites de admisibilidad del modelo**, que no pueden violarse;
2. **rangos iniciales de exploración**, elegidos para el barrido numérico y sujetos a refinamiento posterior.

Los rangos de exploración no son límites físicos universales ni valores óptimos. Solo definen la primera malla reproducible para comparar candidatos bajo el escenario base de la Tarea 4.2 y las métricas de aceptación de la Tarea 4.1.

## Ecuación vigente

La dinámica de frecuencia implementada en `GridFormingFrequencyDynamics` es:

```text
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

con:

- `P_ref` y `P_e` en vatios;
- `omega` en rad/s;
- `M = inertia_m`;
- `D = damping_d`.

Dentro de esta formulación, las unidades implícitas son aproximadamente:

```text
M: W*s^2/rad
D: W*s/rad
```

## Límites de admisibilidad

### Inercia virtual `M`

```text
M > 0
```

Justificación:

- `M = 0` hace indefinida la ecuación por división entre cero;
- `M < 0` invierte el sentido de la respuesta inercial;
- el repositorio ya rechaza `inertia_m <= 0`.

### Amortiguamiento `D`

```text
D >= 0
```

Justificación:

- `D < 0` introduce antiamortiguamiento;
- `D = 0` es matemáticamente admisible y se conservará como caso de referencia sin amortiguamiento;
- la aceptación final de un candidato seguirá dependiendo de las métricas dinámicas, por lo que admitir `D = 0` no implica que dicho caso sea aceptable para la tesis.

### Orden fraccionario `alpha`

En el prototipo FOVIC existente, el parámetro está nombrado como `mu`. Para esta tesis se adopta la equivalencia:

```text
alpha = mu
```

Su dominio admisible es:

```text
0 < alpha < 1
```

El prototipo `FOVICInverter` ya rechaza valores fuera de ese intervalo, incluidos los extremos `0` y `1`.

FOVIC todavía no está integrado en el controlador principal. Por tanto, `alpha` se documenta para una fase comparativa futura y no participa en el primer barrido clásico de `M` y `D`.

## Barrido inicial formal de `M` y `D`

La auditoría de cierre del Bucket 4 identificó que la campaña original de
`6 x 7` excedía el máximo de tres valores por parámetro definido para la Tarea
4.2. El barrido inicial formal queda definido como:

```text
M = [2, 20, 80]
D = [0, 200, 1500]
3 x 3 = 9 combinaciones
```

Intervalos cubiertos:

```text
2 <= M <= 80
0 <= D <= 1500
```

El ejecutor formal rechaza más de tres valores únicos por parámetro. La mayor
resolución debe obtenerse mediante refinamientos locales sucesivos, también
limitados a `3 x 3`.

## Exploración ampliada histórica

La campaña previamente ejecutada utilizó:

```text
M = [2, 5, 10, 20, 40, 80]
D = [0, 50, 100, 200, 500, 1000, 1500]
6 x 7 = 42 combinaciones
```

Se conserva como evidencia histórica de sensibilidad y puede reproducirse con
`--extended-grid`, pero no se presenta como el barrido inicial formal.

## Barrido futuro de `alpha`

Cuando FOVIC esté correctamente refactorizado e integrado, la primera malla
comparativa será:

```text
alpha = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
```

No se combinará automáticamente con la campaña histórica de 42 parejas.

## Estrategia de refinamiento

La exploración compatible con el checklist se realiza en etapas:

1. barrido inicial formal de nueve combinaciones;
2. refinamiento local de máximo tres valores de `M` y tres de `D`;
3. resolución adicional mediante extremos y punto medio de intervalos cada vez
   más estrechos.

## Validaciones ejecutadas

Se reprodujeron las pruebas unitarias de `GridFormingFrequencyDynamics`:

```text
Ran 15 tests
OK
```

Estas pruebas incluyen el rechazo de:

```text
M <= 0
D < 0
```

También se comprobó directamente el prototipo FOVIC:

```text
mu = 0.4  -> aceptado
mu = 0.0  -> rechazado
mu = 1.0  -> rechazado
mu = -0.1 -> rechazado
mu = 1.1  -> rechazado
```

## Criterios aplicados a cada combinación

Cada punto del barrido deberá evaluarse bajo el escalón base del 20 % mediante:

- caída máxima de frecuencia `<= 0.50 Hz`;
- recuperación dentro de `60 +/- 0.10 Hz` en `<= 5.0 s`;
- permanencia en banda de `0.50 s`;
- sobreoscilación positiva del enlace DC `<= 5.0 %`;
- tensión mínima del enlace DC `>= 327.50 V`;
- estabilidad numérica y ausencia de `NaN/Inf`.

Cuando se ejecute la variante con BESS-SLB, también se registrarán corriente pico y RMS, potencia de carga/descarga, energía intercambiada y variación de SoC.

## Alcance

Esta tarea es documental. No cambia:

- la ecuación swing;
- los valores predeterminados de `GFMController`;
- la implementación FOVIC;
- el vector de estados;
- los parámetros eléctricos de la microrred;
- el comportamiento actual de las simulaciones.
