# Identificación exploratoria HPPC ORNL, 25 °C

Fuente: Wiggins, Allu y Wang, [repositorio original](https://github.com/batterysim/nissan-leaf-data), [DOI 10.5281/zenodo.2580327](https://doi.org/10.5281/zenodo.2580327), commit `b2222ed14a678424c1ba4cd07b4adea38b9d08b0`, blob `a2df79c0721770b13f148ff91aad4a7fb5dc1590`, 877627 bytes, SHA-256 `8b4135978f150d465dbd5b83f55f7235b8fbd0c39a91fa9033a65c11622f6bf1`. Se conserva el CSV original y su licencia MIT. El README de origen indica celda Nissan Leaf 2013, 33,1 Ah nominales y temperatura ambiente de 25 °C; no proporciona temperatura de celda en este ensayo ni demuestra su estado de envejecimiento. No corresponde a una muestra SL de Braco.

## Procedimiento

Ejecutar `py -3.13 research/hppc/identify.py` y `py -3.13 -m unittest discover -s research/hppc -p 'test_*.py' -v` con numpy, pandas y scipy instalados. `results.json` contiene resultados completos, por fase, errores máximos, sesgos, sensibilidades y ajustes individuales. El script verifica el SHA-256 antes de leer; la regla `.gitattributes` conserva los bytes originales. Versiones usadas: Python 3.13, SciPy 1.17.0.

Son 13248 registros, tiempo en s, corriente en A y tensión en V; corriente de la fuente negativa en descarga, invertida aquí. Se detectan diez secuencias mediante I < −25 A: cada una incluye 60 muestras de paso 6 (descarga, 30 s), 40 de paso 7 (reposo, 40 s), 100 de paso 8 (regeneración, 10 s). El primer punto de cada secuencia es la última muestra del reposo largo anterior. Las transiciones y corriente de regeneración se usan medidas, incluida su rampa. El integrador analítico asume corriente constante igual a la muestra final en cada intervalo; la resolución y el sincronismo de escalones limitan R0. No se supone tensión al final de 40 s igual a OCV.

Entrenamiento: pulsos 1, 2, 4, 5, 7 y 8; evaluación: 3, 6, 9 y 10. El 10 examina explícitamente el extremo de descarga. La evaluación es dentro del mismo ensayo y celda, no validación independiente de otra celda, ensayo o envejecimiento. Cada trayectoria se condiciona a su tensión medida antes del pulso, incluso en evaluación: no es predicción absoluta ciega de OCV. La evaluación no ajusta parámetros con tensiones de los segmentos reservados.

El modelo utiliza `V=U(q)-R0*i-vrc`, `dvrc/dt=(R1*i-vrc)/tau`; `i` positiva en descarga. Se mantiene vrc continua entre descarga, reposo y regeneración; cada secuencia se inicializa con un único vrc0 común estimado, no se reinicia en las transiciones. El reposo largo motiva examinar también vrc0=0, pero no garantiza equilibrio. `U(q)` varía linealmente dentro de cada secuencia: su pendiente se interpola usando exclusivamente tensiones previas a pulsos de entrenamiento tras reposos largos y carga acumulada; son proxies de cuasi-OCV, no OCV de equilibrio. En los pulsos 9–10 la pendiente se extrapola constante desde el último intervalo entrenado: el extremo es especialmente incierto. La carga acumulada usa integración trapezoidal de corriente muestreada y 33,1 Ah nominales como referencia de escala de SoC; no se conoce SoC absoluto ni capacidad efectiva de esta muestra. El cambio local de tensión depende de Ah, no del origen de SoC. El cambio de corriente en intervalos dispersos puede sesgar la coordenada de carga y su pendiente.

Se minimizan residuos de tensión sin ponderar: las 100 muestras de regeneración tienen más peso que las 60 de descarga y 40 de reposo; no hay precisiones instrumentales ni pesos estadísticos inventados. Los parámetros son constantes para todos los SoC. La alternativa aislada ajusta cada descarga de entrenamiento, suponiendo vrc0=0 y la misma pendiente, y usa la mediana de los parámetros. El cálculo histórico aproximado utiliza las medianas anteriores, vrc0=0 y tensión OCV constante; sus pulsos 2–9 incluyeron parte del conjunto ahora reservado, por tanto sus errores no son evaluación independiente. Los errores abajo se expresan en mV, residuo modelo menos medición.

## Resultados

| Método | R0 mΩ | R1 mΩ | C1 F | τ s | vrc0 mV |
|---|---:|---:|---:|---:|---:|
| Aislado anterior, mediana aproximada | 1,610 | 1,342 | 18 793 | 25,22 | 0 supuesto |
| Aislado recalculado, solo entrenamiento | 1,606 | 1,059 | 18 427 | 19,51 | 0 supuesto |
| Conjunto | 1,643 | 1,054 | 22 292 | 23,50 | −5,51 estimado común |

La C1 histórica se obtiene de las medianas aproximadas τ/R1, no es la mediana previa de C1 (18,68 kF). Los métodos difieren en OCV y estado inicial, por lo que la diferencia no prueba por sí sola una causa de la discrepancia τ histórica pulso 25,22 s versus reposo 17,47 s.

| Método | RMSE entrenamiento descarga / reposo / regeneración | RMSE evaluación descarga / reposo / regeneración |
|---|---|---|
| Histórico, contaminado por selección anterior | 7,65 / 9,24 / 8,90 | 12,82 / 22,13 / 20,05 |
| Aislado recalculado | 6,61 / 7,45 / 6,64 | 12,10 / 21,18 / 18,52 |
| Conjunto | 6,40 / 5,14 / 2,54 | 11,24 / 18,04 / 14,75 |

En el pulso 10 el ajuste conjunto produce RMSE de 21,70 / 35,63 / 29,29 mV y sesgo +18,98 / +35,62 / +29,06 mV, respectivamente. La extrapolación de pendiente de cuasi-OCV y dependencia de parámetros con SoC son explicaciones posibles; no se identifica una causa única. El RMSE global está dominado por el último pulso y por ponderación por muestra. `results.json` conserva N y máximos, no solo promedios.

Con polarización inicial fija en 0 mV, el ajuste conjunto da R1=1,719 mΩ y τ=44,04 s; con +5 mV, 2,346 mΩ y 63,01 s. Los RMSE de evaluación apenas cambian: descarga 11,45 y 11,52 mV frente a 11,24 mV libre. Duplicar la pendiente de cuasi-OCV da τ=18,72 s; anularla da 29,33 s. Quitar un pulso de entrenamiento y recalcular las pendientes da τ entre 22,83 y 26,35 s, pero no mide la incertidumbre de OCV ni de polarización inicial. Los valores singulares del Jacobiano escalado y sus escalas están en el JSON: describen sensibilidad local bajo el modelo, no una incertidumbre instrumental. Sin réplicas, precisión instrumental ni OCV independiente, no es defendible un intervalo de confianza estadístico ni afirmar identificación única de R1, C1, τ y vrc0. La tensión de polarización estimada no es una medición directa ni debe interpretarse como diagnóstico físico individual.

El 1RC conjunto mejora los tres segmentos frente a la mediana aislada bajo esta partición y reproduce parcialmente los transitorios intermedios, pero sus residuos sistemáticos, su fuerte sensibilidad a hipótesis y el deterioro en el extremo no justifican considerarlo suficiente para todo el rango ni identificar una constante de tiempo física única. No se ha comparado formalmente con 2RC; tampoco existe umbral de aceptación experimental acordado. Siguiente paso: obtener OCV cuasi-estática/relajaciones largas y HPPC de celdas SL representativas, repetir ensayos y comparar 1RC dependiente de SoC frente a 2RC con particiones por ensayo y criterios definidos previamente. Mantener separadas las capacidades 44,1 Ah de tesis y 43,5 Ah de Braco; no trasladar estos parámetros ORNL al banco ni integrar DC/DC.
