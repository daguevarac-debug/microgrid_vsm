# BAT26-38 — plan de pruebas y criterios de aceptación

**Propósito.** Especificar cómo verificar implementación, consistencia matemática y límites de evidencia del envejecimiento BLAST-Lite acoplado por ventanas al BESS 1RC, conservando linear como referencia. Este documento es un protocolo; no ejecuta ni duplica las campañas integradas ya aprobadas y no declara validación física.

**Estado:** plan documental listo para revisión; BAT26-38 sigue en curso hasta revisión del usuario. Ningún caso de esta matriz habilita por sí mismo perfiles operativos BLAST.

## 1. Orden de ejecución y reglas de campaña

1. **Antes de cambios de software:** registrar rama/commit, git status, intérprete y dependencias, parámetros, modo de envejecimiento, SoC/SoH/Q iniciales, perfil con unidades/signos, semilla si aplica, partición temporal y hashes de entradas. No reemplazar salidas existentes.
2. **Pruebas unitarias del contrato:** ejecutar las filas unitarias de la matriz. No invocar BLAST en tests que prueban sólo modo linear; BLAST usa el worker de Python 3.12.10 ya instalado y versionado.
3. **Comparación de modos:** mismo BESS, controlador, estado inicial, perfil rápido y condiciones de frontera. Ejecutar default y aging_mode='linear' como control de compatibilidad; luego usar modo blast con snapshots explícitos derivados de un perfil sintético declarado. No estimar un modo a partir de resultados del otro.
4. **Regresiones de microrred:** correrlas sólo tras cualquier cambio de implementación que pueda afectarlas, usando como referencia los resultados ya aprobados. No reabrir la investigación HPPC ni repetir barridos/campañas temporales ya hechos.
5. **Comparación temporal:** mantener los mismos datos originales y cobertura exacta de intervalos para cada partición. Reportar por partición q, qLoss_t, qLoss_EFC, EFC, Q_eff, SoH, tiempo, número de ventanas y hash. No fabricar puntos/interpolaciones para subdividir. No escoger un tamaño de paso por parecer más convergido.
6. **Física:** comparar con experimento sólo cuando perfil, equipo, escala, condiciones, incertidumbre y partición de ajuste/validación estén trazados. En su ausencia, clasificar el resultado REVIEW por límite de evidencia, aunque las pruebas de software pasen.

Las capacidades son referencias separadas: q_nom_ref=66 Ah, cap_2ndLife=46 Ah, qNew(0)·66=46.2 Ah, caso de tesis Q_case=44.1 Ah y caso experimental Braco Q_case=43.5 Ah. No recalcular una como si fuera otra ni multiplicar el caso por 0.7.

## 2. Matriz de casos

