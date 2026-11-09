# BAT26-55 — plan reproducible de ejecución y pruebas integradas

## Separación de evidencia

Las regresiones históricas y las pruebas nuevas deben informarse por separado.

**Regresiones históricas** (contrato preexistente):

1. `python -B src/validation/validate_obj1_regression.py` (LCL, BESS step 3 y
   límites operacionales SoC).
2. `python -B -m unittest discover -s src/validation -p
   test_dc_dc_adapter.py -v`.
3. `python -B src/validation/validate_physical_invariants.py`.
4. `python -B src/validation/validate_gfm_integrated_system.py`.

**BAT26-55** (contrato nuevo):

1. `python -B src/validation/validate_bat26_53_pack_48s.py`.
2. `python -B src/validation/validate_bat26_55_pack_bus_gfm.py --test`.
3. `python -B src/validation/validate_bat26_55_pack_bus_gfm.py`.
4. Nuevos ensayos globales pack–bus–GFM descritos abajo. No se sustituyen las
   regresiones históricas por los ensayos nuevos.

No se deben ejecutar en paralelo: cada solve usa un RHS Python costoso y la
contención hace los tiempos no reproducibles. El runner debe usar un único
proceso Python local, registrar comando, commit, versión de Python/NumPy/SciPy,
hora UTC inicial/final, duración monotónica, código de salida, `nfev`, mensaje
del solver y JSON completo. No debe imponer timeout de aplicación. Una
interrupción conserva el log y se marca `BLOCKED` con último escenario y
tiempo transcurrido; nunca se promueve a PASS. Las salidas van a un directorio
de corrida nuevo para no sobrescribir evidencia versionada.

## Presupuesto de cómputo conocido

La configuración protegida es `max_step=5e-5 s`, `rtol=1e-6`, `atol=1e-8`.
Para `T=6.5 s`, cada solve requiere al menos 130 000 pasos aceptados; el número
real de evaluaciones es mayor y depende de rechazos y pasos adaptativos.

| Validador | Escenarios / solves independientes | Piso de pasos aceptados |
|---|---:|---:|
| `validate_physical_invariants.py` | 2 solves de 6.5 s | 260 000 |
| `validate_gfm_integrated_system.py` | 4 solves de 6.5 s (el registro comparativo reutiliza 2) | 520 000 |
| BAT26-55 actual | 4 solves de 0.30 s | 24 000 |

Este conteo es una cota de trabajo, no una predicción de tiempo. Para estimar
duración antes de una campaña completa, ejecutar una sola vez un escenario
representativo y medirlo con reloj monotónico. No usar `timeout 240s` ni
repetir cuatro solves de inmediato. Ejecutar después el conjunto completo en
Python local con alimentación estable y espacio suficiente para logs; dejar
el proceso terminar. La ejecución completa de las regresiones originales
requiere aproximadamente seis solves de 6.5 s, no un solo solve agregado.

## Pruebas integradas nuevas: criterios previos

Se empleará un único `solve_ivp` global por trayectoria, estado de 15
componentes, `GFMController`, `M=80`, `D=1500`, capacidad inicial e irradiancia
iguales dentro de cada comparación. No se altera ninguna ecuación ni ganancia.
La configuración DC/DC sigue siendo un fixture hipotético y debe etiquetarse
como tal.

Métricas a calcular sobre señales reconstruidas desde cada estado muestreado:

- duración de carga y descarga continua, energía firmada de pack y bus,
  eficiencias/pérdidas integradas y extremos de corriente/potencia;
- `Vdc` mínimo/máximo, frecuencia dinámica `omega/(2*pi)`, nadir/desviación,
  RoCoF y tiempo de establecimiento según ventanas declaradas;
- SoC/SoH, tensión de pack, flags de saturación por etapa y estado de
  protección; residual de `P_bus=Vdc*I_bus`, balance energético y finitud;
- diferencias entre BESS activo y desactivado bajo idénticos perfiles,
  `p_ref`, estado inicial de planta, horizonte, tolerancias y muestreo.

Criterios de aceptación numérica fijados antes de correr:

- solver exitoso, vector de 15 estados finito, `Vdc>0`, SoC dentro de los
  límites del modelo y tensión/corriente/potencia dentro de los límites
  declarados;
