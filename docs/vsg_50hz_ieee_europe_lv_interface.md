# Auditoría de Interfaz VSG 50 Hz – BESS – IEEE European LV (906 Barras)

## 1. Alcance y Decisiones de Arquitectura

Este documento actualiza el registro de auditoría e integración de la variante optativa de **50 Hz** del controlador Grid-Forming (`GFMController`, VSG clásico con ecuación reducida de oscilación) junto con el sistema de almacenamiento en baterías de segunda vida (`SecondLifeBattery1RC` + `DCLinkBESSPIController` en `MicrogridWithBESSPI`) y su interfaz eléctrica parametrizada hacia el alimentador europeo de baja tensión **IEEE European LV Test Feeder** (906 barras, 416 V línea-línea, 50 Hz).

Se preservan íntegramente las reglas no negociables de `AGENTS.md`:
- Los parámetros del controlador VSG permanecen congelados en $M = 80$ y $D = 1500$.
- El modelo original a **60 Hz** permanece intacto como línea base de regresión de los Objetivos 1 y 2.
- El vector de estados conserva exactamente 12 estados sin BESS (`x[10] = omega`, `x[11] = theta`), 15 estados con BESS y 16 estados con `MicrogridWithBESSPI` (`x[15] = xi_bess_vdc`), integrado mediante un único `solve_ivp` global.
- Para mantener idénticos los puntos nominales de potencia activa ($P_{\text{nom}} = 3000\text{ W}$), factor de potencia en atraso ($\cos\varphi = 0{,}95$) y potencia reactiva ($Q_{\text{nom}} = 986{,}05\text{ var}$) a $110\text{ V}_{\text{LN,rms}}$, `BalancedRLLoad` conserva $R = 10{,}92025\ \Omega$ y escala la inductancia en razón $60/50 = 1{,}20$ ($L_{50} = 11{,}42514\text{ mH}$ frente a $L_{60} = 9{,}52095\text{ mH}$), preservando exactamente $X_{\text{load}} = 3{,}58931\ \Omega$.
- El filtro físico LCL conserva $L_1 = L_2 = 1{,}0\text{ mH}$, $C = 30\ \mu\text{F}$, $R_1 = R_2 = 0{,}05\ \Omega$ y $R_d = 1{,}36\ \Omega$. En consecuencia, la reactancia serie inductiva cae un $16{,}67\ \%$ a 50 Hz ($X_1 = X_2 = 0{,}31416\ \Omega$ frente a $0{,}37699\ \Omega$ a 60 Hz), reduciendo la caída de tensión en el filtro y elevando ligeramente la tensión RMS en el PCC ($107{,}263\text{ V}$ a 50 Hz frente a $106{,}896\text{ V}$ a 60 Hz en régimen nominal).

---

## 2. Fase 1: Auditoría y Regresión Pareada 50 Hz vs. 60 Hz en Horizonte de 6,5 s

