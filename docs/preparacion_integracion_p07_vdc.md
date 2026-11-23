# Informe de Preparación para Integración y Contrato Técnico de OVP (Pendiente P-07)

**Proyecto:** `microgrid_vsm` (Tesis de Maestría — Objetivo 2, Pendiente P-07)  
**Worktree / Rama:** `microgrid_vsm_p07_ovp` / `research/obj2-dc-bus-overvoltage` (derivada de PR #61, `3e26ecf17e811c2345eb7de239da7c671087e4c7`)  
**Evidencias base reutilizadas:** [`docs/investigacion_p07_proteccion_sobretension_vdc.md`](investigacion_p07_proteccion_sobretension_vdc.md), [`docs/validacion_cuantitativa_poc_p07_vdc.md`](validacion_cuantitativa_poc_p07_vdc.md), [`docs/fuentes_p07_proteccion_vdc.md`](fuentes_p07_proteccion_vdc.md), [`scripts/poc_p07_dc_bus_ovp.py`](../scripts/poc_p07_dc_bus_ovp.py) y [`outputs/research_p07_ovp_poc/poc_p07_results.json`](../outputs/research_p07_ovp_poc/poc_p07_results.json).  
**Estado de P-07:** **`REVIEW`** (este informe autoriza únicamente el diseño de una implementación experimental opcional futura; **no** modifica `src/` ni cierra P-07).

---

## 1. Revisión científica de la arquitectura propuesta

La arquitectura seleccionada combina:
1. **Chopper resistivo regulado por ciclo de trabajo** $D(V_{\text{dc}}) = \text{clip}\!\left(\frac{V_{\text{dc}} - 374.0}{391.0 - 374.0},\, 0,\, 1\right)$ con $R_{\text{dump}} \in [20, 25]\ \Omega$.
2. **Aislamiento FV de emergencia (Nivel 3)** al alcanzar $V_{\text{dc}} \ge 391.0\text{ V}$ o al superarse el límite térmico/energético del resistor ($E_{\text{dump}} \ge E_{\text{max,térmico}}$).

### 1.1 Modelo promediado frente a conmutación PWM real
Es indispensable **no confundir** la transición del modelo promediado con la frecuencia real de un chopper PWM físico:
- En [`poc_p07_dc_bus_ovp.py`](../scripts/poc_p07_dc_bus_ovp.py), el conteo `n_switchings = 1` del chopper regulado indica **una sola transición de activación** de la envolvente continua $D(V_{\text{dc}}) > 0$ al cruzar $374.0\text{ V}$, no una frecuencia de conmutación PWM de 1 Hz.
- En un convertidor físico con modulación PWM a frecuencia $f_{\text{sw}}$ (típicamente $5\text{–}20\text{ kHz}$), el interruptor IGBT/MOSFET conmuta $f_{\text{sw}}$ veces por segundo. Durante el subintervalo de conducción, la **corriente pico instantánea** en el interruptor y la resistencia es $I_{\text{sw,pico}} = V_{\text{dc}} / R_{\text{dump}}$, la **corriente eficaz (RMS)** que determina el calentamiento óhmico es $I_{\text{RMS,PWM}} = \sqrt{D}\, V_{\text{dc}} / R_{\text{dump}}$, y la **corriente media** drenada de $C_{\text{dc}}$ es $I_{\text{avg}} = D\, V_{\text{dc}} / R_{\text{dump}}$.
- Para el punto estacionario del PoC (`G = 800 W/m²`, `-80 %` carga, $V_{\text{dc}} = 380.62\text{ V}$, $D = 0.3894$, $R_{\text{dump}} = 25\ \Omega$): $I_{\text{avg}} = 5.93\text{ A}$, $P_{\text{avg}} = 2256.58\text{ W}$, mientras que en PWM real $I_{\text{sw,pico}} = 15.22\text{ A}$ e $I_{\text{RMS,PWM}} = 9.50\text{ A}$. El rizado de tensión PWM estimado $\Delta V_{\text{dc,PWM}} \approx \frac{I_{\text{avg}}(1-D)}{f_{\text{sw}} C_{\text{dc}}}$ sería $\approx 0.18\text{ V}$ a $f_{\text{sw}} = 10\text{ kHz}$, no modelado en la formulación promediada.

### 1.2 Exigencias de corriente, potencia y energía sobre $R_{\text{dump}} \in [20, 25]\ \Omega$
| Régimen / Condición | $R_{\text{dump}} = 25\ \Omega$ | $R_{\text{dump}} = 20\ \Omega$ | Implicación de diseño |
| :--- | :---: | :---: | :--- |
| Pico instantáneo a $374.0\text{ V}$ ($D=1$) | $14.96\text{ A}$ / $5595.0\text{ W}$ | $18.70\text{ A}$ / $6993.8\text{ W}$ | Semiconductores y resistor deben soportar pico $\ge 20\text{ A}$ / $7.7\text{ kW}$. |
| Pico instantáneo a $391.0\text{ V}$ ($D=1$) | $15.64\text{ A}$ / $6115.2\text{ W}$ | $19.55\text{ A}$ / $7644.1\text{ W}$ | $20\ \Omega$ da margen térmico/eléctrico extra a $T_c = 0\ ^\circ\text{C}$ ($G=1000$). |
| Excedente transitorio $0.7\text{ s}$ (`G=800, -80%`) | $I_{\text{avg}}=5.93\text{ A}$, $E=1.616\text{ kJ}$ | $I_{\text{avg}}$ similar, menor $D$ | Asumible transitoriamente en resistor pulsado. |
| Excedente sostenido $60\text{ s}$ / $600\text{ s}$ | $134.30\text{ kJ}$ / $1352.86\text{ kJ}$ | $\approx 134\text{–}135\text{ kJ}$ / $1.35\text{ MJ}$ | Inviable adiabáticamente; exige **corte por límite energético** o disipación continua certificada. |
| Eventos repetidos ($N$ ciclos sin enfriamiento) | $E_{\text{acum}} = N \cdot E_{\text{evento}}$ | $E_{\text{acum}} = N \cdot E_{\text{evento}}$ | Requiere integrador térmico o contador de energía acumulada con ventana de enfriamiento. |

### 1.3 Compatibilidad de umbrales con los límites documentados
- Los umbrales **`357.0 V`** (`+5 %`), **`374.0 V`** (`+10 %`) y **`391.0 V`** (`+15 %`) son coherentes con `Vdc_nom = 340.0 V`, superiores a `vdc_min_required = 327.50 V` y `v_uvlo = 200.0 V`, y estrictamente inferiores al límite superior del banco BESS (`403.2 V`) y al equilibrio pasivo (`403.61 V`).
- Al no existir especificaciones de fabricante en [`src/config.py`](../src/config.py) para la tensión máxima de $C_{\text{dc}}$, semiconductores ni capacidad térmica de $R_{\text{dump}}$, estos valores **se conservan explícitamente como hipótesis de ingeniería**, no como límites comerciales certificados.

---

## 2. Interacciones del sistema y secuencia de emergencia

### 2.1 Interacción con BESS saturado en `SoC_max`, PI, UVLO e inversor
1. **BESS en `SoC_max = 0.90` e integrador PI:** `convert_power` fija `charge_limit = -0.0 W` (`i_bus = 0.0 A`) y `DCLinkBESSPIController` activa su *anti-windup* condicional. Como el chopper solo actúa para $V_{\text{dc}} > 374.0\text{ V}$, no compite con el BESS durante regulación normal (`SoC < 0.90`). Al recuperarse el balance (aumento de carga o caída de irradiancia), $D \to 0$ suavemente al bajar de $374.0\text{ V}$ y el PI del BESS retoma la regulación hacia `340.0 V` sin saltos.
2. **Protección UVLO (`200.0 V`) e inversor GFM (`M=80, D=1500`):** el rango OVP (`357–391 V`) está separado `174 V` de UVLO. Mientras $200.0\text{ V} \le V_{\text{dc}} < 391.0\text{ V}$, `GFMController` mantiene la regulación AC sin alterar $M$ ni $D$.

### 2.2 Secuencia segura de actuación en emergencia (`391.0 V` o sobreenergía térmica)
Como demostró `emergency_trip_inverter_only_g1000` (`413.49 V`), **desconectar únicamente el inversor es inválido** porque anula `idc_inv` mientras `ipv > 0` empuja $V_{\text{dc}} \to V_{\text{oc}}$. La secuencia obligatoria es:
1. **Disparo:** si $V_{\text{dc}} \ge 391.0\text{ V}$ **o** $E_{\text{dump}} \ge E_{\text{max,térmico}}$, activar el enclavamiento `ovp_pv_isolated = True`.
2. **Acción primaria (reducción verificable de potencia):** abrir/aislar el aporte FV al bus DC (`i_pv_eff = 0.0 A`, $P_{\text{PV}} \to 0\text{ W}$), manteniendo el chopper habilitado mientras $V_{\text{dc}} > 374.0\text{ V}$ para drenar cualquier exceso residual en $C_{\text{dc}}$.
3. **Evolución segura:** con $i_{\text{pv}} = 0$, $V_{\text{dc}}$ desciende de forma monótona (`dVdc/dt < 0`). Si el BESS está disponible, regula hacia `340.0 V`; si no hay carga/BESS, `GFMController` corta limpiamente al cruzar `v_uvlo = 200.0 V`.
4. **Enclavamiento y reposición:** mantener `ovp_pv_isolated = True` hasta cumplir simultáneamente $V_{\text{dc}} \le 357.0\text{ V}$ y un tiempo mínimo de guarda (p. ej. $\Delta t_{\text{guard}} \ge 1.0\text{ s}$, parámetro a validar).

---

## 3. Explicación de `349.33 V` (PoC) frente a `357.66 V` (modelo de 16 estados)

En el escenario con BESS disponible (`SoC = 0.60`, rechazo `-80 %`), el PoC registró `Vmax = 349.3340 V`, mientras que [`audit_obj2_uvlo_and_overvoltage.py`](../scripts/audit_obj2_uvlo_and_overvoltage.py) obtuvo `357.6637 V`. Esta diferencia de `8.33 V` se explica por cuatro simplificaciones del PoC de 1 estado:
1. **Ganancias del PI del BESS:** [`validate_bess_pi_minimal_tuning.py`](../src/validation/validate_bess_pi_minimal_tuning.py) utiliza `Kp = 170 W/V` y `Ki = 10 W/(V·s)` (frente a `250 W/V` y `1500 W/(V·s)` en el PoC). Con `Kp = 170 W/V`, absorber `~3178 W` de excedente inicial requiere proporcionalmente $\Delta V_{\text{dc}} \approx 3178/170 \approx 18.7\text{ V}$ ($340 + 18.7 = 358.7\text{ V}$, consistente con `357.66 V`).
2. **Dinámica interna del BESS 1RC:** el modelo completo incluye $R_0(\text{SoH})$ y la polarización $V_{\text{rc}}$ en los estados `x[12:15]`.
3. **Eficiencia bidireccional del DC/DC:** [`dc_dc_adapter.py`](../src/bess/dc_dc_adapter.py) aplica $\eta_{\text{charge}} = 0.95$ en el acoplamiento banco-bus.
4. **Dinámica AC del filtro LCL y del VSG (`M=80, D=1500`):** en el modelo de 16 estados, la potencia evacuada `P_bridge` varía transitoriamente con $\omega$, $\theta$ y las corrientes del LCL (`x[1:10]`), mientras el PoC asume evacuación instantánea $P_{\text{load}}/\eta$.

**Qué verificar en la futura integración:** con `Kp = 170 W/V, Ki = 10 W/(V·s)` en 16 estados, el pico con `SoC = 0.60` (`357.66 V`) supera ligeramente `V_warn = 357.0 V`, pero permanece **`16.34 V` por debajo de `V_chopper_on = 374.0 V`**, por lo que debe confirmarse explícitamente que `i_dump = 0.0 A` durante todo el transitorio a `SoC = 0.60`.

---

## 4. Contrato técnico de implementación (para futura integración opcional)

| Elemento del contrato | Especificación obligatoria |
| :--- | :--- |
| **Estados protegidos** | **Prohibido** alterar `x[0:16]` o añadir un segundo `solve_ivp`. La lógica de chopper/aislamiento se evalúa dentro de la función de derivadas del solver global (o mediante estado auxiliar explícitamente aprobado si se modela $E_{\text{dump}}$ continuo). |
| **Señales de entrada** | `vdc_eff` [V], `ipv_raw` [A], `soc_bess` [-], `bess_charge_limit_w` [W]. |
| **Señales de salida** | `i_dump >= 0` [A] (drenaje en numerador de `dVdc/dt`), `pv_isolated` [bool] (`i_pv_eff = 0` si `True`), `ovp_warn` [bool], `duty_chopper` $\in [0, 1]$. |
| **Prioridades de protección** | `1. Nivel 3 Aislamiento FV (391 V o E_dump >= E_max)` > `2. Nivel 2 Chopper regulado (374–391 V)` > `3. BESS PI (340 V)` > `4. UVLO inversor (< 200 V)`. |
| **Ley del actuador Nivel 2** | $D = \text{clip}\!\left(\frac{V_{\text{dc,eff}} - 374.0}{391.0 - 374.0},\, 0,\, 1\right)$, $i_{\text{dump}} = D\,\frac{V_{\text{dc,eff}}}{R_{\text{dump}}}$ con $R_{\text{dump}} \in [20, 25]\ \Omega$. |
| **Histéresis / Enclavamiento** | Nivel 1 (`ovp_warn`): activa $\ge 357.0\text{ V}$, limpia $< 350.2\text{ V}$. Nivel 3 (`pv_isolated`): activa $\ge 391.0\text{ V}$ o sobreenergía térmica; reposición solo si $V_{\text{dc,eff}} \le 357.0\text{ V}$ y $\Delta t \ge \Delta t_{\text{guard}}$. |
| **Límite térmico** | Acumulador $E_{\text{dump}} = \int V_{\text{dc,eff}}\,i_{\text{dump}}\,dt$ (con decaimiento térmico opcional); al alcanzar $E_{\text{max,térmico}}$ paramétrico, dispara Nivel 3. |
| **Criterios de aceptación (`PASS`)** | (1) `SoC=0.90`, rechazo `-80%` y `-100%` (`G=1000, Tc=0..25°C`): `max(Vdc) < 391.0 V` (o aislamiento FV exitoso en Nivel 3 sin rebote); (2) `SoC=0.60`, `-80%`: `e_dump_j == 0.0` (no interferencia); (3) Error de balance energético consistente; (4) `validate_obj1_regression.py` y `validate_physical_invariants.py` en `PASS` sin alterar `M=80, D=1500`. |

---

## 5. Dictamen de preparación

1. **¿Está la arquitectura suficientemente especificada para iniciar una implementación experimental opcional?**  
   **Sí.** El contrato técnico anterior define señales, prioridades, ley continua anti-*chattering*, aislamiento FV en Nivel 3 y criterios de aceptación sin ambigüedades topológicas ni violación de las reglas de `AGENTS.md`.
2. **Restricciones pendientes antes de considerar cerrado P-07:**
   - Ejecutar la integración en un módulo experimental desacoplado sobre el modelo completo de 16 estados (`Kp = 170 W/V, Ki = 10 W/(V·s)`).
   - Verificar que la transición continua de $D(V_{\text{dc}})$ y el enclavamiento discreto de Nivel 3 no degraden la convergencia ni el paso adaptativo de `solve_ivp` (`RK45`).
   - Confirmar no regresión en `validate_obj1_regression.py`, `validate_gfm_integrated_system.py` y `validate_physical_invariants.py`.
   - Especificar explícitamente el parámetro $E_{\text{max,térmico}}$ (y si se adopta $R_{\text{dump}} = 20\ \Omega$ o $25\ \Omega$) como parámetro de diseño documentado mientras no existan hojas de datos de hardware comercial.