- carga y descarga demostradas durante ventanas continuas de al menos 0.10 s
  cada una, con signos coherentes en `I_pack`, `I_bus` y potencia; las
  protecciones de sobretensión, subtensión, bus no positivo y fronteras SoC
  bloquean la transferencia y reportan el motivo esperado;
- residual algebraico de potencia menor o igual a `1e-8 W + 1e-10 * escala`,
  residual de conversión de energía menor o igual al 0.1% de energía absoluta
  transferida (excluyendo trayectorias con energía neta casi cero);
- convergencia: repetir un caso de referencia con `rtol/atol` diez veces más
  estrictos y máximo paso mitad. Entre mallas, exigir diferencias relativas
  menores a 1% en energía, pico de corriente, Vdc mínimo y desviación máxima
  de frecuencia; ninguna clasificación física puede cambiar;
- comparación activa/desactivada: igualdad exacta de perfiles y parámetros,
  mismo solver/horizonte y diferencia medible reportada. No exigir mejora de
  frecuencia o Vdc como requisito de ejecución: un resultado sin mejora queda
  `REVIEW`, no se falsifica como PASS ni FAIL de software.

Debe escogerse un perfil de irradiancia/carga que produzca carga y descarga
continuas antes de la campaña de capacidad. Si no hay un perfil común que las
produzca sin cambiar el controlador, el informe registra el bloqueo y no
declara cubierta esa prueba. No se infieren efectos del SoH; se mantienen
capacidad inicial y condiciones idénticas para aislar la comparación.

Matriz de ejecución propuesta, separada de las regresiones anteriores:

| ID | Escenario | Propósito |
|---|---|---|
| N1 | Un solve global GFM con pack, horizonte 1.20 s, perfil carga→descarga con 0.40 s de preacondicionamiento documentado abajo | Carga y descarga sostenidas, energía, límites y continuidad temporal |
| N2 | Mismo solve N1 con estado inicial exactamente en SoC mínimo/máximo, más probes de tensión pack fuera de rango y Vdc no positivo | Bloqueos SoC y protecciones de adaptador; comparar flags y potencia cero |
| N3 | Repetir N1 con `rtol=1e-7`, `atol=1e-9`, `max_step=25 μs` | Convergencia contra tolerancias BAT26-55 actuales |
| N4a/N4b | Pack habilitado y deshabilitado, mismo vector inicial de planta, perfiles, `p_ref`, capacidad configurada, solver y horizonte | Diferencia atribuible a activar el pack; reportar señales y deltas sin imponer mejora |

La calibración usa niveles de irradiancia ya presentes en la configuración
PV (400, 800, 1000 W/m²; el candidato A conserva el caso previo de 200 W/m²)
y cargas de 2.4, 3.0, 3.6 y 4.2 kW. No cambia ganancias, ley de control,
parámetros físicos ni ecuaciones. Protecciones estáticas y trayectorias
dinámicas se presentan como dos tipos de evidencia distintos.

## Desbloqueo y resultado N1

Antes de simular se evaluó el RHS y el intercambio de puertos en estados
iniciales de 15 estados. La ley existente pide descarga si `Vdc<340 V`, carga
si `Vdc>340 V` y cero a 340 V. A 330 V los sondeos dan `I_pack=+5.209 A`,
`I_bus=+5.000 A`, `P_bus=+1650 W`; a 350 V dan `I_pack=-4.967 A`,
`I_bus=-5.000 A`, `P_bus=-1750 W`. A 340 V ambas corrientes y potencia son
cero. No se forzó `Vdc` durante ninguna integración.

En el estado de reinicio, las corrientes AC iniciales son cero; por eso
`dVdc/dt` aún no refleja la demanda y variar solo carga no cambia ese valor
puntual. Con `Vdc=340 V`, los valores de `dVdc/dt` al cambiar irradiancia son
986.900, 2516.740, 5576.407 y 7106.243 V/s para 200, 400, 800 y 1000 W/m²
respectivamente; la potencia BESS permanece cero en ese instante. Estos son
diagnósticos del RHS en el estado inicial, no respuestas de régimen. La
selección se hizo con las trayectorias globales siguientes.

