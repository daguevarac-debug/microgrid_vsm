# BAT26-51 — Dossier técnico para reunión con el director de tesis

**Documento de trabajo para revisión.** Fecha de consolidación: 6 de noviembre de 2026. Proyecto: microrred fotovoltaica con BESS de segunda vida y control formador de red (VSG). Alcance: estado de resultados disponibles y decisiones que requieren orientación del director en un horizonte de preparación de aproximadamente 8–15 días. **No se presenta como tesis terminada, validación experimental de baterías ni despacho óptimo ejecutado.**

**Fuentes internas principales.** BAT26-38 (plan de validación), BAT26-43 y BAT26-44 (contrato y comparación GFM/BESS), BAT26-45 (envejecimiento a 1000 días), BAT26-46 (contraste SoH/SoC y límites), BAT26-47 (sensibilidad), BAT26-48 (interfaz con despacho), BAT26-49 (ecuaciones y matriz de fuentes) y BAT26-50 (seis figuras reproducibles). En las cifras de resultados se utilizan **informes comunicados por Codex Cloud**; los datos completos de origen y el manifiesto BAT26-50 no se han incorporado aún como binarios versionados a GitHub.

## Resumen ejecutivo

La pregunta que guía este bloque es cómo la pérdida progresiva de capacidad de una batería reutilizada puede modificar su estado de carga y la reserva de energía para operación de una microrred fotovoltaica, y cómo trasladar esas restricciones a un despacho que valore el desgaste. Se implementó un modelo eléctrico Thevenin 1RC para una **pareja de celdas Nissan Leaf en paralelo (2p)** y se incorporó una ruta de envejecimiento por ventanas mediante BLAST-Lite nativo verificado. El estado inicial del caso de segunda vida es **44.1 Ah** respecto a la referencia nominal **66 Ah**, equivalente a **66.81818 % de SoH**. Estos valores son **parámetros del escenario**, no la medición de una pareja identificada.

Bajo un perfil de SoC diario sintético a **25 °C**, BLAST-Lite proyectó a los **1000 días** una capacidad de **35.853796 Ah** y un **SoH de 54.323934 %**, sin alcanzar el piso operativo de escenario del 50 %. La retención relativa al inicio de la segunda vida es aproximadamente 81.30 %, pero el SoH absoluto se refiere a 66 Ah. El contador de BLAST fue **711.451843 EFC**, mientras la suma de excursiones equivalentes fraccionales de SoC resultó **800**. Son convenciones diferentes, que se explican en la metodología BAT26-49 y se visualizan separadamente en BAT26-50.

En una comparación de cuatro estados independientes de envejecimiento, una **descarga del puerto 2p de +8 A durante una hora**, comenzando desde SoC = 0.6, ocasionó un SoC final de **0.418592** con Qeff=44.1 Ah y **0.376870** con Qeff=35.854 Ah. La reserva de carga ideal desde SoC=0.6 hasta 0.1 se redujo de **22.050 a 17.927 Ah** (≈18.7 %). Este resultado evidencia el efecto operacional de la pérdida de capacidad **en el puerto de batería**, pero no puede interpretarse directamente como energía del bus DC ni del sistema IEEE 33.

La respuesta dinámica rápida del GFM se simuló en su arquitectura aprobada de 15 estados, con **M=80, D=1500**, demanda local **3.0 kW** y escalón de **+20 %**. Los cuatro estados de capacidad superaron los criterios de la campaña y reportaron una desviación máxima de **Vdc de 0.9023 %** y caída de frecuencia de **0.002975 Hz**; sin embargo, el BESS estuvo **absorbiendo energía en todos los casos**. En consecuencia, esta prueba no demuestra aún cómo cambia el **soporte de descarga** del GFM cuando la batería está más envejecida. La carga local y el acoplamiento secuencial con IEEE 33 tampoco constituyen un modelo dinámico bidireccional de toda la red.

El bloque de validación se encuentra en **PASS de implementación numérica y REVIEW de validez física**. Los datos experimentales de una misma pareja Leaf 2p con pruebas independientes de capacidad, temperatura, corriente y voltaje no han sido identificados/recuperados de forma suficiente para cuantificar error de predicción; OCV/R0/R1/C1 y la ruta DC/DC/banco no están calibradas. **No** se calculan RMSE físicos ni se proyecta vida de campo validada.

## Pregunta, contribución y método aplicado

