# BAT26-32: refinamiento temporal y contrato de fronteras

## Alcance y reproducibilidad

Ejecutado el 3 de noviembre de 2026, con el mismo entorno aislado Python 3.12.10 y BLAST-Lite 1.1.0 de la prueba anterior. `convergence.py` verifica los SHA-256 de la clase y base instaladas, la versión y los resultados anteriores para 1 y 2 ventanas. Ambos archivos instalados fueron cotejados antes con el commit oficial `b093495b47dc40dd96dba865d91f553619501e94`; esto no verifica todo el paquete. NumPy 1.26.4. No se alteró la instalación.

```powershell
& "$env:LOCALAPPDATA\microgrid_blast_probe_312\Scripts\python.exe" outputs/analysis/blast_temporal_convergence/convergence.py
& "$env:LOCALAPPDATA\microgrid_blast_probe_312\Scripts\python.exe" -m unittest discover -s outputs/analysis/blast_temporal_convergence -p 'test_*.py' -v
```

Tres pruebas independientes pasaron. El script genera `results.json` y `convergence.csv` en esta carpeta. Para cada magnitud registran diferencia con signo, diferencia absoluta y diferencia relativa con signo respecto de 1 ventana, 64 ventanas y refinamiento anterior; relativa es diferencia dividida entre el valor absoluto de referencia, no porcentaje; se deja vacía cuando el denominador es cero o no hay anterior. 64 es solo referencia finita, no solución exacta. Ambas capacidades equivalentes registradas son `66*qNew` y `46*q`.

Para cada caso se usan exactamente las mismas 121 muestras originales. Reposo: 30 días, SoC 0.5, 25 °C. Ciclo: 7200 s, SoC 1→0→1, 3600 s por tramo, 25 °C, muestras cada 60 s. Rampa: idéntico ciclo con temperatura 20→30 °C. El ciclo es sintético, con tasa 1C relativa a capacidad inicial disponible; la rampa no está validada por el único ensayo cíclico declarado por la clase. Cada partición crea una instancia nueva, que se conserva con todo su historial durante sus ventanas. Se bisecan recursivamente índices enteros: los bordes son anidados; en cada par solo se comparte la muestra de frontera. Un control comprueba que los 120 intervalos aparecen exactamente una vez, y que la suma bruta `sum(abs(ΔSoC))/2` es idéntica en todas las particiones. Por tanto no se agregan puntos ni rebases. En 64 ventanas hay 56 de dos intervalos y 8 de uno; no puede dividirse toda ventana adicionalmente sin crear muestras nuevas. No se amplió la malla porque cambiaría los puntos y la cuadratura, impidiendo atribuir el cambio exclusivamente a segmentación.

## Resultados

| Perfil | Ventanas | q | qNew | qLoss_t | qLoss_EFC | EFC | 66·qNew (Ah) | Δq frente a anterior |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Reposo | 1 | 0.9812071334 | 0.6868449934 | 0.0187928666 | 0 | 0 | 45.331770 | — |
| | 2 | 0.9800539828 | 0.6860377880 | 0.0199460172 | 0 | 0 | 45.278494 | -0.001153151 |
| | 4 | 0.9802079202 | 0.6861455441 | 0.0197920798 | 0 | 0 | 45.285606 | +0.000153937 |
| | 8 | 0.9805056269 | 0.6863539389 | 0.0194943731 | 0 | 0 | 45.299360 | +0.000297707 |
| | 16 | 0.9807282622 | 0.6865097835 | 0.0192717378 | 0 | 0 | 45.309646 | +0.000222635 |
| | 32 | 0.9808936890 | 0.6866255823 | 0.0191063110 | 0 | 0 | 45.317288 | +0.000165427 |
| | 64 | 0.9809930570 | 0.6866951399 | 0.0190069430 | 0 | 0 | 45.321879 | +0.000099368 |
| Ciclo | 1 | 0.9986848302 | 0.6990793811 | 0.0012393698 | 0.0000758000 | 1.0000000000 | 46.139239 | — |
| | 2 | 0.9986100377 | 0.6990270264 | 0.0013154189 | 0.0000745434 | 0.9995328171 | 46.135784 | -0.000074793 |
| | 4 | 0.9986264377 | 0.6990385064 | 0.0012990267 | 0.0000745356 | 0.9992866621 | 46.136541 | +0.000016400 |
| | 8 | 0.9986326328 | 0.6990428429 | 0.0012925314 | 0.0000748359 | 0.9991655551 | 46.136828 | +0.000006195 |
| | 16 | 0.9986380854 | 0.6990466598 | 0.0012868069 | 0.0000751077 | 0.9991079013 | 46.137080 | +0.000005453 |
| | 32 | 0.9986449390 | 0.6990514573 | 0.0012797432 | 0.0000753178 | 0.9990852282 | 46.137396 | +0.000006854 |
| | 64 | 0.9986499330 | 0.6990549531 | 0.0012746129 | 0.0000754541 | 0.9990765239 | 46.137627 | +0.000004994 |
| Rampa | 1 | 0.9986465880 | 0.6990526116 | 0.0012776120 | 0.0000758000 | 1.0000000000 | 46.137472 | — |
| | 2 | 0.9983146430 | 0.6988202501 | 0.0016108066 | 0.0000745504 | 0.9996230483 | 46.122137 | -0.000331945 |
| | 4 | 0.9984500495 | 0.6989150347 | 0.0014754058 | 0.0000745447 | 0.9994025369 | 46.128392 | +0.000135407 |
| | 8 | 0.9985051972 | 0.6989536380 | 0.0014199564 | 0.0000748464 | 0.9992972249 | 46.130940 | +0.000055148 |
| | 16 | 0.9985323117 | 0.6989726182 | 0.0013925691 | 0.0000751192 | 0.9992496399 | 46.132193 | +0.000027115 |
| | 32 | 0.9985477508 | 0.6989834256 | 0.0013769195 | 0.0000753296 | 0.9992305436 | 46.132906 | +0.000015439 |
| | 64 | 0.9985561090 | 0.6989892763 | 0.0013684250 | 0.0000754660 | 0.9992227519 | 46.133292 | +0.000008358 |