Todos los candidatos usan Qeff=44.1 Ah, SoC inicial 0.60, SoH snapshot
0.6681818, `GFMController(p_ref=4000 W, M=80, D=1500)`, la topología de un
string con 96 unidades 2p en serie, `RK45`, `rtol=1e-6`, `atol=1e-9`,
`max_step=50 μs`, muestreo cada 0.5 ms y un solve global de 15 estados. Fixture
DC/DC hipotético común: eficiencia 0.95 en ambos sentidos, límite por unidad
10 A, bus 20 A y 5 kW. En la tabla, ventanas medidas excluyen los primeros
50 ms del horizonte; en los perfiles con transición a 0.40 s también se
reporta si los signos continúan tras la transición. Todos los solves acabaron
con éxito, estados/señales finitos, saturaciones 0 y protecciones `ok`.

| ID | Perfil (G en W/m²; carga en kW) | Ventana de carga | Ventana de descarga | SoC observado | Vdc (V) | Frecuencia (Hz) | Máx. `|Ipack|` / `|Ibus|` (A) | `Pbus` mínimo–máximo (kW) | Pérdida máx. (W) | Tiempo | Evaluación |
|---|---|---|---|---|---|---|---|---|---:|---:|---|
| A | G=200; 3.0 hasta 0.1 s, después 4.2; 0.8 s | ninguna | 0.750 s (0.050–0.800) | 0.599953–0.600000 | 320.869–340.000 | 59.98783–60.00500 | 9.713 / 9.565 | 0–3.069 | 161.54 | 22.291 s | No cubre carga; sí descarga sostenida |
| B | G=1000; carga constante 2.4; 0.8 s | 0.750 s (0.050–0.800) | ninguna | 0.600000–0.600034 | 340.000–353.662 | 60.00000–60.01629 | 6.852 / 6.831 | −2.416–0 | 120.79 | 23.016 s | No cubre descarga |
| C | 0–0.4 s G=1000/carga 2.4; después G=400/carga 4.2; 0.8 s | 0.353 s (0.050–0.403) | 0.397 s (0.404–0.800) | 0.5999996–0.6000171 | 326.339–353.662 | 59.97441–60.01629 | 7.041 / 6.831 | −2.416–2.229 | 120.79 | 21.152 s | Ambos sentidos; fase de carga empieza al inicio |
| D | 0–0.4 s G=800/carga 2.4; después G=400/carga 3.6; 0.8 s | 0.353 s (0.050–0.403) | 0.397 s (0.403–0.800) | 0.5999963–0.6000098 | 329.512–347.985 | 59.98299–60.01058 | 5.455 / 5.244 | −1.389–1.728 | 90.94 | 22.925 s | Ambos sentidos; fase de carga empieza al inicio |
| E | 0–0.4 s G=800/carga 3.0; 0.4–0.8 G=1000/carga 2.4; 0.8–1.2 G=400/carga 4.2 | 0.350 s (0.450–0.800) | 0.350 s (0.850–1.200) | 0.600000–0.6000230 | 326.339–353.579 | 59.97441–60.01210 | 7.040 / 6.831 | −2.401–2.229 | 120.03 | 31.988 s calibración; 31.857 s N1 | Aceptado: ambas ventanas después del preacondicionamiento |

Los intervalos de E medidos en la malla de 0.5 ms son 0.450–0.7995 s para
carga y 0.850–1.1995 s para descarga (cada uno 0.3495 s). Así, ninguno depende
exclusivamente del transitorio inicial. La corriente de pack máxima queda bajo
10 A, la del bus bajo 20 A y la potencia del bus bajo 5 kW; Vdc es positivo,
SoC permanece en límites y Vpack queda entre 333.240 y 335.066 V. Se observaron
`P_bus=Vdc*I_bus` con residual máximo cero, `P_pack=P_bus+P_loss` con residual
integrado `−7.29e−17 Wh`, pérdidas máximas de 120.03 W y 0.030682 Wh acumulados.
La potencia BESS firmada integrada fue −0.083353 Wh en pack y −0.114034 Wh en
bus. Frecuencia se reconstruyó exclusivamente como `omega/(2*pi)`. Las cuatro
banderas de saturación tuvieron fracción cero y el estado de protección fue
`ok` en toda la trayectoria; N1 verifica el monitoreo, no la activación de
protecciones, reservada para N2.

N1 pasa con Python 3.12.14, NumPy 2.3.5 y SciPy 1.17.0 mediante:

```bash
python -B src/validation/validate_bat26_55_n1_profile.py
```

