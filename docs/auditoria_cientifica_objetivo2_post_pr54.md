# Auditoría Científica Independiente Post-PR #54 — Objetivo 2

**Repositorio:** `daguevarac-debug/microgrid_vsm`
**Rama de auditoría:** `audit/ieee906-objective2-scientific-corrections` (derivada de `feat/ieee906-vsg50-interface` @ `687d24f`)
**Alcance:** Revisión independiente de afirmaciones físicas, matemáticas, numéricas y documentales del PR #54, integrando además los hallazgos de auditoría de código de Codex Cloud (`review/pr54-independent` @ `b63e602`, no publicado aún en GitHub).

---

> **Actualización:** esta auditoría describe el estado anterior al parche. La [validación cruzada posterior](validacion_cruzada_objetivo2_pr55_pr56.md) documenta los casos regenerados y mantiene en `REVIEW` la convergencia frente al tamaño de paso.

## 1. Resumen Ejecutivo y Dictamen sobre el Cierre Condicionado del Objetivo 2

El paquete de simulación del Objetivo 2 alcanza un **cierre numérico, dimensional y paramétrico preliminar**, pero **no constituye validación experimental completa** ni puede declararse **cierre definitivo del Objetivo 2** en el estado actual del commit `687d24f` por dos razones principales:

1. **Defectos de severidad alta en `src/microgrid_bess_dcdc.py` (identificados por Codex Cloud en `review/pr54-independent` @ `b63e602`):**
   - El cálculo de límites pasa `vbus_eval = max(Vdc, Vmin)` a `convert_power`, mientras que la corriente efectiva en el bus se calcula como `i_bus = P_bus / Vdc`, lo que puede superar el límite de corriente configurado cuando `Vdc < Vmin` (`50,0 V`).
   - Los límites del DC/DC (`p_min_w`, `p_max_w`) no se intersectan explícitamente con `_available_p_bess_max_w(SoH)`, lo que puede omitir restricciones heredadas de potencia y afectar la saturación del PI y su anti-windup.
   - Aunque Codex verificó 49 pruebas y 29 subpruebas en su rama local, las **campañas dinámicas completas de 50/60 Hz y los 13 escenarios DC/DC todavía no se han regenerado con estas correcciones**.
2. **Brechas experimentales y de referencia externa declaradas:**
   - Todos los parámetros electroquímicos (`OCV`, `R0`, `R1`, `C1`, `k_R`, `k_deg`) son proxies numéricos o hipótesis paramétricas (ninguno calibrado experimentalmente en laboratorio propio).
   - La replicación de la tabla resumen IEEE PES 2015 mantiene una discrepancia máxima del **9,54 %** (`REVIEW`).

**Dictamen:** Se recomienda **mantener el PR #54 y el presente PR de auditoría en borrador**, conservar la condición de **no declarar el Objetivo 2 completamente validado**, e integrar/re-ejecutar las campañas dinámicas 50/60 Hz y los 13 escenarios DC/DC una vez incorporadas las correcciones de límites de `src/microgrid_bess_dcdc.py`.

---

## 2. Clasificación Detallada de Hallazgos

