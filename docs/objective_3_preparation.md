# Preparación del Objetivo 3

El Objetivo 3 aplica de forma integrada el modelado del Objetivo 1 y el control
VSG clásico del Objetivo 2 a una red real o representativa de Colombia mediante
simulación, escenarios y perturbaciones. La red aún no se ha recibido. San Andrés
y Cundinamarca son opciones mencionadas por el director, no casos implementados.

## Baseline auditado

Auditoría inicial: `main`, commit `f40f2c8`, sin modificaciones de código. Había
dos CSV BESS Step-3 modificados y siete resultados sin seguimiento; se preservan
como trabajo previo. La preparación se realiza en `chore/prepare-objective-3`.
No existía `docs/chatgpt_work_context.md`; se crea como contexto operativo.

| Alcance | Componentes y flujo reutilizable |
| --- | --- |
| Objetivo 1 cerrado | `pv_model.py`, `dclink.py`, `inverter_source.py` (fuente promediada), `lcl_filter.py`, `microgrid.py`, `bess/`, `controllers/grid_following.py`; entrada `python src/main.py` y `--with-bess`. |
| Objetivo 2 cerrado con limitaciones | `controllers/gfm_controller.py`, `controllers/grid_forming.py`, `controllers/dc_link_bess_pi.py`, `microgrid_bess_pi.py`, `tuning_metrics.py`; campaña `validate_gfm_integrated_system.py`. |
| Red benchmark activa | `ieee33_base.py`, `ieee33_coupling.py`, entrada `python src/ieee33_main.py`; modo histórico `--baseline`. |
| Investigación conservada | `FOVICInverter`/Oustaloup en `inverter_source.py` es prototipo no integrado; evaluación en `fovic_reuse_evaluation.md`. Validadores del bloque GFM aislado y barridos antiguos son evidencia histórica, no selección activa. |

Se protegen las ecuaciones, signos y estados de `AGENTS.md`: `x[10]=omega`
en GFM, `x[11]=theta`, BESS en `x[12:15]`, PI externo en `x[15]`, un único
solver global, `M=80`, `D=1500`. No se modifica ningún módulo existente de código.

La autoridad de cierre actual es
`objective_2_activities_2_1_to_2_3_closure.md`: actividad 2.1 `PASS`, actividades
2.2 y 2.3 cerradas en `REVIEW`. El `REVIEW` integrado al 40% y el `FAIL`
de factibilidad DC del escenario severo extendido de sintonía son resultados
distintos y se conservan. Floquet de 12 estados es evidencia numérica formal
del estudio; el de 16 es diagnóstico con deriva lenta. No hay validación
experimental, FOVIC final, DC/DC detallado ni BMS industrial.

## Contrato mínimo de red

Se adopta un diccionario serializable en JSON, validado por `study_network.py`,
sin dependencia de PowerFactory, pandapower ni nuevas bibliotecas. La estructura
anterior `ieee33bus.txt` estaba ligada a 33 buses y a un único nivel de tensión;
no ofrecía un contrato independiente. El nuevo adaptador de salida reutiliza
las funciones pandapower ya usadas por `ieee33_base.py`.

La versión 1 representa un estado operativo trifásico balanceado, conectado,
con líneas en servicio, cargas PQ, generación PQ y una fuente slack equivalente.
El fixture completo está en `src/validation/fixtures/objective3_synthetic.json`.