El validador escribe el resumen reproducible en
`outputs/validation/bat26_55_n1_profile.json`; registró 149888 `nfev` y
31.857 s de integración. Se conserva `aging_mode="blast"` con snapshot inicial
de capacidad: SoH permaneció 0.6681818 durante esta ventana; no se atribuye
ningún efecto dinámico al SoH. Los ratings/eficiencias DC/DC siguen siendo
fixtures hipotéticos, no especificaciones certificadas.

## Estado de ejecución

Las corridas de los dos validadores que habían agotado 240 s se completaron en
Python local sin límite artificial. El commit de base fue
`e61580526776975faddeb4cfbc6d4114ce80d043`; las ejecuciones no modificaron
fuentes ni parámetros.

| Grupo | Escenario | Tiempo medido | Resultado |
|---|---|---:|---|
| Invariantes históricas | GFM sin BESS, escalón 20 %, 6.5 s | 82.721 s; 785456 `nfev` | PASS |
| Invariantes históricas | GFM+BESS-PI, escalón 20 %, 6.5 s | 136.905 s; 785096 `nfev` | PASS |
| Invariantes históricas | campaña completa, 2 solves | 220.373 s | PASS: balance DC, identidad de potencia, SoC y signos |
| GFM histórico | steady, 6.5 s | 77.299 s; 785210 `nfev` | PASS |
| GFM histórico | escalón +20 %, sin BESS, 6.5 s | 77.883 s; 785456 `nfev` | PASS |
| GFM histórico | escalón +40 %, sin BESS, 6.5 s | 74.299 s; 785672 `nfev` | REVIEW documentado |
| GFM histórico | escalón +20 %, BESS-PI, 6.5 s | 137.858 s; 785096 `nfev` | PASS |
| GFM histórico | campaña completa, 4 solves | 385.395 s | REVIEW global; sin fallos de solver |
| BAT26-55 actual | cuatro capacidades, 0.30 s cada una | 36.245 s total | PASS; descarga en las cuatro |
| BAT26-55 N1 | perfil E, carga y descarga con preacondicionamiento, 1.20 s | 31.857 s; 149888 `nfev` | PASS; ventanas continuas de 0.3495 s por sentido |
| BAT26-53 | auditoría aritmética pack | 0.325 s | PASS aritmético solamente |
| BAT26-55 | 7 pruebas algebraicas | 0.804 s de proceso | PASS |
| DC/DC | 15 pruebas unitarias | 0.329 s | PASS |
| Obj. 1 | LCL + BESS step 3 + límites SoC | 31.318 s | PASS; artefactos generados restaurados |

Todos los datos JSON se guardaron bajo `/tmp` para no sustituir salidas
versionadas. El GFM integrado reprodujo el REVIEW histórico de +40 %; no se
convirtió en PASS.

N1 está **PASS** como validación numérica interna del perfil precondicionado
descrito arriba. No equivale a evidencia de hardware, HIL, protecciones activas
ni estabilidad de largo plazo. N2, N3 y N4 siguen pendientes y no se ejecutaron
en esta tarea.

Los dos códigos 124 originales significan `BLOCKED: límite de 240 s`, no PASS
ni FAIL. El histórico previo de BAT26-55 registra resultados de `cf0a9f0` y de
la corrección, pero no sustituye la medición actual. No se fusiona ningún PR.

## N2 — protecciones pack–bus–GFM (2026-11-09)

**PASS numérico interno**: 39/39 comprobaciones estáticas y 70/70 dinámicas
reconstruidas, con cuatro integraciones globales de 15 estados completadas.
Son comprobaciones nuevas, no los 95 checks originales de Cloud. Se mantienen
`GFMController`, M=80, D=1500, snapshot 44.1 Ah, fixture DC/DC hipotético y
el perfil E de N1. La evidencia completa está en
`outputs/validation/bat26_55_n2_protections.json`. La rama partió del commit
`4224c4d58e59d5942e2869b847f8172e97f4eeb3`; el código ejecutado incluía los
cambios locales de N2. Python 3.14.0, NumPy 2.3.5, SciPy 1.16.3; UTC
23:40:37–23:43:53; duración total monotónica 195.709 s.
Tras la corrida se añadieron al JSON únicamente la anotación REVIEW y el
código de salida; luego se añadió al runner el guardado parcial `BLOCKED` y
la prevención de sobrescritura. Las comprobaciones estáticas del runner final
se volvieron a ejecutar; no se repitieron los solves por cambios de reporte.