El script [`src/validation/validate_vsg_50hz_interface.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/src/validation/validate_vsg_50hz_interface.py) extiende la campaña dinámica a **$t_{\text{end}} = 6{,}5\text{ s}$** con muestreo diagnóstico de $0{,}5\text{ ms}$ y ventanas explícitas:
- **Ventana de arranque en frío AC:** $0{,}0 \le t < 0{,}7\text{ s}$ (corrientes de inductores y tensiones de condensadores LCL nulas en $t = 0$).
- **Ventana preevento:** $0{,}7 \le t < 0{,}8\text{ s}$.
- **Ventana transitoria:** $0{,}8 \le t \le 2{,}0\text{ s}$ (escalón de carga en $t_{\text{step}} = 0{,}8\text{ s}$).
- **Ventana posevento completa:** $0{,}8 \le t \le 6{,}5\text{ s}$.
- **Ventana de régimen permanente (steady-state):** $5{,}5 \le t \le 6{,}5\text{ s}$.

### 2.1 Auditoría de Ventanas de $V_{dc}$ (Inicial vs. Mínimo Global vs. Mínimo Posevento)

En todos los escenarios sin BESS, el bus DC inicia en $V_{dc}(0) = 340{,}0\text{ V}$ con corriente AC nula en el inversor; durante los primeros $0{,}2\text{ s}$, el arreglo FV carga el condensador $C_{dc} = 2\text{ mF}$ hasta su equilibrio preevento ($\approx 379{,}31\text{ V}$ a 60 Hz y $\approx 378{,}93\text{ V}$ a 50 Hz). Por consiguiente:
- En los escenarios **nominal** y **+20 % sin BESS**, el mínimo global en toda la simulación ocurre en el instante inicial: $V_{dc,\text{global,min}} = V_{dc}(0) = 340{,}00\text{ V}$ ($t = 0{,}0\text{ s}$), mientras que el mínimo posterior al escalón ($t \ge 0{,}8\text{ s}$) es $379{,}31 / 378{,}93\text{ V}$ (nominal) y $364{,}76 / 363{,}52\text{ V}$ (+20 %).
- En los escenarios con **BESS+PI**, el lazo PI regula hacia $V_{dc,\text{ref}} = 340{,}0\text{ V}$ absorbiendo el excedente inicial del arreglo FV.

### 2.2 Tabla Comparativa Pareada 60 Hz vs. 50 Hz (Horizonte 6,5 s)

Evidencia reproducible en [`outputs/validation/vsg_50hz_interface_audit_6p5s.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/vsg_50hz_interface_audit_6p5s.json), [`outputs/validation/vsg_50hz_interface_audit_6p5s.csv`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/vsg_50hz_interface_audit_6p5s.csv) y figura [`outputs/validation/vsg_50hz_vs_60hz_6p5s.png`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/vsg_50hz_vs_60hz_6p5s.png).

| $f_0$ [Hz] | Escenario | BESS+PI | Estado | $f_{\text{post,min}}$ [Hz] | $\Delta f_{\max}$ [Hz] | $\|\text{RoCoF}\|_{\max}$ [Hz/s] | $t_{\text{rec}}$ [s] | $V_{dc}(0)$ [V] | $V_{dc,\text{glob,min}}$ [V] | $V_{dc,\text{post,min}}$ [V] | $V_{dc,\text{final}}$ [V] | $V_{\text{PCC,rms}}$ [V] | $P_{\text{PCC,ss}}$ [W] | $m_{\max}$ | Frac. sat. post [%] |
|---:|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 60 | Nominal | No | `PASS` | 60,002718 | 0,000000 | 0,0000 | 0,0000 | 340,00 | 340,00 | 379,31 | 379,31 | 106,90 | 2833,06 | 0,9151 | 0,00 |
| 50 | Nominal | No | `PASS` | 50,002743 | 0,000000 | 0,0000 | 0,0000 | 340,00 | 340,00 | 378,93 | 378,93 | 107,26 | 2852,53 | 0,9151 | 0,00 |
| 60 | +20 % | No | `PASS` | 59,992563 | 0,010155 | 0,9067 | 0,0000 | 340,00 | 340,00 | 364,76 | 364,85 | 106,23 | 3356,77 | 0,9151 | 0,00 |
| 50 | +20 % | No | `PASS` | 49,992210 | 0,010533 | 0,9151 | 0,0000 | 340,00 | 340,00 | 363,52 | 363,65 | 106,68 | 3385,78 | 0,9151 | 0,00 |
| 60 | +40 % | No | `REVIEW` | 59,977593 | 0,025125 | 1,8023 | 0,0000 | 340,00 | 313,86 | 313,86 | 313,92 | 101,16 | 3551,74 | 0,9500 | 98,20 |
| 50 | +40 % | No | `REVIEW` | 49,975679 | 0,027065 | 1,8234 | 0,0000 | 340,00 | 311,52 | 311,52 | 311,59 | 100,92 | 3535,36 | 0,9500 | 98,41 |
| 60 | +20 % | Sí | `PASS` | 59,992563 | 0,010155 | 0,6398 | 0,0000 | 340,00 | 340,00 | 340,86 | 340,94 | 106,23 | 3356,77 | 0,9151 | 0,00 |
| 50 | +20 % | Sí | `PASS` | 49,992210 | 0,010533 | 0,6497 | 0,0000 | 340,00 | 340,00 | 340,78 | 340,85 | 106,68 | 3385,78 | 0,9151 | 0,00 |
| 60 | +40 % | Sí | `PASS` | 59,957933 | 0,044785 | 1,5624 | 0,0000 | 340,00 | 338,24 | 338,24 | 338,79 | 105,60 | 3864,76 | 0,9199 | 0,00 |
| 50 | +40 % | Sí | `PASS` | 49,955753 | 0,046990 | 1,5879 | 0,0000 | 340,00 | 338,11 | 338,11 | 338,64 | 106,12 | 3902,52 | 0,9203 | 0,00 |