| ID | Caso y herramienta existente | Procedimiento verificable | Resultado exigido |
|---|---|---|---|
| M1 | Capacidad/SoH inicial y snapshot: test_aging_capacity_contract.py, test_capacity_snapshot_integration.py | Construir CapacitySnapshot(66,Q_case,1), luego snapshots con q/q0 conocido; probar Qcase 44.1 y, como caso separado, 43.5. | Q_eff=Q_case·retention, SoH=Q_eff/66, retención inicial 1, Q fijo durante cada ventana. No doble factor 0.7 ni pérdida previa. |
| M2 | SoH/capacidad constantes: mismo contrato y test_blast_lite_adapter.py | linear: corriente cero deja z_deg y SoH lineales invariantes. blast: snapshot fijo mantiene Q/SoH en toda integración rápida aunque z_deg se use como diagnóstico. En reposo BLAST sí puede actualizar pérdida calendario entre ventanas transcurrido tiempo. | Distinguir constante dentro de ventana de envejecimiento calendario entre ventanas; ningún doble fade. |
| M3 | Descarga y carga; signos: test_soc_variable_capacity_boundary.py, test_bess_sign_coherence.py, test_dclink_dynamics.py | Corriente positiva y negativa en BESS; observar derivada SoC, potencia BESS, corriente de enlace DC y respuesta neta GFM. | i>0 implica dSoC/dt<0, p_bess_dc=Vdc·i>0 para Vdc positiva y mayor soporte DC; i<0 invierte esos signos y reduce disponibilidad neta. |
| M4 | Ciclo parcial/operativo completo: test_blast_lite_adapter.py más perfiles del banco BAT26-36 | Perfil sintético con corriente y SoC consistentes en rango permitido: por ejemplo 0.7→0.3→0.7 parcial y 0.9→0.1→0.9 excursión completa del rango operativo. Comparar Ah absoluto y EFC según BAT26-36; guardar EFC BLAST original por separado. | Sin contar dos veces intervalos o ventanas; carga y descarga cuentan en throughput absoluto; una frontera compartida es sólo una muestra, no un intervalo nuevo. El ciclo matemático 1→0→1 sólo puede quedar como test aislado del contador BLAST, explícitamente fuera del dominio operativo SoC 0.1–0.9. |
| M5 | Límites SoC: test_blast_lite_adapter.py, test_soc_variable_capacity_boundary.py, validate_bess_soc_operational_limits.py | Probar límites 0.1/0.9 y solicitudes hacia afuera y hacia adentro; comprobar rechazo del estado inválido en frontera. | Bloquear descarga en el mínimo y carga en el máximo; aceptar el sentido de recuperación. Nunca clipping silencioso ni corriente ficticia por rebase. |
| M6 | Exclusividad y ruta de referencia: test_blast_lite_adapter.py, test_capacity_snapshot_integration.py | Comparar constructor default con aging_mode='linear' sobre idéntico estado; probar configuraciones inválidas linear+snapshot / blast sin snapshot. En BLAST, cambiar z_deg no cambia Q/SoH del snapshot; en linear, no se llama ni avanza BLAST. | Default y explicit linear conservan baseline; un solo mecanismo actualiza capacidad. Para un punto inicial equivalente retention=1, la capacidad/SoH inicial concuerda. No exigir que BLAST y lineal produzcan la misma degradación. |
| M7 | Continuidad/historial entre ventanas: test_blast_lite_adapter.py, test_capacity_snapshot_integration.py, test_soc_variable_capacity_boundary.py | Secuencia con punto frontera compartido; verificar timestamps/SoC/T continuos, estado completo 15/16 copiado, hash por ventana, acumuladores BLAST monótonos y capacidad relativa anclada. | Cada intervalo físico aparece una vez; BLAST no se reinicia entre ventanas del mismo caso; SoC, Vrc, z_deg, controlador y PI no se rebasan. Frontera sin corriente, potencia, Wh, Ah o EFC artificial. |
| M8 | Sensibilidad al paso: scripts/resultados existentes outputs/analysis/blast_temporal_convergence/ y blast_original_probe/ | Reproducir sólo mallas de puntos medidos ya aprobadas y particiones anidadas existentes; mismo perfil/hash e historia. Registrar diferencias q, pérdidas/EFC por partición. | PASS de reproducibilidad exige repetir exactamente salida para el mismo código, entrada y partición, y cobertura sin huecos/solapes. No hay umbral aprobado para convergencia: discrepancia entre pasos se reporta REVIEW, sin declarar convergencia o FAIL físico. |
| M9 | Identidad de energía RC: test_bess_rc_energy_identity.py | Verificar para carga y descarga OCV·i = Vt·i + i²R0 + Vrc²/R1 + d(½C1Vrc²)/dt − ½Vrc²·dC1/dt, con C1(SoC) diferenciable dentro de cada tramo de tabla. | Identidad algebraica satisfecha con tolerancia de redondeo/derivación numérica fijada por la prueba. No es medida de pasividad ni energía electroquímica. En nudos de interpolación la derivada se trata por tramos; no extrapolar suavidad. |
| M10 | Identidad de energía del capacitor DC: ampliar con prueba unitaria pequeña asociada a test_dclink_dynamics.py (aún no existe una aserción explícita de energía) | Para Cdc constante y E_C=½Cdc·Vdc², verificar dE_C/dt=Cdc·Vdc·dVdc/dt=Vdc(ipv+i_bess−idc_inv). Cubrir flujo balanceado y ambos signos de i_bess. | Identidad del campo vectorial/algebra de DC PASS dentro de error de máquina. Si se integra una ventana, error admisible debe derivarse de rtol/atol del solver y método de cuadratura antes de comparar; no establecer porcentaje ad hoc. |
| M11 | DC/DC algebraico: test_dc_dc_adapter.py | Reutilizar pruebas ya existentes de raíces, sentidos, eficiencias ingresadas, límites y casos inviables sólo para la función algebraica independiente. | PASS matemático del adaptador con parámetros sintéticos declarados; nunca etiquetarlo prueba del convertidor, su eficiencia real o del balance batería–bus. |
| M12 | Regresiones protegidas de Objetivo 1, BESS, GFM y PI | Mantener comandos del apartado 4 y revisar estados/signos y criterios existentes sin cambiar sus tolerancias. | Ninguna regresión nueva. Conservar resultado histórico GFM integrado REVIEW en +40 %/Vdc; no exigir que desaparezca para aprobar el software. |
| M13 | Comparación física BLAST/lineal en segunda vida | Pendiente de adquisición de datos: mismo grupo 2p identificado, condiciones, SoH, temperatura de celda, protocolo y canales; fijar por adelantado train/validation y métricas. | Por ahora REVIEW / no evaluable. No inventar perfiles medidos ni umbrales. PASS físico sólo tras cumplimiento de protocolo de experimento preregistrado; FAIL físico sólo ante discrepancia que exceda incertidumbre y tolerancia justificadas a priori. |

