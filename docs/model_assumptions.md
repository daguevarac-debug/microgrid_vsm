# Supuestos simplificados vigentes

Este documento consolida los supuestos activos del baseline para mantener el
README corto y enfocado en ejecución/estado.

## BESS-SLB

- Modelo térmico: no implementado (temperatura constante asumida).
- Degradación: primer orden lineal, sin modelo de rodilla ni efectos no lineales.
- OCV/R1/C1: datos interpolados desde tabla; no incluye histéresis.
- R0 aging: ley empírica simplificada, no copiada textualmente de literatura.
- El BESS-SLB esta modelado y validado, y existe una integracion preliminar/conservadora al bus DC mediante `MicrogridWithBESS`.

## Generador fotovoltaico (baseline actual)

- Se usa el modelo equivalente de un diodo para representar el módulo fotovoltaico.
- El módulo de referencia es el LONGi LR7-54HJD-500M y los datos base provienen de su datasheet oficial en STC.
- Los parámetros tabulados usados como referencia son: Voc, Isc, Vmp, Imp, número de celdas y coeficientes de temperatura.
- Los parámetros no tabulados del modelo de un diodo (n, Rs y Rsh) se estiman mediante ajuste numérico en STC usando únicamente los puntos del datasheet.
- El ajuste de n se restringe a un rango físicamente razonable para silicio (1 <= n <= 2).
- Se imponen Rs > 0 y Rsh > 0; Rsh se acota superiormente para evitar soluciones numéricamente válidas pero poco físicas.
- En esta etapa la validación del modelo PV se realiza solo en STC, comparando Voc, Isc, Vmp e Imp del modelo frente al datasheet.
- No se modelan efectos de sombreado parcial, mismatch entre módulos, suciedad, degradación del módulo FV ni dispersión estadística entre paneles.
- No se implementa un modelo térmico dinámico del módulo; la temperatura de celda se trata como entrada del modelo.
- La curva I-V/P-V del arreglo se obtiene escalando el módulo por el número de módulos en serie y strings en paralelo definidos en config.py.

## Filtro LCL (baseline)

Los parametros del filtro LCL se mantienen centralizados en `src/config.py` y
se interpretan por fase.

- `L1 = 1e-3 H`
- `R1 = 0.05 ohm`
- `Cf = 10e-6 F`
- `Rd = 1e6 ohm`
- `L2 = 1e-3 H`
- `R2 = 0.05 ohm`

Estos valores corresponden al baseline actual. Pueden ajustarse en etapas
posteriores si el analisis de resonancia lo requiere.

El filtro LCL implementado en `src/lcl_filter.py` se modela por fase en
coordenadas `abc`.

- `di1/dt = (v_inv - vc - R1*i1) / L1`
- `dvc/dt = (i1 - i2 - vc/Rd) / Cf`
- `di2/dt = (vc - v_pcc - R2*i2) / L2`

Interpretacion fisica:

- La primera y tercera ecuacion se obtienen por KVL en los lazos de los
  inductores `L1` y `L2` con sus resistencias serie.
- La ecuacion del capacitor se obtiene por KCL en el nodo del capacitor,
  considerando la rama de amortiguamiento `Rd`.
- Esta revision no cambia el modelo; solo agrega trazabilidad de tesis sobre las
  ecuaciones ya implementadas.

Integracion del filtro LCL en la dinamica de la microrred (baseline):

- El inversor entrega la tension trifasica `v_inv`.
- Esta `v_inv` entra al filtro mediante `plant.lcl_derivatives(v_inv, v_pcc, i1, vc, i2)`.
- La carga/PCC se representa en el baseline como `v_pcc = i2 * R_load`.
- El filtro devuelve `di1dt`, `dvcdt` y `di2dt`, que se insertan en el vector
  de derivadas del sistema dinamico.
- Esta subtarea confirma la integracion ya existente; no implementa una nueva
  funcionalidad.

Verificacion de coherencia dimensional (ecuaciones LCL ya implementadas):

- `di1/dt = (v_inv - vc - R1*i1) / L1`: el numerador esta en voltios (`V`) y al
  dividir por henrios (`H`) se obtiene `A/s`.
