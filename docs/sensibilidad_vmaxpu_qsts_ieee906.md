# Análisis de Sensibilidad: Impacto de `Vmaxpu=1.05` vs. `Vmaxpu=1.20` en los Escenarios QSTS FV+BESS del Benchmark IEEE European LV (906 Barras)

- **Fecha:** 2026-11-20
- **Rama experimental:** `experiment/ieee906-vmaxpu-qsts-sensitivity` (derivada de `audit/scientific-pending-review`, commit `547b9fa`, que incluye PR #57 + PR #58)
- **Alcance ejecutado:** Experimento mínimo de 30 flujos de potencia OpenDSS (5 instantes representativos $\times$ 3 escenarios $\times$ 2 valores de `Vmaxpu`). **No se ejecutó la campaña completa de 24 horas (1 440 minutos)**; su regeneración queda únicamente como recomendación fundamentada.
- **Dictamen:** **Sensibilidad MATERIAL en magnitudes absolutas y en el signo del ahorro de importación entre barras 34 y 822; ranking cualitativo de pérdidas y soporte de tensión conservado. Se recomienda regenerar la campaña QSTS completa de 24 h con `Vmaxpu=1.20` y conservar ambas configuraciones como análisis de sensibilidad.**

---

## 1. Fase 1 — Auditoría del Parámetro `Vmaxpu` e Implementación QSTS

1. **Dónde se establece `Vmaxpu` y valor efectivo:**
   En los archivos oficiales del alimentador (`Master.dss` y `Loads.txt`, commit inmutable `5005c668a72d20775f4c2d060feebb2866ba1d38` de `tshort/OpenDSS`), ninguna de las 55 cargas monofásicas especifica `Vmaxpu`. En consecuencia, OpenDSS (`opendssdirect.py==0.9.4`, `dss-python==0.15.7`) aplica el valor interno por defecto **`Vmaxpu = 1.05`** (y `Vminpu = 0.95`) sobre la tensión nominal de carga `kV = 0.23` ($230\text{ V}$). Esto fija un umbral de **$241{,}50\text{ V}$** por encima del cual todas las cargas `Model = 1` conmutan automáticamente de potencia constante a **impedancia constante** ($P, Q \propto V^2$).
2. **Interacción con la cabecera de `1.05 pu`:**
   Con `Vsource.Source pu=1.05` sobre $416 / \sqrt{3} = 240{,}178\text{ V}$, la red opera habitualmente entre $245$ y $255\text{ V}$ ($1{,}065\text{–}1{,}107\text{ pu}$ sobre base $230\text{ V}$). Por ello, en la configuración original del PR #57 (`scripts/ieee_europe_lv_906_interface_and_qsts.py`), casi la totalidad de las 55 cargas opera fuera del intervalo de potencia constante.
3. **Hipótesis conservadas sin modificar archivos canónicos:**
   - Transformador de acoplamiento de 5 kVA (`H2_YNyn0_zk4p2_r1p5_nominal_hyp`): `YNyn0`, $r_k = 1{,}5\ \%$, $x_k = 4{,}0\ \%$, **`P0 = 0` (`%noloadloss=0`)** y **`%imag=0`**.
   - Tensión de cabecera: **`1.05 pu`** en `11 kV`.
   - Acoplamiento **QSTS unidireccional** (sin realimentación dinámica al modelo ODE del VSG).
   - `Master.dss`, `Loads.txt`, ecuaciones VSG, modelos electroquímicos y resultados de PR #57/#58 permanecen intactos.
4. **Selección de 5 instantes representativos (a partir del perfil nominal de 24 h y snapshots del PR #57):**
   - `00:01` (`min=0`): Demanda mínima nocturna (`2,797 kW`), sin FV ni BESS (`DER_net = 0,000 kW`).
   - `09:26` (`min=565`): Demanda máxima diaria (`57,358 kW`, instante pico IEEE 2015), FV alta (`2,340 kW`), BESS cargando (`-0,216 kW`), `DER_net = +2,123 kW`.
   - `12:00` (`min=720`): Demanda media-alta (`29,746 kW`), pico solar (`3,000 kW`), carga máxima BESS (`-1,000 kW`), `DER_net = +2,000 kW` (verificado contra `noon_snapshot` del PR #57).
   - `15:30` (`min=930`): Demanda media-baja diurna (`16,737 kW`), FV moderada (`1,826 kW`), BESS en reposo (`0,000 kW`), `DER_net = +1,826 kW`.
   - `19:00` (`min=1140`): Demanda alta vespertina (`33,837 kW`), FV nula (`0,000 kW`), descarga máxima BESS (`+1,354 kW`), `DER_net = +1,354 kW` (verificado contra `evening_peak_snapshot_min1140` del PR #57).
5. **Verificación de paridad con PR #57 (`Vmaxpu=1.05`):**
   Los instantes `min=720` y `min=1140` coinciden con [`phase3_phase4_interface_and_qsts_summary.json`](../outputs/analysis/ieee_europe_lv_906/phase3_phase4_interface_and_qsts_summary.json) con discrepancia máxima $\le 1{,}08 \times 10^{-4}\text{ kW}$ en carga, $\le 2 \times 10^{-6}\text{ kW}$ en pérdidas y $\le 1 \times 10^{-7}\text{ pu}$ en tensión.

---

## 2. Fase 2 — Resultados del Experimento Mínimo

- **Script reproducible:** [`scripts/audit_ieee906_vmaxpu_qsts_sensitivity.py`](../scripts/audit_ieee906_vmaxpu_qsts_sensitivity.py)
- **Evidencias independientes:** [`outputs/experiment_vmaxpu_qsts_sensitivity/vmaxpu_qsts_representative_summary.json`](../outputs/experiment_vmaxpu_qsts_sensitivity/vmaxpu_qsts_representative_summary.json) y [`vmaxpu_qsts_representative_instants.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/vmaxpu_qsts_representative_instants.csv)
- **Costo computacional real:** **3,095 s** de tiempo de pared para las 30 resoluciones OpenDSS (`Python 3.11.2`, `opendssdirect.py==0.9.4`, `dss-python==0.15.7`).

### 2.1 Efecto del modelo de carga (`Vmaxpu=1.20` menos `Vmaxpu=1.05`)

| Instante | Escenario | Cargas fuera de PQ (`1.05` $\to$ `1.20`) | $\Delta P_{\text{load}}$ [kW] ([%]) | $\Delta Q_{\text{load}}$ [kvar] | $\Delta P_{\text{loss,red}}$ [kW] ([%]) | $\Delta P_{\text{loss,tot}}$ [kW] ([%]) | $\Delta V_{\min}$ [pu] |
|:---:|:---|:---:|---:|---:|---:|---:|---:|
| `00:01` | `base_no_dg` | `100,0 %` $\to$ `0,0 %` | `-0,2481` (`-8,15 %`) | `-0,0815` | `-0,00037` (`-15,63 %`) | `-0,00037` (`-15,63 %`) | `+0,000102` |
| `09:26` | `base_no_dg` | `78,2 %` $\to$ `0,0 %` | `-1,4732` (`-2,50 %`) | `-0,4841` | `-0,03675` (`-1,76 %`) | `-0,03675` (`-1,76 %`) | `-0,000218` |
| `09:26` | `pv_bess_far_822_xfmr_5kva` | `78,2 %` $\to$ `0,0 %` | `-1,5046` (`-2,56 %`) | `-0,4944` | `-0,03670` (`-1,82 %`) | `-0,03671` (`-1,81 %`) | `-0,000215` |
| `12:00` | `base_no_dg` | `100,0 %` $\to$ `0,0 %` | `-2,0363` (`-6,41 %`) | `-0,6693` | `-0,03785` (`-12,00 %`) | `-0,03785` (`-12,00 %`) | `+0,000964` |
| `12:00` | `pv_bess_near_34_xfmr_5kva` | `100,0 %` $\to$ `0,0 %` | `-2,0437` (`-6,43 %`) | `-0,6717` | `-0,03753` (`-12,15 %`) | `-0,03753` (`-11,74 %`) | `+0,000969` |
| `12:00` | `pv_bess_far_822_xfmr_5kva` | `100,0 %` $\to$ `0,0 %` | `-2,0680` (`-6,50 %`) | `-0,6797` | `-0,03642` (`-12,74 %`) | `-0,03643` (`-12,27 %`) | `+0,000981` |
| `15:30` | `base_no_dg` | `100,0 %` $\to$ `0,0 %` | `-1,2588` (`-6,99 %`) | `-0,4137` | `-0,01600` (`-12,79 %`) | `-0,01600` (`-12,79 %`) | `+0,000828` |
| `15:30` | `pv_bess_far_822_xfmr_5kva` | `100,0 %` $\to$ `0,0 %` | `-1,2778` (`-7,09 %`) | `-0,4200` | `-0,01494` (`-13,87 %`) | `-0,01495` (`-12,80 %`) | `+0,000846` |
| `19:00` | `base_no_dg` | `100,0 %` $\to$ `0,0 %` | `-2,1608` (`-6,00 %`) | `-0,7102` | `-0,04353` (`-10,06 %`) | `-0,04353` (`-10,06 %`) | `+0,000999` |
| `19:00` | `pv_bess_near_34_xfmr_5kva` | `100,0 %` $\to$ `0,0 %` | `-2,1668` (`-6,02 %`) | `-0,7122` | `-0,04332` (`-10,14 %`) | `-0,04332` (`-10,02 %`) | `+0,001003` |
| `19:00` | `pv_bess_far_822_xfmr_5kva` | `100,0 %` $\to$ `0,0 %` | `-2,1840` (`-6,06 %`) | `-0,7178` | `-0,04269` (`-10,39 %`) | `-0,04269` (`-10,27 %`) | `+0,001015` |

### 2.2 Separación del efecto de ubicación (Barra 34 vs. Barra 822 respecto a `base_no_dg`)

| Instante (`DER_net`) | `Vmaxpu` | $\Delta P_{\text{load}}$ Barra 34 / 822 [W] | $\Delta P_{\text{loss,red}}$ Barra 34 / 822 [%] | $\Delta P_{\text{loss,tot}}$ Barra 34 / 822 [%] | Ventaja importación 822 sobre 34 ($P_{\text{src,34}} - P_{\text{src,822}}$) [W] |
|:---:|:---:|:---:|:---:|:---:|---:|
| `09:26` (`+2,123 kW`) | `1.05` | `+8,36 / +31,39` | `-0,68 % / -3,23 %` | `-0,10 % / -2,62 %` | `+29,81` |
| `09:26` (`+2,123 kW`) | `1.20` | `0,00 / -0,01` | `-0,69 % / -3,28 %` | `-0,10 % / -2,67 %` | **`+52,81`** |
| `12:00` (`+2,000 kW`) | `1.05` | `+7,45 / +31,68` | `-2,08 % / -9,36 %` | `+1,35 % / -5,89 %` | **`-1,39`** *(rebote de carga)* |
| `12:00` (`+2,000 kW`) | `1.20` | `-0,01 / -0,05` | `-2,24 % / -10,12 %` | `+1,65 % / -6,18 %` | **`+21,89`** |
| `15:30` (`+1,826 kW`) | `1.05` | `+3,92 / +19,02` | `-2,64 % / -13,89 %` | `+4,56 % / -6,63 %` | **`-1,10`** *(rebote de carga)* |
| `15:30` (`+1,826 kW`) | `1.20` | `0,00 / -0,02` | `-2,83 % / -14,96 %` | `+5,43 % / -6,64 %` | **`+13,23`** |
| `19:00` (`+1,354 kW`) | `1.05` | `+5,96 / +23,16` | `-1,25 % / -5,08 %` | `-0,10 % / -3,92 %` | **`-0,64`** *(rebote de carga)* |
| `19:00` (`+1,354 kW`) | `1.20` | `0,00 / 0,00` | `-1,33 % / -5,44 %` | `-0,05 % / -4,14 %` | **`+15,92`** |

### 2.3 Hallazgos físicos clave

1. **Proporción de cargas fuera del régimen `PQ`:** Bajo `Vmaxpu = 1.05`, el **100 % (55/55)** de las cargas opera como impedancia constante en 4 de los 5 instantes (`00:01`, `12:00`, `15:30`, `19:00`) y el **78,2 % (43/55)** incluso en el pico máximo (`09:26`). Bajo `Vmaxpu = 1.20`, el **0,0 % (0/55)** sale del régimen `PQ`.
2. **Impacto material en magnitudes absolutas:** Pasar a `Vmaxpu = 1.20` reduce la potencia de carga activa y reactiva entre **`-2,5 %` y `-8,2 %`** y reduce las **pérdidas del alimentador entre `-1,8 %` y `-15,6 %`** (`-10,1 %` a `-13,9 %` durante las ventanas operativas de FV+BESS), debido a la relación cuadrática $P_{\text{loss}} \propto I^2 R \propto P^2$. Las pérdidas del transformador de 5 kVA (`5,04` a `12,57 W`) apenas varían ($< 0{,}01\text{ W}$) porque `p_der_net` es idéntico. Las tensiones nodales cambian menos de `0,00102 pu` ($\approx 0{,}25\text{ V}$).
3. **Efecto sobre la comparación Barra 34 vs. Barra 822:**
   - **El ranking cualitativo de pérdidas y soporte de tensión NO cambia:** la ubicación lejana en barra 822 sigue siendo claramente superior a la barra 34 en reducción de pérdidas del alimentador y pérdidas totales (incluso mejora ligeramente en términos relativos bajo `1.20`: `-10,12 %` vs. `-9,36 %` a mediodía y `-5,44 %` vs. `-5,08 %` a las `19:00`).
   - **El signo de la ventaja en importación de subestación SÍ se invierte:** bajo `Vmaxpu = 1.05`, inyectar en barra 822 eleva la tensión local por encima de $241{,}50\text{ V}$ y provoca un **rebote artificial de carga** (`+19` a `+32 W`) que supera el ahorro en pérdidas, haciendo que la barra 822 importe ligeramente *más* energía que la barra 34 (`-0,64` a `-1,39 W`, lo que explicaba el anómalo `499,947 kWh` vs. `499,937 kWh` del PR #57). Bajo `Vmaxpu = 1.20`, el rebote desaparece (`0,00 W`) y la barra 822 reduce de forma consistente la importación desde la subestación (`+13,2` a `+52,8 W` sobre la barra 34).

---

## 3. Fase 3 — Campaña QSTS Completa de 24 Horas (`Vmaxpu = 1.20`) y Contraste con PR #57 (`Vmaxpu = 1.05`)

- **Script reproducible:** [`scripts/run_ieee906_qsts_24h_vmaxpu1p20.py`](../scripts/run_ieee906_qsts_24h_vmaxpu1p20.py)
- **Evidencias independientes:**
  - [`outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_comparison.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_comparison.csv)
  - [`outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_vs_pr57.json`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_vs_pr57.json)
- **Costo computacional y comprobaciones de integridad:**
  - **4 320 flujos OpenDSS** (3 escenarios $\times$ 1 440 minutos) completados en **`16,347 s`** (`3,518 s` `base_no_dg`, `6,735 s` barra 34, `6,090 s` barra 822).
  - Residuo máximo de balance de potencia activa en los 4 320 pasos: **`0,002274 kW`**.
  - Máximo número de cargas fuera del rango `PQ` (`[0,95; 1,20] pu`) en todo el día: **`0 / 55`** en los 3 escenarios.
  - No se repitió `Vmaxpu = 1.05`; el contraste utiliza directamente el archivo versionado [`outputs/analysis/ieee_europe_lv_906/qsts_24h_scenarios_comparison.csv`](../outputs/analysis/ieee_europe_lv_906/qsts_24h_scenarios_comparison.csv) (`sha256: 8892d809...`).

### 3.1 Acumulados diarios de 24 h: `Vmaxpu = 1.20` (nuevo) vs. `Vmaxpu = 1.05` (PR #57)

| Escenario | `Vmaxpu` | Demanda [kWh] | Importación [kWh] | Pérd. red [kWh] | Pérd. xfmr [kWh] | Pérd. total [kWh] | $\Delta$ Pérd. red vs. base [%] | $\Delta$ Pérd. total vs. base [%] | $V_{\min}$ / $V_{\max}$ [pu] | Min $>1{,}05$ / $>1{,}06$ |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| `base_no_dg` | `1.05` | `517,306` | `522,368` | `5,0627` | `0,0000` | `5,0627` | `0,00 %` | `0,00 %` | `0,98165 / 1,06432` | `415 / 6` |
| `base_no_dg` | **`1.20`** | **`483,914`** | **`488,459`** | **`4,5450`** | `0,0000` | **`4,5450`** | `0,00 %` | `0,00 %` | `0,98143 / 1,06480` | `439 / 6` |
| `pv_bess_near_34_xfmr_5kva` | `1.05` | `517,375` | `499,937` | `5,0016` | `0,1064` | `5,1079` | `-1,21 %` | **`+0,89 %`** | `0,98180 / 1,06444` | `425 / 6` |
| `pv_bess_near_34_xfmr_5kva` | **`1.20`** | **`483,914`** | **`465,960`** | **`4,4867`** | `0,1063` | **`4,5930`** | **`-1,28 %`** | **`+1,06 %`** | `0,98158 / 1,06493` | `454 / 6` |
| `pv_bess_far_822_xfmr_5kva` | `1.05` | `517,598` | `499,947` | `4,7880` | `0,1074` | `4,8954` | `-5,43 %` | **`-3,30 %`** | `0,98228 / 1,06512` | `472 / 6` |
| `pv_bess_far_822_xfmr_5kva` | **`1.20`** | **`483,914`** | **`465,757`** | **`4,2822`** | `0,1073` | **`4,3895`** | **`-5,78 %`** | **`-3,42 %`** | `0,98206 / 1,06547` | `503 / 7` |

*(En los 6 casos, `minutes_above_1p10_pu = 0` y `minutes_below_0p90_pu = 0`; la inyección neta DER es idéntica: `22,5458 kWh/día`, con `22,9183 kWh` FV y `-0,3724 kWh` pérdidas ciclo BESS.)*

### 3.2 Desviaciones entre `Vmaxpu = 1.20` y `Vmaxpu = 1.05` y verificación de conclusiones

1. **Magnitudes absolutas:** Con `Vmaxpu = 1.20`, la demanda diaria cae **`-6,46 %` a `-6,51 %`** (`-33,39` a `-33,68 kWh`), la importación cae **`-6,49 %` a `-6,84 %`**, las pérdidas del alimentador caen **`-10,23 %` a `-10,56 %`** (`-0,51` a `-0,52 kWh`), y las pérdidas totales caen **`-10,08 %` a `-10,33 %`**. Las pérdidas del transformador de 5 kVA varían $< 0{,}0001\text{ kWh}$ y los extremos de tensión cambian $< 0{,}0005\text{ pu}$ ($\approx 0{,}12\text{ V}$).
2. **Orden de preferencia y signos de pérdidas totales (CONSERVADOS):**
   - La **barra 822 (lejana)** sigue siendo inequívocamente superior a la **barra 34 (cercana)** en reducción de pérdidas del alimentador (`-5,78 %` vs. `-1,28 %`), pérdidas totales (`-3,42 %` vs. `+1,06 %`) y mejora de tensión mínima (`0,98206` vs. `0,98158 pu`).
   - **Los signos de variación de pérdidas totales NO cambian:** siguen siendo **positivos (`+1,06 %`, antes `+0,89 %`)** en barra 34 (las pérdidas del transformador de `0,1063 kWh` superan el ahorro en el alimentador de `0,0583 kWh`) y **negativos (`-3,42 %`, antes `-3,30 %`)** en barra 822 (ahorro neto real de `0,1555 kWh/día`).
3. **Resolución de la anomalía de importación de red (Barra 822 vs. Barra 34):**
   - Bajo `Vmaxpu = 1.05`, la barra 822 importaba **`+0,0102 kWh` más** que la barra 34 (`499,9471` vs. `499,9368 kWh`) debido al rebote artificial de carga (`+0,2226 kWh` adicionales por impedancia constante).
   - Bajo `Vmaxpu = 1.20`, la demanda es invariante (`483,9136 kWh` en los 3 escenarios) y la barra 822 **reduce la importación en `-0,2034 kWh/día`** respecto a la barra 34 (`465,7569` vs. `465,9603 kWh`), en concordancia exacta con su ahorro neto de pérdidas totales (`0,2035 kWh/día`).

---

## 4. Comparación Completa de los Siete Escenarios (Campaña Integral de 24 h)

Para cerrar la matriz completa de 7 escenarios del PR #57 sin repetir simulaciones ya validadas, se ejecutaron exclusivamente los **4 escenarios fotovoltaicos sin BESS** con `Vmaxpu = 1.20` (`5 760` flujos OpenDSS nuevos: `pv_near_34_direct`, `pv_far_822_direct`, `pv_near_34_xfmr_5kva` y `pv_far_822_xfmr_5kva`) mediante [`scripts/run_ieee906_qsts_24h_pv_only_vmaxpu1p20.py`](../scripts/run_ieee906_qsts_24h_pv_only_vmaxpu1p20.py), reutilizando los 3 escenarios ya calculados en la Fase 3 (`base_no_dg`, `pv_bess_near_34_xfmr_5kva`, `pv_bess_far_822_xfmr_5kva`).

- **Costo computacional de los 4 escenarios nuevos (`5 760` flujos):** **`26,660 s`** de simulación pura (`6,80 s` `pv_near_34_direct`, `6,54 s` `pv_far_822_direct`, `6,70 s` `pv_near_34_xfmr_5kva`, `6,62 s` `pv_far_822_xfmr_5kva`; `55,779 s` totales incluyendo descarga fresca de los datos IEEE fijados).
- **Integridad y conservación de energía:** convergencia del `100 %` (`5 760 / 5 760` flujos), `0 / 55` cargas fuera del rango `PQ`, `e_loss_xfmr_der_kwh = 0,000000 kWh` en ambos escenarios de conexión directa, residuo diario de balance $\le 0{,}000514\text{ kWh}$ y residuo instantáneo máximo `0,002272 kW`.
- **Evidencias consolidadas (sin sobrescribir archivos previos):**
  - [`outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_all7_comparison.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_all7_comparison.csv)
  - [`outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_all7_paired_1p05_vs_1p20.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_all7_paired_1p05_vs_1p20.csv)
  - [`outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_all7_vmaxpu1p20_vs_pr57.json`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_all7_vmaxpu1p20_vs_pr57.json)

### 4.1 Tabla comparativa completa de los 7 escenarios (`Vmaxpu = 1.05` PR #57 vs. `Vmaxpu = 1.20` PQ)

| Escenario | Tipo | Demanda [kWh] (`1.05` $\to$ `1.20`) | Importación [kWh] (`1.05` $\to$ `1.20`) | Pérd. red [kWh] (`1.05` $\to$ `1.20`) | Pérd. xfmr [kWh] (`1.20`) | Pérd. total [kWh] (`1.05` $\to$ `1.20`) | $\Delta$ Pérd. red vs. base (`1.05` $\to$ `1.20`) | $\Delta$ Pérd. total vs. base (`1.05` $\to$ `1.20`) | $V_{\min}$ / $V_{\max}$ [pu] (`1.20`) | Min $>1{,}05$ / $>1{,}06$ (`1.05` $\to$ `1.20`) |
|:---|:---:|:---:|:---:|:---:|---:|:---:|:---:|:---:|:---:|:---:|
| `base_no_dg` | Base | `517,306` $\to$ `483,914` | `522,368` $\to$ `488,459` | `5,0627` $\to$ `4,5450` | `0,0000` | `5,0627` $\to$ `4,5450` | `0,00 %` $\to$ `0,00 %` | `0,00 %` $\to$ `0,00 %` | `0,98143 / 1,06480` | `415/6` $\to$ `439/6` |
| `pv_near_34_direct` | Solo FV | `517,371` $\to$ `483,914` | `499,460` $\to$ `465,488` | `5,0079` $\to$ `4,4928` | `0,0000` | `5,0079` $\to$ `4,4928` | `-1,08 %` $\to$ **`-1,15 %`** | `-1,08 %` $\to$ **`-1,15 %`** | `0,98160 / 1,06494` | `430/6` $\to$ `458/6` |
| `pv_far_822_direct` | Solo FV | `517,578` $\to$ `483,914` | `499,473` $\to$ `465,302` | `4,8136` $\to$ `4,3074` | `0,0000` | `4,8136` $\to$ `4,3074` | `-4,92 %` $\to$ **`-5,23 %`** | `-4,92 %` $\to$ **`-5,23 %`** | `0,98214 / 1,06572` | `469/7` $\to$ `507/7` |
| `pv_near_34_xfmr_5kva` | Solo FV + Xfmr | `517,369` $\to$ `483,914` | `499,605` $\to$ `465,634` | `5,0085` $\to$ `4,4934` | `0,1454` | `5,1539` $\to$ `4,6389` | `-1,07 %` $\to$ **`-1,13 %`** | `+1,80 %` $\to$ **`+2,07 %`** | `0,98160 / 1,06494` | `430/6` $\to$ `457/6` |
| `pv_far_822_xfmr_5kva` | Solo FV + Xfmr | `517,574` $\to$ `483,914` | `499,619` $\to$ `465,452` | `4,8165` $\to$ `4,3102` | `0,1465` | `4,9631` $\to$ `4,4567` | `-4,86 %` $\to$ **`-5,17 %`** | `-1,97 %` $\to$ **`-1,94 %`** | `0,98213 / 1,06571` | `469/7` $\to$ `506/7` |
| `pv_bess_near_34_xfmr_5kva` | FV+BESS + Xfmr | `517,375` $\to$ `483,914` | `499,937` $\to$ `465,960` | `5,0016` $\to$ `4,4867` | `0,1063` | `5,1079` $\to$ `4,5930` | `-1,21 %` $\to$ **`-1,28 %`** | `+0,89 %` $\to$ **`+1,06 %`** | `0,98158 / 1,06493` | `425/6` $\to$ `454/6` |
| `pv_bess_far_822_xfmr_5kva` | FV+BESS + Xfmr | `517,598` $\to$ `483,914` | `499,947` $\to$ `465,757` | `4,7880` $\to$ `4,2822` | `0,1073` | `4,8954` $\to$ `4,3895` | `-5,43 %` $\to$ **`-5,78 %`** | `-3,30 %` $\to$ **`-3,42 %`** | `0,98206 / 1,06547` | `472/6` $\to$ `503/7` |

*(En todos los escenarios: `minutes_above_1p10_pu = 0` y `minutes_below_0p90_pu = 0`. Inyección FV = `22,9183 kWh/día` en los 4 escenarios solo-FV; inyección neta DER = `22,5458 kWh/día` en los 2 escenarios FV+BESS.)*

### 4.2 Separación de efectos (Solo FV vs. FV+BESS, Directo vs. Transformador) y robustez de conclusiones

1. **Atribución estricta entre FV y BESS (bajo `Vmaxpu = 1.20`):**
   - **Contribución exclusiva de FV (sin BESS):** en barra 822 con transformador, la generación fotovoltaica por sí sola logra el grueso del ahorro en pérdidas del alimentador (`-5,17 %`) y reduce las pérdidas totales en `-1,94 %`.
   - **Contribución incremental del BESS (`pv_bess_*_xfmr_5kva` vs. `pv_*_xfmr_5kva`):** añadir el BESS aporta un ahorro adicional de `-0,61 pp` en pérdidas del alimentador en barra 822 (`-5,17 %` $\to$ `-5,78 %`) y reduce las pérdidas de cobre del transformador de 5 kVA un **`-26,8 %`** (`0,1465` $\to$ `0,1073 kWh`) al recortar el pico solar de `3,0` a `2,0 kW`, elevando el ahorro neto de pérdidas totales de `-1,94 %` a **`-3,42 %`** (`-1,48 pp` atribuibles al BESS). Esta mejora incremental de `1,48 pp` corresponde estrictamente a la comparación bajo los **perfiles sintéticos establecidos** (curva solar semisenoidal y despacho BESS idealizado de balance SoC diario nulo) y **no implica validación experimental del BESS ni de su envejecimiento**. En contrapartida, las pérdidas internas de ciclo del BESS (`0,3724 kWh/día`) incrementan la energía importada neta en `+0,305 kWh/día` respecto a `pv_far_822_xfmr_5kva`.
2. **Conclusiones ROBUSTAS (invariantes frente a `Vmaxpu = 1.05` vs. `1.20`):**
   - **Ubicación más favorable:** la **barra 822 (lejana)** supera consistentemente a la **barra 34 (cercana)** en pérdidas del alimentador, pérdidas totales y mejora de tensión mínima tanto en conexión directa como con transformador 5 kVA, con y sin BESS.
   - **Impacto del transformador de 5 kVA (`P0 = 0`):** en barra 34, las pérdidas del transformador (`0,1454 kWh` solo FV; `0,1063 kWh` FV+BESS) superan el ahorro en el alimentador, invirtiendo el balance total a signo positivo (`+2,07 %` y `+1,06 %` con `1.20`, frente a `+1,80 %` y `+0,89 %` con `1.05`). En barra 822, el balance total permanece negativo (`-1,94 %` solo FV y `-3,42 %` FV+BESS).
   - **Extremos de tensión:** variaciones menores a `0,0005 pu` ($\approx 0,12\text{ V}$).
3. **Conclusiones SENSIBLES al modelo de carga:**
   - **Magnitudes diarias absolutas:** con `Vmaxpu = 1.20`, la demanda diaria cae `-6,46 %` a `-6,51 %`, la importación cae `-6,49 %` a `-6,84 %` y las pérdidas del alimentador caen `-10,23 %` a `-10,56 %`.
   - **Signo de la ventaja en importación de subestación (Barra 822 vs. Barra 34):** en los **tres pares** (directo, transformador solo FV, y FV+BESS con transformador), `Vmaxpu = 1.05` producía una penalización artificial en importación para la barra 822 (`+0,0129`, `+0,0143` y `+0,0102 kWh/día` más que barra 34) por rebote de carga. Con `Vmaxpu = 1.20`, la barra 822 **ahorra importación en los tres pares**: **`-0,1854 kWh/día`** (directo), **`-0,1822 kWh/día`** (solo FV + xfmr) y **`-0,2034 kWh/día`** (FV+BESS + xfmr).

---

## 5. Recomendación Científica, Limitaciones y Reproducibilidad

- **Configuración propuesta como referencia `PQ` de trabajo:** **Proponer `Vmaxpu = 1.20` (potencia constante `PQ` pura) como referencia de trabajo para los 7 escenarios QSTS**, por coherencia con IEEE PES 2015 (PR #58), invarianza de la demanda (`483,914 kWh/día` en los 7 casos) y consistencia física entre ahorro de pérdidas e importación de red en los tres pares de ubicación.
- **Distinción crítica (benchmark vs. cargas físicas reales):** `Vmaxpu = 1.20` **NO constituye una caracterización experimental de consumidores residenciales reales** (cuya demanda real suele exhibir dependencia de tensión tipo ZIP/CVR), sino una **convención de modelado `PQ` puro** coherente con el benchmark IEEE PES 2015. Por ello, **se conservan ambas configuraciones (`Vmaxpu = 1.05` del PR #57 y `Vmaxpu = 1.20`) como sensibilidad metodológica**. Este estudio no modifica automáticamente el dossier ni el documento principal de tesis.
- **Comandos de reproducción (sin dependencias temporales, commit IEEE fijado `5005c668a72d20775f4c2d060feebb2866ba1d38`):**
  ```bash
  python scripts/audit_ieee906_vmaxpu_qsts_sensitivity.py --download
  python scripts/run_ieee906_qsts_24h_vmaxpu1p20.py
  python scripts/run_ieee906_qsts_24h_pv_only_vmaxpu1p20.py
  ```
- **Dependencias verificadas:** `Python 3.11.2`, `numpy==2.4.6`, `opendssdirect.py==0.9.4`, `dss-python==0.15.7`, `dss-python-backend==0.14.5`.
- **Trazabilidad SHA-256 de artefactos:**
  - [`vmaxpu_qsts_representative_summary.json`](../outputs/experiment_vmaxpu_qsts_sensitivity/vmaxpu_qsts_representative_summary.json): `2ee5fff8dad1f5de55407cfb3c6fdf0c2e9ec20af5caaa28345e948538ebffc5`
  - [`vmaxpu_qsts_representative_instants.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/vmaxpu_qsts_representative_instants.csv): `2efb68d28b3cb40b0723963d72be3f1e12bf38f22ae3f01eb2460e014ab524eb`
  - [`qsts_24h_vmaxpu1p20_vs_pr57.json`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_vs_pr57.json): `4166146b988aa4e9f01689e1311ad2acc3f02526e1f5c524a00cb8d5ab3f4793`
  - [`qsts_24h_vmaxpu1p20_comparison.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_comparison.csv): `c1b45d9543f49778dc2264e713fb420a9fa492906ca9d2969b6ee2672e52b425`
  - [`qsts_24h_vmaxpu1p20_all7_comparison.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_vmaxpu1p20_all7_comparison.csv): `ad774a11b1087e97da50d6968ec73cf893674d866aec908b15a9dc503ea3decd`
  - [`qsts_24h_all7_paired_1p05_vs_1p20.csv`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_all7_paired_1p05_vs_1p20.csv): `c89f90386f27e0d2d9d81c0ab0eab0a0c986a83e81799979458a507ea5c74d99`
  - [`qsts_24h_all7_vmaxpu1p20_vs_pr57.json`](../outputs/experiment_vmaxpu_qsts_sensitivity/qsts_24h_all7_vmaxpu1p20_vs_pr57.json): `dcbd4a021c7e3401c32448b6a10c71ed6ba9c7bfcdc3857f8b7d38651b3d224d`
