# Dossier Académico de Cierre del Objetivo 2: Integración VSG (50/60 Hz), Banco BESS Nissan Leaf 48×2s2p con Interfaz DC/DC y Acoplamiento al Alimentador IEEE European LV (906 Barras)

**Documento:** Dossier de presentación ante Dirección de Tesis
**Repositorio y rama:** `G:\OneDrive - Universidad Nacional de Colombia\microgrid_vsm_ieee906` — `feat/ieee906-vsg50-interface`
**Trazabilidad base:** [`AGENTS.md`](../AGENTS.md), [`objective_2_closure_criteria.md`](../docs/objective_2_closure_criteria.md), [`bat26-49-source-evidence-matrix.md`](../docs/bat26-49-source-evidence-matrix.md), [`informe_integracion_vsg50_bess_ieee906.md`](../docs/informe_integracion_vsg50_bess_ieee906.md)

---

## 1. Propósito, Alcance y Dictamen Ejecutivo

Este dossier consolida la evidencia numérica, física y documental reproducible que sustenta la solicitud de **cierre condicionado del Objetivo 2** de la tesis de maestría. El Objetivo 2 comprende la implementación e integración dinámica de un controlador Grid-Forming clásico tipo Máquina Síncrona Virtual (`GFMController`, VSG) con un sistema de almacenamiento en baterías de segunda vida (`SecondLifeBattery1RC`), su regulación externa del bus DC (`DCLinkBESSPIController`) y el cierre físico de la frontera banco–bus DC mediante la arquitectura paramétrica aprobada en **BAT26-53** (**48 módulos Nissan Leaf 2s2p en serie** acoplados por una etapa DC/DC bidireccional al bus de $340\text{ V}$), junto con la extensión verificada a **50 Hz** y el acoplamiento secuencial unidireccional hacia el alimentador europeo de baja tensión **IEEE European LV (906 barras, $416\text{ V}_{\text{LL}}$, $50\text{ Hz}$)**.

**Dictamen formal:** Existe fundamento técnico y trazabilidad reproducible para solicitar el **cierre condicionado del Objetivo 2** ante el director de tesis, bajo la delimitación explícita de **validación numérica interna con parámetros de referencia y escenarios sintéticos**. El dossier **no** declara validación experimental de laboratorio, **no** sustituye la selección comercial de un transformador ni un BMS industrial, y **no** inicia prematuramente el controlador de orden fraccionario (FOVIC) ni el despacho óptimo económico (Objetivo 3).

---

## 2. Formulación Metodológica y Arquitectura del Sistema

### 2.1 Principios de Arquitectura y Separación de Capas

La arquitectura del software impone cuatro restricciones estructurales no negociables definidas en [`AGENTS.md`](../AGENTS.md):
1. **Integrador global único:** La planta eléctrica (FV, condensador DC, filtro LCL, carga R-L), el ángulo y frecuencia del VSG, los estados electroquímicos del BESS y el estado integral del controlador PI del bus DC se integran simultáneamente en un único llamado a `scipy.integrate.solve_ivp` (`RK45`, $\Delta t_{\max} = 5\times 10^{-5}\text{ s}$, $\text{rtol} = 10^{-6}$, $\text{atol} = 10^{-8}$).
2. **Separación de capas:** La física de planta reside en [`src/microgrid.py`](../src/microgrid.py); la lógica GFM en [`src/controllers/gfm_controller.py`](../src/controllers/gfm_controller.py); la regulación externa del bus DC en [`src/controllers/dc_link_bess_pi.py`](../src/controllers/dc_link_bess_pi.py) y [`src/microgrid_bess_pi.py`](../src/microgrid_bess_pi.py); el acoplamiento físico no invasivo banco–DC/DC en [`src/microgrid_bess_dcdc.py`](../src/microgrid_bess_dcdc.py) y [`src/bess/dc_dc_adapter.py`](../src/bess/dc_dc_adapter.py); y la visualización/reporte en scripts externos.
3. **Orden protegido de estados:**
   - **GFM sin BESS (12 estados):** $[V_{dc},\ i_{1a}, i_{1b}, i_{1c},\ v_{ca}, v_{cb}, v_{cc},\ i_{2a}, i_{2b}, i_{2c},\ \omega,\ \theta]$.
   - **GFM con BESS y PI/DC-DC (16 estados):** $[V_{dc},\ i_{1abc},\ v_{cabc},\ i_{2abc},\ \omega,\ \theta,\ \text{SoC},\ V_{rc},\ z_{\text{deg}},\ \xi_{V_{dc}}]$, donde $x[10] = \omega$, $x[11] = \theta$, $x[12{:}15]$ corresponden al BESS 1RC y $x[15] = \xi_{V_{dc}}$ al integrador del PI externo.