- `dvc/dt = (i1 - i2 - vc/Rd) / Cf`: el numerador esta en amperios (`A`) y al
  dividir por faradios (`F`) se obtiene `V/s`.
- `di2/dt = (vc - v_pcc - R2*i2) / L2`: el numerador esta en voltios (`V`) y al
  dividir por henrios (`H`) se obtiene `A/s`.

Esta verificacion confirma consistencia dimensional del modelo. No valida aun la
seleccion numerica optima de `L1`, `L2`, `Cf`, `R1`, `R2` o `Rd`.
La justificacion numerica de parametros se abordara despues mediante analisis
de resonancia/estabilidad y referencia tecnica.

Frecuencia de resonancia del filtro LCL (baseline):

- Se usa la expresion estandar: `f_res = (1/(2*pi)) * sqrt((L1 + L2)/(L1*L2*Cf))`.
- Con `L1 = 1e-3 H`, `L2 = 1e-3 H` y `Cf = 10e-6 F`, se obtiene
  `f_res ≈ 2250.8 Hz`.
- Este valor queda muy por encima de la frecuencia fundamental (`60 Hz`), por
  lo que los parametros actuales se mantienen como baseline razonable.
- Este calculo no demuestra que `L1`, `L2` y `Cf` sean optimos ni cierra la
  validacion dinamica completa del filtro.
- La aceptacion completa de estos parametros queda condicionada a la siguiente
  subtarea: verificar que `f_res` no interfiera con la banda de control.
- Tambien queda pendiente comparar con la frecuencia de conmutacion `f_sw`; como
  criterio practico de diseno, la literatura suele ubicar la resonancia entre
  `10*f_g` y `0.5*f_sw`.

Referencias tecnicas para esta trazabilidad:

- Referencia principal: Pena-Alzola et al. (2013), diseno robusto y resonancia
  en filtros LCL para convertidores conectados a red.
- Referencia de apoyo: "Modelling, Design and Performance Analysis of LCL
  Filter for Grid Connected Three Phase Power Converters" (criterio
  `10*f_g <= f_res <= 0.5*f_sw`).

Verificacion preliminar frente a banda de control/conmutacion:

- Con `f_g = 60 Hz`, el limite inferior del criterio practico es:
  `10*f_g = 10*60 = 600 Hz`.
- Como `f_res ≈ 2250.8 Hz`, se cumple `f_res > 600 Hz`, por lo que la
  resonancia queda alejada de la frecuencia fundamental y respalda el baseline.
- Para el limite superior, `f_res <= 0.5*f_sw` implica `f_sw >= 2*f_res`; con
  el valor actual, se requiere `f_sw >= 4501.6 Hz`.
- El baseline actual no define aun una frecuencia de conmutacion ni una banda
  de control consolidada; por tanto, esta subtarea no cierra la validacion
  completa de interaccion con el control y deja documentado el requisito minimo
  para la siguiente etapa.
- Si en etapas posteriores se adopta `f_sw >= 5 kHz`, el valor actual de
  `f_res` cumpliria el criterio `f_res <= 0.5*f_sw`; sin embargo, esta decision
  no se fija en esta subtarea.

Referencias de esta verificacion:

- Principal: Pena-Alzola et al. (2013), resonancia y estabilidad de filtros LCL
  en convertidores conectados a red.
- Apoyo: "Modelling, Design and Performance Analysis of LCL Filter for Grid
  Connected Three Phase Power Converters" para el criterio
  `10*f_g <= f_res <= 0.5*f_sw`.

Validacion practica de oscilaciones no fisicas (baseline):

- Se ejecuto `python src/validation/validate_lcl_no_unphysical_oscillations.py`.
- Se revisaron los estados del filtro LCL `i1`, `vc` e `i2`.
- Se verifico ausencia de `NaN/inf` en la simulacion baseline.
- Se evaluo que las ventanas finales (`70-85 %` y `85-100 %` del tiempo) no
  muestren crecimiento artificial evidente mediante razones RMS.
- Resultado reportado por el script: `PASS`.
- Esta prueba es un chequeo practico de no crecimiento no fisico; no reemplaza
  una demostracion formal de estabilidad ni el analisis posterior de control.

