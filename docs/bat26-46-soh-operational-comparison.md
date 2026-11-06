# BAT26-46 — Comparación operacional a cuatro niveles de SoH

## Pregunta de investigación
¿Cómo cambia la variación de SoC, la reserva de carga y la respuesta GFM a igual demanda cuando el grupo equivalente de batería envejece desde el SoH inicial hasta el previsto tras 1000 ciclos sintéticos? El criterio de Roma exige 3–4 niveles, incluido el inicial del 66,8 %, y diferencias reproducibles de capacidad, SoC y energía/potencia.

## Escenarios y trazabilidad
Se escogen cuatro hitos de BAT26-45: 0, 100, 500 y 1000 ciclos. Los valores se toman de la tabla redondeada a tres decimales del documento BAT26-45, no de mediciones experimentales ni de archivos BLAST originales con precisión completa.

| Ciclos de BAT26-45 | Capacidad al inicio del caso (Ah) | SoH respecto a 66 Ah (%) |
| ---: | ---: | ---: |
| 0 | 44.100 | 66.818 |
| 100 | 42.273 | 64.050 |
| 500 | 39.038 | 59.148 |
| 1000 | 35.854 | 54.324 |

Cada estado es una condición inicial independiente; no representa la reproducción de 1000 días dentro del solver del VSG ni una segunda aplicación de pérdida de capacidad.

## Dos comparaciones complementarias
El ensayo de capacidad descarga el puerto del modelo 1RC a +8 A durante 3600 s en todos los casos, con SoC inicial igual a 0,6, iguales ecuaciones y caracterización OCV/R1/C1. La corriente está definida en el puerto equivalente del grupo 2p, no en el bus de 340 V. Se registran caída de SoC, energía terminal modelada en Wh, Ah utilizables de SoC 0,6 a 0,1, y autonomía ideal a 8 A. La diferencia algebraica anticipada es aproximadamente 18,14 puntos de SoC para 44,1 Ah y 22,31 puntos para 35,854 Ah. La simulación verificará los valores reales.

El ensayo dinámico reutiliza el validador GFM seleccionado existente, con cuatro estados de capacidad, arquitectura de 15 estados, M=80, D=1500, carga local nominal 3 kW y escalón +20 % durante 6,5 s. Debe reportar límites disponibles, respuesta de bus DC, caída de frecuencia y modo real de intercambio. No se debe presentar este ensayo como una simulación de una hora, ni como la variante externa PI de 16 estados.

Los parámetros y ecuaciones físicos no se modifican. Se conserva la convención de corriente positiva para descarga. R0(SoH) y OCV/R1/C1 siguen siendo aproximaciones no calibradas. La energía terminal en Wh no es energía medida ni potencia entregable a IEEE 33.

## Ejecución mediante Codex Cloud
Trabajar exclusivamente en feat/bat26-46-soh-operational-comparison con Python principal. BLAST original no se ejecuta de nuevo; sus cuatro valores publicados sirven como condiciones iniciales aproximadas.

~~~bash
.venv/bin/python -B -m unittest discover -s src/validation -p test_bat26_46_soh_levels.py -v
.venv/bin/python -B src/validation/run_bat26_46_soh_levels.py
~~~

Se genera una carpeta única bajo outputs/analysis/bat26_46_soh_levels/ con summary.json, comparison.csv y las figuras soc_same_current.png y available_charge_vs_cycles.png. No se deben inventar resultados antes de ejecutar; REVIEW de GFM por desempeño no significa error de software si los invariantes permanecen válidos.

## Criterio y limitaciones
Para cerrar BAT26-46 se deben revisar los cuatro niveles, verificar diferencias de SoC y capacidad, comprobar que las cuatro simulaciones GFM no violan invariantes, y describir en términos cuantitativos el efecto de SoH. La falta de calibración eléctrica 2p, convertidor DC/DC, datos experimentales y validez del envejecimiento queda reservada a BAT26-47. Las variables y el costo de desgaste para despacho corresponden a BAT26-48.

