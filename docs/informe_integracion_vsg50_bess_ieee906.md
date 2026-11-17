# Informe Técnico de Cierre: Integración VSG 50 Hz – Banco BESS 48s 2s2p + DC/DC – IEEE European LV (906 Barras)

**Repositorio:** `G:\OneDrive - Universidad Nacional de Colombia\microgrid_vsm_ieee906`
**Rama:** `feat/ieee906-vsg50-interface`
**Alcance:** Integración autónoma, cierre físico de la interfaz banco–bus DC (arquitectura paramétrica aprobada `BAT26-53`) y auditoría científica independiente para la variante de 50 Hz acoplada unidireccionalmente al alimentador IEEE European LV (906 barras, 416 V LL, 50 Hz).

---

## 1. Resumen Ejecutivo y Dictamen de Cierre del Objetivo 2

Se completó el cierre físico no invasivo de la interfaz entre el banco de segunda vida (`BAT26-53`: **48 módulos Nissan Leaf 2s2p en serie**, $96\text{ unidades 2p}$ en serie, $360\text{ V}$ nominales, $44{,}1\text{ Ah}$ iniciales, $\text{SoH}_0 = 0{,}668182$) y el bus DC independiente de **$340\text{ V}$** mediante [`src/microgrid_bess_dcdc.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/src/microgrid_bess_dcdc.py) (`MicrogridWithBESSDCDC`), reutilizando el adaptador algebraico [`src/bess/dc_dc_adapter.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/src/bess/dc_dc_adapter.py) dentro del mismo integrador global `solve_ivp` de 16 estados y manteniendo intactas todas las ecuaciones protegidas y $M = 80$, $D = 1500$.

**Dictamen sobre el Objetivo 2:** **LISTO PARA PRESENTACIÓN AL DIRECTOR CON CIERRE CONDICIONADO.**
El cierre es *condicionado* porque la consistencia numérica interna, las leyes físicas 1RC/DC-DC, el soporte bidireccional en carga y descarga, la separación entre $I_{\text{bank}}$ e $I_{\text{bus}}$ y el acoplamiento estático/QSTS con IEEE 906 están demostrados y auditados, mientras que permanecen explícitamente bloqueados (`BLOCKED`) la validación experimental en laboratorio (RPT/HPPC de módulos Nissan Leaf), las hojas de datos de un transformador comercial $190{,}53/416\text{ V}$ y el desarrollo del Objetivo 3 (FOVIC y despacho óptimo).

| Componente / Fase | Estado | Nivel de Evidencia | Artefacto Principal |
|:---|:---:|:---|:---|
| **Fase 1:** Dinámica 50 Hz vs. 60 Hz (6,5 s, nominal y +20 %) | `PASS` | Validación numérica interna | [`vsg_50hz_interface_audit_6p5s.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/vsg_50hz_interface_audit_6p5s.json) |
| **Fase 1:** Escalón +40 % sin BESS ($M=80, D=1500$) | `REVIEW` | Limitación física demostrada (techo MPP FV) | [`vsg_50hz_vs_60hz_6p5s.png`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/vsg_50hz_vs_60hz_6p5s.png) |
| **Fase 2A:** Descarga BESS+PI 16 estados (referencia acoplamiento directo) | `PASS` | Validación numérica interna (escala $V_{dc}/V_t$ en `REVIEW`) | [`bess_50hz_discharge_summary.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_50hz_discharge/bess_50hz_discharge_summary.json) |
| **Fase 2B (`BAT26-53`):** Banco 48s 2s2p + DC/DC bidireccional (13 casos, 50 Hz) | `PASS` | Validación numérica interna (paramétrica, no experimental) | [`bess_dcdc_50hz_summary.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json) |
| **Fase 3:** Transformador $190{,}53/416\text{ V}$, $5\text{ kVA}$ y auditoría $I_0$ (`YNyn0`/`Dyn`/`Ynd`) | `PASS` / `REVIEW` | Sensibilidad OpenDSS (20 casos $I_0$ + 12 mediodía) | [`transformer_zero_sequence_audit.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/analysis/ieee_europe_lv_906/transformer_zero_sequence_audit.json) |
| **Fase 4:** QSTS 24 h (Barras 34 y 822, perfiles sintéticos) | `PASS` | Flujo cuasiestático unidireccional (1440 min) | [`qsts_24h_scenarios_comparison.csv`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/analysis/ieee_europe_lv_906/qsts_24h_scenarios_comparison.csv) |
| **Fase 5:** Auditoría crítica y paridad IEEE PES 2015 | `PASS` / `REVIEW` | 7 `PASS`, 1 `REVIEW` (9,54 % IEEE 2015), 1 `BLOCKED`, 0 `FAIL` | [`phase5_scientific_audit.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/phase5_scientific_audit.json) |
| **Fase 6:** Pruebas unitarias y regresiones Obj. 1 e invariantes | `PASS` | 26 pruebas unitarias (27 subtests) + regresiones Obj. 1/GFM | [`test_microgrid_bess_dcdc.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/src/validation/test_microgrid_bess_dcdc.py) |
| **Objetivo 3 / Hardware:** FOVIC, despacho óptimo, RPT/HPPC, catálogo Xfmr | `BLOCKED` | Fuera de alcance hasta aprobación de Objetivo 2 y datos | Sección 7 |

