# Tarea 5.2 — Implementación mínima del soporte del BESS al enlace DC

## Subtarea 1 — Revisión de signo y activación

Estado: cerrada sin modificación de código.

La Tarea 5.1 confirmó que la convención de signos y la activación existentes son correctas:

- `IBESS > 0` y `PBESS > 0` representan descarga e inyección al enlace DC.
- `IBESS < 0` y `PBESS < 0` representan carga y absorción desde el enlace DC.
- La identidad `PBESS = Vdc*IBESS` se cumple numéricamente.
- La ley anterior `IBESS_cmd = Kp_bess*(Vdc_ref - Vdc)` produce una orden positiva cuando `Vdc < Vdc_ref`.
- No se detectaron solicitudes positivas de descarga bloqueadas sin causa operativa.

Por tanto, no se corrige la lógica de signo existente.

## Subtarea 2 — Lazo externo PI del enlace DC

Estado: cerrada como bloque aislado.

Se añadió `src/controllers/dc_link_bess_pi.py` con la estructura:

`e_vdc = Vdc_ref - Vdc`

`PBESS_ref_unsat = Kp*e_vdc + Ki*xi_vdc`

La salida positiva conserva la convención de descarga del BESS. Los parámetros se expresan como `Kp [W/V]` y `Ki [W/(V*s)]` y deben suministrarse explícitamente.

## Subtarea 3 — Conexión del PI a la referencia de potencia del BESS

Estado: cerrada.

Se añadió `src/microgrid_bess_pi.py` con la clase optativa `MicrogridWithBESSPI`. La referencia de potencia se convierte mediante:

`IBESS_cmd = PBESS_ref / Vdc`

La arquitectura anterior `MicrogridWithBESS` conserva sus 15 estados. La nueva arquitectura añade `xi_bess_vdc` en `x[15]`; los primeros 15 índices no se desplazan y los 16 estados se integran con el mismo solver global.

La clase entrega al VSG únicamente la potencia real del BESS. No modifica la ecuación de oscilación, la referencia del VSG, la inercia virtual `M` ni el amortiguamiento `D`.

## Subtareas 4 y 5 — Saturación, anti-windup, límites y deshabilitación

Estado: cerradas.

La referencia PI queda limitada antes de convertirse a corriente:

`PBESS_ref = sat(PBESS_ref_unsat, PBESS_min, PBESS_max)`

Los límites dinámicos se construyen con las restricciones existentes de corriente, potencia, SoC y SoH. El límite positivo corresponde a descarga y el negativo a carga. Con `bess_enabled = False`, la referencia aplicada, la corriente y la derivada integral son cero.

Se implementó anti-windup por integración condicional: el integrador se congela cuando el error empuja la salida más allá del límite activo y vuelve a integrar cuando el error ayuda a abandonar la saturación.

## Subtarea 6 — Pruebas unitarias del soporte BESS-DC

Estado: cerrada.

Las pruebas cubren signo de potencia y corriente, error nulo, respuesta ante subtensión y sobretensión, saturación, anti-windup, límites de corriente, potencia, SoC y SoH, BESS deshabilitado, conservación del mapeo de estados y conservación de `M` y `D`.

Archivos:

- `src/validation/test_dc_link_bess_pi.py`;
- `src/validation/test_microgrid_bess_pi_connection.py`.

## Subtarea 7 — Ajuste mínimo de Kp y Ki

Estado: implementada con una sola pareja candidata, pendiente de validación local.

No se realiza una optimización ni un barrido. Se evalúa únicamente:

- `Kp = 170 W/V`, equivalente al soporte proporcional anterior cerca de 340 V: `340 V * 0.5 A/V`;
- `Ki = 10 W/(V*s)`, valor integral pequeño para introducir corrección estacionaria sin un cambio agresivo.

La pareja se valida en el escenario GFM seleccionado `(M, D) = (80, 1500)` con escalón severo de carga del 40 %. La aceptación requiere éxito numérico, cumplimiento de los criterios existentes del enlace DC y frecuencia, y respeto de los límites del BESS.

El error final respecto a 340 V se registra como diagnóstico, pero no se añade como criterio nuevo.

Script y prueba:

- `src/validation/validate_bess_pi_minimal_tuning.py`;
- `src/validation/test_validate_bess_pi_minimal_tuning.py`.

Salida:

`outputs/validation/dc_link_regulation/gfm_m80_d1500_bess_pi_minimal_tuning.json`
