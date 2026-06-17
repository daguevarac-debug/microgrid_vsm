# Texto de tesis: cierre de la Actividad 2.1 y decisión sobre FOVIC

## Ubicación en el documento

Insertar como subsección `1.3.1`, al final de `1.3 Modelo del inversor grid-forming` y antes de `1.4 Modelo del banco de baterías de segunda vida`.

## 1.3.1 Criterio de cierre de la Actividad 2.1 y decisión sobre FOVIC

Como criterio de cierre de la Actividad 2.1 se adoptó, para la primera integración del inversor grid-forming, una estrategia VSG clásica basada en la ecuación swing reducida. La formulación conserva como estados dinámicos la frecuencia angular ω y el ángulo eléctrico θ, integrados junto con los estados de la planta mediante un único solucionador temporal. En el vector del modo GFM, ω ocupa la posición previamente asignada al integrador del control grid-following, mientras θ mantiene su ubicación. Esta diferenciación preserva el baseline: cuando se emplea el controlador grid-following, la frecuencia permanece fija en ω_ref y el estado asociado al regulador del enlace DC no se reinterpreta.

```text
dθ/dt = ω

dω/dt = [P_ref,eff - P_e - D_ω(ω - ω_ref)] / M_ω
```

La actividad se considera cerrada porque la dinámica angular quedó conectada al camino principal del modelo, el controlador conserva una interfaz común con la planta y las condiciones iniciales distinguen de forma explícita los modos grid-following y grid-forming. Además, se verificó la ausencia de regresiones en el baseline mediante las pruebas unitarias disponibles, la ejecución del caso principal y los escenarios aislados nominal, escalón de carga del 20 %, cambio abrupto del 40 % y comparación preliminar sin y con BESS. Estos resultados constituyen la línea base pre-GFM para las comparaciones posteriores.

La decisión final fue no incorporar el término fraccionario FOVIC en esta primera versión. La implementación existente del bloque FOVIC mantiene estados internos para la aproximación de Oustaloup, el bloque DC y el filtro equivalente del BESS, y los actualiza mediante Euler explícito con un paso temporal externo. Esta estructura no es compatible de forma directa con un integrador adaptativo, que puede repetir o rechazar evaluaciones, ni con el contrato empleado por el controlador GFM. Su conexión inmediata introduciría memoria oculta y podría duplicar dinámicas asociadas al almacenamiento.

FOVIC se conserva como extensión comparativa futura. Antes de integrarlo, sus estados deberán exponerse en el vector global y formularse mediante una función de derivadas sin efectos secundarios, integrada por el mismo solucionador de la planta. La potencia auxiliar fraccionaria deberá limitarse según SoC, SoH, corriente y potencia disponible del BESS-SLB. Solo se justificará su adopción si una comparación bajo perturbaciones equivalentes demuestra mejoras medibles en nadir de frecuencia, RoCoF, tiempo de establecimiento u oscilación de potencia frente al VSG clásico. En consecuencia, la Actividad 2.1 se cierra con el VSG clásico como estrategia implementada y FOVIC como línea de trabajo posterior.

## Registro de edición del PDF

El texto se incorporó en una página nueva identificada como `15A`, situada entre la página impresa 15 de la sección 1.3 y la página impresa 16 donde comienza la sección 1.4. Esta inserción evita alterar el contenido y la numeración existente del avance de tesis mientras no se disponga del archivo Word maestro.
