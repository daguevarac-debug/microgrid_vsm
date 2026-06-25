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

La salida positiva conserva la convención de descarga del BESS. Los parámetros se expresan como `Kp [W/V]` y `Ki [W/(V*s)]` y deben suministrarse explícitamente. Esta etapa no realiza sintonización.

## Subtarea 3 — Conexión del PI a la referencia de potencia del BESS

Estado: cerrada.

Se añadió `src/microgrid_bess_pi.py` con la clase optativa `MicrogridWithBESSPI`. La referencia de potencia se convierte mediante:

`IBESS_cmd = PBESS_ref / Vdc`

La arquitectura anterior `MicrogridWithBESS` conserva sus 15 estados. La nueva arquitectura añade `xi_bess_vdc` en `x[15]`; los primeros 15 índices no se desplazan y los 16 estados se integran con el mismo solver global.

La clase entrega al VSG únicamente la potencia real del BESS. No modifica la ecuación de oscilación, la referencia del VSG, la inercia virtual `M` ni el amortiguamiento `D`.

## Subtareas 4 y 5 — Saturación, anti-windup, límites y deshabilitación

Estado: implementadas, pendientes de validación local.

La referencia PI queda limitada antes de convertirse a corriente:

`PBESS_ref = sat(PBESS_ref_unsat, PBESS_min, PBESS_max)`

Los límites dinámicos se construyen con las restricciones existentes:

- corriente máxima disponible dependiente de SoH;
- potencia máxima disponible dependiente de SoH;
- límite de potencia equivalente a `Vdc*IBESS_max_available`;
- SoC mínimo que bloquea descarga;
- SoC máximo que bloquea carga;
- estado explícito `bess_enabled`.

El límite positivo corresponde a descarga y el negativo a carga. Cuando el BESS está deshabilitado, ambos límites son cero, la referencia aplicada es cero, la corriente es cero y el VSG recibe disponibilidad de soporte igual a cero.

Se implementó anti-windup por integración condicional:

- si la salida satura en el límite superior y `e_vdc > 0`, se fija `dxi_bess_vdc/dt = 0`;
- si la salida satura en el límite inferior y `e_vdc < 0`, se fija `dxi_bess_vdc/dt = 0`;
- si el error ayuda a abandonar la saturación, el integrador continúa y puede descargarse;
- con BESS deshabilitado, el integrador permanece congelado.

El controlador no puede ordenar descarga cuando:

- `bess_enabled = False`;
- `SoC <= SoC_min`;
- la disponibilidad de corriente o potencia es cero por SoH o límites nominales;
- `Vdc <= 0` impide una conversión válida de potencia a corriente.

Las señales integradas incluyen referencia no saturada y saturada, límites dinámicos, bandera de saturación, estado de anti-windup, habilitación y disponibilidad de carga/descarga.

Pruebas:

- `src/validation/test_dc_link_bess_pi.py`;
- `src/validation/test_microgrid_bess_pi_connection.py`.
