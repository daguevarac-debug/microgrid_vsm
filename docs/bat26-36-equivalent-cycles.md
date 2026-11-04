# BAT26-36 — conteo de ciclos equivalentes de uso

## Alcance y decisión

Para degradación en modo BLAST se utiliza **exclusivamente el EFC interno que genera la clase original**, con su `q` e historial; se registra junto con `qLoss_t`, `qLoss_EFC`, perfil, versión y partición. No se alimenta al modelo un segundo contador de EFC ni se añade además la pérdida lineal basada en `z_deg`. Para el modo lineal se conserva la ley existente con `z_deg`, sin hacer avanzar BLAST.

Para seguimiento operativo se propone **Ah absolutos de throughput**, con Ah de descarga y carga por separado, indicando puerto, signo y unidad física; en paralelo, reportar EFC respecto a capacidad inicial del caso para comparación intuitiva, y EFC respecto a capacidad efectiva si se busca expresar el uso en capacidades disponibles de cada ventana. Para comparaciones futuras de despacho reportar al menos throughput, `EFC_ini`, `EFC_eff`, SoH/Q inicial y final, duración, fracción de ciclo/DoD y condiciones; añadir energía y potencia por separado con su puerto, sin convertir EFC en costo o vida útil por sí solo. Esto es una convención de reporte, no una ley de degradación adicional ni evidencia de que los contadores sean equivalentes.

`z_deg` existente integra `|i_bess|/3600`, pero es throughput de la corriente del **puerto del modelo**. No se interpreta automáticamente como Ah de una pareja 2p: el modelo de bus/DC-DC idealizado carece de transformación física validada de corriente, topología y eficiencias. El adaptador actual exige una corriente 2p sintética para trazabilidad y hash, pero **no la pasa a BLAST ni comprueba el balance corriente–SoC**. Sus pruebas no acreditan un perfil operativo físico.

## Definiciones y dimensiones

Sean `t` en segundos, `i` en A a un puerto especificado, `Q_0=Q_init_case` en Ah, `Q_eff(t)>0` en Ah y `s=SoC` adimensional. Convención existente: `i>0` descarga y `i<0` carga; se supone eficiencia coulómbica unitaria como en la ODE. EFC es adimensional y un ciclo equivalente completo corresponde aquí a un throughput absoluto de **dos** capacidades de referencia, sin asumir que el ciclo termine al SoC inicial.

| Indicador | Definición desde t0 | Unidad y referencia |
|---|---|---|
| Descarga | `A_dis = ∫ max(i,0) dt / 3600` | Ah, por el puerto declarado |
| Carga | `A_ch = ∫ max(-i,0) dt / 3600` | Ah, magnitud positiva, mismo puerto |
| Throughput absoluto | `A_abs = A_dis + A_ch = ∫ |i| dt/3600` | Ah; no es energía en Wh |
| Carga neta extraída | `A_net = A_dis − A_ch` | Ah con signo; no sustituye `A_abs` |
| EFC inicial | `EFC_ini = A_abs/(2 Q_0)` | adimensional; Q0 fijo de escenario, 44.1 Ah en tesis o 43.5 Ah en caso Braco |
| EFC efectivo variable | `EFC_eff = ∫ |i|/[2·3600·Q_eff(t)] dt` | adimensional; normalización local por capacidad efectiva; con snapshots, sumar cada ventana |
| EFC interno BLAST | `Σ_k q_k^− · (1/2) Σ_j |s_k,j − s_k,j−1|` | adimensional; q del **inicio de cada llamada**, relativo al inicio original de segunda vida de la clase |

Para `Q_eff` fijo dentro de la ventana `k`, la ODE de BAT26-34 da `ds/dt=−i/(3600 Q_eff,k)`. Por tanto, sin saltos de coordenadas ni omisiones, `ΔEFC_eff,k = (1/2)∫|ds|` y, para muestras que representen exactamente la variación total de SoC, `ΔEFC_eff,k=(1/2)Σ|Δs|`. Si los datos de SoC omiten oscilaciones o tienen ruido, esa suma puede subcontar o sobrecontar; no equivale automáticamente a integrar una corriente real. Para `Q_eff=Q_0` en todo el intervalo, `EFC_ini=EFC_eff`; al variar Q, normalmente no. `A_dis`, `A_ch` y `A_abs` no se duplican por signo ni se normalizan por capacidad para obtener Ah.

En el BESS actual `dz_deg/dt=|i_bess|/3600`, de modo que `z_deg(t)−z_deg(t0)=A_abs` a la escala de esa corriente. El valor absoluto de `z_deg` puede incluir historia previa; se deben guardar inicio y final, no reinterpretar `z_deg` como EFC. El solver integra el estado existente; aquí no se propone otro estado ni una modificación de ecuaciones. En modo BLAST `z_deg` permanece diagnóstico y no reduce capacidad por segunda vez.

## EFC de BLAST-Lite 1.1.0