4. **Convenciones de signos invariantes:** $i_{\text{bess}} > 0$ y $P_{\text{bess}} > 0$ indican **descarga** (entrega de potencia desde la batería hacia el bus DC); $i_{\text{bess}} < 0$ y $P_{\text{bess}} < 0$ indican **carga**.

---

## 3. Ecuaciones Fundamentales, Parámetros y Procedencia Científica

### 3.1 Planta Fotovoltaica, Bus DC, Inversor Promediado, LCL y Carga R-L

| Subsistema | Ecuación / Relación Matemática | Parámetros Principales | Procedencia y Trazabilidad |
|:---|:---|:---|:---|
| **Arreglo FV** (`PVArraySingleDiode`) | Modelo de un diodo con $N_{s,\text{arr}}=10$, $N_{p,\text{arr}}=1$ | Módulo LONGi LR7-54HJD-500M ($V_{oc,\text{STC}}=41{,}35\text{ V}$, $I_{sc,\text{STC}}=15{,}30\text{ A}$, $V_{mp}=34{,}17\text{ V}$, $I_{mp}=14{,}63\text{ A}$). A $G=800\text{ W/m}^2, 25\ ^\circ\text{C}$: $P_{\text{MPP}}=3972{,}27\text{ W}_{\text{DC}}$ a $342{,}7\text{ V}$. | Hoja de datos LONGi; ajuste STC en [`src/config.py`](../src/config.py) y `validate_pv_stc_fit.py`. |
| **Bus DC** (`DCLinkParams`) | $C_{dc}\dfrac{dV_{dc}}{dt} = i_{\text{pv}} + i_{\text{bus}} - i_{dc,\text{inv}}$ | $C_{dc} = 2{,}0\text{ mF}$, $V_{dc,0} = V_{dc,\text{ref}} = 340{,}0\text{ V}$, $V_{\min} = 50{,}0\text{ V}$, $\text{UVLO} = 200{,}0\text{ V}$. | Ecuación protegida en [`AGENTS.md`](../AGENTS.md) y `src/dclink.py`. |
| **Inversor promediado** (`GridFormingInverter`) | $v_{\text{inv},\phi} = \dfrac{m\,V_{dc}}{2}\sin(\theta - \phi_k)$, $i_{dc,\text{inv}} = \dfrac{p_{\text{bridge}}}{\eta_{\text{inv}} V_{dc}}$ | $\eta_{\text{inv}} = 0{,}97$, $m_{\max} = 0{,}95$, $V_{\text{LN,rms}} = 110{,}0\text{ V}$ ($190{,}53\text{ V}_{\text{LL}}$), $V_{dc,\min,\text{mod}} = \dfrac{2\sqrt{2}\cdot 110}{0{,}95} = 327{,}502\text{ V}$. | `src/inverter_source.py`; límite lineal de modulación SPWM. |
| **Filtro LCL** (`LCLFilter`) | Dinámica trifásica $i_1, v_c, i_2$ con resistencia de amortiguamiento $R_d$ | $L_1 = L_2 = 1{,}0\text{ mH}$, $R_1 = R_2 = 0{,}05\ \Omega$, $C_f = 10\ \mu\text{F}$ (config) / $30\ \mu\text{F}$ planta, $R_d$ protegido en `validate_lcl_no_unphysical_oscillations.py`. | `src/lcl_filter.py` y `docs/model_assumptions.md`. |
| **Carga R-L equilibrada** (`BalancedRLLoad`) | $Z = 3 V_{\text{LN}}^2 \cos\varphi / P_{3\phi}$, $R = Z\cos\varphi$, $L = \dfrac{Z\sin\varphi}{2\pi f_0}$ | $P_{\text{nom}} = 3000\text{ W}$, $\cos\varphi = 0{,}95$ atraso ($Q_{\text{nom}} = 986{,}05\text{ var}$), $R = 10{,}92025\ \Omega$, $L_{60} = 9{,}52095\text{ mH}$, $L_{50} = 11{,}42514\text{ mH}$. | Escalado físico exacto en [`src/microgrid.py`](../src/microgrid.py). |

