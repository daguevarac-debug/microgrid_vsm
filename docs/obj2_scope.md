# Alcance del Objetivo 2: interfaz de señales entre planta y control GFM

## Propósito

Este documento delimita qué información de la planta eléctrica está disponible actualmente para el controlador del inversor, qué magnitudes deben calcularse o estimarse antes de integrar una estrategia grid-forming y cuál será la base arquitectónica inicial del Objetivo 2. Su alcance es documental: no activa el modo GFM, no modifica `Microgrid.system_dynamics`, no cambia el orden del vector de estados y no cierra todavía la comparación final de desempeño entre VSG clásico, FOVIC u otras variantes.

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

## Decisión sobre la base de implementación

La base de implementación del Objetivo 2 será `GridFormingFrequencyDynamics`, extendida de manera conservadora hasta conformar el controlador GFM/VSG integrado. `FOVICInverter` no se adoptará como clase base de la primera implementación. Permanecerá en el repositorio como prototipo de investigación y posible comparador posterior, sujeto a una refactorización específica antes de conectarlo a la planta completa.

La decisión no afirma que el FOVIC tenga menor desempeño dinámico. Los trabajos de Nour et al. (2023) y Yu et al. (2023) muestran que los términos de orden fraccionario pueden aportar grados de libertad adicionales, mejorar el amortiguamiento y reducir desviaciones de frecuencia frente a formulaciones convencionales en sus respectivos sistemas de prueba. Sin embargo, esos beneficios dependen de una aproximación fraccionaria, parámetros adicionales, bandas de frecuencia, orden del filtro y supuestos de planta que deben validarse para esta microrred y para el BESS de segunda vida. No es metodológicamente válido transferir directamente esas mejoras al presente modelo sin una comparación bajo iguales perturbaciones, límites de almacenamiento y criterios de desempeño.

`GridFormingFrequencyDynamics` representa explícitamente los estados mínimos `theta` y `omega` y calcula sus derivadas sin memoria oculta. Esta estructura es compatible con el esquema continuo de `solve_ivp`, con la interfaz planta-control ya documentada y con el vector actual, en el que `theta` ya existe y `omega` es el único estado dinámico GFM ausente. También permite estudiar separadamente el efecto de la inercia virtual, el amortiguamiento y las restricciones del BESS-SLB, lo cual mejora la trazabilidad de los resultados de tesis.

En contraste, `FOVICInverter` mantiene estados privados para la aproximación de Oustaloup, el bloque DC y el filtro equivalente del BESS. Con el orden predeterminado `N = 5`, la aproximación fraccionaria genera once estados, a los que se suman `x_dc` y `x_bess`. Esos trece estados se actualizan internamente mediante Euler explícito usando un `dt` suministrado por el llamador. Esta forma de memoria interna no es compatible de manera directa con una función de derivadas evaluada por un integrador adaptativo, porque el solver puede repetir o rechazar evaluaciones sin aceptar el paso correspondiente. Antes de usar FOVIC en la simulación principal, todos sus estados deberán exponerse en el vector global o el controlador deberá reformularse como subsistema discreto de paso fijo.

El estado privado `x_bess` de `FOVICInverter` representa un filtro agregado de respuesta de potencia y no sustituye los estados físicos `soc_bess`, `vrc_bess` y `zdeg_bess` del modelo Thévenin 1RC. La integración directa de ambas estructuras podría duplicar dinámicas asociadas al almacenamiento si no se define con claridad la frontera entre comando de potencia, convertidor DC/DC, batería y supervisión. Esta dificultad es especialmente relevante porque la batería es de segunda vida y la tesis debe mantener explícitos los límites de SoC, SoH, corriente y potencia disponible.

Desde el punto de vista de la tesis, comenzar con la dinámica mínima permite establecer una línea base verificable y atribuir cualquier mejora posterior a una modificación concreta. La estrategia inicial será, por tanto, un VSG clásico basado en la ecuación swing, complementado por una capa separada de supervisión del BESS-SLB. Dicha capa limitará la potencia de soporte sin ocultar las restricciones de la batería dentro del núcleo de frecuencia. Este enfoque prioriza implementación reproducible, interpretación física, menor número de parámetros y facilidad de validación frente a una estrategia fraccionaria de mayor orden.

FOVIC solo deberá avanzar a integración completa si una comparación posterior demuestra una mejora relevante frente al VSG clásico en métricas previamente definidas, como nadir de frecuencia, RoCoF, tiempo de establecimiento, oscilación de potencia y exigencia energética al BESS, y si dicha mejora justifica el aumento de estados, parámetros y complejidad numérica. En ese caso, la implementación deberá derivarse de una versión refactorizada de `FOVICInverter`, no de su memoria interna actual.

### Alcance de la decisión

La decisión adoptada es arquitectónica y metodológica:

```text
Base de primera implementación: GridFormingFrequencyDynamics
Estrategia inicial: VSG clásico con J/M y D
Protección del almacenamiento: capa supervisora separada con límites de SoC, SoH, corriente y potencia
FOVICInverter: comparador o extensión posterior, previa refactorización
```

Esta decisión no elimina la revisión futura de control droop, FOVIC u otras variantes. Tampoco fija aún los valores de `J`, `M`, `D`, `P_ref`, límites de potencia inercial ni criterios cuantitativos de sintonía.

## Criterios para la integración posterior

La implementación futura deberá mantener separadas tres responsabilidades. `HardwarePlant` conservará las ecuaciones físicas; `Microgrid` ensamblará estados y calculará mediciones algebraicas como `v_pcc_abc` y `P_e`; el controlador GFM producirá la dinámica de `theta` y `omega`, la referencia de tensión y las señales de actuación. Esta separación evita que el controlador reconstruya por su cuenta la física del filtro o de la carga.

Antes de conectar el GFM a `Microgrid.system_dynamics`, deberá verificarse que `P_e` usa la tensión PCC R-L completa, que su convención de signo coincide con `P_ref - P_e`, que no se introduce un nuevo estado innecesario y que la medición no depende del valor aproximado empleado actualmente por el baseline grid-following.

La futura implementación basada en `GridFormingFrequencyDynamics` deberá conservar la compatibilidad con `InverterControllerBase`, exponer explícitamente las derivadas de los estados GFM y mantener las restricciones del BESS fuera del núcleo swing. No se conectará `FOVICInverter` a `Microgrid.system_dynamics` mientras sus estados dinámicos permanezcan ocultos y actualizados internamente.

## Estado de esta definición

La interfaz y la base arquitectónica inicial quedan documentadas, pero no implementadas. El baseline continúa usando `GridFollowingController`; `GridFormingFrequencyDynamics` permanece aislado y la regla 12 de `AGENTS.md` sigue vigente. Cualquier modificación posterior de la firma de `compute_control`, del vector de estados, del cálculo de `v_pcc_abc` o de la integración de estados GFM deberá realizarse en una subtarea específica, con actualización de pruebas y trazabilidad documental.
