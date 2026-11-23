# Informe de Integración Experimental Opcional de OVP en el Modelo de 16 Estados (Pendiente P-07)

**Proyecto:** `microgrid_vsm` (Tesis de Maestría — Objetivo 2, Pendiente P-07)  
**Worktree / Rama:** `microgrid_vsm_p07_ovp` / `research/obj2-dc-bus-overvoltage` (derivada de PR #61, `3e26ecf17e811c2345eb7de239da7c671087e4c7`)  
**Módulos implementados:** [`src/controllers/dc_link_ovp.py`](../src/controllers/dc_link_ovp.py), [`src/microgrid_bess_dcdc.py`](../src/microgrid_bess_dcdc.py) (cableado opcional deshabilitado por defecto)  
**Pruebas y evidencias:** [`scripts/validate_p07_ovp_integration.py`](../scripts/validate_p07_ovp_integration.py), [`scripts/test_dc_link_ovp_unit.py`](../scripts/test_dc_link_ovp_unit.py), [`outputs/research_p07_ovp_integration/p07_ovp_integration_results.json`](../outputs/research_p07_ovp_integration/p07_ovp_integration_results.json)  
**Dictamen P-07:** **`PASS_NUMERICO` parcial** para el control promediado del chopper en 16 estados (`ovp_enabled=True`); **P-07 global permanece en `REVIEW`** por las funciones híbridas, térmicas y de hardware pendientes.

---

## 1. Arquitectura implementada

1. **Componente desacoplado y sin estado ([`DCLinkOVPController`](../src/controllers/dc_link_ovp.py)):**
   - Evalúa de forma puramente algebraica (sin mutar variables globales, atributos persistentes, enclavamientos ni temporizadores dentro del RHS de `solve_ivp`) la ley promediada de ciclo de trabajo:
     $$D(V_{\text{dc}}) = \text{clip}\!\left(\frac{V_{\text{dc}} - V_{\text{on}}}{V_{\text{hard}} - V_{\text{on}}},\, 0,\, 1\right), \quad i_{\text{dump}} = D(V_{\text{dc}})\,\frac{V_{\text{dc}}}{R_{\text{dump}}} \ge 0$$
   - Parámetros preliminares por defecto: `enabled=False`, `v_warn_v=357.0 V`, `v_on_v=374.0 V`, `v_hard_v=391.0 V`, `r_dump_ohm=25.0 Ω`. **Todos son hipótesis de simulación respecto a `340.0 V`, no límites comerciales certificados.**
   - Incluye la bandera opcional `pv_isolation_enabled=False` como abstracción sin memoria para pruebas (`ipv_eff = 0` si `Vdc >= V_hard`), no como modelo físico validado de interruptor DC.
2. **Integración no invasiva en [`MicrogridWithBESSDCDC`](../src/microgrid_bess_dcdc.py):**
   - Acepta `ovp_controller: DCLinkOVPController | None = None` (deshabilitado por defecto).
   - Conserva intactas las **16 variables dinámicas**, el único integrador global `solve_ivp` (`RK45`), `M = 80`, `D = 1500`, `src/microgrid.py` y `src/microgrid_bess_pi.py`.
   - Incorpora `- ovp_out.i_dump_a` en la entrada de corriente del bus DC (`i_bess=i_bus - ovp_out.i_dump_a`) manteniendo las convenciones de signo de `AGENTS.md`.

---

## 2. Resultados en el modelo completo de 16 estados

| Caso (`MicrogridWithBESSDCDC`, 50 Hz, `M=80, D=1500`) | `ovp_enabled` | `Vdc_post_max` [V] | `Vdc_final` [V] | `duty_max` | `I_dump_max` [A] | `P_dump_max` [W] | `E_dump` [J] | `t_act_prom` [s] | Error rel. energía | `nfev` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `socmax_m80pct_ovp_disabled_default` (`G=800, -80%`) | `False` | `403.6090` | `403.6058` | `0.0000` | `0.000` | `0.00` | `0.000` | `0.000` | `6.21e-4` | `153788` |
| `socmax_m80pct_ovp_enabled_r25` (`G=800, -80%`) | `True` | `380.6425` | `380.6311` | `0.3907` | `5.949` | `2264.51` | `1669.871` | `1.160` | `3.37e-4` | `153758` |
| `bess_active_soc060_m80pct_ovp_enabled_r25` (`SoC=0.60`) | `True` | `357.6637` | `357.0342` | `0.0000` | `0.000` | `0.00` | `0.000` | `0.000` | `1.84e-4` | `153794` |
| `socmax_g1000_m99pct_ovp_enabled_r25` (`G=1000, -99%`) | `True` | `384.7962` | `384.7933` | `0.6351` | `9.775` | `3761.34` | `3216.692` | `1.187` | `2.37e-4` | `170564` |

### Verificaciones principales
1. **Equivalencia numérica con `ovp_enabled=False`:** reproduce exactamente `403.6090 V` (`403.6058 V` final) de la auditoría histórica sin OVP.
2. **Mitigación efectiva en `SoC = 0.90`:** reduce el pico de `403.6090 V` a `380.6425 V` (`-22.97 V`, debajo de `391.0 V` y del límite de banco `403.2 V`), sin rigidez numérica (`nfev = 153758` frente a `153788`) y con `0` violaciones UVLO (`vdc >= 200 V`).
3. **No intervención en operación normal (`SoC = 0.60`):** `vdc_post_max = 357.6637 V` (`< 374.0 V`), `E_dump = 0.0 J` y `t_act_prom = 0.0 s`.
4. **Mayor irradiancia (`G = 1000 W/m²`, rechazo `-99 %` usando `0.01 * p_nom` por restricción `load_profile > 0`):** contiene `Vdc` en `384.7962 V` (`< 391.0 V`, `duty_max = 0.6351`), manteniendo el error relativo de balance energético en `2.37e-4`.
5. **Nota sobre `t_act_prom`:** representa el tiempo en que la ley promediada continua permanece con $D(V_{\text{dc}}) > 0$, **no** conmutaciones físicas PWM ni frecuencia de disparo.

---

## 3. Regresiones y pruebas ejecutadas

| Suite / Script | Resultado | Observación |
| :--- | :---: | :--- |
| [`scripts/test_dc_link_ovp_unit.py`](../scripts/test_dc_link_ovp_unit.py) | **`PASS`** | Valida `enabled=False`, acotamiento `D in [0,1]` y abstracción `pv_isolation_enabled`. |
| [`scripts/validate_p07_ovp_integration.py`](../scripts/validate_p07_ovp_integration.py) | **`PASS`** | Valida los 4 escenarios en `MicrogridWithBESSDCDC` de 16 estados. |
| [`src/validation/validate_obj1_regression.py`](../src/validation/validate_obj1_regression.py) | **`PASS`** | `lcl_no_unphysical_oscillations`, `bess_step3`, `bess_soc_operational_limits` en `PASS`. |
| [`src/validation/validate_physical_invariants.py`](../src/validation/validate_physical_invariants.py) | **`PASS`** | Conservación DC, identidad BESS, límites SoC y signos en `PASS`. |
| [`src/validation/validate_gfm_integrated_system.py`](../src/validation/validate_gfm_integrated_system.py) | **`PASS` / `REVIEW`** | `steady_operation`, `load_step_20` y `bess_vs_no_bess` en `PASS`; `load_step_40` en `REVIEW` documentado (`AGENTS.md` #32–33). |

---

## 4. Funciones pendientes y alcance del cierre parcial

Quedan explícitamente **pendientes de implementación** (no simuladas falsamente dentro del RHS):
1. **Enclavamiento/histéresis de aislamiento FV de emergencia (Nivel 3) y temporizadores de guarda:** requieren una arquitectura híbrida por eventos fuera del RHS sin estado de `solve_ivp`.
2. **Límite térmico/energético acumulado ($E_{\text{dump}} \ge E_{\text{max,térmico}}$):** requiere modelo térmico o integrador de energía con eventos y parámetros comerciales certificados.
3. **Conmutación física PWM, especificaciones de semiconductores, condensador y validación experimental/HIL.**

En consecuencia, el **control promediado OVP en 16 estados** alcanza **`PASS_NUMERICO` parcial**, mientras **P-07 global se mantiene en `REVIEW`**.

---

## 5. Revisión final de equivalencia y convergencia numérica

La verificación reproducible en [`scripts/verify_p07_ovp_reproducibility_and_convergence.py`](../scripts/verify_p07_ovp_reproducibility_and_convergence.py) ([`p07_ovp_equivalence_and_convergence.json`](../outputs/research_p07_ovp_integration/p07_ovp_equivalence_and_convergence.json)) demuestra:

1. **Equivalencia bit a bit con `ovp_enabled=False` (`SoC = 0.90`, `-80 %` carga):**
   - Condiciones iniciales idénticas (`16` estados), `M = 80.0`, `D = 1500.0` y `nfev = 153788` idéntico.
   - Diferencia máxima en la trayectoria de los **16 estados**: `0.0`.
   - Diferencia máxima en el RHS de `solve_ivp` y en las señales eléctricas (`Vdc`, `p_pcc`, `p_bridge`, `i_bess_bus_a`, `p_bess_bus_w`, `v_bess_unit_v`, `xi_bess_vdc_v_s`): `0.0`, con `0` acciones OVP.
2. **Convergencia numérica bajo refinamiento (`max_step: 5e-5 → 1e-5`, `rtol: 1e-6 → 1e-7`, `atol: 1e-8 → 1e-9`):**
   - `vdc_post_max_v`: `380.642470173 V` vs. `380.642475211 V` (`|Δ| = 5.04e-6 V`).
   - `vdc_final_v`: `380.631065398 V` vs. `380.631065397 V` (`|Δ| = 1.65e-9 V`).
   - `e_ovp_dump_j`: `1669.871114 J` vs. `1669.871160 J` (`|Δ| = 4.59e-5 J`, relativa `2.75e-8`).
   - `p_ovp_dump_max_w`: `2264.514829 W` vs. `2264.516607 W` (`|Δ| = 1.78e-3 W`).
   - `t_first_activation_s`: `0.041 s` vs. `0.041 s` (`|Δ| = 0.0 s`).
   - Costo computacional: `nfev` pasa de `153758` a `720128` (`ratio = 4.68` para un refinamiento `5.0x` de `max_step`), descartando rigidez anómala o *chattering*.
3. **Advertencia de seguridad sobre `v_hard = 391.0 V`:** mientras el aislamiento FV con enclavamiento híbrido y el límite térmico permanezcan pendientes, **`v_hard = 391.0 V` no debe presentarse como protección efectiva independiente** ante excedentes que superen la capacidad de `R_dump = 25 Ω` (p. ej., clima muy frío con irradiancia elevada y BESS saturado).

---

## 6. Relación exacta de archivos para un eventual PR DRAFT

**Incluidos en el paquete P-07:**
- Código y pruebas: `src/controllers/dc_link_ovp.py`, `src/microgrid_bess_dcdc.py`, `scripts/poc_p07_dc_bus_ovp.py`, `scripts/test_dc_link_ovp_unit.py`, `scripts/validate_p07_ovp_integration.py`, `scripts/verify_p07_ovp_reproducibility_and_convergence.py`.
- Documentación: `docs/fuentes_p07_proteccion_vdc.md`, `docs/investigacion_p07_proteccion_sobretension_vdc.md`, `docs/validacion_cuantitativa_poc_p07_vdc.md`, `docs/preparacion_integracion_p07_vdc.md`, `docs/informe_integracion_p07_ovp.md`.
- Evidencias nuevas: `outputs/research_p07_ovp_poc/` (`poc_p07_results.json`, `poc_p07_summary.csv`) y `outputs/research_p07_ovp_integration/` (`p07_ovp_integration_results.json`, `p07_ovp_equivalence_and_convergence.json`).

**Excluidos del PR (salidas históricas regeneradas localmente en `outputs/validation/` durante regresiones):**
- `outputs/validation/bess_step3/case_a_constant_discharge.png`, `case_b_pulse_discharge-rest-charge.png`, `summary_cases.csv`, `summary_metrics.csv`.
- `outputs/validation/gfm_integrated_system/gfm_integrated_system_summary.json`.
- `outputs/validation/objective1_regression/objective1_regression_summary.json`.
- `outputs/validation/physical_invariants/gfm_physical_invariants_summary.json`.

