# Auditoría documental: datos para identificar un ECM 1RC Nissan Leaf de segunda vida

**Fecha:** 3 de noviembre de 2026
**Alcance:** disponibilidad de evidencia experimental para OCV, R0, R1 y C1, con énfasis en grupos Nissan Leaf 2p de segunda vida y SoH conocido. Esta auditoría no recalibra ni cambia el modelo. El trabajo experimental HPPC de la rama `research/ornl-hppc-model-comparison` queda fuera de alcance.

## Decisión

**No se identificó un conjunto público verificable que permita identificar y validar conjuntamente OCV, R0, R1 y C1 de unidades Nissan Leaf 2p de segunda vida con SoH trazable.** Hay datos pertinentes, pero cada fuente cubre una parte distinta:

- Braco documenta unidades 2p de Nissan Leaf retiradas, envejecimiento, capacidad y resistencia DC. Los artículos disponibles no publican trazas originales V/I con resolución temporal suficiente ni parámetros identificados de un modelo 1RC por unidad.
- Cui et al. publican y enlazan un conjunto experimental de ocho unidades Nissan Leaf retiradas con caracterizaciones repetidas, HPPC y datos de operación. Los archivos locales auditados identifican ensayos de una unidad `Cell 1p1`; la designación y documentación revisadas no demuestran que sea el grupo 2p de 66 Ah empleado en este proyecto. La capacidad RPT está medida en ventana 3–4 V y no constituye por sí sola un SoH comparable con la referencia 66 Ah. Los canales de temperatura del subconjunto local revisado son ceros y no se pueden usar como mediciones térmicas. La serie permite análisis a nivel de la unidad medida, sujeto a validar protocolo, señales y referencia, pero no resuelve el caso 2p solicitado.
- Gao et al. caracterizan más de 100 packs retirados y ciclan dos celdas; informan SoH agregado y envejecimiento, pero no publican un conjunto verificable de trazas 2p con los cuatro parámetros del ECM.
- ORNL publica datos HPPC/carga/descarga de una celda Nissan Leaf de 33,1 Ah. La documentación del repositorio no establece un SoH o historial de vida comparable con las muestras de segunda vida; son útiles como referencia metodológica a escala de celda, no como validación del caso 2p.

Por tanto, **los datos disponibles no justifican sustituir por valores experimentales específicos de 2p los parámetros provisionales del ECM actual**. No se propone ningún valor nuevo ni transferencia silenciosa desde celdas de primera vida.

## Qué mide cada evidencia

| Evidencia | Qué permite sostener | Qué no debe afirmarse |
|---|---|---|
| Curva de descarga Braco | Tensión terminal dependiente de capacidad descargada, bajo la corriente/temperatura publicadas. | Que cada punto sea OCV; una curva bajo carga incluye caída óhmica y polarización. |
| Resistencia DC de pulso Braco | Resistencia aparente para la duración y el SoC del pulso. Braco 2023 presenta un procedimiento rápido de 2 min por celda para estimar capacidad y resistencia DC; la duración total del procedimiento no define por sí sola el instante de lectura de R_DC. | Que sea directamente R0 instantánea. La resistencia DC incorpora la respuesta dinámica hasta el instante de lectura y depende del protocolo. |
| HPPC con V(t), I(t) y descansos | Puede permitir estimar R0 y una o más constantes de tiempo si se conocen SoC, temperatura, escalas y reposos, y si la respuesta 1RC es identificable. | Que R1/C1 estén validados solo porque la tensión modelada ajuste el mismo pulso usado para estimarlos. Hace falta validación separada. |
| `quasi-OCV` / C/40 Cui | Referencia cuasiestática conforme al procedimiento publicado. | OCV de equilibrio sin corriente o tensión en circuito abierto, salvo que los datos incluyan y documenten reposo/relajación suficiente. |
| Capacidad de RPT | Capacidad en una ventana, tasa y temperatura específicas; puede fundamentar SoH solo respecto de una capacidad de referencia definida bajo las mismas condiciones. | SoH comparable si se divide una capacidad 3–4 V por 66 Ah nominal (o por una referencia de ventana distinta). |
| Par 2p | Debe conservarse la identidad de la pareja, su conexión y el nivel eléctrico al asociar tensión/corriente/SoH. | Convertir parámetros de una celda individual a 2p sin documentar topología y reglas de escalado. |

La etiqueta “2p” no equivale a dos muestras independientes: es un grupo paralelo. Un módulo Leaf 2s2p contiene dos grupos 2p en serie; la capacidad Ah se conserva en serie y la tensión se suma. La identificación y el escalado deben nombrar explícitamente la unidad ensayada.

## Fuentes revisadas y uso admisible

