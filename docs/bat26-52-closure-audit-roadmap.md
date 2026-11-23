# BAT26-52 — Auditoría final del plan y backlog de la siguiente iteración

**Fecha de corte:** 6 de noviembre de 2026. **Naturaleza:** auditoría del conjunto BAT26-20 a BAT26-52, no terminación científica de la tesis ni demostración de despacho óptimo. Fuentes cotejadas: AGENTS.md, src/config.py, docs/model_assumptions.md, docs/bat26-38-validation-test-plan.md y BAT26-45 a BAT26-51.

## Dictamen

El trabajo disponible demuestra consistencia de implementación y resultados de escenarios sintéticos: BLAST-Lite con modelo original auditado, 1000 jornadas a 25 °C, SoH 54.323934 % y Qeff 35.853796 Ah para la pareja Nissan Leaf 2p de referencia de 66 Ah y capacidad inicial de tesis 44.1 Ah. Una descarga 1RC de +8 A en el puerto 2p durante una hora produjo mayor caída de SoC a menor capacidad; la carga ideal entre SoC 0.6 y 0.1 disminuyó de 22.050 a 17.927 Ah. BAT26-47 identificó sensibilidad no monótona a la partición BLAST. BAT26-48 dejó un contrato de SoH/SoC y costo simbólico, sin optimización. BAT26-49 documentó fuentes y ecuaciones. BAT26-50 y BAT26-51 prepararon seis figuras y dossier; Codex reportó ZIP y hashes verificados.

**Límite central:** PASS numérico o documental no equivale a validación experimental de una batería identificada. El GFM en BAT26-46 permaneció cargando, no demostró soporte en descarga; no existe mapeo físico aprobado del puerto 2p al bus DC de 340 V, banco dimensionado, ni despacho económico ejecutado. Los archivos binarios ZIP/PNG/CSV/manifiesto permanecen fuera del repositorio y deben copiarse a un medio persistente antes de una reunión.

## Matriz de estado y necesidad científica

| Componente | Estado verificado | Puerta de validación pendiente |
| --- | --- | --- |
| BLAST / SoH | Curva sintética, hashes y sensibilidad 1/2/4 ventanas | Datos Leaf 2p originales, RPT, I/V/T, validación independiente; criterio de convergencia fundamentado |
| ECM 1RC | Relación Thevenin, pruebas algebraicas y respuesta a +8 A | OCV de reposo, R0 instantánea, R1/C1 medidos para Leaf 2p, HPPC |
| GFM VSG | Arquitectura de 15 estados y M=80, D=1500 funcionales | Justificar unidades/escala M,D y ensayo de descarga positiva bajo cuatro SoH |
| Variante PI externa | Arquitectura opcional de 16 estados definida y protegida en AGENTS.md | Comparación bajo idéntica planta y demanda sin mezclar estados ni dos PI |
| FOVIC / comparaciones de control | No es controlador final implementado según AGENTS.md | Decidir alcance de FOVIC, droop, V-f y justificación del aporte del Objetivo 2 |
| Banco BESS–DC/DC | Capacidad Ah de pareja 2p; bus DC idealizado | Número serie/paralelo, tensión real, electrónica bidireccional, eficiencia, rating y límites BMS |
| IEEE 33 | Posprocesamiento secuencial unidireccional | Escalamiento a potencia representativa; si se exige, co-simulación bidireccional explícita |
| Despacho Objetivo 3 | Contrato y proxy de degradación simbólico, 7 tests | Definir servicio, horizonte, demanda/PV, restricción terminal SoC, precios y resolver problema optimizador |
| Dossier del director | BAT26-49 a 51 con fuentes, figuras y ZIP reportado | Conservar ZIP y manifest íntegros fuera del workspace temporal; aprobación científica del director aún pendiente |

## Orden recomendado de decisión

**D1 — Frontera y escala.** Antes de transformar 44.1 Ah de una pareja 2p en kWh de banco o potencia en bus, escoger escala física (pareja, banco para 3 kW o sistema representativo de IEEE 33) y especificar topología DC/DC o equivalente paramétrico justificado. Si se adopta un equivalente para investigación sin validarlo en hardware, etiquetarlo como escenario y conservar el bloqueo de potencia física real.

