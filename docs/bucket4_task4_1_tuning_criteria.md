# Bucket 4 — Tarea 4.1: criterios de sintonización y métricas objetivo

## Alcance

Esta tarea fija criterios reproducibles para evaluar posteriormente combinaciones de inercia virtual `M`, amortiguamiento `D` y, si aplica, parámetros FOVIC. Los límites se aplican de forma idéntica a todos los candidatos y no deben confundirse con una sintonización ya realizada.

Los valores adoptados son criterios de diseño de la tesis. No se presentan como límites normativos universales.

## Criterios adoptados

| Métrica | Definición | Límite de aceptación |
|---|---|---:|
| Caída máxima de frecuencia | `f_pre - min(f_post)` | `<= 0.50 Hz` |
| Tiempo de recuperación de frecuencia | Primer instante de entrada a `60 +/- 0.10 Hz` con permanencia de `0.50 s` | `<= 5.0 s` |
| Sobreoscilación positiva del enlace DC | `100*(Vdc_max - Vdc_ref)/Vdc_ref` | `<= 5.0 %` |
| Tensión mínima del enlace DC | Mínimo postperturbación | `>= 327.52 V` |

La frecuencia previa al evento se calcula como el promedio de los últimos `0.10 s` anteriores al escalón. La referencia del enlace DC es `340 V`. La tensión mínima requerida se deriva de `2*sqrt(2)*110/0.95`, usando la tensión fase-neutro RMS y el índice máximo de modulación del modelo.

## Justificación bibliográfica resumida

La selección de `0.50 Hz` se apoya en trabajos sobre VSG y control grid-forming en microrredes aisladas o de baja inercia. Zhang et al. adoptan una banda de frecuencia estrecha alrededor de 50 Hz; Long et al. muestran desviaciones inferiores a 0.5 Hz con VSG-ESS; Elwakil et al. reportan mejoras de nadir mediante adaptación conjunta de inercia y amortiguamiento; Behnam et al. validan experimentalmente respuestas cercanas a 0.5 Hz en un sistema de 60 Hz; Bhowmik et al. reportan desviaciones de frecuencia y tiempos de establecimiento bajo escalones severos de carga.

El límite de `5.0 s` para recuperación es deliberadamente menos agresivo que los resultados subsegundo de algunos controladores adaptativos. El objetivo es evitar que la sintonización premie respuestas rápidas obtenidas mediante picos excesivos de corriente o potencia en una batería de segunda vida. Elwakil et al. muestran tiempos de recuperación de varios segundos en una microrred aislada con almacenamiento híbrido, mientras que Bhowmik et al. reportan oscilaciones amortiguadas dentro de aproximadamente 5 s en configuraciones con inversores grid-forming.

El límite de `5 %` para sobreoscilación del enlace DC se adopta como margen práctico. Bakeer et al. estudian soporte bidireccional de inercia en microrredes híbridas AC/DC y reportan mejoras cuantificables en la desviación del bus DC. Bakeer et al. también muestran que estrategias VSG de orden fraccionario pueden reducir de forma marcada la sobreoscilación del enlace DC. Un límite de `3 %` sería alcanzable con control avanzado y baterías en buenas condiciones, pero puede inducir una sintonización innecesariamente agresiva para módulos reutilizados.

## Consideración obligatoria para baterías de segunda vida

Cumplir las métricas de frecuencia y tensión es necesario, pero no suficiente. Entre dos candidatos que satisfagan los límites, no debe seleccionarse automáticamente el de menor error dinámico. La selección final también debe comparar:

- corriente pico y corriente RMS del BESS;
- potencia máxima de carga y descarga;
- energía total intercambiada durante la perturbación;
- variación de SoC;
- SoH y tensión terminal mínima;
- límites de corriente y potencia reducidos por envejecimiento y resistencia interna.

La función `bess_stress_metrics` registra estas magnitudes sin imponer todavía umbrales no justificados. Los límites electroquímicos definitivos deben fijarse en una subtarea posterior a partir de la caracterización de los módulos de segunda vida y de la política BMS adoptada.

## Referencias principales

1. Fini, M. H.; Golshan, M. E. H. *Determining Optimal Virtual Inertia and Frequency Control Parameters to Preserve the Frequency Stability in Islanded Microgrids with High Penetration of Renewables*. Electric Power Systems Research.
2. Long, B.; Liao, Y.; Chong, K. T.; Rodríguez, J.; Guerrero, J. M. *MPC-Controlled Virtual Synchronous Generator to Enhance Frequency and Voltage Dynamic Performance in Islanded Microgrids*. IEEE Transactions on Smart Grid, 2021. DOI: 10.1109/TSG.2020.3027051.
3. Zhang, Y.; Sun, Q.; Zhou, J.; Guerrero, J. M.; Wang, R.; Lashab, A. *Optimal Frequency Control for Virtual Synchronous Generator Based AC Microgrids via Adaptive Dynamic Programming*. IEEE Transactions on Smart Grid. DOI: 10.1109/TSG.2022.3196412.
4. Elwakil, M. M.; El Zoghaby, H. M.; Sharaf, S. M.; Mosa, M. A. *Adaptive Virtual Synchronous Generator Control Using Optimized Bang-Bang for Islanded Microgrid Stability Improvement*. Protection and Control of Modern Power Systems, 2023. DOI: 10.1186/s41601-023-00333-7.
5. Bakeer, A.; Chub, A.; Abid, A.; Zaid, S. A.; Alghamdi, T. A. H.; Salama, H. S. *Enhancing Grid-Forming Converters Control in Hybrid AC/DC Microgrids Using Bidirectional Virtual Inertia Support*. Processes, 2024. DOI: 10.3390/pr12010139.
6. Behnam, R.; Asif, U.; Shadmand, M. *AI-Based Control Scheme for Resilient Grid-Forming Inverters Under DC Link Voltage Disturbances*. IEEE Open Journal of the Industrial Electronics Society, 2025. DOI: 10.1109/OJIES.2025.3625471.
7. Bhowmik, B.; Amoasi Acquah, M.; Kim, S.-Y. *Hybrid Compatible Grid Forming Inverters with Coordinated Regulation for Low Inertia and Mixed Generation Grids*. Scientific Reports, 2025. DOI: 10.1038/s41598-025-11367-2.
8. Bakeer, A.; Hussain, S.; Chub, A.; Salama, H. S.; Magdy, G. *Energy Storage-Enabled Fractional-Order Virtual Synchronous Generator for DC-Link Voltage Regulation in DC Microgrid Under Load and Renewable Disturbances*. Scientific Reports, 2026. DOI: 10.1038/s41598-026-45850-1.

## Implementación

Las definiciones están implementadas en `src/tuning_metrics.py`. Las pruebas unitarias se encuentran en `src/validation/test_tuning_metrics.py`. La implementación evita modificar todavía el horizonte global de simulación; una corrida destinada a verificar el criterio de recuperación debe extenderse al menos hasta `t_step + 5.0 + 0.5 s`.
