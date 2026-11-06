# BAT26-48 — Formulación de la interfaz SoH–SoC–envejecimiento para el despacho (Objetivo 3)

**Estado:** Diseño de contrato y metodología económica; no hay despacho óptimo implementado ni costo COP calibrado. **Límites de evidencia:** BAT26-47 confirmó consistencia numérica de BLAST/1RC, pero la validación experimental independiente permanece REVIEW / NOT_EVALUABLE.

## 1. Justificación científica y alcance

BAT26-20 identificó como solicitud principal del director relacionar degradación por uso, estado de salud SoH, estado de carga SoC y despacho. El criterio de BAT26-48 exige variables, límites y costo de degradación para un Objetivo 3 **futuro**, sin afirmar que ya exista un algoritmo optimizador ejecutado. Las publicaciones Cheng et al. (2023), Schade y Egging-Bratseth (2024), Collath et al. (2022), Lee y Kim (2022) y Nguyen et al. (2025) justifican modelar la degradación como variable de estado, restricción operativa y/o costo. Su lectura **no** suministra el precio colombiano de un BESS Nissan Leaf 2p ni acredita transferencia de sus coeficientes a este proyecto.

Esta es una **formulación propuesta por la tesis**, compatible con el software ya creado, no una transcripción de ecuaciones literales de esos autores.

## 2. Variables, referencia física y trazabilidad

El componente de almacenamiento implementado representa una **pareja Nissan Leaf 2p**, con capacidad nominal de referencia **66 Ah**. El caso de tesis ya comienza degradado, con capacidad inicial **44.1 Ah**, de modo que SoH inicial = 44.1/66 = 66.81818 %. No hay que volver a aplicar el factor original 0.7 de BLAST ni multiplicar dos leyes de degradación.

Para cada ventana lenta de envejecimiento j:

\[
r_j=\frac{q_j^{BLAST}}{q_0^{BLAST}},\qquad
Q_{eff,j}^{2p}=Q_{case}^{2p} r_j,\qquad
SoH_j=\frac{Q_{eff,j}^{2p}}{Q_{nom,ref}^{2p}}.
\]

La capacidad se congela en los pasos rápidos del sistema, y solo cambia en la frontera entre ventanas. Las referencias originales BLAST de 46 Ah y 46.2 Ah NO son los 44.1 Ah iniciales del caso de tesis.

| Dato/estado | Unidad física | Origen / regla |
| --- | --- | --- |
| Capacidad nominal de referencia | 66 Ah por pareja 2p | Caso Nissan Leaf, referencia |
| Capacidad inicial del caso | 44.1 Ah por pareja 2p | Condición de segunda vida fijada |
| Retención desde inicio de caso | fracción, 0–1 | BLAST q_j/q_0 bajo perfil sintético admitido |
| SoH | fracción = Qeff/66 | Límite operativo del escenario 0.50 |
| SoC y límites | fracción | Condición inicial; rango operativo 0.10–0.90 |
| Corriente I_bat | A del puerto 2p | Convención I positiva = descarga |
| Temperatura de celda y tiempos | °C, s | Perfil requerido por modelo de envejecimiento |
| Capacidad disponible para descargar/cargar | Ah de pareja 2p | Carga admisible, NO energía |
| Contador EFC nominal | ciclos equivalentes | Throughput Ah y denominador elegido explícitamente |
| Contador EFC BLAST | ciclos equivalentes internos | Salida de BLAST con retención; NO intercambiable |
| Límite I_bat, BMS | A del puerto 2p | Requiere identificar BMS real |
| Límites P_dis/P_ch del bus | kW de puerto DC | SIN topología ni eficiencia DC/DC verificadas |
| Energía entregable en bus | kWh | NO derivable de Ah2p×340 V |
| Costo de activo y valor residual | COP de unidad económica definida | Pendiente de valores y fuente |
| Costo marginal de pérdida | COP/Ah perdido | Proxy hipotético, no calibración |

Los snapshots redondeados de BAT26-45 fueron Qeff = **44.100, 42.273, 39.038, 35.854 Ah** a 0, 100, 500 y 1000 ciclos diarios respectivamente. Se usaron en BAT26-46 para comparar operación 1RC con corriente fija de +8 A en el **puerto de batería**; el ensayo GFM del mismo trabajo operó solo en modo de **absorción/carga** y no verificó soporte en descarga. Estos datos NO son mediciones ni convierten el 1RC en un banco eléctricamente identificado.

## 3. Restricciones matemáticas del despacho futuro

Para pasos rápidos k de duración Δt_k en horas, corriente de puerto firmada y Qeff congelada dentro de la ventana lenta j, el balance de SoC a nivel 2p es:

