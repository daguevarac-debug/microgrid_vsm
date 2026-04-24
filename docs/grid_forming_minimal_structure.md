# Estructura mínima del inversor grid-forming

Este documento fija la estructura mínima que se usará como base para implementar el inversor grid-forming en etapas posteriores de la tesis.

Alcance de esta etapa:

- Definir variables de estado internas del inversor grid-forming.
- Explicitar el papel del ángulo eléctrico `theta`.
- Explicitar el papel de la frecuencia angular `omega`.
- Dejar planteadas las ecuaciones dinámicas mínimas.
- Diferenciar el inversor grid-forming de una fuente sinusoidal ideal.

Fuera de alcance en esta etapa:

- No se implementa todavía el controlador grid-forming completo.
- No se activa todavía el modo grid-forming en `main.py`.
- No se cambia todavía el vector de estados del baseline existente.
- No se modifica la física ya validada del PV, BESS, DC-link ni LCL.

## 1. Estado actual del baseline

El baseline actual usa un controlador grid-following PI para regulación del bus DC. La fase eléctrica se propaga con frecuencia fija de referencia.

Por tanto, el sistema actual no debe presentarse todavía como control grid-forming final.

## 2. Variables de estado mínimas del inversor grid-forming

Para representar el inversor grid-forming mínimo como una fuente interna de tensión con dinámica propia, el vector mínimo de estados del bloque GFM debe ser:

```text
x_gfm = [theta, omega]
```

Donde:

- `theta` [rad]: ángulo eléctrico interno del inversor.
- `omega` [rad/s]: frecuencia angular interna del inversor.

En el baseline actual, `theta` ya existe como variable asociada a la fase eléctrica de la fuente/inversor, pero `omega` todavía no está incorporada como estado dinámico independiente; la frecuencia se mantiene referida a `omega_ref`.

La incorporación futura de `omega` como estado debe hacerse de forma explícita y documentada, sin cambiar silenciosamente el orden del vector de estados existente de `Microgrid` ni activar todavía control grid-forming.

## 3. Ángulo eléctrico theta

`theta` [rad] es el ángulo eléctrico interno del inversor grid-forming y define la fase de la tensión trifásica sintetizada:

```text
v_a = Vpk * sin(theta)
v_b = Vpk * sin(theta - 2*pi/3)
v_c = Vpk * sin(theta + 2*pi/3)
```

En este contexto, `theta` no debe interpretarse como una señal externa impuesta por la red. En el baseline actual, `theta` ya existe, pero todavía está asociado a una frecuencia fija de referencia.

En el inversor grid-forming, `theta` debe evolucionar según:

```text
dtheta/dt = omega
```

Esta ecuación queda documentada como estructura mínima futura; no se implementa todavía ni cambia el vector de estados actual de `Microgrid`.

## 4. Frecuencia angular omega

`omega` [rad/s] es la frecuencia angular interna del inversor grid-forming y gobierna la evolución del ángulo eléctrico interno:

```text
dtheta/dt = omega
```

La referencia nominal se define como:

```text
omega_ref = 2*pi*f_nom
```

Para `f_nom = 60 Hz`, `omega_ref ≈ 376.99 rad/s`.

En una fuente sinusoidal ideal, `omega` es constante e impuesta. En un inversor grid-forming, `omega` debe tratarse como un estado dinámico interno.

La ecuación para `domega/dt` queda fuera de esta subtarea; no se implementa todavía ni cambia el vector de estados actual de `Microgrid`.

## 5. Ecuación dinámica mínima de frecuencia

La estructura matemática mínima se plantea como una forma reducida tipo VSG/swing, coherente con la revisión de GFM/VSG de Anttila et al. (2022), el uso de inercia virtual y amortiguamiento en microrred wind-PV-battery de Zhou et al. (2023), el soporte de inercia virtual con BESS de Nour et al. (2023) y la ecuación swing para dinámica de frecuencia en microrred de Nguyen et al. (2025):

```text
dtheta/dt = omega
```

```text
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

Donde:

- `theta` [rad]: ángulo eléctrico interno del inversor.
- `omega` [rad/s]: frecuencia angular interna del inversor.
- `P_ref` [W]: potencia activa mecánica/virtual o referencia activa equivalente.
- `P_e` [W]: potencia eléctrica entregada por el inversor; `P_ref - P_e` representa el desequilibrio activo.
- `D` [W/(rad/s)]: amortiguamiento virtual.
- `M` [J/(rad/s)^2] o parámetro equivalente: inercia virtual.
- `omega_ref` [rad/s]: frecuencia angular nominal.

Para mantener coherencia con el modelo existente, `P_e` puede calcularse en una implementación futura como la potencia medida en el lado AC/PCC:

```text
P_e = v_pcc^T * i2
```

Esta sección solo define la estructura matemática mínima; no implementa `domega/dt`, no activa control grid-forming y no introduce FOVIC ni controles avanzados.

## 6. Diferencia frente a una fuente sinusoidal ideal

Una fuente sinusoidal ideal de frecuencia fija impone:

```text
theta(t) = omega_ref*t + theta0
omega(t) = omega_ref
```

En ese caso, la frecuencia es externa/constante y no responde a cambios de carga ni a desequilibrios de potencia.

El inversor grid-forming mínimo no solo genera senoidales; incorpora estados internos:

```text
x_gfm = [theta, omega]
```

con la estructura dinámica mínima:

```text
dtheta/dt = omega
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

La diferencia clave es que `omega` puede variar dinámicamente ante el desequilibrio activo `P_ref - P_e`, con amortiguamiento virtual `D` e inercia virtual o equivalente `M`.

Esta definición sigue siendo estructural: no implica que el control grid-forming ya esté implementado, ni cambia el vector de estados actual de `Microgrid`.

## 7. Implicación para la siguiente tarea

La siguiente tarea debe implementar de forma conservadora:

```text
dtheta/dt = omega
```

y luego conectar la evolución de `omega` con el desequilibrio de potencia.

La implementación no debe activar todavía control avanzado de inercia virtual ni FOVIC si el objetivo inmediato solo es validar la dinámica básica de frecuencia.

## 8. Criterio de cierre de esta tarea

Esta tarea se considera cerrada si queda definido y trazable que:

- El bloque grid-forming mínimo tiene estados `theta` y `omega`.
- `theta` genera la fase de la tensión trifásica.
- `omega` gobierna la evolución de `theta`.
- La dinámica base cumple `dtheta/dt = omega`.
- La evolución de `omega` se asocia al desequilibrio `P_ref - P_e`.
- Se diferencia explícitamente de una fuente sinusoidal ideal de frecuencia fija.