La hipótesis de trabajo, **aún no verificada experimentalmente**, es que una disminución de Qeff modifica la dinámica de SoC y los límites de operación del BESS y, por ello, puede influir en la programación de carga y descarga. Se adopta una separación temporal: la planta rápida mantiene Qeff constante durante una ventana, mientras BLAST acumula deterioro y devuelve un nuevo factor de retención en su frontera.

La relación de transferencia implementada es:

$$
Q_{\mathrm{eff},j}=44.1\,\mathrm{Ah}\;\frac{q_j^{BLAST}}{q_0^{BLAST}},\qquad SoH_j=\frac{Q_{\mathrm{eff},j}}{66\,\mathrm{Ah}}.
$$

El estado de carga bajo corriente firmada del puerto 2p cumple, con tiempo en segundos:

$$
\frac{dSoC}{dt}=-\frac{I_{\mathrm{bat}}^{2p}}{3600Q_{\mathrm{eff}}^{2p}},\qquad I_{\mathrm{bat}}^{2p}>0\;\text{descarga}.
$$

La tensión terminal del 1RC es una estructura Thevenin compatible con Tran et al. (2021), Ec. (1), PDF p. 4:

$$
V_t=OCV(SoC)-I_{\mathrm{bat}}R_0(SoH)-V_{RC},
\qquad
\frac{dV_{RC}}{dt}=-\frac{V_{RC}}{R_1C_1}+\frac{I_{\mathrm{bat}}}{C_1}.
$$

La ODE RC es la forma continua asociada a la actualización discreta de Tran, no una ecuación literalmente copiada. La química y escala del estudio Tran (LFP 20 Ah) difieren de la pareja Leaf 2p. El mapa R0(SoH), las tablas actuales OCV/R1/C1 y el coeficiente k_R siguen siendo provisionales; la resistencia DC a 10 segundos de Braco (2023) **no equivale** a R0 instantánea.

## Resultados cuantitativos sintetizados

| Indicador | Inicio/caso base | Resultado final y comparación | Alcance |
| --- | ---: | ---: | --- |
| Capacidad del grupo 2p | 44.100 Ah | 35.853796 Ah, 1000 días | Envejecimiento sintético BAT26-45 |
| SoH respecto a 66 Ah | 66.81818 % | 54.323934 % | Reducción ≈12.494 puntos porcentuales |
| Capacidad de referencia calendario | 44.100 Ah | ≈39.879 Ah tras 1000 días | Reposo con esfuerzo SoC distinto; no aislamiento de mecanismo |
| Contador de uso geométrico | 0 | 800 excursiones equivalentes SoC | No equivale necesariamente a EFC Ah fijo |
| EFC original BLAST | 0 | 711.451843 | Contador del modelo, no ciclos de campo |
| SoC con +8 A durante una hora | 0.6 inicial | 0.418592 (sin desgaste adicional) vs 0.376870 (1000 días previos) | Comparación 1RC con cuatro condiciones iniciales |
| Reserva de carga SoC 0.6 a 0.1 | 22.050 Ah | 17.927 Ah | Ah ideales, no Wh de bus |
| Energía terminal transferida +8 A/1h | 29.668 Wh | 29.577 Wh | Mismo throughput en una hora; NO energía total máxima |
| Respuesta GFM 3→3.6 kW | M=80, D=1500 | Vdc max 0.9023 %, caída f max 0.002975 Hz | Todos los casos absorbieron/cargaron |
| Partición BLAST 100 días | 1 ventana: SoH=64.049385 % | 2 ventanas: 64.038716 %; 4: 64.041229 % | Sensibilidad sin tolerancia de convergencia |
| Sensibilidad 1RC a paso solver | 15 s referencia | Máx. ΔSoC=1.67×10⁻¹³ puntos; ΔE=3.96×10⁻⁸ Wh | Solo consistencia numérica del escenario |
| BAT26-48 | Contrato SoH/SoC, EFC, proxy económico | 7/7 tests PASS | Sin DC/DC real ni optimizador de despacho |

