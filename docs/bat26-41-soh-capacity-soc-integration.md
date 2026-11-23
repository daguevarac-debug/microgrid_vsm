# BAT26-41 — acoplamiento SoH → capacidad efectiva → SoC

## Alcance y contrato

Se comprobó el acoplamiento existente con BLAST-Lite original en tres ventanas consecutivas, tanto para GFM/BESS de 15 estados como para GFM/BESS/PI de 16. La transición la realiza explícitamente el ensayo con `preserve_window_state`; no se implementó un orquestador ni se modificaron ecuaciones, solver o componentes de planta. Los perfiles son sintéticos y sus resultados son evidencia de software, no predicciones físicas ni validación experimental.

Para la ventana `k`, con `q0=q(t0)` y el snapshot mantenido fijo durante la integración:

```text
retención_k = q_k/q0
Qeff_k = 44.1 Ah · retención_k
SoH_k = Qeff_k/(66 Ah)
dSoC/dt = -i_bess/(3600 Qeff_k),  i_bess > 0 descarga
dz_deg/dt = |i_bess|/3600  [Ah/s]
```

La instancia nueva comienza con `q0=1`, retención 1 y Qeff=44.1 Ah. BLAST conserva su historia entre ventanas; después de cada integración entrega `q` y el snapshot siguiente. El `z_deg` continúa midiendo throughput pero, en modo `blast`, no alimenta una segunda ley de pérdida de capacidad. Si hay historia BLAST previa, `q0` debe anclarse al comienzo del caso sin borrar esa historia: 44.1 Ah representa entonces la capacidad inicial ya envejecida, no se descuenta otra vez su pérdida histórica. La transferencia de retención a ese caso es una hipótesis, no una calibración.

Referencias distintas: 66 Ah nominales; 46 Ah como `cap_2ndLife` de BLAST; 46.2 Ah como `qNew(0)·66`; 44.1 Ah para este caso; 43.5 Ah para otro escenario. No se reconcilian 46 y 46.2 ni se multiplica el caso por 0.7 de nuevo.

## Ensayo integrado y resultados

Se ejecutó `outputs/analysis/bat26_41_windowed/check_windows.py` con la microrred y el worker BLAST reales. Cada arquitectura usa una instancia persistente BLAST, tres integraciones globales consecutivas de 0.02 s, 21 muestras por ventana y temperatura sintética constante de celda de 25 °C. `M=80`, `D=1500`, `P_ref=3000 W`, SoC inicial 0.6; PI, cuando aplica, tiene Kp=100 y Ki=20. Se emplean RK45 y los valores de configuración `rtol=1e-6`, `atol=1e-8`, `max_step=5e-5 s`. La actualización BLAST se ejecuta después de terminar cada solve, fuera de la RHS. El extremo de cada ventana coincide con el comienzo de la siguiente, sin duplicar intervalos.

El campo requerido de corriente sintética de grupo 2p se construye **solo para esta prueba** como una hipótesis numérica 1:1 con `i_bess`; no se ha identificado ni validado una transformación bus–grupo. La API BLAST utilizada calcula EFC a partir de SoC, no de esa corriente. La etiqueta sintética no acredita un perfil operativo. Las muestras completas, vectores, hashes de perfiles, pérdidas, `z_deg`, tolerancias y versiones están en `outputs/analysis/bat26_41_windowed/results.json`.

| Estados | Ventana | Qeff usada → siguiente [Ah] | SoC inicial → final | q final = retención | EFC acumulado BLAST |
|---|---:|---|---|---:|---:|
| 15 | 1 | 44.100000000000 → 44.099849415345 | 0.600000000000 → 0.600000271996 | 0.999996585382 | 1.359978436e-7 |
| 15 | 2 | 44.099849415345 → 44.099779543946 | 0.600000271996 → 0.600000574312 | 0.999995000997 | 2.871554636e-7 |
| 15 | 3 | 44.099779543946 → 44.099734558537 | 0.600000574312 → 0.600000876769 | 0.999993980919 | 4.383832077e-7 |
| 16 | 1 | 44.100000000000 → 44.099849415369 | 0.600000000000 → 0.600000228211 | 0.999996585383 | 1.141053910e-7 |
| 16 | 2 | 44.099849415369 → 44.099779543982 | 0.600000228211 → 0.600000518151 | 0.999995000997 | 2.590749601e-7 |
| 16 | 3 | 44.099779543982 → 44.099734558582 | 0.600000518151 → 0.600000810872 | 0.999993980920 | 4.054347505e-7 |

En cada una de las 126 muestras se comprobó la igualdad de la derivada de SoC con la corriente y Qeff de su ventana; el error máximo observado fue cero con la aritmética evaluada. Se comprobó también `Qeff_siguiente=44.1*q/q0` y la persistencia de tres entradas de historia. Para cada intervalo se verificó el incremento propio de BLAST `ΔEFC=0.5*q_previo*Σ|ΔSoC|`; no se añadió un incremento de EFC en la operación de copia de frontera. `z_deg` cambia durante las ventanas por la corriente integrada, no al copiar el estado. La actualización de capacidad tampoco añade una integral de corriente o potencia: un valor algebraico instantáneo no es carga ni energía intercambiada.

