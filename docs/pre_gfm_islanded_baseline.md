# Línea base pre-GFM de operación aislada

## Propósito

Este documento registra la ejecución de referencia previa a activar el controlador grid-forming en el modelo principal. La simulación conserva el controlador `GridFollowingController` como baseline y sirve para comparar posteriormente el efecto de integrar el GFM.

## Contexto de ejecución

- Fecha de ejecución: 2026-06-17.
- Rama: `task-2.1-gfm-controller-contract`.
- Comando:

```powershell
python src/validation/validate_islanded_operation_scenarios.py
```

- Código de salida: `0`.
- Controlador activo: `GridFollowingController`.
- Frecuencia: fija en `omega_ref`; no existe todavía dinámica GFM integrada en estos resultados.
- Evidencia local generada: `outputs/pre_gfm_islanded_baseline.txt`.

## Resultado general

Los cuatro escenarios terminaron con `status=PASS`. Todos los casos que ejecutan `solve_ivp` reportaron `solver_success=True` y estados finitos.

| Escenario | Resultado | Métrica principal |
| --- | --- | --- |
| Operación nominal | PASS | `Vdc_final = 379.309457 V` |
| Escalón de carga del 20 % | PASS | `delta_vdc = 3.835563 %`, límite interno `10 %` |
| Cambio abrupto de carga del 40 % | PASS | `delta_vdc = 14.957581 %`, límite interno `15 %` |
| Comparación sin BESS / con BESS al 20 % | PASS | `3.835563 %` sin BESS y `0.902255 %` con BESS |

## Escenario 1: operación nominal

Condiciones:

- Potencia activa nominal: `3000 W`.
- Potencia reactiva nominal: `986.052316 var`.
- Factor de potencia: `0.95` inductivo.
- BESS inactivo.
- Perfil de carga constante.

Resultados:

- `Vdc_final = 379.309457 V`.
- `p_pcc_final = 2833.097938 W`.
- `p_bridge_final = 2858.714276 W`.
- `max_abs_i2 = 13.806652 A`.
- Razones de crecimiento finales iguales a `1.0` para `Vdc`, `i2`, `p_pcc` y `p_bridge`.

Interpretación: no se detecta crecimiento sostenido en las ventanas finales del escenario nominal. Este resultado es una verificación numérica interna, no una validación experimental.

## Escenario 2: escalón de carga del 20 %

Condiciones:

- Instante del escalón: `0.8 s`.
- Potencia antes del escalón: `3000 W`.
- Potencia después del escalón: `3600 W`.
- Cambio aplicado: `20 %`.
- BESS inactivo.

Resultados:

- `Vdc_pre_step = 379.309457 V`.
- `Vdc_min_post_step = 364.760804 V`.
- `Vdc_final = 364.760804 V`.
- Caída absoluta: `14.548653 V`.
- Caída relativa: `3.835563 %`.
- Límite interno: `10 %`.
- `p_pcc_final = 3357.234683 W`.
- `p_bridge_final = 3393.718497 W`.
- `max_abs_i2 = 15.692529 A`.
- Razones de crecimiento finales iguales a `1.0`.

Interpretación: el baseline supera el criterio interno del escenario moderado con margen suficiente y sin señales no finitas.

## Escenario 3: cambio abrupto de carga del 40 %

Condiciones:

- Instante del escalón: `0.8 s`.
- Potencia antes del escalón: `3000 W`.
- Potencia después del escalón: `4200 W`.
- Cambio aplicado: `40 %`.
- BESS inactivo.

Resultados:

- `Vdc_pre_step = 379.309457 V`.
- `Vdc_min_post_step = 322.573938 V`.
- `Vdc_final = 338.515050 V`.
- Caída absoluta: `56.735519 V`.
- Caída relativa: `14.957581 %`.
- Límite interno: `15 %`.
- Margen frente al límite: `0.042419` puntos porcentuales.
- `p_pcc_final = 3632.497946 W`.
- `p_bridge_final = 3678.607551 W`.
- `max_abs_i2 = 18.201983 A`.
- Razón de crecimiento de `Vdc = 1.005671`.
- Razón de crecimiento de `i2 = 1.000258`.
- Razón de crecimiento de `p_pcc = 1.000515`.
- Razón de crecimiento de `p_bridge = 1.000514`.

Interpretación: el escenario pasa, pero queda prácticamente sobre el límite interno. Este caso debe conservarse como comparación sensible al evaluar el GFM, porque pequeñas variaciones del modelo o de los parámetros pueden cambiar su clasificación.

## Escenario 4: comparación sin BESS y con BESS

Condiciones comunes:

- Escalón de carga del `20 %` en `0.8 s`.
- Potencia antes del escalón: `3000 W`.
- Potencia después del escalón: `3600 W`.

Sin BESS:

- `Vdc_pre_step = 379.309457 V`.
- `Vdc_min_post_step = 364.760804 V`.
- `Vdc_final = 364.760804 V`.
- `delta_vdc = 3.835563 %`.
- `max_abs_i2 = 15.692529 A`.

Con BESS preliminar:

- `Vdc_pre_step = 344.801523 V`.
- `Vdc_min_post_step = 341.690534 V`.
- `Vdc_final = 341.690818 V`.
- `delta_vdc = 0.902255 %`.
- `max_abs_i2 = 15.692168 A`.
- `i_bess_min = -2.459666 A`.
- `i_bess_max = 0 A`.
- `i_bess_final = -0.845409 A`.
- `p_bess_dc_min = -848.386376 W`.
- `p_bess_dc_final = -288.868431 W`.
- `soc_bess_final = 0.600019`.
- `soh_bess_final = 0.668182`.
- `vt_bess_final = 3.791690 V`.

La diferencia entre las caídas relativas es `-2.933308` puntos porcentuales a favor del caso con BESS. Sin embargo, los casos parten de valores distintos de `Vdc_pre_step` y el BESS presenta corriente y potencia negativas, correspondientes a carga. Por tanto, esta comparación no demuestra todavía soporte activo del BESS ante el escalón; solo documenta el comportamiento del acople preliminar existente.

## Criterio de referencia para la integración GFM

Al activar el controlador GFM, los mismos escenarios deberán volver a ejecutarse y compararse contra esta línea base. Como mínimo se deberán revisar:

- éxito del integrador y ausencia de `NaN` o `Inf`;
- `Vdc` antes, durante y después de los escalones;
- frecuencia, nadir y RoCoF;
- `p_pcc`, `p_bridge` e `i2`;
- respuesta del escenario abrupto del 40 %, por su margen reducido;
- signos y límites del intercambio BESS;
- diferencias entre los puntos de operación sin BESS y con BESS.

## Conclusión

La línea base grid-following pre-GFM queda aprobada para comparación posterior. No se detectaron fallos numéricos ni regresiones en los cuatro escenarios. El caso del 40 % debe tratarse como escenario crítico, y la mejora aparente del caso con BESS debe mantenerse como resultado preliminar hasta integrar el GFM y una estrategia de gestión del almacenamiento coherente con soporte activo y restricciones de batería de segunda vida.