### 3.2 Controlador VSG Clásico (`GFMController`)

La ecuación de oscilación reducida implementada en [`src/controllers/gfm_controller.py`](../src/controllers/gfm_controller.py) es:
$$\frac{d\omega}{dt} = \frac{P_{\text{ref,eff}} - P_e - D(\omega - \omega_{\text{ref}})}{M}, \qquad \frac{d\theta}{dt} = \omega, \qquad f_{\text{din}}(t) = \frac{\omega(t)}{2\pi}$$
donde $P_e = \mathbf{v}_{\text{pcc}}^\top \mathbf{i}_2$ se calcula con la tensión trifásica completa en el PCC de la carga R-L, $M = 80$ y $D = 1500$ permanecen congelados desde la selección de sintonía del Objetivo 2, $\omega_{\text{ref}} = 2\pi f_0$ ($376{,}991\text{ rad/s}$ a $60\text{ Hz}$; $314{,}159\text{ rad/s}$ a $50\text{ Hz}$), y $P_{\text{ref,eff}}$ incorpora la limitación por disponibilidad neta en el lado DC (PV + BESS).

### 3.3 Banco Nissan Leaf 48×2s2p (`BAT26-53`), Modelo Thevenin 1RC e Interfaz DC/DC

De acuerdo con la matriz de procedencia [`bat26-49-source-evidence-matrix.md`](../docs/bat26-49-source-evidence-matrix.md) y la decisión arquitectónica **BAT26-53**:
- **Estructura del banco (`BAT26-53`):** 48 módulos Nissan Leaf `2s2p` en serie $\Rightarrow N_s = 96$ pares `2p` en serie, $N_p = 1$ rama en paralelo, tensión nominal $96 \times 3{,}75\text{ V} = 360\text{ V}$, capacidad nominal de referencia $Q_{\text{nom,ref}} = 66{,}0\text{ Ah}$ (Braco et al., 2020, 2023) y capacidad inicial de segunda vida $Q_{\text{init}} = 44{,}1\text{ Ah}$ ($\text{SoH}_0 = 44{,}1/66{,}0 = 0{,}668182$).
- **Ecuaciones 1RC protegidas por unidad `2p` (`src/bess/model.py`, estructura Tran et al., 2021):**
  $$V_{t,\text{unit}} = \text{OCV}(\text{SoC}) - I_{\text{unit}} R_0(\text{SoH}) - V_{rc}, \qquad \frac{dV_{rc}}{dt} = -\frac{V_{rc}}{R_1 C_1} + \frac{I_{\text{unit}}}{C_1}$$
  $$\frac{d\text{SoC}}{dt} = -\frac{I_{\text{unit}}}{3600\,Q_{\text{eff}}}, \qquad \frac{dz_{\text{deg}}}{dt} = \frac{|I_{\text{unit}}|}{3600}, \qquad \text{SoH} = \max\left(\text{SoH}_{\min},\ \text{SoH}_0 - k_{\text{deg}} z_{\text{deg}}\right)$$
  $$Q_{\text{eff}} = Q_{\text{nom,ref}}\cdot \text{SoH}, \qquad R_0(\text{SoH}) = R_{0,\text{nom}}\left(1 + k_R(1 - \text{SoH})\right)$$
  con $\text{SoC} \in [0{,}10;\ 0{,}90]$, $\text{SoH}_{\min} = 0{,}50$, $R_{0,\text{nom}} = 0{,}970\text{ m}\Omega$, $k_R = 1{,}0$ y $k_{\text{deg}} = 1{,}478\times 10^{-6}\text{ Ah}^{-1}$ (leyes empíricas reducidas de tesis, no coeficientes experimentales calibrados de un módulo físico particular).