La tabla es redondeada; el CSV es la fuente numérica. Las diferencias 32→64 de q son respectivamente +9.9368e-5, +4.9940e-6 y +8.3581e-6; relativas al valor con 32 ventanas son +1.0130e-4, +5.0007e-6 y +8.3703e-6. El reposo no es monótono: se aleja primero y luego se aproxima. No se fijó tolerancia física aceptable antes del análisis y no se demuestra convergencia general ni del límite continuo para los tres perfiles.

## Qué hace la implementación

En `_update_power_state`, con estado cero se inicializa exactamente `y=k*(Δx)^p`; con estado positivo se usa un incremento Euler explícito `Δy=k*p*(y/k)^((p-1)/p)*Δx`. Al aplicar pasos grandes a una potencia no lineal aparece error de discretización, que cambia de signo y magnitud con la partición y el arranque. No implica un cambio real en el perfil.

Para el reposo de estrés constante y sin desgaste previo, una referencia analítica externa es `qLoss_t=k_cal*t_days^0.464`; `k_cal=0.00387800860446317`, pérdida a 30 días `0.0187928665818934`, `q=0.9812071334181066`. Coincide con una ventana porque la rama de arranque calcula esa potencia; esto no convierte una ventana en exacta para estrés variable ni para todos los estados. A 64 ventanas la diferencia de q frente a esta referencia es -0.0002140764, aproximadamente -0.02182 % de q. El error disminuyó desde 2 ventanas pero todavía es mayor que cero; por finitud de muestras no se prueba el límite.

`_extract_stressors` calcula por ventana `ΔEFC=0.5*sum(abs(ΔSoC))*q_preventana`. La variación bruta de SoC es siempre 1 en el ciclo; el EFC interno difiere porque q disminuye y se vuelve a evaluar cada ventana. La pérdida cíclica también usa Euler tras el primer paso: una diferencia de `qLoss_EFC` no se explica solo por EFC. La tasa calendario es el promedio temporal no lineal de temperatura y SoC de cada ventana; cambiar agrupación cambia la combinación de tasas con la actualización de estado. En la rampa intervienen por ello agregación térmica y discretización, no una temperatura distinta físicamente suministrada.

Precaución adicional de implementación: al tener solo dos muestras, el cálculo `Crate` integra una sola muestra y devuelve cero. La clase Nissan examinada no usa `Crate` en `update_rates` ni `update_states`, así que no cambia estas pérdidas; no extrapolar ese hallazgo a otras clases ni usar ese `Crate` como diagnóstico correcto a resolución de un intervalo.

## Referencias y reinicio de caso