**No se suman las pérdidas \`qLoss_t\` y \`qLoss_EFC\` para reclamar una separación experimental pura**; corresponden a los estados del BLAST original bajo protocolos específicos. La diferencia reposo/ciclado no es un experimento con la única variable «ciclado» aislada.

## Seis figuras previstas para la reunión y lectura recomendada

| Figura de BAT26-50 | Interpretación defendible | Advertencia de presentación |
| --- | --- | --- |
| Fig. 1 — SoH vs EFC BLAST | Tendencia de envejecimiento del escenario sintético | Sin extrapolación a vida útil certificada |
| Fig. 2 — Tres contadores EFC | Distingue excursiones SoC (800), throughput normalizado y BLAST (711.451843) | Los últimos dos coinciden numéricamente y sus líneas se superponen; NO son equivalentes universales |
| Fig. 3 — Qeff vs días | Contraste de pérdida de capacidad por dos protocolos sintéticos | No atribuir toda la diferencia a envejecimiento cíclico puro |
| Fig. 4 — SoC(t) a +8 A | Más caída de SoC con Qeff menor a igual corriente de puerto | No equiparar los +8 A con corriente de bus DC |
| Fig. 5 — Ah utilizables | Menor reserva de carga disponible entre dos límites SoC | Carga ideal en Ah, no energía Wh |
| Fig. 6 — Wh terminales | Energía terminal transferida durante **igual hora y corriente** | El rango 29.668 a 29.577 Wh es solo ≈0.31 %, con eje vertical ampliado |

Los seis PNG fueron mostrados por el estudiante y revisados visualmente en la conversación. Codex Cloud confirmó la presencia de las fuentes BAT26-45/46 y verificó los **hashes SHA-256 de los cinco archivos de origen, las seis figuras y \`checkpoints.csv\`** frente a \`manifest.json\`; todos coincidieron según el reporte recibido. El paquete de resultados original está disponible en el workspace de Codex Cloud. Esta verificación procede del informe de Codex comunicado por el estudiante; el ZIP y sus archivos no fueron descargados ni recalculados directamente desde esta revisión. Directorio original informado:

\`outputs/analysis/bat26_50_figures/run_20261106T153947_125249Z/\`

Codex Cloud **ya creó un ZIP portátil**, que contiene las seis figuras PNG, \`checkpoints.csv\` y \`manifest.json\`, sin alterar sus fuentes. Ruta comunicada: \`outputs/analysis/bat26_51_director_dossier/BAT26-50_figures_portable.zip\`. El archivo ZIP fue reportado con SHA-256 \`ef3ca61c27c5e73bb275e67e5782071f6a5239faee09c208ffa14c72eccbd6d3\`. Para la reunión se debe **conservar y compartir el ZIP existente**, además de mantener trazabilidad con el generador y criterios versionados en GitHub. El ZIP todavía no está incorporado como archivo binario al repositorio.

## Interfaz con el Objetivo 3: listo y no listo

BAT26-48 definió un contrato de entrada con SoC, SoH, Qeff, capacidad utilizable en Ah y estados de envejecimiento, validado con siete pruebas de software. El contrato prohíbe asignar valores de potencia o energía a la salida del banco DC sin topología física y eficiencia identificadas. La ecuación del bus Vdc=340 V y \`i_bess\` del GFM idealizado no son iguales a Vt e I_bat de la pareja 2p.

Como **propuesta económica únicamente**, el costo del desgaste se escribiría:

$$
C_{\mathrm{deg}}^{esc}
=\frac{C_{\mathrm{activo}}^{esc}-V_{\mathrm{residual}}^{esc}}
{Q_{\mathrm{case}}-Q_{\mathrm{EOL}}}
\max(0,Q_{\mathrm{eff},j}-Q_{\mathrm{eff},j+1}).
$$

En el escenario actual Q_EOL=66·0.5=33 Ah (pareja 2p), pero **no se ha definido un costo real del activo en COP, su valor residual ni un banco cuya magnitud coincida con la del denominador**. Esta fórmula es una **asignación hipotética propuesta por el trabajo**, no un coeficiente de BLAST ni una ecuación literalmente tomada de Cheng, Schade o Lee y Kim. No se ha implementado ni ejecutado un optimizador.

La comparación futura debería usar la misma física, condiciones iniciales, restricciones y perfiles de FV/carga, contrastando una política sin penalización monetaria de desgaste y otra con penalización documentada. El modelo de envejecimiento debe contabilizar calendario y ciclo sin doble penalización por la misma pérdida ΔQ. Se requiere elegir el horizonte temporal y la condición terminal del SoC antes de decidir que una política «ahorra».

## Decisiones concretas solicitadas al director

**Primera decisión — núcleo científico.** Confirmar si es aceptable presentar BAT26-45 como **estudio de escenario sintético** para demostrar el acoplamiento SoH–SoC y reservar la validación física para trabajo posterior, o si se exige adquirir una base experimental Leaf 2p antes de avanzar a una propuesta cuantitativa de despacho.

**Segunda decisión — escala eléctrica.** Determinar si el objetivo se centrará en el **grupo equivalente 2p** y un control local de 3 kW, o en diseñar un **banco dimensionado** mediante número serie/paralelo, electrónica DC/DC y pérdidas para una potencia asignada. Sin este acuerdo, no es defendible convertir Qeff 2p en energía de red.

**Tercera decisión — controlador.** Ratificar el alcance del VSG clásico M=80 y D=1500 como configuración de referencia, justificar sus unidades/escala físicas y decidir si la variante de 16 estados con PI externo y/o el FOVIC final son prioritarios antes de estudiar el despacho. El hecho de que BAT26-46 no registrara soporte de descarga exige evaluar un escenario de demanda compatible con descarga real.

**Cuarta decisión — despacho y economía.** Escoger la frontera eléctrica (puerto DC, PCC o red agregada), horizonte, perfiles de demanda/FV, condición terminal del SoC, modo aislado o conectado y datos de precio o función de desgaste justificables. No existe todavía costo COP ni función objetivo calibrada.

**Quinta decisión — experimento y métrica.** Priorizar una misma pareja Leaf 2p identificada con RPT repetidos, I/V/T, HPPC y datos de calibración/validación independientes, o delimitar formalmente el estudio como simulación. Para IEEE 33, documentar un escenario de potencia representativo y evitar presentar el posprocesamiento secuencial existente como co-simulación bidireccional.

## Propuesta de preparación de la reunión en 8–15 días

Los primeros días se dedican a **consolidar el paquete persistente de evidencia BAT26-50**, verificar la fuente y la identidad de cada figura, y seleccionar las cuatro o seis figuras de la reunión. Después se realizará una lectura crítica de la matriz bibliográfica BAT26-49, prestando especial atención a Braco 2020/2021/2023 y Tran 2021; estas fuentes respaldan la estructura y la caracterización de referencia, pero **no** validan nuestros coeficientes 1RC. La fase final de preparación consistirá en redactar una exposición breve centrada en la relación SoH→Qeff→SoC→disponibilidad, mostrar explícitamente qué está demostrado y llevar las cinco decisiones anteriores por escrito. Este documento no fija una cita con el director ni promete un resultado optimizado dentro de ese intervalo.

## Bibliografía mínima y procedencia

**Braco et al. (2020)**, DOI 10.1016/j.est.2020.101695, PDF del estudiante pp. 2–4 y 6: Nissan Leaf segunda vida, 2s2p, protocolo de capacidad/SoH y envejecimiento. **Braco et al. (2023)**, DOI 10.1016/j.apenergy.2022.120235, PDF pp. 4–5: unidad 2p y Tabla 1, diferencia entre resistencia DC de pulso y R0 instantánea. **Tran et al. (2021)**, DOI 10.1016/j.est.2021.103252, PDF p. 4, Ecs. (1)–(2): estructura Thevenin 1RC, con muestras LFP 20 Ah que requieren recalibración para Leaf. **Cheng et al. (2023)**, DOI 10.1016/j.rser.2022.113053: despacho de segunda vida con SoH variable. **Collath et al. (2022)**, DOI 10.1016/j.est.2022.105634: revisión de programación consciente del envejecimiento. **Schade y Egging-Bratseth (2024)**, DOI 10.1002/est2.588, §4.2 HTML: mecanismos de desgaste y valoración económica. La matriz de afirmaciones y límites exactos está en \`docs/bat26-49-source-evidence-matrix.md\`; para artículos económicos sin PDF examinado se citan DOI/secciones editoriales, **no páginas inventadas**.

**Estado de preparación:** el cotejo documental con BAT26-45 a 50, la verificación de hashes por Codex y la creación del ZIP portátil fueron **reportados como completados**. Se han conservado las limitaciones metodológicas. Este documento puede cerrarse como dossier académico; para la exposición permanece la decisión editorial de seleccionar las figuras que verá el director. El ZIP y los PNG no están versionados como binarios en GitHub; conservar su copia fuera del entorno temporal de Codex.
