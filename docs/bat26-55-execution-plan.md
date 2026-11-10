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
| N3 | Repetir N1 con `rtol=1e-7`, `atol=1e-10`, `max_step=25 μs` | Convergencia contra referencia N1 en el mismo entorno Python |
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
`-1e-9` y cero Ah se evalúan como cero. El umbral coincidía con el `atol=1e-9`
Ah de N1/N2, pero en N3 el `atol` refinado ejecutado es `1e-10` Ah; por tanto,
la banda local es 10 veces dicho atol. No es un límite físico configurable ni
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
listadas entre las regresiones anteriores. Para N3 no se repitieron las campañas
N1/N2 ni los validadores históricos dinámicos. `py_compile` y
`git diff --check` pasaron. N3 se ejecutó después y su evidencia se registra
abajo; N4 sigue pendiente y BAT26-55 no está cerrada.

## N3 — convergencia numérica pack–bus–GFM (2026-11-09)

**PASS numérico interno** con dos integraciones completas del mismo modelo,
perfil E de N1, condiciones iniciales de 15 estados y malla común de salida de
0.5 ms. Se usó un solo intérprete local para evitar diferencias entre entornos:
Python 3.14.0, NumPy 2.3.5 y SciPy 1.16.3. N3 no vuelve a ejecutar N1, N2 ni
validadores históricos. Comando:

```powershell
.venv/Scripts/python.exe -B src/validation/validate_bat26_55_n3_convergence.py
```

La corrida inició el 2026-11-10 00:04:13 UTC y terminó el 2026-11-10
00:06:19 UTC (126.307 s totales, incluidos diagnósticos cortos). RK45 de
referencia (`rtol=1e-6`, `atol=1e-9`, `max_step=50 μs`) completó en 40.810 s,
149888 `nfev` y 24734 pasos aceptados. La malla refinada solicitada
(`rtol=1e-7`, `atol=1e-10`, `max_step=25 μs`) completó en 84.094 s,
293582 `nfev` y 48705 pasos aceptados. Ambos alcanzaron 1.20 s con éxito y
mantuvieron el mismo estado inicial, perfiles de irradiancia/carga y muestreo.

La tabla resume referencia → refinada y delta absoluto. Todas las métricas
escaladas difieren menos de 1%; las diferencias de ventanas cumplen 0.5 ms.

| Métrica | Referencia | Refinada | Diferencia absoluta |
|---|---:|---:|---:|
| Vdc mínimo (V) | 326.338748549 | 326.338746776 | 1.7732e-6 V |
| Vdc máximo (V) | 353.579201197 | 353.579203507 | 2.3101e-6 V |
| Desviación máxima de frecuencia (Hz) | 0.0255915181 | 0.0255915353 | 1.7215e-8 Hz |
| Pico absoluto corriente pack (A) | 7.039887891 | 7.039887889 | 2.1982e-9 A |
| Pico absoluto corriente bus (A) | 6.830625725 | 6.830626612 | 8.8661e-7 A |
| Energía absoluta intercambiada (Wh) | 1.196582053 | 1.196582249 | 1.9544e-7 Wh |
| Energía firmada pack (Wh) | -0.083352536 | -0.083352884 | 3.4804e-7 Wh |
| Energía firmada bus (Wh) | -0.114034127 | -0.114034480 | 3.5305e-7 Wh |
| Pérdidas integradas (Wh) | 0.0306815911 | 0.0306815961 | 5.0112e-9 Wh |
| SoC final | 0.600005564007 | 0.600005564031 | 2.3532e-11 |
| Ventana de carga/descarga (s) | 0.3495 / 0.3495 | 0.3495 / 0.3495 | 0 / 0 s |

Los signos clasificaron las mismas muestras en ambos sentidos (1606 carga,
794 descarga); no hubo cambio de clasificación. Los estados/señales fueron
finitos, el vector tuvo 15 estados, Vdc fue positivo, SoC y tensión de pack
quedaron dentro de sus límites, y corrientes/potencia respetaron los límites
del fixture. El residual algebraico de potencia máximo fue 0 W y el residual
de energía fue menor que `2.8e-17 Wh` en ambas corridas. La carga y descarga
mantuvieron ventanas superiores a 0.10 s.

