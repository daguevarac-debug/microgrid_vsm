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