- **Interfaz DC/DC bidireccional y PI externo (`MicrogridWithBESSDCDC` + `DCLinkBESSPIController`):**
  $$e_{V_{dc}} = V_{dc,\text{ref}} - V_{dc}, \qquad P_{\text{ref,unsat}} = K_p e_{V_{dc}} + K_i \xi_{V_{dc}}, \qquad P_{\text{bus}} = \text{sat}\left(P_{\text{ref,unsat}},\ P_{\text{ch,lim}},\ P_{\text{dis,lim}}\right)$$
  $$V_{\text{bank}} = 96\,V_{t,\text{unit}}, \qquad I_{\text{bank}} = N_p I_{\text{unit}}, \qquad P_{\text{bank}} = V_{\text{bank}} I_{\text{bank}}, \qquad I_{\text{bus}} = \frac{P_{\text{bus}}}{V_{dc}}$$
  $$P_{\text{bank}} = \begin{cases} P_{\text{bus}}/\eta_{\text{dis}}, & P_{\text{bus}} \ge 0 \\ \eta_{\text{ch}} P_{\text{bus}}, & P_{\text{bus}} < 0 \end{cases}, \qquad P_{\text{loss,DC/DC}} = P_{\text{bank}} - P_{\text{bus}} \ge 0$$
  con anti-windup condicional que congela $d\xi_{V_{dc}}/dt = 0$ cuando el comando está saturado y el error $e_{V_{dc}}$ empuja en la misma dirección de la saturación.

---

## 4. Dinámica Comparada 50 Hz vs. 60 Hz en Horizonte de 6,5 s (Fase 1)

Las simulaciones extendidas a $6{,}5\text{ s}$ ([`validate_vsg_50hz_interface.py`](../src/validation/validate_vsg_50hz_interface.py), [`vsg_50hz_interface_audit_6p5s.json`](../outputs/validation/vsg_50hz_interface_audit_6p5s.json), [`vsg_50hz_vs_60hz_6p5s.png`](../outputs/validation/vsg_50hz_vs_60hz_6p5s.png)) emplean ventanas explícitas: arranque en frío ($0\text{–}0{,}7\text{ s}$), preevento ($0{,}7\text{–}0{,}8\text{ s}$), transitorio ($0{,}8\text{–}2{,}0\text{ s}$) y régimen permanente ($5{,}5\text{–}6{,}5\text{ s}$).

| $f_0$ [Hz] | Escenario | BESS+PI | Estado | $f_{\text{post,min}}$ [Hz] | $\|\text{RoCoF}\|_{\max}$ [Hz/s] | $V_{dc}(0)$ [V] | $V_{dc,\text{glob,min}}$ [V] | $V_{dc,\text{post,min}}$ [V] | $V_{dc,\text{final}}$ [V] | $V_{\text{PCC,rms}}$ [V] | $P_{\text{PCC,ss}}$ [W] | Sat. $m$ post [%] |
|---:|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 60 | Nominal | No | `PASS` | 60,002718 | 0,0000 | 340,00 | 340,00 | 379,31 | 379,31 | 106,90 | 2833,06 | 0,00 |
| 50 | Nominal | No | `PASS` | 50,002743 | 0,0000 | 340,00 | 340,00 | 378,93 | 378,93 | 107,26 | 2852,53 | 0,00 |
| 60 | +20 % | No | `PASS` | 59,992563 | 0,9067 | 340,00 | 340,00 | 364,76 | 364,85 | 106,23 | 3356,77 | 0,00 |
| 50 | +20 % | No | `PASS` | 49,992210 | 0,9151 | 340,00 | 340,00 | 363,52 | 363,65 | 106,68 | 3385,78 | 0,00 |
| 60 | +40 % | No | `REVIEW` | 59,977593 | 1,8023 | 340,00 | 313,86 | 313,86 | 313,92 | 101,16 | 3551,74 | 98,20 |
| 50 | +40 % | No | `REVIEW` | 49,975679 | 1,8234 | 340,00 | 311,52 | 311,52 | 311,59 | 100,92 | 3535,36 | 98,41 |
| 60 | +20 % | Sí | `PASS` | 59,992563 | 0,6398 | 340,00 | 340,00 | 340,86 | 340,94 | 106,23 | 3356,77 | 0,00 |
| 50 | +20 % | Sí | `PASS` | 49,992210 | 0,6497 | 340,00 | 340,00 | 340,78 | 340,85 | 106,68 | 3385,78 | 0,00 |
| 60 | +40 % | Sí | `PASS` | 59,979907 | 1,2102 | 340,00 | 338,24 | 338,24 | 338,81 | 105,59 | 3867,57 | 0,00 |
| 50 | +40 % | Sí | `PASS` | 49,975616 | 1,2293 | 340,00 | 338,11 | 338,11 | 338,64 | 106,10 | 3908,01 | 0,00 |

