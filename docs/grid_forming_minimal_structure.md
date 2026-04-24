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

Para representar un inversor grid-forming como fuente interna de tensión con dinámica propia, el bloque mínimo del inversor debe tener los siguientes estados:

```text
x_gfm = [theta, omega]
```

Donde:

- `theta` [rad]: ángulo eléctrico interno del inversor.
- `omega` [rad/s]: frecuencia angular interna del inversor.

Estos estados pertenecen al bloque de control/fuente del inversor. Cuando se integren al modelo completo, deben añadirse de forma explícita y documentada, sin cambiar silenciosamente el orden del vector de estados existente.

## 3. Ángulo eléctrico theta

El ángulo `theta` define la fase de la tensión trifásica sintetizada por el inversor:

```text
v_a = Vpk * sin(theta)
v_b = Vpk * sin(theta - 2*pi/3)
v_c = Vpk * sin(theta + 2*pi/3)
```

En una fuente sinusoidal ideal, `theta` se impone desde afuera como una señal fija. En un inversor grid-forming, `theta` es un estado interno del sistema.

## 4. Frecuencia angular omega

La frecuencia angular `omega` determina la velocidad de evolución del ángulo interno:

```text
dtheta/dt = omega
```

En el baseline actual, la frecuencia se mantiene fija en `omega_ref`. En un inversor grid-forming, `omega` puede cambiar dinámicamente ante desequilibrios de potencia.

## 5. Ecuación dinámica mínima de frecuencia

La estructura mínima de frecuencia se deja planteada con una ecuación tipo swing reducida:

```text
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

Donde:

- `P_ref` [W]: potencia activa mecánica/virtual o referencia activa equivalente.
- `P_e` [W]: potencia eléctrica entregada por el inversor al punto de acople local.
- `D` [W/(rad/s)]: amortiguamiento virtual.
- `M` [J/(rad/s)^2] o parámetro equivalente: inercia virtual agregada.
- `omega_ref` [rad/s]: frecuencia angular nominal.

Para mantener coherencia con el modelo existente, una opción natural para `P_e` en la integración futura es la potencia medida en el lado AC/PCC:

```text
P_e = v_pcc^T * i2
```

La selección final de `P_e` debe mantenerse trazable porque el código actual también calcula `p_bridge` y `p_pcc` como señales diagnósticas.

## 6. Diferencia frente a una fuente sinusoidal ideal

Una fuente sinusoidal ideal se define por:

```text
theta(t) = omega_ref*t + theta0
omega(t) = omega_ref
```

Eso significa que la frecuencia no responde al intercambio de potencia, ni al escalón de carga, ni al estado del bus DC.

Un inversor grid-forming mínimo se diferencia porque:

```text
dtheta/dt = omega
omega = estado dinamico
omega responde a P_ref - P_e
```

Por esta razón, el inversor grid-forming puede formar una referencia de tensión/frecuencia interna sin depender de una red externa rígida.

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