---

## 2. Fase 1: Auditoría 6,5 s (50 Hz vs. 60 Hz) y Compromiso Frecuencia–Tensión

### 2.1 Escalado a 50 Hz y Auditoría de Ventanas de $V_{dc}$

- `BalancedRLLoad` conserva $R = 10{,}92025\ \Omega$ y escala $L_{50} = 11{,}42514\text{ mH}$ ($1{,}20 \times L_{60}$), manteniendo $X_{\text{load}} = 3{,}58931\ \Omega$ y $Q_{\text{nom}} = 986{,}05\text{ var}$ a $110\text{ V}_{\text{LN,rms}}$. El filtro LCL conserva $L_1 = L_2 = 1{,}0\text{ mH}$ y $C = 30\ \mu\text{F}$, reduciendo su reactancia serie un $16{,}67\ \%$ a 50 Hz ($0{,}31416\ \Omega$ vs. $0{,}37699\ \Omega$).
- Se distinguen explícitamente $V_{dc}(0) = 340{,}00\text{ V}$, $V_{dc,\text{global,min}}$ ($340{,}00\text{ V}$ en $t = 0\text{ s}$ para nominal y +20 % sin BESS) y $V_{dc,\text{post,min}}$ ($378{,}93\text{ V}$ nominal y $363{,}52\text{ V}$ en +20 % a 50 Hz).
- En **+40 % sin BESS**, la demanda nominal ($4200\text{ W}_{\text{AC}}$) excede el techo FV ($P_{\text{PV,MPP}} = 3972{,}27\text{ W}_{\text{DC}} \equiv 3853{,}10\text{ W}_{\text{AC}}$ tras $\eta = 0{,}97$). Al agotarse los $36{,}33\text{ J}$ del condensador $C_{dc}$ en $\approx 0{,}12\text{ s}$, $V_{dc}$ cae a $311{,}52\text{ V}$ (50 Hz), $m_{\text{ctrl}}$ satura en $0{,}95$ el $98{,}41\ \%$ de la ventana posevento y la carga R-L se autolimita a $3535{,}36\text{ W}$ (`REVIEW` conservado).

### 2.2 Causa Física del Compromiso en el Nadir de Frecuencia (+40 % con vs. sin BESS)

En el escenario **+40 % a 50 Hz**, la regulación DC mejora drásticamente con BESS+DC/DC ($V_{dc,\text{post,min}} = 338{,}11\text{ V}$ frente a $311{,}52\text{ V}$ sin BESS), pero el nadir de frecuencia con BESS (**$49{,}97562\text{ Hz}$**, caída $\Delta f = 0{,}02711\text{ Hz}$) es **$62{,}6\ \mu\text{Hz}$ inferior** al obtenido sin batería (**$49{,}97568\text{ Hz}$**):
- **Sin BESS:** El colapso de $V_{dc}$ satura la modulación y deprime la tensión PCC a $V_{\text{PCC,rms}} = 100{,}92\text{ V}$. Como la carga R-L es de impedancia constante ($P \propto V_{\text{PCC}}^2/R$), la potencia absorbida cae a **$3535{,}36\text{ W}$**, reduciendo el déficit $(P_{\text{ref}} - P_e)$ en la ecuación de oscilación del VSG.
- **Con BESS+DC/DC:** El bus DC se mantiene en $338{,}60\text{ V}$ ($> 327{,}50\text{ V}$) y la tensión PCC permanece en **$106{,}10\text{ V}$**, por lo que la carga absorbe **$3908{,}01\text{ W}$** (**$+372{,}65\text{ W}$** más que sin BESS). Ese mayor $P_e$ produce una excursión de frecuencia ligeramente mayor, aunque muy por debajo del límite de diseño de $0{,}50\text{ Hz}$ ($\Delta f = 0{,}0271\text{ Hz}$).