| Campo | Unidad, significado y restricciones |
| --- | --- |
| `schema_version` | Entero `1`; campos adicionales se rechazan para evitar pérdidas silenciosas. |
| `name`, `provenance`, `synthetic` | Nombre, procedencia/revisión del caso y booleano explícito; `false` no certifica validez académica. |
| `base_mva`, `frequency_hz` | Base trifásica de potencia y frecuencia positivas; no cambian la base del controlador ni convierten `M` en `H`. |
| `buses` | Lista `{id, vn_kv}`; ID externo estable como texto, tensión nominal RMS línea-línea en kV. |
| `lines` | `{id, from_bus, to_bus, length_km, r_ohm_per_km, x_ohm_per_km, c_nf_per_km, max_i_ka}`; parámetros por fase/secuencia positiva, R/X/C no negativos, impedancia no nula. |
| `loads` | `{id, bus, p_mw, q_mvar}`; potencias trifásicas, P positiva consumida, Q positiva inductiva consumida. |
| `generators` | `{id, bus, p_mw, q_mvar}`; P positiva inyectada, Q positiva inyectada; lista vacía permitida. |
| `slack` | `{bus, vm_pu, va_degree}`; una referencia de tensión y ángulo. |
| `pcc_bus` | ID de bus existente, explícito, nunca deducido de la posición en una lista. |

Todos los valores numéricos deben ser finitos; no se aceptan booleanos como
números ni claves JSON duplicadas. Los IDs son únicos por tabla. Se verifica
conectividad desde slack, referencias válidas y tensión compatible en cada línea.
Las bases de impedancia, si la fuente usa pu, se convierten en el futuro adaptador
con `Z_base = V_LL,kV² / S_3ph,MVA` y se documenta la conversión.

Límite deliberado: no hay transformadores, interruptores, islas, fases
desbalanceadas, controles de generadores PV ni equipos dinámicos de red en v1.
Cada bus declara su tensión, pero una red conectada con diferentes niveles
necesitará extender el contrato con transformadores al recibir datos reales.
No se deben omitir equipos, cerrar interruptores abiertos ni inventar ratings
para hacer que un archivo real encaje. La fuente slack actual es un equivalente
de flujo estático; no demuestra operación dinámica aislada de San Andrés.

## Ejecución y trazabilidad

Desde la raíz, con el entorno científico existente:

```bash
python src/objective3_main.py src/validation/fixtures/objective3_synthetic.json
python src/objective3_main.py src/validation/fixtures/objective3_synthetic.json --run-baseline --q-pcc-mvar 0
python -m pytest src/validation/test_objective3_interface.py -q
```

El primer comando valida datos usando solo biblioteca estándar. El segundo
reutiliza `run_scenario(STEP_20_BESS_PI_SPEC)` de la campaña integrada: carga local
3 kW, escalón 20%, GFM+BESS+PI, 16 estados y 6.5 s. La red no altera esa carga
ni realimenta la ODE. Tras resolverla, promedia aritméticamente `p_pcc` en la
ventana `t > 6.5*SIM_SS_WINDOW_FRACTION`, convierte W→kW→MW y resuelve los flujos
base y con inyección en el PCC. No hay segundo integrador dinámico.

`--q-pcc-mvar` es obligatorio en ese ensayo: Q=0 es solamente la hipótesis
del fixture. No se infiere Q dinámica ni se implementa control Q-V. La potencia
local se usa como inyección equivalente adicional, igual que el enfoque IEEE 33;
al recibir la red se deberá verificar qué carga/generación ya contiene el caso
fuente para evitar doble conteo. No se escala la microrred de 3 kW automáticamente.
El enlace LV/MV es equivalente e idealizado, sin transformador dinámico.

Cada corrida escribe `network.json` y `summary.json` en una carpeta nueva de
`outputs/objective3/`, o en `--output-dir`. Un directorio existente se rechaza.
Se guardan procedencia, copia normalizada, SHA-256 del contrato, fecha UTC,
commit, cambios locales en `src`, versiones usadas, PCC, ventana y métricas.
El resumen contiene tensiones por bus, cargas de líneas, pérdidas, potencia
slack y residuos de balance P/Q antes/después. `EXECUTION_FAILED` conserva el
error de ejecución; `DATA_CHECKED` y `BASELINE_EXECUTED` no son `PASS` académico.
Las clasificaciones internas originales se conservan en `local_metrics`.