\[
SoC_{k+1}=SoC_k-\frac{I_{bat,k}^{2p}\,\Delta t_k[\mathrm h]}
{Q_{eff,j}^{2p}[\mathrm{Ah}]},\qquad
0.10\le SoC_k\le0.90,\qquad SoH_j\ge0.50.
\]

Es la misma relación de Coulomb que utiliza el proyecto con Δt en segundos y factor 3600. Cualquier violación del límite debe rechazarse explícitamente; no debe ocultarse mediante saturación silenciosa del estado ni un cambio ficticio de SoC al actualizar SoH.

Los límites de corriente física en una etapa posterior deben tener las formas:

\[
-I_{ch,max}^{2p}(SoC,SoH,T)\le I_{bat}^{2p}
\le I_{dis,max}^{2p}(SoC,SoH,T).
\]

Son funciones BMS aún pendientes de medir o parametrizar. El Ah disponible ideal se obtiene mediante:

\[
Q_{disponible}^{2p}=(SoC-SoC_{min})Q_{eff}^{2p}
\quad[\mathrm{Ah}].
\]

**Ah no equivale a Wh.** La energía terminal requiere integrar la tensión del 1RC frente a la corriente; la energía disponible en el bus exige número de unidades serie/paralelo, topología DC/DC, eficiencias por sentido, pérdidas y rangos de tensión. La tensión nominal del enlace DC de **340 V** NO es tensión de una pareja Nissan Leaf 2p. En el repositorio, la corriente i_bess de la ecuación del bus DC es una variable idealizada, que NO debe igualarse directamente a I_bat física de pareja 2p.

El futuro balance energético solo puede imponerse después de llevar todos los términos a **una misma frontera eléctrica**, por ejemplo:

\[
P_{PV,usada}+P_{bat,desc}+P_{red,imp}+P_{no\ servida}
=P_{demanda}+P_{bat,carga}+P_{red,exp}+P_{perdidas}.
\]

Para microrred aislada, los términos de importación/exportación externa se fijan en cero. El acoplamiento actual con IEEE 33 es secuencial y unidireccional, NO co-simulación dinámica; además, la microrred de 3 kW requiere justificar la escala de potencia antes de atribuir resultados representativos a IEEE 33.

## 4. Vida útil y dos escalas temporales

La propuesta distingue evolución rápida SoC de actualización lenta SoH. Para una corriente de puerto en A y tiempos en horas, el uso nominal se puede contabilizar como:

\[
EFC_{nom}=\frac{\sum_k |I_{bat,k}^{2p}|\,\Delta t_k}{2Q_{ref}^{2p}}.
\]

La referencia Qref es una elección expresa: usar 44.1 Ah del inicio de segunda vida o la capacidad efectiva actual produce convenciones distintas. **Auditoría BAT26-49:** el perfil BAT26-45 acumula 0.8 ciclos equivalentes de *excursión fraccional de SoC* por jornada, es decir **800 excursiones equivalentes** en 1000 días. **No debe identificarse automáticamente esta cifra con el EFC por Ah y Qref fija de la ecuación anterior**: si Qeff disminuye, también cambia el throughput físico de Ah de cada jornada. El reporte histórico denomina a los 800 «EFC nominales» y permanece intacto por reproducibilidad; los **711.452 EFC BLAST** corresponden a su contador propio. Antes del despacho se deben declarar y armonizar los tres contadores: excursión SoC, throughput Ah con referencia fija y EFC BLAST. Véase docs/bat26-49-methodology-equations.md, sección B.3.

El adaptador BLAST por ventanas conserva el estado del proceso original y, hasta validar señales físicas, **solo acepta perfiles expresamente sintéticos** de SoC, temperatura de celda y corriente de grupo 2p. El optimizador no puede llamar BLAST como si fuera una función convexa, diferenciable y calibrada de potencia AC. Un posible surrogate por tramos, entrenado y validado contra simulaciones bajo perfiles comparables, sería **desarrollo futuro**, no un resultado de BAT26-48. El modo lineal y el modo BLAST son excluyentes para actualizar la misma capacidad.

## 5. Costo de desgaste: propuesta paramétrica sin precios inventados

La función objetivo general, solo a modo de **propuesta futura**, podría combinar costos energéticos y desgaste:

\[
\min\;\sum_k\Delta t_k\left[
\pi_{imp,k}P_{imp,k}-\pi_{exp,k}P_{exp,k}
+c_{ENS,k}P_{no\ servida,k}
+c_{vert,k}P_{vertimiento,k}
\right]+C_{deg}(\mathbf u,\mathbf x;\theta).
\]

No se han identificado para esta tesis precios horarios de importación/exportación, penalización fundamentada por energía no servida, régimen de vertimiento ni frontera final del despacho. No activar términos que no correspondan al servicio seleccionado; para modo aislado las transacciones con red externa son cero.

