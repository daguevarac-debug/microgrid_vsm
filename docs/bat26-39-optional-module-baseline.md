# BAT26-39 — verificación del módulo opcional frente al baseline

## Alcance y resultado

El modo predeterminado y `aging_mode='linear'` reproducen exactamente los valores del commit local `95272bee594a6f16817945fd6b2959681a7bc552` en las entradas, estados, derivadas y trayectorias **cortas** ensayadas; no se invoca ni importa BLAST. Las regresiones pertinentes y las pruebas de selección pasan. El resultado prueba compatibilidad en estos casos, no igualdad universal de todas las trayectorias ni validación experimental.

La comprobación inicial encontró que pasar un `capacity_snapshot` sin modo seleccionaba `blast` de forma implícita. Además, el adaptador verificaba que sus perfiles fueran sintéticos, pero la microrred aceptaba snapshots sin una declaración de uso sintético. Para cumplir el requisito explícito de BAT26-39 se corrigió solo la selección de constructor: sin `aging_mode` se elige `linear`; para snapshot se exige `aging_mode='blast'` y `blast_profile_kind='synthetic'`. `linear` rechaza snapshots y la etiqueta BLAST; `blast` rechaza snapshot ausente, etiqueta ausente u otra etiqueta. Se añadió cobertura de rechazo en las arquitecturas de 15/16 estados y se actualizaron los tests anteriores que suministraban snapshots de forma implícita. **Compatibilidad:** quienes usaban el snapshot opcional de la interfaz provisional deben añadir ambas opciones; la ruta predeterminada sin snapshot no cambia. Se actualizó el párrafo de selección de `docs/bat26-33-blast-capacity-bridge.md` para evitar instrucciones contradictorias.

La cadena `synthetic` es una declaración explícita del llamador, no una certificación de procedencia de un snapshot que se cree manualmente. El adaptador existente, cuando se utiliza para actualizar BLAST, rechaza perfiles distintos de `synthetic`, corriente que no sea `synthetic_2p_group` y temperatura que no sea `synthetic_cell`; tampoco convierte corriente del bus a corriente 2p. No se habilita una afirmación de operación física ni validación por la etiqueta.

## Comparación con baseline identificable

El script `outputs/analysis/bat26_39_baseline/compare.py` exporta exclusivamente `src` del commit citado mediante `git archive` a un directorio temporal nuevo. No cambia el checkout. Ejecuta ese árbol y el árbol de trabajo en procesos separados, usando el **mismo intérprete Python 3.14.0**, NumPy 2.3.5, SciPy 1.16.3 y el mismo archivo `OCV_SOC.xlsx` del checkout, cuyo SHA-256 es `b8d53a78bfda473f02513463f30e1e986948408230da6c4d66a4fdbfd2327a8d`. `src/config.py` tiene el mismo hash en commit y trabajo. El script fija `PYTHONDONTWRITEBYTECODE=1`, impide importaciones `blast`/`bess.blast_*`, bloquea `subprocess.Popen` durante los cálculos de cada hijo y comprueba que `blast` no aparece en `sys.modules`.

Casos: grid-following + BESS (15 estados), GFM + BESS (15), y GFM + BESS + PI (16). En cada uno se comparan el commit con el constructor actual predeterminado y con `linear` explícito. Las tres implementaciones reciben igual Excel y parámetros, estado inicial con `Vdc=340 V` y `z_deg=12.5 Ah`, y dos estados adicionales de derivada (`Vdc=330 V`, `SoC=.4`; `Vdc=350 V`, `SoC=.9`). Los estados de controlador/PI y el vector completo se conservan y se comparan. GFM usa `M=80`, `D=1500` y `P_ref=3000 W`; PI usa Kp=100 W/V, Ki=20 W/(V·s). La configuración contiene además Qnom=66 Ah, Qinit=44.1 Ah, `k_deg=1.478e-6`, SoHmin=.5, SoCmin=.1, SoCmax=.9, R0nom=.000970 Ω, sensibilidad R0=1, Cdc=.002 F, Imax=66 A, Pmax=22440 W, Vdc_ref=340 V. El script lee y compara los valores reales de configuración; valores completos y nfev constan en `results.json`.

Se evalúan derivadas en los tres estados e integración RK45 de 0 a 0.02 s, muestras en 0, .005, .01, .015 y .02 s, `rtol=1e-6`, `atol=1e-8` y `max_step=5e-5 s`, iguales en ambos árboles. Cada comparación exige igualdad exacta de arrays, no una tolerancia de porcentaje elegida tras mirar datos. Resultado: **diferencia máxima absoluta 0** en condición inicial, estados de prueba, derivadas y todas las muestras de trayectoria; nfev coincide para cada caso. El archivo guarda arrays, parámetros, hashes de archivos y resultado de cada comparación; identifica fuentes locales y Python observado sin exigir una ruta fija de otro equipo.

```powershell
.venv\Scripts\python.exe -B outputs/analysis/bat26_39_baseline/compare.py
```

