# Criterio formal de cierre del Objetivo 1

## Propósito del documento

Este documento define el criterio de terminado del Objetivo 1 en el alcance
baseline actual de la tesis. El Objetivo 1 se considera cerrado cuando existe un
modelo eléctrico y dinámico trazable de la microrred fotovoltaica aislada con
BESS-SLB, degradación y restricciones operativas, junto con evidencia de
validación práctica interna coherente con el estado implementado del repositorio.

El cierre aquí descrito no equivale a validación experimental completa, diseño
óptimo final ni integración definitiva de una estrategia grid-forming/VSG/FOVIC.
Su función es delimitar qué queda suficientemente desarrollado para habilitar el
Objetivo 2 y qué permanece como trabajo posterior.

## Qué significa "modelo desarrollado"

En este repositorio, "modelo desarrollado" significa que existe una
representación físico-matemática e implementada, con trazabilidad documental, de
los componentes principales requeridos para el baseline de una microrred PV +
BESS-SLB:

- modelo fotovoltaico;
- bus DC;
- inversor/fuente y control baseline grid-following;
- filtro LCL;
- carga agregada trifásica balanceada R-L;
- modelo BESS-SLB Thevenin 1RC con degradación de primer orden;
- restricciones operativas del almacenamiento, incluyendo SoC, corriente,
  potencia y disponibilidad dependiente de SoH;
- integración preliminar BESS-DC-link mediante `MicrogridWithBESS`;
- estructura mínima GFM aislada con estados `theta` y `omega`;
- interfaz planta-control documentada para la transición al Objetivo 2.

El término "desarrollado" no significa que ya estén completos el controlador
GFM/VSG final, la estrategia FOVIC, el BMS final, el convertidor DC/DC detallado
ni el diseño óptimo definitivo de parámetros de control. Tampoco implica que el
bloque GFM aislado reemplace el baseline grid-following del modelo principal.

## Qué significa "modelo validado"

En este contexto, "modelo validado" significa validación baseline, práctica e
interna del modelo implementado. La validación se interpreta como evidencia de
coherencia técnica suficiente para continuar la tesis, no como demostración
experimental final ni como prueba formal definitiva de estabilidad y control.

La validación baseline incluye:

- revisión de consistencia de ecuaciones implementadas;
- coherencia dimensional y de unidades;
- verificación de signos y convenciones de potencia, corriente y tensión;
- revisión de restricciones operativas del BESS-SLB;
- comparación con referencias técnicas, datasheets o curvas externas cuando
  aplica;
- ejecución documentada de scripts de validación existentes en `src/validation/`;
- métricas y figuras reportadas en `outputs/validation/`.

Por tanto, el modelo puede considerarse validado en sentido baseline/práctico
para la Actividad 1.3, pero no debe presentarse como validado experimentalmente
ni como una validación formal final de la estrategia GFM/VSG/FOVIC.

## Qué evidencia lo respalda

La evidencia documental y técnica que respalda el cierre del Objetivo 1 es:

- `README.md`: resume el estado del repositorio, el alcance implementado, las
  validaciones disponibles y las limitaciones vigentes.
- `docs/model_assumptions.md`: documenta supuestos, alcance de validez y
  limitaciones del baseline.
- `docs/grid_forming_minimal_structure.md`: define la estructura matemática
  mínima del bloque GFM aislado.
- `docs/grid_forming_plant_control_interface.md`: documenta la interfaz
  planta-control y las variables necesarias para el Objetivo 2.
- `src/validation/`: contiene los scripts de validación internos del baseline.
- `outputs/validation/`: contiene salidas, métricas y figuras generadas por las
  validaciones documentadas.

Según el estado documentado en `README.md`, la evidencia técnica incluye:

- validación STC del modelo fotovoltaico contra datasheet;
- validaciones BESS Step-2 para dinámica Thevenin 1RC;
- validaciones BESS Step-3 para degradación `z_deg`, SoH, capacidad efectiva y
  resistencia;
- comparaciones externas Braco Fig. 5(b) para SL 0.5C, 1C y 1.5C;
- validaciones de intercambio de potencia BESS-DC-link, unidades, escalas,
  límites de SoC/corriente/potencia y escenarios de SoH;
- validaciones prácticas del filtro LCL;
- validación de carga R-L agregada y escenarios aislados consolidados;
- validaciones mínimas aisladas del bloque GFM, sin acoplarlo al modelo
  principal `Microgrid`.

La comparación sin BESS vs. con BESS preliminar y los escenarios de SoH se
consideran evidencia diagnóstica de baseline. No constituyen prueba final de
soporte dinámico, ni validación de un BMS final, ni validación de una estrategia
VSG/FOVIC integrada.

## Qué queda fuera del objetivo

Quedan fuera del cierre del Objetivo 1:

- diseño final de la estrategia VSG/FOVIC;
- implementación final del controlador de inercia virtual;
- integración completa del GFM con la planta PV + BESS + bus DC + LCL + PCC;
- BMS final y lógica completa de gestión del almacenamiento;
- convertidor DC/DC detallado para el BESS;
- validación experimental con datos medidos;
- perfiles reales medidos de demanda;
- modelo ZIP completo, cargas no lineales o desbalanceadas;
- optimización final de parámetros de control;
- comparación final contra estrategias droop o V-f;
- validación formal definitiva de estabilidad del controlador.

Estos elementos pertenecen al trabajo futuro de la tesis, especialmente al
Objetivo 2 y a etapas posteriores de integración y validación formal.

## Qué habilita formalmente el Objetivo 2

El cierre del Objetivo 1 habilita formalmente el Objetivo 2 porque deja
disponible una planta baseline documentada y una interfaz explícita entre planta,
controlador y BESS/BMS. En particular, quedan establecidos:

- una planta eléctrica baseline con PV, bus DC, inversor, LCL, carga y BESS-SLB;
- estados y señales relevantes para la transición a control grid-forming;
- variables observables y manipulables identificadas;
- restricciones operativas del BESS trazadas mediante SoC, SoH, corriente y
  potencia disponible;
- supuestos y advertencias de alcance documentados;
- una estructura mínima GFM aislada que sirve como base, sin presentarse como
  controlador final;
- una interfaz planta-control preparada para formular y evaluar la estrategia
  VSG/FOVIC en una etapa posterior.

Con esto, el Objetivo 2 puede iniciar de forma trazable la tarea de "Determinar
la estrategia de control de inercia virtual del inversor grid-forming con el
sistema de gestión de baterías de segunda vida". En ese objetivo deberán
formularse la estructura completa VSG/FOVIC, la incorporación de límites y estados
del BESS/BMS, y la sintonía de parámetros como `H`, `D`, el orden fraccionario
`alpha` y otros criterios dinámicos. Estas decisiones no quedan cerradas por el
Objetivo 1.
