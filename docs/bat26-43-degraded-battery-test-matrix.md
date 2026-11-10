# BAT26-43 — Matriz reproducible de pruebas de batería degradada

## Propósito y criterio de cierre

El criterio de Roma es disponer de evidencia numérica de **SoC, SoH, signos, EFC, energía y límites**, sobre la base de BAT26-42. La revisión de la rama `feat/blast-aging-adapter` (commit base `f23966e29e57a71e188abbb256d44707b4a07a2e`) identificó cobertura existente suficiente para cada dimensión. No se añade ninguna ecuación, coeficiente, estado ni prueba conceptual redundante; el vacío es una ejecución conjunta, fechada, no destructiva y con resultados atribuibles a un commit.

**Estado:** protocolo y ejecutor preparados en GitHub; ejecución nueva y cierre de BAT26-43 **pendientes**. Los registros anteriores son antecedentes, no resultados de esta nueva matriz. Se mantiene la revisión histórica GFM +40 %/Vdc y no se inicia BAT26-44 por adelantado.

## Trazabilidad de la matriz

| Evidencia | Grupo del ejecutor | Pruebas existentes | Cobertura |
|---|---|---:|---|
| Capacidad y SoH de referencia | capacity | 11 | Qnom 66 Ah, caso 44,1 Ah, q/q0, no multiplicar qNew=0,7 |
| SoC por capacidad y frontera | soc_boundary | 4 | Corriente y signo, Ah, continuidad fraccional y rechazo sin clipping |
| Snapshot integrado en 15/16 estados | snapshot | 6 | SoH fijo en ventana, ausencia de doble degradación, GFM/PI y estados |
| Signo de descarga y carga en GFM | signs | 3 | i_bess, dSoC/dt y soporte DC, con signos coherentes |
| Energía algebraica 1RC | rc_energy | 1 | Contabilidad local con C1(SoC) variable; no es energía electroquímica medida |
| Energía del capacitor y límites SoH | dc_energy_limits | 5 | M10: potencia instantánea y ventana de corrientes constantes; saturaciones |
| Derivada del enlace DC | dc_link | 5 | Corrientes entrantes/salientes y ausencia de inyección ficticia |
| DC/DC algebraico separado | dc_dc_separate | 15 | Pérdidas sintéticas, signos, límites y protección del adaptador **no integrado** |
| Adaptador BLAST original | blast_snapshots | 10 | Historia, capacidad relativa, ventanas, límites, modo explícito y EFC |
| Throughput/EFC nativo BLAST | blast_efc | 7 | Ah/EFC_ini/EFC_eff, perfiles sintéticos, partición, SoC y anclaje |

La matriz reúne **67 tests nominales existentes** (60 en el entorno principal, incluidos los que utilizan el worker, y 7 en Python BLAST nativo). El número efectivo se mide al ejecutarla; si alguna suite reporta menos pruebas que su mínimo documentado, termina en FAIL, aunque el proceso Python devuelva éxito. Una dependencia BLAST ausente deja **NOT_RUN / INCOMPLETE**, nunca un PASS artificial. El ejecutor no presume que resultados anteriores equivalen a ejecución actual.

Se reutilizan además las evidencias numéricas ya publicadas de BAT26-36 (ciclos parciales, EFC y capacidad variable), BAT26-41 (tres ventanas con BLAST-Lite 1.1.0, arquitectura de 15 y 16 estados) y BAT26-42 (identidad de energía DC y límites), sin reejecutar scripts que sobrescriben archivos previos. En particular, `outputs/analysis/bat26_36_efc/check_efc.py` se importa mediante descubrimiento `unittest`: se ejecutan sus siete métodos, **no su bloque __main__ que reescribe results.json**. Tampoco se ejecuta `check_windows.py`, cuyo bloque principal reescribe los resultados de BAT26-41.

## Ejecución reproducible, cuando esté disponible el computador personal

Desde la raíz del proyecto y sobre el commit con el PR de BAT26-43:

~~~powershell
& .\.venv\Scripts\python.exe -B src/validation/run_bat26_43_matrix.py
~~~

El ejecutor identifica el Python principal desde `sys.executable`; el entorno nativo de BLAST se obtiene de `BLAST_LITE_PYTHON`, o de la instalación local previamente utilizada en `%LOCALAPPDATA%\microgrid_blast_probe_312\Scripts\python.exe`. El worker BLAST sigue exigiendo Python 3.12.10, BLAST-Lite 1.1.0 y los SHA-256 auditados; el ejecutor no altera esos mecanismos.

Cada intento crea una carpeta única `outputs/analysis/bat26_43_matrix/run_<UTC>/` que contiene `summary.json` y logs por suite. Registra el commit Git, versión del intérprete principal, presencia del entorno BLAST, SHA-256 de archivos fuente y de referencias numéricas, conteo efectivo por suite, código de salida y clasificación PASS, FAIL o NOT_RUN. No modifica código ni archivos de los ensayos históricos y no realiza commit/push. Se debe revisar el JSON y, ante un fallo, el log respectivo antes de decidir si existe una regresión de software o un problema de entorno.

El proceso devuelve código 0 exclusivamente cuando **todas** las suites exigidas obtienen PASS; devuelve 1 si hay FALLAS o cobertura incompleta. La salida es evidencia nueva local y no se publica automáticamente, ya que la visibilidad del repositorio es pública y pueden existir rutas o datos internos en logs.

## Interpretación científica y bloqueos

La prueba de energía DC establece únicamente la identidad del campo `Cdc*dVdc/dt = ipv+i_bess-idc_inv`; la del 1RC establece una identidad algebraica con parámetros provisionales. Ninguna demuestra balance físico batería–convertidor–bus, rendimiento real del convertidor, energía electroquímica o validez de parámetros medidos. Del mismo modo, `z_deg` mide Ah del puerto equivalente y el EFC de BLAST deriva de la serie de SoC, sin utilizar la señal `current_2p_a` como esfuerzo de corriente: no se debe presentar como verificación de una transformación física bus–grupo 2p.

Los rangos de SoC y los límites de potencia/corriente son hipótesis de supervisión; no equivalen a un BMS industrial, no incluyen temperatura o tensión terminal validada y no prueban invariancia continua entre todas las muestras. La sensibilidad temporal BLAST carece todavía de tolerancia física fundamentada; las corrientes/temperaturas operativas del conjunto 2p y la validación experimental continúan pendientes.

**Dictamen preliminar:** la cobertura existente responde al criterio de BAT26-43 para consistencia de software; esta tarea podrá cerrarse únicamente después de ejecutar la matriz y revisar los resultados. La comparación OFF/ON y las regresiones completas de Objetivos 1 y 2 corresponden a BAT26-44, no a esta preparación.
