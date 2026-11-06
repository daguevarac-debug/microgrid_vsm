# BAT26-54 — D1.2: dimensionamiento preliminar AC–bus–banco

**Estado: estudio algebraico, no selección de hardware ni implementación dinámica.** Candidato de simulación: buck-boost bidireccional no aislado de cuatro interruptores; conservar DAB aislado si el análisis de seguridad exige aislamiento galvánico. La selección de aislamiento, la eficiencia y los límites siguen abiertos. Referencia de rama: `feat/blast-aging-adapter`; BAT26-53 está en PR #49 independiente y no fusionado. Los datos de BAT26-53 se usan como escenario explícito, sin importar su código ni asumir su fusión.

## Alcance, fuentes y niveles de evidencia

| Tipo | Dato y alcance |
|---|---|
| Fuente publicada / adopción BAT26-53 | Leaf 48 módulos 2s2p en serie = 96 grupos 2p en serie, 192 celdas; 7,5 V y 66 Ah por módulo; tensión nominal 360 V, capacidad de cadena 66 Ah (no se multiplica en serie). [Braco 2021, tabla I, DOI 10.1109/TIA.2021.3075180](https://doi.org/10.1109/TIA.2021.3075180); [Braco 2023, tabla 1, DOI 10.1016/j.apenergy.2022.120235](https://doi.org/10.1016/j.apenergy.2022.120235). |
| Derivado | 48×(5–8,3 V) = 240–398,4 V; 48×7,5 = 360 V. Braco 2023 publica 403,2 V para pack y 8,30 V por módulo: no coinciden al escalar; se retiene 398,4 V como límite **derivado del módulo**, no medición del pack de tesis. [Castillo-Martínez 2022, DOI 10.3390/s22176376](https://doi.org/10.3390/s22176376) documenta otro pack de 240–403,2 V. |
| Decisión de tesis | Q inicial 44,1 Ah; SoH inicial 44,1/66 = 0,66818; SoC 0,1–0,9. Energía ideal a tensión nominal 15,876 kWh y ventana 12,7008 kWh; no son energía terminal ni de bus medida. |
| Repositorio | Carga activa 3 kW a FP 0,95 atrasado; escalones +20 % y +40 % (3,6 y 4,2 kW); Vdc de referencia 340 V. Control GFM con M=80, D=1500; vector GFM+BESS 15 estados y PI opcional 16 estados. No se cambian. |
| Hipótesis de cálculo | Régimen estacionario o foto cuasiestática, 3 fases equilibradas, FP constante, pérdidas de filtro = 0 en tabla de referencia, η puente = 0,97 y η DC/DC = 0,95 en cada sentido, 1 kW FV en bus cuando se indica. Ninguno certifica una instalación. |

**Literatura de topología:** [Kitazoe, Natori y Sato 2024, DOI 10.1541/ieejjia.23012442](https://doi.org/10.1541/ieejjia.23012442), presenta control bidireccional experimental con cuatro interruptores; no valida esta potencia o batería. [Ríos, Pagano y Lucas 2021, DOI 10.3390/en14020404](https://doi.org/10.3390/en14020404) estudia el DAB y reparto de potencia mediante simulación. [DOI 10.1109/TPEL.2024.3397882](https://doi.org/10.1109/TPEL.2024.3397882) estudia una variante DAB para rango amplio, no establece rating para este proyecto. La eficiencia no es inherentemente igual para ambas topologías y requiere medición o curvas justificadas.

| Comparación | Buck-boost 4 interruptores | DAB |
|---|---|---|
| Tensión y sentido | Ambos sentidos y cruce de razón unitaria; verificar transición de modos y corriente. | Ambos sentidos mediante puentes y transformador; verificar rango de desfase, corriente RMS y ZVS. |
| Aislamiento | No galvánico; puesta a tierra y fallas son decisivas. | Galvánico por transformador, sujeto al diseño y coordinación de aislamiento. |
| Compromisos | Inductor, conmutación, protecciones y control de transición; sin demostrar eficiencia. | Transformador, inductancia de transferencia, posible corriente circulante y pérdida de ZVS; sin suponer eficiencia superior. |

## Fronteras y semántica del código existente

`src/config.py` define `MICROGRID_ETA_DEFAULT=0.97`. En `src/controllers/gfm_controller.py` y `grid_following.py`, `p_bridge = dot(v_inv,i1)` y `p_dc = max(p_bridge,0)/plant.eta`; `idc_inv = p_dc/max(vdc_eff,Vmin)` por encima de UVLO. Así, eta escala **bus a puente**, no necesariamente bus a carga o PCC: el filtro LCL tiene su propio balance. Si `vdc_eff < Vmin` el denominador protegido evita división por cero, por lo que `Vdc*idc_inv=p_dc` no es identidad general en ese régimen; debajo de UVLO se anula la transferencia. En GFM también se multiplica la disponibilidad neta DC por esa eta para limitar `p_ref_eff`. Esta reutilización no es una segunda pérdida física en serie. `p_pcc=dot(v_pcc,i2)` es otra frontera, y no se asume igual a `p_bridge` durante transitorios.

La ruta integrada actual usa una misma `i_bess` en ECM y bus; no representa aún conversión física pack–bus. `src/bess/dc_dc_adapter.py` es un adaptador algebraico independiente: η de descarga cumple Pbus=ηd Ppack y η de carga Ppack=ηc Pbus con signos negativos durante carga; sus parámetros no son datos de hardware. No confundir esta η con la η del puente ni sumar pérdidas del filtro dos veces. La ruta de inversor actual es unidireccional de DC a AC: el ejemplo de carga supone excedente FV en el bus, no recarga desde AC.

## Ecuaciones y servicios

Bajo FP constante, `S_AC=P_AC/FP`, `Q_AC=P_AC*tan(acos(FP))`. Con `P_filtro≥0` como pérdida activa puente→carga, sin energía almacenada variable y sin otras cargas AC:

```
P_puente = P_AC + P_filtro
P_inv_dc = P_puente / eta_inv
P_bess_bus = P_inv_dc - P_FV_dc
P_pack = P_bess_bus/eta_dis       si P_bess_bus >= 0
P_pack = eta_charge*P_bess_bus    si P_bess_bus < 0
I_bus = P_bess_bus/Vdc; I_pack = P_pack/Vpack
P_loss_inv = P_inv_dc-P_puente; P_loss_dcdc = P_pack-P_bess_bus
P_pack + P_FV_dc = P_AC + P_filtro + P_loss_inv + P_loss_dcdc
```

Potencia/corriente positiva indica descarga. En carga ambas son negativas y las pérdidas siguen positivas. La ecuación de balance supone que todo excedente FV entra en batería: si BMS/SoC/convertidor lo impide, se necesita vertimiento o una carga adicional. No incluye auxiliares. `P_filtro=0` es hipótesis optimista, no dato del filtro; el cálculo admite otra cifra. La potencia FV es **potencia efectivamente inyectada al bus**, no irradiancia ni potencia de placa.

**A. Incremental +1,2 kW AC:** con FP constante el incremento de carga aparente es 1,263 kVA y de reactiva 0,394 kvar. Con FV constante y pérdida incremental de filtro cero, el aporte BESS adicional es 1,2/0,97 = 1,237 kW DC al bus. Es un **incremento respecto al punto previo**, no la potencia total del BESS ni la capacidad total del inversor. La carga completa posterior requiere al menos 4,421 kVA en su puerto AC, sin contar el efecto del filtro; no se puede dimensionar el inversor completo a 1,263 kVA.

**B. Respaldo completo:** 4,2 kW AC a FP 0,95 son 4,421 kVA y 1,380 kvar. Con FV cero y filtro ideal, la demanda de inversor es 4,330 kW DC y la del pack 4,558 kW con η=0,95. A 110 V RMS fase-neutro balanceados, la corriente de línea de carga es `S/(3*110)` = 13,397 A; esto no incluye rizado, sobrecargas, desbalance ni pérdidas LCL. Una potencia DC/DC de 4,2 kW no basta para garantizar 4,2 kW AC bajo estas hipótesis.

| Servicio, FV efectiva | S carga/incremento kVA | P inversor DC / ΔP DC kW | P BESS bus / ΔP kW | P pack / ΔP kW | I bus / ΔI a 340 V A | I pack / ΔI a 240 V A | Pérdidas puente / DC-DC W |
|---|---:|---:|---:|---:|---:|---:|---:|
| A: +1,2 kW AC, ΔFV=0 | 1,263 | 1,237 | 1,237 | 1,302 | 3,639 | 5,426 | 37,11 / 65,11 |
| B: 4,2 kW AC, FV=0 | 4,421 | 4,330 | 4,330 | 4,558 | 12,735 | 18,991 | 129,90 / 227,89 |
| B: 4,2 kW AC, FV=1 kW | 4,421 | 4,330 | 3,330 | 3,505 | 9,794 | 14,605 | 129,90 / 175,26 |

La fila A supone además que el BESS ya descarga antes y después, con eficiencia incremental constante; si cruza cero, hay que calcular ambos puntos por separado con η de carga/descarga. La fila FV=1 kW ilustra disponibilidad, **no garantiza** generación. En configuración del repositorio hay 10 módulos × 34,17 V × 14,63 A = 4,999 kW de placa en STC; no implica que se produzcan en el bus a 340 V, irradiancia 800 W/m² o en perturbación. El modelo FV está directamente al bus y su punto depende de tensión, irradiancia y temperatura; no se asume MPPT ni eficiencia FV adicional.

## Sensibilidades, protecciones y límites

Para B sin FV, η_inv=0,97, η_d=0,95 y Vpack=240 V: al variar Vdc hipotéticamente 306/340/374 V (−10/0/+10 %), Ibus es 14,150/12,735/11,577 A. Son **puntos de sensibilidad**, no dominio permitido ni resultados de simulación. A 340 V la razón Vbus/Vpack sobre 240–398,4 V es 1,4167–0,8534; a los puntos de bus 306–374 V y extremos de pack resulta 0,7681–1,5583. No se supone regulación AC válida a todas esas tensiones: modulación, márgenes y control deben evaluarse dinámicamente. Con Pbus fijo de 4,330 kW y ηd=0,95, Ipack a 240/360/398,4 V es 18,991/12,660/11,441 A, antes de límites dependientes del estado.

Para B sin FV y Vpack=240 V:

| η puente / η descarga, hipotéticas | Pbus kW | Ppack kW | Ipack A | Pérdida puente / DC-DC W |
|---|---:|---:|---:|---:|
| 1 / 1 | 4,200 | 4,200 | 17,500 | 0 / 0 |
| 0,97 / 0,98 | 4,330 | 4,418 | 18,409 | 129,90 / 88,37 |
| 0,97 / 0,95 | 4,330 | 4,558 | 18,991 | 129,90 / 227,89 |
| 0,95 / 0,90 | 4,421 | 4,912 | 20,468 | 221,05 / 491,23 |

La batería debe respetar SoC mínimo/máximo con bloqueo de descarga/carga, tensión de cada grupo, límites de corriente y potencia diferenciados por sentido, SoH, temperatura y duración, así como dispersión, contactores, pre-carga, fusibles y falla de comunicación. La tensión de 240–398,4 V no demuestra que todos esos puntos sean alcanzables a potencia completa. El baseline de 66 A y 22,44 kW es límite de simulación histórica, **no rating** de pack, BMS o convertidor. Faltan HPPC, datos térmicos, OCV/RC y grupos identificados; además faltan curvas de eficiencia/corriente, rango completo de Vdc, auxiliares, frecuencia de conmutación, filtrado, aislamiento, coordinación de protecciones, límites AC y energía/tiempo de respaldo. No se dimensionan L, semiconductores ni disipadores con datos ausentes.

## Recomendación y reproducción

Estudiar como dos envolventes separadas **1,237 kW DC incremental** y **4,330 kW DC de respaldo completo sin FV**, bajo las hipótesis arriba indicadas; usar 4,421 kVA como potencia aparente mínima de carga del caso severo, no rating final de inversor. Recomendar el segundo caso como envolvente conservadora de potencia *de estudio*, condicionado a que el servicio de respaldo total se confirme y se añadan pérdidas LCL, auxiliares, margen y requerimientos transitorios. Para soporte incremental la potencia total depende del punto de operación. Ninguna cifra prueba disponibilidad real; tampoco se deduce duración mediante energía ideal.

Reproducir desde la raíz (Python estándar, sin dependencias nuevas):

```bash
python src/validation/validate_bat26_54_port_sizing.py --test
python src/validation/validate_bat26_54_port_sizing.py > /tmp/bat26-54-sensibilidad.json
```

El segundo comando emite escenarios para 1,2/4,2 kW, FV 0/1 kW, Vdc 306/340/374 V, Vpack 240/360/398,4 V y barrido independiente de eficiencias. Los cuatro tests verifican balances en descarga/carga con FV, pérdidas de filtro, FP, sensibilidad de tensión y errores de entrada; son pruebas de aritmética y no validación física o simulación dinámica.