Decision sobre ajuste de parametros LCL:

- En esta subtarea no se ajustan parametros del filtro LCL.
- La decision se basa en la validacion `PASS` de no oscilaciones no fisicas:
  - `all_states_finite=True`
  - `growth_ratio_i1=1.000238`
  - `growth_ratio_vc=1.000238`
  - `growth_ratio_i2=1.000238`
- Los parametros actuales (`L1`, `L2`, `Cf`, `R1`, `R2`, `Rd`) se mantienen
  como baseline.
- Esta decision no implica un diseno optimo final del filtro.
- Ajustes futuros podran realizarse si el analisis de control, `f_sw` o
  validaciones posteriores lo requieren.

## DC-link (PV + BESS preliminar)

Ecuacion dinamica usada en el baseline:

- `dVdc/dt = (ipv + i_bess - idc_inv) / Cdc`

Significado fisico de variables:

- `ipv`: corriente FV hacia el bus DC.
- `i_bess`: corriente de intercambio BESS-bus DC.
- `idc_inv`: corriente absorbida por el inversor desde el bus DC hacia AC.

Convencion de signos:

- Corriente positiva entra al capacitor del bus DC y aumenta `Vdc`.
- `ipv > 0` inyecta al bus.
- `i_bess > 0` descarga BESS e inyecta al bus.
- `i_bess < 0` carga BESS desde el bus.
- `idc_inv > 0` extrae corriente del bus hacia el lado AC.

Interaccion energetica en el bus DC:

- PV y BESS aportan corriente al nodo DC.
- El inversor demanda corriente del nodo DC para alimentar la etapa AC.
- El desbalance neto de corrientes determina `dVdc/dt`.

### Intercambio de potencia BESS-DC-link

Para trazabilidad diagnostica de la integracion preliminar BESS-bus DC se
reporta:

- `p_bess_dc = Vdc * i_bess`

Convencion de signos:

- `i_bess > 0` indica descarga del BESS hacia el bus DC.
- `p_bess_dc > 0` indica potencia entregada por el BESS al sistema.
- `i_bess < 0` indica carga del BESS desde el bus DC.
- `p_bess_dc < 0` indica potencia absorbida por el BESS desde el sistema.

Esta senal es una metrica diagnostica de intercambio de potencia en la
integracion preliminar. No representa todavia un modelo detallado del
convertidor DC/DC ni sus perdidas, control interno o limites dinamicos.

### Compatibilidad de escalas y unidades BESS-DC-link

Variables principales y unidades:

- `Vdc` [V]: tension del bus DC de la microrred.
- `i_bess` [A]: corriente de intercambio BESS-bus DC; positiva en descarga.
- `p_bess_dc` [W]: potencia diagnostica referida al bus DC,
  `p_bess_dc = Vdc * i_bess`.
- `soc_bess` [-] y `soh_bess` [-]: estados normalizados del BESS.
- `vt_bess` [V]: tension terminal del modelo interno Thevenin 1RC.
- `Q_eff` [Ah], `R0` [ohm], `R1` [ohm] y `C1` [F]: parametros efectivos o
  interpolados del modelo interno 1RC.

`p_bess_dc` esta referida al bus DC de la integracion preliminar. `vt_bess`
pertenece al modelo interno 1RC y no debe interpretarse por si sola como la
tension del bus DC ni como una representacion completa del banco escalado.

La integracion actual es preliminar/conservadora: preserva la convencion de
signos y permite trazabilidad de potencia, pero todavia no representa
explicitamente el convertidor DC/DC ideal ni el escalamiento del banco completo
en serie/paralelo.

Si `src/validation/validate_bess_units_scales.py` reporta `REVIEW` por una razon
alta `Vdc/vt_bess`, no se interpreta como fallo numerico. Es una advertencia de
interpretacion fisica: falta representar explicitamente el convertidor DC/DC
ideal o el escalamiento del banco completo.

### Caso nominal integrado BESS-DC-link

Objetivo de la prueba:

