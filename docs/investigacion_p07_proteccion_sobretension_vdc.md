# Investigación y Diseño Preliminar de Protección contra Sobretensión del Bus DC (Pendiente P-07)

**Proyecto:** `microgrid_vsm` (Tesis de Maestría — Objetivo 2, Pendiente P-07)  
**Rama de investigación:** `research/obj2-dc-bus-overvoltage` (derivada de PR #61, `3e26ecf17e811c2345eb7de239da7c671087e4c7`)  
**Estado de P-07:** **`REVIEW`** (este documento formula la investigación y el diseño preliminar; **no** implementa cambios en `src/` ni cierra P-07 hasta ejecutar futuras simulaciones de validación).  
**Documentos relacionados:** [`docs/fuentes_p07_proteccion_vdc.md`](fuentes_p07_proteccion_vdc.md), [`docs/auditoria_integral_review_objetivo2.md`](auditoria_integral_review_objetivo2.md).

---

## 1. Diagnóstico del comportamiento actual en el código

La auditoría de los módulos vigentes confirma que la arquitectura actual (`MicrogridWithBESSDCDC` + `GFMController` + `DCLinkBESSPIController` + `dc_dc_adapter`) posee protección de **subtensión** (UVLO) y límites de **corriente/potencia/SoC del BESS**, pero **carece de protección activa contra sobretensión (OVP) en el bus DC**:

1. **Acoplamiento directo del arreglo FV al bus DC (`src/microgrid.py:186`):**  
   `pv_current` evalúa `self.pv.ipv_from_vpv(vdc_eff, G=irradiance, T_c=cell_temp_c)`. No existe convertidor DC/DC elevador ni lazo MPPT/recorte activo en el puerto FV; por lo tanto, `Vpv = Vdc` y la corriente FV depende exclusivamente de la curva `I–V` del arreglo (10 módulos en serie LONGi LR7-54HJD-500M) y de la tensión instantánea del bus.
2. **Inversor GFM unidireccional DC→AC sin limitación superior de `Vdc` (`src/controllers/gfm_controller.py:223-248`):**  
   - `GFMController.compute_control` verifica únicamente el límite inferior `if vdc_eff < plant.v_uvlo:` (`v_uvlo = 200.0 V` en `src/config.py`), anulando `v_inv`, `p_bridge`, `idc_inv` y `m_ctrl`.
   - Para `vdc_eff >= v_uvlo`, ajusta `m_required = 2.0 * self.modulator.v_pk / vdc_eff` y `m_ctrl = min(self.m_base, m_required)`, manteniendo la tensión AC de salida y evacuando `idc_inv = max(p_bridge, 0.0) / (plant.eta * max(vdc_eff, plant.dcp.Vmin))`.
   - El límite `p_ref_eff = min(self.p_ref, p_net_ac_available)` acota la referencia mecánica del VSG, **pero no recorta la corriente FV entrante al bus DC**.
3. **Bloqueo del BESS en `SoC_max = 0.90` (`src/bess/dc_dc_adapter.py:113-146`):**  
   Cuando `soc >= soc_max (0.90)`, `convert_power` fija la capacidad de carga en `charge = 0.0` (`charge_limit = -0.0 W`), forzando `i_bus = 0.0 A`. `DCLinkBESSPIController` activa su *anti-windup* condicional, pero queda sin actuador disponible para absorber excedentes en el bus.
4. **Límites implementados vs. límites meramente diagnósticos:**  
   - **Activos en la ODE:** `plant.v_uvlo = 200.0 V` (`gfm_controller.py`), `dcp.Vmin = 50.0 V` (`src/dclink.py`), tensión de unidad BESS `[2.50, 4.20] V` equivalente a `[240.0, 403.2] V` en el banco de `48` módulos `2s2p` (`96` unidades en serie en `dc_dc_adapter.py`), `soc_min = 0.10`, `soc_max = 0.90`, `bus_power_max_w = 22440.0 W`, `bus_current_max_a = 66.0 A`.
   - **Solo diagnósticos (sin acción de control):** `max_vdc_overshoot_pct = 5.0 %` (`357.0 V` respecto a `340.0 V`), `max_vdc_event_deviation_pct = 5.0 %` y `vdc_min_required_v = 327.50 V` en `src/tuning_metrics.py`.

---

## 2. Balance físico de energía y explicación exacta del punto `403.61 V`

En `src/microgrid.py:230`, la ecuación diferencial protegida del enlace DC (`AGENTS.md` #8–10) es:

$$\frac{dV_{\text{dc}}}{dt} = \frac{i_{\text{pv}} + i_{\text{bess}} - i_{\text{dc,inv}}}{C_{\text{dc}}}$$

Multiplicando ambos lados por $V_{\text{dc}}$ y manteniendo la convención de signos del repositorio ($i_{\text{bess}} > 0$ descarga hacia el bus, $i_{\text{bess}} < 0$ carga desde el bus, $i_{\text{dc,inv}} \ge 0$ consumo del inversor hacia AC):

$$P_{\text{PV}} + P_{\text{BESS,bus}} - P_{\text{INV,AC}} - P_{\text{LOSS}} = C_{\text{dc}}\, V_{\text{dc}} \frac{dV_{\text{dc}}}{dt}$$

donde $P_{\text{PV}} = V_{\text{dc}}\,i_{\text{pv}}$, $P_{\text{BESS,bus}} = V_{\text{dc}}\,i_{\text{bess}}$ y $P_{\text{INV,DC}} = V_{\text{dc}}\,i_{\text{dc,inv}} = P_{\text{bridge}}/\eta = P_{\text{INV,AC}} + P_{\text{LOSS}}$ (pérdidas de puente y filtro LCL).

### Verificación cuantitativa en el rechazo de carga del `-80 %` (`scripts/audit_obj2_uvlo_and_overvoltage.py`)
En el escenario con `G = 800 W/m²`, `Tc = 25 °C`, `Cdc = 0.002 F` y escalón de carga de `3000 W` a `600 W` AC en `t = 0.5 s` (`outputs/audit_obj2_review_closure/uvlo_and_overvoltage_audit.json`):

| Magnitud / Punto operativo | `Vdc = 340.00 V` (Nominal) | `Vdc = 357.66 V` (`SoC=0.60`, pico) | `Vdc = 374.00 V` (`+10 %`) | `Vdc = 403.61 V` (`SoC=0.90`, pico/estacionario) | `Voc` (`G=800, Tc=25°C`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Corriente FV `Ipv` [A] | `11.1528` | `10.1887` | `8.5472` | `1.5211` | `0.0000` |
| Potencia FV `P_PV` [W] | `3791.96` | `3644.09` | `3196.67` | `613.95` | `0.00` |
| Energía en `Cdc` `0.5·Cdc·Vdc²` [J] | `115.60` | `127.92` | `139.88` | `162.90` | `165.89` (`407.30 V`) |
| Acción BESS `i_bus` [A] | Regulación activa | `-8.5148` (absorbe) | N/A | `0.0` (bloqueado en `SoC_max`) | `0.0` |

- **Con `SoC = 0.60`:** el BESS absorbe el excedente (`i_bus_min = -8.5148 A`), conteniendo el pico en **`357.66 V`** (`+5.20 %`).
- **Con `SoC = 0.90`:** `P_BESS,bus = 0 W`. Al caer la demanda AC a ~`600 W`, el excedente inicial (~`3178 W`) carga `Cdc = 2 mF` (`ΔE_cap = 47.30 J` entre `340 V` y `403.61 V`), empujando pasivamente `Vdc` por la rama derecha (región de tensión constante) de la curva `I–V` hasta alcanzar un nuevo equilibrio térmico/eléctrico en **`403.61 V`** (`+18.71 %`), donde `P_PV(403.61 V) = 613.95 W` iguala a `600 W / 0.97` más pérdidas del LCL.
- **Significado físico y de diseño:** aunque `config.py` no declara un límite nominal de condensador/IGBT, `403.61 V` supera ampliamente el criterio diagnóstico `+5 %` (`357.0 V`), rebasa la banda estándar de falla `±10 %` (`374.0 V`, Choi et al., 2022), excede levemente el límite de tensión del banco BESS (`403.2 V`) y podría acercarse a `413.5 V` (`G = 1000 W/m², Tc = 25 °C`) o superarlo si `Tc < 25 °C`.

---

## 3. Comparación de alternativas de protección OVP

| Criterio | Alternativa A: Recorte FV por desplazamiento de tensión (*PV Curtailment*) | Alternativa B: *Braking Chopper* resistivo / *Dump Load* en bus DC | Alternativa C: Esquema híbrido escalonado (BESS + Chopper / Recorte FV + OVP duro) |
| :--- | :--- | :--- | :--- |
| **Principio físico** | Desplaza `Vpv` hacia `Voc` mediante un convertidor DC/DC FV (modo CV/droop en lugar de MPPT). | Conecta en paralelo con `Cdc` una resistencia `R_dump` mediante interruptor PWM/histéresis para disipar `P_surplus = Vdc²·D / R_dump`. | Prioriza BESS (`340–357 V`), activa disipación/recorte en banda intermedia (`374 V`) y dispara OVP duro (`391 V`) como última barrera. |
| **Compatibilidad con `microgrid_vsm` actual** | **Baja sin cambio topológico:** hoy `Vpv = Vdc` (acoplamiento directo sin boost FV). | **Muy Alta:** se acopla como una corriente de drenaje adicional `i_dump >= 0` en `dVdc/dt` sin alterar el arreglo FV ni el BESS. | **Alta en versión BESS + Chopper + OVP duro** (y extensible a recorte FV cuando se añada DC/DC FV). |
| **Eficiencia y estrés térmico** | Alta (no disipa potencia en calor). | Disipa excedentes en calor durante eventos transitorios o `SoC_max` prolongado. | Óptima: el BESS absorbe eventos normales y el chopper solo actúa en saturación/emergencia. |
| **Riesgo de *chattering* / estabilidad** | Requiere transición suave MPPT↔CV para evitar oscilaciones en la rodilla `P–V`. | Controlable mediante banda de histéresis o ciclo de trabajo `D(Vdc)` continuo/PI. | Bajo si se separan bandas con histéresis y *anti-windup* coordinado. |

---

## 4. Arquitectura preliminar recomendada para P-07

Se recomienda adoptar la **Alternativa C** implementada inicialmente con **BESS prioritario + Chopper resistivo controlado en el bus DC + Disparo OVP duro con histéresis** (dejando el puerto de recorte FV preparado para cuando el modelo incorpore un convertidor DC/DC FV).

### 4.1 Señales, ubicación del actuador y bandas de tensión sobre `Vdc_nom = 340.0 V`

- **Señal de disparo local:** `vdc_eff` (tensión filtrada/efectiva del enlace DC ya disponible en `GFMController` y `MicrogridWithBESSDCDC`), sin dependencia de comunicaciones (*DC Bus Signaling*).
- **Ubicación del actuador:** rama resistiva controlada en paralelo con el condensador `Cdc` (`i_dump(Vdc, estado) >= 0` saliendo del bus), modificando el balance futuro únicamente mediante `- i_dump` en el numerador de `dVdc/dt`.

| Nivel | Banda / Umbral de `Vdc` | Desviación vs. `340 V` | Acción recomendada | Histéresis / Recuperación |
| :--- | :---: | :---: | :--- | :--- |
| **Nivel 0 (Normal)** | `327.5 V – 357.0 V` | `-3.68 %` a `+5.00 %` | Operación nominal. `DCLinkBESSPIController` regula `Vdc` con prioridad absoluta si `SoC < 0.90`. `i_dump = 0`. | N/A |
| **Nivel 1 (Advertencia / Pre-alerta)** | `357.0 V – 374.0 V` | `+5.00 %` a `+10.00 %` | Bandera diagnóstica de advertencia (`OVP_WARN`). BESS a máxima carga admisible por SoC/SoH/corriente. `i_dump = 0`. | Limpia advertencia si `Vdc < 350.2 V` (`+3.0 %`). |
| **Nivel 2 (Chopper activo / Recorte)** | `>= 374.0 V` | `>= +10.00 %` | Activa *braking chopper* con ley proporcional saturada `D = clip((Vdc - 374.0)/(391.0 - 374.0), 0, 1)` (o histéresis) para evacuar hasta `P_pv_max ≈ 5 kW` (`R_dump ≈ 25–28 Ω`). | Desactiva por histéresis al caer por debajo de **`363.8 V`** (`+7.0 %`). |
| **Nivel 3 (OVP duro / Protección crítica)** | `>= 391.0 V` | `>= +15.00 %` | Disparo OVP de emergencia: aísla el aporte hacia el bus / desconecta fuente FV o puente si falla Nivel 2, quedando por debajo de `403.2 V` (banco BESS) y `403.61 V`. | Reenganche bloqueado hasta `Vdc <= 357.0 V` (`+5.0 %`) tras tiempo mínimo de guarda. |

### 4.2 Interacciones críticas y prevención de efectos indeseados

1. **Interacción con `DCLinkBESSPIController` y `SoC_max`:**  
   El Nivel 2 solo inicia a `374.0 V` (`+10 %`), muy por encima del pico observado con BESS disponible (`357.66 V` a `SoC = 0.60`). Así, el chopper **no compite** con el BESS en operación normal y únicamente entra cuando el BESS está saturado en `SoC_max = 0.90` o limitado en potencia/corriente. El *anti-windup* condicional existente en `DCLinkBESSPIController` permanece intacto.
2. **Interacción con UVLO (`200.0 V`) y `GFMController`:**  
   Las bandas OVP (`357–391 V`) están completamente desacopladas de `v_uvlo = 200.0 V` y por encima de `vdc_min_required = 327.50 V`. Durante la actuación del Nivel 2, `GFMController` conserva `M = 80`, `D = 1500` y su regulación de tensión/frecuencia AC sin perturbaciones.
3. **Prevención de *chattering*:**  
   La combinación de ley proporcional continua `D(Vdc)` en `[374.0, 391.0] V` con histéresis de desactivación (`363.8 V`) evita conmutaciones abruptas de alta frecuencia en el paso de integración ODE (`solve_ivp`), a diferencia de un relé sin banda muerta.
4. **Dimensionamiento orientativo de `R_dump`:**  
   Para disipar `P_pv_stc ≈ 5000 W` a `Vdc = 374–391 V`, se requiere `R_dump <= 374² / 5000 ≈ 27.97 Ω` (por ejemplo, `R_dump = 25 Ω`, que disipa `5.59 kW` a `374 V` y `6.12 kW` a `391 V`, superando el máximo aporte FV a `1000 W/m²`).

---

## 5. Supuestos, limitaciones y plan de validación futuro

### Supuestos y limitaciones actuales
- Los valores de `R_dump`, tasas de rampa y tiempos de guarda térmicos del resistor son **parámetros de diseño preliminar**; no se ha modelado la dinámica térmica de `R_dump` ni un convertidor DC/DC FV dedicado.
- El diseño se fundamenta en simulaciones internas del modelo promediado (`MicrogridWithBESSDCDC`) y literatura revisada por pares, **no** en ensayos experimentales o HIL.
- **No se ha implementado código OVP** en esta etapa; `src/`, las ecuaciones VSG, `M = 80`, `D = 1500`, los vectores de estado y los resultados validados permanecen intactos.

### Plan de validación futuro para cerrar P-07
Para transicionar **P-07** de `REVIEW` a `PASS` en una etapa posterior de implementación:
1. Implementar el actuador de Nivel 2/3 en un módulo desacoplado (sin alterar los 16 estados protegidos ni añadir un segundo `solve_ivp`).
2. Reejecutar el escenario crítico `overvoltage_socmax_load_rejection_m80pct` (`SoC = 0.90`, rechazo `-80 %`) verificando `max(Vdc) < 385 V` (debajo de `391 V` y `403.2 V`) y ausencia de *chattering*.
3. Repetir con rechazo del `-100 %` (`load = 0 W`), `G = 1000 W/m²` y `Tc = 0–25 °C`.
4. Verificar no regresión en `SoC = 0.60` (`i_dump = 0` durante todo el transitorio, pico `357.66 V` inalterado), en UVLO (`validate_obj1_regression.py`) y en `validate_physical_invariants.py`.