Para cantidades cercanas a cero se fijaron antes de interpretar resultados:
`7e-4 Wh` para energía firmada casi nula, acotada por el máximo fixture de
5 kW durante un intervalo de 0.5 ms (`5000*0.0005/3600 = 6.94e-4 Wh`), `1e-5 Hz`
para desviación casi nula (1.7e-7 pu respecto a 60 Hz), `1e-12 Ah` para
`z_deg` aceptado y `0.5 ms` para duración de ventanas. En las métricas con escala
significativa se aplicó el límite relativo estricto menor a 1%. No fue necesario
usar estas tolerancias absolutas en las energías medidas, que son distintas de
cero; las ventanas se evaluaron con la tolerancia temporal absoluta.

### Auditoría de tolerancia local `z_deg`

En las dos integraciones de N3 el mínimo observado en etapas internas y estados
aceptados fue 0 Ah, y hubo cero llamadas internas con valor negativo. Además,
se hicieron tres probes RK45 de solo 2 ms desde la condición límite N2
(SoC=0.90, Vdc=339.999 V, `z_deg(0)=0`), no cuatro solves completos N2. Los
umbrales diagnósticos `1e-9` y `1e-10 Ah` completaron ambos con 626 `nfev`,
mínimo interno `-6.9802e-13 Ah` y mínimo aceptado 0 Ah. Un umbral `1e-13 Ah`
detuvo el probe ante la etapa `-1.77998e-13 Ah`, reproduciendo el mecanismo de
N2. RHS puntuales entre `-1e-9` y 0 Ah dieron derivadas idénticas al estado cero;
`-1.01e-9 Ah` se rechazó.

La banda de producción (`1e-9 Ah`) es 10 veces el `atol` refinado de N3, pero
las sondas muestran que es una tolerancia para etapas de prueba RK45, no para
estados aceptados. Su efecto máximo en la ley lineal es `1.478e-15` de SoH y
`9.7548e-14 Ah` de capacidad efectiva; el valor aceptado nunca fue negativo y
la convergencia global pasó. No se detecta evidencia de que enmascare error
físico relevante ni afecte la convergencia en el perfil probado. No se cambió
el código del modelo, la ley ni el umbral.

El criterio `PASS` exige éxito de ambas integraciones, todos los invariantes
físicos y diferencias dentro de los umbrales definidos. `FAIL` corresponde a
fallo de solver, invariante o convergencia. `REVIEW` registra la limitación de
diseño separada del resultado numérico y no revoca el PASS de N3.

**REVIEW de diseño** conservado: el modelo no implementa protección superior
del bus y la trayectoria alcanza 353.579 V. Este punto es una limitación del
modelo, no un fallo numérico ni una afirmación de seguridad. El conversor sigue
siendo un fixture hipotético; N3 no es evidencia experimental/HIL. El JSON
completo está en `outputs/validation/bat26_55_n3_convergence.json`.

## N4 — comparación pack ON/OFF (intento detenido; 2026-11-10)

**BLOCKED; sin resultado numérico N4.** Se inició el comparador
`validate_bat26_55_n4_on_off.py` en el HEAD `213fea13eeac617e13379912e91a0dcaaab3b69a`,
con Python 3.14.0, NumPy 2.3.5 y SciPy 1.16.3. Antes de integrar, el programa
comprueba igualdad exacta de los 12 estados iniciales compartidos, igualdad de
parámetros de planta/controlador y perfiles. El proceso permaneció activo y
consumiendo CPU durante más de una hora, sin retornar los dos objetos de
solución de `solve_ivp`. Se interrumpió manualmente; no se obtuvo `nfev`, tiempo
por solve ni métricas ON/OFF. La ejecución incompleta no permite concluir que
el solver falló ni atribuir inestabilidad física a OFF.

El primer runner solo escribía JSON después de ambos solves. Se corrigió para
guardar progreso antes del solve OFF y entre OFF/ON en futuras ejecuciones. El
JSON actual es un registro del intento bloqueado y declara explícitamente que
no hay resultado parcial disponible; no contiene métricas inventadas. Se
conserva en `outputs/validation/bat26_55_n4_on_off.json` junto con el validador.

