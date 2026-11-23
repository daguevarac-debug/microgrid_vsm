# Verificación Cuantitativa y Prueba de Concepto Aislada para P-07 (Protección contra Sobretensión del Bus DC)

**Proyecto:** `microgrid_vsm` (Tesis de Maestría — Objetivo 2, Pendiente P-07)  
**Worktree / Rama:** `microgrid_vsm_p07_ovp` / `research/obj2-dc-bus-overvoltage` (derivada de PR #61, `3e26ecf17e811c2345eb7de239da7c671087e4c7`)  
**Script reproducible:** [`scripts/poc_p07_dc_bus_ovp.py`](../scripts/poc_p07_dc_bus_ovp.py)  
**Artefactos de salida:** [`outputs/research_p07_ovp_poc/poc_p07_results.json`](../outputs/research_p07_ovp_poc/poc_p07_results.json), [`outputs/research_p07_ovp_poc/poc_p07_summary.csv`](../outputs/research_p07_ovp_poc/poc_p07_summary.csv)  
**Estado de P-07:** **`REVIEW`** (un `PASS` del prototipo aislado acredita únicamente su consistencia física y numérica bajo los escenarios ensayados; **no** valida el controlador completo de 16 estados ni sustituye la futura validación integrada).

---

## 1. Revisión del dimensionamiento y evaluación de hipótesis preliminares

### 1.1 Balance energético y límites del sistema actual
El modelo [`PVArraySingleDiode`](../src/pv_model.py) con los parámetros por defecto de [`src/config.py`](../src/config.py) (`10` módulos en serie LONGi LR7-54HJD-500M, `Cdc = 0.002 F`, `eta_inv = 0.97`, `Vdc_nom = 340.0 V`, `v_uvlo = 200.0 V`, `SoC_max = 0.90`, banco BESS `48 × 2s2p` con límite superior `403.2 V`, `I_max = 66.0 A`, `P_max = 22440 W`) gobierna el bus DC según:

$$P_{\text{PV}}(V_{\text{dc}}, G, T_c) + P_{\text{BESS,bus}} - P_{\text{INV,DC}} - P_{\text{dump}} = C_{\text{dc}}\,V_{\text{dc}}\,\frac{dV_{\text{dc}}}{dt}$$

### 1.2 Naturaleza de los umbrales (`357.0`, `363.8`, `374.0`, `391.0 V`)
Estos valores son **hipótesis de diseño de ingeniería**, no límites certificados de componentes comerciales:
- **`357.0 V` (`+5 %`):** banda de advertencia alineada con el criterio diagnóstico `max_vdc_overshoot_pct = 5.0 %` de [`src/tuning_metrics.py`](../src/tuning_metrics.py).
- **`374.0 V` (`+10 %`):** umbral de activación del *chopper*, alineado con bandas de regulación/falla de `±10 %` en literatura de microrredes DC (Choi et al., 2022) y holgado sobre el transitorio con BESS activo (`357.66 V` en el modelo de 16 estados).
- **`363.8 V` (`+7 %`):** reposición por histéresis (`ΔV_hyst = 10.2 V`) para el esquema todo/nada.
- **`391.0 V` (`+15 %`):** barrera de disparo OVP duro, situada `12.2 V` por debajo del límite superior del banco BESS (`403.2 V`) y `12.61 V` por debajo del equilibrio sin protección (`403.61 V`).

> **Parámetros no especificados en el repositorio (requieren definición antes de diseño de hardware):** tensión máxima nominal del condensador DC (`Cdc`), tensión colector-emisor / drenador-fuente de los semiconductores (`IGBT/MOSFET`), potencia continua/pulsada nominal de `R_dump`, capacidad térmica equivalente `C_th` [J/K] y resistencia térmica ambiente `R_th` [K/W].

---

## 2. Resultados de la prueba de concepto aislada (`dt = 5e-5 s`, RK4)

El prototipo aislado reproduce el escenario de rechazo de carga del `-80 %` (`3000 W → 600 W` AC en `t = 0.5 s`, `G = 800 W/m²`, `Tc = 25 °C`) y contrasta los tres esquemas junto con operación normal (`SoC = 0.60`) y disparo de emergencia (`G = 1000 W/m²`, rechazo `-100 %`):

| Escenario | `Vdc_post_max` [V] | `Vdc_final` [V] | `P_dump_max` [W] | `I_dump_max` [A] | `E_dump` [J] | Conmutaciones | `t > 374 V` [s] | Error rel. energía |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `no_protection_socmax_m80pct` | `403.5801` | `403.5801` | `0.00` | `0.000` | `0.000` | `0` | `0.694` | `3.69e-10` |
| `hysteresis_chopper_socmax_m80pct` (`374/363.8 V`) | `374.1544` | `370.0676` | `5599.66` | `14.966` | `2042.148` | `277` | `0.006` | `1.93e-10` |
| `hysteresis_tight_band_chattering_check` (`374/373.5 V`) | `374.1718` | `373.4133` | `5600.18` | `14.967` | `1864.675` | `4049` | `0.006` | `1.97e-10` |
| `regulated_chopper_socmax_m80pct` (`D` proporcional) | `380.6200` | `380.6200` | `2256.58` | `5.929` | `1615.957` | `1` | `0.695` | `2.08e-10` |
| `regulated_chopper_bess_active_soc060` | `349.3340` | `340.1508` | `0.00` | `0.000` | `0.000` | `0` | `0.000` | `1.29e-10` |
| `hysteresis_chopper_bess_active_soc060` | `349.3340` | `340.1508` | `0.00` | `0.000` | `0.000` | `0` | `0.000` | `1.29e-10` |
| `emergency_trip_inverter_only_g1000` | `413.4925` | `413.4925` | `0.00` | `0.000` | `0.000` | — | — | — |
| `emergency_trip_pv_isolation_g1000` | `199.8671` | `199.8671` | `0.00` | `0.000` | `0.000` | — | — | — |

### Hallazgos clave del contraste numérico
1. **Validación de referencia y conservación energética:** el prototipo sin protección converge a `403.5801 V`, a solo `0.03 V` del modelo completo de 16 estados (`403.61 V`, diferencia atribuible a pérdidas óhmicas/amortiguamiento del filtro LCL). Todos los casos conservan la energía con error relativo `≤ 3.69e-10`.
2. **Chattering severo en todo/nada vs. suavidad del chopper regulado:**
   - Con histéresis `374.0 / 363.8 V`, el *chopper* conmuta **`277` veces en `0.7 s`** (`~198 Hz`), generando pulsos de `5.60 kW` (`14.97 A`) y un rizado permanente de `10.2 V` en `Vdc`. Si la banda se estrecha a `374.0 / 373.5 V`, las conmutaciones escalan a **`4049` en `0.7 s`** (`~2.89 kHz`, limitado solo por `dt = 5e-5 s`), confirmando riesgo real de *chattering* y estrés en el integrador ODE.
   - Con el **chopper regulado** `D(Vdc) = clip((Vdc - 374.0)/(391.0 - 374.0), 0, 1)`, la transición ocurre con **`1` sola conmutación**, estabilizando suavemente en `380.62 V` (`P_dump_ss = 2256.58 W`, `I_dump = 5.93 A`, sin rizado).
3. **No intervención en operación normal (`SoC = 0.60`):** con BESS disponible, `Vdc` permanece bajo `350 V` en el prototipo (`357.66 V` en el modelo de 16 estados), muy por debajo de `374.0 V`, resultando en `E_dump = 0.0 J` y `0` conmutaciones.
4. **Riesgo del disparo de emergencia solo en el inversor:** desconectar únicamente el inversor al llegar a `391.0 V` mientras la FV sigue conectada **agrava la sobretensión** hasta `Voc = 413.49 V` (`G = 1000 W/m²`). Por tanto, **el Nivel 3 debe aislar obligatoriamente la fuente FV del bus DC** (llevando `Vdc` de forma segura hacia UVLO `200 V`).

---

## 3. Sensibilidad paramétrica de `R_dump` y exigencia térmica ante excedentes prolongados

### 3.1 Sensibilidad de `R_dump` y temperatura ambiente (`G = 1000 W/m²`, rechazo `-100 %`)
- **Barrido `R_dump` (`Tc = 25 °C`):** `15 Ω` (`Vmax = 381.05 V, D = 0.4149`), `20 Ω` (`383.04 V, D = 0.5318`), `25 Ω` (`384.86 V, D = 0.6391, Imax = 9.839 A`), `28 Ω` (`385.88 V, D = 0.6991`), `35 Ω` (`388.06 V, D = 0.8273`).
- **Barrido `Tc` con `R_dump = 25 Ω`:** a `Tc = 45 °C`, `Voc` cae a `354.54 V` (el chopper ni siquiera se activa); a `Tc = 0 °C`, `Vmax = 390.09 V` con `D = 0.9463` e `Imax = 14.766 A`, quedando a menos de `1 V` del disparo duro (`391.0 V`). Una resistencia de **`20 Ω`** ofrece mayor margen térmico-eléctrico en clima frío (`Tc = 0 °C`) que `25 Ω`.

### 3.2 Análisis térmico paramétrico para eventos prolongados (`P_dump_ss = 2256.58 W`)
Sin un valor certificado de masa térmica `C_th`, la elevación adiabática `ΔT = E_dump / C_th` muestra que **un *braking chopper* solo es viable como protección transitoria o con disipación continua certificada + enclavamiento por energía/tiempo**:

| Duración del excedente | Energía disipada `E_dump` [kJ] | `ΔT` (`C_th = 50 J/K`) [°C] | `ΔT` (`C_th = 100 J/K`) [°C] | `ΔT` (`C_th = 250 J/K`) [°C] | `ΔT` (`C_th = 500 J/K`) [°C] |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `0.7 s` (transitorio corto) | `1.616` | `32.32` | `16.16` | `6.46` | `3.23` |
| `10.0 s` | `21.474` | `429.48` | `214.74` | `85.90` | `42.95` |
| `60.0 s` | `134.303` | `2686.06` | `1343.03` | `537.21` | `268.61` |
| `600.0 s` (`10 min`) | `1352.856` | `27057.12` | `13528.56` | `5411.42` | `2705.71` |

**Conclusión térmica:** ante excedentes prolongados (`> 5–10 s` en `SoC_max`) o eventos repetidos sin enfriamiento, la disipación acumulada alcanza cientos de kJ / MJ. Por ello, la protección debe incluir un **temporizador de sobreenergía / límite térmico (`I²t` o `E_dump_max`)** que active el **aislamiento FV (Nivel 3)** si el *chopper* permanece activo de forma sostenida.

---

## 4. Arquitectura única recomendada para implementación futura

Se recomienda implementar exclusivamente el **Chopper Regulado por Ciclo de Trabajo en Bus DC + Aislamiento FV de Emergencia (Nivel 3 con enclavamiento térmico)**:
1. **Ventajas demostradas:** elimina el *chattering* (`1` conmutación frente a `277–4049`), evita rizado en `Vdc` y reduce picos de corriente en la rama resistiva (`5.93 A` frente a `14.97 A` a `G = 800 W/m²`), no interfiere con el BESS (`0 J` cuando `SoC = 0.60`), y evita el ascenso hacia `Voc` mediante aislamiento FV en Nivel 3 o por excedente prolongado.
2. **Especificación recomendada para pruebas integradas:** `V_warn = 357.0 V`, `V_chopper_on = 374.0 V`, ley continua `D = clip((Vdc - 374.0)/(391.0 - 374.0), 0, 1)`, `R_dump = 20–25 Ω` (prefiriendo `20 Ω` para margen a `Tc = 0 °C`), y disparo Nivel 3 (`391.0 V` o `E_dump > E_max_termico`) mediante **aislamiento del arreglo FV**.
3. **Condiciones de validez:** esta recomendación es válida dentro de la topología actual de FV directo sin etapa boost. Antes de cerrar **P-07** (`REVIEW` → `PASS`), deberá integrarse en el modelo completo de 16 estados (`MicrogridWithBESSDCDC` + `GFMController` con `M = 80`, `D = 1500`) y validar estabilidad ODE, frecuencia AC y no regresión en Objetivo 1 y 2.
