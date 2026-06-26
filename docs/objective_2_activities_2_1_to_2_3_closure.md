# Objective 2 Closure: Activities 2.1 to 2.3

## 1. Proposito y alcance

Este documento consolida el cierre tecnico de las Actividades 2.1, 2.2 y 2.3
del Objetivo especifico 2. Reune el diseno del controlador de inercia virtual,
las restricciones BESS/BMS, la sintonizacion multi-escenario y la validacion de
estabilidad de pequena senal del VSG clasico implementado.

El alcance queda delimitado asi:

- no es FOVIC;
- no es validacion experimental;
- no es una prueba de busqueda de optimo global;
- el acople IEEE 33 sigue siendo secuencial y unidireccional;
- el modelo BESS no representa un BMS industrial final.

El resultado `REVIEW` usado en este cierre no equivale a error de software. Es
una decision de trazabilidad para conservar limitaciones fisicas o
interpretativas que permanecen dentro del alcance implementado.

## 2. Arquitectura final

La arquitectura final implementada para el Objetivo 2 integra:

- arreglo PV con modelo de un diodo;
- enlace DC con estado `Vdc`;
- inversor promediado;
- filtro LCL en coordenadas `abc`;
- carga trifasica R-L balanceada;
- controlador `GFMController` con dinamica VSG clasica;
- BESS-SLB con modelo Thevenin 1RC y degradacion de primer orden;
- PI externo opcional del enlace DC en `MicrogridWithBESSPI`;
- supervision simplificada de SoC, SoH, corriente disponible y potencia
  disponible.

El flujo energetico principal es:

```text
PV -> enlace DC -> inversor promediado -> filtro LCL -> PCC -> carga R-L
```

El BESS se conecta bidireccionalmente al enlace DC mediante la corriente
firmada `i_bess`. La supervision BMS usada aqui limita SoC, SoH, corriente y
potencia, pero no constituye un BMS industrial final.

Diagrama relativo:

`figures/objective_2_vsg_bess_block_diagram.svg`

## 3. Actividad 2.1: diseno del controlador

La Actividad 2.1 queda documentada en detalle en
`objective_2_virtual_inertia_controller_design.md`. El controlador activo para
la integracion es `GFMController`, con la estrategia VSG clasica seleccionada.

La ecuacion de oscilacion virtual implementada es:

```text
domega/dt = (P_ref_eff - P_e - D*(omega - omega_ref))/M
```

La dinamica angular protegida es:

```text
dtheta/dt = omega
```

La potencia electrica realimentada se calcula con la tension completa del PCC:

```text
P_e = v_pcc^T*i2
```

La frecuencia dinamica se deriva de:

```text
frequency_hz = omega/(2*pi)
```

La referencia activa efectiva `P_ref_eff` se limita por disponibilidad DC y por
la contribucion BESS admisible. Si el BESS carga, su potencia DC firmada reduce
la disponibilidad neta; si descarga, solo aumenta el soporte dentro de los
limites de SoC, SoH, corriente y potencia.

Unidades del punto seleccionado:

```text
M = 80 W*s^2/rad
D = 1500 W*s/rad
alpha = no aplicable
```

`M` y `H` no son equivalentes directamente. La relacion convencional solo puede
usarse si se declara una base:

```text
M = 2*H*S_base/omega_ref
```

Este cierre no declara una nueva `S_base`, por lo tanto no calcula un valor
numerico de `H`.

Mapeo protegido de estados:

```text
GFM sin BESS:
x[10] = omega
x[11] = theta

GFM con BESS:
x[12] = soc_bess
x[13] = vrc_bess
x[14] = zdeg_bess

GFM con BESS y PI externo:
x[15] = xi_bess_vdc
```

La Actividad 2.1 queda en estado formal `PASS`.

## 4. Actividad 2.2: restricciones BESS/BMS

La evidencia de la Actividad 2.2 esta en:

- `src/validation/validate_objective2_bess_control_limits.py`
- `outputs/validation/objective2_bess_limits/summary.json`
- `outputs/validation/objective2_bess_limits/summary.csv`

El validador cubre quince criterios:

1. operacion nominal;
2. SoC proximo al limite inferior;
3. SoC proximo al limite superior;
4. bloqueo de descarga en `soc_min`;
5. bloqueo de carga en `soc_max`;
6. SoH alto, medio y degradado;
7. saturacion de corriente;
8. saturacion de potencia;
9. reduccion de disponibilidad por SoH;
10. carga y descarga;
11. BESS deshabilitado;
12. anti-windup;
13. estados y senales finitas;
14. identidad `p_bess_dc = Vdc*i_bess`;
15. ausencia de violaciones operativas.

Conteo exacto:

```text
14 PASS
1 REVIEW
0 FAIL
```

El `REVIEW` corresponde a la advertencia interpretativa sobre la escala
`Vdc/vt_bess`. No corresponde a una violacion de SoC, SoH, corriente, potencia,
identidad fisica, signos o anti-windup.

Estado de la Actividad 2.2:

```text
Cerrada en REVIEW con limitacion declarada
```

## 5. Actividad 2.3: sintonia multi-escenario

La evidencia de sintonizacion esta en:

- `src/validation/tune_objective2_vsg_parameters.py`
- `outputs/validation/objective2_vsg_tuning/tuning_results.csv`
- `outputs/validation/objective2_vsg_tuning/tuning_summary.json`

Dominio evaluado:

```text
M = [20, 50, 80]
D = [200, 850, 1500]
9 candidatos
```

Escenarios formales:

- `load_step_20_no_bess`
- `load_step_20_bess_pi_nominal_soh`
- `irradiance_drop_20_bess_pi`

Escenario extendido:

- `load_step_40_no_bess`

La funcion objetivo normalizada combina desviacion de frecuencia, RoCoF,
recuperacion de frecuencia, error estacionario de frecuencia, desviacion del
enlace DC, error estacionario de `Vdc`, estres de corriente BESS, estres de
potencia BESS y excursion de SoC. Los pesos son escalas de diseno, no
estandares universales.

Ranking corregido:

| Posicion | M | D | Puntuacion formal | Estado escenarios formales | Estado severo extendido |
| ---: | ---: | ---: | ---: | --- | --- |
| 1 | 80 | 1500 | 0.13438663777278462 | PASS | FAIL |
| 2 | 80 | 850 | 0.13719564782786461 | PASS | FAIL |
| 3 | 50 | 1500 | 0.144406151722225 | PASS | FAIL |
| 4 | 50 | 850 | 0.14746423377208218 | PASS | FAIL |
| 5 | 80 | 200 | 0.1596054104778474 | PASS | FAIL |
| 6 | 50 | 200 | 0.17040145615148955 | PASS | FAIL |
| 7 | 20 | 1500 | 0.18117787009768932 | PASS | FAIL |
| 8 | 20 | 850 | 0.18673044105702497 | PASS | FAIL |
| 9 | 20 | 200 | 0.20941380415882077 | PASS | FAIL |

La seleccion se denomina:

```text
punto seleccionado dentro del dominio multi-escenario evaluado
```

Resultado seleccionado:

```text
M = 80
D = 1500
formal_aggregate_score = 0.13438663777278462
formal_domain_selection_status = PASS
```

No se afirma robustez para el escenario severo sin BESS.

## 6. Metricas del punto seleccionado

Configuracion de calculo:

```text
rocof_window = post_event
rocof_dt = 0.001 s
solver_max_step = 5e-5 s
```

| Escenario | RoCoF maximo | Desviacion maxima de frecuencia | Vdc_min | Vdc_min_required | Estado |
| --- | ---: | ---: | ---: | ---: | --- |
| `load_step_20_no_bess` | 0.8349562789220499 Hz/s | 0.007438528600062 Hz | 364.76328025611036 V | 327.5020881285063 V | PASS |
| `load_step_40_no_bess` | 1.6536822726678224 Hz/s | 0.02240762711011257 Hz | 313.8643954758725 V | 327.5020881285063 V | FAIL |
| `load_step_20_bess_pi_nominal_soh` | 0.6201204867721799 Hz/s | 0.003865342756164125 Hz | 341.380259704056 V | 327.5020881285063 V | PASS |
| `irradiance_drop_20_bess_pi` | 1.5758551337192728 Hz/s | 0.003924070989420159 Hz | 344.08972096502674 V | 327.5020881285063 V | PASS |

Metricas adicionales del punto seleccionado:

