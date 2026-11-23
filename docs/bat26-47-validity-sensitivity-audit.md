# BAT26-47 — Contraste de evidencia y sensibilidad del modelo

## Pregunta y decisión de evidencia
El criterio de Roma es contrastar la batería de segunda vida con mediciones independientes compatibles cuando existan. En caso contrario, delimitar el dominio y cuantificar sensibilidad. Este informe separa **verificación de software**, **sensibilidad de parámetros y particiones**, **comparación cualitativa con publicaciones** y **validación experimental independiente**, que por ahora NO ha sido demostrada.

El caso implementado es un grupo equivalente Nissan Leaf 2p con capacidad nominal 66 Ah, capacidad inicial de tesis 44,1 Ah y estado inicial SoH=66,818 %. BAT26-45 produjo una curva sintética de 1000 días hasta 54,324 % y 35,854 Ah con BLAST-Lite 1.1.0 a 25 °C; BAT26-46 mostró reducción de autonomía bajo descarga de 8 A del puerto 1RC y cuatro simulaciones GFM 15 estados que permanecieron **solo en absorción**, sin probar soporte en descarga.

## Matriz de comparabilidad de evidencia, sin inventar datos

| Referencia | Datos accesibles comprobados hasta BAT26-47 | Compatibilidad y uso autorizado | Conclusión metodológica |
| --- | --- | --- | --- |
| Braco et al. 2020/2021, Nissan Leaf LMO/grafito 2s2p | Curvas, protocolo y resultados publicados; series originales no adquiridas | Alta proximidad química y formato 2p; protocolos de envejecimiento distintos | Contraste bibliográfico cualitativo; sin ajuste/test independiente ni residuos por muestra |
| Braco et al. 2023, pareja 2p Leaf 66 Ah | Mediciones publicadas de capacidad y resistencia de pulso | Caracterización inicial; R_DC a 10 s NO equivale a R0 instantánea | No valida trayectoria temporal de SoH ni R1/C1 |
| Pérez et al. 2025, eTransportation 24:100400 | Tablas/figuras experimentales; datos originales confidenciales según auditoría BAT26-31 | Modelado por etapas del ciclo de vida de Leaf; coeficientes y protocolos NO idénticos a BLAST | Comparación de dominio y tendencias, no cálculo de RMSE independiente |
| Cui et al. 2024, Cell Reports Physical Science 5:101941 | Dataset público declarado por autores: https://osf.io/fns57/ ; archivos sin descarga/inspección y acceso remoto no confirmado | Ocho unidades Nissan Leaf reutilizadas, química afín, pero ensayo de 3–4 V, temperatura/definiciones de Q distintas | Candidato prioritario a validar; nivel B hasta obtener series y auditar RPT e identidades de muestras |
| Gao et al. 2024, eTransportation 20:100313 | Artículo con dos celdas ensayadas a miles de ciclos; datos disponibles a solicitud según declaración editorial | Leaf Gen1 y trayectoria de envejecimiento, pero unidad celular, perfiles y ventanas diferentes | Referencia de contexto, no comparación cuantitativa contra el caso 2p de 44,1 Ah |
| ORNL / Wiggins, datos HPPC de Leaf Gen1 | CSV de celda nominal ~33,1 Ah, primera vida, según auditoría BAT26-31 | Potencial para contraste de formas I/V, no vida segunda | No valida desgaste de segunda vida; parámetros no transferibles automáticamente |
| `OCV_SOC.xlsx` del repositorio | 58 muestras etiquetadas; SoC reconstruido por loader desde Ah/66 | Procedencia/unidades y protocolo sin acreditación; curva rotulada OCV vinculada a descarga bajo carga | **No** constituye OCV/R1/C1 experimental calibrado para el mismo grupo 2p |

Fuentes: fichas y decisión BAT26-31 (Roma); `docs/bat26-35-ecm-parameter-evidence.md`; Braco 2020 DOI 10.1016/j.est.2020.101695; Braco 2023 DOI 10.1016/j.apenergy.2022.120235; Cui 2024 DOI 10.1016/j.xcrp.2024.101941; Pérez 2025 DOI 10.1016/j.etran.2025.100400; Gao 2024 DOI 10.1016/j.etran.2024.100313. Los datos de Cui fueron anunciados públicamente, pero en esta tarea no se recuperaron sus archivos binarios: no afirmar nivel A ni validación independiente.

## Sensibilidad BLAST de la predicción de envejecimiento

