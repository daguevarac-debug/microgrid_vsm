# Evaluación de reutilización de `FOVICInverter.compute_delta_P_ESS()`

## Propósito

Esta evaluación determina si la implementación existente de `FOVICInverter.compute_delta_P_ESS()` puede incorporarse directamente dentro de `GFMController` o si requiere una refactorización para ser compatible con `InverterControllerBase`, el vector global de estados y el integrador adaptativo `solve_ivp`.

La evaluación no activa FOVIC, no modifica ecuaciones y no amplía el vector de estados actual.

## Componentes revisados

- `src/inverter_source.py`: `FOVICInverter`, `oustaloup_step()`, `compute_delta_P_ESS()` y `calculate_derivatives()`.
- `src/controllers/base.py`: contrato `InverterControllerBase.compute_control()` y salida `ControlOutput`.
- `src/controllers/gfm_controller.py`: integración actual del VSG clásico mediante `GridFormingFrequencyDynamics`.
- `docs/obj2_scope.md`: decisión arquitectónica de implementar primero la swing clásica y dejar FOVIC como extensión posterior.

## Resultado de la evaluación

**Decisión: `compute_delta_P_ESS()` no puede reutilizarse directamente dentro de `GFMController`. Requiere refactorización previa.**

La formulación matemática y la construcción de la aproximación de Oustaloup sí pueden conservarse como referencia para una implementación futura, pero la forma actual de actualización de estados no cumple el contrato dinámico del modelo principal.

## Compatibilidad con `InverterControllerBase`

El contrato actual exige que el controlador:

1. reciba las señales de planta y los estados correspondientes al instante evaluado;
2. calcule una acción sin integrar estados por su cuenta;
3. devuelva un `ControlOutput` con tensión del inversor, corriente DC equivalente, derivadas angulares y señales de potencia;
4. sea evaluable repetidamente por `solve_ivp` sin efectos secundarios dependientes del orden de llamadas.

`FOVICInverter.compute_delta_P_ESS()` no cumple esas condiciones por las siguientes razones:

| Aspecto | Contrato requerido | Implementación FOVIC actual | Resultado |
| --- | --- | --- | --- |
| Herencia/interfaz | Controlador compatible con `InverterControllerBase` | `FOVICInverter` no hereda de la interfaz | No compatible |
| Firma | `compute_control(t, theta, estado, Vdc, v_pcc, i1, i2, plant, ipv)` | `compute_delta_P_ESS(delta_f, dt)` | No compatible |
| Salida | `ControlOutput` completo | Escalar `delta_P_ESS` | No compatible |
| Estados dinámicos | Estados visibles en el vector global | `_x_oust`, `_x_dc` y `_x_bess` privados | No compatible |
| Evaluación ODE | Función pura de `t` y `x` | Modifica memoria interna | No compatible |
| Paso temporal | Determinado por `solve_ivp` | Requiere `dt` externo | No compatible |
| Integración | Un único integrador global | Euler explícito interno | No compatible |
| Límites BESS-SLB | SoC, SoH, corriente y potencia disponibles | No recibe ni aplica estos límites | Incompleto |

## Problema principal: memoria interna y `dt`

La implementación actual actualiza internamente:

```text
_x_oust <- _x_oust + dt * x_oust_dot
_x_dc   <- _x_dc   + dt * x_dc_dot
_x_bess <- _x_bess + dt * x_bess_dot
```

Esta lógica supone que cada llamada representa un paso temporal aceptado y que las llamadas ocurren en orden estrictamente creciente. Esa suposición no es válida para `solve_ivp`.

Un integrador adaptativo puede:

- evaluar varias veces la función de derivadas para construir un solo paso;
- repetir una evaluación con un estado distinto;
- rechazar un paso y volver a un tiempo anterior;
- cambiar internamente el tamaño del paso.

Si `compute_delta_P_ESS()` modifica memoria durante esas evaluaciones, el resultado pasa a depender del historial de llamadas del solver y no solo de `(t, x)`. Esto rompe la definición de una ODE reproducible y puede introducir integración duplicada, deriva numérica y resultados diferentes al cambiar tolerancias.

## Estados ocultos identificados

Para un orden de Oustaloup `N`, la realización actual requiere:

```text
x_oust: 2N + 1 estados
x_dc:   1 estado
x_bess: 1 estado
```

Por tanto, el bloque FOVIC añade:

```text
n_FOVIC = 2N + 3
```

Con el valor predeterminado `N = 5`:

```text
x_oust = 11 estados
x_dc   = 1 estado
x_bess = 1 estado
Total  = 13 estados adicionales
```

Una futura integración explícita produciría, antes de cualquier nueva decisión arquitectónica:

- GFM sin BESS físico: `12 + 13 = 25` estados.
- GFM con BESS físico: `15 + 13 = 28` estados.

