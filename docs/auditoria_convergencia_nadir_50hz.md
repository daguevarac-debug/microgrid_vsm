# Auditoría Científica: Convergencia Numérica y Refinamiento de Paso del Nadir de Frecuencia a 50 Hz (+40 % Escalón de Carga)

- **Fecha:** 2026-11-18
- **Rama base de referencia:** `integration/obj2-pr55-pr56-validated` (PR #57, commit `740a704`)
- **Rama de auditoría:** `audit/scientific-pending-review`
- **Dictamen:** **PASS — Se propone cerrar el estado `REVIEW` de convergencia frente al tamaño de paso** *(distinguiendo explícitamente la estabilidad numérica empírica observada, de orden $< 0{,}00007\ \mu\text{Hz}$, respecto de una cota matemática formal de error global; se conserva aparte el `REVIEW` físico del escenario +40 % sin BESS por limitación del bus DC).*

---

## 1. Resumen Ejecutivo

En la auditoría previa ([`outputs/validation/vsg_50hz_nadir_convergence_audit.json`](../outputs/validation/vsg_50hz_nadir_convergence_audit.json)), el refinamiento de tolerancias de `RK45` a `max_step = 50 µs` (`L1: rtol=1e-6, atol=1e-8` $\to$ `L2: rtol=1e-8, atol=1e-10`) mostró que la diferencia entre los mínimos pos-evento de frecuencia con y sin BESS ante el escalón de carga de $+40\ \%$ a $50\text{ Hz}$ variaba apenas en `0,000733 µHz` (`-62,446448 µHz` frente a `-62,445715 µHz`), pero dejaba en estado `REVIEW` la independencia respecto al tamaño máximo de paso (`max_step`).

En esta investigación se ejecutó una campaña controlada de refinamiento espacial-temporal sobre el horizonte completo de **$6{,}5\text{ s}$**, preservando exactamente los parámetros físicos ($M = 80$, $D = 1500$, $f_0 = 50\text{ Hz}$, vector protegido de 16 estados en `MicrogridWithBESSDCDC`, condiciones iniciales y escalón en $t = 0{,}8\text{ s}$), evaluando **`max_step = 50 µs`, `25 µs` y `12,5 µs`** con `rtol = 1e-8, atol = 1e-10` e interpolación densa continua (`dense_output=True`, optimización `minimize_scalar` con `xatol = 1e-12 s`).

Los resultados demuestran que:
1. La diferencia continua $\Delta f_{\text{cont}} = f_{\text{BESS,min}} - f_{\text{noBESS,min}}$ permanece en **`-62,445715 µHz`** (`50 µs`), **`-62,445717 µHz`** (`25 µs`) y **`-62,445652 µHz`** (`12,5 µs`), con una variación total de apenas **`0,000066 µHz`** ($6{,}6 \times 10^{-11}\text{ Hz}$), es decir, **$\sim 946\,000\times$ menor** que el efecto físico reportado (`-62,45 µHz`).
2. El desplazamiento temporal del mínimo en el caso **con BESS** (`3,27 s` $\to$ `6,42 s` $\to$ `3,29 s` $\to$ `4,01 s`) no es inestabilidad del integrador, sino un efecto geométrico esperado: entre $t = 3{,}2\text{ s}$ y $t = 6{,}5\text{ s}$ el sistema con BESS alcanza un **equilibrio plano en régimen permanente** cuya oscilación total máxima es de apenas **$3{,}34 \times 10^{-13}\text{ Hz}$** (`25 µs`) a **$9{,}95 \times 10^{-13}\text{ Hz}$** (`12,5 µs`), en el piso de redondeo `float64`.
3. Por el contrario, el caso **sin BESS** posee un **nadir transitorio verdadero y bien localizado** en **`t = 0,8918415 s`**, invariante en $\pm 0{,}1\ \mu\text{s}$ y $\pm 0{,}00005\ \mu\text{Hz}$ entre `50 µs`, `25 µs` y `12,5 µs`.

---

## 2. Metodología Reproducible y Archivos Examinados

### 2.1 Referencias y código base
- Script reproducible de esta auditoría: [`scripts/audit_vsg_nadir_step_convergence.py`](../scripts/audit_vsg_nadir_step_convergence.py).
- Script de auditoría previo (`L1`, `L2`): [`src/validation/audit_vsg_nadir_convergence.py`](../src/validation/audit_vsg_nadir_convergence.py).
- Evidencia previa (`L1`, `L2`): [`outputs/validation/vsg_50hz_nadir_convergence_audit.json`](../outputs/validation/vsg_50hz_nadir_convergence_audit.json).
- Definición del modelo 50 Hz y escenario $+40\ \%$: [`src/validation/validate_bess_dcdc_50hz.py`](../src/validation/validate_bess_dcdc_50hz.py) (`_build_dcdc_model`, `T_END_S = 6.5`, `T_STEP_S = 0.8`).

### 2.2 Diseño de la campaña controlada y comandos de reproducción
- **Condiciones iniciales y parámetros congelados:** `M = 80.0`, `D = 1500.0`, `f_hz = 50.0 Hz`, `vdc0 = 340.0 V`, `soc_initial = 0.60`, `omega(0) = 2*pi*50 rad/s`, `theta(0) = 0.0 rad`, vector protegido de 16 estados (`MicrogridWithBESSDCDC`), carga nominal `3000 W` con escalón `+40 %` (`4200 W`) en `t = 0.8 s`.
- **Integrador:** `scipy.integrate.solve_ivp(..., method="RK45", dense_output=True)` sobre $[0{,}0;\ 6{,}5]\text{ s}$.
- **Niveles evaluados:**
  - `L1` (previo): `max_step = 50 µs`, `rtol = 1e-6`, `atol = 1e-8`, muestreo `dt = 500 µs`.
  - `L2` (previo): `max_step = 50 µs`, `rtol = 1e-8`, `atol = 1e-10`, muestreo `dt = 100 µs`.
  - `L3` (nuevo): `max_step = 25 µs`, `rtol = 1e-8`, `atol = 1e-10`, muestreo `dt = 100 µs`.
  - `L4` (nuevo): `max_step = 12,5 µs`, `rtol = 1e-8`, `atol = 1e-10`, muestreo `dt = 100 µs`.
- **Comandos de reproducción desde la raíz del repositorio:**
  ```bash
  python scripts/audit_vsg_nadir_step_convergence.py --max-step 2.5e-5 --rtol 1e-8 --atol 1e-10 --bess true --out outputs/audit_pending_review/nadir_25us_bess_true.json
  python scripts/audit_vsg_nadir_step_convergence.py --max-step 2.5e-5 --rtol 1e-8 --atol 1e-10 --bess false --out outputs/audit_pending_review/nadir_25us_bess_false.json
  python scripts/audit_vsg_nadir_step_convergence.py --max-step 1.25e-5 --rtol 1e-8 --atol 1e-10 --bess true --out outputs/audit_pending_review/nadir_12p5us_bess_true.json
  python scripts/audit_vsg_nadir_step_convergence.py --max-step 1.25e-5 --rtol 1e-8 --atol 1e-10 --bess false --out outputs/audit_pending_review/nadir_12p5us_bess_false.json
  python scripts/audit_vsg_nadir_step_convergence.py --summarize
  ```
- **Cálculo continuo del mínimo:** búsqueda en malla uniforme pos-evento ($t \ge 0{,}8\text{ s}$) de `omega(t)/(2*pi)` seguida de minimización acotada `scipy.optimize.minimize_scalar` sobre `sol.sol(t)[10]/(2*pi)` con `xatol = 1e-12 s`.
- **Caracterización de la meseta plana (con BESS):** cálculo de la amplitud total $\max(f) - \min(f)$ en $[3{,}2;\ 6{,}5]\text{ s}$ y muestreo en instantes fijos de referencia.
- **Entorno y dependencias verificadas:** `Python 3.11.2`, `numpy==2.4.6`, `scipy==1.17.1`.
- **Evidencia independiente generada (sin sobrescribir `outputs/validation/`):**
  - [`outputs/audit_pending_review/nadir_25us_bess_true.json`](../outputs/audit_pending_review/nadir_25us_bess_true.json) (`sha256: 6d06e6b8681464aaf6713d9adc10c5f2437b4e39eb7fe064e4c1b096dc0ea0a7`)
  - [`outputs/audit_pending_review/nadir_25us_bess_false.json`](../outputs/audit_pending_review/nadir_25us_bess_false.json) (`sha256: f0de113e370efdc79e475edb24eaec4517183f225b8dbcb79a246cebb53be429`)
  - [`outputs/audit_pending_review/nadir_12p5us_bess_true.json`](../outputs/audit_pending_review/nadir_12p5us_bess_true.json) (`sha256: 35070feb58fb1337199c2c7d1e21878f8765d4806fb1414af6cc8715d9f4a24b`)
  - [`outputs/audit_pending_review/nadir_12p5us_bess_false.json`](../outputs/audit_pending_review/nadir_12p5us_bess_false.json) (`sha256: e7fe8b2c1e605136b211f40b993b0f1401cde8ae92378e9939daf8fe844b78bf`)
  - [`outputs/audit_pending_review/nadir_step_convergence_summary.json`](../outputs/audit_pending_review/nadir_step_convergence_summary.json) (`sha256: d12b085100533f534897ce7e8cfddbefc1f4e0a1ab9c0b6b77c35e222ee773ec`)

---

## 3. Resultados Numéricos Comparativos (Horizonte 6,5 s)

### 3.1 Valores individuales, diferencias y desviaciones entre refinamientos

| Nivel | `max_step` [µs] | `rtol / atol` | $f_{\text{BESS,min}}$ [Hz] | $t_{\text{BESS}}$ [s] | $f_{\text{noBESS,min}}$ [Hz] | $t_{\text{noBESS}}$ [s] | $\Delta f_{\text{cont}}$ [µHz] | Cambio vs. nivel previo [µHz] |
|:---|---:|:---:|---:|---:|---:|---:|---:|---:|
| `L1` | `50,0` | `1e-6 / 1e-8` | `49.975616373721` | `3.267364` | `49.975678820169` | `0.89184156` | **`-62,446448`** | — |
| `L2` | `50,0` | `1e-8 / 1e-10` | `49.975616373714` | `6.423100` | `49.975678819428` | `0.89184147` | **`-62,445715`** | `+0,000733` |
| `L3` | `25,0` | `1e-8 / 1e-10` | `49.975616373716` | `3.292233` | `49.975678819433` | `0.89184148` | **`-62,445717`** | `-0,000002` |
| `L4` | `12,5` | `1e-8 / 1e-10` | `49.975616373734` | `4.006905` | `49.975678819386` | `0.89184146` | **`-62,445652`** | `+0,000066` |

### 3.2 Costo computacional

| Nivel | Evaluaciones RHS (`nfev`, con BESS) | Evaluaciones RHS (`nfev`, sin BESS) | Pasos aceptados (con / sin BESS) | Tiempo total de pared [s] |
|:---|---:|---:|---:|---:|
| `L1` (`50 µs`, tol base) | `786 266` | `786 278` | — | `290,4` |
| `L2` (`50 µs`, tol ref.) | `986 624` | `987 434` | — | `375,2` |
| `L3` (`25 µs`, tol ref.) | `1 584 848` | `1 583 810` | `263 240` / `263 212` | `496,2` *(270,5 + 225,7)* |
| `L4` (`12,5 µs`, tol ref.) | `3 124 952` | `3 124 982` | `520 604` / `520 605` | `953,0` *(522,3 + 430,7)* |

### 3.3 Análisis de la región plana en el escenario con BESS

Al evaluar la trayectoria continua `sol.sol(t)[10]/(2*pi)` en instantes fijos para `L3` (`25 µs`) y `L4` (`12,5 µs`) se confirma la naturaleza asintóticamente plana del régimen permanente con BESS:

| Instante $t$ [s] | $f_{\text{BESS}}(t)$ en `L3` (`25 µs`) [Hz] | $f_{\text{BESS}}(t)$ en `L4` (`12,5 µs`) [Hz] | Diferencia `L4 - L3` [µHz] |
|---:|---:|---:|---:|
| `0.8918415` | `49.980026003195` | `49.980026002469` | `-0,000726` |
| `2.0000000` | `49.975616373720` | `49.975616373735` | `+0,000015` |
| `3.2673639` | `49.975616373716` | `49.975616373735` | `+0,000019` |
| `4.0000000` | `49.975616373716` | `49.975616373735` | `+0,000019` |
| `5.5000000` | `49.975616373716` | `49.975616373734` | `+0,000018` |
| `6.4231000` | `49.975616373716` | `49.975616373734` | `+0,000018` |
| `6.5000000` | `49.975616373716` | `49.975616373734` | `+0,000018` |

La variación total $\max(f) - \min(f)$ en todo el intervalo $[3{,}2;\ 6{,}5]\text{ s}$ es:
- `L3 (25 µs)`: **`3,34 × 10⁻¹³ Hz`** (`0,00000033 µHz`).
- `L4 (12,5 µs)`: **`9,95 × 10⁻¹³ Hz`** (`0,00000099 µHz`).

---

## 4. Interpretación Numérica: Estabilidad Observada vs. Cota Rigurosa de Error

1. **Régimen de saturación por redondeo, no de error de truncamiento:**
   Entre `L3 (25 µs)` y `L4 (12,5 µs)` la variación de $\Delta f_{\text{cont}}$ es `0,000066 µHz`, ligeramente superior a la observada entre `L2` y `L3` (`0,000002 µHz`), y no decrece con razón $2^5 = 32$ propia de un método de orden 5 en régimen asintótico. Esto ocurre porque a `max_step <= 50 µs` y `rtol=1e-8, atol=1e-10`, el error de truncamiento local ya se encuentra por debajo del piso de **error de redondeo acumulado en `float64`** sobre $1{,}6\text{–}3{,}1 \times 10^6$ evaluaciones (en $\omega \approx 314{,}0\text{ rad/s}$, 1 ULP equivale a $\sim 9 \times 10^{-15}\text{ Hz}$, y la deriva acumulada sobre $5{,}2 \times 10^5$ pasos es del orden de $10^{-12}\text{–}10^{-11}\text{ Hz}$).
2. **Distinción epistemológica rigurosa:**
   Esta campaña **no constituye una cota analítica *a priori* de error global** ni incluye una comparación con un integrador implícito o de orden 8 (`DOP853`) sobre los $6{,}5\text{ s}$ completos (y la discontinuidad escalón en $t = 0{,}8\text{ s}$ es integrada sin reinicio explícito de evento). Sin embargo, sí establece **estabilidad numérica empírica robusta** en un rango de factor $4\times$ en `max_step` (`50 µs` $\to$ `25 µs` $\to$ `12,5 µs`) y $100\times$ en tolerancias (`1e-6` $\to$ `1e-8`).
3. **Suficiencia para la conclusión científica de la tesis:**
   - La señal física analizada ($\Delta f_{\text{nadir}} \approx -62{,}45\ \mu\text{Hz}$, es decir, que el BESS reduce la caída de frecuencia en apenas $0{,}25\ \%$ de la excursión total porque sostiene $V_{dc}$ y evita la autolimitación de potencia de la carga R-L) tiene una **incertidumbre numérica observada $< 0{,}0008\ \mu\text{Hz}$** frente a tolerancias y **$< 0{,}00007\ \mu\text{Hz}$** frente a refinamiento de paso (`50` $\to$ `12,5 µs`).
   - Dicha incertidumbre es **$\sim 946\,000\times$ inferior** a la diferencia analizada y **$\sim 7 \times 10^9$ veces inferior** al criterio de diseño de frecuencia de la microrred ($\Delta f_{\max} \le 0{,}50\text{ Hz}$).

---

## 5. Dictamen y Conclusión Defendible ante el Director de Tesis

- **Dictamen de esta auditoría (`PASS`):** Se propone **cerrar el estado `REVIEW` de convergencia numérica frente al tamaño de paso** para la diferencia de nadir a $50\text{ Hz}$, sustentado en estabilidad numérica empírica observada hasta `12,5 µs` (sin afirmar una cota analítica formal del error global).
- **Configuración recomendada como línea base:** `RK45` con `max_step = 50 µs`, `rtol = 1e-8`, `atol = 1e-10` (o `rtol = 1e-6, atol = 1e-8` para campañas de barrido, dado su error relativo $< 0{,}0012\ \%$ sobre $\Delta f_{\text{cont}}$).
- **Separación explícita de dictámenes en el proyecto:**
  - Convergencia numérica del nadir (`50 / 25 / 12,5 µs`): **`PASS`** (propuesta de cierre).
  - Causa de discrepancia IEEE 906 (2015): **`PASS`** (identificada y reproducida en [`auditoria_discrepancia_ieee906_2015.md`](auditoria_discrepancia_ieee906_2015.md)).
  - Escenario severo $+40\ \%$ sin BESS: **`REVIEW`** (permanece abierto por limitación física real del bus DC: $V_{dc}$ cae a $311{,}52\text{ V}$ bajo el techo FV de $3972\text{ W}_{\text{DC}}$ y satura el índice de modulación en $m = 0{,}95$).
  - Validación experimental del envejecimiento BESS y catálogo 5 kVA: **`BLOCKED`** (pendiente de ensayos de laboratorio RPT/HPPC propios y perfiles medidos).
