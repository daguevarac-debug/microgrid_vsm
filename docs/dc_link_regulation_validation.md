# Validación de la regulación del enlace DC

## Configuración

- Punto VSG: `(M, D) = (80, 1500)`.
- PI del BESS: `Kp = 170 W/V`, `Ki = 10 W/(V*s)`.
- Escenario: escalón severo de carga del 40 %, de 3000 W a 4200 W en `t = 0.8 s`.
- Convención: `PBESS > 0` e `IBESS > 0` representan descarga.
- Horizonte de simulación: 6.5 s.

## Resultados por SoH

| Caso | SoH inicial | Estado | Descarga observada | Fracción post-escalón en descarga | PBESS media post [W] | PBESS máx. post [W] | IBESS máx. descarga [A] | Límite mínimo de corriente disponible [A] | Límite mínimo de potencia de descarga [W] | Límite corriente | Límite potencia | Vdc cumple | Frecuencia cumple |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| SoH_1p00 | 1.000000 | PASS | Sí | 0.998667 | 242.462732 | 243.748209 | 0.719418 | 66.000000 | 22331.065127 | Sí | Sí | Sí | Sí |
| SoH_0p70 | 0.700000 | PASS | Sí | 0.998667 | 242.462732 | 243.748209 | 0.719418 | 46.200000 | 15631.745583 | Sí | Sí | Sí | Sí |
| SoH_nominal | 0.668182 | PASS | Sí | 0.998667 | 242.462732 | 243.748209 | 0.719418 | 44.100000 | 14921.211692 | Sí | Sí | Sí | Sí |

La respuesta dinámica es prácticamente igual en los tres casos porque la demanda real del controlador queda muy por debajo incluso del límite más restrictivo. El pico absoluto de corriente fue `2.455701 A`, frente a un mínimo disponible de `44.100000 A`, y el pico absoluto de potencia fue `847.165674 W`, frente a un mínimo de descarga disponible de `14921.211692 W`. Por tanto, el SoH reduce correctamente la capacidad disponible, pero no llega a saturar el soporte requerido en este evento.

## Descarga efectiva durante el déficit

Después del escalón, la carga aumenta a `4200 W` y la potencia disponible de referencia es `3678.198276 W`, lo que produce un déficit comandado de `521.801724 W`.

En los tres casos se observó descarga positiva del BESS durante el `99.8667 %` de las muestras posteriores al escalón. Para el caso nominal:

- `PBESS` media post-escalón: `242.462732 W`.
- `PBESS` máxima post-escalón: `243.748209 W`.
- `IBESS` máxima de descarga: `0.719418 A`.
- Identidad física respetada: `PBESS = Vdc * IBESS`.

La potencia negativa mínima post-escalón (`-828.755559 W`) corresponde al breve tránsito inmediatamente asociado al cambio de régimen; la potencia media positiva confirma soporte neto de descarga durante el déficit.

## Comparación sin soporte y con soporte corregido

| Métrica | Sin soporte BESS | PI+BESS nominal |
|---|---:|---:|
| Vdc mínima post-escalón [V] | 313.864395 | 338.349472 |
| Desviación máxima de Vdc [%] | 17.253883 | 1.832355 |
| Margen sobre Vdc mínima requerida [V] | -13.637693 | 10.847384 |
| Vdc cumple criterios | No | Sí |
| Caída máxima de frecuencia [Hz] | 0.025126 | 0.022792 |
| Frecuencia cumple criterios | Sí | Sí |

El caso anterior sin soporte incumple los criterios del enlace DC: su tensión cae hasta `313.864395 V`, por debajo del mínimo requerido de `327.502088 V`. El caso corregido mantiene `Vdc` en `338.349472 V` como mínimo y reduce la desviación máxima del evento de `17.253883 %` a `1.832355 %`.

La frecuencia cumple en ambos casos, aunque el soporte corregido reduce ligeramente la caída máxima de `0.025126 Hz` a `0.022792 Hz`.

## Criterios verificados

- Descarga positiva observada durante el déficit de potencia.
- Potencia media post-escalón positiva.
- Corriente real dentro del límite dinámico dependiente de SoH.
- Potencia real y referencia saturada dentro de los límites dinámicos.
- SoC dentro de `[SoC_min, SoC_max]`.
- SoH dentro del rango operativo.
- Criterios vigentes del enlace DC cumplidos.
- Criterios de frecuencia de la Actividad 2.3 cumplidos.
- Orden decreciente de disponibilidad con SoH confirmado.

## Limitaciones

- El convertidor se representa mediante un modelo promediado y reducido; no se modela la conmutación detallada del convertidor DC/DC.
- No se incluyen retardos de comunicación del BMS ni dinámica térmica.
- El horizonte de 6.5 s valida la respuesta dinámica corta, no el envejecimiento de largo plazo.
- `Kp` y `Ki` corresponden a un ajuste mínimo admisible, no a una optimización global.
- La comparación principal usa SoH nominal para el caso corregido; los otros SoH se validan por separado.
- La igualdad práctica de las respuestas entre SoH no significa que el SoH no afecte al modelo; significa que el evento no exige suficiente potencia para activar esos límites.

## Archivos generados

- `outputs/validation/dc_link_regulation/task_5_3_bess_soh_support_summary.json`
- `outputs/validation/dc_link_regulation/task_5_3_bess_soh_support_summary.csv`
- `outputs/validation/dc_link_regulation/task_5_3_no_support_vs_bess_pi.csv`
- `outputs/validation/dc_link_regulation/task_5_3_no_support_vs_bess_pi.png`
- `docs/dc_link_regulation_validation.md`

## Estado final

`PASS`

Las tres condiciones de SoH cumplen descarga efectiva, límites eléctricos, criterios de frecuencia y criterios del enlace DC. La comparación confirma que la regulación PI+BESS corrige el incumplimiento de `Vdc` observado en el caso anterior sin soporte.
