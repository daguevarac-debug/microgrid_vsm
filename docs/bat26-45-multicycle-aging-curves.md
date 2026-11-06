# BAT26-45 — SoH y capacidad frente a 100–1000 ciclos sintéticos

## Propósito de tesis

BAT26-44 verificó la respuesta dinámica de pocos segundos. Este ejercicio cambia explícitamente la escala temporal: evalúa hasta 1000 jornadas de uso de un grupo equivalente Nissan Leaf 2p, y registra SoH, capacidad efectiva, EFC y pérdidas calculadas por BLAST. Su objetivo es **mostrar degradación observable sin multiplicar artificialmente los coeficientes**.

La implementación utiliza el modelo oficial **BLAST-Lite 1.1.0**, clase \`Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery\`, ejecutada exclusivamente en Python **3.12.10**. El script verifica los dos hashes SHA-256 ya auditados en BAT26-32/36/41. No cambia archivos ni coeficientes de BLAST.

## Protocolo sintético fijo

Se toma \`Qnom=66 Ah\` y una capacidad **inicial del caso de tesis** \`Q0=44.1 Ah\` (\`SoH0=66.81818 %\`). Esto no debe confundirse con las referencias nativas de BLAST: \`cap_2ndLife=46 Ah\` y \`66*qNew(0)=46.2 Ah\`. La hipótesis de transferencia sigue siendo \`Qeff=44.1 Ah × q/q0\`. El dominio operativo del caso termina en \`SoH=50 %\` (33 Ah); no se admite predecir explotación por debajo de ese umbral.

Cada jornada dura **24 h** a temperatura de celda fija y sintética de **25 °C**. El SoC recorre \`0.50 → 0.10 → 0.90 → 0.50\` durante 3,2 h; permanece a 0,50 durante 20,8 h. Las rampas representan \`0.5 C\` relativo a la **capacidad efectiva al inicio de cada jornada**, no una medición de corriente del grupo físico. La trayectoria es continua entre jornadas y no agrega saltos de SoC no contabilizados.

Un ciclo diario suma \`|ΔSoC|=1.6\` y **0.8 EFC nominales**. Los contadores \`efc_blast\` de BLAST y \`efc_from_case_throughput\` calculado con Ah sintéticos se informan **por separado**, puesto que BLAST pondera el cambio de SoC con su propia retención \`q\`. Por ello, **1000 ciclos diarios no deben rotularse como 1000 EFC**; corresponderían a 800 EFC nominales antes de la corrección de capacidad.

La referencia calendario repite el mismo intervalo diario, temperatura, instantes y tamaño de ventana, pero mantiene \`SoC=0.50\` y \`i=0\`. La diferencia entre trayectorias no equivale a aislar un único mecanismo, puesto que también pueden diferir los esfuerzos de SoC; el resultado nativo \`qLoss_EFC\` se muestra separadamente para contextualizar ese efecto.

## Controles metodológicos

La ejecución conserva **una misma instancia BLAST por perfil durante todos los ciclos**. Cada día es una ventana de 24 h de tiempos absolutos crecientes, con el punto frontera compartido y el mismo SoC al inicio y al final. No se resetean los estados internos ni se fuerza un SoH deseado. Se registran las salidas en 0, 1, 10, 50, 100, 250, 500, 750 y 1000 ciclos cuando se alcanzan.

BLAST presenta sensibilidad conocida al tamaño de ventana, identificada en BAT26-32 y BAT26-36. Como control adicional, la misma trayectoria de los primeros 100 ciclos se ejecuta con **dos ventanas por día** (fase activa y reposo), conservando fronteras físicas y tiempo total. Se reporta la diferencia de SoH y EFC entre particiones sin inventar una tolerancia experimental de aceptación. Esta comparación es un diagnóstico numérico, no una demostración de convergencia temporal.

El estado \`LIMIT_REACHED\` indica que la campaña tocó o cruzó el piso operativo antes de 1000 ciclos; no es un permiso para extrapolar. \`FAIL\` indica incumplimiento de integridad, error del modelo o problema de generación de figuras. El estado \`PASS\` corresponde a la ejecución numérica completa dentro del protocolo y sus verificaciones, **no** a validación experimental.

## Comandos en Codex Cloud

Abrir tarea nueva en la rama \`feat/bat26-45-multicycle-aging-curves\`, tras comprobar que el entorno realmente ofrece Python 3.12.10 y BLAST-Lite 1.1.0 originales, incluido \`setuptools\` y los dos hashes de fuente.

Comprobar primero las propiedades del perfil (sin BLAST):

~~~bash
.venv/bin/python -B -m unittest discover -s src/validation -p test_bat26_45_synthetic_profile.py -v
~~~

Ejecutar un piloto de **100 ciclos** en el intérprete BLAST nativo:

~~~bash
"$BLAST_LITE_PYTHON" -B src/validation/run_bat26_45_multicycle.py --cycles 100 --sensitivity-cycles 100
~~~

Solo si el piloto termina sin errores graves, completar **1000 ciclos**:

~~~bash
"$BLAST_LITE_PYTHON" -B src/validation/run_bat26_45_multicycle.py --cycles 1000 --sensitivity-cycles 100
~~~

El ejecutor **no** genera muestras instantáneas del controlador VSG ni co-simula la microrred. BLAST usa únicamente las trayectorias SoC y temperatura; la corriente sintética indicada permite contextualizar la amplitud y el throughput, pero **no** entra como medida de corriente nativa ni como interfaz física DC/DC del BESS.

## Evidencia esperada

Cada intento crea un directorio nuevo en \`outputs/analysis/bat26_45_multicycle/run_<UTC>/\`. Allí se guardan \`summary.json\` con el SHA del commit, versiones, dos hashes, resultados por checkpoint, sensibilidad numérica y condiciones de validez; \`cycle_history.csv\` con todas las jornadas y capacidad/pérdida estimada; y tres figuras: \`soh_vs_cycles_full.png\` (eje 0–100 %), \`soh_vs_cycles_zoom.png\` (eje ampliado **explícitamente rotulado**) y \`capacity_vs_cycles.png\` (Ah). Las curvas no están producidas ni verificadas hasta ejecutar efectivamente los comandos.

La primera revisión debe priorizar los datos a **100 y 1000 ciclos**, la diferencia entre calendario y ciclado, las pérdidas originales \`qLoss_t\` y \`qLoss_EFC\`, el número efectivo \`efc_blast\` y la diferencia por tamaño de ventana. Si la degradación resulta pequeña o inesperada, se informa como tal; **no se modifica \`k_deg\`, BLAST, la escala gráfica de manera engañosa ni los datos** para mejorar su apariencia.

## Interpretación científica y límites

Este ensayo no debe confundirse con predicción de vida remanente validada. Los autores de BLAST señalan que sus modelos describen vida esperada y contienen extrapolaciones condicionadas por datos de envejecimiento acelerado; no incluyen todos los modos de fallo de baterías ni desequilibrios internos: [BLAST-Lite oficial](https://github.com/NatLabRockies/BLAST-Lite#caveats). La política de SoC fijo con menor throughput a medida que se degrada la batería corresponde a una hipótesis elegida, no a una operación universal. El escenario de 1000 días (aproximadamente 2,74 años) no representa mediciones de campo.

Tampoco se ha calibrado la transferencia de la referencia BLAST de 46/46,2 Ah a los 44,1 Ah de la tesis, ni implementado la degradación nativa dentro del control VSG a escala de 1000 días. Esta última integración y la validación física con perfiles 2p, temperatura medida, convertidor y degradación observada requieren trabajos posteriores.

**Estado de ejecución:** Codex Cloud informó **PASS** para piloto de 100 ciclos y campaña de 1000 ciclos; cuatro pruebas del perfil sintético superadas, Python BLAST 3.12.10, BLAST-Lite 1.1.0 y ambos hashes auditados confirmados. Los resultados resumidos se registran a continuación. El informe y las figuras están en el espacio de trabajo de Codex; **no** se han incorporado automáticamente al repositorio público.

## Resultados numéricos de la campaña (reporte Codex Cloud, 5-11-2026)

La ejecución corresponde al commit `959362a62bd2499953360b76e5e4c41185ecbb73`, previo al añadido de esta sección documental. El usuario proporcionó el informe final de Codex y las cifras siguientes; la copia completa de `summary.json` y los PNG **no fue inspeccionada directamente desde esta revisión**.

| Ciclos diarios / días | SoH del caso ciclado (%) | Qeff (Ah) | EFC BLAST | EFC nominal |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 64.049 | 42.273 | 77.876 | 80 |
| 250 | 61.975 | 40.904 | 190.976 | 200 |
| 500 | 59.148 | 39.038 | 372.152 | 400 |
| 1000 | 54.324 | 35.854 | 711.452 | 800 |

El caso inicia en **SoH 66.81818 % y Qeff 44.1 Ah**. A los 1000 ciclos se estima una reducción absoluta de **12.494 puntos porcentuales de SoH** y **8.246 Ah** de capacidad. El caso calendario de igual duración finaliza en SoH **60.422 %** y Qeff **39.879 Ah**. La diferencia de **6.098 puntos porcentuales** entre perfiles no corresponde exclusivamente a la degradación cíclica, pues el esfuerzo calendario depende del perfil de SoC. El SoH del caso ciclado permanece por encima del piso operativo establecido de 50 % y no se prolonga la extrapolación.

A los 1000 ciclos la pérdida nativa `qLoss_t` fue **0.09582** y la cíclica `qLoss_EFC` fue **0.09117**. A los 100 ciclos, una partición de dos ventanas por jornada en lugar de una modificó SoH en **−0.01067 puntos porcentuales** y EFC en **−0.02689**. Estas diferencias indican sensibilidad numérica del método por ventanas y no establecen por sí mismas un margen experimental aceptable.

Evidencias en workspace de Codex Cloud: `outputs/analysis/bat26_45_multicycle/run_20261105T211126_668639Z/summary.json`, `cycle_history.csv`, `soh_vs_cycles_full.png`, `soh_vs_cycles_zoom.png`, `capacity_vs_cycles.png`. Piloto: `outputs/analysis/bat26_45_multicycle/run_20261105T211115_381076Z/summary.json`. Estos archivos no tienen garantizada persistencia en GitHub y no deben citarse como adjuntos publicados.

**Dictamen de software:** la campaña satisface el criterio de BAT26-45 de trazar SoH frente al uso durante un horizonte largo, con las limitaciones de transferencia de capacidad, sensibilidad temporal y carácter sintético explicitadas. El siguiente trabajo debe tratar el enlace con el despacho sin confundir los 1000 ciclos diarios con 1000 EFC ni declarar calibración física del grupo 2p.