Se preservan `cap=66 Ah`, `cap_2ndLife=46 Ah`, y `qNew(0)*66=0.7*66=46.2 Ah`; la diferencia 0.2 Ah continúa sin resolver. Tesis `Q_init=44.1 Ah` y Braco `Q_init=43.5 Ah` son casos distintos, no valores emitidos por BLAST. Bajo la hipótesis no calibrada de transferir `r=q(t)/q(t0)` al inicio original (`q(t0)=1`), ciclo con 64 ventanas produce 44.040462 Ah y 43.441272 Ah respectivamente. Son distintas de 46·q y 66·qNew.

Si el caso comienza después de historial, fijar `q0=q(t0)>0` y mantener la instancia con `qLoss_t`, `qLoss_EFC`, historial, tiempo, EFC y configuración completos. Usar `r=q(t)/q0`, no q absoluto ni qNew directo; así r(t0)=1 y Qeff(t0)=Q_init. El cociente evita contar dos veces la pérdida previa en la escala de Q inicial, pero **no** reconstituye el historial ni ajusta las leyes a la batería de 44.1/43.5 Ah. El mismo q0 puede corresponder a repartos de pérdidas distintos, con evolución distinta. La prueba usa un reposo previo y verifica que se conservan los estados, y que el cociente y q absoluto difieren. No reiniciar el objeto en t0 ni manipular sus estados para forzar Q inicial.

## Propuesta de contrato temporal, aún no decisión física

1. Establecer t0, procedencia de Q_init, versión/código, estados completos y condiciones previas; congelar `q0`. Definir explícitamente temperatura de celda suministrada, unidades, muestreo, SoC y dominio experimental. Registrar evidencia de transferibilidad y la discrepancia de referencias. No extrapolar la validación cíclica de 25 °C/DoD 100 %/1C a perfiles someros.
2. Definir particiones antes de ejecutar, con tiempos crecientes, muestras de frontera coherentes, sin huecos, ni intervalos duplicados, ni ventanas degeneradas. Conservar la misma instancia y sus estados. Registrar bordes, entradas y salidas, y `r=q/q0`, junto con q, qNew, contribuciones, EFC, política y versión. Comparar refinamientos y acordar tolerancias físicas por aplicación; este estudio no justifica elegir una duración universal.
3. Entre actualizaciones, `CapacitySnapshot(66,Q_init,r)` congela Qeff y SoH, sujeto a sus restricciones `0<r<=1`. Detectar explícitamente retención no finita/fuera de rango, límites de SoH y superación de dominio; no recortar silenciosamente. Precisar cuándo queda efectiva una actualización y evitar que degradación lineal y BLAST se apliquen simultáneamente sobre la misma capacidad. Este documento no define código de acoplamiento ni cambia la ODE.
4. **Conservar SoC fraccional:** `s+=s-`; con Q+<Q-, el producto sQ disminuye sin corriente externa, representando una pérdida o inaccesibilidad algebraica cuya física debe modelarse o justificarse. Si s ya estaba dentro de [0.1,0.9], permanece dentro, pero puede cambiar la interpretación de la carga.
5. **Conservar carga algebraica:** `s+=s-*Q-/Q+`; preserva sQ por definición, no demuestra conservación electroquímica de carga accesible. Con capacidad decreciente eleva s, pudiendo superar 0.9 o 1. No recortar silenciosamente ni tratar el exceso como carga descargada: se requiere una regla explícita, trazable y físicamente justificada para límites o rechazo.
6. Cualquier rebase es un evento de coordenadas, no corriente: cerrar la ventana con el SoC anterior y arrancar la siguiente en el valor posterior, sin alimentar a BLAST un salto artificial como segmento de SoC. Mantener por separado el intercambio físico y contabilizar throughput solo con muestras reales, o una representación explícita equivalente. Este mecanismo altera el estado inicial de la siguiente trayectoria y debe probarse con el adaptador; no sumar la discontinuidad al EFC. En la prueba, alimentar 0.5→0.503225 como si fuera perfil a q=1 crea ~0.0016126 EFC ficticios; alimentar SoC constante tras rebase crea cero. Ese ejemplo usa la API original solo como diagnóstico.

**Dictamen:** se puede diseñar y probar un prototipo aislado del puente, pero no aceptar ni integrar aún un puente operativo. Permanecen sin resolver la selección física de frontera y límites, el criterio de precisión y política de ventanas, el historial inicial apropiado, la compatibilidad de dominio y la justificación/validación de transferencia a Q_init de tesis o Braco. El estudio es verificación numérica interna, no validación experimental de BLAST ni del BESS. BAT26-32 sigue en curso.
