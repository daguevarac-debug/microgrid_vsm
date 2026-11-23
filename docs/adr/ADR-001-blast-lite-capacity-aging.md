# ADR-001 — Selección de BLAST-Lite para envejecimiento de capacidad del BESS SLB

- **Estado:** Selección metodológica aprobada; integración y validación física pendientes para BAT26-33.
- **Fecha:** 2026-11-03
- **Alcance:** ley lenta de capacidad para escenarios de batería Nissan Leaf de segunda vida.
- **Fuera de alcance:** ECM 1RC, ecuaciones/estados del solver, control, despacho y parámetros eléctricos.

## Contexto y decisión

La ley lineal actual del proyecto actualiza SoH a partir de throughput acumulado (`z_deg`): `SoH=max(soh_min, soh_init_case-k_deg*z_deg)`. Es un baseline computacional simple y reproducible, pero sólo representa pérdida asociada a uso acumulado: no responde explícitamente a tiempo en reposo, temperatura de celda ni SoC de almacenamiento. `k_deg=1.478e-6` no debe presentarse como calibración experimental independiente del proyecto.

**Decisión aprobada metodológicamente por el usuario:** seleccionar la clase Nissan Leaf de BLAST-Lite como modelo preferido para estudios de degradación calendario y cíclica de segunda vida, porque combina ambas pérdidas en estados separados, usa entradas de tiempo, SoC, temperatura y throughput, y declara origen en módulos Leaf de segunda vida de 66 Ah. Conservar la ley lineal como referencia y alternativa de regresión, mutuamente excluyente con BLAST al actualizar capacidad. Esta selección metodológica no prueba que BLAST sea físicamente válido para la pareja, el perfil o las condiciones térmicas de la tesis.

La pérdida calendario se calcula con exposición tiempo–temperatura–SoC; la pérdida cíclica se actualiza con uso/EFC. En la clase original ambas contribuciones y el historial interno se preservan (`qLoss_t`, `qLoss_EFC`, `EFC`, `t_days`, `q` y `qNew`). No se sustituye el estado original por un ajuste de sus salidas ni se reinicia BLAST entre ventanas de un mismo historial.

## Referencias de capacidad y contrato provisional

Se mantienen como cantidades distintas, sin reconciliarlas por redondeo:

| Cantidad | Valor | Significado |
|---|---:|---|
| `q_nom_ref_ah` | 66 Ah | referencia nominal nueva de la unidad Leaf 2p |
| `cap_2ndLife` BLAST | 46 Ah | atributo fijado por la clase original |
| `qNew(0)·66` BLAST | 46.2 Ah | resultado de `qNew(0)=0.7`; discrepa 0.2 Ah del atributo anterior |
| `q_init_case_ah` tesis | 44.1 Ah | capacidad inicial definida para el escenario de tesis; no es una medición de la misma muestra BLAST |
| `Q_case_Braco` | 43.5 Ah | referencia experimental reportada por Braco para su experimento; no se identifica automáticamente con el caso de 44.1 Ah |

La interfaz de escenario aprobada como **hipótesis de modelado** es `retention_since_case_start(t)=q(t)/q(t0)` y `Q_eff(t)=q_init_case_ah·retention_since_case_start(t)`. En `t0`, la retención vale 1. El `q(t)` del numerador es la salida de la trayectoria original BLAST cuyo estado/historial permanece intacto. `qNew` se conserva como salida de referencia original, no como entrada de capacidad del caso. No multiplicar `q_init_case_ah` por 0.7, no restar otra vez pérdidas previas y no reemplazar `q(t0)` por una constante artificial. La aceptación de este contrato no es validación experimental ni transferencia demostrada a 44.1 o 43.5 Ah; tampoco recalibra coeficientes ni identifica una batería particular.

El contrato ya prototipado en `src/bess/aging_capacity.py` expresa ese snapshot de manera inmutable: `q_eff_ah=q_init_case_ah·retention` y `soh=q_eff_ah/q_nom_ref_ah`. El módulo no importa ni implementa BLAST. Este ADR no conecta dicho contrato al solver.

## Hipótesis de transferencia y límites de evidencia