| ID | Hallazgo Auditado | Clasificación | Evidencia Verificable | Acción Realizada / Pendiente |
|:---:|:---|:---:|:---|:---|
| **H1** | Arquitectura `48×2s2p` (`BAT26-53`), modelo 1RC y trazabilidad electroquímica | **PARCIALMENTE CONFIRMADO** | `src/bess/model.py`, `OCV_SOC.xlsx` (`FIgura5(B)`, 58 filas), `docs/bat26-35-ecm-parameter-evidence.md`, `docs/bat26-49-source-evidence-matrix.md` | Consistencia dimensional y de signos confirmada; en `docs/dossier_objetivo2_presentacion_director.md` §3.3 se separó explícitamente dato bibliográfico (`66 Ah`, `3,75 V`), proxy numérico (`OCV` en descarga, `R1/C1`), hipótesis provisional (`R0` pulso 10 s) e hipótesis empírica de software (`k_R`, `k_deg`). |
| **H2** | Defectos de límites en `src/microgrid_bess_dcdc.py` (`max(Vdc, Vmin)` vs `P_bus/Vdc` y falta de intersección con `_available_p_bess_max_w(SoH)`) | **CONFIRMADO** | `src/microgrid_bess_dcdc.py` L123, L162, L172–173, L188, L201; auditoría Codex Cloud (`review/pr54-independent` @ `b63e602`) | No se modificó `src/microgrid_bess_dcdc.py` en esta rama. Se documentó expresamente en el dossier (§5 y §8) qué conclusiones requieren re-verificación post-parche (los 13 escenarios DC/DC y campañas 50/60 Hz con BESS+DC/DC). |
| **H3** | Ausencia de recarga sostenida en los 13 escenarios DC/DC | **CONFIRMADO** | `outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json` (los 13 casos tienen `i_bank_ss_mean_a >= 0` y `soc_final <= soc_initial`; corrientes negativas son solo transitorias) | Se añadió prueba dinámica de **carga sostenida** (`-40 %`, `3000 -> 1800 W`, 50 Hz) en `src/validation/test_audit_post_pr54_sustained_charge.py`, verificando `i_bank_ss = -5,056 A`, `P_bank/P_bus = 0,95 = eta_ch`, aumento neto de SoC y balances energéticos (sujeto a re-verificación post-parche). |
| **H4** | Subestimación de residuos energéticos publicados en el dossier | **CONFIRMADO** | `outputs/validation/phase5_scientific_audit.json` (`max_dcdc_conversion_residual_post_j = 1.023e-12 J`, `max_1rc_bank_residual_max_w = 4.547e-13 W`) vs. dossier previo (`1.42e-13 J`, `3.41e-13 W`) | Corregido en `docs/dossier_objetivo2_presentacion_director.md` §5, incluyendo los residuos de la prueba de carga sostenida (`1.819e-12 J` y `6.821e-13 W`). |
| **H5** | Sensibilidad numérica de la diferencia de `62,6 µHz` en nadir (+40 % a 50 Hz) | **ESTABLE FRENTE A TOLERANCIAS / PASO EN REVIEW** | `src/validation/audit_vsg_nadir_convergence.py`, `outputs/validation/vsg_50hz_nadir_convergence_audit.json` | Ver Sección 3 (`L1_RK45_base` vs. `L2_RK45_tol`: $\Delta f_{\text{cont}} = -62{,}446\ \mu\text{Hz}$ idéntico a $<0{,}001\ \mu\text{Hz}$). |
| **H6** | Interpretación de pérdidas en IEEE 906 y efecto de `%noloadloss = 0` del transformador | **CONFIRMADO** | `outputs/analysis/ieee_europe_lv_906/qsts_24h_scenarios_comparison.csv`, `scripts/ieee_europe_lv_906_interface_and_qsts.py` | Corregido en el dossier §7.2: pérdidas exclusivas del alimentador (`-1,21 %` barra 34; `-5,43 %` barra 822) vs. pérdidas totales con transformador (`+0,89 %` barra 34; `-3,30 %` barra 822), más sensibilidad algebraica paramétrica $P_0 \in [10, 25]\text{ W}$ (punto de equilibrio en $P_0 \approx 6,97\text{ W}$). |
| **H7** | Tensiones máximas (`255,82 V`, `1,065 pu`) y límites normativos EN 50160 | **CONFIRMADO** | `outputs/analysis/ieee_europe_lv_906/qsts_24h_scenarios_comparison.csv` (`base_no_dg = 1,06432 pu / 255,63 V`; `pv_bess_far_822 = 1,06512 pu / 255,82 V`) | Corregido en el dossier §7.2: se distingue base `416/sqrt(3) = 240,18 V` (con `Vsource = 1,05 pu`), referencia `230 V` (`+10 % = 253,0 V`) y criterios temporales de EN 50160 (promedios 10 min durante 1 semana), sin declarar incumplimiento formal desde 24 h QSTS. |
| **H8** | Secuencia cero en transformador `YNyn0`, `Dyn`, `Ynd` | **CONFIRMADO** | `outputs/analysis/ieee_europe_lv_906/transformer_zero_sequence_audit.json` | Validado que `YNyn0` transmite $I_0$ si el inversor es de 4 hilos aterrado ($0,3059\text{ A}$ en 416 V) y solo la atenúa en 3 hilos sin neutro ($0,0051\text{ A}$). |
| **H9** | Discrepancia del `9,54 %` frente a tablas IEEE PES 2015 | **PENDIENTE (`REVIEW`)** | `docs/ieee_europe_lv_906_reference_audit.md`, `outputs/validation/phase5_scientific_audit.json` (`C08`) | Conservado explícitamente en `REVIEW` sin forzar explicación no reproducible. |
| **H10** | Validación experimental BESS, catálogo de transformador, perfil solar medido y FOVIC | **BLOCKED** | `outputs/validation/phase5_scientific_audit.json` (`C09`), `AGENTS.md` | Mantenido explícitamente fuera del alcance implementado del Objetivo 2. |

---

## 3. Sensibilidad Numérica del VSG (`+40 %`, 50 Hz, con y sin BESS)