Usar exclusivamente el intérprete BLAST nativo **Python 3.12.10**, BLAST-Lite 1.1.0 y dos hashes SHA-256 ya auditados. En `src/validation/run_bat26_47_blast_partition.py`, reproducir el mismo perfil diario de BAT26-45 (129 muestras; SoC 0,5→0,1→0,9→0,5; temperatura sintética 25 °C) durante **100 días**. Mantener 128 intervalos físicos por día, mismas muestras, tiempos y contornos; variar únicamente la partición en **1, 2 o 4 ventanas por jornada**.

Registrar SoH final, Qeff, q, qLoss_t, qLoss_EFC, EFC BLAST y diferencias respecto a una ventana. BAT26-45 había mostrado **−0,01067 puntos porcentuales de SoH y −0,02689 EFC** para dos ventanas frente a una a 100 días. El nuevo control de cuatro ventanas determinará si la discrepancia aumenta o disminuye; **NO** se puede declarar convergencia numérica sin criterio físico o tolerancia establecida previamente. No retocar parámetros de envejecimiento para que el resultado se vea mejor.

## Sensibilidad ECM 1RC y escenarios de operación

El ejecutor `src/validation/run_bat26_47_ecm_sensitivity.py` usa dos capacidades de BAT26-45, 44,1 y 35,854 Ah, como condiciones iniciales independientes. Cada una se simula durante una hora desde SoC 0,6 con corrientes sintéticas del **puerto de batería**, −8, +4, +8 y +16 A; se exploran máximos de paso de `solve_ivp` de 120, 60, 30 y 15 segundos, manteniendo las tolerancias declaradas y una malla común de 121 muestras para energía terminal. La respuesta del 1RC puede sufrir pequeños efectos del modo lineal durante esta hora; no son datos externos.

Se añade una sensibilidad meramente ilustrativa de la pendiente `k_R` de la relación `R0(SoH)` con valores **0, 1 y 2**, exclusivamente sobre instancias locales del modelo a +8 A y un máximo de paso de 60 segundos. Los extremos NO son intervalos de confianza, escenarios medidos ni una calibración. Su finalidad es identificar si la energía terminal estimada depende de un coeficiente provisional. OCV/R1/C1 y la definición misma de R0 siguen sin validación experimental; no sustituyen ese vacío con un barrido paramétrico.

Ambos scripts generan carpetas nuevas y resumen JSON en `outputs/analysis/bat26_47_ecm_sensitivity/` y `outputs/analysis/bat26_47_blast_partition/`. Deben informar el SHA del código, versiones, número de casos, estado de invariantes y una interpretación *cuantitativa* de sensibilidad. No sobrescribir `results.json` de BAT26-36/41/45.

## Ejecución y criterio de cierre

Desde Codex Cloud, en la rama `feat/bat26-47-validity-sensitivity`, usar primero el Python principal para los tests y la sensibilidad del 1RC:

~~~bash
.venv/bin/python -B -m unittest discover -s src/validation -p test_bat26_47_sensitivity_contract.py -v
.venv/bin/python -B src/validation/run_bat26_47_ecm_sensitivity.py
~~~

Después comprobar el entorno BLAST nativo exacto y ejecutar la partición de 100 días:

~~~bash
"$BLAST_LITE_PYTHON" -B src/validation/run_bat26_47_blast_partition.py --days 100
~~~

**Criterio de software PASS:** todos los tests y barridos se ejecutan sin violar límites y se generan reportes reproducibles. **Evaluación científica REVIEW:** las diferencias de partición y de parámetros quedan documentadas sin tolerancia experimental, y no hay comparación cuantitativa independiente con mediciones compatibles. **FAIL** significa error del código, un test fallido, salida no finita o violación de límites; no corresponde a un REVIEW puramente interpretativo.

El ensayo GFM de BAT26-46 quedó en absorción; esta tarea **no debe declarar validación de descarga o soporte a la red**. El usuario puede llevar este resultado al director como límite identificado y como siguiente diseño experimental necesario, no como fallo del VSG.

## Salidas requeridas para decisión BAT26-48

Documentar en los dos JSON los deltas numéricos y anexar tablas de sensibilidad. Si la sensibilidad temporal no es despreciable o el modelo puede abandonar su dominio, dejar la decisión de validez como `REVIEW` explícito. Definir una solicitud de datos: una misma pareja 2p de Leaf reutilizada con corriente, tensión terminal, temperatura de celda, RPT de capacidad repetidos (mismos límites de tensión y T), HPPC, identificador de muestra/pack y separación por grupo entre calibración/validación. Sin estos datos NO es justificable publicar MAE/RMSE de envejecimiento ni atribuir precisión experimental al BLAST transferido.

**Estado inicial:** protocolo y código preparados, sin nuevas ejecuciones. BAT26-47 permanece inProgress hasta revisar cifras reales y redactar un dictamen que distinga validez numérica de evidencia experimental.

