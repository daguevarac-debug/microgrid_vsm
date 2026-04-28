# Supuestos simplificados vigentes

Este documento consolida los supuestos activos del baseline para mantener el
README corto y enfocado en ejecución/estado.

## Resumen académico de supuestos del baseline

Los supuestos de este documento delimitan el alcance del modelo físico-matemático
y dinámico usado en la Actividad 1.3. El modelo corresponde a un baseline trazable
para una microrred PV + BESS-SLB, orientado a estudiar coherencia eléctrica y
operación preliminar del conjunto PV + BESS-SLB + bus DC + inversor + filtro LCL
+ carga/PCC. No representa todavía una validación experimental, un diseño óptimo
final ni una estrategia grid-forming/VSG completamente integrada.

- Temperatura constante: no se implementa un modelo térmico dinámico. La
  temperatura se trata como condición asumida o entrada de los submodelos que la
  requieren.
- Modelo promediado: la dinámica del convertidor se representa sin conmutación
  PWM explícita ni armónicos de alta frecuencia.
- Carga simplificada: la carga se modela como una carga trifásica agregada,
  balanceada y de tipo R-L; no se incluye un modelo ZIP completo ni perfiles
  reales medidos de demanda.
- Degradación de primer orden: el SoH, la capacidad efectiva y la resistencia
  interna del BESS-SLB se representan mediante leyes simplificadas, sin modelo
  electroquímico detallado.
- Alcance de validez: el baseline es adecuado para validación práctica interna y
  análisis preliminar de coherencia dinámica del sistema implementado, no para
  certificar desempeño experimental ni optimización final.
- Limitaciones conocidas: siguen pendientes la integración final del BESS con
  convertidor DC/DC y BMS detallados, el control grid-forming/VSG acoplado a la
  planta completa, la estrategia final de inercia virtual y la validación formal
  con escenarios experimentales o perfiles medidos.

## BESS-SLB

- Modelo térmico: no implementado (temperatura constante asumida).
- Degradación: primer orden lineal, sin modelo de rodilla ni efectos no lineales.
- OCV/R1/C1: datos interpolados desde tabla; no incluye histéresis.
- R0 aging: ley empírica simplificada, no copiada textualmente de literatura.
- El BESS-SLB esta modelado y validado, y existe una integracion preliminar/conservadora al bus DC mediante `MicrogridWithBESS`.

## Alcance del IEEE 33 en la tesis

El sistema IEEE 33 se usa como red benchmark de distribucion para evaluar el
efecto de una inyeccion equivalente de microrred en un sistema radial. El
objetivo de esta parte de la tesis es validar el caso de estudio en red mediante
la comparacion estatica entre el caso base del IEEE 33 y el caso con microrred
actualizada.

El acople implementado es secuencial one-way:

1. Primero se simula la microrred local.
2. Luego se calcula `p_ss_kw` como promedio estacionario de `p_pcc`.
3. Despues se inyecta esa potencia como `sgen` estatico en el PCC del IEEE 33.

El IEEE 33 no retroalimenta dinamicamente la microrred y no hay co-simulacion en
tiempo real. Tampoco se modela explicitamente un transformador LV/MV entre la
microrred y la red benchmark. El resultado debe interpretarse como
postprocesamiento estatico de red, no como validacion final de estabilidad
dinamica de red.

En el caso actualizado, el BESS actua dentro de la microrred, acoplado
preliminarmente al bus DC mediante `MicrogridWithBESS`. El BESS no se modela en
pandapower como bateria independiente, carga, generador ni elemento `storage`
separado. En el IEEE 33 solo se observa la potencia neta equivalente de la
microrred en el PCC.

El PCC usado es el Nodo 18 del IEEE 33 y el nivel de tension de la red se
mantiene en `12.66 kV`. Este caso tampoco representa un acople dinamico
GFM/VSG integrado al IEEE 33; el bloque GFM/VSG permanece como estructura
minima aislada hasta su integracion explicita en una etapa posterior.

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

## Modelo de carga de la microrred (baseline)

El modelo de carga de la microrred evoluciona desde el cierre puramente
resistivo inicial hacia una carga agregada AC trifasica balanceada de
impedancia constante R-L, con factor de potencia inductivo. En el baseline
actual, `Microgrid.load_profile` representa potencia activa trifasica agregada
`P_load(t)` para construir una impedancia R-L equivalente; no representa todavia
un perfil horario medido ni una entrada independiente `Q_load(t)`.

La carga nominal inicial se define como:

- `P_load_nominal = 3000 W`.
- `fp = 0.95` inductivo.
- `V_ln_rms = 110 V`.
- `f = 60 Hz`.
- Escalon baseline: `P_load(t)` pasa de `1.00*P_load_nominal` a
  `1.20*P_load_nominal`.

Trazabilidad con el baseline resistivo anterior:

- `R1 = 14.4 ohm` equivale aproximadamente a
  `P1 = 3*V_ln_rms^2/R1 = 3*110^2/14.4 = 2520.8 W`.
- `R2 = 9.6 ohm` equivale aproximadamente a
  `P2 = 3*V_ln_rms^2/R2 = 3*110^2/9.6 = 3781.2 W`.
- La nueva magnitud nominal de `3000 W` se adopta como valor intermedio
  prudente y coherente con esas potencias previas.

Para una carga serie R-L balanceada por fase, el modelo usa:

- `phi = arccos(fp)`.
- `Q_load = P_load*tan(phi)`, positiva para carga inductiva.
- `|Z| = 3*V_ln_rms^2*fp/P_load`.
- `R_load = |Z|*fp`.
- `X_load = |Z|*sin(phi)`.
- `L_load = X_load/(2*pi*f)`.

La ecuacion de carga por fase es `v_pcc = R_load*i2 + L_load*di2/dt`. Para no
agregar estados nuevos al vector dinamico, esta relacion se sustituye
directamente en la ecuacion del inductor de salida del filtro LCL:

- `di2/dt = (vc - (R2_LCL + R_load)*i2)/(L2_LCL + L_load)`.
- `v_pcc = R_load*i2 + L_load*di2/dt`.

Esta implementacion mantiene el orden del vector de estados y cambia solo el
cierre local de la carga en el lado AC.

### Perturbaciones de prueba de carga

Para pruebas iniciales y futuras pruebas de operacion aislada se definen tres
niveles simples de carga activa agregada:

- Caso nominal: `P_load = 1.00*P_load_nominal = 3000 W`.
- Escalon moderado: `P_load = 1.20*P_load_nominal = 3600 W`, equivalente a un
  aumento de carga del `20 %`.
- Cambio brusco: `P_load = 1.40*P_load_nominal = 4200 W`, equivalente a un
  aumento severo de carga del `40 %`.

En los tres casos se mantiene `fp = 0.95` inductivo y la potencia reactiva se
calcula como:

- `Q_load = P_load*tan(arccos(fp))`.

Por tanto, cada nivel de carga conserva la representacion R-L equivalente y
solo cambia la magnitud de la impedancia calculada. El caso baseline por
defecto usa el escalon moderado: antes de `t_step`, la carga es nominal; despues
de `t_step`, la carga aumenta al `120 %` de `P_load_nominal`.

Estas perturbaciones son escenarios de prueba, no perfiles reales medidos. Los
perfiles horarios, ruido estocastico, desbalance de fases, modelos ZIP completos
y modelos de motores quedan fuera de esta subtarea.

### Escenario de operacion estable en regimen permanente

El primer escenario de operacion aislada se define como caso nominal estable sin
perturbacion de carga:

- Carga constante `P_load = P_load_nominal = 3000 W`.
- Factor de potencia constante `fp = 0.95` inductivo.
- Representacion R-L balanceada equivalente.
- Sin escalon de carga; no se usa el escalon moderado por defecto.
- Sin BESS activo en esta subtarea.
- Sin perfil horario real, ruido estocastico, cambio brusco, desbalance, motores
  ni modelo ZIP completo.

El objetivo de este escenario es verificar estabilidad numerica/practica del
caso nominal aislado antes de introducir perturbaciones de carga o soporte BESS.
No representa todavia una validacion experimental ni un perfil real de demanda.

### Escenario con escalon de carga del 20 %

El segundo escenario de operacion aislada aplica una perturbacion moderada de
demanda sobre la carga R-L agregada:

- Carga inicial `P_load = 3000 W`.
- Carga final `P_load = 3600 W`, equivalente a `1.20*P_load_nominal`.
- Factor de potencia constante `fp = 0.95` inductivo.
- Sin BESS activo en esta subtarea.
- Sin perfil horario real, ruido estocastico, desbalance, motores ni modelo ZIP
  completo.

El objetivo es verificar la respuesta dinamica practica ante una perturbacion
moderada de demanda. Este escenario no representa un perfil medido ni un evento
estocastico; queda como base para comparaciones posteriores con soporte BESS.

### Escenario de cambio brusco de carga

El tercer escenario de operacion aislada aplica una perturbacion severa de
demanda sobre la carga R-L agregada:

- Carga inicial `P_load = 3000 W`.
- Carga final `P_load = 4200 W`, equivalente a `1.40*P_load_nominal`.
- Incremento de carga del `40 %`.
- Factor de potencia constante `fp = 0.95` inductivo.
- Sin BESS activo en esta subtarea.
- Sin perfil horario real, ruido estocastico, desbalance, motores ni modelo ZIP
  completo.

El objetivo es verificar la respuesta ante una perturbacion severa de demanda.
Este escenario no representa todavia un perfil medido ni un evento estocastico;
queda como caso de estres para comparaciones posteriores con soporte BESS.