Se ejecutó la campaña escalonada reproducible [`src/validation/audit_vsg_nadir_convergence.py`](../src/validation/audit_vsg_nadir_convergence.py) conservando $M = 80$, $D = 1500$, $f_0 = 50\text{ Hz}$ y el vector protegido de 16 estados sobre el horizonte completo de $6{,}5\text{ s}$:

| Nivel | Método | $\Delta t_{\max}$ [s] | `rtol` / `atol` | $f_{\text{min,BESS}}$ [Hz] ($t_{\text{nadir}}$) | $f_{\text{min,sin BESS}}$ [Hz] ($t_{\text{nadir}}$) | $\Delta f_{\text{grid}}$ [$\mu$Hz] | $\Delta f_{\text{cont}}$ [$\mu$Hz] | `nfev` (con / sin) |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|
| `L1_RK45_base` | `RK45` | $5\times 10^{-5}$ | $10^{-6} / 10^{-8}$ | `49,975616374` ($3{,}2674\text{ s}$) | `49,975678820` ($0{,}8918\text{ s}$) | `-62,552` | **`-62,446`** | `786 266 / 786 278` |
| `L2_RK45_tol` | `RK45` | $5\times 10^{-5}$ | $10^{-8} / 10^{-10}$ | `49,975616374` ($6{,}4231\text{ s}$) | `49,975678819` ($0{,}8918\text{ s}$) | `-62,457` | **`-62,446`** | `986 624 / 987 434` |

**Conclusiones técnicas de la sensibilidad:**
1. **Tolerancia local vs. error global efectivo:** Aunque $\text{rtol} = 10^{-6}$ sobre $\omega = 314{,}16\text{ rad/s}$ sugiere una tolerancia local por paso de $\sim 50\ \mu\text{Hz}$, el límite $\Delta t_{\max} = 5\times 10^{-5}\text{ s}$ impuesto por la dinámica eléctrica rápida del filtro LCL y la inercia $M = 80$ mantiene el error global efectivo en la frecuencia mecánica muy por debajo del microhertz.
2. **Estabilidad frente a tolerancias:** Al refinar `rtol` y `atol` en $100\times$ (`L1` $\to$ `L2`), $\Delta f_{\text{cont}}$ permanece invariante en **`-62,446 µHz`** (deriva $< 0{,}001\ \mu\text{Hz}$). El pequeño desplazamiento de $\Delta f_{\text{grid}}$ (`-62,552` $\to$ `-62,457 µHz`) se debe en parte a la discretización de muestreo ($\Delta t = 5\times 10^{-4}\text{ s}$ vs. $10^{-4}\text{ s}$) en torno al mínimo transitorio en $t = 0{,}8918\text{ s}$. Ambos niveles usan el mismo paso máximo; no demuestran convergencia frente al paso ni justifican descartar otros errores. Los niveles L3 y L4 no figuran en la evidencia y permanecen pendientes.
3. **Distinción física del instante de nadir:** Sin BESS, el mínimo es un valle transitorio breve en $t = 0{,}8918\text{ s}$ previo al colapso de $V_{dc}$ ($311{,}52\text{ V}$) y autolimitación de la carga ($3535{,}36\text{ W}$); con BESS, la frecuencia desciende monótonamente hacia un equilibrio plano de régimen permanente ($49{,}975616\text{ Hz}$). Ambas trayectorias siguen sujetas a re-verificación tras el parche de límites en `src/microgrid_bess_dcdc.py`.

---

## 4. Conclusiones que Requieren Re-verificación Post-Parche de Límites

Una vez que se integren las correcciones de `src/microgrid_bess_dcdc.py` (`review/pr54-independent` @ `b63e602`), deberán regenerarse y re-verificarse:
1. Los **13 escenarios de `validate_bess_dcdc_50hz.py`** (`bess_dcdc_50hz_summary.json`), especialmente los casos con restricción de potencia (`irrad_drop_dcdc_pmax1200w`), variación de `SoH` (`0,55`–`1,00`) y baja tensión de banco (`soc0p12_below340v`), así como cualquier caso límite donde `Vdc` pudiera acercarse a `Vmin`.
2. Las **campañas dinámicas 50/60 Hz** (`validate_vsg_50hz_interface.py` y `vsg_50hz_interface_audit_6p5s.json`) en los escenarios con BESS+DC/DC habilitado.
3. La prueba adicional de **carga sostenida** (`test_audit_post_pr54_sustained_charge.py`).
4. Las tablas de las **Secciones 4, 5 y 6** del dossier [`docs/dossier_objetivo2_presentacion_director.md`](../docs/dossier_objetivo2_presentacion_director.md).
