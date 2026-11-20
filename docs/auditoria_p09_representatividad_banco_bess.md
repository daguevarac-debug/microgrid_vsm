# Auditoría técnica de P-09 — Representatividad física del banco BESS (`48×2s2p`)

- **Repositorio:** `daguevarac-debug/microgrid_vsm`
- **Rama experimental:** `experiment/audit-p05-p09` (derivada de `e5a9360ed38344eff125317a4afe14c92a338480`, PR #60)
- **Script reproducible:** [`scripts/audit_p09_bess_bank_scaling.py`](../scripts/audit_p09_bess_bank_scaling.py)
- **Evidencia JSON:** [`outputs/audit_p05_p09/p09_bess_scaling_audit.json`](../outputs/audit_p05_p09/p09_bess_scaling_audit.json)
- **Módulos auditados (sin modificaciones):** [`src/microgrid_bess_dcdc.py`](../src/microgrid_bess_dcdc.py), [`src/bess/dc_dc_adapter.py`](../src/bess/dc_dc_adapter.py), [`src/bess/model.py`](../src/bess/model.py), [`src/config.py`](../src/config.py)

---

## 1. Dictamen científico consolidado de P-09

| Nivel de verificación | Dictamen | Alcance exacto |
| --- | :---: | --- |
| **Consistencia dimensional y escalamiento homogéneo (`MicrogridWithBESSDCDC`, `48×2s2p` + DC/DC)** | **`PASS_DIMENSIONAL`** *(exclusivamente modelo homogéneo equivalente)* | Todas las leyes de escala serie-paralelo (tensión, capacidad, corriente, potencia, $R_0$, $R_1$, $C_1$, constante de tiempo $\tau_{rc}$, energía y balance de potencia DC/DC) son algebraica y dimensionalmente consistentes sin errores de escala (`error de balance ≤ 4.55×10⁻¹³ W`, $\Delta\tau_{rc} = 0.0\text{ s}$). **No declara validada experimentalmente la configuración física ni sus protecciones.** |
| **Arquitectura heredada sin DC/DC (`MicrogridWithBESSPI`, unidad `2p` directa)** | **`REVIEW`** | Mantiene la relación no física `Vdc / V_unit ≈ 89.70` (`340 V / 3.79 V`); debe preservarse únicamente como arquitectura histórica de regresión y no como banco físico a escala de bus DC. |
| **Representatividad de un banco real de segunda vida (heterogeneidad, térmica, barras, protecciones y BMS)** | **`REVIEW` / Requiere validación experimental** | El modelo `48×2s2p` es un **equivalente homogéneo balanceado**. No captura dispersión de `SoH`, $R_0$, temperatura ni desbalance de tensión $\Delta V$ entre módulos en serie, donde la unidad más débil limita toda la cadena (`10.20 %` a `25.17 %` de pérdida de capacidad utilizable), ni valida experimentalmente la configuración física ni sus protecciones. |

---

## 2. Ecuaciones de escalamiento serie-paralelo (`1s1p` → `2p` → `2s2p` → `48×2s2p`)

En [`src/microgrid_bess_dcdc.py`](../src/microgrid_bess_dcdc.py) y [`src/bess/dc_dc_adapter.py`](../src/bess/dc_dc_adapter.py), la unidad de referencia integrada en el vector de estados (`soc_bess`, `vrc_bess`, `zdeg_bess`) es la **pareja en paralelo `2p`** de Nissan Leaf (`q_nom_ref_ah = 66.0 Ah`, `q_init_case_ah = 44.1 Ah`, `SoH_0 = 44.1 / 66.0 = 0.668182`, `v_nom = 3.75 V`, Braco et al. 2020/2023).

El banco completo `BAT26-53` conecta **48 módulos `2s2p` en serie**, lo que equivale a $N_s = 48 \times 2 = 96$ unidades `2p` en serie y $N_p = 1$ cadena en paralelo ($96\text{s} \times 1\text{p}$ de parejas `2p`, o $96\text{s}2\text{p}$ de celdas pouch individuales `1s1p`). Bajo el supuesto **homogéneo balanceado** (todas las unidades idénticas, sin impedancia de barras, fusibles ni contactores), las transformaciones exactas respecto a la unidad `2p` son:

$$V_{\mathrm{bank}} = N_s V_{\mathrm{unit}}, \qquad I_{\mathrm{bank}} = N_p I_{\mathrm{unit}}, \qquad Q_{\mathrm{bank}} = N_p Q_{\mathrm{unit}}$$

$$P_{\mathrm{bank}} = V_{\mathrm{bank}} I_{\mathrm{bank}} = N_s N_p V_{\mathrm{unit}} I_{\mathrm{unit}}, \qquad E_{\mathrm{bank}} = N_s N_p E_{\mathrm{unit}}$$

$$R_{0,\mathrm{bank}} = \frac{N_s}{N_p} R_{0,\mathrm{unit}}, \qquad R_{1,\mathrm{bank}} = \frac{N_s}{N_p} R_{1,\mathrm{unit}}, \qquad C_{1,\mathrm{bank}} = \frac{N_p}{N_s} C_{1,\mathrm{unit}}$$

$$\tau_{rc,\mathrm{bank}} = R_{1,\mathrm{bank}} C_{1,\mathrm{bank}} = \left(\frac{N_s}{N_p} R_{1,\mathrm{unit}}\right)\left(\frac{N_p}{N_s} C_{1,\mathrm{unit}}\right) = R_{1,\mathrm{unit}} C_{1,\mathrm{unit}} = \tau_{rc,\mathrm{unit}}$$

La invarianza de $\tau_{rc}$ garantiza que la dinámica interna de polarización 1RC (`dV_rc/dt = -V_rc/(R1*C1) + i_unit/C1`) puede integrarse exactamente a escala de unidad `2p` siempre que $i_{\mathrm{unit}} = I_{\mathrm{bank}} / N_p$ y $V_{\mathrm{bank}} = N_s V_{\mathrm{unit}}$ se acoplen coherentemente en potencia a través del convertidor DC/DC bidireccional:

$$P_{\mathrm{bus}} = \begin{cases} \eta_{\mathrm{dis}} P_{\mathrm{bank}}, & P_{\mathrm{bus}} \ge 0 \text{ (descarga)} \\ P_{\mathrm{bank}} / \eta_{\mathrm{ch}}, & P_{\mathrm{bus}} < 0 \text{ (carga)} \end{cases}, \qquad i_{\mathrm{bus}} = \frac{P_{\mathrm{bus}}}{V_{\mathrm{dc}}}, \qquad P_{\mathrm{loss}} = P_{\mathrm{bank}} - P_{\mathrm{bus}} \ge 0$$

---

## 3. Verificación dimensional por nivel jerárquico (`SoC = 0.60`, `SoH = 0.6682`)

Los valores siguientes provienen de [`outputs/audit_p05_p09/p09_bess_scaling_audit.json`](../outputs/audit_p05_p09/p09_bess_scaling_audit.json), evaluados con la caracterización cargada por `_build_bess_for_soh` (`OCV_SOC.xlsx`, `R0_nom = 0.970 mΩ`, `k_R = 1.0`, `eta = 0.95`):

| Magnitud | Celda pouch (`1s1p`) | Pareja ref. (`2p`, `1s2p`) | Módulo Leaf (`2s2p`) | Banco `48×2s2p` (`96s×1p` de `2p`) | Regla de escala respecto a `2p` |
| --- | :---: | :---: | :---: | :---: | --- |
| Tensión nominal $V_{\mathrm{nom}}$ [V] | `3.75` | `3.75` | `7.50` | **`360.00`** | $\times N_s$ (`×96`) |
| Envolvente absoluta $V_{\min}$ / $V_{\max}$ [V] | `2.50` / `4.20` | `2.50` / `4.20` | `5.00` / `8.40` | **`240.00` / `403.20`** | $\times N_s$ (`×96`) |
| Capacidad nominal $Q_{\mathrm{nom}}$ [Ah] | `33.00` | `66.00` | `66.00` | **`66.00`** | $\times N_p$ (`×1`) |
| Capacidad caso $Q_{\mathrm{case}}$ (`SoH=0.6682`) [Ah] | `22.05` | `44.10` | `44.10` | **`44.10`** | $\times N_p$ (`×1`) |
| Corriente máx. nominal / disponible 1C [A] | `33.00` / `22.05` | `66.00` / `44.10` | `66.00` / `44.10` | **`66.00` / `44.10`** | $\times N_p$ (`×1`) |
| Resistencia $R_{0,\mathrm{nom}}$ [mΩ] | `1.940` | `0.970` | `1.940` | **`93.120`** | $\times N_s / N_p$ (`×96`) |
| Resistencia $R_{0,\mathrm{case}}$ (`SoH=0.6682`) [mΩ] | `2.584` | `1.292` | `2.584` | **`124.019`** | $\times N_s / N_p$ (`×96`) |
| Resistencia polarización $R_1$ (`SoC=0.60`) [mΩ] | `6.539` | `3.270` | `6.539` | **`313.892`** | $\times N_s / N_p$ (`×96`) |
| Capacitancia polarización $C_1$ (`SoC=0.60`) [F] | `5502.05` | `11004.10` | `5502.05` | **`114.626`** | $\times N_p / N_s$ (`÷96`) |
| Constante de tiempo $\tau_{rc} = R_1 C_1$ [s] | **`35.9801`** | **`35.9801`** | **`35.9801`** | **`35.9801`** | **Invariante** ($\Delta = 0.0\text{ s}$) |
| Energía nominal / caso (`3.75 V`) [kWh] | `0.1237` / `0.0827` | `0.2475` / `0.1654` | `0.4950` / `0.3307` | **`23.760` / `15.876`** | $\times N_s N_p$ (`×96`) |
| Energía útil en `SoC ∈ [0.10, 0.90]` [kWh] | `0.0662` | `0.1323` | `0.2646` | **`12.701`** | $\times 0.80 \cdot N_s N_p$ |
| Potencia 1C nominal / disponible [kW] | `0.1237` / `0.0827` | `0.2475` / `0.1654` | `0.4950` / `0.3307` | **`23.760` / `15.876`** | $\times N_s N_p$ (`×96`) |

### Verificación de envolvente de tensión y acoplamiento DC/DC (`Vdc_ref = 340.0 V`)

| `SoC` | `OCV_unit` [V] | `V_bank_OC` [V] | `V_bank_OC / Vdc_ref` | Modo DC/DC en descarga | Límite descarga bus [W] | Límite carga bus [W] | `I_bank` a `3 kW` [A] | `I_bus` a `3 kW` [A] | Pérdida DC/DC [W] |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `0.10` | `3.33765` | **`320.41`** | `0.9424` | *Boost* (elevador) | `0.00` (bloqueo `SoC_min`) | `-15127.86` | `0.000` | `0.000` | `0.00` |
| `0.20` | `3.55441` | `341.22` | `1.0036` | *Buck* (reductor) | `14066.42` | `-16093.83` | `9.286` | `8.824` | `157.89` |
| `0.50` | `3.74397` | `359.42` | `1.0571` | *Buck* (reductor) | `14828.81` | `-16938.59` | `8.813` | `8.824` | `157.89` |
| `0.60` | `3.79033` | `363.87` | `1.0702` | *Buck* (reductor) | `15015.27` | `-17145.20` | `8.704` | `8.824` | `157.89` |
| `0.90` | `3.93489` | **`377.75`** | `1.1110` | *Buck* (reductor) | `15596.68` | `0.00` (bloqueo `SoC_max`) | `8.383` | `8.824` | `157.89` |

**Observaciones clave de la auditoría dimensional:**

1. **Sin errores de escala en `MicrogridWithBESSDCDC`:** La relación de tensión respecto al bus DC pasa de `89.702` (en `MicrogridWithBESSPI`) a **`0.9344`** (`340 V / 363.87 V` en `SoC = 0.60`), con error de balance de potencia `≤ 4.55×10⁻¹³ W`.
2. **Necesidad física de etapa *buck-boost*:** La tensión en circuito abierto del banco (`320.41 V` a `377.75 V`) cruza `Vdc_ref = 340.0 V` cerca de `SoC ≈ 0.19`. Por tanto, un convertidor puramente reductor o puramente elevador no cubriría la ventana `[0.10, 0.90]`; se requiere un DC/DC bidireccional **buck-boost** (coherente con el contrato algebraico de `convert_power`).
3. **Coherencia de límites físicos:** En `SoC = 0.60`, la potencia disponible 1C en el lado bus (`15 244 W` en circuito abierto; `15 015 W` con caída $R_0$) y el límite heredado por corriente de bus (`340 V × 44.1 A = 14 994 W`) quedan correctamente intersectados por debajo del tope nominal configurado (`22 440 W`), sin violar la restricción 1C del banco ni la capacidad de la etapa de potencia.

---

## 4. Diferencia crítica: modelo equivalente homogéneo vs. banco real de segunda vida

Aunque el modelo `48×2s2p` obtiene **`PASS_DIMENSIONAL`** como representación paramétrica homogénea, **no equivale a un banco físico real de segunda vida** por cinco mecanismos documentados en la literatura experimental:

1. **Efecto del eslabón más débil en cadenas en serie ($96\text{s} \times 1\text{p}$):** Como todas las 96 unidades `2p` comparten la misma corriente $I_{\mathrm{bank}}$, el primer módulo en alcanzar `V_min` o `V_max` detiene toda la cadena. Sin balanceo activo ni derivación modular, una sola unidad `2p` más degradada impone una reducción directa de capacidad utilizable:

   | `SoH` de la unidad `2p` más débil (media del banco `0.6682`) | Capacidad utilizable de la cadena [Ah] | Energía nominal efectiva [kWh] | Pérdida de capacidad respecto al modelo homogéneo [%] |
   | :---: | :---: | :---: | :---: |
   | `0.6682` (homogéneo) | `44.10` | `15.876` | `0.00 %` |
   | `0.6000` | `39.60` | `14.256` | **`−10.20 %`** |
   | `0.5500` | `36.30` | `13.068` | **`−17.69 %`** |
   | `0.5000` | `33.00` | `11.880` | **`−25.17 %`** |

2. **Dispersión real de `SoH` y desbalance $\Delta V$ en Nissan Leaf Gen 1:** Gao et al. (2024, *eTransportation*, `10.1016/j.etran.2024.100313`) midieron >100 packs Leaf Gen 1 retirados con `SoH` en **60–67 %** y establecieron umbrales empíricos de desbalance de tensión entre celdas (`ΔV < 50 mV` balance aceptable; `ΔV > 100 mV` desbalance severo o falla incipiente). Braco et al. (2021, *IEEE Trans. Ind. Appl.*, `10.1109/TIA.2021.3075180`) confirmaron además fuerte dispersión estadística entre módulos retirados de distintos vehículos.
3. **Heterogeneidad entre módulos en modelos ECM:** Salek et al. (2022, *Mathematics*, `10.3390/math10203843`) modelaron packs SLB con módulos homogéneos frente a heterogéneos (`75 % / 80 % / 85 % SoH`) mediante ECM validado en laboratorio, demostrando redistribución desigual de corriente, `SoC` y velocidad de degradación respecto al equivalente homogéneo. Cui et al. (2024, *Cell Reports Physical Science*, `10.1016/j.xcrp.2024.101941`) observaron trayectorias de degradación divergentes incluso entre celdas sometidas al mismo perfil estacionario.
4. **Resistencia parásita de interconexión y degradación no lineal:** El valor escalado `R0_case = 124.02 mΩ` suma únicamente las 96 unidades `2p` ideales y omite resistencia de barras, fusibles, contactores y uniones atornilladas (típicamente `+15–30 mΩ` adicionales en packs automotrices de ~360–400 V), además de no modelar la rodilla de envejecimiento (*aging knee*, Braco 2020/2021).
5. **Acoplamiento térmico y dinámica del convertidor DC/DC:** El modelo opera isotérmicamente (sin gradiente térmico entre centro y extremos del pack) y representa el convertidor DC/DC con eficiencia constante (`0.95`) y relación algebraica instantánea, sin inductancia/capacitancia de filtro ni dinámica de conmutación o lazo interno de corriente.

---

## 5. Qué queda pendiente para cerrar P-09 de forma defendible ante el director

- **Lo que ya queda cerrado en el Objetivo 2 (`PASS_DIMENSIONAL`):** Queda demostrado que [`MicrogridWithBESSDCDC`](../src/microgrid_bess_dcdc.py) (`48×2s2p` + DC/DC algebraico) **no presenta errores de escala** y cierra la brecha dimensional de tensión (`89.70 → 0.9344`) que mantenía `MicrogridWithBESSPI`.
- **Lo que permanece abierto (`REVIEW` / requiere datos y validación experimental):**
  1. **Aceptación académica de alcance:** Confirmar con el director que el modelo `48×2s2p` se presenta explícitamente en la tesis como **modelo equivalente homogéneo balanceado a nivel de sistema**, dejando fuera del Objetivo 2 la heterogeneidad celda-a-celda y el modelo térmico.
  2. **Si se desea modelar heterogeneidad (trabajo futuro / Obj. 3):** Incorporar una representación multi-módulo o de eslabón más débil (distribución de `SoH_i`, $R_{0,i}$ y umbral $\Delta V_{\max}$), resistencia parásita de barras y validación experimental sobre un banco o módulo instrumentado (enlazado con `P-10`, `BLOCKED_DATOS`).