### Escenario comparativo con y sin BESS

El escenario comparativo usa el escalon moderado del `20 %` para evaluar la
misma perturbacion con y sin almacenamiento:

- Carga inicial `P_load = 3000 W`.
- Carga final `P_load = 3600 W`, equivalente a `1.20*P_load_nominal`.
- Factor de potencia constante `fp = 0.95` inductivo.
- Caso sin BESS: `Microgrid`.
- Caso con BESS: `MicrogridWithBESS`, usando la integracion preliminar al bus
  DC ya existente.
- Se revisan `Vdc`, potencias, corrientes, `i_bess`, `p_bess_dc`, SoC y SoH.

Este escenario no exige todavia una mejora dinamica obligatoria del BESS frente
al caso sin almacenamiento; la comparacion se reporta como diagnostico. Tampoco
representa la estrategia final grid-forming/VSG, un BMS final ni un convertidor
DC/DC detallado. Su objetivo es cerrar los escenarios con almacenamiento y sin
almacenamiento bajo una misma perturbacion de carga.

### Justificacion de representatividad

La carga R-L equivalente se adopta como aproximacion baseline para cerrar
electricamente el PCC y evaluar una perturbacion basica de carga activa/reactiva
sin introducir complejidad adicional en esta etapa. Esta representacion es util
para validaciones iniciales del acoplamiento PV, DC-link, inversor, filtro LCL y
PCC, pero no sustituye una caracterizacion medida de demanda real ni debe
presentarse como modelo final de carga de la microrred.

El respaldo conceptual se limita a las ideas explicitas de las referencias
revisadas:

- IEEE PES Task Force on Microgrid Dynamic Modeling (2023) reconoce que la
  representacion de cargas es relevante para estudios de dinamica y estabilidad
  de microrredes. Tambien clasifica los modelos de carga para estos estudios en
  estaticos, dinamicos, compuestos y cargas con interfaz de electronica de
  potencia; ademas, indica que es practica comun agregar tipos de carga
  similares como cargas agregadas. La seleccion del enfoque de modelado depende
  de la naturaleza del estudio de estabilidad, del numero de cargas y tamano de
  la microrred, del tamano relativo de cada carga y de la disponibilidad de
  datos.
- Fachini et al. (2024) se usa solo como respaldo de que, en estudios de
  microrred con PV, BESS y generacion convencional, pueden emplearse cargas
  agregadas dentro de la microrred. Ese trabajo considera una carga agregada de
  la microrred y agrega variaciones estocasticas y perfiles de carga para
  pruebas de operacion en isla y resincronizacion. No se trasladan a este
  repositorio su arquitectura MPC ni sus valores numericos.
- Madjovski et al. (2024) se usa solo como respaldo de que el modelado de carga
  es importante para estabilidad en sistemas de distribucion con generacion
  renovable. Ese trabajo considera modelos estaticos, dinamicos y compuestos, y
  presenta el modelo ZIP como modelo estatico que combina impedancia constante,
  corriente constante y potencia constante. No se adoptan aqui sus parametros ni
  sus resultados.

Como decision de tesis, la carga objetivo para etapas posteriores sigue siendo
una carga agregada AC trifasica balanceada vista desde el PCC. Se representara
posteriormente mediante perfiles `P_load(t)` y `Q_load(t)`, donde `Q_load(t)`
podra calcularse a partir de un factor de potencia constante o definirse desde
datos disponibles. El baseline R-L actual queda como transicion simple hacia ese
perfil agregado P-Q.

### Simplificaciones vigentes del modelo de carga

El modelo de carga vigente se interpreta como una carga agregada equivalente
vista desde el PCC, no como una representacion de equipos individuales. Sus
simplificaciones activas son:

- Se asume operacion AC trifasica balanceada.
- Se usa una carga estatica de impedancia constante R-L.
- Se mantiene `fp = 0.95` inductivo como factor de potencia constante.
- Se usa `P_load_nominal = 3000 W`.
- Se definen perturbaciones deterministicas nominal, `+20 %` y `+40 %`.
- Durante las perturbaciones se conserva el mismo factor de potencia.
- No se usa todavia un perfil horario real medido.
- No se incluyen variaciones estocasticas.
- No se incluye desbalance de fases.
- No se incluye un modelo ZIP completo.
- No se incluyen motores de induccion.
- No se incluyen cargas con interfaz de electronica de potencia, como SMPS,
  VFD o cargadores EV.
- No se incluyen armonicos.
- No se incluye dependencia explicita con frecuencia.
- No representa todavia una caracterizacion medida de demanda real.
- No sustituye una validacion experimental de carga.