---

## 3. Fase 2B (`BAT26-53`): Cierre Físico del Banco 48s 2s2p e Interfaz DC/DC Bidireccional

### 3.1 Topología Aprobada y Ecuaciones de Acoplamiento No Invasivo

Siguiendo `BAT26-53`, `MicrogridWithBESSDCDC` acopla el banco de **48 módulos Nissan Leaf 2s2p en serie** ($N_s = 96$ unidades 2p en serie, $N_p = 1$, $V_{\text{nom}} = 360\text{ V}$, $Q_{\text{nom,ref}} = 66{,}0\text{ Ah}$, $Q_{\text{init}} = 44{,}1\text{ Ah}$, $\text{SoH}_0 = 0{,}668182$) al bus DC de $340\text{ V}$ mediante `bess.dc_dc_adapter.convert_power`:
$$V_{\text{bank}} = 96\left(\text{OCV}(\text{SoC}) - V_{rc} - I_{\text{unit}} R_0(\text{SoH})\right), \quad I_{\text{bank}} = N_p I_{\text{unit}}, \quad P_{\text{bank}} = V_{\text{bank}} I_{\text{bank}}$$
$$P_{\text{bus}} = \begin{cases} \eta_{\text{dis}} P_{\text{bank}}, & P_{\text{bus}} \ge 0\ (\text{descarga}) \\ P_{\text{bank}} / \eta_{\text{ch}}, & P_{\text{bus}} < 0\ (\text{carga}) \end{cases}, \quad P_{\text{loss,DC/DC}} = P_{\text{bank}} - P_{\text{bus}} \ge 0, \quad I_{\text{bus}} = \frac{P_{\text{bus}}}{V_{dc}}$$
La corriente física del banco $I_{\text{unit}}$ alimenta exclusivamente la EDO 1RC (`soc_bess`, `vrc_bess`, `zdeg_bess`), mientras que $I_{\text{bus}}$ entra en $dV_{dc}/dt = (i_{\text{pv}} + I_{\text{bus}} - i_{dc,\text{inv}})/C_{dc}$.

### 3.2 Resultados de la Campaña de 13 Escenarios a 50 Hz (`validate_bess_dcdc_50hz.py`)