- **Diferencia física 50 vs. 60 Hz:** A 50 Hz, la reactancia serie del filtro LCL ($X_1 = X_2 = 0{,}31416\ \Omega$) es $16{,}67\ \%$ menor que a 60 Hz ($0{,}37699\ \Omega$), lo que eleva ligeramente $V_{\text{PCC}}$ y la potencia activa entregada a la carga R-L en casos no saturados.
- **Causa física del `REVIEW` en +40 % sin BESS:** La demanda nominal del escalón ($4200\text{ W}_{\text{AC}}$) supera el techo máximo de generación FV ($3853{,}10\text{ W}_{\text{AC}}$ en el MPP y $3753{,}05\text{ W}_{\text{AC}}$ en $V_{dc} = 327{,}502\text{ V}$). Los $36{,}33\text{ J}$ (50 Hz) almacenados en $C_{dc}$ por encima de $327{,}502\text{ V}$ se agotan en $\approx 0{,}12\text{ s}$; la modulación satura en $0{,}95$ el $98{,}41\ \%$ de la ventana posevento y la carga se autolimita a $3535{,}36\text{ W}$. No es un fallo numérico sino una restricción energética física.

---

## 5. Cierre Físico BESS 48×2s2p + DC/DC Bidireccional y Balances Energéticos (Fase 2B)

Los 13 escenarios ejecutados con [`validate_bess_dcdc_50hz.py`](../src/validation/validate_bess_dcdc_50hz.py) ([`bess_dcdc_50hz_summary.json`](../outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json), figuras [`bess_dcdc_bank_vs_bus_50hz.png`](../outputs/validation/bess_dcdc_50hz/bess_dcdc_bank_vs_bus_50hz.png) y [`frequency_nadir_vdc_tradeoff_50hz.png`](../outputs/validation/bess_dcdc_50hz/frequency_nadir_vdc_tradeoff_50hz.png)) demuestran:

| Escenario (50 Hz) | Estado | $V_{\text{bank,ss}}$ [V] | $I_{\text{bank,ss}}$ [A] | $I_{\text{bus,ss}}$ [A] | $P_{\text{bank,ss}}$ [W] | $P_{\text{bus,ss}}$ [W] | $P_{\text{loss,ss}}$ [W] | $V_{dc,\text{post,min}}$ [V] | $f_{\text{post,min}}$ [Hz] |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `+40%`, $\text{SoC}_0=0{,}60$, $\eta=0{,}95$ | `PASS` | 363,75 | +0,827 | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoC}_0=0{,}12$ ($<340\text{ V}$) | `PASS` | **328,47** | **+0,916** | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoC}_0=0{,}88$ ($>340\text{ V}$) | `PASS` | **376,52** | **+0,799** | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoH}\in\{1{,}00;\ 0{,}70;\ 0{,}55\}$ | `PASS` | 363,77–363,74 | +0,827 | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\eta=1{,}00$ / $\eta=0{,}90$ | `PASS` | 363,75 / 363,74 | +0,786 / +0,873 | +0,844 | +285,77 / +317,52 | +285,77 | 0,00 / 31,75 | 338,11 | 49,97562 |
| `+40%`, BESS deshabilitado | `REVIEW` | 363,87 | 0,000 | 0,000 | 0,00 | 0,00 | 0,00 | 311,52 | 49,97568 |
| Caída $G$ ($800\to 400$), $\eta=0{,}95$ | `PASS` | 363,29 | +3,532 | +3,644 | +1283,19 | +1219,03 | 64,16 | 332,68 | 49,99007 |
| Caída $G$ ($800\to 400$), $\eta=0{,}90$ | `PASS` | 363,26 | +3,729 | +3,644 | +1354,48 | +1219,03 | 135,45 | 332,68 | 49,99007 |
| Caída $G$ ($800\to 400$), $P_{\max}=1200\text{ W}$ | `PASS` | 363,30 | +3,477 | +3,631 | +1263,16 | +1200,00 | 63,16 | 330,49 | 49,99007 |
| Caída $G$ ($800\to 400$), BESS deshabilitado | `REVIEW` | 363,87 | 0,000 | 0,000 | 0,00 | 0,00 | 0,00 | 220,60 | 49,93531 |

