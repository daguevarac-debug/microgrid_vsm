# Fuentes científicas verificadas para los pendientes del Objetivo 2

- **Repositorio:** `daguevarac-debug/microgrid_vsm`
- **Rama de trabajo:** `audit/obj2-review-closure` (base `104230baefd7286fc238111e452e3c618c2ea111`, cadena PR #57 → PR #58 → PR #59)
- **Complemento directo de:** [`docs/bat26-49-source-evidence-matrix.md`](bat26-49-source-evidence-matrix.md) y [`docs/auditoria_integral_review_objetivo2.md`](auditoria_integral_review_objetivo2.md)

---

## 1. Criterio metodológico y prohibiciones de transferencia

Este documento compila publicaciones científicas verificadas (DOI, autores, revista, año, método, ecuaciones, montaje, resultados y unidades) orientadas específicamente a fundamentar los pendientes del Objetivo 2 que permanecen en estado `REVIEW`, `BLOCKED_DATOS` o `FUERA_DE_ALCANCE`. No duplica las referencias ya auditadas en [`docs/bat26-49-source-evidence-matrix.md`](bat26-49-source-evidence-matrix.md) (Braco 2020/2021/2023, Tran 2021, Cheng 2023, Collath 2022, Schade & Egging-Bratseth 2024, Nguyen 2025, Wang 2025).

### Regla estricta de no-mezcla de químicas ni escalas

1. **Prohibición de mezcla química:** Los parámetros identificados para celdas LFP, NCM/C comerciales o pouch NCM/LMO de otras generaciones **no** pueden transferirse directamente al modelo de tesis de segunda vida (`LMO/NMC` Nissan Leaf) sin recalibración sobre ensayos de la unidad identificada.
2. **Prohibición de mezcla de escalas:** Queda prohibido trasladar sin escalado físico explícito parámetros entre:
   - **celda individual** (`1s1p`, ~3.7 V, ~32–33 Ah en Leaf Gen 1),
   - **pareja en paralelo `2p`** (~3.75 V, 66 Ah nominal en Braco 2020/2023; `MicrogridWithBESSPI`),
   - **módulo `2s2p`** (~7.5 V nominal, 8.4 V máx., 66 Ah), y
   - **banco completo `48×2s2p`** (`96s2p`, ~360 V nominal, 403.2 V máx., ~24 kWh nominales; `MicrogridWithBESSDCDC`).
   El escalado de tensión (`N_s`), corriente (`N_p`), resistencia interna (`R_banco = (N_s / N_p)·R_celda` + barras/contactos) y dispersión celda-a-celda debe declararse explícitamente y validarse antes de cerrar cualquier estado `BLOCKED_DATOS`.
3. **Separación de naturaleza de evidencia:** Toda ficha distingue explícitamente entre **datos experimentales**, **resultados de simulación** e **hipótesis de tesis**, así como entre **bibliografía que respalda una metodología o arquitectura** frente a **evidencia que valida parámetros específicos del proyecto**. Ninguna de las nueve fuentes listadas valida directamente los parámetros específicos de hardware de la tesis; todas respaldan metodología, criterios de diseño, normativa o fenomenología de referencia.
4. **Verificación de metadatos y DOI:** Los ocho DOI (`F-01` a `F-08`) y las referencias normativas (`F-09`) fueron verificados contra registros editoriales e institucionales (MDPI, Elsevier/ScienceDirect, Cell Press/Stanford, MPCE/idUS y normativa UE/IEC/CENELEC).

---

## 2. Mapa rápido de fuentes frente a pendientes del Objetivo 2

| ID Fuente | Referencia | DOI / Norma | Evidencia principal | Tipo de respaldo en la tesis | Pendiente(s) de Objetivo 2 que fundamenta |
| --- | --- | --- | --- | --- | --- |
| **F-01** | Cui et al. (2024), *Cell Reports Physical Science* | `10.1016/j.xcrp.2024.101941` | Experimental (15 meses, 8 celdas SLB, dataset abierto OSF `fns57`) | **Metodología y benchmark externo** (NO valida parámetros de Leaf `2p` de la tesis) | `P-10` (calibración de envejecimiento SLB y validación predictiva de `k_deg`, `k_R`, BLAST-Lite) |
| **F-02** | Zhang et al. (2023), *Batteries* | `10.3390/batteries9010001` | Experimental (HPPC FreedomCAR en celda NCM/C a 20 °C) | **Metodología de identificación 1-RC** (NO valida `R0`, `R1`, `C1` de Leaf `2p`) | `P-10` (identificación 1-RC vs. 2-RC y efecto del intervalo de muestreo en `R0`, `R1`, `C1`) |
| **F-03** | Ren et al. (2023), *Energies* | `10.3390/en16124789` | Simulación (MATLAB/Simulink, 50 kW, 380 V AC / 800 V DC) | **Metodología de sintonización / control** (NO valida ganancias `M=80`, `D=1500` de 3 kW) | `P-06` (selección y justificación de `M`, `D`, relación de amortiguamiento y futuro control adaptativo / Obj. 3) |
| **F-04** | Choi et al. (2022), *Energies* | `10.3390/en15134559` | Simulación PSIM + prototipo experimental de laboratorio (25 kW / 50 kWh) | **Arquitectura y umbrales de referencia OVP/UVLO** (NO valida hardware de la tesis) | `P-07`, `P-08` (regulación autónoma de subtensión/sobretensión en bus DC y desconexión por falla) |
| **F-05** | Gao et al. (2024), *eTransportation* | `10.1016/j.etran.2024.100313` | Experimental (>100 packs Nissan Leaf Gen 1 retirados + 4200 ciclos) | **Fenomenología de referencia Leaf Gen 1** (NO sustituye ensayos de la unidad específica de tesis) | `P-09`, `P-10` (dispersión de SoH, desbalance `ΔV` entre celdas y envejecimiento específico de Leaf Gen 1) |
| **F-06** | Matas-Díaz et al. (2025), *J. Mod. Power Syst. Clean Energy* | `10.35833/MPCE.2024.000316` | Análisis analítico de pequeña señal + validación experimental | **Metodología de estabilidad de pequeña señal** (NO valida estabilidad global del modelo de 16 estados) | `P-05`, `P-06` (estabilidad de pequeña señal de VSG con filtro LCL y sintonización sistemática de ganancias) |
| **F-07** | Gao et al. (2024), *Sustainable Energy, Grids and Networks* | `10.1016/j.segan.2024.101308` | Análisis de pequeña señal + simulación / validación | **Metodología de amortiguamiento VSG** (NO valida ganancias del proyecto) | `P-05`, `P-06`, `P-12` (amortiguamiento y estabilidad en sistemas VSG con parámetros coordinados) |
| **F-08** | Shadoul et al. (2022), *Energies* | `10.3390/en15228406` | Revisión sistemática (topologías, órdenes de control, BESS) | **Marco conceptual y taxonomía VSG** (NO aporta validación paramétrica) | `P-05`, `P-06`, `P-12` (marco comparativo de orden de modelo VSG, lazos internos y papel del almacenamiento) |
| **F-09** | Reglamento (UE) 548/2014 + IEC 60076-1 / EN 50588-1:2017 | Normativa UE / IEC / CENELEC | Marco normativo de pérdidas en vacío (`P0`) y carga (`Pk`) | **Marco normativo de definición de pérdidas** (NO sustituye hoja de datos de un transformador de 5 kVA específico) | `P-11` (sustitución de hipótesis `P0 = 0` en transformador de 5 kVA en IEEE 906) |

---

## 3. Fichas detalladas de publicaciones obligatorias

### F-01 — Cui et al. (2024): Envejecimiento experimental y estimación de SoH en baterías de segunda vida

- **Referencia completa:** Xiaofan Cui, Muhammad Aadil Khan, Gabriele Pozzato, Surinder Singh, Ratnesh Sharma, Simona Onori (2024). *Taking second-life batteries from exhausted to empowered using experiments, data analysis, and health estimation*. *Cell Reports Physical Science*, 5(5), 101941.
- **DOI:** `https://doi.org/10.1016/j.xcrp.2024.101941` (preprint `arXiv:2402.18859`; dataset abierto en OSF `https://osf.io/fns57/`).
- **Naturaleza de la evidencia:** **Datos experimentales** (campaña de 15 meses) + algoritmos de estimación de salud basados en datos.
- **Método y montaje experimental:**
  - Ensayo de 8 celdas pouch de segunda vida retiradas de vehículos eléctricos (química NCM/grafito de otro fabricante/formato respecto a la pareja Leaf 2p de la tesis), sometidas durante 15 meses a un perfil sintético de almacenamiento estacionario conectado a red en la ventana **3.0–4.0 V** (evitando los extremos de tensión típicos de tracción EV).
  - Caracterizaciones periódicas (RPT) para seguimiento de capacidad efectiva, resistencia interna y firmas de degradación; partición de entrenamiento/validación para regresión Elastic Net (ENR) y agrupamiento adaptativo (*adaptive clustering*).
- **Resultados y unidades verificadas:**
  - Estimación de SoH por ENR con error porcentual absoluto medio **`MAPE < 2.3 %`** en el conjunto de prueba.
  - Con agrupamiento adaptativo, el error porcentual máximo en la celda 2.4 bajó de **`2.7 %`** (modelo *offline*) a **`1.55 %`**.
  - Demuestra empíricamente que las celdas retiradas con historial heterogéneo presentan trayectorias no lineales y dispersión significativa incluso bajo idéntico protocolo estacionario.
- **Limitaciones y restricciones de uso en la tesis:**
  - Las 8 celdas no son parejas `2p` de Nissan Leaf Gen 1 (`66 Ah`), por lo que sus curvas de capacidad y resistencia **no pueden sustituir** las mediciones físicas de una pareja Leaf identificada.
  - En la tesis (`docs/bat26-49-source-evidence-matrix.md`), el dataset OSF `fns57` está identificado pero aún no descargado ni ingerido en `src/bess/`.
- **Prerrequisitos para adoptar en la tesis (`P-10`):** Descargar y verificar integridad (SHA-256) del dataset OSF `fns57`, utilizarlo únicamente como **benchmark externo de metodología** para validar la arquitectura de identificación de `k_deg`/`k_R` y calibración de `SoH(z_deg)`, declarando explícitamente la diferencia de química y formato respecto al banco `48×2s2p` Leaf.

---

### F-02 — Zhang et al. (2023): Efecto del intervalo de muestreo en la identificación de modelos 1-RC y 2-RC mediante HPPC

- **Referencia completa:** Hehui Zhang, Chang Deng, Yutong Zong, Qingsong Zuo, Haipeng Guo, Shuai Song, Liangxing Jiang (2023). *Effect of Sample Interval on the Parameter Identification Results of RC Equivalent Circuit Models of Li-ion Battery: An Investigation Based on HPPC Test Data*. *Batteries*, 9(1), 1.
- **DOI:** `https://doi.org/10.3390/batteries9010001`.
- **Naturaleza de la evidencia:** **Datos experimentales** (ensayo HPPC de laboratorio) + identificación paramétrica por mínimos cuadrados no lineales.
- **Ecuaciones clave:**
  - Modelo 1-RC (Thevenin de primer orden, equivalente estructural a `src/bess/model.py`):
    $$V_t(t) = \mathrm{OCV}(\mathrm{SoC}) - I(t) R_0 - V_{rc}(t), \qquad \frac{dV_{rc}}{dt} = -\frac{V_{rc}}{R_1 C_1} + \frac{I}{C_1}$$
  - Modelo 2-RC (dos ramas de polarización en serie con constantes de tiempo $\tau_1 = R_1 C_1$ y $\tau_2 = R_2 C_2$).
- **Montaje experimental:**
  - Celda prismática comercial NCM/C (`1s1p`), cámara térmica controlada a **20 °C ± 1 °C**.
  - Protocolo **FreedomCAR HPPC**: pulsos de descarga y carga de **10 s a 1C**, con **40 s de reposo**, evaluados de `SoC = 0.1` a `1.0` en pasos de `0.1`, muestreo base a **10 Hz** (`Δt = 0.1 s`), submuestreado a **`Δt = 0.1, 0.2, 0.5 y 1.0 s`**.
- **Resultados y unidades verificadas:**
  - El modelo **1-RC** mantiene **`RMSE < 2.0 mV`** y **`R² > 0.99`** en todo el rango de `SoC` para los cuatro intervalos de muestreo (`0.1–1.0 s`), mostrando robustez de identificabilidad.
  - El modelo **2-RC** pierde identificabilidad cuando **`Δt ≥ 0.5 s`**, degradándose hasta **`RMSE = 8.09 mV`** y error máximo de **`19.61 mV`** en `SoC = 0.4`.
- **Limitaciones y restricciones de uso en la tesis:**
  - Celda nueva NCM/C a 20 °C (no SLB Nissan Leaf `2p` ni envejecida). Sus valores numéricos de `R0`, `R1`, `C1` **no** deben copiarse a `src/config.py`.
- **Aporte directo y prerrequisitos (`P-10`):** Respalda metodológicamente la elección del modelo **Thevenin 1-RC** en `src/bess/model.py` frente a 2-RC cuando los registros disponibles o el paso de adquisición son moderados (`≥ 0.5 s`), y fija el requisito mínimo de frecuencia de muestreo (`≥ 2–10 Hz`) para futuros ensayos HPPC sobre módulos Leaf 2p.

---

### F-03 — Ren et al. (2023): Control adaptativo de VSG con coordinación multiparamétrica (`J`, `D`, `K_P`)

- **Referencia completa:** Bixing Ren, Qiang Li, Zhiyuan Fan, Yichao Sun (2023). *Adaptive Control of a Virtual Synchronous Generator with Multiparameter Coordination*. *Energies*, 16(12), 4789.
- **DOI:** `https://doi.org/10.3390/en16124789`.
- **Naturaleza de la evidencia:** **Simulación** (MATLAB/Simulink, modo conectado a red). No incluye validación experimental en hardware.
- **Ecuaciones clave:**
  - Ecuación de oscilación de segundo orden con inercia virtual $J$, amortiguamiento $D$ y estatismo activo $K_P$:
    $$J \omega_N \frac{d\omega}{dt} = P_{\mathrm{ref}} - P_e - D(\omega - \omega_N) - K_P(\omega - \omega_N)$$
  - Relación de amortiguamiento óptima de segundo orden ("sistema óptimo de Siemens", $\xi = 0.707$) vinculando dinámicamente $J$, $D$ y $K_P$ en cuatro etapas del transitorio según el signo de $\Delta\omega \cdot (d\omega/dt)$ (aceleración $> 0$ vs. desaceleración $< 0$).
  - Cotas analíticas de diseño de $J_{\max}$, $D_{\min}$ y $K_P$ a partir de $P_{\max}$, $P_{\min}$ y la banda admisible de frecuencia ($50 \pm 0.2\text{ Hz}$).
- **Configuración de simulación y resultados verificados:**
  - Sistema trifásico: `U_g = 380 V`, `U_dc = 800 V`, `P_nom = 50 kW`, `Q_nom = 0 var`, `L_abc = 0.8 mH`, `C_abc = 10 µF`, `J_0 = 1.127 kg·m²`, `K_P0 = 5000`; escalón de carga de `+10 kW` en `t = 1 s` (duración `2 s`) y perturbación de frecuencia de red `+0.2 Hz`.
  - Ante `+10 kW`: con parámetros fijos ($\xi = 0.707$) el nadir fue **`49.83 Hz`** (`Δf = 0.17 Hz`, tiempo de ajuste `0.30 s`); con control adaptativo coordinado multiparamétrico el nadir mejoró a **`49.877 Hz`** (`Δf = 0.123 Hz`, mejora de `27.65 %`, tiempo de ajuste `0.22 s`, mejora de `26.67 %`).
- **Limitaciones y restricciones de uso en la tesis:**
  - Operación **conectada a red** a 50 kW con bus DC rígido (`800 V`), sin modelado de déficit de potencia FV ni dinámica del bus DC ni BESS.
  - Por tanto, sus ganancias numéricas (`J_0`, `D`, `K_P0`) **no** son transferibles a la microrred aislada de `3 kW / 340 V DC` de esta tesis.
- **Aporte directo y prerrequisitos (`P-06`, `P-12`):** Fundamenta la crítica documentada en el Objetivo 2 sobre las limitaciones de parámetros fijos `M = 80`, `D = 1500` seleccionados en frontera de malla finita, y provee un criterio analítico ($\xi \in (0.7, 1)$ y normalización por potencia nominal $S_{\mathrm{base}}$) para la futura etapa comparativa del Objetivo 3 (VSG clásico vs. adaptativo / FOVIC).

---

### F-04 — Choi et al. (2022): Regulación autónoma de subtensión y sobretensión del bus DC mediante ESS distribuidos

- **Referencia completa:** Jung-Sik Choi, Seung-Yeol Oh, Dae-Seak Cha, Byoung-Sun Ko, Mina Kim (2022). *Autonomous DC-Bus Voltage Regulation in DC Microgrid Using Distributed Energy Storage Systems*. *Energies*, 15(13), 4559.
- **DOI:** `https://doi.org/10.3390/en15134559`.
- **Naturaleza de la evidencia:** **Simulación (PSIM) + validación experimental** en prototipo de laboratorio.
- **Método y lógica de protección/regulación:**
  - Interfaz bidireccional de 4 ramas entrelazadas (*four-legged interleaved bidirectional half-bridge*, desfase de 90°) acoplada a un bus DC bipolar.
  - Banda normal de operación: **`±4 %`** de la tensión nominal del bus DC.
  - Banda de regulación autónoma (sin comunicación externa): entre **`±4 %` y `±10 %`**, con ventana de verificación estacionaria de **`10 ms`**, rampa de corriente de **`10 A/s`** (descarga ante subtensión, carga ante sobretensión) y tiempo de estabilización de **`10 s`**.
  - **Umbrales de falla (UVLO / OVP):** **`±10 %`** de la tensión nominal del bus DC; al superarse, la interfaz desconecta el ESS del bus DC para evitar propagación de falla.
  - Algoritmo previo de satisfacción de SoC (*prior SoC satisfaction*) en coordinación con el BMS antes de entrar en modo de regulación de tensión.
- **Montaje experimental y resultados verificados:**
  - Prototipo de laboratorio: batería `50 kWh`, interfaz bidireccional `25 kW`, simulador FV `60 kW`, simulador de red DC `50 kW`, carga DC `60 kW`.
  - Verificación experimental de recuperación ante subtensión por pico de carga, recuperación ante sobretensión por exceso FV y desconexión segura tanto en secuencia de carga como de descarga al cruzar `±10 %`.
- **Limitaciones y restricciones de uso en la tesis:**
  - Enfoque de microrred DC bipolar de 25–60 kW con estudio cualitativo del dimensionamiento (los propios autores señalan pendiente el diseño cuantitativo general de capacidad).
- **Aporte directo y prerrequisitos (`P-07`, `P-08`):** Respalda la necesidad arquitectónica identificada en esta auditoría de incorporar **protección simétrica de sobretensión de bus DC (OVP / curtailment FV / freno resistivo)** complementaria al `v_uvlo = 200 V` ya existente en [`src/controllers/gfm_controller.py`](../src/controllers/gfm_controller.py), así como la coordinación explícita con los límites de `SoC` (`0.10–0.90`) para cuando la batería alcance `soc_max = 0.90` o quede deshabilitada.

---

## 4. Publicaciones complementarias verificadas (2022–2025 y normativa)

### F-05 — Gao et al. (2024): Evaluación experimental de packs Nissan Leaf Gen 1 en segunda vida

- **Referencia completa:** Wei Gao, Zhi Cao, Naser Vosoughi Kurdkandi, Yuhong Fu, Chris Mi (2024). *Evaluation of the second-life potential of the first-generation Nissan Leaf battery packs in energy storage systems*. *eTransportation*, 20, 100313.
- **DOI:** `https://doi.org/10.1016/j.etran.2024.100313`.
- **Naturaleza de la evidencia:** **Datos experimentales** sobre >100 packs retirados de Nissan Leaf Gen 1 + ensayos de ciclado acelerado (4200 ciclos, 100 % DoD, 0.5C en dos celdas retiradas).
- **Resultados y unidades verificadas:**
  - El SoH medido en más de 100 packs Nissan Leaf Gen 1 retirados se concentra en **60–67 %** de capacidad remanente.
  - Criterio empírico de balance entre celdas: **`ΔV < 50 mV`** indica buen balance; **`ΔV > 100 mV`** indica desbalance severo o falla incipiente.
  - Proyección de vida útil estacionaria de **12–20 años** manteniendo el pack completo para preservar consistencia frente al desensamble.
- **Aporte directo (`P-09`, `P-10`):** Directamente alineado con la química y arquitectura `48×2s2p` (`24 kWh` nominales) de [`src/microgrid_bess_dcdc.py`](../src/microgrid_bess_dcdc.py). Justifica cuantitativamente por qué el supuesto de banco homogéneo balanceado de la tesis (`MicrogridWithBESSDCDC`) requiere, antes de validación experimental, modelar dispersión de `SoH` y límites de desbalance `ΔV` entre módulos.

### F-06 — Matas-Díaz et al. (2025): Análisis sistemático de pequeña señal de VSG con filtro LCL

- **Referencia completa:** Francisco Jesús Matas-Díaz, Manuel Barragán-Villarejo, José María Maza-Ortega (2025). *A Systematic Small-Signal Analysis Procedure for Improving Synchronization Stability of Grid-Forming Virtual Synchronous Generators*. *Journal of Modern Power Systems and Clean Energy*, 13(1), 102–114.
- **DOI:** `https://doi.org/10.35833/MPCE.2024.000316`.
- **Naturaleza de la evidencia:** **Modelo analítico linealizado en marco `dq`** (VSC trifásico con filtro LCL amortiguado en serie) + **validación experimental**.
- **Aporte directo (`P-05`, `P-06`):** Contrasta explícitamente implementaciones S-VSG (ecuación de oscilación) y PI-VSG con y sin lazos internos de tensión/corriente (OCL/ICL). Sirve como referencia metodológica para separar los modos electromecánicos rápidos del filtro LCL/VSG respecto a estados lentos no periódicos (`soc_bess`, `zdeg_bess`, `xi_bess_vdc`) en el análisis de estabilidad de 16 estados (`P-05`), y para justificar la incorporación futura de lazos internos y control Q-V (`P-12`).

### F-07 — Gao et al. (2024): Control adaptativo con amortiguamiento mutuo para VSG

- **Referencia completa:** Xian Gao, Dao Zhou, Amjad Anvari-Moghaddam, Frede Blaabjerg (2024). *An adaptive control strategy with a mutual damping term for paralleled virtual synchronous generators system*. *Sustainable Energy, Grids and Networks*, 38, 101308.
- **DOI:** `https://doi.org/10.1016/j.segan.2024.101308`.
- **Naturaleza de la evidencia:** **Análisis modal de pequeña señal y validación dinámica**.
- **Aporte directo (`P-05`, `P-06`, `P-12`):** Fundamenta la interacción entre amortiguamiento virtual, estabilidad oscilatoria y futura extensión a múltiples inversores formadores de red o control adaptativo en el Objetivo 3.

### F-08 — Shadoul et al. (2022): Revisión integral de topologías, órdenes de control y almacenamiento en VSG

- **Referencia completa:** Myada Shadoul, Razzaqul Ahshan, Rashid S. AlAbri, Abdullah Al-Badi, Mohammed Albadi, Mohsin Jamil (2022). *A Comprehensive Review on a Virtual-Synchronous Generator: Topologies, Control Orders and Techniques, Energy Storages, and Applications*. *Energies*, 15(22), 8406.
- **DOI:** `https://doi.org/10.3390/en15228406`.
- **Naturaleza de la evidencia:** **Revisión bibliográfica sistemática**.
- **Aporte directo (`P-05`, `P-06`, `P-12`):** Clasifica los modelos VSG por orden (2.º orden reducido vs. modelos con lazos internos y almacenamiento) y justifica por qué un VSG de 2.º orden sin lazo de corriente/tensión ni soporte energético del lado DC requiere respaldo de almacenamiento (`BESS`) ante escalones severos de carga (`P-04`).

### F-09 — Normativa europea e internacional para pérdidas de transformadores de distribución (`P0`, `Pk`)

- **Referencias normativas:**
  - **Reglamento (UE) n.º 548/2014 de la Comisión** (y modificación **Reglamento (UE) 2019/1783**): requisitos de diseño ecológico (Tier 1 2015, Tier 2 julio 2021) aplicables a transformadores de potencia ≥ 1 kVA a 50 Hz.
  - **IEC 60076-1** (*Power transformers — Part 1: General*) y **EN 50588-1:2017** (*Medium power transformers 50 Hz, with highest voltage for equipment not exceeding 36 kV*).
- **Naturaleza de la evidencia:** **Marco normativo y definiciones físicas estándar** (`P0` pérdidas en vacío en núcleo energizado 24/7; `Pk` pérdidas en carga $I^2 R$ referidas a potencia nominal `Sr`).
- **Aporte directo (`P-11`):** Justifica por qué el supuesto `P0 = 0` usado en el transformador de interfaz de `5 kVA` del estudio IEEE European LV 906 (`PR #57` y `PR #59`) es una **hipótesis exploratoria de sensibilidad** que subestima las pérdidas diarias constantes en vacío (24 h × `P0`), y define los datos mínimos de placa requeridos (`Sr`, `P0`, `Pk`, `uk %`) de un fabricante comercial para cerrar `P-11`.