Se inspeccionó directamente `BatteryDegradationModel._extract_stressors()` instalado: `delta_efc = 0.5*sum(abs(diff(soc))) * self.outputs['q'][-1]`. La función usa las muestras de SoC de esa llamada, incluido el tramo compartido solo como punto, y toma `q` **antes** de actualizar la ventana. Luego `update_battery_state` acumula ese incremento en `stressors['efc']`; la clase Leaf utiliza `delta_efc` en la actualización incremental de `qLoss_EFC`. No usa la corriente `current_2p_a` enviada al adaptador para calcular el EFC.

`q` inicia en 1 respecto de la capacidad de arranque de segunda vida del propio modelo; `qNew=0.7q` es la salida de referencia nueva. El comentario de la clase base menciona Ah por Ah nominal y reescala por salud, pero el código no multiplica ni divide por un atributo Ah explícito al calcular EFC. Una interpretación como throughput normalizado a una capacidad inicial de segunda vida requiere suponer `Q_BLAST,k = Q_SL,0*q_k` y un perfil de SoC consistente: entonces `ΔEFC_BLAST = ΔAh/(2 Q_SL,0)`. **El código por sí solo no elige inequívocamente entre 46 y 46.2 Ah** como conversión física. No confundir `q` con `qNew` ni afirmar que EFC interno es directamente Ah/(2·66) para el caso de tesis.

Con la hipótesis adicional del puente `Q_eff,k=Q_case,0*q_k/q_case_start`, misma partición, SoC consistente con la corriente y capacidad fija en cada ventana, resulta para los **incrementos posteriores al anclaje**:

```text
ΔAh_k = Q_eff,k Σ_j |Δs_k,j|
ΔEFC_ini,k = (q_k/q_case_start) · (1/2)Σ_j |Δs_k,j|
ΔEFC_BLAST,k = q_case_start · ΔEFC_ini,k
ΔEFC_eff,k = (1/2)Σ_j |Δs_k,j|.
```

Es una identidad **condicional**, no un factor universal: falla si la capacidad o corriente del perfil no corresponde a la hipótesis, si las ventanas de Q y BLAST no coinciden, si los datos no representan la trayectoria completa o si se comparan acumulados con orígenes distintos. El ancla del adaptador cambia `q_case_start` pero no reinicia EFC BLAST: para un caso que comienza tras historial hay que restar también el EFC acumulado al inicio. El test incluye historial anterior y verifica la identidad sin alterar el modelo. El EFC inicial/efectivo no se usa para reemplazar el EFC interno en `qLoss_EFC`.

La partición también importa para BLAST: el estado se actualiza entre llamadas, por lo que el siguiente `q_k` puede disminuir incluso con el mismo perfil continuo. La integración incremental de pérdidas y los promedios de estrés también varían al cambiar ventanas. El throughput de corriente de un perfil físico idéntico sí es aditivo: sumar cada intervalo exactamente una vez, sin volver a contar el punto de frontera. Ningún resultado de refinamiento aislado demuestra convergencia del desgaste; ver el presupuesto de BAT26-32/33.

## DoD, ciclos parciales y límites

Una excursión monótona de SoC `s_alto→s_bajo` tiene `DoD=s_alto−s_bajo` si está expresado en fracción del rango completo de SoC. Una descarga de 0.9 a 0.1 tiene DoD 0.8 y cuenta 0.4 EFC bajo normalización efectiva constante; la carga inversa añade 0.4. Un ciclo cerrado 0.7→0.3→0.7 tiene DoD 0.4 y 0.4 EFC efectivos; no son 0.4 ciclos completos medidos experimentalmente si la secuencia tiene historia, asimetría o capacidad cambiante. En secuencias con múltiples inversiones, `max(s)−min(s)` describe el rango de la ventana, no la distribución de profundidades: una definición por ciclo o rainflow debe especificar algoritmo, fronteras y medios ciclos pendientes. El EFC por throughput no registra por sí solo DoD, C-rate, temperatura o dirección.

La supervisión del modelo bloquea descarga en `s≤0.1` y carga en `s≥0.9`. El ciclo matemático 1→0→1 de la prueba es un **control del contador fuera de los límites operativos**, no una simulación operativa autorizada. El EFC por throughput que solo incluye una descarga total de 100 % es 0.5, aunque no exista posterior carga; para un ciclo cerrado de 100 % a Q constante es 1. No inferir energía: obtener Wh integrando tensión por corriente en el puerto declarado.

## Frontera de capacidad y cambios de coordenada

Con ADR-001, en la frontera `s+=s−` y el snapshot cambia `Q−→Q+`. No hay duración, corriente ni transferencia de carga o energía asociadas al evento, por lo cual `ΔA_abs=Δz_deg=ΔEFC_ini=ΔEFC_eff=ΔEFC_BLAST=0` en la frontera. La magnitud contable `s·Q_eff` cambia en `s(Q+−Q−)` y no es Ah intercambiados. Las capacidades solo ponderan las integrales de corriente en intervalos físicos con duración.