### 2.3 Cuantificación Física del `REVIEW` en +40 % sin BESS

A $G = 800\text{ W/m}^2$ y $T_c = 25\ ^\circ\text{C}$, el arreglo FV de 10 módulos en serie presenta:
- Punto de máxima potencia (MPP): $P_{\text{PV,MPP}} = 3972{,}27\text{ W}_{\text{DC}}$ a $V_{\text{MPP}} = 342{,}7\text{ V}$, equivalente a un techo AC de $P_{\text{AC,max}} = \eta_{\text{inv}} P_{\text{PV,MPP}} = 3853{,}10\text{ W}_{\text{AC}}$ ($\eta_{\text{inv}} = 0{,}97$).
- En el umbral de saturación de modulación ($V_{dc,\text{min}} = \frac{2\sqrt{2}\cdot 110}{0{,}95} = 327{,}502\text{ V}$), el arreglo FV entrega $P_{\text{PV}}(327{,}50\text{ V}) = 3869{,}12\text{ W}_{\text{DC}}$ ($3753{,}05\text{ W}_{\text{AC}}$).
- Un escalón nominal de $+40\ \%$ demanda $4200\text{ W}_{\text{AC}}$ a tensión nominal ($\approx 4330\text{ W}_{\text{DC}}$), generando un déficit estructural de **$346{,}9\text{ W}_{\text{AC}}$ respecto al MPP** y **$447{,}0\text{ W}_{\text{AC}}$ en el umbral de modulación**.
- El condensador $C_{dc} = 2\text{ mF}$ almacena únicamente $\Delta E_{C_{dc}} = \frac{1}{2} C_{dc}(V_{dc,\text{pre}}^2 - V_{dc,\text{min}}^2) = 36{,}62\text{ J}$ (60 Hz) y $36{,}33\text{ J}$ (50 Hz) por encima de $327{,}502\text{ V}$, energía que se agota en $\approx 0{,}12\text{ s}$. Tras cruzar $327{,}502\text{ V}$, el índice de modulación se satura en $m_{\max} = 0{,}95$ durante el $98{,}20\ \%$ (60 Hz) y $98{,}41\ \%$ (50 Hz) de la ventana posevento ($100\ \%$ en estado estacionario), reduciendo la tensión PCC a $101{,}16\text{ V}$ (60 Hz) y $100{,}92\text{ V}$ (50 Hz), donde la potencia de la carga R-L de impedancia constante se autolimita a $3551{,}74\text{ W}$ (60 Hz) y $3535{,}36\text{ W}$ (50 Hz). Se conserva el estado `REVIEW` sin alterar $M = 80$ ni $D = 1500$.

---

## 3. Fase 2: Validación Funcional de Soporte por Descarga del BESS a 50 Hz

