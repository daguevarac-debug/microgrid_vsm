# Alcance del Objetivo 2: interfaz de señales entre planta y control GFM

## Propósito

Este documento delimita qué información de la planta eléctrica está disponible actualmente para el controlador del inversor y qué magnitudes deben calcularse o estimarse antes de integrar una estrategia grid-forming. Su alcance es exclusivamente documental: no activa el modo GFM, no modifica `Microgrid.system_dynamics`, no cambia el orden del vector de estados y no selecciona todavía entre VSG clásico, FOVIC o una arquitectura híbrida.

## Ruta actual de señales hacia el controlador

La planta física está encapsulada en `HardwarePlant`, mientras que `Microgrid` extrae los estados, evalúa los perfiles y llama a `controller.compute_control(...)`. En consecuencia, el controlador no recibe directamente el vector completo de estados ni debe acceder de forma indiscriminada a la física interna de la planta. La interfaz actual entrega las siguientes variables:

| Variable recibida por `compute_control` | Origen | Naturaleza | Uso actual o previsto |
|---|---|---|---|
| `t` | Integrador numérico | Tiempo de simulación | Evaluación temporal y lógica de control. No es una señal física de planta. |
| `theta` | Estado `x[11]` de `Microgrid` | Estado interno del control/inversor | En el baseline evoluciona a frecuencia fija. En GFM continuará como ángulo interno, con `dtheta/dt = omega`. |
| `xi_vdc` | Estado `x[10]` de `Microgrid` | Estado interno del PI grid-following | Solo pertenece al regulador PI del enlace DC. Su permanencia dependerá de la arquitectura futura. |
| `vdc_eff` | Estado `Vdc = x[0]`, limitado inferiormente a cero | Medición de planta | Limita la tensión AC sintetizable, la modulación, la condición UVLO y el intercambio de potencia DC/AC. |
| `i1` | Estados `x[1:4]` | Medición de planta | Corriente trifásica del lado inversor del filtro LCL. Permite calcular potencia en el puente y aplicar límites de corriente. |
| `i2` | Estados `x[7:10]` | Medición de planta | Corriente trifásica del lado PCC/carga. Es necesaria para estimar la potencia eléctrica entregada. |
| `v_pcc` | Calculada por `Microgrid` antes de llamar al controlador | Estimación de planta | La implementación actual usa una clausura resistiva provisional. No debe asumirse como la tensión PCC exacta del modelo R-L. |
| `ipv` | Resultado de `HardwarePlant.pv_current(...)` | Medición/modelo de fuente DC | Permite estimar la potencia fotovoltaica disponible en el enlace DC. |
| `plant` | Referencia al objeto `HardwarePlant` | Contenedor de parámetros y métodos | Da acceso a `eta`, `v_uvlo`, `dcp`, `lcl` y al modelo FV. No debe confundirse con una señal medida. |

Aunque `HardwarePlant` contiene la dinámica del PV, el enlace DC y el filtro LCL, no todas sus variables físicas llegan explícitamente al controlador. En particular, `vc_abc = x[4:7]` permanece en `Microgrid.system_dynamics` y no forma parte de la firma actual de `compute_control`. Tampoco se entregan como entradas `idc_inv`, `p_bridge`, `p_pcc` ni `P_e`; las primeras son salidas o diagnósticos calculados durante la evaluación del control y de la planta.

## Señales disponibles directamente y señales que deben calcularse

La distinción operativa para el Objetivo 2 es la siguiente:

| Magnitud | Disponibilidad actual | Tratamiento para el GFM |
|---|---|---|
| `Vdc` | Directa desde el vector de estados | Debe mantenerse como entrada de planta para limitar la referencia de tensión y la modulación. |
| `i1_abc` | Directa desde el vector de estados | Debe conservarse para supervisión de corriente, potencia del puente y futuras protecciones. |
| `i2_abc` | Directa desde el vector de estados | Debe conservarse porque participa en la estimación de la potencia eléctrica en el PCC. |
| `vc_abc` | Disponible en la planta, pero no llega al controlador | Podrá requerirse para reconstruir la tensión PCC exacta o para lazos internos; no es necesaria en la ecuación swing mínima si se entrega `P_e` ya calculada. |
| `v_pcc_abc` | Actualmente se entrega una aproximación resistiva | Debe calcularse con la clausura R-L completa antes de emplearse en la realimentación de potencia del GFM. |
| `P_e` | No existe como estado ni como entrada explícita | Debe estimarse algebraicamente a partir de las variables eléctricas de planta. |
| `idc_inv` | Calculada por el controlador actual | Debe seguir siendo una consecuencia del intercambio de potencia y no una entrada manipulable independiente. |
| `p_bridge` | Calculada como `v_inv_abc^T i1_abc` | Es útil para balance energético y diagnóstico, pero no equivale necesariamente a la potencia entregada en el PCC. |