## 3. Tres niveles de comprobación de energía

1. **Identidades algebraicas del modelo:** el test RC comprueba la descomposición instantánea asociada al ECM vigente y el término de C1(SoC) variable. La identidad del capacitor comprueba el campo Cdc·dVdc/dt; ambas permiten tolerancia de punto flotante/estimación de derivadas. Son PASS/FAIL de implementación matemática, no validación física.
2. **Contabilidad integrada de puertos del modelo:** integrar por separado Vdc·i_bess, Vdc·idc_inv y E_C sobre una simulación con estados finitos; el residuo aceptable se obtiene de los errores de integración declarados. El terminal del inversor no es PCC sin pérdidas/modelo completo, y Vt·i_bess del ECM no equivale automáticamente a Vdc·i_bess.
3. **Balance físico batería–DC/DC–bus:** aún no validado. Requiere topología serie/paralelo confirmada, corriente del puerto 2p medida/derivada con transformación acreditada, tensión/calibración y eficiencias dependientes de sentido, pérdidas/térmica, sincronía y mediciones independientes de energía a ambos puertos. Ningún test del adaptador DC/DC algebraico ni identidad del capacitor cierra ese balance.

No usar SoC·Q_eff como Wh. No incluir el cambio de snapshot en una integral como energía, corriente, Ah o EFC. Para balances físicos, declarar tensión/corriente y dirección de cada puerto y convención de signo antes de integrar.

## 4. Criterios globales PASS / REVIEW / FAIL

### PASS

- Pruebas exactas de contrato, signos, modos, estados y fronteras pasan reproduciblemente.
- Las identidades de RC y DC satisfacen la relación analítica dentro de la tolerancia computacional derivada; integración de energía satisface el error atribuible al solver/cuadratura previamente especificado.
- El modo default/linear sigue equivalente a los resultados de baseline existentes; BLAST sólo cambia capacidad en su modo y no se suma a k_deg·z_deg.
- Repetir el mismo perfil, hash, versión, partición y estado/historia da resultado determinista. PASS sólo indica reproducibilidad/consistencia interna.

### REVIEW

- Software correcto, pero validación física ausente o señales no acreditadas.
- Diferencias entre particiones temporales sin tolerancia numérica/física previamente aprobada; registrar todos los valores como sensibilidad, sin afirmar convergencia.
- Un escenario conserva el estado del solver, pero el criterio operativo de diseño existente no se cumple; en particular, el GFM +40 %/Vdc conserva su REVIEW de referencia.
- Resultado del DC/DC algebraico sin aparato, parámetros medidos o balance experimental de ambos puertos.

### FAIL