- **Operación bidireccional en todo el rango de tensión del banco:** En $\text{SoC}_0 = 0{,}12$ el banco opera por debajo de $340\text{ V}$ ($328{,}47\text{ V}$) elevando corriente ($I_{\text{bank}} = +0{,}916\text{ A} > I_{\text{bus}} = +0{,}844\text{ A}$); en $\text{SoC}_0 = 0{,}60$ y $0{,}88$ opera por encima de $340\text{ V}$ ($363{,}75\text{ V}$ y $376{,}52\text{ V}$) reduciendo corriente ($I_{\text{bank}} = +0{,}827\text{ A}$ y $+0{,}799\text{ A}$).
- **Verificación de balances energéticos posevento ($0{,}8\text{–}6{,}5\text{ s}$):**
  - Balance en $C_{dc}$: $|\Delta E_{C_{dc}} - \int(P_{\text{pv}} + P_{\text{bus}} - P_{\text{inv,dc}})dt| \le 0{,}0322\text{ J}$ (sobre $>23\,255\text{ J}$).
  - Balance DC/DC: $|E_{\text{bank}} - E_{\text{bus}} - E_{\text{loss,DC/DC}}| \le 1{,}42\times 10^{-13}\text{ J}$.
  - Descomposición 1RC del banco: residuo máximo puntual $\le 3{,}41\times 10^{-13}\text{ W}$.
  - Conteo de Coulomb con $I_{\text{unit}}$: error $|\Delta\text{SoC}_{\text{ODE}} - \Delta\text{SoC}_{\int}| \le 4{,}16\times 10^{-10}$.

---

## 6. Análisis del Compromiso Tensión DC/PCC vs. Nadir de Frecuencia (+40 %)

En el escenario **+40 % a 50 Hz**, el contraste pareado entre BESS habilitado y deshabilitado revela un compromiso físico fundamental asociado a las **cargas de impedancia constante**:
1. **Sin BESS (`step40_dcdc_bess_disabled`):** El bus DC colapsa a $311{,}52\text{ V}$, la modulación satura en $m = 0{,}95$ y la tensión PCC cae a $V_{\text{PCC,rms}} = 100{,}92\text{ V}$. Al ser la carga R-L de impedancia constante ($P_{\text{load}} \propto V_{\text{PCC}}^2 / R$), la potencia eléctrica real demandada al inversor se autolimita a $P_e = 3535{,}36\text{ W}$. Con $P_{\text{ref,VSG}} = 3678{,}20\text{ W}$, el escalón neto de torque eléctrico es moderado y el nadir de frecuencia alcanza $49{,}97568\text{ Hz}$.
2. **Con BESS+DC/DC (`step40_dcdc_soc0p60_eta0p95`):** La regulación del bus DC ($338{,}60\text{ V} > 327{,}50\text{ V}$) evita la saturación de modulación ($m_{\max} = 0{,}9202$) y sostiene la tensión PCC en $106{,}10\text{ V}$. En consecuencia, la carga R-L absorbe **$P_e = 3908{,}01\text{ W}$** (**$+372{,}65\text{ W}$** adicionales respecto al caso sin BESS). Al mantenerse fija $P_{\text{ref,VSG}}$ y los parámetros $M = 80, D = 1500$, el nadir reportado es $49{,}97562\text{ Hz}$ frente a $49{,}97568\text{ Hz}$ sin BESS, una diferencia observada de aproximadamente $62{,}6 \mu\text{Hz}$. Esta es una observación numérica de estas ejecuciones; su sensibilidad al integrador y a sus tolerancias aún no ha sido evaluada, así que el mecanismo plausible descrito no se presenta como causalidad demostrada.
3. **Implicación para la tesis:** Este resultado demuestra que sostener la tensión del bus DC mejora la calidad de suministro en tensión y potencia servida a la carga, a costa de exigir mayor esfuerzo activo al lazo de frecuencia del VSG frente a cargas dependientes de tensión; aun así, la caída máxima de frecuencia ($0{,}02711\text{ Hz}$) queda $18\times$ por debajo del umbral de diseño de $0{,}50\text{ Hz}$.