El máximo salto de los 15 o 16 estados al copiar cada frontera es exactamente cero, incluidos SoC, Vrc, z_deg, omega, theta y el estado PI cuando existe. En estos casos particulares también fueron cero los cambios instantáneos calculados de corriente y potencia DC. La tensión terminal, señal algebraica que depende de SoH mediante R0, sí cambió: en 15 estados, respectivamente, 5.2975e-9, 2.4755e-9 y 1.5858e-9 V; en 16, 4.9812e-9, 2.3890e-9 y 1.5362e-9 V. Esos saltos algebraicos no son saltos de estado; otras condiciones podrían producir también cambios algebraicos de corriente o potencia sin implicar por sí solos un impulso de duración finita.

Conservar SoC fraccional no conserva `SoC·Qeff`: su cambio algebraico es `SoC_frontera·(Qeff_siguiente−Qeff_anterior)`. Este producto cambia incluso sin evolución temporal en la frontera; no se contabiliza como corriente, throughput, EFC o energía transferida. Tampoco demuestra conservación física de carga o energía. La política alternativa de conservar carga requeriría cambiar la coordenada SoC, evaluar sus límites y separar ese cambio de los ciclos de uso; ADR-001 adopta provisionalmente continuidad fraccional, sin validarla como ley física.

## Verificación y regresiones

```powershell
# Opcional si el entorno no está en la ubicación local preparada:
$env:BLAST_LITE_PYTHON = '<ruta al Python 3.12.10 con BLAST-Lite 1.1.0>'
.venv\Scripts\python.exe -B outputs/analysis/bat26_41_windowed/check_windows.py
.venv\Scripts\python.exe -B -m unittest discover -s src\validation -p test_blast_lite_adapter.py -v
.venv\Scripts\python.exe -B -m unittest discover -s src\validation -p test_aging_capacity_contract.py -v
.venv\Scripts\python.exe -B -m unittest discover -s src\validation -p test_capacity_snapshot_integration.py -v
.venv\Scripts\python.exe -B src/validation/test_soc_variable_capacity_boundary.py -q
.venv\Scripts\python.exe -B src/validation/test_microgrid_bess_pi_connection.py -q
.venv\Scripts\python.exe -B src/validation/test_gfm_controller.py -q
.venv\Scripts\python.exe -B src/validation/test_microgrid_controller_state_mapping.py -q
.venv\Scripts\python.exe -B src/validation/test_bess_sign_coherence.py -q
.venv\Scripts\python.exe -B src/validation/test_dc_link_bess_pi.py -q
```

| Evidencia | Resultado |
|---|---|
| Ensayo integrado BLAST real, tres ventanas × arquitecturas 15/16 | **PASS** en los casos sintéticos indicados |
| Adaptador BLAST, contrato capacidad y snapshots | **PASS**, 27 pruebas (10+11+6) |
| Frontera SoC, conexión PI, GFM, mapeo estados, signos y PI | **PASS**, 44 pruebas (4+12+11+5+3+9) |
| Exclusividad y ruta lineal | **PASS**: cambiar z_deg no cambia la derivada SoC en snapshot BLAST; default y `linear` coinciden exactamente en el estado ensayado; BAT26-39 comparó trayectorias cortas contra commit `95272bee594a6f16817945fd6b2959681a7bc552` con diferencia máxima cero |
| Límites | **PASS** en muestras y pruebas de frontera: se rechaza SoC 0.099/0.901 sin clipping; se bloquea descarga a 0.1 y carga a 0.9 y se permite recuperación, en ambas arquitecturas. Las 21 muestras no prueban cotas entre todas las muestras |
| Objetivo 1, invariantes, GFM integrado y PI | Evidencia anterior BAT26-39/BAT26-33; no se repitieron campañas pesadas al no cambiar código de producción. GFM +40 % mantiene **REVIEW** por Vdc, no FAIL del solver |

El worker exige Python 3.12.10, BLAST-Lite 1.1.0 y verifica los SHA-256 de clase y base documentados en BAT26-40, comparados previamente con el commit oficial `b093495b47dc40dd96dba865d91f553619501e94`. La microrred se ejecutó con Python 3.14, NumPy 2.3.5 y SciPy registrado en JSON. No se exige una ruta absoluta específica: puede configurarse `BLAST_LITE_PYTHON`.

## Límites y criterio de cierre

La trayectoria de 60 ms y DoD diminuto no demuestra capacidad predictiva de degradación: la clase original dispone de datos cíclicos cercanos a 25 °C, 100 % DoD y 1C. La sensibilidad del integrador de envejecimiento a particiones sigue sin tolerancia física acordada; aquí no se afirma convergencia temporal. Faltan temperatura real de celda, transformación corriente bus–grupo 2p, historial y perfiles acreditados, validación de transferencia a 44.1 Ah, balance energético físico y validación experimental. El historial del worker es en memoria, sin recuperación durable demostrada.

**Conclusión:** el criterio de coherencia SoH → Qeff → SoC y continuidad de estados se satisface como comprobación de software para los casos y límites descritos; no acredita la política de frontera ni el envejecimiento como resultados físicos. BAT26-41 permanece abierta para decisión del usuario y no se marca completada automáticamente.