La trayectoria de 0.02 s y tres puntos de evaluación de RHS son una regresión dirigida: no demuestran equivalencia para cualquier perfil, duración o dependencia futura. La misma copia de Excel y el mismo entorno se usan para ambas ramas; no se declara independiente la validación física del Excel. El snapshot no aparece en el commit anterior: no se compara `blast` con una implementación que no lo contenía.

## Exclusividad, perfil sintético y frontera

`SecondLifeBattery1RC` sigue admitiendo su API de snapshot a bajo nivel, sin importar BLAST; en microrred la combinación explícita selecciona una sola ruta. En `linear`, `SoH=max(soh_min,soh_init−k_deg*z_deg)` alimenta Qeff. En `blast`, `CapacitySnapshot` fija SoH/Qeff durante la ventana; `z_deg` conserva su derivada de throughput pero no produce una segunda pérdida de capacidad. Las 10 pruebas de `test_blast_lite_adapter.py` pasaron con el BLAST original: incluyen retención inicial, historia, ancla posterior, perfiles operativos rechazados, límites de SoH, cambios de `z_deg` bajo snapshot, ciclo sintético, continuidad y ausencia de corriente/potencia/EFC artificiales en la frontera de reposo. `preserve_window_state` conserva los 15/16 estados y rechaza SoC fuera de límites sin clipping. No es un orquestador automático de ventanas.

El worker exige Python **3.12.10** y BLAST-Lite **1.1.0**; valida SHA-256 de la clase Leaf `258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844` y de la base `1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f`, cotejadas con el commit oficial `b093495b47dc40dd96dba865d91f553619501e94`. NumPy del worker observado: 1.26.4. El ejecutable Python se entrega al adaptador por argumento; las pruebas aceptan variable `BLAST_LITE_PYTHON` o el entorno local previamente preparado. No existe una ruta absoluta de otro equipo como requisito de la API.

Referencias separadas: 66 Ah nominal, 46 Ah `cap_2ndLife`, 46.2 Ah de `qNew(0)*66`, 44.1 Ah para tesis y 43.5 Ah para otro caso. El adaptador fija `q0=q(t0)`; al comenzar una instancia nueva q0=1. `anchor_case()` fija q0 tras historia previa sin resetear BLAST ni EFC: `Q_eff=Q_init*q/q0`, sin repetir 0.7 o pérdida histórica. La historia y los hashes de ventanas permanecen en memoria durante el proceso; no hay checkpoint durable.

## Resultados y evidencia

| Comprobación | Resultado | Ejecución/evidencia |
|---|---|---|
| Default/linear vs commit, grid-following y GFM 15, GFM/PI 16 | **PASS**, máximos 0 en puntos ensayados | comparación nueva, `results.json` |
| BLAST opcional, rechazo de modo/perfil y snapshots | **PASS**, 10 pruebas | suite nueva ejecutada contra worker real y entradas sintéticas |
| Contrato de capacidad, snapshots, SoC, RC y signos/DC | **PASS**, 30 pruebas (11+6+4+1+5+3) | suites unitarias repetidas tras corrección |
| PI, GFM, mapeo y interfaz BESS | **PASS**, 44 pruebas (9+12+11+5+7) | suites unitarias repetidas tras corrección |
| Objetivo 1 | **PASS**, LCL, BESS paso 3 y límites SoC | campaña nueva con código final en copia temporal; `objective1.log` |
| BESS paso 2 | **PASS** | ejecución nueva en copia temporal; `bess_step2.log` |
| Invariantes físicos y GFM integrado | **PASS** invariantes; GFM **REVIEW** en +40 % por Vdc, demás escenarios PASS | evidencia BAT26-33, no repetida como campaña pesada |
| PI integrado 20 % y 40 % | **PASS** ambos | evidencia BAT26-33, no repetida como campaña pesada |
| Datos físicos, validez BLAST y convergencia temporal | **REVIEW / no evaluable** | sin perfiles 2p/T acreditados ni tolerancia temporal fundamentada |

Las campañas de BAT26-33 están en `outputs/analysis/bat26_33_validation_20261103/`. En esta máquina se conservó la copia temporal de fuente que las produjo: al compararla con el código de esta tarea, `model.py`, `microgrid_bess_pi.py`, `config.py`, controladores GFM/PI, `dclink.py` y los tres scripts de campaña coinciden por SHA-256. `microgrid.py` solo cambia la selección/validación del constructor; no se modifican las ecuaciones dinámicas, estados, LCL, enlace DC, VSG ni parámetros. La comparación nueva del baseline y las pruebas de constructor/estado cubren esa modificación. Por indicación del usuario no se repitieron las campañas pesadas de invariantes, GFM y PI; sus salidas conservadas se citan como evidencia **previa**, no como ejecuciones nuevas. La prueba explícita de energía del capacitor M10 prevista en BAT26-38 sigue pendiente; las pruebas DC de esta tarea verifican su ecuación de corriente, no reemplazan ese test de energía.

No se realizó validación experimental, balance físico batería–convertidor–bus, caracterización de R0(SoH) ni demostración de convergencia temporal BLAST. `git diff --check` pasó. BAT26-39 queda en curso y no se cierra automáticamente.
