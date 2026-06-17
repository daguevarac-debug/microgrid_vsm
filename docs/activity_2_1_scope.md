# Actividad 2.1 — Alcance mínimo y criterio de cierre

## Propósito

La Actividad 2.1 tiene como objetivo implementar la planta de control grid-forming mínima que reemplazará al `GridFollowingController` dentro de la dinámica principal, sin introducir todavía FOVIC, control `Q-V`, convertidor DC/DC detallado ni una estrategia final de protección BMS.

La actividad debe producir una línea base VSG clásica, continua, reproducible y compatible con `solve_ivp`. Esta línea base servirá después para añadir las restricciones del BESS-SLB y comparar variantes más avanzadas.

## Diferencia entre formulación cerrada e implementación cerrada

La formulación se considera cerrada cuando ya no quedan decisiones matemáticas o de interfaz pendientes para programar el controlador. La Actividad 2.1 completa se considera cerrada cuando esa formulación está implementada, conectada a la planta y validada mediante pruebas mínimas.

Cerrar la formulación no significa demostrar todavía que el VSG es la estrategia final de la tesis. Significa que existe una definición única y programable de sus ecuaciones, estados, entradas, salidas, signos, unidades y límites de responsabilidad.

## Formulación mínima que debe quedar fijada

La dinámica seleccionada es:

```text
dtheta/dt = omega

domega/dt = (P_ref_eff - P_e - D_omega*(omega - omega_ref)) / M_omega
```

La potencia eléctrica se define en el PCC:

```text
P_e = v_pcc_abc^T * i2_abc
```

La convención de signo debe ser positiva cuando el inversor entrega potencia hacia la carga o el PCC. Un desequilibrio `P_ref_eff - P_e > 0` debe producir aceleración positiva, salvo el efecto del amortiguamiento.

El vector mínimo sin BESS deberá quedar documentado y aplicado como:

```text
x_gfm = [
    Vdc,
    i1_a, i1_b, i1_c,
    vc_a, vc_b, vc_c,
    i2_a, i2_b, i2_c,
    omega,
    theta,
]
```

Por tanto, `omega` reemplazará de forma explícita a `xi_vdc` en la posición 10 y `theta` permanecerá en la posición 11. El cambio no podrá realizarse silenciosamente: deberá reflejarse en condiciones iniciales, documentación, pruebas y funciones de posprocesamiento.

Para `MicrogridWithBESS`, el vector mínimo deberá conservar los tres estados de batería ya existentes:

```text
x_gfm_bess = x_gfm + [soc_bess, vrc_bess, zdeg_bess]
```

La formulación también deberá fijar que `P_ref_eff` es una referencia activa ya limitada por la capa que corresponda. En la Actividad 2.1 podrá emplearse una referencia fija o una limitación mínima coherente con la potencia disponible, pero no deberá presentarse todavía como protección final del BESS-SLB.

## Interfaz mínima del controlador

El controlador GFM deberá implementar `InverterControllerBase` o una interfaz compatible explícitamente documentada. Deberá recibir como mínimo `theta`, `omega`, `Vdc`, `P_e`, la referencia activa efectiva y los parámetros necesarios de la planta para modular la tensión y calcular el intercambio DC/AC.

La salida mínima deberá contener la tensión trifásica sintetizada `v_inv_abc`, la corriente equivalente `idc_inv`, `dtheta/dt`, `domega/dt`, la potencia del puente, la potencia en el PCC, la referencia activa aplicada y el índice de modulación.

`HardwarePlant` mantendrá las ecuaciones físicas. `Microgrid` ensamblará estados y calculará magnitudes algebraicas. El controlador no deberá reconstruir internamente la dinámica del filtro LCL ni la carga R-L.

## Criterio de formulación cerrada

La formulación se declarará cerrada únicamente cuando se cumplan simultáneamente las condiciones siguientes:

| Condición | Evidencia requerida |
|---|---|
| La ecuación de `domega/dt` es única y no contiene `s^mu` | Ecuación documentada con signos y unidades |
| El orden del vector de estados está fijado | Definición explícita de los vectores de 12 y 15 posiciones |
| `P_e` tiene una definición única | Cálculo en el PCC con la tensión R-L completa |
| Las entradas y salidas del controlador están fijadas | Firma o contrato documentado |
| Las condiciones iniciales están definidas | `omega(0) = omega_ref` y `theta(0) = theta0` |
| Las responsabilidades están separadas | Planta, controlador y supervisión BESS delimitados |
| Los parámetros tienen significado y unidades | `M_omega`, `D_omega`, `omega_ref`, `P_ref_eff` documentados |
| El plan de validación está definido | Pruebas de equilibrio, signo, escalón y límites de modulación |

Si una de estas decisiones permanece abierta, la formulación no estará cerrada y no deberá generarse todavía el prompt definitivo de implementación.

## Criterio de done de la Actividad 2.1

La Actividad 2.1 se considerará terminada solo cuando el controlador GFM mínimo esté funcionando dentro de la dinámica principal y cumpla todos los criterios siguientes:

| Resultado mínimo | Criterio de aceptación |
|---|---|
| Controlador GFM integrado | `Microgrid.system_dynamics` puede ejecutar el modo GFM sin usar la dinámica fija del `GridFollowingController` |
| Estados GFM integrados | `omega` y `theta` pertenecen al vector resuelto por `solve_ivp`; no existe memoria dinámica oculta |
| Potencia eléctrica coherente | `P_e` usa la tensión PCC R-L completa y la corriente `i2_abc` |
| Modulación funcional | `v_inv_abc` se genera desde `theta`, `V_ref`, `Vdc` y el límite de modulación |
| Intercambio DC/AC conservado | `idc_inv` mantiene la convención y la ecuación validada del enlace DC |
| Compatibilidad con BESS | `MicrogridWithBESS` puede ejecutar el mismo controlador conservando `soc_bess`, `vrc_bess` y `zdeg_bess` |
| Equilibrio nominal | Con `P_ref_eff = P_e` y `omega = omega_ref`, `domega/dt` es aproximadamente cero |
| Signo físico correcto | Un aumento de carga produce inicialmente una tendencia de reducción de frecuencia |
| Respuesta finita | La simulación no genera `NaN`, `Inf` ni estados dimensionalmente inconsistentes |
| Regresión controlada | El baseline grid-following continúa disponible como referencia y sus entradas públicas no se rompen sin compatibilidad |
| Evidencia reproducible | Existen pruebas o validaciones ejecutables y un registro de resultados |
| Documentación actualizada | Se documentan vector de estados, ecuaciones, parámetros, señales y limitaciones |

No será suficiente que la clase aislada calcule `domega/dt`. La actividad exige que el controlador forme parte del camino dinámico principal y que la planta responda a su ángulo y frecuencia.

## Validaciones mínimas

La validación mínima deberá incluir una prueba unitaria de equilibrio, una prueba del signo de `domega/dt`, una simulación nominal, una perturbación de carga y una ejecución con `MicrogridWithBESS`. Las pruebas deberán comprobar al menos frecuencia, ángulo, `P_e`, `P_ref_eff`, `Vdc`, índice de modulación y ausencia de valores no finitos.

Las métricas de nadir, RoCoF y tiempo de establecimiento podrán registrarse desde esta etapa, pero no se presentarán todavía como desempeño final de tesis hasta completar la integración del BESS supervisado y la comparación de estrategias.

## Fuera del alcance de la Actividad 2.1

No forman parte del criterio de cierre de esta actividad el término fraccionario `s^mu`, la refactorización completa de `FOVICInverter`, la sintonización óptima de `M_omega` y `D_omega`, el control reactivo `Q-V`, droop avanzado, la modelación detallada del convertidor DC/DC, la protección térmica completa, un BMS comercial ni la selección final entre VSG y FOVIC.

Tampoco se exige demostrar todavía la vida útil extendida del BESS. La Actividad 2.1 debe entregar únicamente una base GFM/VSG funcional sobre la cual puedan conectarse después las restricciones de una batería de segunda vida.

## Regla de avance

No deberá iniciarse la siguiente actividad mientras falte alguno de los criterios de done anteriores. El cierre deberá registrar los archivos modificados, pruebas ejecutadas, resultados obtenidos, limitaciones restantes y la confirmación de que el baseline grid-following continúa disponible como referencia.