1. **Braco et al. (2020)**, “Experimental assessment of cycling ageing of lithium-ion second-life batteries from electric vehicles”, *Journal of Energy Storage* 32, 101695. [DOI: 10.1016/j.est.2020.101695](https://doi.org/10.1016/j.est.2020.101695); [versión aceptada de Universidad Pública de Navarra](https://academica-e.unavarra.es/entities/publication/c65fdf6e-8027-4e66-86cc-0e4f2a05c751). Ensayos acelerados de envejecimiento de módulos Nissan Leaf en segunda vida y mediciones de capacidad/resistencia; los resultados publicados son curvas/tablas, no archivos brutos de V/I para identificar 1RC. La campaña puede solaparse con Braco 2021; no contarla como replicación independiente sin IDs de muestras.
2. **Braco et al. (2021)**, “Experimental Assessment of First- and Second-Life Electric Vehicle Batteries: Performance, Capacity Dispersion, and Aging”. [DOI: 10.1109/TIA.2021.3075180](https://doi.org/10.1109/TIA.2021.3075180); [versión aceptada UNAV](https://academica-e.unavarra.es/bitstreams/9553c975-b6ba-46e2-8d3c-47aac1bb52e6/download). Describe módulos LMO/grafito 2s2p y ensayos de capacidad/rendimiento de primera y segunda vida. Las curvas terminales bajo carga y la dispersión publicada no forman un mapa OCV ni parámetros R1/C1.
3. **Braco et al. (2023)**, “Fast capacity and internal resistance estimation method for second-life batteries from electric vehicles”, *Applied Energy* 329, 120235. [DOI: 10.1016/j.apenergy.2022.120235](https://doi.org/10.1016/j.apenergy.2022.120235). Valida regresiones de capacidad y resistencia en 506 celdas, 203 módulos y 3 packs Leaf. Es evidencia amplia para estimación rápida de capacidad/resistencia DC; no entrega una caracterización completa 1RC por grupo 2p con SoH y trazas públicas.
4. **Cui et al. (2024)**, “Taking second-life batteries from exhausted to empowered using experiments, data analysis, and health estimation”, *Cell Reports Physical Science* 5, 101941. [DOI: 10.1016/j.xcrp.2024.101941](https://doi.org/10.1016/j.xcrp.2024.101941); [artículo completo (Stanford)](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/92.pdf); [datos y código citados por el artículo: OSF FNS57](https://osf.io/fns57/) ([DOI del proyecto](https://doi.org/10.17605/OSF.IO/FNS57)). Ocho unidades retiradas, protocolos de RPT/HPPC y operación de segunda vida. Los libros locales inspeccionados y documentados en `outputs/analysis/cui_2024_cell_1p1/BAT26-32_Cui2024_Cell1p1_auditoria.md` son de `Cell 1p1`, no acreditan un ensayo de pareja 2p de 66 Ah. RPT 3–4 V, SoH/temperatura requieren normalización antes de comparar. “Quasi OCV” no debe renombrarse OCV de equilibrio.
5. **Gao et al. (2024)**, “Evaluation of the second-life potential of the first-generation Nissan Leaf battery packs in energy storage systems”, *eTransportation* 20, 100313. [DOI: 10.1016/j.etran.2024.100313](https://doi.org/10.1016/j.etran.2024.100313); [PDF del grupo SDSU](https://chrismi.sdsu.edu/publications/214.pdf). Evaluación de más de 100 packs retirados y envejecimiento de dos celdas. Aporta contexto SoH/vida útil, no archivos V/I 2p para identificar OCV–1RC.
6. **Wiggins, Allu y Wang (2019)**, “Battery cell data from a 2013 Nissan Leaf”, ORNL. [Repositorio GitHub con CSV y descripción del protocolo](https://github.com/batterysim/nissan-leaf-data); [DOI de datos: 10.5281/zenodo.2580327](https://doi.org/10.5281/zenodo.2580327). Incluye HPPC a 10/25/40 °C y ciclos/descargas para una celda de 33,1 Ah. El repositorio no permite clasificar con confianza su estado como primera o segunda vida; sirve de apoyo metodológico a escala de celda, no como fuente de parámetros de 2p con SoH conocido.

La consulta local/Roma incluyó la auditoría del libro `OCV_SOC.xlsx`, Braco Fig. 3 y Cui `Cell 1p1`. Ese libro contiene columnas rotuladas OCV/R1/C1 pero sin procedencia, protocolo, unidades declaradas ni método de identificación. Su contenido es un mapa provisional de simulación, no evidencia experimental trazable de esos parámetros. Véase `outputs/analysis/aging_contract/auditoria_ocv_paso67.md` en la copia local original.

## Incertidumbre que conserva el 1RC provisional

- **OCV(SoC):** procedencia y condición de circuito abierto no acreditadas; eje/denominador de SoC y extremos fuera de la tabla son inciertos.
- **R0:** no se ha demostrado que el valor del mapa sea una resistencia instantánea medida con extrapolación a `t → 0+`. No intercambiarlo con R_DC a 10 s u otro instante de lectura de pulso.
- **R1 y C1:** unidades, extracción y vínculo con trazas de relajación no trazables en el libro. La constante de tiempo (R_1C_1) tampoco está validada para la pareja 2p.
- **Temperatura y SoH:** faltan para una comparación homogénea con la condición de referencia del modelo; SoH depende de capacidad, ventana, tasa y temperatura usadas en numerador y denominador.
- **Transferencia de escala:** celda individual, pareja 2p, módulo 2s2p y banco no son intercambiables. La regla de escalado necesita la topología eléctrica efectiva y validación experimental.

El ECM puede seguir usándose como **modelo provisional de integración/sensibilidad**, con esta limitación declarada. No reportar su salida como predicción validada experimentalmente de una batería Nissan Leaf 2p. La suficiencia podrá revisarse si se obtiene para las mismas parejas 2p: identidad/topología y SoH definido, V/I temporales de HPPC más reposos, temperatura, SoC/protocolo y metadatos de calibración, junto con un conjunto de validación no usado en el ajuste.

## Siguiente prioridad

Cerrar por ahora la investigación eléctrica del ECM, registrar sus parámetros como provisionales y retomar **BLAST-Lite** y los pendientes del Objetivo 1 según la priorización de BAT26-32 y BAT26-49–52. Reabrir la identificación eléctrica solo ante adquisición verificable de los datos faltantes. No se modificaron BESS, VSG, PI, DC/DC, `OCV_SOC.xlsx` ni `main`; no se ejecutaron simulaciones ni validaciones de software.
