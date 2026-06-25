# Tarea 5.2 — Implementación mínima del soporte del BESS al enlace DC

## Subtarea 1 — Revisión de signo y activación

Estado: cerrada sin modificación de código.

La Tarea 5.1 confirmó que la convención de signos y la activación existentes son correctas:

- `IBESS > 0` y `PBESS > 0` representan descarga e inyección al enlace DC.
- `IBESS < 0` y `PBESS < 0` representan carga y absorción desde el enlace DC.
- La identidad `PBESS = Vdc*IBESS` se cumple numéricamente.
- La ley actual `IBESS_cmd = Kp_bess*(Vdc_ref - Vdc)` produce una orden positiva cuando `Vdc < Vdc_ref`.
- En el escenario severo del 40 %, después del escalón se observó descarga positiva del BESS.
- No se detectaron solicitudes positivas de descarga bloqueadas sin causa operativa.

Por tanto, no se corrige la lógica existente.

## Subtarea 2 — Lazo externo PI del enlace DC

Estado: implementado como bloque aislado, todavía no conectado a la planta.

Se añadió `src/controllers/dc_link_bess_pi.py` con la estructura:

`e_vdc = Vdc_ref - Vdc`

`PBESS_ref_unsat = Kp*e_vdc + Ki*xi_vdc`

`dxi_vdc/dt = e_vdc`

La salida positiva conserva la convención de descarga del BESS. Los parámetros se expresan como `Kp [W/V]` y `Ki [W/(V*s)]`. El bloque exige que las ganancias se suministren explícitamente; esta subtarea no realiza sintonización.

El integrador se mantiene aislado y no altera el vector protegido GFM+BESS de 15 estados. Su incorporación al solver global, la conexión a la referencia de potencia, la saturación y el anti-windup corresponden a subtareas posteriores.

Pruebas asociadas:

`src/validation/test_dc_link_bess_pi.py`