| SoC inicial | Vdc inicial | nfev | Integración (s) | Comprobaciones | Vdc máximo (V) |
|---:|---:|---:|---:|---:|---:|
| 0.10 | 330 | 149972 | 43.946 | 18/18 | 353.579 |
| 0.10 | 350 | 149852 | 44.407 | 17/17 | 353.579 |
| 0.90 | 330 | 149846 | 48.508 | 17/17 | 399.775 |
| 0.90 | 350 | 149840 | 56.366 | 18/18 | 399.775 |

Los estados aceptados de throughput fueron no negativos en las cuatro
trayectorias. La tolerancia de SoC usada para evaluar límites es 1e-9; el
mayor SoC aceptado fue 0.900000000113391. Las pruebas estáticas comprueban
bloqueo direccional y recuperación, subtensión/sobretensión del pack y bus
nulo/negativo para ambas solicitudes y reposo. Los ensayos dinámicos prueban
respuesta inicial, bloqueo cuando comienza en la dirección prohibida,
recuperación, finitud, límites declarados e identidades algebraicas de potencia.

**REVIEW de diseño**: durante el bloqueo de carga, Vdc llegó a 399.775 V.
Actualmente no se modela una protección superior de tensión del bus; no se
infiere que el valor sea seguro ni se presenta como protección actuante.
La evaluación es numérica, no validación experimental ni de hardware.
**FAIL** se reserva para checks fallidos, integración incompleta o excepción;
no se convierte ese REVIEW en fallo de software ni en protección implementada.

### Diagnóstico y corrección

El chequeo estricto anterior fue reproducido con RK45 y el modelo N2: desde
SoC=0.90, Vdc=339.999 V, una evaluación interna recibió
`z_deg=-1.7799833744101956e-13 Ah` en `t=8.269636213425761e-7 s`; el último
estado aceptado era `z_deg=1.0036913816616821e-14 Ah` en
`t=9.99626355469048e-8 s`. El diagnóstico reproduce el mecanismo, no afirma
reproducir exactamente los valores reportados en Cloud. Las etapas de RK45
pueden emplear coeficientes negativos aunque la derivada sea no negativa.

Solo dentro de `MicrogridWithBESS.system_dynamics`, valores de trabajo entre
`-1e-9` y cero Ah se evalúan como cero. El umbral coincide numéricamente con
el `atol=1e-9` Ah del estado en N1/N2; no es un límite físico configurable ni
una proyección de estados aceptados. Los valores más negativos se rechazan y
los métodos públicos de estado y diagnóstico permanecen estrictos. No cambia
`dz_deg/dt=abs(I_pack)/3600`, el vector, ni la ley de capacidad. La solución
no modifica el RHS propio de la arquitectura opcional de 16 estados.

Una primera campaña exploratoria completó los cuatro solves, pero el validador
marcó erróneamente FAIL porque exigía bloqueo también al caso que arranca en
sentido permitido y se aleja del límite. Se corrigió ese criterio antes de la
campaña final; sus resultados no se mezclan con los de la tabla.

Reproducción desde la raíz (usar el Python del entorno con dependencias):

```powershell
.venv/Scripts/python.exe -B src/validation/validate_bat26_55_n2_protections.py --static --output "$env:TEMP/bat26_n2_static.json"
.venv/Scripts/python.exe -B src/validation/validate_bat26_55_n2_protections.py --output "$env:TEMP/bat26_n2_new.json"
.venv/Scripts/python.exe -B -m unittest discover -s src/validation -p test_bess_zdeg_rhs_tolerance.py -v
```

Las pruebas puntuales de snapshot (6), interfaz de controlador (7), tolerancia
(1), puertos BAT26-55 (7) y adaptador DC/DC (15) pasaron; estas dos últimas
se ejecutaron como comprobaciones algebraicas pertinentes, pese a estar también
listadas entre las regresiones anteriores. No se repitieron las campañas N1,
N3, N4 ni los validadores históricos dinámicos. `py_compile` y
`git diff --check` pasaron. N3 y N4 siguen pendientes; BAT26-55 no está cerrada.