Como **proxy de escenario económico** y no como ley de envejecimiento, una pérdida de capacidad puede valorarse proporcionalmente al costo neto asociado al rango de vida útil que se desea consumir:

\[
Q_{EOL}^{esc}=Q_{nom,ref}SoH_{min}=66(0.50)=33\;\mathrm{Ah},
\]
\[
c_{desgaste}^{esc}
=\frac{C_{activo}^{esc}-V_{residual}^{esc}}
{Q_{case}-Q_{EOL}^{esc}}\quad[\mathrm{COP/Ah}],\qquad
C_{deg}^{esc}=c_{desgaste}^{esc}\max(0,Q_{eff,j}-Q_{eff,j+1}).
\]

Para el grupo equivalente **2p** el denominador hipotético es **11.1 Ah** (44.1 menos 33). Si C_activo representa un **banco** completo, no es válido dividirlo por Ah de una **sola pareja** sin modelar la escala física; los costos deberán incluir procedencia, reposición o reacondicionamiento, depreciación, valor residual y si corresponde descuento temporal. **BAT26-48 no fija ningún importe COP.**

La expresión de costo es una **asignación económica lineal propuesta por este trabajo**, no una fórmula literal de los autores citados. No puede interpretarse como una degradación electroquímica validada ni atribuirse a BLAST. Tampoco debe cobrarse una penalización adicional por EFC sobre la **misma** pérdida de capacidad ya incluida en C_deg: sería doble contabilización. La comparación BLAST de reposo frente a ciclado no separa puramente el envejecimiento calendario y cíclico, puesto que también difieren los esfuerzos SoC.

## 6. Comparación de políticas del Objetivo 3, aún pendiente

Para aislar el efecto del costo de desgaste se propone comparar **A:** estrategia con los mismos límites físicos y SoH evolutivo, pero sin penalización monetaria de envejecimiento, frente a **B:** estrategia con iguales límites, horizontes, condiciones iniciales, demanda, FV y clima, y con costo de degradación de procedencia definida. Un control con SoH congelado puede describirse como **C**, pero no debe utilizarse para afirmar la ventaja económica del precio de desgaste si cambia simultáneamente la física de la batería.

Antes del despacho se requieren como mínimo: frontera eléctrica y modo aislado/conectado, dimensionamiento de banco y DC/DC, eficiencia y ratings, perfiles temporales representativos PV/carga, función económica y datos de precios, condiciones terminales SoC y SoH, política BMS/temperatura y modo de actualización de desgaste. BAT26-47 no validó experimentalmente OCV/R0/R1/C1 ni el efecto de degradación sobre soporte en **descarga GFM**; esas limitaciones no se pueden omitir.

## 7. Contrato de datos y pruebas de la fase

El módulo nuevo **src/validation/bat26_48_dispatch_contract.py** define un objeto inmutable AgingBoundary con capacidades nominal/inicial/actual, SoH/SoC, límites y procedencia sintética. Calcula Ah disponibles, balance ideal de Coulomb de puerto 2p y EFC nominal. Exporta un contrato versionado **BAT26-48/2p-readonly-v1**. Devuelve **null** para límites DC de potencia, corriente BMS, energía de bus y eficiencia DC/DC, y declara **BLOCKED_DC_DC_TOPOLOGY_AND_RATINGS**. La función de mapeo DC bloquea explícitamente su uso sin topología y parámetros aprobados.

El objeto EconomicScenario utiliza la relación simbólica de pérdida de capacidad únicamente para **valores etiquetados hipotéticos**; no introduce un precio comercial en el modelo. El archivo **src/validation/test_bat26_48_dispatch_contract.py** cubre siete casos: referencia inicial sin doble degradación, 1000 ciclos, signo de corriente, límites SoC, frontera bus DC bloqueada, EFC y precio de escenario sin afirmación comercial. Se ejecutaron localmente los siete con Python estándar (**7/7 PASS**, sin tocar producción); habrá que repetir en el checkout de Codex Cloud:

    .venv/bin/python -B -m unittest discover -s src/validation -p test_bat26_48_dispatch_contract.py -v

**Criterio de cierre BAT26-48:** datos/limitaciones/costo simbólico sustentados, contrato verificable y revisión del PR; **NO** exige ejecución de optimización ni costo monetario real. Continuación: BAT26-49 (metodología con citas por página), BAT26-50 (figuras/datos), BAT26-51 (dossier del director) y BAT26-52 (cierre y backlog de interfaz física/red).

## 8. Bibliografía académica verificada y alcance de uso

Las fuentes externas siguientes se contrastaron en páginas editoriales; en el caso de Schade y Collath se consultaron además apartados del texto completo. **No se han inspeccionado integralmente todas las ecuaciones y anexos de cada paper**. Por tanto, las fórmulas propuestas arriba se declaran propias del proyecto y su atribución precisa a páginas queda para BAT26-49.