Las salidas nuevas se excluyen de Git para evitar incorporar corridas por
accidente; la evidencia histórica versionada permanece intacta. Para publicar
una campaña futura, seleccionar explícitamente sus resúmenes y documentación.

## Información que debe llegar con la red

Entregar el archivo fuente original y versión del software: proyecto/exportación
DIgSILENT PowerFactory (incluidas bibliotecas/tipos usados) o red pandapower
serializada, preferiblemente JSON con versión. No hay parser de esos formatos
externos todavía. Acompañarlo de:

1. Procedencia, fecha, autorización de uso y si es real, equivalente o representativa.
2. Caso operativo activo, diagrama, IDs, conectividad, equipos y estado de interruptores.
3. Niveles de tensión, frecuencia, bases, unidades y convenciones de signo.
4. Parámetros y límites de líneas/transformadores, taps y conexiones.
5. Cargas P/Q, generación, controles, slack/referencia y límites disponibles.
6. PCC propuesto con ID exacto, interfaz LV/MV y alcance/capacidad de la microrred.
7. Flujo fuente convergido: tensiones, flujos, pérdidas y balance de generación/demanda.
8. Perfiles/eventos disponibles de demanda, irradiancia y temperatura, con tiempos,
   unidades y condiciones iniciales BESS; objetivos y comparadores acordados.

## Siguiente paso exacto

Inventariar el archivo recibido y sus equipos; elegir **un** adaptador desde
su formato hacia este contrato. Si hay elementos no soportados, ampliar solo
los que contiene la red y probarlos antes de ejecutar estudios. Conservar un
mapeo de IDs y un registro de conversiones de unidades, sin cambiar el núcleo
Obj. 1–2. No ejecutar código incrustado en un archivo fuente para importarlo.

Antes de aceptar el caso: validar topología, estados de servicio, bases,
tensiones, signos, cargas/generación y PCC; reproducir el balance inicial y el
flujo fuente; comprobar convergencia, residuos, límites y comparación de
tensiones/flujos/pérdidas. Acordar tolerancias y equivalencias con la fuente,
sin inventar umbrales académicos. Revisar escalamiento, doble conteo y Q del PCC.
Luego definir escenarios finales y ejecutar comparaciones trazables.

Métricas reutilizables: frecuencia desde omega (nadir, desviación, RoCoF,
recuperación y error estacionario), Vdc, SoC/SoH, corriente/potencia y saturación
BESS desde `tuning_metrics.py` y validadores existentes. Las ventanas y criterios
siguen los de cada campaña Obj. 2; el ensayo usa los de la campaña integrada,
no sustituye la sintonía multi-escenario con RoCoF postevento. Frecuencia local
no equivale a frecuencia dinámica de toda la red externa. Escenarios reales,
comparadores, umbrales finales y eventual acople dinámico quedan por definir.

## Regresión protegida

Pruebas rápidas: `python -m pytest src/validation -q`. Validaciones protegidas:

```bash
python src/validation/validate_obj1_regression.py
python src/validation/validate_gfm_integrated_system.py
python src/validation/validate_physical_invariants.py
python src/validation/validate_ieee33_gfm_pcc_average.py
python src/validation/validate_ieee33_gfm_voltage_profile.py
python src/validation/validate_objective2_bess_control_limits.py
python src/validation/validate_objective2_small_signal_stability.py
python src/validation/validate_objective2_control_closure.py
```

Estos scripts pueden sobrescribir sus salidas históricas: ejecutarlos en copia
aislada cuando haya resultados locales por conservar. La sintonía completa de
9 candidatos × 4 escenarios se reserva para cambios de control/modelo/métricas;
su evidencia existente y pruebas unitarias se comprueban en esta preparación.

## Verificación de esta preparación — 2026-09-20 (Colombia)

Código nuevo consolidado en `2932086`, sobre baseline `f40f2c8`. Las regresiones
se ejecutaron en una copia temporal obtenida de `git archive`, incorporando los
archivos nuevos y la documentación actualizada. El código físico es idéntico al
baseline. Los nueve resultados locales preexistentes conservaron su SHA-256.