El código público [BLAST-Lite](https://github.com/NatLabRockies/BLAST-Lite), clase `Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery`, conserva una referencia de módulo/mita de módulo Leaf 2p de 66 Ah y reporta ajuste calendario atribuido a Braco (2022) y ciclado atribuido a Braco (2020). La versión auditada fue BLAST-Lite 1.1.0; la clase y su base se cotejaron con el commit fuente `b093495b47dc40dd96dba865d91f553619501e94`. Fuentes bibliográficas: Braco et al., *Journal of Energy Storage* (2020), [DOI 10.1016/j.est.2020.101695](https://doi.org/10.1016/j.est.2020.101695); Braco et al., *IEEE Transactions on Industry Applications* (2021), [DOI 10.1109/TIA.2021.3075180](https://doi.org/10.1109/TIA.2021.3075180); y Braco et al. (2022), [DOI 10.1109/EEEIC/ICPSEUROPE54979.2022.9854784](https://doi.org/10.1109/EEEIC/ICPSEUROPE54979.2022.9854784).

La ley cíclica tiene soporte experimental mucho más estrecho que sus entradas aparentes: el docstring/dominio de la clase describe ciclado a 25 °C, 100 % DoD y 1C; el modelo reduce el ciclado a throughput/EFC y no identifica explícitamente efectos de DoD, C-rate o temperatura de ciclado. La campaña FV/VSG de la tesis incluye potencialmente ciclos someros, corrientes variables y temperatura no medida. Temperatura de celda, SoC/tiempo y corriente representativa del grupo 2p requieren procedencia trazable. Sustituir temperatura de celda por ambiente, o corriente de celda por corriente de grupo, exige transformación topológica y térmica documentada; hoy no está validado.

Por tanto, el traslado de la **forma de retención** a 44.1 Ah o 43.5 Ah es hipótesis de escenario. Ni las pruebas de API ni la identidad algebraica `q/q0` validan la evolución real en esas capacidades, las distribuciones de carga entre celdas, ni la capacidad bajo el perfil de la tesis. Los datos públicos experimentales localizados no proporcionan una serie completa independiente de la misma pareja 2p con SoH, temperatura, corriente y protocolo suficientes para contrastar cuantitativamente la trayectoria. No se atribuirán a BLAST las mediciones de Braco que no fueron usadas para una réplica independiente.

## Dependencia temporal: evidencia numérica y política de estudio

Los experimentos aislados locales (`outputs/analysis/blast_original_probe`, `blast_temporal_convergence`, `blast_contract_prototype`) preservan las mismas 121 muestras y cubren los 120 intervalos al comparar 1, 2, 4, 8, 16, 32 y 64 ventanas. Se conserva la instancia BLAST y su historial a través de ventanas. Cambiar la partición sí cambia el resultado: entre 32 y 64 ventanas, `q` varió `+9.9368e-5` en reposo, `+4.9940e-6` en el ciclo a 25 °C y `+8.3581e-6` en la rampa térmica. El reposo de 64 ventanas difirió `−0.0002140764` de la referencia analítica de estrés constante. El resultado de una sola ventana coincide con esa referencia por una rama de inicialización de BLAST; no demuestra exactitud general. El EFC también cambia por ponderación con `q` previo a cada ventana.

**No se declara convergencia:** no existe tolerancia física/numerical predefinida, y 64 ventanas ya contienen tramos de uno o dos intervalos; continuar subdividiendo requeriría inventar muestras. El integrador incremental explícito, el promedio de una tasa no lineal y la actualización de EFC explican sensibilidad al particionado. Son errores/sensibilidades numéricas observados en estas pruebas, no estimadores del error físico ni evidencia de que el modelo de envejecimiento represente el uso real.

Política reproducible previa a cualquier comparación posterior:

1. Congelar versión, commit, Python/dependencias, perfil y archivo de entrada con hash; guardar código, configuración y salida.
2. Comparar sólo particiones anidadas de las muestras medidas originales, cubriendo cada intervalo una vez y manteniendo una instancia/historial BLAST. No interpolar datos para aparentar refinamiento.
3. Reportar `q`, ambas pérdidas, EFC y diferencia respecto al paso previo para cada partición y cada perfil; etiquetar resultados como sensibilidad de paso.
4. Definir antes de ver resultados una tolerancia ligada al uso previsto y a resolución/incertidumbre de datos. Si no hay base para ella o la secuencia de diferencias no la satisface, reportar **sin convergencia demostrada** y no elegir una partición por conveniencia.
5. Separar esa evaluación de error numérico de incertidumbre de transferencia, dispersión entre baterías, sensores, temperatura, SoC, topología 2p y dominio experimental.

## Frontera de SoC y carga almacenada

Hay dos convenciones de libro contable y ninguna está físicamente validada para una actualización de capacidad en esta tesis:

- **Conservar SoC fraccional:** mantener `SoC+ = SoC−` al entrar un nuevo snapshot de `Q_eff`. Conserva continuidad del estado SoC y evita una corriente/throughput inventado; no conserva el producto interpretativo `SoC·Q_eff` como carga almacenada, por lo cual no debe afirmarse conservación física de carga. El cambio de capacidad no equivale a extraer una corriente medida.
- **Conservar algebraicamente `SoC·Q_eff`:** reajustar `SoC+ = SoC− Q_before/Q_after`. Conserva ese producto algebraico, pero genera salto de SoC (puede rebasar `soc_max`; el prototipo produjo 0.900091 desde 0.9) y alteraría OCV. Si el salto se suministra a BLAST como evolución física, crea EFC/throughput ficticio. No hacerlo.

Para **simulaciones de escenario únicamente**, queda aprobada provisionalmente la conservación del SoC fraccional entre ventanas; registrar el cambio de `Q_eff` como evento de contabilidad separado y continuar integrando corriente real según el modelo existente. No crear corriente, energía transferida, Ah throughput ni EFC en el instante de cambio. La carga algebraica `SoC·Q_eff` no se conserva automáticamente y esta política no está validada físicamente. No recortar SoC ni modificar dispatch para ocultar una violación: si el escenario no satisface límites después del snapshot, marcarlo no factible/requiere revisión.

## Exclusión mutua y protecciones de regresión

La futura selección de modo de envejecimiento debe hacer excluyentes las rutas de capacidad:

- Modo lineal: sólo la ley existente modifica SoH/Qeff; BLAST no avanza.
- Modo BLAST de escenario: sólo el snapshot derivado de BLAST modifica SoH/Qeff; el término lineal `k_deg·z_deg` no aplica un segundo factor de pérdida. `z_deg` podría seguir como diagnóstico, pero no producir otro decaimiento.
- La ley de resistencia `R0(SoH)` actual es otra relación constitutiva y no se recalibrará ni desactivará silenciosamente por esta decisión de capacidad. Su validez y acoplamiento a un SoH BLAST deben decidirse explícitamente antes de reportar resultados eléctricos.

Antes de habilitar cualquiera de los modos, pruebas mínimas: (1) caso predeterminado sin snapshot reproduce exactamente la ruta lineal/baseline; (2) pruebas Objective 1 `validate_obj1_regression.py`, `validate_bess_step2.py`, `validate_bess_step3.py`, `validate_bess_soc_operational_limits.py`; (3) invariantes físicos `validate_physical_invariants.py`; (4) regresión de BESS PI/GFM pertinente, protegiendo estados 12/15/16, signos, límites, potencia DC y ecuación del enlace DC; (5) exclusividad con aserciones de que una sola fuente cambia Qeff; (6) contrato BLAST `q(t0)/q(t0)=1`, historial intacto, sin doble 0.7 ni doble pérdida, referencias 44.1/43.5 y `q_nom=66` separadas; (7) frontera SoC sin Ah/EFC sintético y violaciones reportadas, no recortadas. Esta lista es un plan, no resultados de ejecución.

## Condiciones para avanzar a BAT26-33

BAT26-32 queda cerrada como **selección metodológica con limitaciones explícitas**, tras la aprobación del usuario de BLAST-Lite preferido para escenarios, transferencia `q/q0` como hipótesis, frontera SoC fraccional provisional y exclusividad BLAST/lineal. No representa cierre de validación empírica ni autorización para conectar el adaptador en esta tarea. BAT26-33 deberá implementar el puente y el contrato de ventanas sólo después de inspeccionar los cambios locales, definir entradas con procedencia y nivel 2p, conservar la política de paso sin declarar convergencia, proteger exclusividad y completar regresiones; además tratar explícitamente la incertidumbre de `R0(SoH)`. Si se requiere validación física, obtener datos del grupo objetivo antes de afirmarla.

## Plan breve para BAT26-33 (no implementado)

Archivos candidatos a modificación, sujetos a inspección del diff vigente antes de editar:

- `src/bess/aging_capacity.py`: mantener la semántica inmutable de `CapacitySnapshot` y documentar/validar el límite de actualización entre ventanas si se decide que el contrato pertenece aquí.
- `src/bess/model.py`: añadir una selección explícita y mutuamente excluyente de ley; BLAST actualiza capacidad sólo por snapshot y la ruta lineal permanece idéntica cuando se selecciona baseline. No cambiar ecuaciones ECM ni el estado `z_deg` protegido.
- Nuevo módulo aislado `src/bess/blast_lite_adapter.py` (nombre provisional): encapsular la instancia BLAST original, entradas con unidades/procedencia, estado/historial persistente, cálculo de `q/q0` y producción de snapshots. Mantener BLAST fuera de `rhs` y sin solver anidado.
- `src/validation/test_aging_capacity_contract.py` y `src/validation/test_capacity_snapshot_integration.py`, más nuevo test del adaptador si se justifica: comprobar contrato de ventanas, no duplicación y exclusividad.
- Sólo si el flujo exige configuración pública: `src/config.py` o la interfaz de construcción en `src/microgrid.py`/`src/microgrid_bess_pi.py`, con cambios mínimos y compatibilidad de constructor; deben preservarse estados 12/15/16, PI y ecuaciones protegidas.

Contrato de ventanas propuesto: actualizar BLAST una vez por ventana con muestras físicas ordenadas, mantener la misma instancia y acumuladores; comprobar `q(t0)>0`, retención finita en `(0,1]`, `retention(t0)=1` y monotonicidad no creciente para estos perfiles; formar un `CapacitySnapshot` congelado y usarlo en la ventana rápida siguiente. El instante de frontera no aporta una muestra/intervalo ficticio, corriente, energía ni EFC. Una violación de límites de SoC/capacidad se reporta; no se recorta. Registrar versión/hash BLAST, índices/tiempo de muestra y partición. La sensibilidad temporal observada continúa reportándose como no convergencia demostrada mientras no haya tolerancia fundada.

Criterios de aceptación BAT26-33: (1) prueba de `q/q0` y de referencias 66/46/46.2/44.1/43.5 sin doble conteo; (2) prueba de que BLAST y lineal no actualizan capacidad juntos y BLAST no avanza en modo lineal; (3) continuidad de SoC fraccional entre ventanas sin EFC/Ah/corriente/energía artificiales; (4) historia BLAST preservada y orden/partición trazables; (5) valor por defecto y ruta lineal equivalentes al baseline anterior; (6) límites operativos y estados 12/15/16, signos, potencia BESS y ecuación DC-link inalterados; (7) regresiones pertinentes verdes: `validate_obj1_regression.py`, `validate_bess_step2.py`, `validate_bess_step3.py`, `validate_bess_soc_operational_limits.py`, `validate_physical_invariants.py` y validación GFM/PI que toque la ruta; (8) ninguna afirmación de validación experimental sin datos de la misma población objetivo.

Este plan no se ejecutó en BAT26-32 y no modifica implementación.

## Evidencia local auditada

- `outputs/analysis/blast_original_probe/README.md`, `results.json`: API original; reposo/ciclado/rampa sintéticos; referencias 46/46.2 Ah.
- `outputs/analysis/blast_temporal_convergence/README.md`, `results.json`, script y pruebas: partición temporal, pasos, cobertura y resultados; tres pruebas reportadas como pasadas en el informe del experimento.
- `outputs/analysis/blast_contract_prototype/README.md`, `ERROR_BUDGET.md`, `results.json` y pruebas: contrato read-only e hipótesis de transferencia; seis pruebas reportadas como pasadas.
- `src/bess/aging_capacity.py`: snapshot inmutable sin dependencia BLAST.
- `src/validation/test_aging_capacity_contract.py` y `test_capacity_snapshot_integration.py`: pruebas de contrato e integración sintética presentes. Los resultados documentados de las seis pruebas del prototipo corresponden al directorio de experimento, no demuestran que todas las pruebas de `src/validation` se hayan ejecutado ahora.

No se ejecutaron pruebas en esta preparación documental. No se modificó el solver, el ECM ni parámetros físicos.
