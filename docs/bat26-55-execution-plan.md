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
| N1 | Un solve global GFM con pack, horizonte inicial 0.30 s, perfil carga→descarga elegido por calibración de perfiles y declarado antes del solve aceptado | Carga y descarga sostenidas, energía, límites y continuidad temporal |
| N2 | Mismo solve N1 con estado inicial exactamente en SoC mínimo/máximo, más probes de tensión pack fuera de rango y Vdc no positivo | Bloqueos SoC y protecciones de adaptador; comparar flags y potencia cero |
| N3 | Repetir N1 con `rtol=1e-7`, `atol=1e-9`, `max_step=25 μs` | Convergencia contra tolerancias BAT26-55 actuales |
| N4a/N4b | Pack habilitado y deshabilitado, mismo vector inicial de planta, perfiles, `p_ref`, capacidad configurada, solver y horizonte | Diferencia atribuible a activar el pack; reportar señales y deltas sin imponer mejora |

Si N1 requiere más de 0.30 s para obtener ambas ventanas continuas, extender el
horizonte en incrementos declarados antes de la corrida aceptada y registrar
el costo esperado `T/max_step` por trayectoria. La calibración solo busca una
excitación reproducible con perfiles existentes; no cambia ganancias, ley de
control, parámetros físicos ni ecuaciones. Protecciones estáticas y trayectorias
dinámicas se presentan como dos tipos de evidencia distintos.

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
| BAT26-53 | auditoría aritmética pack | 0.325 s | PASS aritmético solamente |
| BAT26-55 | 7 pruebas algebraicas | 0.804 s de proceso | PASS |
| DC/DC | 15 pruebas unitarias | 0.329 s | PASS |
| Obj. 1 | LCL + BESS step 3 + límites SoC | 31.318 s | PASS; artefactos generados restaurados |

Todos los datos JSON se guardaron bajo `/tmp` para no sustituir salidas
versionadas. El GFM integrado reprodujo el REVIEW histórico de +40 %; no se
convirtió en PASS.

Las pruebas integradas nuevas N1–N4 están **BLOCKED / diseñadas, no ejecutadas**:
falta calibrar y declarar un perfil único que produzca ventanas sostenidas de
carga y descarga bajo el controlador existente. El solve actual de 0.30 s
solo demuestra descarga; no se presenta como cobertura de carga sostenida,
convergencia refinada ni comparación del pack habilitado/deshabilitado. La
calibración no cambia el modelo y debe preceder la aceptación experimental.

Los dos códigos 124 originales significan `BLOCKED: límite de 240 s`, no PASS
ni FAIL. El histórico previo de BAT26-55 registra resultados de `cf0a9f0` y de
la corrección, pero no sustituye la medición actual. No se fusiona ningún PR.