## Resultado de la ejecución (reporte Codex Cloud, 6-11-2026)

El usuario compartió el informe de ejecución de BAT26-46, basado en el commit `351eb2a2566c2aa7bc0a75d8a8cbcc89b4d8f1b9` y en las capacidades redondeadas de BAT26-45. El ejecutor compiló y la campaña concluyó con **PASS**. El archivo de tests contiene **tres métodos y los tres pasaron**; no se deben afirmar cuatro pruebas. Las cuatro simulaciones GFM también pasaron sus invariantes y criterios.

| Ciclos BAT26-45 | Qeff inicial (Ah) | SoH (%) | SoC final tras 1 h a 8 A | Ah utilizables SoC 0,6→0,1 | Autonomía ideal a 8 A (h) | Energía terminal modelada (Wh) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 44.100 | 66.818 | 0.418592 | 22.050 | 2.756 | 29.668 |
| 100 | 42.273 | 64.050 | 0.410752 | 21.137 | 2.642 | 29.650 |
| 500 | 39.038 | 59.148 | 0.395069 | 19.519 | 2.440 | 29.616 |
| 1000 | 35.854 | 54.324 | 0.376870 | 17.927 | 2.241 | 29.577 |

La caída de SoC por 8 Ah extraídos pasa de **18.141 a 22.313 puntos porcentuales**. La carga ideal disponible entre SoC 0,6 y 0,1 disminuye **4,123 Ah** (aproximadamente 18,7 %) y la autonomía ideal baja **0,515 h** (aproximadamente 18,7 %). La energía terminal estimada para una **misma transferencia de 8 Ah** cambia muy poco (29,668 a 29,577 Wh), porque el horizonte se mantiene en una hora; no es evidencia de que la energía máxima almacenable se conserve ni se debe extrapolarla al banco o al bus DC.

En las cuatro simulaciones seleccionadas GFM (M=80; D=1500; carga 3,0 kW y escalón a 3,6 kW), se reportaron **PASS** con caída máxima de frecuencia **0,002975 Hz**, desviación máxima del bus DC **0,9023 %**, corriente DC máxima absoluta **2,4009 A** y potencia DC máxima absoluta **827,82 W**, sin diferencias perceptibles entre los cuatro casos en las cifras entregadas. El BESS estuvo **absorbiendo/cargando** en todos: **no hubo descarga** y, por tanto, estos resultados **no prueban la capacidad de soporte de descarga bajo carga creciente**. Los límites de corriente disponibles disminuyeron de 44,100 a 35,854 A y los de potencia DC de aproximadamente 14,994 a 12,190 kW, pero en esta perturbación no fueron vinculantes.

La corriente de 8 A corresponde al puerto equivalente del grupo 2p usado en el ensayo aislado 1RC. La corriente de 2,4009 A y la potencia de 827,82 W corresponden a los intercambios modelados en el bus DC idealizado del ensayo GFM; **no deben convertirse ni compararse directamente sin una topología DC/DC y un mapeo físico justificado**.

Evidencia reportada por usuario desde Codex Cloud: `outputs/analysis/bat26_46_soh_levels/run_20261106T134134_370846Z/summary.json`, `comparison.csv`, `soc_same_current.png` y `available_charge_vs_cycles.png`. Las cifras provienen del informe de Codex aportado por el usuario; el resumen completo y las figuras del espacio de trabajo no se inspeccionaron directamente aquí ni están versionados automáticamente en GitHub.

**Dictamen:** BAT26-46 satisface el criterio de comparación sintética de cuatro SoH bajo demanda igual y documenta la reducción de reserva de Ah/autonomía. No demuestra un efecto visible de SoH en las métricas GFM del caso ensayado ni comportamiento físico de soporte en descarga. Ese límite deberá ser explícito en BAT26-47 y en la presentación al director; queda pendiente validar la caracterización OCV/R1/C1, R0(SoH), el grupo 2p y el convertidor DC/DC.