## Estimación requerida de la potencia eléctrica `P_e`

La ecuación reducida del GFM/VSG requiere una potencia eléctrica de realimentación:

```text
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

Para conservar coherencia con la frontera eléctrica de la microrred, la definición preferida es la potencia activa instantánea en el PCC:

```text
P_e = v_pcc_abc^T * i2_abc
```

`P_e` es una variable algebraica; no debe agregarse como estado dinámico. Su signo deberá conservar la convención de potencia positiva cuando el inversor entrega energía hacia la carga o el PCC.

La implementación actual exige una precaución. Antes de llamar a `compute_control`, `_compute_step_control()` construye `v_pcc` mediante `HardwarePlant.pcc_voltage(i2, r_load)`, cuya expresión corresponde a la clausura resistiva heredada:

```text
v_pcc_abc,aprox = R_load * i2_abc
```

Sin embargo, el modelo validado de carga es R-L. La tensión PCC físicamente coherente se obtiene después mediante:

```text
di2/dt = (vc - (R2 + R_load)*i2) / (L2 + L_load)
v_pcc_abc = R_load*i2 + L_load*di2/dt
```

Por tanto, el valor de `p_pcc` calculado dentro del controlador grid-following con la aproximación resistiva no debe reutilizarse sin revisión como `P_e` final del GFM. La futura integración deberá calcular la tensión PCC R-L exacta a partir del estado instantáneo y entregar al controlador una de estas dos interfaces explícitas:

```text
Opción A: p_e
Opción B: v_pcc_abc e i2_abc
```

La opción A reduce el acoplamiento entre el controlador y la planta, puesto que `Microgrid` conserva la responsabilidad de calcular magnitudes eléctricas. La opción B mantiene más información disponible para protecciones y control de tensión, pero obliga a documentar con precisión cómo se obtiene `v_pcc_abc`.

La potencia del puente,

```text
p_bridge = v_inv_abc^T * i1_abc
```

no debe sustituir automáticamente a `P_e`. Entre el puente y el PCC existen el filtro LCL, pérdidas resistivas e intercambio temporal de energía en inductores y capacitor; en consecuencia, `p_bridge` y `p_pcc` pueden diferir durante transitorios. `p_bridge` debe conservarse como señal de balance y diagnóstico, mientras que `P_e` para la ecuación de frecuencia debe referirse preferentemente al PCC.

## Entradas mínimas del futuro controlador GFM

El núcleo GFM deberá recibir o disponer de `P_ref`, `V_ref`, `Vdc` y `P_e`. Los estados `theta` y `omega` pertenecerán al propio controlador. Las corrientes `i1_abc` e `i2_abc`, junto con `v_pcc_abc`, podrán mantenerse como mediciones auxiliares para límites de corriente, supervisión de potencia y futuras capas de control de tensión.

Las variables del BESS-SLB no pertenecen a `HardwarePlant`. `SoC`, `SoH`, `i_bess`, `p_bess_dc`, `i_bess_max_available` y `p_bess_dc_max_available` deberán llegar desde `MicrogridWithBESS` o desde una capa supervisora equivalente. Su función será restringir `P_ref`, la potencia inercial disponible o los parámetros adaptativos del control; no reemplazan la medición eléctrica `P_e`.

## Criterios para la integración posterior

La implementación futura deberá mantener separadas tres responsabilidades. `HardwarePlant` conservará las ecuaciones físicas; `Microgrid` ensamblará estados y calculará mediciones algebraicas como `v_pcc_abc` y `P_e`; el controlador GFM producirá la dinámica de `theta` y `omega`, la referencia de tensión y las señales de actuación. Esta separación evita que el controlador reconstruya por su cuenta la física del filtro o de la carga.

Antes de conectar el GFM a `Microgrid.system_dynamics`, deberá verificarse que `P_e` usa la tensión PCC R-L completa, que su convención de signo coincide con `P_ref - P_e`, que no se introduce un nuevo estado innecesario y que la medición no depende del valor aproximado empleado actualmente por el baseline grid-following.

## Estado de esta definición

La interfaz queda documentada, pero no implementada. El baseline continúa usando `GridFollowingController`; `GridFormingFrequencyDynamics` permanece aislado y la regla 12 de `AGENTS.md` sigue vigente. Cualquier modificación posterior de la firma de `compute_control`, del vector de estados o del cálculo de `v_pcc_abc` deberá realizarse en una subtarea específica, con actualización de pruebas y trazabilidad documental.