No se cambiaron ecuaciones, parámetros, perfiles, estados ni tolerancias. N4 no
está aprobada; no se hizo commit ni push. Para continuar se debe ejecutar el
runner con los mismos perfiles y solver, usando el checkpoint para identificar
qué caso está activo y obtener ambos solves completos. BAT26-55 permanece
abierta; no se ejecutó N4b adicional, no se mezcló con el REVIEW histórico de
6.5 s y no se atribuyeron efectos dinámicos al envejecimiento.

### Diagnóstico N4 y repetición controlada (2026-11-10; registro histórico)

N4 sigue **BLOCKED**: no hay métricas comparativas válidas ni se publicaron
archivos. El intento anterior de más de una hora no conservó el escenario activo,
por lo que no puede atribuirse retrospectivamente con certeza. En el nuevo
intento instrumentado se identificó el problema en **OFF dentro de `solve_ivp`**.
Los límites se mantuvieron: RK45, `rtol=1e-6`, `atol=1e-9`, paso máximo 50 μs,
perfil E y estados iniciales compartidos iguales. Los logs completos están en
`outputs/validation/bat26_55_n4_performance.log`; `max_rhs_time_s` es el máximo
instante evaluado por el RHS y puede ser una etapa interna o rechazada, no un
estado aceptado. Python 3.14.0, NumPy 2.3.5 y SciPy 1.16.3.

| Horizonte (s) | ON tiempo solve (s) / nfev | OFF tiempo solve (s) / nfev |
|---:|---:|---:|
| 0.01 | 0.998 / 2714 | 0.501 / 2828 |
| 0.05 | 2.611 / 10544 | 1.065 / 10802 |
| 0.20 | 8.068 / 28946 | 3.551 / 29300 |
| 0.45 | 15.781 / 59282 | 6.760 / 59630 |
| 0.85 | 28.873 / 107888 | 12.716 / 108248 |

Los tiempos de 0.01 s incluyen `cProfile`, por lo que no son directamente
comparables con los demás. El perfil señala `_compute_step_control` y GFM en
ambas rutas; ON añade el puerto BESS y el RHS de batería. En un ensayo aparte
de 0.01 s/21 muestras sin perfilador, integración / reconstrucción / serialización
JSON tardaron 0.294 / 0.0198 / 0.00031 s OFF y 0.511 / 0.0366 / 0.00038 s ON.
No se extrapolan esos tiempos de posprocesado al horizonte completo.

En la campaña de 1.20 s, OFF avanzó normalmente hasta cerca de 0.8946 s y
después acumuló 1,356,292 evaluaciones en 175.0 s, con máximo tiempo de RHS
0.895393 s. Se detuvo el árbol completo de procesos con un guardia externo a
aproximadamente 178 s para no exceder los 180 s; el runner original interpretó
la terminación como salida 1 y el JSON fue anotado posteriormente como BLOCKED.
No se inició el solve completo ON tras ese bloqueo. El supervisor local se
corrigió para que los futuros timeouts terminen también el hijo de Python en
Windows y queden como BLOCKED. El tiempo de serialización del resultado completo
no se dispone porque OFF nunca retornó.

Una sonda OFF independiente con evento terminal a 200.001 V llegó a
`t=0.894614129 s` en 15.329 s y 113672 evaluaciones. En ese mismo estado se
sondeó el RHS a ambos lados del umbral UVLO de 200 V: a 199.999999 V,
`dVdc/dt=+3055.513 V/s`, potencia de puente y corriente de inversor cero; a
200.000001 V, `dVdc/dt=-719.573 V/s`, potencia 1464.733 W y corriente 7.550 A.
Las derivadas apuntan hacia la discontinuidad desde ambos lados. Esta evidencia
explica la reducción extrema de paso y el costo observado como conmutación
repetida alrededor de UVLO; no demuestra inestabilidad física ni prueba qué
ocurrió en el intento anterior sin instrumentación.

El validador también reconstruía ON mediante `power_signals`, que no incorpora
los valores de supervisión BESS al control GFM. Se corrigió solo el cálculo de
señales N4 para usar los mismos valores que el RHS; sondas con Vdc=330 y 350 V
confirmaron `p_cmd` real de 4000 y 1929.250 W frente a 3675.005 y 3626.750 W
del helper anterior. Este defecto afecta el informe, no explica la lentitud del
solve. La comparación sigue sin realizarse. No se modificaron las ecuaciones,
parámetros, controlador, DC/DC, BLAST, arquitectura ni tolerancias.