- Verificar que el baseline integrado `MicrogridWithBESS` corre el caso nominal
  PV + DC-link + LCL + BESS-SLB con estabilidad numerica practica y coherencia
  fisica minima.

Alcance:

- Es una validacion practica del baseline actual.
- No es una validacion formal del controlador.
- No evalua desempeno final grid-forming, VSG/FOVIC ni estrategia de inercia
  virtual.
- No introduce cambios de parametros, ganancias, ecuaciones ni arquitectura.

Variables revisadas por `src/validation/validate_bess_integrated_nominal.py`:

- Estados completos de la solucion numerica.
- `Vdc`, `i_bess`, `p_bess_dc`, `soc_bess`, `vt_bess`, `soh_bess`.
- `p_bridge`, `p_pcc` y `p_load`.
- Identidad diagnostica `p_bess_dc = Vdc * i_bess` en toda la trayectoria.

Criterio de reporte:

- `PASS`: el solver termina correctamente, estados y senales son finitos, los
  rangos fisicos basicos se cumplen y la identidad de potencia BESS-DC-link se
  mantiene.
- `REVIEW`: el caso corre y los checks basicos se cumplen, pero aparece una
  advertencia interpretativa, por ejemplo una escala alta `Vdc/vt_bess`.
- `FAIL`: error numerico, `NaN/inf`, violacion de rangos fisicos o identidad
  `p_bess_dc = Vdc * i_bess` incorrecta.

Un `REVIEW` asociado a la escala `Vdc/vt_bess` no invalida la corrida nominal.
Indica que la interpretacion fisica sigue limitada hasta modelar explicitamente
el convertidor DC/DC ideal o el escalamiento del banco completo.

### Limites operativos de SoC del BESS

Para la integracion preliminar BESS-DC-link se aplican limites operativos
conservadores de SoC:

- `soc_min = 0.10`
- `soc_max = 0.90`
- `soc_initial = 0.60`

Criterio de bloqueo de corriente:

- Descarga bloqueada cuando `soc_bess <= soc_min` e `i_bess` comandada seria
  positiva.
- Carga bloqueada cuando `soc_bess >= soc_max` e `i_bess` comandada seria
  negativa.
- En el rango operativo interior, la corriente BESS conserva la convencion:
  `i_bess > 0` descarga hacia el bus DC e `i_bess < 0` carga desde el bus DC.

Este es un supuesto operativo baseline para evitar excursion fuera de una
ventana conservadora. No es una optimizacion final ni una especificacion BMS
definitiva.

### Limites operativos de corriente del BESS

Para la integracion preliminar BESS-DC-link se usa:

- `i_bess_max = 66 A`
- Saturacion simetrica: `-66 A <= i_bess <= +66 A`

Convencion de signos:

- `i_bess > 0`: descarga del BESS hacia el bus DC.
- `i_bess < 0`: carga del BESS desde el bus DC.

Trazabilidad:

- El valor de `66 A` se adopta como referencia baseline equivalente a `1C`,
  tomando como base la capacidad nominal cercana a `66 Ah` reportada para
  modulos/celdas Nissan Leaf en Braco et al. (2020), Braco et al. (2021) y
  Braco et al. (2023).

Este valor no representa todavia una especificacion final de BMS ni un limite
definitivo del convertidor DC/DC. Es una restriccion operativa conservadora para
evitar corrientes no acotadas en la integracion preliminar BESS-DC-link.

### Limites operativos de potencia del BESS

La potencia diagnostica BESS-DC-link se calcula como:

- `p_bess_dc = Vdc * i_bess`

Para la integracion preliminar se usa el limite operativo baseline:

- `p_bess_dc_max = 22440 W`
- Calculado como `Vdc_ref * i_bess_max = 340 V * 66 A`
- Limite simetrico: `-p_bess_dc_max <= p_bess_dc <= +p_bess_dc_max`

Convencion de signos:

- `p_bess_dc > 0`: el BESS entrega potencia al bus DC.
- `p_bess_dc < 0`: el BESS absorbe potencia desde el bus DC.

Este limite esta referido al bus DC y no a `vt_bess` del modelo interno 1RC.
Es un supuesto baseline para evitar potencia DC no acotada en la integracion
preliminar. No representa todavia una especificacion final del BMS ni del
convertidor DC/DC.

