# BAT26-50 — Figuras y datos reproducibles para la revisión del director

**Criterio Roma:** SoH vs EFC, SoC vs tiempo, capacidad/energía, código y configuración de figuras; depende de BAT26-45 a 47. **No se elaboran gráficas científicas con valores reconstruidos de tablas redondeadas ni se presenta una ilustración generada por IA como evidencia.**

## Datos fuente obligatorios

Se requieren las carpetas *originales* de la ejecución de Codex Cloud. BAT26-45 debe aportar el historial diario de **1001 filas para días 0 a 1000**, no solo las cuatro filas de checkpoints. BAT26-46 debe aportar sus cuatro escenarios de 1 h al puerto de grupo 2p con corriente de descarga +8 A, junto con el PNG de la trayectoria completa de SoC que ya generó su solver.

| Campaña | Archivo(s) requerido(s) | Identificación reportada por Codex |
| --- | --- | --- |
| BAT26-45, 1000 días | summary.json, cycle_history.csv | outputs/analysis/bat26_45_multicycle/run_20261105T211126_668639Z/ |
| BAT26-46, cuatro SoH | summary.json, comparison.csv, soc_same_current.png | outputs/analysis/bat26_46_soh_levels/run_20261106T134134_370846Z/ |

Las rutas anteriores describen el espacio de trabajo original de Codex Cloud, **no** rutas versionadas en GitHub. Si esos archivos no están disponibles, se debe **parar con diagnóstico explícito**; no interpolar una trayectoria de 1000 días a partir de 0/100/500/1000, ni inventar valores intermedios de SoC. Si se han perdido, solo el ejecutor original con BLAST/Python auditados y las condiciones históricas puede regenerarlos.

## Construcción reproducible

El script src/validation/build_bat26_50_figures.py lee los cuatro CSV/JSON originales y copia, sin alterar píxeles, el PNG SoC(t) que generó BAT26-46. Comprueba que los summaries son PASS y corresponden al mismo nombre de tarea; que el historial de BAT26-45 incluye los 1001 días sin huecos; que SoH y Qeff son finitos y monótonos según su simulación; que EFC/throughput no retroceden; que los valores finales concuerdan exactamente con summary.json; que los cuatro checkpoints de BAT26-46 corresponden a 0/100/500/1000 días y a 8 A; y que sus capacidades proceden de BAT26-45 redondeadas a tres decimales dentro de 0.00051 Ah.

Produce seis figuras a 180 dpi. **Fig. 1:** SoH ciclado contra EFC **interno BLAST**, sin asignar erróneamente EFC al escenario calendario. **Fig. 2:** tres contadores separados contra días: excursiones equivalentes de SoC (800 tras 1000), throughput sintético en Ah normalizado a Q_ref=44.1 Ah y efc interno BLAST (711.452). **Fig. 3:** Qeff ciclado frente a referencia de calendario, ambos en Ah contra días; no interpreta la diferencia como mecanismo cíclico puro. **Fig. 4:** archivo SoC(t) de BAT26-46, reproducible por el ejecutor de esa tarea y copiado exactamente con hash para evitar inventar líneas temporales desde un resumen de extremos. **Fig. 5:** carga ideal disponible [Ah] entre SoC 0.6 y 0.1 tras distintos hitos. **Fig. 6:** Wh de **energía terminal transferida** durante una hora a +8 A, no energía máxima del BESS ni energía entregada al bus.

El paquete incluye checkpoints.csv con valores **no redondeados de BAT26-45** cuando el CSV original los contiene, los indicadores de BAT26-46 y manifest.json con hashes SHA-256 de todos los datos de entrada, figuras, CSV procesado, versión Python/Matplotlib, commit de Git y limitaciones. No sobrescribe las campañas de origen.

**Ejecutar en Codex Cloud usando Python principal**, en la rama feat/bat26-50-reproducible-figures:

~~~bash
.venv/bin/python -B -m unittest discover -s src/validation -p test_bat26_50_figure_contract.py -v
.venv/bin/python -B src/validation/build_bat26_50_figures.py \
  --bat45-dir outputs/analysis/bat26_45_multicycle/run_20261105T211126_668639Z \
  --bat46-dir outputs/analysis/bat26_46_soh_levels/run_20261106T134134_370846Z
~~~

Si la ruta anterior no existe, localizar los directorios originales efectivamente creados, verificar su summary.json y suministrarlos explícitamente; no elegir por nombre una ejecución fallida o de 100 ciclos. No se requiere volver a ejecutar BLAST para construir las figuras a partir de sus datos ya disponibles.

## Revisión científica de las figuras

No debe mezclarse la corriente +8 A del **puerto de pareja 2p** con i_bess del **bus DC idealizado**. SoH y Qeff de BAT26-45 resultan de perfiles SoC y temperatura sintéticos; no corresponden a degradación medida. La energía BAT26-46 es **energía entregada al puerto terminal en una hora de descarga fijada**, NO capacidad energética total ni potencia a IEEE33.