La alternativa de conservar algebraicamente `sQ` rebasea `s+=s−Q−/Q+`; si su salto se inserta como tramo de una serie BLAST, `_extract_stressors` lo interpreta como circulación de carga aunque no haya corriente. No hacerlo. El adaptador actual exige igualdad de SoC y tiempo en el punto compartido y `preserve_window_state` conserva el vector y rechaza SoC fuera de límites; aun así no existe orquestador automático de ventanas ni prueba física experimental de la hipótesis.

## Referencias de capacidad

| Referencia | Valor | Uso |
|---|---:|---|
| Nominal nueva de unidad 2p | 66 Ah | referencia de SoH del caso y límite nominal del modelo |
| `cap_2ndLife` BLAST | 46 Ah | atributo original; no se iguala a 46.2 |
| `qNew(0)*66` | 46.2 Ah | 0.7·66; diferencia de 0.2 Ah respecto al atributo |
| Inicio del caso de tesis | 44.1 Ah | denominador de `EFC_ini` de ese caso |
| Inicio del caso Braco | 43.5 Ah | denominador de un caso separado, no del caso de tesis |

Un ejemplo de 88.2 Ah de throughput representa 1 EFC respecto a 44.1 Ah; sería 1.0137931 respecto a 43.5 Ah, 0.6681818 respecto a 66 Ah, 0.9586957 respecto a 46 Ah o 0.9545455 respecto a 46.2 Ah. Esas divisiones son comparaciones algebraicas para **la misma escala física**, no equivalencias de muestras ni el contador BLAST.

## Pruebas sintéticas y resultados

Comando ejecutado desde la raíz, Python 3.12.10, BLAST-Lite 1.1.0, clase/base verificadas por hash frente al commit auditado `b093495b47dc40dd96dba865d91f553619501e94`:

```powershell
& "$env:LOCALAPPDATA\microgrid_blast_probe_312\Scripts\python.exe" -B outputs/analysis/bat26_36_efc/check_efc.py
```

**7 pruebas PASS**: unidades/signos de `rhs`; estado `z_deg` mediante integración aislada del BESS por dos ventanas; reposo, carga, descarga, ciclo completo, parcial y capacidad variable; invariancia de throughput/EFC físicos al partir perfiles equivalentes; EFC real BLAST y dependencia de q y partición; historial previo/anclaje condicional; frontera sin throughput; y referencias. No se ejecutó un segundo solver dentro de la microrred: `solve_ivp` se usa solamente en la prueba aislada de dos intervalos. `results.json` contiene salida y q/EFC por ventana. Los perfiles suponen Q inicial 44.1 Ah, intervalos de una hora y T sintética de 25 °C.

La regresión dirigida existente de frontera de SoC `test_soc_variable_capacity_boundary.py` también terminó con **4 PASS** en el `.venv` principal de Python 3.14. No se repitieron simulaciones pesadas: no se modificó código de la microrred.

| Perfil sintético | `A_abs` Ah | `EFC_ini` | `EFC_eff` | EFC BLAST por tramos | BLAST con cada tramo subdividido en cuatro |
|---|---:|---:|---:|---:|---:|
| Reposo | 0 | 0 | 0 | 0 | 0 |
| Descarga 0.9→0.1 | 35.28 | 0.4 | 0.4 | 0.4000000000 | 0.3997797742 |
| Carga 0.1→0.9 | 35.28 | 0.4 | 0.4 | 0.4000000000 | 0.3998133229 |
| Completo 1→0→1 | 88.2 | 1 | 1 | 0.9995328171 | 0.9991655602 |
| Parcial 0.7→0.3→0.7 | 35.28 | 0.4 | 0.4 | 0.3998194754 | 0.3996810794 |
| Q 44.1→39.69 Ah, SoC 0.9→0.5→0.9 | 33.516 | 0.38 | 0.4 | 0.3997990581 | 0.3996450032 |

El caso de Q variable impone **un cambio hipotético de 10 %**, independiente de la degradación BLAST calculada, para aislar denominadores y frontera: no representa una trayectoria acoplada BLAST–BESS. Los casos por tramos se subdividen sin cambiar el perfil continuo de corriente ni SoC, pero se generan más muestras en la variante subdividida; el test adicional completo una llamada frente a dos usa la misma malla de 121 puntos y demuestra la diferencia de EFC por partición. Para Q variable el test del BESS integra por separado ambas ventanas y obtiene `z_deg=33.516 Ah`, sin cambio en frontera. Los valores BLAST numéricos son ejecución real del paquete con entradas sintéticas, no validación experimental ni calibración en microred.

## Dictamen de cierre

El criterio documental de Roma —definir Ah-throughput y EFC, DoD, unidades y actualización sin doble conteo— **queda satisfecho dentro del alcance matemático y de pruebas sintéticas descrito**, sujeto a revisión del usuario. No se debe marcar BAT26-36 completada automáticamente. Quedan fuera de ese cierre la procedencia física 2p, temperatura de celda, validación experimental de la degradación, sensibilidad numérica temporal y una futura implementación de reportes integrados de despacho. No se modificaron modelo, ecuaciones, parámetros, solver, ECM, DC/DC ni BLAST original.
