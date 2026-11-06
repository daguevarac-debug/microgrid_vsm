# BAT26-46 — Comparación operacional a cuatro niveles de SoH

## Pregunta de investigación
¿Cómo cambia la variación de SoC, la reserva de carga y la respuesta GFM a igual demanda cuando el grupo equivalente de batería envejece desde el SoH inicial hasta el previsto tras 1000 ciclos sintéticos? El criterio de Roma exige 3–4 niveles, incluido el inicial del 66,8 %, y diferencias reproducibles de capacidad, SoC y energía/potencia.

## Escenarios y trazabilidad
Se escogen cuatro hitos de BAT26-45: 0, 100, 500 y 1000 ciclos. Los valores se toman de la tabla redondeada a tres decimales del documento BAT26-45, no de mediciones experimentales ni de archivos BLAST originales con precisión completa.

| Ciclos de BAT26-45 | Capacidad al inicio del caso (Ah) | SoH respecto a 66 Ah (%) |
| ---: | ---: | ---: |
| 0 | 44.100 | 66.818 |
| 100 | 42.273 | 64.050 |
| 500 | 39.038 | 59.148 |
| 1000 | 35.854 | 54.324 |

Cada estado es una condición inicial independiente; no representa la reproducción de 1000 días dentro del solver del VSG ni una segunda aplicación de pérdida de capacidad.

## Dos comparaciones complementarias
El ensayo de capacidad descarga el puerto del modelo 1RC a +8 A durante 3600 s en todos los casos, con SoC inicial igual a 0,6, iguales ecuaciones y caracterización OCV/R1/C1. La corriente está definida en el puerto equivalente del grupo 2p, no en el bus de 340 V. Se registran caída de SoC, energía terminal modelada en Wh, Ah utilizables de SoC 0,6 a 0,1, y autonomía ideal a 8 A. La diferencia algebraica anticipada es aproximadamente 18,14 puntos de SoC para 44,1 Ah y 22,31 puntos para 35,854 Ah. La simulación verificará los valores reales.

El ensayo dinámico reutiliza el validador GFM seleccionado existente, con cuatro estados de capacidad, arquitectura de 15 estados, M=80, D=1500, carga local nominal 3 kW y escalón +20 % durante 6,5 s. Debe reportar límites disponibles, respuesta de bus DC, caída de frecuencia y modo real de intercambio. No se debe presentar este ensayo como una simulación de una hora, ni como la variante externa PI de 16 estados.

Los parámetros y ecuaciones físicos no se modifican. Se conserva la convención de corriente positiva para descarga. R0(SoH) y OCV/R1/C1 siguen siendo aproximaciones no calibradas. La energía terminal en Wh no es energía medida ni potencia entregable a IEEE 33.

## Ejecución mediante Codex Cloud
Trabajar exclusivamente en feat/bat26-46-soh-operational-comparison con Python principal. BLAST original no se ejecuta de nuevo; sus cuatro valores publicados sirven como condiciones iniciales aproximadas.

~~~bash
.venv/bin/python -B -m unittest discover -s src/validation -p test_bat26_46_soh_levels.py -v
.venv/bin/python -B src/validation/run_bat26_46_soh_levels.py
~~~

Se genera una carpeta única bajo outputs/analysis/bat26_46_soh_levels/ con summary.json, comparison.csv y las figuras soc_same_current.png y available_charge_vs_cycles.png. No se deben inventar resultados antes de ejecutar; REVIEW de GFM por desempeño no significa error de software si los invariantes permanecen válidos.

## Criterio y limitaciones
Para cerrar BAT26-46 se deben revisar los cuatro niveles, verificar diferencias de SoC y capacidad, comprobar que las cuatro simulaciones GFM no violan invariantes, y describir en términos cuantitativos el efecto de SoH. La falta de calibración eléctrica 2p, convertidor DC/DC, datos experimentales y validez del envejecimiento queda reservada a BAT26-47. Las variables y el costo de desgaste para despacho corresponden a BAT26-48.

Estado del PR: protocolo y código preparados; pruebas y campañas pendientes de ejecución.