**Cheng, M., Zhang, X., Ran, A., Wei, G., y Sun, H. (2023)**. *Optimal dispatch approach for second-life batteries considering degradation with online SoH estimation*. Renewable and Sustainable Energy Reviews 173, 113053. [DOI 10.1016/j.rser.2022.113053](https://doi.org/10.1016/j.rser.2022.113053). SoH variable y despacho de segunda vida, sin adopción automática de parámetros.

**Schade, C., y Egging-Bratseth, R. (2024)**. *Battery degradation: Impact on economic dispatch*. Energy Storage 6(2), e588. [DOI 10.1002/est2.588](https://doi.org/10.1002/est2.588). Degradación calendario/ciclos, SoC y sensibilidad económica de costo de reposición.

**Collath, N., Tepe, B., Englberger, S., Jossen, A., y Hesse, H. (2022)**. *Aging aware operation of lithium-ion battery energy storage systems: A review*. Journal of Energy Storage 55, 105634. [DOI 10.1016/j.est.2022.105634](https://doi.org/10.1016/j.est.2022.105634). Requisitos de estresores relevantes, rango validado, computación y métodos en restricciones/objetivo.

**Lee, J.-O., y Kim, Y.-S. (2022)**. *Novel battery degradation cost formulation for optimal scheduling of battery energy storage systems*. International Journal of Electrical Power & Energy Systems 137, 107795. [DOI 10.1016/j.ijepes.2021.107795](https://doi.org/10.1016/j.ijepes.2021.107795). Desgaste/costo con conteo de ciclos para programación.

**Nguyen, M. Q., Nguyen, L. D., y Pham, N. T. (2025)**. *Economic Scheduling of Microgrids With a bi-Level Model Considering Battery Aging*. Energy Storage 7(3), e70166. [DOI 10.1002/est2.70166](https://doi.org/10.1002/est2.70166). Costo de envejecimiento calendario/cíclico y programación de microredes; sin extrapolar ahorros publicados.

**Wang, S., Guo, D., Han, X., Lu, L., Sun, K., Li, W., Sauer, D. U., y Ouyang, M. (2020)**. *Impact of battery degradation models on energy management of a grid-connected DC microgrid*. Energy, artículo 118228. [DOI 10.1016/j.energy.2020.118228](https://doi.org/10.1016/j.energy.2020.118228). Importancia de elegir modelo de envejecimiento apropiado al despacho.

**Zhuang, J., Bach, A., van Vlijmen, B. H. C., Reichelstein, S. J., Chueh, W., Onori, S., y Benson, S. M. (2025)**. *Technoeconomic decision support for second-life batteries*. Applied Energy, artículo 125800. [DOI 10.1016/j.apenergy.2025.125800](https://doi.org/10.1016/j.apenergy.2025.125800). Marcos técnico-económicos para usos de segunda vida; no precio del grupo 2p colombiano.

**Material ya suministrado:** Braco (2020, 2021, 2023) como evidencia experimental Leaf y Tran (2021) como metodología ECM en química LFP diferente. Auditorías propias de GitHub **docs/bat26-35-ecm-parameter-evidence.md**, **docs/bat26-38-validation-test-plan.md** y **docs/bat26-47-validity-sensitivity-audit.md**, con sus límites físicos y numéricos explícitos.


## Confirmación de pruebas y alcance de cierre (6 de noviembre de 2026)

Codex Cloud informó que las **7/7 pruebas de contrato** ejecutadas en el checkout del PR #44 concluyeron con PASS, sin modificar ecuaciones de planta, BLAST, controladores, costos ni fuentes. Se verificaron las convenciones de corriente de la pareja 2p frente al bus DC, el balance SoC con Qeff congelada, la ausencia de doble aplicación del SoH inicial, la diferenciación de EFC nominal respecto a BLAST, el rechazo de límites inválidos y el bloqueo explícito de campos de potencia/energía DC hasta definir la interfaz física.

El usuario comunicó asimismo que los DOI citados resuelven a publicaciones pertinentes. Esta revisión bibliográfica **corrobora la motivación conceptual**, no implica lectura de todos los anexos ni verificación de las ecuaciones originales página por página; por tanto, estas se preservan como **propuestas de la tesis**. El precio en COP, la topología real de banco/DC/DC, los parámetros BMS/eficiencia, el dimensionamiento en IEEE 33 y la validación experimental permanecen abiertos. **BAT26-48 se cierra como especificación de interfaz, no como implementación de optimización económica o despacho físico.**

La evidencia numérica es el reporte de Codex Cloud facilitado por el usuario; no se adjuntaron logs del checkout a este repositorio. BAT26-49 revisará las páginas de fuentes primarias, las ecuaciones, las unidades y los supuestos antes de preparar el dossier del director.