Estos tamaños son informativos. No autorizan modificar los vectores protegidos actuales.

## Elementos que sí pueden conservarse

La reutilización futura puede preservar:

- los parámetros `K_DC`, `T_DC`, `T_BESS`, `K_H`, `mu`, `omega_l`, `omega_h` y `oustaloup_order`;
- las ecuaciones de polos, ceros y ganancia de la aproximación de Oustaloup;
- la estructura en cascada del bloque fraccionario, el bloque DC y el filtro de potencia del BESS;
- la definición conceptual de `delta_P_ESS` como señal auxiliar de potencia;
- las validaciones numéricas de parámetros existentes.

No debe conservarse la integración Euler con memoria privada dentro del controlador principal.

## Refactor mínimo requerido

Antes de conectar FOVIC al modelo principal se requiere, como mínimo:

### 1. Exponer todos los estados

Definir un vector explícito:

```text
x_fovic = [x_oust_0, ..., x_oust_2N, x_dc, x_bess]
```

Los estados deberán formar parte del vector global integrado por el mismo `solve_ivp` que integra la planta, `omega`, `theta` y el BESS físico.

### 2. Sustituir el paso Euler por una función de derivadas pura

La interfaz matemática deberá tener una forma equivalente a:

```text
fovic_rhs(t, x_fovic, delta_f)
    -> dx_fovic_dt, delta_P_FOVIC
```

La función no deberá modificar atributos internos, no deberá recibir `dt` y deberá devolver las derivadas de todos sus estados.

### 3. Separar el bloque fraccionario del controlador completo

La opción preferida es implementar el bloque FOVIC como un subsistema compuesto por `GFMController` o por un futuro `FOVICController`, en vez de introducir memoria fraccionaria directamente dentro del método actual `compute_control()`.

Una clase controladora futura deberá implementar `InverterControllerBase` y devolver un `ControlOutput` completo.

### 4. Normalizar variables y unidades

La implementación actual recibe `delta_f`, mientras el GFM principal integra `omega` en `rad/s`. Antes de conectar ambos bloques se deberá fijar explícitamente:

```text
delta_f = (omega - omega_ref) / (2*pi)     [Hz]
```

También deberá verificarse la equivalencia de escalas entre:

- `H` y `M_omega`;
- el amortiguamiento `D` en frecuencia y `D_omega` en la ecuación swing;
- `delta_P_ESS` y las potencias trifásicas expresadas en vatios.

### 5. Aplicar límites del BESS-SLB

La señal fraccionaria no podrá entrar sin saturación en la ecuación de frecuencia. Deberá limitarse con la disponibilidad real calculada por la capa supervisora:

```text
p_charge_available
p_discharge_available
SoC
SoH
i_bess_max_available
p_bess_dc_max_available
```

El estado privado `_x_bess` del prototipo es un filtro de potencia. No sustituye `soc_bess`, `vrc_bess` ni `zdeg_bess`, y no debe duplicar la física del modelo Thévenin 1RC.

### 6. Definir la entrada a la ecuación swing

La integración futura deberá adoptar una forma explícita como:

```text
domega/dt = (
    P_ref_eff
    - P_e
    + delta_P_FOVIC_limited
    - D_omega*(omega - omega_ref)
) / M_omega
```

La convención de signo deberá validarse con escenarios donde el aumento de carga produzca inicialmente reducción de frecuencia y la señal del almacenamiento responda en la dirección esperada.

## Pruebas mínimas para autorizar una integración futura

Una refactorización FOVIC deberá demostrar:

1. función de derivadas sin efectos secundarios;
2. dimensión correcta para distintos valores de `N`;
3. equilibrio con `delta_f = 0`;
4. invariancia frente a evaluaciones repetidas de la misma pareja `(t, x)`;
5. resultados consistentes al variar tolerancias de `solve_ivp`;
6. conversión correcta entre Hz y rad/s;
7. saturación por SoC, SoH, corriente y potencia;
8. ausencia de duplicación de estados físicos del BESS;
9. comparación bajo los mismos escenarios pre-GFM y VSG clásico;
10. mejora medible en nadir, RoCoF, tiempo de establecimiento u oscilación de potencia que justifique los estados adicionales.

## Decisión de cierre de la subtarea

```text
Reutilización directa de compute_delta_P_ESS(): NO
Reutilización de formulación y construcción Oustaloup: SÍ
Refactor requerido: SÍ
Activación FOVIC en GFMController en esta etapa: NO
Estrategia vigente: VSG clásico primero
```

La evaluación confirma la decisión de `docs/obj2_scope.md`: FOVIC permanece como extensión comparativa futura. No se añadirán estados Oustaloup ni se modificará `GFMController` hasta completar y validar la integración VSG clásica y aprobar una arquitectura explícita para los estados fraccionarios.