### Orden de saturaciones carga/descarga del BESS

En la integracion preliminar `MicrogridWithBESS`, la corriente de intercambio
`i_bess` se limita con el siguiente orden operativo:

1. Se calcula `i_bess_cmd` por soporte proporcional del DC-link.
2. Se aplica saturacion de corriente:
   `-i_bess_max <= i_bess <= +i_bess_max`.
3. Se aplican bloqueos direccionales por SoC:
   - descarga bloqueada si `soc_bess <= soc_min`.
   - carga bloqueada si `soc_bess >= soc_max`.
4. Finalmente se aplica saturacion de potencia DC:
   `abs(Vdc * i_bess) <= p_bess_dc_max`.

La saturacion es simetrica para carga y descarga en esta etapa baseline y
mantiene la convencion `i_bess > 0` para descarga e `i_bess < 0` para carga.
Este orden no representa todavia una logica BMS final ni un convertidor DC/DC
detallado; es una restriccion operativa conservadora para la integracion
preliminar BESS-DC-link.

Simplificaciones validas para esta etapa:

- Acople BESS-bus DC idealizado (sin modelo explicito del convertidor DC/DC).
- `idc_inv` modelado unidireccional DC->AC en el baseline.
- `p_available` del controlador referido a disponibilidad FV.
- No se incluye carga DC adicional ni perdidas explicitas del bus DC.

Alcance de validacion en esta etapa:

- Se verifico coherencia fisica de la ecuacion y de la convencion de signos.
- Se implementaron pruebas unitarias basicas del balance/signos en:
  `src/validation/test_dclink_dynamics.py`.

- `DeltaVdc_abs = |Vdc_pre_step - Vdc_min_post|`.
- `DeltaVdc_pct = 100 * DeltaVdc_abs / Vdc_pre_step`.
- `t_rec_95_pre`: primer instante despues del minimo post-escalon en que
  `Vdc` recupera el 95 % de la caida respecto al valor pre-escalon.
- `t_settle_new_2pct`: primer instante en que `Vdc` entra a una banda de
  `+-2 %` respecto al valor final post-escalon.
- Si existe nuevo punto operativo y no se recupera el nivel pre-escalon en la
  ventana simulada, se prioriza la interpretacion con `t_settle_new_2pct`.
- Para esta etapa, se acepta si `Vdc` permanece dentro de la banda `+-2 %`
  respecto al valor final post-escalon durante el tramo final de la simulacion.
- Si se usa una ventana de `2 s` con escalon en `0.8 s`, puede reportarse
  tambien `t_settle_new_2pct` como metrica auxiliar.
- Este criterio es interno de validacion de etapa; no es un limite normativo ni
  una especificacion final de diseno del convertidor/control.

Criterio explicito PASS/FAIL (validacion DC-link en esta etapa):

- PASS si se cumplen simultaneamente:
  - `DeltaVdc_pct <= 5 %` en el evento de escalon evaluado.
  - `Vdc` y estados relevantes permanecen acotados y sin `NaN/inf`.
  - El balance corriente-potencia del bus DC es consistente con el modelo:
    `dVdc/dt = (ipv + i_bess - idc_inv)/Cdc` y su forma de potencia equivalente.
  - La integracion es numericamente estable en chequeo practico (misma tendencia
    y metricas principales similares bajo ajuste moderado de tolerancias/paso).
  - Desempeno dinamico post-escalon: se cumple `t_rec_95_pre` si aplica, o en
    presencia de nuevo punto operativo se verifica permanencia en banda `+-2 %`
    respecto al valor final post-escalon en el tramo final de simulacion.
- FAIL en caso contrario.
- Este PASS/FAIL es un criterio interno de validacion del modelo en etapa
  baseline; no es criterio normativo ni especificacion final de control
  grid-forming.

Respaldo conceptual general:

- El enfoque de balance promedio en bus DC es consistente con literatura de
  microrredes/inversores DC-link en los articulos de soporte revisados en el
  proyecto (sin reclamar citas textuales aqui).