---

## 7. Integración con el Alimentador IEEE European LV (906 Barras) y Auditoría Crítica

### 7.1 Transformador $190{,}53/416\text{ V}$, $5\text{ kVA}$ y Tratamiento de Secuencia Cero

Las hipótesis de diseño `H1`–`H5` ([`ieee_europe_lv_906_interface_and_qsts.py`](../scripts/ieee_europe_lv_906_interface_and_qsts.py)) adoptan $a = 416 / (110\sqrt{3}) = 2{,}183434$ y $S_{\text{ref}} = 5\text{ kVA}$ ($I_{\text{nom,190V}} = 15{,}15\text{ A}$, $I_{\text{nom,416V}} = 6{,}94\text{ A}$) con sensibilidad de impedancia $z_k \in [3{,}23\ \%;\ 6{,}32\ \%]$.
La auditoría específica de secuencia cero de 20 casos ([`audit_ieee906_transformer_zero_seq.py`](../scripts/audit_ieee906_transformer_zero_seq.py), [`transformer_zero_sequence_audit.json`](../outputs/analysis/ieee_europe_lv_906/transformer_zero_sequence_audit.json)) demuestra que **no debe generalizarse que `YNyn0` bloquee la corriente homopolar**:
- Con inversor de **3 hilos** (sin retorno de neutro en `DER_LV`), `YNyn0` presenta $I_{0,\text{416V}} = 0{,}0051\text{ A}$ en la barra 822 únicamente porque el circuito primario está abierto a secuencia cero.
- Con inversor de **4 hilos aterrado**, `YNyn0` **transmite** corriente homopolar ($I_{0,\text{inv}} = 0{,}6671\text{ A} \to I_{0,\text{416V}} = 0{,}3059\text{ A}$), desequilibrando las potencias por fase ($0{,}942 / 1{,}063 / 0{,}959\text{ kW}$).
- `Dyn` atrapa siempre $I_0$ en la delta del inversor ($I_{0,\text{416V}} = 0{,}5723\text{ A}$, spread $0{,}2136\text{ kW}$), mientras `Ynd` bloquea $I_0$ en el lado de $416\text{ V}$ ($0{,}0000\text{ A}$) a costa de dejar el lado de red sin referencia de neutro.

### 7.2 Escenarios QSTS de 24 h, Coherencia Energética y Discrepancia IEEE 2015

- **Separación estricta y coherencia:** Los transitorios ODE de $6{,}5\text{ s}$ no se extrapolan a 24 h; el estudio QSTS de 1440 minutos ([`ieee906_transformer_and_qsts_comparison.png`](../outputs/analysis/ieee_europe_lv_906/ieee906_transformer_and_qsts_comparison.png)) es un flujo cuasiestático unidireccional con perfiles solares y BESS **sintéticos** (no medidos). Con la capacidad del banco `BAT26-53` ($15{,}876\text{ kWh}$), el ciclado diario QSTS ($3{,}820\text{ kWh}$ carga / $3{,}447\text{ kWh}$ descarga, $\Delta\text{SoC}_{24\text{h}} = 0$) corresponde a $\Delta\text{SoC} = 24{,}1\ \%$, reduciendo las pérdidas de líneas en la barra 822 en **$-5{,}43\ \%$** ($4{,}7880\text{ vs. }5{,}0627\text{ kWh/día}$) y mejorando la tensión mínima de $0{,}9827$ a $0{,}9897\text{ pu}$. Ni 3 kW FV ni el BESS pueden alimentar aisladamente el alimentador completo ($517{,}31\text{ kWh/día}$).
- **Discrepancia IEEE 2015 (`REVIEW`):** Aunque los 55 perfiles de carga (79 200 muestras), 905 líneas y 10 códigos de línea coinciden exactamente con los archivos oficiales de IEEE PES, la comparación contra la tabla resumen publicada en 2015 mantiene un error relativo máximo de **$9{,}54\ \%$** en potencia activa por fase ([`ieee_europe_lv_906_reference_audit.md`](../docs/ieee_europe_lv_906_reference_audit.md)), por lo que la replicación externa de dicha tabla se conserva en `REVIEW`.

---