- Falla una aserción algebraica más allá de precisión/redondeo justificados, hay signo/unidad/puerto incorrecto, estado NaN, intervalo omitido o contado dos veces, reinicio de BLAST, snapshot inconsistente, doble envejecimiento, clipping silencioso, límite SoC vulnerado sin rechazo/supervisión, cambios en estados protegidos o regresión de baseline.
- En evaluación física preregistrada, una discrepancia excede incertidumbre combinada y tolerancia fijada antes de examinar resultados. En ausencia de esos datos/criterios, usar REVIEW, no fabricar FAIL físico.

**Tolerancias.** Las tolerancias de identidades unitarias se atan a doble precisión y al cálculo de derivadas usado en cada test; para ODE se fijan desde los rtol/atol existentes y el error de cuadratura. No proponer un porcentaje uniforme para resultados de magnitudes distintas. Para datos experimentales, documentar resolución de sensor, calibración, sincronización y propagación de incertidumbre antes de definir bandas. No hay tolerancia aceptada para convergencia temporal de BLAST, por tanto esa decisión siempre permanece REVIEW hasta justificar una con base científica.

## 5. Comparación de modos y protección de regresiones

### Control linear predeterminado

- Confirmar constructor default ≡ aging_mode='linear' con mismo estado, parámetros y perfil.
- Ejecutar pruebas de ley lineal con z_deg=0, throughput positivo y saturación al SoH mínimo; verificar SoH=max(soh_min, soh_init−k_deg·z_deg) y Qeff=Qnom·SoH según código.
- Rechazar snapshot suministrado en modo linear, y comprobar que BLAST no se importa/avanza en esa ruta.

### Modo BLAST sintético

- Usar perfiles etiquetados synthetic, temperatura sintética de celda y corriente sintética 2p con unidades/signo; no derivar corriente grupo 2p de la corriente del puerto DC.
- Comparar mismo estado inicial y snapshot retention=1 con linear al inicio para igualdad de capacidad/SoH, Coulomb counting y signos, no igualdad de pérdidas futuras.
- Para snapshots sucesivos, verificar ecuación q/q0, monotonicidad/validez de q conforme contrato, historia conservada, capacidad fija dentro de cada integración y cambio sólo entre ventanas.
- Hacer variar z_deg bajo snapshot para demostrar que permanece diagnóstico y no aplica segunda pérdida; hacer variar BLAST sólo en modo BLAST. Probar que combinaciones inválidas se rechazan.
- Reportar q, ambas pérdidas, EFC BLAST, Qeff, SoH y estado por ventana; la diferencia frente a linear es comparación de leyes de escenario, no superioridad experimental.

### Regresiones obligatorias tras cualquier cambio de implementación

1. **Objetivo 1:** python src/validation/validate_obj1_regression.py.
2. **BESS:** python src/validation/validate_bess_step2.py; python src/validation/validate_bess_step3.py; python src/validation/validate_bess_soc_operational_limits.py.
3. **Invariantes y GFM:** python src/validation/validate_physical_invariants.py; python src/validation/validate_gfm_integrated_system.py.
4. **PI:** python src/validation/validate_dc_link_pi_scenarios.py; además suites unitarias PI/estado pertinentes si la ruta cambia.
5. **Pruebas dirigidas:** comandos unittest discover del inventario en la tabla, más el futuro test explícito de energía del capacitor DC.

Comandos de referencia desde la raíz del repositorio (sólo suites unitarias; ejecutar al implementar/cambiar la ruta correspondiente):

    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_blast_lite_adapter.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_aging_capacity_contract.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_capacity_snapshot_integration.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_soc_variable_capacity_boundary.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_bess_rc_energy_identity.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_dclink_dynamics.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_bess_sign_coherence.py -v
    .venv\Scripts\python.exe -m unittest discover -s src\validation -p test_dc_dc_adapter.py -v

La última suite verifica sólo el adaptador algebraico; no sustituye las comprobaciones del balance físico indicadas en la sección 3.

No re-ejecutar campañas integradas ni sweep temporal por crear este documento. Si se modifica una ruta física, correr sólo estos gates relacionados y conservar el resultado +40 % en REVIEW si persiste según criterio original.

