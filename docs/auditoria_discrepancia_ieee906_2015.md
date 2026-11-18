# Auditoría Científica: Causa Raíz de la Discrepancia del 9,54 % en el Benchmark IEEE European LV (906 Barras)

- **Fecha:** 2026-11-18
- **Rama base de referencia:** `integration/obj2-pr55-pr56-validated` (PR #57, commit `740a704`)
- **Rama de auditoría:** `audit/scientific-pending-review`
- **Dictamen:** **PASS (Causa raíz identificada y reproducida cuantitativamente; discrepancia reducida de 9,5393 % a 0,0438 % en $P$ y 0,0002 % en $V$)**

---

## 1. Resumen Ejecutivo

La comparación previa entre nuestra reproducción del alimentador **IEEE European Low Voltage Test Feeder** (906 barras, 55 cargas monofásicas, 50 Hz) y las Tablas II y III del informe oficial IEEE PES de mayo de 2015 presentaba una discrepancia máxima de **9,5393 %** en potencia activa por fase en el secundario del transformador `TR1` (y **9,4139 %** en potencia reactiva), manteniéndose en estado `REVIEW` en [`docs/ieee_europe_lv_906_reference_audit.md`](ieee_europe_lv_906_reference_audit.md).

La presente auditoría demuestra cuantitativamente que **la causa raíz exacta del 9,54 % no reside en los perfiles de carga, ni en la topología, ni en las impedancias de línea, ni en la resistencia del transformador, sino en la interacción entre la tensión nominal de las cargas (`kV=0.23`), la tensión de cabecera (`pu=1.05` sobre `416 V`), y el parámetro por defecto `Vmaxpu = 1.05` del modelo `Load` (`Model=1`) en OpenDSS**:

1. El transformador de subestación `TR1` (`11 / 0,416 kV`) tiene una base secundaria fase-neutro de $416 / \sqrt{3} = 240{,}178\text{ V}$. Con `Vsource.Source pu=1.05`, la tensión en vacío en cabecera LV es **$252{,}19\text{ V}$**.
2. Las 55 cargas en `Loads.txt` están declaradas con **`kV=0.23`** ($230\text{ V}$ fase-neutro) y **`Model=1`** (potencia constante $P + jQ$), sin especificar `Vmaxpu`.
3. Sobre la base de carga de $230\text{ V}$, la tensión de operación normal ($251\text{–}255\text{ V}$) equivale a **$1{,}091\text{–}1{,}107\text{ pu}$**, superando el límite por defecto de OpenDSS **`Vmaxpu = 1.05`** ($1{,}05 \times 230 = 241{,}50\text{ V}$).
4. Al superar $241{,}50\text{ V}$, OpenDSS conmuta automáticamente las cargas de potencia constante a **impedancia constante** ($P \propto V^2$), incrementando la potencia absorbida en $\approx (252{,}16 / 241{,}50)^2 \approx +9{,}0\ \%$ en vacío/baja carga y hasta $+9{,}54\ \%$ en la fase C a las `09:26` ($V_{\max} = 254{,}73\text{ V}$), mientras que en la fase B a las `09:26` (alta carga, $V_{\min} = 238{,}42\text{ V} < 241{,}50\text{ V}$) el error era de apenas $+0{,}42\ \%$.
5. Al elevar únicamente `Vmaxpu=1.20` (`batchedit load..* vmaxpu=1.20`) para preservar el comportamiento de **potencia constante pura (`Model=1`)** en todo el rango operativo del alimentador, el error máximo respecto a las Tablas II y III de IEEE 2015 cae de **9,5393 % a 0,0438 %** en potencia activa (`0,00377 kW`, y `0,00084 kW` con `tolerance=1e-8`), de **9,4139 % a 0,0906 %** en potencia reactiva, y a **0,00045 V (0,00018 %)** en tensiones máximas y mínimas por fase.

---

## 2. Metodología Reproducible y Archivos Examinados

### 2.1 Archivos de código y documentación auditados
- [`docs/ieee_europe_lv_906_reference_audit.md`](ieee_europe_lv_906_reference_audit.md): informe previo de auditoría de paridad de fuentes y sensibilidad (`UseActual`, `%Rs`).
- [`scripts/ieee_europe_lv_906_study.py`](../scripts/ieee_europe_lv_906_study.py): descarga verificada por SHA-256 desde `tshort/OpenDSS` (`Distrib/IEEETestCases/LVTestCase`) y construcción de `_study_master.dss`.
- [`scripts/ieee_europe_lv_906_reference.py`](../scripts/ieee_europe_lv_906_reference.py): extracción de potencias en el terminal LV de `Transformer.TR1` y extremos de tensión LV por fase en los minutos `0` (`00:01`), `565` (`09:26`) y `1439` (`24:00`).
- [`scripts/ieee_europe_lv_906_reference_sensitivity.py`](../scripts/ieee_europe_lv_906_reference_sensitivity.py): pruebas A/B previas sobre `UseActual` y `%Rs`.
- [`scripts/ieee_europe_lv_906_source_audit.py`](../scripts/ieee_europe_lv_906_source_audit.py): auditoría de paridad contra `ieee-pes-amps/dtf-dev`.
- [`outputs/analysis/ieee_europe_lv_906/ieee_2015_reference_check.csv`](../outputs/analysis/ieee_europe_lv_906/ieee_2015_reference_check.csv) y [`ieee_2015_reference_summary.json`](../outputs/analysis/ieee_europe_lv_906/ieee_2015_reference_summary.json).

### 2.2 Procedencia inmutable y archivos del alimentador IEEE inspeccionados
- **Commit fijado en `tshort/OpenDSS`:** `5005c668a72d20775f4c2d060feebb2866ba1d38` (`Distrib/IEEETestCases/LVTestCase`), `source_manifest.json` `sha256: 2315987e23cc2438fbfea6530acc2b4e723a52faf5fbf098403330ca7f7c87b2`.
- `Master.dss` (`sha256: 959fd0f0e9f033c269b3c66228db444138dfbdbc40d39d11d88656cb2b5e9853`): `Set DefaultBaseFrequency=50`, `Edit Vsource.Source BasekV=11 pu=1.05 ISC3=3000 ISC1=5`, `batchedit loadshape..* useactual=no`, `Set voltagebases=[11 .416]`.
- `Transformers.txt` (`sha256: d951d5bd01b13eb6a1e92abc6b90d45c9c546b13c87237025e0eb0a5026dd1d1`): `New Transformer.TR1 Buses=[SourceBus 1] Conns=[Delta Wye] kVs=[11 0.416] kVAs=[800 800] XHL=4 sub=y`.
- `Loads.txt` (`sha256: c07b99a8b8ebd4ed5339689c7d43637443a09fac4334b1c427e9e4be484b7f6e`): 55 cargas monofásicas con `Phases=1 kV=0.23 kW=1 PF=0.95 Yearly=Shape_i`.
- `LoadShapes.txt` (`sha256: aeb630f37dcf2b19c985c2f87a5a32e8d710fe76003659c28364d82f12e389c0`): 55 perfiles de 1440 puntos (`minterval=1`, `useactual=true` sobrescrito a `useactual=no` en `Master.dss`).

### 2.3 Entorno, comando de reproducción y artefactos
- **Dependencias:** `Python 3.11.2`, `opendssdirect.py==0.9.4`, `dss-python==0.15.7`, `dss-python-backend==0.14.5`.
- **Comando de reproducción desde la raíz del repositorio:**
  ```bash
  python scripts/audit_ieee906_vmaxpu_root_cause.py --download
  ```
- **Evidencia independiente generada (sin sobrescribir `outputs/analysis/ieee_europe_lv_906/`):**
  - [`outputs/audit_pending_review/ieee906_vmaxpu_root_cause.json`](../outputs/audit_pending_review/ieee906_vmaxpu_root_cause.json) (`sha256: 5ddefddf864c99107450e66966b898c902b421ae939290fef314d619e0c29c67`)
  - [`outputs/audit_pending_review/ieee906_vmaxpu_root_cause.csv`](../outputs/audit_pending_review/ieee906_vmaxpu_root_cause.csv) (`sha256: e22c85949a39bc585caa9c1ee5595cd6d7fc5a12e7fcba0e1a5615558b7eafeb`)

---

## 3. Diagnóstico Físico y Numérico de la Causa Raíz

### 3.1 Definición de magnitudes y convenciones
Se verificó que [`scripts/ieee_europe_lv_906_reference.py`](../scripts/ieee_europe_lv_906_reference.py) mide correctamente:
- **Instantes:** indexación base cero (`minute=0` $\leftrightarrow$ `00:01`, `minute=565` $\leftrightarrow$ `09:26`, `minute=1439` $\leftrightarrow$ `24:00`).
- **Punto de medida:** terminal secundario (LV) de `Transformer.TR1` con signo invertido (`-Powers[offset + 2*i]`, potencia entregada hacia la red LV), lo cual evita la mezcla de fases propia del devanado primario en Delta (`Vsource.Source`).
- **Tensiones:** magnitudes fase-neutro de todos los nodos LV (`0 < kVBase < 1`), agrupadas por nodo físico `1, 2, 3` (fases A, B, C).

### 3.2 Distribución de tensiones sobre las 55 cargas (`kV=0.23`)
En `opendssdirect-py 0.9.4`, los valores por defecto de cada objeto `Load` en `Loads.txt` son:
`Model = 1` (potencia constante $P+jQ$), `Vminpu = 0.95`, **`Vmaxpu = 1.05`**, `kV = 0.23` ($230\text{ V}$).

El umbral superior de potencia constante por defecto es $1{,}05 \times 230\text{ V} = \mathbf{241{,}50\text{ V}}$. Al consultar las tensiones nodales en los tres instantes de referencia bajo el modelo canónico se observa:

| Instante | Fase | N.º cargas | Cargas con $V > 241{,}50\text{ V}$ | Rango $V$ [V] | Rango $V/230$ [pu] | Error $P_{\text{LV}}$ canónico [%] |
|:---:|:---:|---:|---:|:---:|:---:|---:|
| `00:01` (`min=0`) | A | 21 | **21 / 21** (100 %) | $[251{,}88;\ 252{,}11]$ | $[1{,}0952;\ 1{,}0961]$ | $+8{,}8133\ \%$ |
| `00:01` (`min=0`) | B | 19 | **19 / 19** (100 %) | $[251{,}93;\ 252{,}09]$ | $[1{,}0953;\ 1{,}0961]$ | $+8{,}8325\ \%$ |
| `00:01` (`min=0`) | C | 15 | **15 / 15** (100 %) | $[252{,}01;\ 252{,}06]$ | $[1{,}0957;\ 1{,}0959]$ | $+8{,}9356\ \%$ |
| `09:26` (`min=565`) | A | 21 | **21 / 21** (100 %) | $[245{,}18;\ 251{,}42]$ | $[1{,}0660;\ 1{,}0931]$ | $+4{,}3257\ \%$ |
| `09:26` (`min=565`) | B | 19 | **7 / 19** (37 %) | $[238{,}42;\ 247{,}90]$ | $[1{,}0366;\ 1{,}0778]$ | **$+0{,}4188\ \%$** |
| `09:26` (`min=565`) | C | 15 | **15 / 15** (100 %) | $[252{,}15;\ 254{,}62]$ | $[1{,}0963;\ 1{,}1071]$ | **$+9{,}5393\ \%$** |
| `24:00` (`min=1439`) | A | 21 | **21 / 21** (100 %) | $[250{,}99;\ 251{,}91]$ | $[1{,}0913;\ 1{,}0953]$ | $+8{,}3713\ \%$ |
| `24:00` (`min=1439`) | B | 19 | **19 / 19** (100 %) | $[251{,}02;\ 251{,}75]$ | $[1{,}0914;\ 1{,}0946]$ | $+8{,}3582\ \%$ |
| `24:00` (`min=1439`) | C | 15 | **15 / 15** (100 %) | $[251{,}77;\ 251{,}89]$ | $[1{,}0946;\ 1{,}0952]$ | $+8{,}7301\ \%$ |

Esto explica por completo el patrón asimétrico que parecía misterioso:
- A las `00:01` y `24:00`, las 55 cargas superan ampliamente $241{,}50\text{ V}$ ($\approx 1{,}095\text{ pu}$), por lo que OpenDSS las convierte en impedancia constante escalada respecto a $V_{\max} = 1{,}05\text{ pu}$, generando un sesgo casi uniforme de $+8{,}4\ \%$ a $+8{,}9\ %$.
- A las `09:26`, la fase B soporta la demanda pico ($35{,}29\text{ kW}$), cayendo por debajo de $241{,}50\text{ V}$ en sus nodos más cargados ($238{,}42\text{ V}$); por ello, casi toda la fase B permanece en potencia constante y su error era solo $+0{,}42\ %$. Simultáneamente, el desequilibrio eleva la fase C hasta $254{,}73\text{ V}$ ($1{,}1075\text{ pu}$), maximizando el recorte cuadrático a **$+9{,}54\ %$**.

---

## 4. Verificación Cuantitativa: Canónico (`Vmaxpu=1.05`) vs. Potencia Constante Pura (`Vmaxpu=1.20`)

### 4.1 Resumen global de errores máximos (9 muestras $P$, 9 muestras $Q$, 18 muestras $V$)

| Variante diagnóstica | Máx. error $P_{\text{LV}}$ [kW] ([%]) | Máx. error $Q_{\text{LV}}$ [kvar] ([%]) | Máx. error $V_{\max}$ [V] ([%]) | Máx. error $V_{\min}$ [V] ([%]) |
|:---|---:|---:|---:|---:|
| Canónico (`Vmaxpu=1.05` por defecto) | `0,774604` (**`9,5393 %`**) | `0,237642` (**`9,4139 %`**) | `0,063960` (`0,0251 %`) | `0,399621` (`0,1627 %`) |
| `Vmaxpu=1.10` | `0,009294` (`0,1503 %`) | `0,003066` (`0,1462 %`) | `0,004488` (`0,0018 %`) | `0,001533` (`0,0006 %`) |
| **`Vmaxpu=1.20` (PQ puro)** | **`0,003771` (`0,0438 %`)** | **`0,001080` (`0,0906 %`)** | **`0,000452` (`0,0002 %`)** | **`0,000415` (`0,0002 %`)** |
| `Vmaxpu=1.20` + `tolerance=1e-8` | `0,000840` (`0,0439 %`) | `0,000315` (`0,0907 %`) | `0,000419` (`0,0002 %`) | `0,001562` (`0,0007 %`) |

*(Nota: Con `Vmaxpu=1.10` aún persiste un `0,15 %` en fase C a las `09:26` porque $254{,}62 / 230 = 1{,}1071 > 1{,}10$; con `Vmaxpu=1.20` ninguna carga alcanza el umbral.)*

### 4.2 Comparación detallada por instante y fase con `Vmaxpu=1.20`

| Instante | Magnitud | IEEE 2015 OpenDSS (A / B / C) | Simulación `Vmaxpu=1.20` (A / B / C) | Error relativo máx. |
|:---:|:---|:---:|:---:|:---:|
| `00:01` | $P_{\text{LV}}$ [kW] | `1.0572 / 0.9270 / 0.8153` | `1.0569 / 0.9266 / 0.8154` | **`0,0438 %`** |
| `00:01` | $Q_{\text{LV}}$ [kvar] | `0.3475 / 0.3044 / 0.2678` | `0.3472 / 0.3046 / 0.2679` | `0,0906 %` |
| `00:01` | $V_{\max}$ [V] | `252.165 / 252.166 / 252.169` | `252.1647 / 252.1659 / 252.1691` | `0,0001 %` |
| `00:01` | $V_{\min}$ [V] | `251.909 / 251.946 / 252.023` | `251.9092 / 251.9464 / 252.0229` | `0,0002 %` |
| `09:26` | $P_{\text{LV}}$ [kW] | `17.9072 / 35.2927 / 6.1837` | `17.9070 / 35.2965 / 6.1836` | **`0,0107 %`** |
| `09:26` | $Q_{\text{LV}}$ [kvar] | `5.4897 / 11.5328 / 2.0971` | `5.4896 / 11.5339 / 2.0970` | `0,0094 %` |
| `09:26` | $V_{\max}$ [V] | `251.901 / 251.443 / 254.730` | `251.9008 / 251.4425 / 254.7304` | `0,0002 %` |
| `09:26` | $V_{\min}$ [V] | `245.577 / 238.367 / 251.952` | `245.5770 / 238.3673 / 251.9521` | `0,0001 %` |
| `24:00` | $P_{\text{LV}}$ [kW] | `3.7201 / 3.6648 / 2.3369` | `3.7201 / 3.6649 / 2.3368` | **`0,0050 %`** |
| `24:00` | $Q_{\text{LV}}$ [kvar] | `1.2189 / 1.2048 / 0.7678` | `1.2190 / 1.2048 / 0.7677` | `0,0137 %` |
| `24:00` | $V_{\max}$ [V] | `252.113 / 252.105 / 252.134` | `252.1126 / 252.1051 / 252.1336` | `0,0002 %` |
| `24:00` | $V_{\min}$ [V] | `251.080 / 251.109 / 251.805` | `251.0798 / 251.1090 / 251.8049` | `0,0001 %` |

Adicionalmente, el resultado `1.0569 / 0.9266 / 0.8154 kW` obtenido a las `00:01` con `Vmaxpu=1.20` coincide **exactamente hasta el cuarto decimal** con la columna **GridLAB-D** reportada en el informe IEEE PES 2015, confirmando que las tablas publicadas en 2015 corresponden al régimen de carga de **potencia constante pura (`Model=1` sin recorte en $1{,}05\text{ pu}$)**.

También se comprobó la hipótesis alternativa de cambiar la tensión nominal de las cargas a `kV=0.2401777` ($416/\sqrt{3}\text{ V}$) manteniendo `Vmaxpu=1.05`; dicha variante deja un residual de `0,4836 %` en la fase C a las `09:26` (porque $254{,}73 / 240{,}18 = 1{,}0606 > 1{,}05$), descartándola frente a `Vmaxpu=1.20`. Asimismo, se verificó que la resistencia por defecto de `Transformer.TR1` en OpenDSS ya corresponde a `%Rs=[0.2 0.2]` (0,4 % total, igual a `Transformer.csv` oficial).

---

## 5. Alcance, Limitaciones y Decisión Científica

1. **Diferenciación respecto a los escenarios QSTS posteriores con FV + BESS + Transformador 5 kVA:**
   La reproducción del benchmark oficial IEEE (sin generación distribuida, 3 instantes de referencia) debe distinguirse estrictamente de los escenarios QSTS de 24 h posteriores con FV, BESS y transformador de acoplamiento de 5 kVA ([`qsts_24h_scenarios_comparison.csv`](../outputs/analysis/ieee_europe_lv_906/qsts_24h_scenarios_comparison.csv)). Esos escenarios QSTS fueron ejecutados con el archivo `Master.dss` canónico (`Vmaxpu=1.05` por defecto). Sus comparaciones **escenario-contra-escenario siguen siendo internamente consistentes** (todas comparten exactamente la misma ley de carga), pero su energía importada base (`522,373 kWh`) y sus pérdidas (`5,0627 kWh`) incluyen el escalamiento cuadrático de impedancia constante cuando $V > 241{,}50\text{ V}$.
2. **Impacto de adoptar `Vmaxpu=1.20` sobre las conclusiones de la tesis:**
   `Vmaxpu=1.20` se documenta aquí estrictamente como **configuración diagnóstica** para explicar la discrepancia de 2015. **Si se decidiera adoptar `Vmaxpu=1.20` como línea base operativa del alimentador, sería obligatorio regenerar todas las simulaciones QSTS de 24 h (caso base sin GD y todos los escenarios FV/BESS) para recalcular pérdidas, energía importada y perfiles de tensión antes de actualizar las conclusiones de la tesis.** En ningún caso deben mezclarse cifras QSTS obtenidas con `Vmaxpu=1.05` y con `Vmaxpu=1.20`.
3. **Conservación del modelo canónico:**
   Conforme a las restricciones de esta auditoría, **no se ha modificado** `Master.dss`, `Loads.txt`, los datos oficiales IEEE ni los CSV/JSON validados del PR #57.
4. **Dictamen y conclusión defendible ante el director de tesis:**
   - **Dictamen:** **PASS** para la identificación causal de la discrepancia del 9,54 %.
   - **Conclusión defendible:** La discrepancia del 9,5393 % frente a las Tablas II–III de IEEE PES 2015 no se debe a errores de datos, topología ni codificación propia, sino a la activación del límite por defecto `Vmaxpu=1.05` de OpenDSS sobre cargas declaradas a $230\text{ V}$ en un alimentador operado a $1{,}05\text{ pu}$ de $416\text{ V}$ ($252\text{ V}$). Bajo la configuración diagnóstica `Vmaxpu=1.20` (potencia constante pura), nuestro modelo reproduce la referencia IEEE 2015 con error máximo de **0,0438 % en potencia activa**, **0,0906 % en potencia reactiva** y **$\approx 0{,}0002\ \%$ en tensión**.
   - **Separación explícita de dictámenes:** convergencia numérica del nadir (`PASS` en [`auditoria_convergencia_nadir_50hz.md`](auditoria_convergencia_nadir_50hz.md)), causa de discrepancia IEEE 906 identificada (`PASS` aquí), escenario severo $+40\ \%$ sin BESS (`REVIEW` físico por $V_{dc}$), y validación experimental del envejecimiento (`BLOCKED`).
   - **Trazabilidad de artefactos:** [`ieee906_vmaxpu_root_cause.json`](../outputs/audit_pending_review/ieee906_vmaxpu_root_cause.json) (`sha256: 5ddefddf864c99107450e66966b898c902b421ae939290fef314d619e0c29c67`) y [`ieee906_vmaxpu_root_cause.csv`](../outputs/audit_pending_review/ieee906_vmaxpu_root_cause.csv) (`sha256: e22c85949a39bc585caa9c1ee5595cd6d7fc5a12e7fcba0e1a5615558b7eafeb`).
