# Estructura del inversor grid-forming implementado

## Estado actual

La estructura mínima grid-forming definida inicialmente para el Objetivo 2 ya
está implementada e integrada en la planta completa mediante
`GFMController`. El controlador conserva una formulación VSG clásica reducida,
compatible con la interfaz común de controladores del repositorio.

El GFM actual no es una fuente sinusoidal ideal de frecuencia fija y tampoco es
una implementación FOVIC. `omega` es un estado dinámico interno que responde al
desequilibrio de potencia activa y gobierna la evolución del ángulo `theta`.

## Estados internos del GFM

El bloque grid-forming usa:

```text
x_gfm = [theta, omega]
```

con:

- `theta` [rad]: ángulo eléctrico interno;
- `omega` [rad/s]: frecuencia angular interna.

En la arquitectura completa, estos estados ocupan posiciones protegidas:

```text
GFM sin BESS, 12 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta]

GFM con BESS, 15 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess]

GFM con BESS y PI de Vdc, 16 estados:
[Vdc, i1_a, i1_b, i1_c, vc_a, vc_b, vc_c,
 i2_a, i2_b, i2_c, omega, theta,
 soc_bess, vrc_bess, zdeg_bess, xi_bess_vdc]
```

Por tanto:

- `x[10] = omega` en modo GFM;
- `x[11] = theta`;
- los estados BESS permanecen en `x[12]`, `x[13]` y `x[14]`;
- el PI externo del bus DC, cuando se usa, añade `xi_bess_vdc` en `x[15]`;
- todos los estados se integran en un único `solve_ivp`.

## Síntesis trifásica de tensión

La tensión interna del inversor se genera a partir de `theta`:

```text
v_a = Vpk*sin(theta)
v_b = Vpk*sin(theta - 2*pi/3)
v_c = Vpk*sin(theta + 2*pi/3)
```

La amplitud sintetizable depende de la referencia de tensión, del bus DC y del
límite de modulación. Si `Vdc` cae por debajo del umbral UVLO, el controlador
anula la tensión del puente y la corriente DC del inversor.

## Dinámica angular y de frecuencia

La formulación implementada es:

```text
dtheta/dt = omega
```

```text
domega/dt = (P_ref_eff - P_e - D*(omega - omega_ref))/M
```

Donde:

- `P_ref_eff` [W]: referencia activa limitada por disponibilidad DC;
- `P_e` [W]: potencia eléctrica entregada en el PCC;
- `D`: amortiguamiento virtual;
- `M`: parámetro de inercia virtual equivalente;
- `omega_ref = 2*pi*f_nom`.

La potencia eléctrica se calcula con la tensión completa del PCC de la carga R-L:

```text
P_e = v_pcc^T*i2
```

No se usa la aproximación puramente resistiva para la realimentación final del
GFM integrado.

## Referencia activa y disponibilidad energética

`GFMController` no aplica una referencia activa ilimitada. La potencia efectiva
se restringe por la disponibilidad neta del lado DC:

```text
P_pv_dc_available = max(Vdc*ipv, 0)
P_dc_net_available = P_pv_dc_available + P_bess_dc_actual
P_net_ac_available = max(eta*P_dc_net_available, 0)
P_ref_eff = min(P_ref, P_net_ac_available)
```

Cuando el BESS carga, `P_bess_dc_actual < 0` y reduce la potencia neta disponible.
Cuando descarga, puede aumentar el soporte solo dentro de los límites de SoC,
SoH, corriente y potencia disponibles.

## Punto seleccionado para validación integrada

La campaña principal usa:

```text
M = 80
D = 1500
```

Este punto corresponde a la formulación VSG clásica adoptada para el cierre del
Objetivo 2. Cambiarlo exige repetir la campaña integrada y documentar el nuevo
criterio de selección.

## Diferencia frente a una fuente sinusoidal ideal

Una fuente ideal de frecuencia fija impondría:

```text
theta(t) = omega_ref*t + theta0
omega(t) = omega_ref
```

El GFM implementado, en cambio, integra `omega` como estado y permite que la
frecuencia responda a `P_ref_eff - P_e` con inercia y amortiguamiento virtuales.
La frecuencia observable se obtiene como:

```text
frequency_hz = omega/(2*pi)
```

## Integración con el BESS

La arquitectura con BESS conserva:

```text
dVdc/dt = (ipv + i_bess - idc_inv)/Cdc
p_bess_dc = Vdc*i_bess
```

El controlador recibe información de supervisión sobre:

- SoC;
- SoH;
- corriente máxima disponible;
- potencia máxima disponible;
- potencia DC real y firmada del BESS.

La arquitectura opcional `MicrogridWithBESSPI` añade un PI externo del bus DC.
Ese PI limita su referencia por las restricciones del BESS y usa anti-windup
condicional. No modifica las ecuaciones VSG ni los valores seleccionados de `M`
y `D`.

## Validación implementada

La estructura integrada se verifica mediante:

- `validate_gfm_integrated_system.py`;
- `validate_physical_invariants.py`;
- `validate_obj1_regression.py`;
- `validate_ieee33_gfm_pcc_average.py`;
- `validate_ieee33_gfm_voltage_profile.py`.

Los escenarios estacionario, escalón del 20 % y comparación BESS/no BESS están en
`PASS`. El escalón severo del 40 % queda en `REVIEW` por el criterio del enlace
DC, no por error del solucionador ni de la dinámica GFM.

## Alcance y trabajo futuro

La estructura actual cierra la integración VSG clásica del Objetivo 2. Quedan
fuera:

- FOVIC y dinámica de orden fraccionario;
- control reactivo Q-V;
- lazos internos detallados de corriente y tensión;
- convertidor DC/DC detallado;
- BMS industrial final;
- optimización global y demostración formal completa de estabilidad;
- validación experimental o HIL.

La formulación implementada debe presentarse como GFM/VSG clásico integrado, no
como contribución FOVIC final.