## 6. Puertas que bloquean perfiles BLAST operativos

El adaptador actual acepta sólo entradas sintéticas. Antes de permitir modo operativo deben acreditarse, sin campos inferidos silenciosamente:

- **Corriente:** sensor o transformación medida/identificada de la corriente al grupo 2p, sentido de carga/descarga, offset, ancho de banda, escala de serie/paralelo y sincronía con SoC; nunca copiar i_bess del bus como current_2p_a sin puente validado.
- **Temperatura:** temperatura de celda representativa, sensor/ubicación/calibración y sincronía; ambiente no sustituye temperatura de celda.
- **SoC y capacidad:** definición/estimador y su incertidumbre, ventanas temporales completas, historial desde q(t0) y referencia Qcase; evitar discontinuidad o rebase entre ventanas.
- **Escala eléctrica:** unidad 2p efectiva, topología módulo/pack, mapa OCV/RC, tensión/corriente de sus puertos y DC/DC con eficiencias por sentido, límites y pérdidas identificados.
- **Límites/dominio:** perfil dentro del rango documentado de BLAST y de límites BESS; los ensayos cíclicos originales de la clase se restringen alrededor de 25 °C, DoD 100 % y 1C. Perfil fuera de ese dominio sólo se etiqueta como extrapolación de escenario.
- **Procedencia:** instrumento, calibración, tasa de muestreo, licencia/dataset, hash, faltantes/duplicados, preparación sin interpolación oculta y separación de ajuste frente a validación.

Hasta cerrar estas puertas, una ejecución sintética sirve para verificar software y sensibilidad, no para describir degradación real del BESS.

## 7. Resultados previos disponibles y límites

| Fuente | Evidencia disponible | Lectura para este protocolo |
|---|---|---|
| BAT26-33 bridge report | 10 pruebas adaptador, 11 contrato, 6 integración; logs reportan Objective 1/invariantes PASS; GFM integrado REVIEW en +40 %/Vdc; PI 20/40 PASS. | Control software previo; no perfiles operativos acreditados ni validación física. |
| BAT26-34 | test_soc_variable_capacity_boundary.py: 4 PASS (repetido en checkout anterior). | SoC fraccional, carga algebraica y frontera sin clipping. |
| BAT26-35 | Matriz documental de valores OCV/1RC y limitaciones. | Parámetros eléctricos provisionales; no identifica energía química ni transferibilidad. |
| BAT26-36 | 7 PASS EFC/BLAST/BESS, 4 PASS frontera y resultados JSON reproducidos según Roma. | Consistencia sintética; EFC BLAST y resultados varían con q/partición; no tolerancia de convergencia aprobada. |
| BAT26-37 | Repetido para esta revisión: RC energy 1 PASS, DC/DC algebraico 15 PASS, signos 3 PASS, dinámica DC 5 PASS, snapshot integration 6 PASS. | Identidades/unit tests, no balance físico integral batería–convertidor–bus. |
| Sensibilidad temporal BLAST (BAT26-32/33) | Con 121 muestras y particiones 1–64, diferencias q(32→64) reportadas: reposo +9.9368e-5, ciclo 25 °C +4.9940e-6, rampa +8.3581e-6; sin criterio/tolerancia predefinidos. | No declarar convergencia. Usar como base para el informe, no repetir sweep en BAT38. |

No asumir que todos los conteos de prueba anteriores se ejecutaron hoy: sólo las cinco suites enumeradas de BAT26-37 se repitieron durante esta revisión. Los resultados de otras baterías de pruebas proceden de sus informes/logs previos.

## 8. Dictamen BAT26-38

El criterio de BAT26-38 puede satisfacerse documentalmente con este plan y el inventario de pruebas existentes. El documento especifica casos, comandos, gates, tolerancias defendibles, categorías PASS/REVIEW/FAIL, evidencias previas y bloqueos de perfiles operativos. No implica ejecutar de nuevo campañas aprobadas, implementar la futura prueba del capacitor DC, probar convergencia de BLAST ni validar energía física experimental. Se deja la tarea abierta para revisión del usuario; BAT26-38 no se marca completada automáticamente.
