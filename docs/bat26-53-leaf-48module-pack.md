# BAT26-53 — Escala física aprobada: pack Nissan Leaf 48x(2s2p)

**Decisión del tesista: 6 de noviembre de 2026. Estado: escenario paramétrico, sin certificación experimental ni convertidor seleccionado.**

## Frontera física y capacidad

Se adopta una cadena **homogénea** de 48 módulos Nissan Leaf 2s2p en serie: 96 parejas de celdas 2p en serie, una cadena y 192 celdas individuales. En Braco et al. (2021, tabla I), cada módulo presenta 7,5 V nominales, intervalo 5,0–8,3 V y capacidad 66 Ah. Braco et al. (2023, tabla 1) consignan 3,75 V/66 Ah por unidad 2p. Los Ah de una conexión serie **no se multiplican por 48 ni por 96**.

El valor **44,1 Ah** es la capacidad inicial del **escenario de tesis**, no una medición de un pack identificado en Braco. El SoH inicial es 44,1/66=0,6681818. La tensión nominal resulta 48x7,5=**360 V**. Con tensión nominal constante, la energía aproximada es 360x44,1/1000=**15,876 kWh**; en ventana SoC de 10 a 90 %, 15,876x0,8=**12,7008 kWh**. Ambas cifras son estimaciones ideales, no energía terminal integrada ni energía suministrada al bus después de pérdidas.

Se conserva el mismo CapacitySnapshot por unidad 2p para transportar la retención BLAST hacia la cadena homogénea; no se vuelve a contabilizar la pérdida de primera vida. El resultado histórico BAT26-45 Qeff=35,853796 Ah es una **simulación sintética** que puede transportarse como escenario a la cadena, pero no constituye envejecimiento medido de un pack.

## Tensión y puertos separados

El rango seleccionado de Braco (2021), 5–8,3 V por módulo, produce **240–398,4 V** por cadena. Castillo-Martínez et al. (2022) documentan **240–403,2 V** para **otro pack real**. Las diferencias de máximos entre estudios se preservan; no se sustituyen los datos de una publicación por los de otra. El pack puede presentar tensiones tanto inferiores como superiores a los **340 V** de referencia del bus DC. Si este bus debe permanecer regulado, es necesaria una interfaz bidireccional que admita las dos relaciones de tensión o una arquitectura alternativa por decidir.

Cadena física: pareja 2p (3,75 V, 66 Ah nominales) → dos parejas en serie (módulo 2s2p) → 48 módulos en serie (puerto batería, Vpack variable, Ipack) → convertidor bidireccional **por seleccionar** → puerto bus DC (referencia 340 V, Ibus, Pbus) → inversor GFM → PCC → IEEE 33 con postprocesamiento estático unidireccional.

La corriente de la cadena Ipack atraviesa cada pareja 2p; no se multiplica por 96. La corriente del bus se obtiene de Pbus/Vdc. En descarga, Pbus = eta_discharge x Ppack y, en carga, magnitud(Ppack_ch) = eta_charge x magnitud(Pbus_ch). La eficiencia se **suministra como parámetro**, no como valor de hardware aprobado. Solo como ejemplo ideal sin pérdidas, a 3 kW la corriente del pack a 360 V sería 8,3333 A, y la del bus a 340 V sería 8,8235 A.

## Código y verificación de esta iteración

Se incorporan únicamente el modelo paramétrico **src/bess/leaf_48module_pack.py**, la prueba **src/validation/validate_bat26_53_pack_48s.py** y este documento. El modelo aprovecha CapacitySnapshot y el adaptador algebraico bidireccional **src/bess/dc_dc_adapter.py** que ya existía; no duplica la ecuación 1RC, añade estados ni cambia el controlador VSG.

Para el adaptador existente se definen n_series=96, n_parallel=1 y tensiones por unidad 2p de 2,50 a 4,15 V. Los parámetros de eficiencia de carga/descarga, corriente límite de la pareja 2p, corriente límite del bus y potencia máxima del convertidor se exigen al invocar la interfaz. **No hay ratings certificados disponibles**.

Ejecutar en PowerShell desde la raíz del repositorio:

    python src/validation/validate_bat26_53_pack_48s.py

Se verifican estructura, capacidad serie, SoH, energía ideal, envejecimiento de escenario, descarga y carga algebraicas, conservación de potencia, límites de SoC e identificación de variables por puerto. El fixture de demostración **solamente para pruebas** utiliza eta_charge=eta_discharge=0,95; límites de corriente 2p de 10 A; corriente de bus de 20 A y potencia de bus de 5000 W. **Ninguno de esos valores representa un rating aceptado para el convertidor o BMS real.**

No se modifican **src/config.py**, **src/microgrid.py**, **src/microgrid_bess_pi.py**, las ecuaciones y estados ODE, la ley BLAST, el convenio de corriente positiva de descarga, M=80, D=1500 ni las conexiones a IEEE 33. Los límites históricos del baseline 66 A y 22,44 kW **no demuestran que el pack y su convertidor puedan entregar 22,44 kW**.

## Pendientes

La etapa D1 aún requiere elegir topología y eficiencia del convertidor, ratings continuos/transitorios, limitaciones del BMS por SoC/SoH y temperatura, tensión terminal por OCV/RC de un pack real y dispersión entre módulos. El soporte GFM en descarga positiva a cuatro SoH corresponde a D2; la representatividad de p_ss_kw sobre IEEE 33 corresponde a D6; la optimización de despacho corresponde a D5. Ninguno se declara validado por este módulo de escala.

## Referencias

Braco et al. (2021), *Experimental Assessment of First- and Second-Life Electric Vehicle Batteries: Performance, Capacity Dispersion, and Aging*, IEEE TIA, **tabla I**. DOI: https://doi.org/10.1109/TIA.2021.3075180.

Braco et al. (2023), *Fast capacity and internal resistance estimation method for second-life batteries from electric vehicles*, Applied Energy 329, 120235, **tabla 1**. DOI: https://doi.org/10.1016/j.apenergy.2022.120235.

Castillo-Martínez et al. (2022), *Design and On-Field Validation of an Embedded System for Monitoring Second-Life Electric Vehicle Lithium-Ion Batteries*, Sensors 22(17), 6376, **tabla 1**. DOI: https://doi.org/10.3390/s22176376.

Ríos, Pagano y Lucas (2021), *Bidirectional Power Sharing for DC Microgrid Enabled by Dual Active Bridge DC-DC Converter*, Energies 14(2), 404, **alternativa de arquitectura**, no DAB implementado. DOI: https://doi.org/10.3390/en14020404.
