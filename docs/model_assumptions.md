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