**D2 — Ensayo de soporte GFM.** Conservar como referencia el VSG de 15 estados, M=80 y D=1500, y diseñar una perturbación que realmente produzca i_bess positiva y p_bess_dc positiva; contrastar los mismos cuatro niveles de SoH y verificar límites de corriente/potencia, SoC, frecuencia, Vdc y estabilidad del solver. BAT26-46 en carga no satisface esta prueba. Mantener separada la posible comparación con PI de 16 estados.

**D3 — Justificación M/D y alcance de control.** Documentar unidades, normalización y sensibilidad de M/D. Acordar si el VSG clásico es control de referencia suficiente o si FOVIC y comparaciones droop/V-f son indispensables para la contribución original. No cambiar los valores actuales sin pruebas protegidas y decisión documentada.

**D4 — Datos y validación física.** Auditar una serie de pareja Leaf 2p identificada que tenga corriente, tensión, temperatura de celda, RPT repetidas, HPPC y condiciones comparables; establecer conjuntos de calibración/validación independientes. Si no existe, delimitar formalmente resultados como escenarios y no calcular RMSE físico ni vida certificada.

**D5 — Objetivo 3.** Tras fijar frontera y límites, definir un problema reproducible con perfiles de generación FV y demanda, horizonte, SoC inicial/final y restricciones de envejecimiento. Comparar políticas A/B sobre igual física y datos, con o sin penalización de desgaste, sin duplicar costo por EFC y pérdida Ah. Si el costo es hipotético, declarar análisis de sensibilidad y no ahorro comercial real.

**D6 — IEEE 33.** Justificar potencia equivalente de inyección e interconexión con el benchmark; una carga local de 3 kW no debe presentarse como sistema de varios MW sin escalado. Posprocesamiento no significa co-simulación eléctrica dinámica.

## Evidencia mínima para aprobar cada puerta

| Puerta | Evidencia concreta de salida | Si no existe |
| --- | --- | --- |
| D1 escala | Diagrama de conexiones, N_s/N_p, V_bat, Vdc, ratings, eficiencia y convenciones de puertos | Continuar bloqueando E_bus y P_bus desde Ah2p |
| D2 descarga | Transitorios de los cuatro SoH con corrientes/potencias firmadas positivas y métricas GFM | Declarar que solo se probó carga en BAT26-46 |
| D3 control | Unidades y estudio de sensibilidad/selección M/D; decisión 15/16 estados/FOVIC | Conservar M=80, D=1500 como referencia, no óptimo universal |
| D4 validez | Datos medidos con origen/RPT/HPPC y partición calibración-validación | REVIEW científico, sin métricas experimentales inventadas |
| D5 despacho | Modelo de optimización, perfiles, restricciones, solver, objetivos y resultados comparativos | No anunciar despacho implementado ni costo real |
| D6 IEEE 33 | Balance y escala documentados, tipo de acoplamiento declarado | Solo análisis secuencial one-way |

**Prioridad propuesta para reunión:** D1 (frontera física), D2 (evidencia de descarga) y D3 (control M/D); D4 condiciona el alcance de las afirmaciones científicas; D5 será la siguiente implementación formal del Objetivo 3; D6 se ajustará a lo acordado. Si el director prioriza el despacho, iniciar D5 como escenario hipotético puede ser viable, pero debe respetar el bloqueo físico de D1.

## Repositorio, entrega y criterio de cierre

Rama científica actual: feat/blast-aging-adapter. Main no se ha integrado con esta serie de PR y no debe fusionarse sin auditoría. Los vectores de 15/16 estados, el convenio de corriente positiva de descarga, la ecuación del bus y M=80/D=1500 están protegidos por AGENTS.md. PR #47 fusionado en esa rama mediante squash e5856fdfb6577730664e1aa740c5c2a39c2c7cfc. El ZIP portátil reportado por Codex tiene SHA-256 ef3ca61c27c5e73bb275e67e5782071f6a5239faee09c208ffa14c72eccbd6d3, no recalculado aquí y no versionado como binario GitHub.

Este documento satisface la parte de auditoría de BAT26-52 **como borrador de backlog**; el cierre administrativo exige cotejo final en GitHub/Roma y registrar la decisión de siguiente iteración. Completar 33/33 tareas del plan no significa haber completado los tres objetivos de la tesis, validación experimental ni despacho.

**Estado:** PR documental de BAT26-52 preparado para revisión. Ningún parámetro, ecuación física, controlador ni archivo histórico se modificó.