Opciones futuras requieren decisión explícita: estudiar una formulación híbrida
con eventos y reglas de conmutación verificadas, o modelar histéresis de UVLO
si se justifica físicamente y se aprueba el cambio de comportamiento. También
puede informarse el tramo anterior al umbral como diagnóstico parcial, sin
presentarlo como comparación N4 de 1.20 s. Ninguna opción se aplicó aquí.
La sonda del umbral puede reproducirse con
`python -B src/validation/validate_bat26_55_n4_on_off.py --diagnose-uvlo`;
una ejecución completa usa procesos separados y límite de 180 s. N4 y BAT26-55
permanecen abiertas; este trabajo no es validación experimental ni HIL.

### N4 — comparación diagnóstica pre-UVLO (2026-11-10)

**Revisión metodológica posterior a las corridas exploratorias, no criterio
predeclarado.** El solve OFF exploratorio de 1.20 s se volvió prohibitivamente
lento al aproximarse a la discontinuidad de conmutación del UVLO; las sondas
independientes mostraron derivadas de Vdc dirigidas hacia el umbral de 200 V
desde ambos lados. Para obtener una comparación emparejada reproducible sin
cambiar la física ni integrar la región de chattering, se adoptó después el
endpoint diagnóstico de observación a 201 V. Este endpoint no equivale al UVLO
de 200 V, no es un disparo de protección, no demuestra desconexión física y no
se presenta como criterio fijado antes de los experimentos exploratorios.

Se conserva el intento `BLOCKED` de 1.20 s y se crea un resultado separado en
`outputs/validation/bat26_55_n4_pre_uvlo.json`. En una corrida con Python
3.14.0 / NumPy 2.3.5 / SciPy 1.16.3, RK45 (`rtol=1e-6`, `atol=1e-9`, paso
máximo 50 μs), perfil E y malla común de 0.5 ms, OFF alcanzó el evento
diagnóstico terminal descendente `Vdc - 201 V = 0` en `t=0.893244040314869 s`.
El estado de evento tiene `Vdc=201 V`; terminó por evento y no por fallo del
solver. OFF utilizó 113438 evaluaciones, 18647 pasos aceptados y 15.891 s de
solve. ON se integró desde cero hasta ese tiempo exacto con los mismos 12
estados iniciales comunes: 113078 evaluaciones, 18599 pasos aceptados y
32.757 s. La ejecución con posprocesamiento tardó 54.395 s. El evento a 201 V
solo delimita la observación: no cambia UVLO (200 V), la planta ni el control.

La auditoría posterior confirmó que ambos casos usan exactamente 1788 muestras
con la misma malla de 0.5 ms más el endpoint común: `[0,
0.893244040314869] s`. OFF solicitó 1.20 s y terminó en el evento a 201 V; ON
solicitó y alcanzó exactamente el mismo endpoint. Las condiciones iniciales
comunes de 12 estados y los parámetros/perfiles protegidos coinciden. Se
corrigió en el validador y el JSON un campo de metadatos `horizon_reached_s`
que había quedado en 0.85 s por reutilizar el nombre de variable del límite de
ventana de déficit; los estados, malla, métricas y solves no se alteraron.

Las verificaciones automáticas pasan: igualdad exacta de los 12 estados
iniciales y de parámetros comunes, perfiles e inversor; dimensiones 12/15 sin
estados BESS ficticios en OFF; solves exitosos, estados y señales finitos,
Vdc positiva, frecuencia derivada de `omega`, balances DC, identidad pack-bus,
pérdidas no negativas, convenciones de signo y SoC dentro de límites. La
reconstrucción ON usa la supervisión BESS efectiva del RHS y su `p_cmd` coincide
con la reconstrucción. ON permaneció por encima de 201 V. El mayor residuo de
balance DC fue menor que `9.1e-13 W`; los residuos de identidad pack-bus y del
puerto fueron cero en las muestras.

Resultados globales en `[0, 0.893244 s]`, con extremos muestreados en la malla
común. El mínimo OFF coincide con el evento y queda censurado por terminación:

| Métrica | ON | OFF | Lectura ON respecto a OFF |
|---|---:|---:|---:|
| Vdc mínimo / máximo (V) | 326.339 / 353.579 | 201.000 / 399.775 | mínimo OFF truncado; máximo −46.195 V |
| Excursión absoluta máxima desde 340 V | 13.661 V | 139.000 V | −125.339 V (−90.17%); mínimo OFF truncado |
| Frecuencia mínima / máxima (Hz) | 59.9744 / 60.0121 | 59.8933 / 60.0326 | nadir +0.08109 Hz; pico −0.02054 Hz |
| Desviación máxima absoluta de 60 Hz | 0.02559 Hz | 0.10668 Hz | −0.08109 Hz (−76.01%) |
| RoCoF máximo absoluto (Hz/s) | 6.022 | 7.208 | −1.186 (−16.45%); diferencia finita no filtrada |
| Energía PCC / PV DC / puente (Wh) | 0.66856 / 0.99677 / 0.67407 | 0.63650 / 0.64095 / 0.64149 | energía PCC ON +0.03206 Wh |

En ON, energía firmada pack = −0.28325 Wh, bus = −0.30394 Wh y pérdidas =
0.02069 Wh; transferencia absoluta por bus = 0.41091 Wh. El signo negativo
corresponde a carga. SoC final = 0.6000192 y SoH = 0.6681818 (snapshot
constante); no se evalúa sensibilidad dinámica al envejecimiento. OFF tiene
transferencia BESS cero por construcción.

La comparación separa preacondicionamiento `[0, 0.4)`, excedente solar estable
`[0.45, 0.8)` y déficit estable `[0.85, t_event]`. En preacondicionamiento,
Vdc máximo fue 344.897 V ON y 379.311 V OFF; en excedente estable, 353.579 V ON
y 399.775 V OFF. La desviación máxima de frecuencia en esas ventanas fue
0.00731/0.03263 Hz y 0.00707/0.01616 Hz (ON/OFF). En el tramo de déficit
muestreado, Vdc mínimo fue 326.339 V ON y 250.970 V OFF, con desviación máxima
de frecuencia 0.01079/0.10517 Hz. Tras excluir los 50 ms posteriores al cambio
de 0.8 s solo quedan 0.043244 s antes del evento, menos de los 0.10 s previstos
para análisis estable. El déficit es parcial, no una respuesta sostenida; los
extremos OFF no representan la trayectoria posterior al evento.

**Clasificación:** `N4 pre-UVLO = PASS` para ejecución, equivalencia e
invariantes, con interpretación `REVIEW` para diseño/alcance. En el intervalo
simulado se observa menor excursión de tensión y desviación de frecuencia con
ON, y no una diferencia despreciable. No es una meta de eficacia predeclarada
ni se generaliza fuera del tramo. `N4 completo de 1.20 s = BLOCKED`: no existen
dos solves completos de 1.20 s. REVIEW incluye la ausencia de protección
superior de Vdc y los máximos observados; no es una afirmación de seguridad.
El ejercicio no valida hardware/HIL, un DC/DC detallado ni efectos dinámicos
de envejecimiento. El JSON contiene métricas y diferencias reproducibles en
`outputs/validation/bat26_55_n4_pre_uvlo.json`; el
`outputs/validation/bat26_55_n4_on_off.json` conserva el BLOCKED original. No
se repitieron N1–N3 ni regresiones históricas.

Para trabajo posterior, una opción es aislar la conmutación UVLO como transición
híbrida por eventos y verificar explícitamente el reinicio del solver en el
cruce; otra es estudiar histéresis solo con justificación física y aprobación
explícita. No se aplicó ninguna modificación de UVLO en N4.

La separación de resultados es intencional: el JSON
`bat26_55_n4_on_off.json` y las secciones exploratorias anteriores documentan
el intento original completo **BLOCKED**, sin comparación ON/OFF completa. El
JSON `bat26_55_n4_pre_uvlo.json` documenta el ensayo metodológicamente acotado:
**PASS numérico / REVIEW interpretativo** hasta 201 V. Ninguno sustituye ni
reclasifica al otro. En particular, la comparación numérica hasta 201 V no
sustituye dos integraciones ON/OFF completas hasta 1.20 s. N1, N2 y N3 mantienen
sus estados PASS numéricos sin repetición en esta auditoría.