Estas simplificaciones se consideran aceptables para esta etapa porque permiten
cerrar un baseline dinamico simple, aplicar perturbaciones de carga trazables y
conservar compatibilidad con las validaciones existentes. Tambien dejan
preparada la transicion posterior hacia perfiles `P_load(t)` y `Q_load(t)` mas
realistas.

Esta subtarea define la magnitud nominal inicial y reemplaza el cierre
puramente resistivo por una impedancia R-L balanceada. La implementacion de un
perfil horario real `P_load(t), Q_load(t)`, con magnitudes medidas o escenarios
de demanda mas detallados, queda para subtareas posteriores.

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

### Verificacion de operacion dentro de rango

`src/validation/validate_bess_integrated_nominal.py` verifica que, durante el
caso nominal integrado baseline, el BESS permanezca dentro de sus restricciones
operativas principales.

Variables revisadas:

- `soc_bess` y `soh_bess`.
- `i_bess` y `p_bess_dc`.
- `Vdc` y `vt_bess`.

Limites aplicados:

- `soc_min <= soc_bess <= soc_max`.
- `soh_min <= soh_bess <= 1.0`.
- `abs(i_bess) <= i_bess_max`.
- `abs(p_bess_dc) <= p_bess_dc_max`.
- `Vdc > 0` y `vt_bess > 0`.
- Identidad diagnostica `p_bess_dc = Vdc * i_bess`.

Esta prueba verifica el caso nominal integrado del baseline actual. No reemplaza
una validacion exhaustiva con perfiles reales de operacion, ensayos de estres,
estrategias BMS finales ni un modelo detallado del convertidor DC/DC.

### Dependencia del SoH en capacidad efectiva y resistencia interna

El modelo BESS-SLB 1RC ya incorpora dependencia interna del SoH en capacidad
efectiva y resistencia serie:

- `SoH = max(soh_min, SoH_init - k_deg * z_deg)`.
- `Q_eff = Q_nom_ref * SoH`.
- `R0(SoH) = R0_nominal * (1 + k_R * (1 - SoH))`.

La capacidad efectiva `Q_eff` afecta directamente la dinamica de SoC mediante:

- `dSoC/dt = -i_bess / (3600 * Q_eff)`.

La resistencia interna `R0(SoH)` afecta directamente la tension terminal del
modelo Thevenin:

- `Vt_bess = OCV(SoC) - i_bess * R0(SoH) - V_rc`.

En la implementacion actual, `effective_capacity_from_z_deg(z_deg)` calcula
`Q_eff` usando `SoH(z_deg)`, `r0_from_z_deg(z_deg)` calcula `R0` usando
`SoH(z_deg)`, `rhs()` usa `Q_eff` para `dSoC/dt` y `terminal_voltage()` usa
`R0(SoH)`. Esta subtarea no modifica el modelo 1RC; solo agrega trazabilidad
documental de relaciones ya implementadas.

### Dependencia del SoH en corriente y potencia disponibles

Los limites nominales se conservan como referencias baseline:

- `i_bess_max_nominal = 66 A`.
- `p_bess_dc_max_nominal = 22440 W`.

La disponibilidad operacional de soporte se reduce con el SoH:

- `i_bess_max_available = i_bess_max_nominal * SoH`.
- `p_bess_dc_max_available = min(p_bess_dc_max_nominal, Vdc_ref * i_bess_max_available)`.

Para el caso integrado inicial, `SoH ~= 0.668`, por lo que:

- `i_bess_max_available ~= 44.1 A`.
- `p_bess_dc_max_available ~= 14.99 kW`.

El limite nominal de `66 A` se mantiene como referencia `1C` basada en la
capacidad nominal, pero la corriente y potencia disponibles para soporte se
reducen con el SoH del BESS. Esta es una aproximacion operacional baseline para
la integracion preliminar BESS-DC-link; no representa una logica BMS final ni
un rating definitivo del convertidor DC/DC.

### Escenarios de SoH para comparacion integrada

`src/validation/compare_bess_soh_scenarios.py` compara la integracion preliminar
BESS-DC-link bajo el mismo escalon de carga para tres escenarios:

- `SoH = 1.00`.
- `SoH = 0.70`.
- `SoH` nominal actual `~= 0.668`.

Para todos los casos se conserva el mismo perfil de carga y se comparan:

- `Vdc`.
- `i_bess`.
- `p_bess_dc`.
- `soc_bess`.
- `vt_bess`.

La prueba mide el impacto de la disponibilidad de soporte del BESS dependiente
del SoH sobre la respuesta integrada baseline. No es una validacion final del
control ni de una estrategia BMS.

El impacto sobre frecuencia no se interpreta todavia como resultado final,
porque el modelo actual sigue siendo baseline/grid-following y no esta acoplado
a grid-forming/VSG. Cualquier diagnostico de frecuencia queda fuera de las
metricas formales hasta activar esa etapa.

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