Evidencia reproducible en [`outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json), [`bess_dcdc_50hz_summary.csv`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.csv) y figuras [`bess_dcdc_bank_vs_bus_50hz.png`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_dcdc_50hz/bess_dcdc_bank_vs_bus_50hz.png) y [`frequency_nadir_vdc_tradeoff_50hz.png`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_dcdc_50hz/frequency_nadir_vdc_tradeoff_50hz.png).

| Escenario (50 Hz) | Estado | $V_{\text{bank,ss}}$ [V] | $I_{\text{bank,ss}}$ [A] | $I_{\text{bus,ss}}$ [A] | $P_{\text{bank,ss}}$ [W] | $P_{\text{bus,ss}}$ [W] | $P_{\text{loss,ss}}$ [W] | $V_{dc,\text{post,min}}$ [V] | $f_{\text{post,min}}$ [Hz] |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `+40%`, $\text{SoC}_0=0{,}60$, $\eta=0{,}95$ | `PASS` | 363,75 | +0,827 | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoC}_0=0{,}12$ ($<340\text{ V}$) | `PASS` | **328,47** | **+0,916** | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoC}_0=0{,}88$ ($>340\text{ V}$) | `PASS` | **376,52** | **+0,799** | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoH}=1{,}00$ | `PASS` | 363,77 | +0,827 | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoH}=0{,}70$ | `PASS` | 363,75 | +0,827 | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\text{SoH}=0{,}55$ | `PASS` | 363,74 | +0,827 | +0,844 | +300,81 | +285,77 | 15,04 | 338,11 | 49,97562 |
| `+40%`, $\eta=1{,}00$ | `PASS` | 363,75 | +0,786 | +0,844 | +285,77 | +285,77 | 0,00 | 338,11 | 49,97562 |
| `+40%`, $\eta=0{,}90$ | `PASS` | 363,74 | +0,873 | +0,844 | +317,52 | +285,77 | 31,75 | 338,11 | 49,97562 |
| `+40%`, BESS deshabilitado | `REVIEW` | 363,87 | 0,000 | 0,000 | 0,00 | 0,00 | 0,00 | 311,52 | 49,97568 |
| Caída $G$ ($800\to 400$), $\eta=0{,}95$ | `PASS` | 363,29 | +3,532 | +3,644 | +1283,19 | +1219,03 | 64,16 | 332,68 | 49,99007 |
| Caída $G$ ($800\to 400$), $\eta=0{,}90$ | `PASS` | 363,26 | +3,729 | +3,644 | +1354,48 | +1219,03 | 135,45 | 332,68 | 49,99007 |
| Caída $G$ ($800\to 400$), $P_{\max}=1200\text{ W}$ | `PASS` | 363,30 | +3,477 | +3,631 | +1263,16 | +1200,00 | 63,16 | 330,49 | 49,99007 |
| Caída $G$ ($800\to 400$), BESS deshabilitado | `REVIEW` | 363,87 | 0,000 | 0,000 | 0,00 | 0,00 | 0,00 | 220,60 | 49,93531 |

Todos los escenarios activos cumplen:
- Operación bidireccional tanto por debajo de $340\text{ V}$ ($328{,}47\text{ V}$ en $\text{SoC}_0=0{,}12$) como por encima de $340\text{ V}$ ($363{,}75\text{ V}$ y $376{,}52\text{ V}$).
- Separación física $I_{\text{bank}} \ne I_{\text{bus}}$ (hasta $0{,}242\text{ A}$ de diferencia en transitorio $+40\ \%$ y $0{,}316\text{ A}$ a $\text{SoC}_0=0{,}88$).
- Residuos de balance energético: $\le 0{,}0322\text{ J}$ en $C_{dc}$, $\le 1{,}4 \times 10^{-13}\text{ J}$ en conversión DC/DC ($E_{\text{bank}} - E_{\text{bus}} - E_{\text{loss}}$), $\le 3{,}4 \times 10^{-13}\text{ W}$ en descomposición 1RC del banco, y error de conteo de Coulomb con $I_{\text{unit}}$ menor a $4{,}2 \times 10^{-10}$.

---

## 4. Fase 3: Auditoría de Secuencia Cero y Puesta a Tierra del Transformador (`YNyn0`, `Dyn`, `Ynd`)

El script [`scripts/audit_ieee906_transformer_zero_seq.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/scripts/audit_ieee906_transformer_zero_seq.py) evaluó **20 escenarios** en OpenDSS (barras 34 y 822, mediodía $t=720$ y pico nocturno $t=1140$) para corregir cualquier generalización indebida sobre `YNyn0`:

| Caso en Barra 822 ($t=720\text{ min}$, $P=3\text{ kW}$) | Devanados (Inv / Red) | Neutro Inv. | $I_{0,\text{inv}}$ [A] | $I_{0,\text{416V}}$ [A] | $P_{\text{fases,416V}}$ (A / B / C) [kW] | Spread [kW] |
|:---|:---:|:---:|---:|---:|:---:|---:|
| `YNyn0_3wire_ideal` | `wye` / `wye` | 3 hilos (sin retorno $I_0$) | 0,0112 | 0,0051 | 0,992 / 0,992 / 0,992 | 0,0002 |
| `YNyn0_3wire_mag` ($i_{\text{mag}}=1{,}5\ \%$) | `wye` / `wye` | 3 hilos (sin retorno $I_0$) | 0,0112 | 0,0051 | 0,988 / 0,988 / 0,988 | 0,0001 |
| **`YNyn0_4wire_grounded`** | `wye` / `wye` | **4 hilos aterrado** | **0,6671** | **0,3059** | **0,942 / 1,063 / 0,959** | **0,1209** |
| `Dyn_3wire` | `delta` / `wye` | 3 hilos | 0,0000 | **0,5723** | 0,916 / 1,129 / 0,919 | 0,2136 |
| `Ynd_4wire_grounded` | `wye` / `delta` | 4 hilos aterrado | 0,0057 | **0,0000** | 0,986 / 0,986 / 0,993 | 0,0076 |