## 8. Matriz de Cumplimiento del Objetivo 2 y Auditoría de Niveles de Evidencia

| Ítem de Cumplimiento | Nivel de Evidencia | Estado | Fuente Verificable |
|:---|:---|:---:|:---|
| Regresión Objetivo 1 (LCL, BESS paso 3, límites SoC) | Validación numérica interna | `PASS` | `validate_obj1_regression.py` |
| Invariantes físicos y acoplamiento IEEE 33 (60 Hz) | Validación numérica interna | `PASS` | `validate_physical_invariants.py`, [`ieee33_microgrid_resultado.png`](../outputs/validation/figures_final/ieee33_microgrid_resultado.png) |
| Pruebas unitarias 50 Hz, `MicrogridWithBESSDCDC`, `dc_dc_adapter`, QSTS | Pruebas unitarias automatizadas | `PASS` (ver precisión de campañas abajo) | `test_microgrid_bess_dcdc.py`, `test_dc_dc_adapter.py`, `test_vsg_50hz_and_bess_discharge.py`, `test_ieee_europe_lv_906_interface.py` |
| Campaña VSG 50 Hz vs. 60 Hz (6,5 s, nominal y +20 %, +40 % con BESS) | Validación numérica interna | `PASS` | [`vsg_50hz_interface_audit_6p5s.json`](../outputs/validation/vsg_50hz_interface_audit_6p5s.json) |
| Escalón severo +40 % sin BESS ($M=80, D=1500$) | Limitación física demostrada | `REVIEW` | [`vsg_50hz_interface_audit_6p5s.json`](../outputs/validation/vsg_50hz_interface_audit_6p5s.json) |
| Cierre físico `BAT26-53` (48×2s2p + DC/DC bidireccional, 13 casos 50 Hz) | Validación numérica interna paramétrica | `PASS` | [`bess_dcdc_50hz_summary.json`](../outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json) |
| Auditoría secuencia cero (`YNyn0`, `Dyn`, `Ynd`) y QSTS 24 h | Validación numérica interna | `PASS` | [`transformer_zero_sequence_audit.json`](../outputs/analysis/ieee_europe_lv_906/transformer_zero_sequence_audit.json) |
| Replicación de tabla resumen IEEE PES 2015 (error máx. 9,54 %) | Comparación con referencia publicada | `REVIEW` | [`ieee_europe_lv_906_reference_audit.md`](../docs/ieee_europe_lv_906_reference_audit.md) |
| Validación experimental BESS (RPT/HPPC propios), catálogo transformador 5 kVA, perfil solar medido | Validación experimental / datos externos | `BLOCKED` | [`phase5_scientific_audit.json`](../outputs/validation/phase5_scientific_audit.json) |
| Controlador FOVIC y despacho óptimo económico (Objetivo 3) | Alcance futuro | `BLOCKED` | [`AGENTS.md`](../AGENTS.md) |

---

**Precisión sobre el conteo de pruebas:** las 26 pruebas y 27 subpruebas reportadas en el informe original corresponden a una campaña más limitada. La verificación ampliada posterior ejecutó 30 pruebas y 27 subpruebas, con resultados `PASS`. Son campañas distintas; sus cifras no se suman.

---

## 9. Puntos Clave para Discusión con el Director

1. **Aprobación del cierre condicionado del Objetivo 2:** Confirmar si el paquete numérico actual (`GFMController` $M=80, D=1500$ a 60/50 Hz + `MicrogridWithBESSDCDC` 48×2s2p `BAT26-53` + acoplamiento unidireccional IEEE 33 / IEEE 906) cierra formalmente el Objetivo 2 en etapa de simulación paramétrica.
2. **Definición de puesta a tierra del transformador $190{,}53/416\text{ V}$:** Acordar si la conexión al alimentador europeo de 416 V se especificará con inversor de 3 hilos (`YNyn0` sin retorno homopolar) o mediante transformador de aislamiento/esquema específico frente al desequilibrio de cargas monofásicas.
3. **Alcance del Objetivo 3 (FOVIC y despacho):** Autorizar el inicio del diseño de **FOVIC** (comparación frente a VSG clásico, droop y $V\text{-}f$) y definir si el despacho óptimo de degradación usará escenarios sintéticos parametrizados o perfiles medidos externos.