| Escenario | Tiempo recuperacion frecuencia | Error frecuencia estacionario | Desviacion evento Vdc | Error estacionario Vdc | Pico `i_bess` | Pico `p_bess_dc` | Delta SoC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `load_step_20_no_bess` | 5.06043446835136e-06 s | 0.0038709617158758647 Hz | 3.8350776972261866 % | -3.835070565680409 % | 0.0 A | 0.0 W | 0.0 |
| `load_step_40_no_bess` | 6.823002609568363e-07 s | 0.004783480917055272 Hz | 17.253882618467244 % | -17.253881446402126 % | 0.0 A | 0.0 W | 0.0 |
| `load_step_20_bess_pi_nominal_soh` | 9.028448616499318e-07 s | 0.0038652594654848826 Hz | 0.9530121582656839 % | -0.9471653741627581 % | 2.4557013982128315 A | 847.16567398905 W | 1.8535386712259516e-05 |
| `irradiance_drop_20_bess_pi` | 1.3683359092131475e-05 s | 0.0027010488648286923 Hz | 1.8211889221397646 % | -1.8043186761168581 % | 5.324127467483057 A | 1868.6519371456188 W | 4.492196489402911e-05 |

## 7. Estabilidad de pequena senal

La evidencia esta en:

- `src/validation/validate_objective2_small_signal_stability.py`
- `outputs/validation/objective2_vsg_tuning/eigenvalues.csv`
- `outputs/validation/objective2_vsg_tuning/small_signal_summary.json`

Se usa el mapa de un periodo electrico y multiplicadores de Floquet porque los
estados `abc` y `theta` describen una orbita periodica. Un Jacobiano instantaneo
del RHS no captura de forma equivalente la estabilidad del mapa periodico de la
trayectoria nominal.

Resultado formal de 12 estados:

```text
formal 12-state status = PASS
unstable modes = []
neutral phase mode = 12
zeta_min = 0.5808312032635214
zeta threshold = 0.10
determining mode = 9
modal frequency ~= 15.140105 Hz
zeta margin = 0.4808312032635214
```

El caso BESS de 16 estados es diagnostico y queda en `REVIEW` por deriva lenta
de estados BESS e integrador PI, lo que impide tratar la trayectoria como una
orbita periodica cerrada exacta. Ese `REVIEW` no se presenta como inestabilidad
del VSG formal.

## 8. Limitacion del escenario severo

Para el escenario extendido `load_step_40_no_bess` del punto seleccionado:

```text
Vdc_min = 313.8643954758725 V
Vdc_min_required = 327.5020881285063 V
deficit = 13.6376926526338 V
extended_severe_scenario_status = FAIL
```

El escalon de carga de 40 % sin BESS no es fisicamente admisible con la
configuracion evaluada. La tension cae por debajo del minimo requerido para
sintetizar la tension AC nominal, lo que representa insuficiencia energetica
del enlace DC sin apoyo del BESS. Este resultado no invalida la seleccion dentro
de los tres escenarios formales y no permite afirmar robustez para ese escenario
severo.

## 9. Matriz de trazabilidad