**Conclusión corregida:** Un transformador `YNyn0` **NO bloquea intrínsecamente** la corriente homopolar. En el caso anterior con un generador `wye` de 3 hilos (impedancia homopolar abierta en el inversor), $I_0 \approx 0{,}005\text{ A}$ era consecuencia de la ausencia de retorno en el lado del inversor. Cuando existe un camino homopolar aterrado de 4 hilos en el lado inversor, `YNyn0` transmite $I_0$ directamente ($0{,}6671\text{ A} \to 0{,}3059\text{ A}$, razón $a = 2{,}1834$) y desequilibra las potencias de fase. `Dyn` atrapa siempre $I_0$ en su delta ($0{,}5723\text{ A}$), mientras que `Ynd` bloquea estructuralmente $I_0$ en 416 V ($0{,}0000\text{ A}$) a costa de perder la referencia de neutro en el lado de red.

---

## 5. Fase 4: Coherencia entre Dinámica de 6,5 s y QSTS de 24 Horas

Se mantiene la separación estricta de escalas temporales (los transitorios ODE de $6{,}5\text{ s}$ no se extrapolan a un día, y el estudio QSTS de 24 h en OpenDSS es transferencia cuasiestática unidireccional con perfiles sintéticos, **no co-simulación dinámica**). No obstante, la topología aprobada `BAT26-53` ($360\text{ V} \times 44{,}1\text{ Ah} = 15{,}876\text{ kWh}$ nominales) hace ahora **energéticamente coherente** el perfil diario QSTS de la Fase 4:
- La energía cargada en el perfil diario QSTS ($3{,}820\text{ kWh}$) representa una excursión de $\Delta\text{SoC} = 24{,}1\ \%$ sobre los $15{,}876\text{ kWh}$ del banco, perfectamente contenida dentro de la ventana útil $\text{SoC} \in [0{,}10;\ 0{,}90]$ ($12{,}70\text{ kWh}$), a diferencia del par 2p aislado previo ($0{,}165\text{ kWh}$).
- En la barra 822 con transformador `H2` ($5\text{ kVA}$), el perfil FV+BESS reduce las pérdidas del alimentador en **$-5{,}43\ \%$** ($4{,}7880\text{ kWh/día}$ vs. $5{,}0627\text{ kWh/día}$ base), reduce las pérdidas de cobre del transformador en $27{,}0\ \%$ ($0{,}1062\text{ kWh/día}$) y mejora la tensión mínima de $0{,}9827\text{ pu}$ a $0{,}9897\text{ pu}$.

---

## 6. Distinción de Niveles de Evidencia y Auditoría Fase 5

- **Pruebas unitarias automatizadas (`PASS`):** `26 passed, 27 subtests passed` (`test_microgrid_bess_dcdc.py`, `test_dc_dc_adapter.py`, `test_vsg_50hz_and_bess_discharge.py`, `test_ieee_europe_lv_906_interface.py`).
- **Validación numérica interna (`PASS` / `REVIEW`):** `validate_obj1_regression.py` (`PASS`), `validate_physical_invariants.py` (`PASS`), `validate_vsg_50hz_interface.py` (`PASS`/`REVIEW` +40 %), `validate_bess_50hz_discharge.py` (`PASS`), `validate_bess_dcdc_50hz.py` (`PASS`), `audit_scientific_consistency_phase5.py` (**7 `PASS`, 1 `REVIEW`, 1 `BLOCKED`, 0 `FAIL`**).
- **Comparación con referencias publicadas (`REVIEW`):** Se conserva el `REVIEW` de la discrepancia máxima de $9{,}54\ \%$ por fase frente a la tabla resumen IEEE PES 2015 ([`ieee_europe_lv_906_reference_audit.md`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/docs/ieee_europe_lv_906_reference_audit.md)).
- **Validación experimental (`BLOCKED`):** No existen mediciones RPT/HPPC propias de banco Leaf 48s 2s2p, ni catálogo comercial de transformador $190{,}53/416\text{ V}$, ni perfiles solares medidos.

---

## 7. Pendientes para Objetivo 3 (No Iniciados por Regla de Alcance)

1. Aprobación por el director del cierre condicionado del Objetivo 2 con la arquitectura `BAT26-53` (`MicrogridWithBESSDCDC`).
2. Implementación y comparación formal de **FOVIC** frente a VSG ($M=80, D=1500$), droop y $V\text{-}f$.
3. Formulación e implementación del despacho óptimo (Objetivo 3) con costos y perfiles validados o escenarios de sensibilidad explícitos.
