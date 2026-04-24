# Interfaz planta-control del inversor grid-forming

Este documento define la interfaz mínima entre el bloque de control grid-forming y la planta eléctrica. El baseline actual sigue siendo grid-following; esta descripción es estructural y no activa todavía control grid-forming en `main.py` ni cambia el vector de estados de `Microgrid`.

## Entradas manipulables

Para el inversor grid-forming mínimo, las variables manipuladas o referencias de control relevantes son:

1. `P_ref` [W]
   - Referencia de potencia activa.
   - Entra en la dinámica interna de frecuencia:

```text
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

2. `V_ref` o `v_ln_rms` [V RMS fase-neutro]
   - Referencia de tensión AC.
   - Define la amplitud deseada de la tensión trifásica sintetizada por el inversor.

3. `m_ctrl` o `m_max` [-]
   - Índice o límite de modulación.
   - Limita la amplitud sintetizable según el bus DC disponible.

4. `v_inv_abc` [V]
   - Tensión trifásica efectivamente entregada por el bloque inversor a la planta.
   - Es la señal manipulada directa que ve la planta eléctrica.
   - Se calcula a partir de `theta`, `V_ref`/`v_ln_rms`, `Vdc` y `m_max`.

`P_ref` y `V_ref` son referencias de control. `v_inv_abc` es la señal manipulada directa hacia la planta.

`idc_inv` no debe tratarse como entrada manipulable independiente en esta etapa; es una consecuencia del intercambio de potencia entre el bus DC y el lado AC.

`P_e` no es una entrada manipulable; es una magnitud medida o estimada de la planta. `theta` y `omega` son estados internos del control GFM, no entradas manipulables externas.

Quedan fuera de esta interfaz mínima: `Q_ref`, control `Q-V`, droop reactivo, FOVIC y lazos avanzados.
