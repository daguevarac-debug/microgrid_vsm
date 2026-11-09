# BAT26-55 — Acoplamiento optativo del pack Nissan Leaf al bus DC y soporte GFM

## Alcance y referencias revisadas

La integración añade a `MicrogridWithBESS` una ruta optativa para el escenario
BAT26-53: 48 módulos 2s2p en serie, equivalentes a 96 unidades 2p en serie y
una sola cadena. Se conserva una capacidad de cadena en Ah; no se multiplica
por 48 ni por 96. La ruta reutiliza `Leaf48ModulePack`, `CapacitySnapshot`,
`DCDCParameters` y `convert_power`.

Se consultaron las decisiones de BAT26-46 (cuatro capacidades de 44,100,
42,273, 39,038 y 35,854 Ah, mismo SoC inicial y el hallazgo previo de que el
BESS solo cargaba en el GFM), así como los PR #49 y #50. El #49 aporta el pack
48×(2s2p) y la convención de capacidad; el #50 documenta los puertos y advierte
que eficiencias y límites del adaptador son hipótesis, no ratings certificados.
El criterio Roma que acompaña BAT26-46 pide 3–4 niveles y diferencias
reproducibles; el ensayo aquí añade la comprobación de descarga que faltaba.
No se fusionó ningún PR.

## Interfaz y ecuaciones preservadas

**Corrección posterior a la auditoría:** la tabla y las verificaciones de la
campaña original que aparecen más abajo corresponden a `cf0a9f0`, antes de
corregir la solicitud de corriente. No son resultados de la versión corregida.

La ruta se activa solo al proporcionar juntos `leaf_pack` y
`dcdc_parameters`; el camino histórico sigue siendo el predeterminado. El
modelo ECM existente representa una unidad 2p: sus `OCV`, `Vrc`, `R0` y Ah se
usan directamente como valores por unidad 2p. La corriente común de la cadena
es `I_pack`; no se escala por el número de unidades en serie. El adaptador
resuelve la potencia pack–bus y proporciona la corriente del puerto bus.

La ley proporcional heredada solicita corriente **del bus**. Su salida ya
supervisada se convierte en `P_bus_request = max(Vdc, 0)*I_bus_request`;
el adaptador resuelve después el puerto de pack y aplica la eficiencia una vez.
Por ejemplo, a 330 V una solicitud de +5 A representa +1650 W antes de las
restricciones del adaptador. La ruta histórica sin DC/DC no cambia.

El diagnóstico público `dcdc_saturated` ahora incluye cualquier recorte en
la supervisión previa o en el adaptador, ampliando su significado anterior,
que solo reflejaba el adaptador. `dcdc_supervision_saturated` y
`dcdc_adapter_saturated` distinguen ambas etapas; `dcdc_soc_blocked` identifica
el bloqueo direccional SoC. `dcdc_protection_status` conserva su significado
para las protecciones de tensión del adaptador; un bloqueo de protección no
se interpreta como una saturación operativa normal. Pack y ECM deben declarar
los mismos límites SoC; configuraciones incompatibles se rechazan al construir.

Los defectos y su evidencia reproducible en
`src/validation/validate_bat26_55_pack_bus_gfm.py --test` son:

- La tensión de pack en vacío reinterpretaba la corriente de bus: ahora se
  usa la tensión de bus; `test_bus_current_request_and_signed_integrated_power_balance`
  verifica 330 V × 5 A, carga, descarga y pérdidas.
- El recorte previo quedaba oculto: ahora se agregan las etapas y se informan
  por separado; `test_saturation_stages_and_protection_are_distinct` ejercita
  supervisión, adaptador y protección.
- Los límites SoC podían diferir silenciosamente: ahora se rechazan; el test
  `test_soc_contract_boundaries_and_rhs_interleaving` cubre 0,20/0,10, ambos
  sentidos en los límites y RHS con evaluaciones intercaladas.

Los ensayos no constituyen validación experimental, ni prueban carga o soporte
sostenidos. La campaña muestrea 61 puntos y su criterio de descarga requiere
al menos una muestra positiva; no prueba continuidad entre muestras.

### Verificación de la corrección

En la rama de trabajo corregida se ejecutaron, en este orden:

| Comando | Resultado |
|---|---|
| `python -B src/validation/validate_bat26_55_pack_bus_gfm.py --test` | PASS, 7 pruebas |
| `python -B -m unittest discover -s src/validation -p test_dc_dc_adapter.py -v` | PASS, 15 pruebas |
| `python -B src/validation/validate_bat26_53_pack_48s.py` | PASS aritmético |
| `python -B src/validation/validate_bat26_55_pack_bus_gfm.py` | PASS en los cuatro casos; 60 de 61 muestras de descarga por caso |
| `python -B src/validation/validate_obj1_regression.py` | PASS |
| `timeout 240s python -B src/validation/validate_physical_invariants.py` | Pendiente: límite de tiempo, código 124 |
| `timeout 240s python -B src/validation/validate_gfm_integrated_system.py` | Pendiente: límite de tiempo, código 124 |
| `git diff --check` | PASS |

Las regresiones se ejecutaron sobre una copia de las fuentes modificadas para
no alterar resultados versionados. El mínimo Vdc de la campaña corregida fue
aproximadamente 320,870 V en los cuatro casos. El REVIEW de +40 % registrado
en la campaña histórica no fue reevaluado hasta término ni convertido en PASS.

```text
V_pack = 96 * V_unit
P_pack = 96 * V_unit * I_pack
P_bus = eta_discharge * P_pack                  (descarga)
P_pack = eta_charge * P_bus                    (carga, ambos negativos)
I_bus = P_bus / Vdc
P_bess_dc = Vdc * I_bus
dVdc/dt = (Ipv + I_bus - idc_inv) / Cdc
dSoC/dt = -I_pack / (3600 * Q_eff)
dVrc/dt = -Vrc/(R1*C1) + I_pack/C1
dz_deg/dt = |I_pack|/3600
```

Así se preservan los signos positivos de descarga, las ecuaciones ECM y del
enlace DC, y el vector GFM de 15 estados. `GFMController` recibe potencia
firmada real del puerto bus y los límites disponibles en ese puerto; SoC, SoH,
corriente, potencia y tensión continúan supervisados. El adaptador satura una
solicitud inviable; si la tensión de unidad o del bus está fuera de rango,
bloquea el intercambio e informa el estado de protección. Las pérdidas del
convertidor se contabilizan una sola vez como `P_pack - P_bus`; no se alteran
la eficiencia del puente ni las pérdidas LCL.

No se modificaron el orden ni número de estados, ecuaciones protegidas, BLAST-
Lite, `M=80`, `D=1500`, el controlador GFM, IEEE 33 o
`MicrogridWithBESSPI` de 16 estados. Cada escenario dinámico integra todos los
estados en una llamada global a `solve_ivp`. Tanto `system_dynamics` como
`integrated_signals` reconstruyen los puertos desde el estado recibido; la
segunda función no depende de una evaluación anterior.

## Ensayo dinámico de descarga

Los cuatro escenarios son condiciones iniciales independientes, con SoC=0,60,
la misma irradiancia constante de 200 W/m², demanda de 3,0 kW con escalón a
4,2 kW en 0,10 s y el mismo GFM (`M=80`, `D=1500`, `p_ref=4,0 kW`). Se integra
de 0 a 0,30 s, con 15 estados, `RK45`, `rtol=1e-6`, `atol=1e-9` y paso máximo
de 50 μs. La ventana incluye una descarga positiva en los 0,30 s observados.
La frecuencia se calcula como `omega/(2*pi)`.

| Qeff inicial (Ah) | SoH inicial/final | SoC final | Vdc mínimo (V) | f mínima (Hz) | Ipack máx (A) | Ibus máx (A) | Pbus máx (kW) | Energía pack (Wh) | Energía bus (Wh) | Pérdidas DC/DC (Wh) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 44,100 | 0,66818 / 0,66818 | 0,599984 | 320,687 | 59,98789 | 9,6916 | 9,5548 | 3,0641 | 0,237672 | 0,225788 | 0,011884 |
| 42,273 | 0,64050 / 0,64050 | 0,599983 | 320,687 | 59,98789 | 9,6923 | 9,5548 | 3,0641 | 0,237672 | 0,225788 | 0,011884 |
| 39,038 | 0,59148 / 0,59148 | 0,599982 | 320,687 | 59,98789 | 9,6936 | 9,5548 | 3,0641 | 0,237672 | 0,225788 | 0,011884 |
| 35,854 | 0,54324 / 0,54324 | 0,599980 | 320,687 | 59,98789 | 9,6949 | 9,5548 | 3,0641 | 0,237672 | 0,225788 | 0,011884 |