El script [`src/validation/validate_bess_50hz_discharge.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/src/validation/validate_bess_50hz_discharge.py) demuestra soporte activo por descarga ($i_{\text{bess}} > 0$, $p_{\text{bess,dc}} > 0$) bajo dos perturbaciones físicamente coherentes en 50 Hz:
1. **Escalón severo de carga (+40 %, $3000 \to 4200\text{ W}$ en $t = 0{,}8\text{ s}$ a $G = 800\text{ W/m}^2$):** evaluado para $\text{SoH} \in \{1{,}00;\ 0{,}70;\ 0{,}668182\}$ y contrastado con `bess_enabled=False` bajo condiciones iniciales idénticas de 16 estados.
2. **Caída brusca de irradiancia ($800 \to 400\text{ W/m}^2$ en $t = 0{,}8\text{ s}$ con carga nominal de $3000\text{ W}$):** evaluada con `bess_enabled=True`, `bess_enabled=False` y con límite de potencia reducido a $P_{\text{bess,max}} = 1200\text{ W}$ para excitar dinámicamente la saturación y el anti-windup condicional del PI.

Resultados detallados en [`outputs/validation/bess_50hz_discharge/bess_50hz_discharge_summary.json`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_50hz_discharge/bess_50hz_discharge_summary.json) y figuras [`bess_50hz_step40_discharge_comparison.png`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_50hz_discharge/bess_50hz_step40_discharge_comparison.png) y [`bess_50hz_irradiance_drop_and_saturation.png`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/outputs/validation/bess_50hz_discharge/bess_50hz_irradiance_drop_and_saturation.png).

| Caso ($f_0$, Perturbación, SoH) | BESS | Estado | $i_{\text{bess,post}}$ [mín, máx] [A] | $p_{\text{bess,post,max}}$ [W] | $p_{\text{bess,ss}}$ [W] | $E_{\text{bess,post}}$ [J] | $V_{dc,\text{post,min}}$ [V] | $V_{t,\text{bess,min}}$ [V] | Frac. Sat. PI [%] | Residuo $\Delta E_{C_{dc}}$ [J] |
|:---|:---:|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| 50 Hz, +40 % carga, $\text{SoH}=1{,}00$ | Sí | `PASS` | $[-0{,}974;\ +0{,}844]$ | +285,82 | +285,82 | +1622,01 | 338,11 | 3,7901 | 0,00 | 0,0352 |
| 50 Hz, +40 % carga, $\text{SoH}=0{,}70$ | Sí | `PASS` | $[-0{,}974;\ +0{,}844]$ | +285,82 | +285,82 | +1622,01 | 338,11 | 3,7895 | 0,00 | 0,0352 |
| 50 Hz, +40 % carga, $\text{SoH}=0{,}668$ | Sí | `PASS` | $[-0{,}974;\ +0{,}844]$ | +285,82 | +285,82 | +1622,01 | 338,11 | 3,7895 | 0,00 | 0,0352 |
| 50 Hz, +40 % carga (`bess_enabled=False`) | No | `REVIEW` | $[0{,}000;\ 0{,}000]$ | 0,00 | 0,00 | 0,00 | 311,52 | 3,7917 | 0,00 | 0,0393 |
| 60 Hz, +40 % carga, $\text{SoH}=0{,}668$ | Sí | `PASS` | $[-0{,}993;\ +0{,}727]$ | +246,35 | +246,35 | +1396,87 | 338,24 | 3,7897 | 0,00 | 0,0348 |
| 50 Hz, $G: 800\to 400$, $\text{SoH}=0{,}668$ | Sí | `PASS` | $[-0{,}974;\ +3{,}645]$ | +1219,88 | +1218,82 | +6916,78 | 332,68 | 3,7837 | 0,00 | 0,0354 |
| 50 Hz, $G: 800\to 400$ (`bess_enabled=False`) | No | `REVIEW` | $[0{,}000;\ 0{,}000]$ | 0,00 | 0,00 | 0,00 | 220,60 | 3,7917 | 0,00 | 0,0119 |
| 50 Hz, $G: 800\to 400$, $P_{\max}=1200\text{ W}$ | Sí | `PASS` | $[-0{,}974;\ +3{,}631]$ | +1200,00 | +1200,00 | +6830,82 | 330,49 | 3,7837 | 87,38 | 0,0355 |

- **Límite de interpretación arquitectónica (`REVIEW` por escala $V_{dc}/V_{t,\text{bess}}$):** La relación $V_{dc} / V_{t,\text{bess}} \approx 89{,}4$ ($338{,}64\text{ V} / 3{,}7895\text{ V}$) se mantiene explícitamente documentada como advertencia de interpretación (`REVIEW`), dado que `MicrogridWithBESSPI` acopla $i_{\text{bess}} = p_{\text{ref}}/V_{dc}$ directamente al par de celdas 2p Nissan Leaf sin un banco serie-paralelo $N_s \times N_p$ ni convertidor DC/DC bidireccional activo.

---

## 4. Fases 3 y 4: Interfaz de Transformación 190,53 V / 416 V (50 Hz) y Escenarios QSTS 24 h en OpenDSS

El script [`scripts/ieee_europe_lv_906_interface_and_qsts.py`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/scripts/ieee_europe_lv_906_interface_and_qsts.py) implementa y evalúa la interfaz de elevación bajo hipótesis explícitas de diseño ($a = 416 / 190{,}5256 = 2{,}183434$, $S_{\text{ref}} = 5\text{ kVA}$, $I_{\text{nom,190V}} = 15{,}1515\text{ A}$, $I_{\text{nom,416V}} = 6{,}9393\text{ A}$) y ejecuta los escenarios cuasiestáticos de 24 horas (1440 pasos de 1 minuto) manteniendo estricta separación temporal respecto a las simulaciones ODE de 6,5 s.

### 4.1 Sensibilidad del Transformador e Interacción con el Desequilibrio de Red (Mediodía $t = 720\text{ min}$, $P_{\text{DER}} = 3{,}0\text{ kW}$)

| Hipótesis | Conexión (Inv / Red) | $r_k$ [%] | $x_k$ [%] | $z_k$ [%] | Barra | $P_{\text{red,416V}}$ [kW] | $\Delta P_{\text{Cu,xfmr}}$ [W] | $P_{\text{fases,416V}}$ (A / B / C) [kW] | $I_{0,\text{416V}}$ [A] |
|:---|:---:|---:|---:|---:|:---:|---:|---:|:---:|---:|
| `H0_direct_416v` | Directo (PQ ideal) | 0,0 | 0,0 | 0,00 | 822 | 3,0000 | 0,00 | 1,000 / 1,000 / 1,000 | 0,0000 |
| `H1_YNyn0_low_z` | `wye` / `wye` | 1,2 | 3,0 | 3,23 | 822 | 2,9804 | 19,59 | 0,993 / 0,994 / 0,993 | 0,0067 |
| `H2_YNyn0_nominal` | `wye` / `wye` | 1,5 | 4,0 | 4,27 | 822 | 2,9755 | 24,49 | 0,992 / 0,992 / 0,992 | 0,0051 |
| `H3_YNyn0_high_z` | `wye` / `wye` | 2,0 | 6,0 | 6,32 | 822 | 2,9673 | 32,65 | 0,989 / 0,990 / 0,989 | 0,0034 |
| `H4_Dyn_trap` | `delta` / `wye` | 1,5 | 4,0 | 4,27 | 822 | 2,9752 | 24,83 | **0,919 / 1,133 / 0,923** | **0,5718** |
| `H5_Ynd_isolated` | `wye` / `delta` | 1,5 | 4,0 | 4,27 | 822 | 2,9755 | 24,52 | 0,996 / 0,995 / 0,985 | **0,0000** |

> **Hallazgo físico crítico sobre conexión de devanados:** En la barra lejana 822 (fuertemente desequilibrada por cargas monofásicas), un transformador `Dyn` (delta en el inversor / estrella aterrada en 416 V, `H4`) actúa como sumidero de secuencia cero para la red, absorbiendo $I_0 = 0{,}5718\text{ A}$ en el lado de 416 V y distorsionando la inyección por fase a $0{,}919 / 1{,}133 / 0{,}923\text{ kW}$. Por el contrario, `YNyn0` (`H2`) o `Ynd` (`H5`) bloquean o limitan la circulación de secuencia cero ($I_0 \le 0{,}0051\text{ A}$) y preservan la inyección equilibrada ($\approx 0{,}992\text{ kW/fase}$).

### 4.2 Escenarios Cuasiestáticos de 24 Horas (QSTS, 1440 minutos)

| Escenario | Barra | Xfmr 5 kVA (`H2`) | Perfil BESS | $E_{\text{DER,net}}$ [kWh] | $E_{\text{import}}$ [kWh] | $E_{\text{loss,red}}$ [kWh] | $E_{\text{loss,xfmr}}$ [kWh] | $\Delta E_{\text{loss,red}}$ vs. Base [%] | $V_{\text{822,min/max}}$ (Fase A) [pu] |
|:---|:---:|:---:|:---:|---:|---:|---:|---:|---:|:---:|
| `base_no_dg` | — | No | No | 0,000 | 522,373 | 5,0627 | 0,0000 | 0,00 % | 0,9827 / 1,0498 |
| `pv_near_34_direct` | 34 | No | No | 22,918 | 499,400 | 5,0079 | 0,0000 | -1,08 % | 0,9827 / 1,0498 |
| `pv_far_822_direct` | 822 | No | No | 22,918 | 499,206 | 4,8136 | 0,0000 | -4,92 % | 0,9827 / 1,0548 |
| `pv_near_34_xfmr_5kva` | 34 | Sí | No | 22,918 | 499,547 | 5,0085 | 0,1466 | -1,07 % | 0,9827 / 1,0498 |
| `pv_far_822_xfmr_5kva` | 822 | Sí | No | 22,918 | 499,354 | 4,8165 | 0,1455 | -4,86 % | 0,9827 / 1,0548 |
| `pv_bess_near_34_xfmr_5kva` | 34 | Sí | Sí | 22,545 | 499,872 | 5,0016 | 0,1069 | -1,21 % | 0,9831 / 1,0498 |
| `pv_bess_far_822_xfmr_5kva` | 822 | Sí | Sí | 22,545 | 499,553 | 4,7880 | 0,1062 | **-5,43 %** | **0,9897** / 1,0525 |

---

## 5. Estado de Validación y Regresiones

- `py -3.14 src/validation/validate_vsg_50hz_interface.py`: **PASS** (10 escenarios a 6,5 s ejecutados; +40 % sin BESS documentado en `REVIEW`).
- `py -3.14 src/validation/validate_bess_50hz_discharge.py`: **PASS** (demostración de descarga real $i_{\text{bess}} > 0$, saturación PI, anti-windup y balance energético exacto).
- `py -3.12 scripts/ieee_europe_lv_906_interface_and_qsts.py`: **PASS** (sensibilidad de transformador `H1`–`H5` y 7 escenarios QSTS de 24 h).
- `py -3.14 src/validation/audit_scientific_consistency_phase5.py`: **PASS** (6 `PASS`, 2 `REVIEW` documentados, 1 `BLOCKED` por datos experimentales/catálogo pendientes, 0 `FAIL`).
- Para el informe integral de cierre de las 6 fases, consúltese [`docs/informe_integracion_vsg50_bess_ieee906.md`](file:///G:/OneDrive%20-%20Universidad%20Nacional%20de%20Colombia/microgrid_vsm_ieee906/docs/informe_integracion_vsg50_bess_ieee906.md).