| Verificación ejecutada | Resultado | Tiempo medido |
| --- | --- | ---: |
| Suite antes de cambios | 207 pruebas + 18 subpruebas pasan | 24.31 s |
| Suite final completa | 229 pruebas + 18 subpruebas pasan | 20.05 s |
| Interfaz Obj. 3 aislada | 22 pruebas pasan | 2.68 s |
| `validate_obj1_regression.py` | PASS: LCL, BESS Step-3 y límites SoC | 27.94 s |
| `validate_gfm_integrated_system.py` | REVIEW esperado: solo el escalón 40%; restantes PASS | 439.33 s |
| `validate_physical_invariants.py` | PASS | 192.40 s |
| `validate_ieee33_gfm_pcc_average.py` | PASS; residuo del promedio cero | 34.93 s |
| `validate_ieee33_gfm_voltage_profile.py` | PASS; perfil base idéntico | 53.01 s |
| `validate_objective2_bess_control_limits.py` | 14 PASS, 1 REVIEW de escala Vdc/vt_bess | 4.11 s |
| `validate_objective2_small_signal_stability.py` | 12 estados PASS; 16 REVIEW por deriva lenta | 52.90 s |
| `validate_objective2_control_closure.py` | REVIEW; 32 criterios, cero fallos bloqueantes, un fallo diagnóstico histórico | 0.22 s |
| `validate_pv_stc_fit.py` | PASS | 3.22 s |
| `validate_microgrid_rl_load.py` | PASS | 25.96 s |
| `validate_islanded_operation_scenarios.py` | Cuatro escenarios PASS | 162.55 s |
| `validate_bess_step2.py` | Todos los casos PASS | 3.09 s |
| Obj. 3, fixture + `--run-baseline --q-pcc-mvar 0` | BASELINE_EXECUTED; modelo local PASS, ambos flujos convergen | 230.74 s |

Los tiempos son de pared, con algunas ejecuciones concurrentes; no constituyen
un benchmark de rendimiento. No se repitió la sintonía completa de 36 corridas:
no cambiaron control, modelo ni métricas; se verificaron su evidencia mediante
el cierre y sus pruebas unitarias, incluido el fallo físico del caso severo.
Su tiempo completo no se midió en esta sesión.

En el ensayo sintético, `p_ss_kw=3.3571743633847437`, ventana `(4.875, 6.5] s`,
32501 muestras. Los residuos P/Q de ambos flujos fueron menores a `1e-12` en
MW/Mvar. Se guardó en `outputs/objective3/preparation-smoke/`; no es un caso
académico. `python -S src/objective3_main.py ...` también verificó que la ruta
de datos funciona sin paquetes externos.

Compatibilidad: vector de estados **OK**, ecuaciones **OK**, flujo de control
**OK**, imports públicos y shims **OK**, entrypoints **OK**. Ninguna tolerancia
ni criterio se cambió. No se detectaron regresiones ni archivos del núcleo que
requieran inspección adicional por estos cambios.

Entorno usado: Python 3.14.0, NumPy 2.3.5, SciPy 1.16.3, pandas 2.3.3,
matplotlib 3.10.8, openpyxl 3.1.5, pandapower 3.4.0, pytest 9.1.0. No se
instalaron dependencias. Numba no está disponible; pandapower convergió sin
esa aceleración opcional. La configuración previa de dependencias estaba en
README, sin manifiesto de paquetes; no se introduce uno para esta interfaz.

Revisión Ponytail: dos módulos nuevos, diccionarios estándar y reutilización de
`run_scenario`; sin refactor general, jerarquías de clases, registro de
adaptadores, parser externo ni archivos de investigación eliminados. Los
pendientes académicos siguen siendo la red fuente, su equivalencia eléctrica,
los escenarios y los criterios finales del Objetivo 3.
