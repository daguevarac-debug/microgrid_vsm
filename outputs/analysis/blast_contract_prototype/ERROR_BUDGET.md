# Presupuesto de error y límites previos al prototipo

El presupuesto separa fuentes; no constituye una suma de incertidumbres ni un intervalo de confianza. Datos del experimento original con 121 muestras, r=q/q0 y q0=1. Se compara 64 menos 32 ventanas; ninguna se considera solución exacta. Las diferencias en Ah suponen exclusivamente la transferencia hipotética `Q_init*r`.

| Perfil | Δretención 64−32 | ΔQ 44.1 Ah | ΔQ 43.5 Ah | Pérdida 32 → 64 (fracción de Q inicial) | Cambio relativo a pérdida de 64 |
|---|---:|---:|---:|---:|---:|
| Reposo 30 días | +0.00009936796 | +0.00438213 Ah | +0.00432251 Ah | 0.0191063110 → 0.0190069430 | 0.5228 % |
| Ciclo 25 °C | +0.00000499397 | +0.00022023 Ah | +0.00021724 Ah | 0.0013550610 → 0.0013500670 | 0.3699 % |
| Rampa 20–30 °C | +0.00000835813 | +0.00036859 Ah | +0.00036358 Ah | 0.0014522492 → 0.0014438910 | 0.5789 % |

La pérdida es `1−r` desde inicio sin historia; no es la pérdida respecto a celda nueva. En reposo de estrés constante, referencia analítica `r=0.9812071334181`: resultado 64 difiere −0.0002140764, que equivale a −0.00944077 Ah para 44.1 Ah y −0.00931232 Ah para 43.5 Ah, si se aplica la transferencia hipotética. La pérdida acumulada de 64 excede la referencia en esa misma fracción. Un único paso coincide por la rama de inicialización del algoritmo; no es referencia exacta general.

**Discretización:** las diferencias anteriores combinan integración incremental, tasas promediadas y EFC ponderado por q al comienzo de cada ventana. Son sensibilidad observada para estos perfiles, no cota para otros perfiles ni error global conocido. Malla y partición son limitadas; el caso de 64 ventanas incluye intervalos individuales. No se define tolerancia de aceptación arbitraria ni se declara convergencia.

**Incertidumbre física:** ajuste calendario y ciclado, dispersión de unidades, condición inicial, temperatura real, corriente, estado de carga, topología y dominio experimental permanecen inciertos. Las cifras de arriba no cuantifican esos errores y no son validación experimental.

**Transferencia:** multiplicar retención BLAST por 44.1 o 43.5 Ah supone que el envejecimiento relativo y el historial corresponden a cada caso. No hay incertidumbre cuantificada ni evidencia de equivalencia entre unidades ni de que el historial BLAST represente cada Q inicial. No incluir la diferencia 46 vs 46.2 Ah como error numérico: son referencias originales distintas sin reconciliación física demostrada.

Para uso futuro se requieren criterios de aceptación ligados a la precisión exigida en Ah, horizonte, dominio y decisiones de despacho; comparaciones de paso temporal y muestreo por separado; evidencia experimental independiente y presupuesto de transferencia. Nada de ello se sustituye por un umbral elegido después de observar los resultados.