| Actividad | Requisito | Implementacion | Validador | Evidencia | Estado | Limitacion |
| --- | --- | --- | --- | --- | --- | --- |
| 2.1 | Diseno y ecuaciones VSG | `src/controllers/gfm_controller.py`, `src/controllers/grid_forming.py` | `src/validation/validate_objective2_control_closure.py` | `docs/objective_2_virtual_inertia_controller_design.md` | PASS | VSG clasico, no FOVIC |
| 2.1 | Diagrama | SVG vectorial | `src/validation/validate_objective2_control_closure.py` | `docs/figures/objective_2_vsg_bess_block_diagram.svg` | PASS | Diagrama conceptual |
| 2.2 | Limites SoC/SoH | `src/microgrid.py`, `src/microgrid_bess_pi.py` | `src/validation/validate_objective2_bess_control_limits.py` | `outputs/validation/objective2_bess_limits/summary.json` | REVIEW | Advertencia `Vdc/vt_bess` |
| 2.2 | Corriente y potencia | Saturacion por disponibilidad | `src/validation/validate_objective2_bess_control_limits.py` | `outputs/validation/objective2_bess_limits/summary.csv` | PASS | Modelo BMS simplificado |
| 2.2 | Anti-windup | `src/controllers/dc_link_bess_pi.py` | `src/validation/validate_objective2_bess_control_limits.py` | `outputs/validation/objective2_bess_limits/summary.json` | PASS | PI externo opcional |
| 2.2 | Identidad fisica | `p_bess_dc = Vdc*i_bess` | `src/validation/validate_objective2_bess_control_limits.py` | `outputs/validation/objective2_bess_limits/summary.json` | PASS | Sin DC/DC detallado |
| 2.3 | Malla de sintonia | `M=[20,50,80]`, `D=[200,850,1500]` | `src/validation/tune_objective2_vsg_parameters.py` | `outputs/validation/objective2_vsg_tuning/tuning_summary.json` | PASS | Dominio finito, no busqueda de optimo global |
| 2.3 | Escenarios | Tres formales y uno extendido | `src/validation/tune_objective2_vsg_parameters.py` | `outputs/validation/objective2_vsg_tuning/tuning_results.csv` | REVIEW | Severo sin BESS falla |
| 2.3 | RoCoF postevento | `rocof_window=post_event` | `src/validation/tune_objective2_vsg_parameters.py` | `outputs/validation/objective2_vsg_tuning/tuning_results.csv` | PASS | `dt=0.001 s` |
| 2.3 | Estabilidad | Mapa de un periodo | `src/validation/validate_objective2_small_signal_stability.py` | `outputs/validation/objective2_vsg_tuning/small_signal_summary.json` | REVIEW | BESS 16 estados diagnostico |
| 2.3 | Margen `zeta > 0.10` | `zeta_min=0.5808312032635214` | `src/validation/validate_objective2_small_signal_stability.py` | `outputs/validation/objective2_vsg_tuning/eigenvalues.csv` | PASS | Analisis numerico Floquet |
| 2.3 | Escenario severo | Diagnostico extendido no bloqueante | `src/validation/tune_objective2_vsg_parameters.py` | `outputs/validation/objective2_vsg_tuning/tuning_summary.json` | FAIL diagnostico | `Vdc_min < Vdc_min_required` |

## 10. Decision formal de cierre

Interpretacion formal:

```text
Actividad 2.1: PASS
Actividad 2.2: REVIEW, cerrada con limitacion declarada
Actividad 2.3: REVIEW, cerrada con limitacion declarada
Objetivo 2: REVIEW, tecnicamente cerrado dentro del alcance implementado
```

El Objetivo 2 no se declara `PASS` global porque permanecen:

- advertencia de escala `Vdc/vt_bess`;
- deriva lenta del caso BESS para Floquet;
- fallo del escenario severo de 40 % sin BESS;
- ausencia de validacion experimental;
- ausencia de busqueda de optimo global.

`REVIEW` no equivale a error de software. Significa que el alcance implementado
esta tecnicamente cerrado, con limitaciones explicitas que no deben ocultarse.

## 11. Reproducibilidad

Comandos principales:

```bash
python src/validation/validate_objective2_bess_control_limits.py
python src/validation/validate_objective2_small_signal_stability.py
python src/validation/tune_objective2_vsg_parameters.py
python src/validation/validate_objective2_control_closure.py
```

Pruebas unitarias asociadas:

```bash
python -m pytest src/validation/test_validate_objective2_control_closure.py -q
python -m pytest src/validation/test_validate_objective2_small_signal_stability.py -q
python -m pytest src/validation/test_tune_objective2_vsg_parameters.py -q
python -m pytest src/validation/test_microgrid_bess_pi_connection.py -q
```

## 12. Trazabilidad de commits

| Commit | Evidencia aportada |
| --- | --- |
| `2261ec09fee84ace883eac4b37f1c69b11bff845` | Actividad 2.1: consolidacion del diseno del controlador VSG-BESS y correccion del diagrama de bloques. |
| `860f03695a9a89c7f4075f91434a579575ee7e72` | Actividad 2.2: evidencia reproducible de los quince criterios de limites y control BESS/BMS. |
| `28bfeceadef7055efd779db309e2732da38a9406` | Actividad 2.3, primera parte: analisis periodico de estabilidad de pequena senal mediante multiplicadores de Floquet. |
| `e20260b04c5286810579d7fc2db575f83f8784f7` | Actividad 2.3, segunda parte: sintonia VSG multi-escenario inicial e integracion de la comprobacion de pequena senal. |
| `9563b46e02e38120e68d7725dad5217ad3019bf5` | Actividad 2.3, correccion final: RoCoF postevento, factibilidad fisica del enlace DC y separacion entre escenarios formales y escenario severo extendido. |
