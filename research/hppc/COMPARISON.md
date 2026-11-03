# Comparación exploratoria 1RC, 1RC variable y 2RC

El [protocolo](PROTOCOL.md) se registró en el commit `e62bddc` antes de calcular estos resultados. Datos, procedencia y licencia: [README anterior](README.md); CSV original SHA-256 `8b4135978f150d465dbd5b83f55f7235b8fbd0c39a91fa9033a65c11622f6bf1`. Ejecución: `py -3.13 research/hppc/compare_models.py`; pruebas: `py -3.13 -m unittest discover -s research/hppc -p 'test_*.py' -v`. El detalle numérico, incluido RMSE, MAE, sesgo y máximo por pulso/fase y todos los arranques/sensibilidades, se encuentra en `comparison_results.json`.

## Auditoría y alcance

`identify.residual()` excluía el paso 5, lo que también admitía cualquier otro paso presente. Se reemplazó por una selección explícita de pasos 6, 7 y 8; el CSV procesado ya contenía exclusivamente la muestra previa 5 y esos pasos, así que la selección y los resultados históricos para estos datos no cambian. Se añadieron pruebas con pasos ajenos. La nueva comparación usa igual información y pendientes de cuasi-OCV para los tres modelos. Cada pulso se ancla a su tensión medida inmediatamente antes de la descarga; no se obtiene tensión absoluta ciega. La polarización se arrastra entre descarga, reposo y regeneración, no se reinicia tras 40 s.

El entrenamiento usa 1/2/4/5/7/8, la evaluación 3/6/9 y 10. Esos datos reservados ya fueron examinados en la fase anterior: no representan una prueba ciega intacta, otro ensayo o celda. La variación local de cuasi-OCV se calcula solo a partir de antecedentes de entrenamiento; el SoC absoluto, la OCV de equilibrio, la capacidad efectiva y la temperatura real de celda no se conocen. La coordenada es capacidad descargada acumulada, no SoC absoluto; el modelo variable congela su dependencia fuera del intervalo de entrenamiento, incluidos 9 y 10. Hay aproximación de corriente constante por intervalo y los primeros datos tras un escalón limitan el significado de R0 y de la rama rápida.

## Parámetros por celda y resultados

| Modelo | R0 mΩ | R1 mΩ | τ1 s | C1 F | R2 mΩ | τ2 s | C2 F | v0 mV |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1RC constante | 1,658 | 1,026 | 23,87 | 23 272 | — | — | — | −5,77 |
| 1RC variable, centro del entrenamiento | 1,671 | 1,060 | 26,19 | 24 720 | — | — | — | −5,18 |
| 2RC constante | 1,515 | 0,252 | 2,20 | 8 741 | 1,299 | 39,21 | 30 182 | −3,03 |

Los coeficientes logarítmicos variables para R0, R1 y τ1 son −0,0275, −0,3604 y −0,0302. En el primer pulso el modelo variable estima R1=1,519 mΩ y τ=27,00 s; en el último extremo entrenado, y por saturación en los pulsos 9/10, R1=0,739 mΩ y τ=25,42 s. Estos parámetros ajustados no son transferencia a la batería SL. La polarización inicial es un parámetro común de ajuste, no medición directa.

| Modelo | Indicador entrenamiento mV | Indicador 3/6/9 mV | Indicador 10 mV |
|---|---:|---:|---:|
| 1RC constante | 4,958 | 2,952 | 29,459 |
| 1RC variable | 3,871 | 2,174 | 32,206 |
| 2RC constante | 4,886 | 2,831 | 29,433 |

El indicador es la raíz del promedio, con igual peso por fase y pulso, de RMSE²; no es una tolerancia experimental. La distribución por fase, RMSE en mV:

| Modelo y conjunto | Descarga | Reposo | Regeneración |
|---|---:|---:|---:|
| 1RC constante, 3/6/9 | 3,390 | 3,223 | 2,065 |
| 1RC variable, 3/6/9 | 1,878 | 2,003 | 2,576 |
| 2RC, 3/6/9 | 3,360 | 3,180 | 1,628 |
| 1RC constante, 10 | 21,751 | 35,697 | 29,260 |
| 1RC variable, 10 | 27,498 | 39,178 | 28,646 |
| 2RC, 10 | 21,872 | 35,612 | 29,194 |

El modelo variable mejora el indicador 3/6/9 un 26,4 %, pero empeora el 10 un 9,3 %, próximo al límite descriptivo prerregistrado del 10 %. La mejora no aparece en todas las fases; el extremo es extrapolación de cuasi-OCV y de la relación de parámetros saturada. El 2RC mejora 3/6/9 solo un 4,1 %, menor al 10 % fijado, y el pulso 10 prácticamente no cambia. No hay criterio experimental para convertir estos números en aceptación física. La comparación previa de 1RC utilizó pesos por muestra; aquí las tres fases tienen igual peso, así que sus parámetros y métricas no son directamente idénticos a los del informe anterior.

## Estabilidad, sensibilidad y sobreajuste

Con el ajuste nominal ningún parámetro aparece en un límite activo y los cuatro arranques 2RC llegan a objetivos y soluciones muy similares: τ1≈2,20 s y τ2≈39,2 s. Esto evidencia convergencia local para esos arranques, no unicidad global. Al omitir cada pulso de entrenamiento, el 1RC constante da R1=0,956–1,103 mΩ y τ=23,52–26,14 s; para 2RC, R1=0,224–0,263 mΩ y τ1=2,09–2,38 s. Los parámetros centrales variables R1=0,960–1,314 mΩ y τ=23,50–33,31 s, pero sus coordenadas de capacidad cambian en cada ajuste: las magnitudes centrales no describen exactamente el mismo punto físico. El coeficiente de R1 cambia de −0,360 a +0,0136 al omitir el pulso 1; la tendencia estimada depende de ese pulso. La evaluación sobre el pulso 2 omitido empeora de 3,46 mV con 1RC constante a 8,52 mV con el variable. Estas son pruebas internas, no intervalos de confianza.

La sensibilidad a polarización inicial revela una ambigüedad mayor que los multiarrranques: en 1RC constante, imponer v0=0 o +5 mV lleva τ a 44,18 o 62,94 s frente a 23,87 s libre, mientras el indicador 3/6/9 permanece en 2,96 o 3,02 mV. En el 1RC variable, τ central pasa de 26,19 a 44,49 o 63,29 s. Para 2RC, con v0=+5 mV, τ1 sube a 4,61 s y τ2 a 92,42 s; el indicador 3/6/9 permanece en 2,83 mV. Al anular o duplicar la pendiente de cuasi-OCV, el 1RC constante da τ=28,41 o 19,81 s. Ninguno de estos escenarios es un intervalo estadístico ni establece precisión instrumental. La aparente estabilidad local al omitir un pulso no resuelve la correlación entre parámetros, estado inicial y cuasi-OCV.

La comparación es **inconclusa para seleccionar un modelo físico superior**: 1RC variable merece investigación posterior por su mejora intermedia, pero la inversión de tendencia y la sensibilidad impiden considerarlo robustamente superior. 2RC no satisface la mejora mínima predefinida; su rama rápida no queda validada físicamente. El 1RC constante puede mantenerse como aproximación operativa condicionada a este ensayo y rango, con el error del extremo documentado, sin afirmar suficiencia general. Antes de una selección definitiva se necesitan OCV/relajaciones más informativas, repetición en otras celdas y ensayos, y criterios de aceptación fijados antes de medir. No se modificó BESS, BLAST, VSG, PI, DC/DC ni el solver; tampoco se trasladaron parámetros al banco SL.