**Auditoría de etiquetas:** el eje de 800 excursiones equivalentes de SoC antes llamado «EFC nominal» no es automáticamente EFC por throughput con Q_ref constante; la figura comparativa presenta las tres definiciones sin fusionarlas. El resultado envejecimiento solo puede describirse para el perfil simulado. La referencia de SoC en reposo también implica esfuerzo calendario diferente. El GFM de BAT26-46 estuvo en modo de carga y no demostró soporte en descarga.

## Cierre y evidencia pendiente

Para cerrar BAT26-50 se requieren **seis figuras reales, una tabla y un manifiesto** generados satisfactoriamente por Codex, una inspección visual para detectar ejes mal rotulados, leyendas truncadas, calidad de impresión y coherencia con la matriz BAT26-49. Debe reportarse dónde quedaron los archivos y, si se propone su incorporación a GitHub, hacerlo solo mediante un manifiesto de resultados liviano o una ruta validada, sin arrastrar las modificaciones incidentales de outputs/validation/bess_step3.

**Estado inicial:** ejecutor, tests y especificación preparados en GitHub; figuras originales pendientes de recuperación y ejecución; PR en borrador. **No** se debe declarar la campaña BAT26-50 como PASS antes de obtener sus outputs, ni cerrar Roma o fusionar PR hasta revisión.


## Resultados de ejecución y revisión visual comunicados el 6-11-2026

Codex Cloud informó **PASS** de la campaña BAT26-50 y **6/6 pruebas de contrato PASS**. Las dos carpetas originales de BAT26-45 y BAT26-46 estaban disponibles y pasaron la verificación del generador; el historial de BAT26-45 conservó los **1001 registros correspondientes a los días 0–1000**. La comparación BAT26-46 incluyó exactamente cuatro escenarios de 0, 100, 500 y 1000 días, con corriente constante de **+8 A en el puerto 2p**. El PNG de SoC frente al tiempo fue copiado sin recrear su trayectoria.

Directorio de resultados informado por Codex Cloud: `outputs/analysis/bat26_50_figures/run_20261106T153947_125249Z/`. Contiene `fig01_soh_vs_efc_blast.png`, `fig02_efc_definitions.png`, `fig03_capacity_vs_days.png`, `fig04_soc_vs_time_original_bat46.png`, `fig05_usable_charge_ah.png`, `fig06_terminal_energy_fixed_8Ah.png`, `checkpoints.csv` y `manifest.json`. El usuario aportó las **seis imágenes completas**; la inspección visual en esta conversación confirmó ejes y unidades coherentes, leyendas legibles y ausencia de desbordes evidentes. Las carpetas del workspace de Codex **no equivalen a archivos versionados en GitHub**.

El CSV consolidado reporta, tras 1000 jornadas sintéticas, **SoH 54.323934 %**, **Qeff 35.853796 Ah**, **800 excursiones equivalentes de SoC**, **711.451843 EFC internos de BLAST** y **711.451843 EFC por throughput del caso normalizado por 44.1 Ah**. Estos dos últimos contadores **coinciden numéricamente para este perfil/algoritmo de contabilización**, por lo que sus líneas en la figura 2 quedan visualmente superpuestas; la coincidencia **no convierte sus definiciones en intercambiables para cualquier perfil o implementación**. Los 800 corresponden a excursiones geométricas del SoC, no a throughput de Ah dividido entre una referencia fija.

La figura 3 muestra únicamente la diferencia entre dos **protocolos sintéticos completos**, no una separación experimental de envejecimiento calendario y cíclico. La figura 4 demuestra mayor caída de SoC para una misma descarga de puerto al reducirse la capacidad, sin interpretar esa corriente como corriente de bus DC. La figura 5 refleja carga utilizable ideal en **Ah**. La figura 6 refleja energía terminal **transferida en una hora a corriente fija**; la variación aproximada de 29.668 a 29.577 Wh es de **0.091 Wh (≈0.31 %)**, y la escala vertical ampliada **no debe utilizarse para sugerir una gran variación de energía almacenable**.

Codex informó que `manifest.json` registra SHA-256 de fuentes, seis imágenes y tabla, commits y versiones. **No se abrió directamente el manifiesto JSON ni se cotejaron sus hashes desde esta conversación**; las cifras y la generación PASS proceden del informe del estudiante/Codex, mientras que la inspección de imágenes se basó en los PNG adjuntos. Por tanto, el estado **PASS** de BAT26-50 refiere a generación reproducible e inspección visual de las seis figuras, **no** a validación experimental ni a almacenamiento definitivo de los artefactos en GitHub.

**Dictamen de cierre documental:** se cumple el criterio de contar con las seis gráficas y la tabla/manifest de procedencia reportados. Para preparar el dossier BAT26-51, conservar/exportar el paquete original de Codex y, de ser posible, adjuntar las figuras y los datos consolidados a una entrega persistente; la rama GitHub guarda el código y protocolo, pero no los binarios de resultados.
