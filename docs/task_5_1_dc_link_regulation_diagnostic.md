# Tarea 5.1 — Diagnóstico del enlace DC

## Alcance

Este documento registra el estado del modelo antes de cualquier modificación posterior. En esta etapa no se cambian ecuaciones de planta, controlador GFM, ley del BESS, límites operativos ni mapeo de estados.

## Escenario severo

Se reproduce el punto GFM `(M, D) = (80, 1500)` con BESS activo y escalón de carga del 40 % en `t = 0.8 s`, desde 3000 W hasta 4200 W. Se registran `Vdc`, `Pload`, `Psource`, `PBESS` e `IBESS`.

Archivo de señales:

`outputs/validation/dclink_energy_diagnostic/gfm_m80_d1500_severe_40pct_energy_signals.csv`

## Convención de signos

La convención verificada es:

- `IBESS > 0` y `PBESS > 0`: descarga e inyección al enlace DC.
- `IBESS < 0` y `PBESS < 0`: carga y absorción desde el enlace DC.

También se verifica numéricamente `PBESS = Vdc*IBESS`.

La ley de soporte existente es proporcional:

`IBESS_cmd = Kp_bess*(Vdc_ref - Vdc)`.

Por tanto, una caída de `Vdc` por debajo de la referencia genera una orden positiva de descarga.

## Diagnóstico de `charge_only`

El caso `charge_only` no se explica por un error de signo ni por bloqueo incorrecto. En el escenario nominal de comparación por SoH, `Vdc` permanece por encima de `Vdc_ref = 340 V`, de modo que la ley proporcional ordena carga. El estado GFM es `omega`; no existe un estado integral dedicado a corregir el error estacionario del enlace DC.

Resultado reproducible:

`outputs/validation/dclink_energy_diagnostic/gfm_m80_d1500_charge_only_cause.json`

## Resultados severos previos

Para el escalón del 40 %:

- `Vdc_pre_step ≈ 344.802 V`.
- `Vdc_min_post_step ≈ 338.562 V`.
- Desviación máxima del evento `≈ 6.239 V` (`≈ 1.810 %`).
- `Vdc_final ≈ 338.562 V`.
- Tensión mínima requerida `≈ 327.502 V`.

La respuesta cumple el criterio vigente de desviación máxima del 5 % respecto al punto preescalón y permanece sobre la tensión mínima requerida. Esto no equivale a seguimiento exacto de la referencia nominal de 340 V.

## Figura consolidada

El script:

`src/validation/plot_dc_link_regulation_diagnostic.py`

crea tres paneles con eje temporal compartido:

1. `Vdc`, referencia, banda de aceptación y tensión mínima requerida.
2. `Pload`, `Psource` y `PBESS`.
3. `IBESS`.

Salidas:

- `outputs/validation/dc_link_regulation/gfm_m80_d1500_severe_40pct_dc_link_regulation.png`.
- `outputs/validation/dc_link_regulation/gfm_m80_d1500_severe_40pct_dc_link_regulation_summary.json`.

## Conclusión

El modelo es numéricamente consistente y la convención del almacenamiento es correcta. El BESS actúa según el error instantáneo de `Vdc`, pero no existe una acción integral dedicada a llevar el enlace DC a la referencia nominal. Cualquier cambio posterior deberá abordarse como una subtarea independiente y validarse contra este diagnóstico base.
