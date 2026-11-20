# Auditoría técnica de P-05 — Estabilidad de pequeña señal del VSG de 16 estados

- **Repositorio:** `daguevarac-debug/microgrid_vsm`
- **Rama experimental:** `experiment/audit-p05-p09` (derivada de `e5a9360ed38344eff125317a4afe14c92a338480`, PR #60)
- **Script reproducible:** [`scripts/audit_p05_frozen_slow_stability.py`](../scripts/audit_p05_frozen_slow_stability.py)
- **Evidencia JSON:** [`outputs/audit_p05_p09/p05_stability_audit.json`](../outputs/audit_p05_p09/p05_stability_audit.json)
- **Evidencia histórica auditada (sin modificar):** [`outputs/validation/objective2_vsg_tuning/small_signal_summary.json`](../outputs/validation/objective2_vsg_tuning/small_signal_summary.json), [`src/validation/validate_objective2_small_signal_stability.py`](../src/validation/validate_objective2_small_signal_stability.py)

---

## 1. Dictamen científico consolidado de P-05

| Subsistema / Nivel de análisis | Dictamen | Alcance y límites exactos |
| --- | :---: | --- |
| **Subsistema rápido + control reducido (13 estados congelando batería: `Vdc`, `i1_abc`, `vc_abc`, `i2_abc`, `omega`, `theta`, `xi_bess_vdc`)** | **`PASS_MATEMATICO` *(parcial — estabilidad local reducida)*** | Los 12 modos no neutros son localmente exponencialmente estables ($\lvert\mu_k\rvert < 1$, $\operatorname{Re}\lambda_k < 0$) en `MicrogridWithBESSPI` (60 Hz, $\zeta_{\min} = 0.5808 > 0.10$) y `MicrogridWithBESSDCDC` (50 Hz, $\zeta_{\min} = 0.9129 > 0.10$). **Limitación numérica explícita:** a `settling_s = 1.0 s`, `xi_bess_vdc` ($\tau_{\mathrm{PI}} = 17.5\text{ s}$) conserva residuo de periodicidad de `0.00769` (60 Hz) y `0.00903` (50 Hz) (`> 0.005`), por lo que la linealización se evalúa sobre una trayectoria cuasiestacionaria local y no sobre un ciclo límite exacto. |
| **Dinámica lenta de polarización 1RC (`vrc_bess`)** | **`PASS_MATEMATICO` *(ISS escalar)*** | Ecuación lineal desacoplada con polo analítico exacto $\lambda_{rc} = -1/(R_1 C_1) = -0.02779\text{ s}^{-1} < 0$ ($\tau_{rc} = 35.98\text{ s}$): estabilidad entrada-estado (ISS) garantizada. |
| **Dinámica lenta de acumulación (`soc_bess`, `zdeg_bess`)** | **Sin equilibrio asintótico (integradores acotados por supervisión)** | Son integradores puros ($\lambda = 0$) sin órbita periódica cuando $i_{\mathrm{bess}} \neq 0$; su acotamiento depende de la supervisión operativa (`SoC ∈ [0.10, 0.90]`, `SoH ≥ 0.50`), no de estabilidad asintótica de Floquet. |
| **Sistema completo acoplado de 16 estados** | **`REVIEW` *(limitación metodológica y de alcance)*** | El cierre matemático obtenido es **parcial** (estabilidad local reducida en horizonte finito). No queda demostrada estabilidad asintótica global del sistema completo de 16 estados ni estabilidad en gran señal bajo saturación de `m_ctrl`, límites `SoC` o anti-windup, ni existe validación experimental/HIL. |

---

## 2. Partición exacta de estados (16 → 13) y diagnóstico del Floquet histórico

### Partición exacta del vector de estados (`AGENTS.md`)

- **13 estados conservados (`active_indices = [0..11, 15]`):** tensión de bus DC `Vdc` (`x[0]`), corrientes y tensiones trifásicas del filtro LCL `i1_a..c`, `vc_a..c`, `i2_a..c` (`x[1..9]`), frecuencia y ángulo VSG `omega`, `theta` (`x[10..11]`), e integrador PI del bus DC `xi_bess_vdc` (`x[15]`). Se conservan porque gobiernan la respuesta electromecánica y de regulación del bus DC en escalas de $1\text{ ms}$ a $17.5\text{ s}$.
- **3 estados congelados como parámetros cuasiestáticos (`frozen_indices = [12, 13, 14]`):** `soc_bess` (`x[12]`, $\tau_{\mathrm{SoC}} \approx 1.87\times 10^5\text{ s}$), `vrc_bess` (`x[13]`, $\tau_{rc} = 35.98\text{ s}$, analizable analíticamente como ISS escalar) y `zdeg_bess` (`x[14]`, integrador monótono no decreciente $\dot{z}_{\mathrm{deg}} = \lvert i_{\mathrm{bess}}\rvert / 3600 \ge 0$).

### Causas metodológicas del `REVIEW` histórico en 16 estados

En [`outputs/validation/objective2_vsg_tuning/small_signal_summary.json`](../outputs/validation/objective2_vsg_tuning/small_signal_summary.json), el modelo formal de 12 estados (sin BESS) obtuvo `PASS`, mientras que el caso diagnóstico de 16 estados (`MicrogridWithBESSPI`, `M = 80`, `D = 1500`, `Kp = 170 W/V`, `Ki = 10 W/(V·s)`, `f = 60 Hz`, $T = 1/60\text{ s}$) quedó en `REVIEW` por tres causas verificadas en [`src/validation/validate_objective2_small_signal_stability.py`](../src/validation/validate_objective2_small_signal_stability.py):

1. **Ausencia estructural de órbita periódica en `soc_bess` y `zdeg_bess`:**
   $$\frac{d\mathrm{SoC}}{dt} = -\frac{i_{\mathrm{bess}}}{3600\,Q_{\mathrm{eff}}}, \qquad \frac{dz_{\mathrm{deg}}}{dt} = \frac{\lvert i_{\mathrm{bess}}\rvert}{3600} \ge 0$$
   Siempre que $i_{\mathrm{bess}} \neq 0$, $z_{\mathrm{deg}}(t)$ es estrictamente creciente y $\mathrm{SoC}(t)$ presenta deriva neta; por definición, no existe órbita periódica $x(T) = x(0)$ en $\mathbb{R}^{16}$. En `MicrogridWithBESSPI` la corriente $i_{\mathrm{bess}} = P_{\mathrm{bess}}/V_{\mathrm{dc}}$ no depende de $\mathrm{SoC}$ ni de $z_{\mathrm{deg}}$ en zona lineal, por lo que sus autovalores exactos son $\lambda = 0$ ($\mu = 1$); los valores $+1.47\times 10^{-12}\text{ s}^{-1}$ y $+1.73\times 10^{-9}\text{ s}^{-1}$ son redondeo numérico de diferencias finitas.
2. **Falsa clasificación del modo integrador PI (`mode 12`, `xi_bess_vdc`) como `neutral_phase_mode`:**
   En `small_signal_summary.json`, el modo 12 tiene $\lambda_{12} = -0.05718\text{ s}^{-1}$ ($\tau_{\mathrm{PI}} = 17.49\text{ s}$, estrictamente estable), pero en $T = 16.67\text{ ms}$ su multiplicador es $\mu_{12} = e^{-0.05718 / 60} = 0.999047$. Como $\lvert\mu_{12} - 1\rvert = 0.000953 \le \text{NEUTRAL\_TOL} = 0.005$ y `theta` apareció en tercer lugar en `_dominant_states` (`["xi_bess_vdc", "Vdc", "theta"]`), la regla de las [líneas 321–323](../src/validation/validate_objective2_small_signal_stability.py#L321-L323) lo excluyó erróneamente como modo neutro de fase.
3. **Falso `near_unit_circle_review` en la polarización 1RC (`mode 13`, `vrc_bess`):**
   El modo 13 tiene $\lambda_{13} = -0.02779\text{ s}^{-1}$, coincidente con $-1/(R_1 C_1) = -0.027793\text{ s}^{-1}$, y $\mu_{13} = 0.999537 < 1$ cae dentro de `UNIT_CIRCLE_TOL = 0.005` únicamente por la disparidad entre $T = 16.67\text{ ms}$ y $\tau_{rc} = 35.98\text{ s}$.

---

## 3. Verificación de hipótesis matemáticas (perturbación singular, periodicidad y modo angular)

Evaluando las alternativas metodológicas:

| Enfoque evaluado | Aplicabilidad al modelo `abc` de 16 estados | Justificación matemática |
| --- | :---: | --- |
| **Jacobiano instantáneo del RHS en marco `abc`** | **No válido** | $(i_{1,abc}, v_{c,abc}, i_{2,abc})$ son periódicas en el tiempo; los autovalores congelados de $J(x(t))$ no determinan estabilidad de Floquet. |
| **Linealización en equilibrio en marco síncrono `dq`** | **Válido, pero exige reformular la planta** | Exigiría reescribir el modelo `abc` protegido (Matas-Díaz et al., 2025, `10.35833/MPCE.2024.000316`) y seguiría requiriendo congelar `soc_bess` y `zdeg_bess`. |
| **Floquet directo en 16 estados sobre $T$** | **Mal condicionado para estados lentos** | Viola la existencia de órbita periódica por deriva de `soc_bess`/`zdeg_bess` y comprime polos lentos estables en $\mu \in (0.9988, 1)$. |
| **Perturbación singular: Floquet en 13 estados (batería congelada) + análisis lento separado** | **Riguroso para estabilidad local reducida (adoptado)** | Separa la capa límite rápida+control (13 estados) de la dinámica lenta de batería sin modificar ecuaciones protegidas (Khalil, 2002; Ma et al., 2024, `10.1109/TSG.2024.3357481`). |

### Comprobación explícita de las hipótesis de Tikhonov

1. **Separación de escalas ($\varepsilon \ll 1$) — Satisfecha:**
   - LCL + bus DC: $\tau_{\mathrm{elec}} \in [1.04, 14.7]\text{ ms}$; VSG `omega`: $\tau_{\mathrm{VSG}} = M/D = 53.33\text{ ms}$; PI `xi_bess_vdc`: $\tau_{\mathrm{PI}} = 17.49\text{ s}$.
   - Polarización 1RC: $\tau_{rc} = 35.98\text{ s}$ ($\varepsilon_{\mathrm{VSG}/rc} = 1.48\times 10^{-3} \ll 1$).
   - Acumulación `soc_bess`: $\tau_{\mathrm{SoC}} \approx 1.87\times 10^5\text{ s}$ ($\varepsilon_{\mathrm{VSG}/\mathrm{SoC}} = 2.85\times 10^{-7} \ll 1$).
2. **Estabilidad exponencial uniforme de la capa límite (13 estados) — Satisfecha localmente:**
   Los 12 modos no neutros tienen $\operatorname{Re}\lambda_k \le -0.05717\text{ s}^{-1} < 0$ y $\lvert\mu_k\rvert \le 0.999048 < 1$.
3. **Hipótesis NO satisfechas estrictamente (justifican conservar `PASS` parcial y `REVIEW` en el sistema completo):**
   - **Periodicidad de la órbita base a `t = 1.0 s`:** Como $\tau_{\mathrm{PI}} = 17.5\text{ s} \gg 1.0\text{ s}$, `xi_bess_vdc` aún evoluciona lentamente durante el mapa de un periodo, produciendo `max_abs_scaled_residual = 0.00769` (60 Hz) y `0.00903` (50 Hz), por encima de `0.005` (aunque `vdc_relative_error ≤ 1.43e-4` y `theta_increment_error ≤ 7.41e-4 rad`).
   - **Sistema lento completo:** Tikhonov exige estabilidad asintótica del sistema lento para concluir estabilidad en $t \in [0, \infty)$; aquí `soc_bess` y `zdeg_bess` son integradores puros sin equilibrio asintótico, por lo que la conclusión matemática aplica en **horizontes finitos dentro de la ventana supervisada** (`SoC ∈ [0.10, 0.90]`).
   - **Modo angular neutro (`theta`):** El multiplicador $\mu_{13} = 1 + 4.42\times 10^{-7}$ (60 Hz) / $1 + 2.48\times 10^{-7}$ (50 Hz) corresponde a la invarianza rotacional $SO(2)$ de fase $\theta \mapsto \theta + \delta\theta$; el excedente de $\sim 10^{-7}$ sobre $1$ es consistente con el residuo finito de asentamiento y la discretización por diferencias centrales.

---

## 4. Resultados de la prueba numérica reproducible (13 estados congelados)

Ejecutado mediante [`scripts/audit_p05_frozen_slow_stability.py`](../scripts/audit_p05_frozen_slow_stability.py) (`M = 80`, `D = 1500`, `Kp = 170 W/V`, `Ki = 10 W/(V·s)`, `RK45`, `max_step = 50 µs`, `rtol = 1e-6`, `atol = 1e-8`, sensibilidad `1e-6` vs. `2e-6`, vectores propios normalizados por escala física):

| Subsistema / Modo | `MicrogridWithBESSPI` (60 Hz, $T=16.67\text{ ms}$) | `MicrogridWithBESSDCDC` (50 Hz, $T=20.0\text{ ms}$) | Interpretación física |
| --- | --- | --- | --- |
| **Eléctrico LCL rápido (modos 1–3)** | $\lambda \in [-957.2, -931.3]\text{ s}^{-1}$, $\lvert\mu\rvert \approx 10^{-7}$ | $\lambda < -900\text{ s}^{-1}$, $\lvert\mu\rvert \approx 10^{-8}$ | Amortiguamiento rápido de filtro LCL (estable) |
| **Bus DC + proporcional PI (modo 4)** | $\lambda = -253.73\text{ s}^{-1}$, $\lvert\mu\rvert = 0.01457$ | $\lambda < -200\text{ s}^{-1}$, $\lvert\mu\rvert < 0.02$ | Más amortiguado que 12 estados (`-70.16 s⁻¹`) por acción $K_p$ del PI |
| **Modos oscilatorios LCL (modos 5–10)** | $-67.88 \pm j95.13\text{ rad/s}$, **$\zeta_{\min} = 0.5808$** | **$\zeta_{\min} = 0.9129$** | Estrictamente estables y muy por encima de $\zeta_{\min} = 0.10$ |
| **Control VSG `omega` (modo 11)** | $\lambda = \mathbf{-18.752\text{ s}^{-1}}$ ($\lvert\mu\rvert = 0.7316$) | $\lambda = \mathbf{-18.753\text{ s}^{-1}}$ ($\lvert\mu\rvert = 0.6873$) | Coincidencia exacta con $-D/M = -18.75\text{ s}^{-1}$ |
| **Control PI `xi_bess_vdc` (modo 12)** | $\lambda = \mathbf{-0.05717\text{ s}^{-1}}$ ($\lvert\mu\rvert = 0.999048$) | $\lambda = \mathbf{-0.05720\text{ s}^{-1}}$ ($\lvert\mu\rvert = 0.998857$) | **Estrictamente estable** ($\tau_{\mathrm{PI}} = 17.5\text{ s}$, sensibilidad $\Delta\mu < 7\times 10^{-10}$) |
| **Simetría de fase `theta` (modo 13)** | $\mu = 1 + 4.42\times 10^{-7}$ ($\lambda = +2.65\times 10^{-5}\text{ s}^{-1}$) | $\mu = 1 + 2.48\times 10^{-7}$ ($\lambda = +1.24\times 10^{-5}\text{ s}^{-1}$) | Invarianza rotacional $SO(2)$ del sistema aislado |
| **Polarización 1RC `vrc_bess` (analítico)** | $\lambda_{rc} = -0.02779\text{ s}^{-1}$ ($\tau_{rc} = 35.98\text{ s}$) | $\lambda_{rc} = -0.02779\text{ s}^{-1}$ ($\tau_{rc} = 35.98\text{ s}$) | Estrictamente estable (ISS) |

---

## 5. Conclusión y requisitos para cierre definitivo de P-05 ante el director

1. **Alcance demostrado (`PASS_MATEMATICO` parcial):** Se descarta inestabilidad local de pequeña señal en el subsistema reducido de 13 estados (eléctrico LCL + `Vdc` + VSG `omega` + integrador PI `xi_bess_vdc`) y en la polarización 1RC (`vrc_bess`) bajo parámetros lentos de batería congelados.
2. **Limitaciones explícitas del sistema completo (`REVIEW`):**
   - La órbita base a `t = 1.0 s` conserva un residuo de periodicidad de `0.0077–0.0090` por el asentamiento lento de `xi_bess_vdc` ($\tau_{\mathrm{PI}} = 17.5\text{ s}$); un cierre numérico estricto de ciclo límite requeriría mayor tiempo de asentamiento ($t \gtrsim 5\tau_{\mathrm{PI}}$) o un solver de disparo periódico (*periodic shooting*) sobre los 13 estados.
   - Los estados `soc_bess` y `zdeg_bess` no son asintóticamente estables, sino integradores acotados por supervisión.
   - Esta auditoría no sustituye una prueba global en gran señal (Lyapunov bajo saturación de `m_ctrl`, límites `SoC` o anti-windup) ni validación experimental/HIL.

### Fuentes científicas de respaldo metodológico

- **Khalil, H. K. (2002).** *Nonlinear Systems* (3rd ed.), Prentice Hall, Cap. 11 (*Singular Perturbations*, Teorema de Tikhonov).
- **Ma, Z., Wang, Z., Yuan, Y., & Hong, T. (2024).** *Singular Perturbation-Based Large-Signal Order Reduction of Microgrids for Stability and Accuracy Synthesis With Control*. *IEEE Transactions on Smart Grid*, DOI: `10.1109/TSG.2024.3357481`.
- **Matas-Díaz, F. J., Barragán-Villarejo, M., & Maza-Ortega, J. M. (2025).** *A Systematic Small-Signal Analysis Procedure for Improving Synchronization Stability of Grid-Forming Virtual Synchronous Generators*. *J. Mod. Power Syst. Clean Energy*, 13(1), 102–114, DOI: `10.35833/MPCE.2024.000316`.
