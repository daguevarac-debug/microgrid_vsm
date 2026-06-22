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

## Barrido grueso inicial de `M`

Se explorarán los valores:

```text
M = [2, 5, 10, 20, 40, 80]
```

Intervalo cubierto:

```text
2 <= M <= 80
```

Criterio de selección:

- evita comenzar arbitrariamente cerca de `M = 0`, donde una misma descompensación de potencia produciría una derivada de frecuencia muy elevada;
- incluye `M = 2`, ya empleado en una comparación GFM existente del repositorio;
- cubre aproximadamente desde una respuesta de baja inercia hasta una respuesta de alta inercia sin generar una malla excesivamente grande.

Como referencia únicamente orientativa, usando:

```text
S_base = 3000/0.95 = 3157.894737 VA
omega_0 = 2*pi*60 rad/s
M = 2*H*S_base/omega_0
```

la malla equivale aproximadamente a:

| `M` | `H` orientativo [s] |
|---:|---:|
| 2 | 0.119 |
| 5 | 0.298 |
| 10 | 0.597 |
| 20 | 1.194 |
| 40 | 2.388 |
| 80 | 4.775 |

Esta conversión no cambia la variable que se simulará: el barrido se realizará directamente sobre `inertia_m`.

## Barrido grueso inicial de `D`

Se explorarán los valores:

```text
D = [0, 50, 100, 200, 500, 1000, 1500]
```

Intervalo cubierto:

```text
0 <= D <= 1500
```

Criterio de selección:

- `D = 0` proporciona una referencia sin amortiguamiento;
- los valores intermedios permiten observar la transición entre respuesta poco amortiguada y fuertemente amortiguada;
- `D = 1000` y `D = 1500` permiten explorar el orden de magnitud requerido por el escalón base de `600 W`.

A partir del equilibrio aproximado de la ecuación swing:

```text
Delta_P = D*Delta_omega
```

para un escalón de `600 W` y una desviación de frecuencia de `0.10 Hz`:

```text
D ~= 600 / (2*pi*0.10) = 954.93
```

Este cálculo es una guía de escala, no sustituye la simulación ni garantiza recuperación dinámica. La aceptación seguirá dependiendo del nadir, tiempo de recuperación, permanencia en banda y tensión del enlace DC.

## Barrido futuro de `alpha`

Cuando FOVIC esté correctamente refactorizado e integrado, la primera malla será:

```text
alpha = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
```

Intervalo inicial explorado:

```text
0.2 <= alpha <= 0.8
```

Esta malla:

- permanece estrictamente dentro del dominio abierto `(0, 1)`;
- incluye `alpha = 0.4`, valor predeterminado del prototipo actual;
- no redefine el límite físico: valores entre `0` y `0.2`, o entre `0.8` y `1`, podrían estudiarse después si los resultados justifican una expansión del barrido.

## Tamaño del barrido

El barrido clásico inicial contiene:

```text
6 valores de M x 7 valores de D = 42 combinaciones
```

No se ejecutará todavía el producto cartesiano con `alpha`. La malla fraccionaria se incorporará únicamente después de validar una implementación FOVIC compatible con el integrador global y con los límites del BESS-SLB.

## Estrategia de refinamiento

La exploración se realizará en dos etapas:

1. **barrido grueso:** evaluar las 42 combinaciones anteriores;
2. **refinamiento local:** crear una malla más estrecha alrededor de los mejores candidatos que cumplan simultáneamente las métricas de la Tarea 4.1.

Los puntos del refinamiento local no se fijan en esta tarea porque dependerán de los resultados del barrido grueso.

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