En cada caso el solver terminó con éxito y todos los estados/señales fueron
finitos. Se observaron 60 muestras de descarga de 61 puntos temporales,
`I_pack>0`, `I_bus>0` y `P_bus>0`, durante aproximadamente 0,30 s. `V_pack`
quedó entre 332,664 y 334,080 V, dentro del sobre seleccionado de 240–398,4 V.
No se excedieron los límites hipotéticos de corriente del fixture, 20 A de
corriente bus ni 5 kW de potencia bus. Se verificó numéricamente
`P_bus=Vdc*I_bus`, `P_pack=96*V_unit*I_pack` y pérdidas positivas. La pequeña
diferencia de SoC entre casos proviene de su `Q_eff`; `CapacitySnapshot` fija
la capacidad inicial de cada caso y evita volver a contabilizar el
envejecimiento previo. El ensayo no prueba el asentamiento de frecuencia ni el
servicio sostenido: su ventana es de 0,30 s.

## Verificaciones

| Comando | Resultado registrado |
|---|---|
| `python -B src/validation/validate_bat26_55_pack_bus_gfm.py --test` | PASS, 4 pruebas: sentidos, conservación/pérdidas, límites de corriente/potencia/SoC/SoH/tensión, 15 estados, estado determinista y compatibilidad histórica. |
| `python -B src/validation/validate_bat26_55_pack_bus_gfm.py` | PASS, cuatro solves; descarga en los cuatro niveles y límites respetados. |
| `python src/validation/validate_bat26_53_pack_48s.py` | PASS aritmético: topología y capacidad de cadena. |
| `python -m unittest discover -s src/validation -p test_dc_dc_adapter.py -v` | PASS, 15 pruebas. |
| `python src/validation/validate_obj1_regression.py` | PASS: LCL, `bess_step3` y límites SoC. |
| `python src/validation/validate_gfm_integrated_system.py` | REVIEW global: steady, escalón +20 % y caso con BESS-PI PASS; escalón +40 % REVIEW heredado. GFM activo en todos. |
| `python src/validation/validate_physical_invariants.py` | PASS: balances DC con/sin BESS, identidad de potencia, límites SoC y signos de carga/descarga. |
| `python -m py_compile src/microgrid.py src/validation/validate_bat26_55_pack_bus_gfm.py` | PASS. |
| `git diff --check` | PASS. |

Fallos reales durante desarrollo: el primer intento de `--test` falló porque
una raíz algebraica produjo `1.0000000000000002 A` y la aserción exigía
estrictamente `<=1.0`. Se corrigió la tolerancia de comparación a `1e-12`; la
repetición pasó. El primer cálculo energético emitió advertencias porque
`numpy.trapz` está deprecado; se cambió a `numpy.trapezoid` y se volvió a
ejecutar la campaña sin esa ruta deprecada. El primer `git diff --check`
posterior a Objetivo 1 señaló finales CRLF en sus CSV generados; se restauraron
los artefactos de salida y `git diff --check` volvió a pasar. La búsqueda de
“Roma BAT26-55” en GitHub/Drive no encontró un documento o issue independiente;
el criterio Roma consultable quedó en `docs/bat26-46-soh-operational-comparison.md`.

## Restricciones y riesgos abiertos

Este resultado es validación numérica interna, no validación experimental,
HIL, ni prueba de hardware. La eficiencia 0,95, 10 A por unidad 2p, 20 A bus y
5 kW bus son fixtures hipotéticos de prueba. `OCV/R1/C1`, `R0(SoH)`, los
perfiles y la política proporcional de referencia de potencia siguen siendo
provisionales; no hay datos HPPC ni modelo térmico/BMS, balance entre módulos,
dinámica de convertidor, contactores ni protecciones de hardware. El modelo
algebraico no prueba transitorios de conmutación ni la envolvente completa de
operación del bus/inversor. La ventana de 0,30 s confirma descarga numérica,
pero no autonomía, operación estable sostenida, cumplimiento de criterios de
frecuencia de largo plazo ni soporte de una red real.

El informe debe leerse junto con las revisiones de PR #49/#50 y el historial
sintético de BAT26-46. No cierra pendientes experimentales ni cambia main.