## Resultados de ejecución (Codex Cloud; informe comunicado el 6-11-2026)

**Estado de implementación: PASS numérico. Estado de validación experimental: REVIEW / NOT_EVALUABLE.** El usuario entregó los resultados del ejecutor en la rama de PR #43, commit `8e24752cf85abe95152044e1259d2d513b31c4fe`. Los seis tests de contrato pasaron. Esta revisión registra cifras comunicadas por Codex, pero **no inspeccionó directamente los archivos completos de los dos JSON en el espacio de trabajo remoto**. No se modificaron parámetros físicos ni los hashes de BLAST.

### Ensayo de sensibilidad del 1RC

Se ejecutaron **32 casos** (dos capacidades 44,1 y 35,854 Ah × cuatro corrientes de puerto −8/+4/+8/+16 A × cuatro máximos pasos temporales 120/60/30/15 s) y seis variantes adicionales de la pendiente provisional `k_R` (0, 1, 2) para +8 A y paso 60 s. Todos conservaron estados finitos, límites de SoC/SoH y corriente, tensión terminal positiva, convenio de signos y contabilidad de throughput. Comparados con el máximo paso de 15 s, las diferencias máximas absolutas fueron **1,67×10⁻¹³ puntos porcentuales de SoC** y **3,96×10⁻⁸ Wh de energía terminal**. Esto acredita consistencia numérica en el rango ensayado, no exactitud del 1RC físico.

| Capacidad inicial (Ah) | Energía con k_R=0 (Wh) | k_R=1 (Wh) | k_R=2 (Wh) | Rango (Wh) |
| ---: | ---: | ---: | ---: | ---: |
| 44,100 | 29,688 | 29,668 | 29,647 | 0,041 |
| 35,854 | 29,605 | 29,577 | 29,549 | 0,057 |

El valor de SoC final fue indistinguible al variar `k_R`, de acuerdo con el conteo de carga; la energía terminal sí depende del supuesto de resistencia. **k_R=0,1,2** no define límites de incertidumbre ni corresponde a un ajuste de la pareja Leaf 2p.

### Sensibilidad a partición BLAST tras 100 días

Las tres ejecuciones se realizaron con idénticos perfiles sintéticos SoC/temperatura, 129 muestras y 128 intervalos físicos por jornada, cambiando exclusivamente el agrupamiento de esas muestras en ventanas. El intérprete y versión declarados y auditados fueron **Python 3.12.10**, **BLAST-Lite 1.1.0** con ambas huellas SHA-256 originales coincidentes.

| Ventanas/día | SoH final (%) | Qeff final (Ah) | EFC BLAST |
| ---: | ---: | ---: | ---: |
| 1 | 64,049385 | 42,272594 | 77,876407 |
| 2 | 64,038716 | 42,265553 | 77,849515 |
| 4 | 64,041229 | 42,267211 | 77,853695 |

Respecto al caso de una ventana, el de dos arroja **−0,010669 puntos porcentuales de SoH**, **−0,007041 Ah** de Qeff y **−0,026892 EFC**. El de cuatro arroja **−0,008156 puntos porcentuales de SoH**, **−0,005383 Ah** de Qeff y **−0,022713 EFC**. La sucesión de resultados **no es monótona con el número de ventanas**; no se ha establecido convergencia temporal ni existe umbral de error físico predeterminado para aceptarla.

### Dictamen y alcance de cierre

Se cumplen las pruebas de consistencia y sensibilidad numérica previstas por BAT26-47 y queda trazada la **ausencia de validación externa independiente**. Aún no se han adquirido/auditado series de envejecimiento compatibles con una pareja Nissan Leaf 2p de segunda vida y RPT comparables, ni se ha identificado físicamente OCV/R0/R1/C1; tampoco hay verificación de transferencia de corriente mediante DC/DC ni ensayo de soporte GFM en descarga. En estas condiciones, **no** corresponde publicar MAE, RMSE, intervalos de confianza ni predicciones de vida en campo. La comparación experimental, la calibración y la extrapolación permanecen **REVIEW** aunque ambas campañas informen **PASS numérico**.

Los informes originales fueron declarados en Codex Cloud en `outputs/analysis/bat26_47_ecm_sensitivity/run_20261106T145424_655368Z/summary.json` y `outputs/analysis/bat26_47_blast_partition/run_20261106T145447_557519Z/summary.json`, sin garantía de persistencia/versionado en GitHub. Siguiente trabajo: especificar en BAT26-48 entradas, límites y costo de degradación para despacho, sin afirmar que la optimización o validación de batería ya esté completa.
