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

## Estados del modelo/control

El vector mínimo de estados internos del inversor grid-forming es:

```text
x_gfm = [theta, omega]
```

Donde:

- `theta` [rad]: ángulo eléctrico interno del inversor; define la fase de la tensión trifásica sintetizada.
- `omega` [rad/s]: frecuencia angular interna del inversor; gobierna la evolución de `theta`.

La dinámica mínima asociada es:

```text
dtheta/dt = omega
domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M
```

`theta` y `omega` son estados internos dinámicos del control GFM. También pueden registrarse como salidas observables para diagnóstico, pero eso no cambia su naturaleza de estados internos.

No son estados internos del GFM: `P_ref` (referencia de control), `V_ref`/`v_ln_rms` (referencia de tensión), `m_ctrl`/`m_max` (índice o límite de modulación), `P_e` (medición o estimación de planta), `Vdc` (variable de planta/bus DC), `v_inv_abc` (señal manipulada hacia la planta), `freq_hz` (métrica derivada de `omega`), `power_imbalance = P_ref - P_e` (variable algebraica) ni `max_abs_frequency_deviation_hz` (métrica de validación).

## Parámetros de sintonía futura

Los parámetros mínimos configurables del bloque GFM para simulación, validación
aislada y sintonía futura en el Objetivo 2 son:

1. `f_nom` [Hz] u `omega_ref` [rad/s]
   - Frecuencia nominal del inversor.
   - `omega_ref = 2*pi*f_nom`.

2. `theta0` [rad]
   - Ángulo eléctrico inicial.

3. `P_ref` [W]
   - Referencia de potencia activa.
   - Define el punto de equilibrio de potencia activa.

4. `V_ref` o `v_ln_rms` [V RMS fase-neutro]
   - Referencia de tensión AC.
   - Modifica la amplitud deseada de la referencia de tensión sintetizada.

5. `M` o `inertia_m`
   - Parámetro de inercia virtual equivalente.
   - Debe ser estrictamente positivo.

6. `D` o `damping_d`
   - Amortiguamiento virtual.
   - Debe ser mayor o igual que cero.

7. `m_max` o `m_ctrl` [-]
   - Límite o índice de modulación.
   - Restringe la tensión sintetizable según `Vdc`.

Ajustar estos parámetros no debe cambiar la estructura del modelo. `M`/`inertia_m`
y `D`/`damping_d` modifican la respuesta transitoria de frecuencia; `P_ref` define
el equilibrio de potencia activa; `V_ref`/`v_ln_rms` y `m_max`/`m_ctrl` modifican
la amplitud de la referencia de tensión sintetizada y su límite por bus DC. En el
Objetivo 2 también podrán considerarse límites derivados del BESS/BMS, como
corriente disponible, potencia disponible, `SoC` y `SoH`, para restringir la
potencia inercial o la referencia activa.

Estos parámetros son candidatos de sintonía futura. No constituyen todavía una
estrategia VSG/FOVIC final ni implican que el control grid-forming esté integrado
al modelo principal de microrred.

No son parámetros ajustables del control GFM: `Vdc` (pertenece a la planta/bus DC), `P_e` (medición o estimación de planta), `theta` y `omega` (estados internos), `freq_hz`, `power_imbalance` y `max_abs_frequency_deviation_hz` (métricas derivadas).

Quedan fuera de esta etapa: `Q_ref`, droop `Q-V`, ganancias de lazos internos de tensión/corriente, FOVIC, parámetros fraccionarios y estrategias avanzadas de despacho o control.

## Salidas observables

Las salidas observables no deben confundirse con entradas manipulables. En esta interfaz mínima se distinguen tres grupos.

### 1. Salida directa hacia la planta

- `v_inv_abc` [V]: tensión trifásica sintetizada por el inversor. Es la señal que la planta eléctrica recibe desde el bloque inversor y puede registrarse para verificar amplitud, balance y limitación por `Vdc`.

### 2. Mediciones o estimaciones provenientes de la planta

- `P_e` [W]: potencia activa eléctrica entregada por el inversor. Puede estimarse en una integración futura como `P_e = v_pcc^T * i2`; no es entrada manipulable.
- `Vdc` [V]: tensión del bus DC disponible para sintetizar tensión AC.
- `i1_abc` [A]: corriente del lado inversor/filtro.
- `i2_abc` [A]: corriente del lado PCC/carga.
- `v_pcc_abc` [V]: tensión en el punto de acople local.
- `idc_inv` [A]: corriente DC equivalente asociada al intercambio de potencia DC/AC; no es entrada manipulable independiente.

### 3. Métricas derivadas para diagnóstico y validación

- `theta` [rad]: ángulo interno GFM. Es estado interno, pero observable para diagnóstico.
- `omega` [rad/s]: frecuencia angular interna. Es estado interno, pero observable para diagnóstico.
- `freq_hz` [Hz]: frecuencia equivalente calculada como `omega/(2*pi)`.
- `power_imbalance` [W]: diferencia `P_ref - P_e`; explica el signo de la evolución de frecuencia.
- `max_abs_frequency_deviation_hz` [Hz]: métrica de validación respecto a la frecuencia nominal.

`P_e`, `Vdc`, `i1_abc`, `i2_abc` y `v_pcc_abc` son señales de planta o mediciones/estimaciones. `theta` y `omega` son estados internos del GFM que se registran como salidas observables para diagnóstico. `freq_hz` y `max_abs_frequency_deviation_hz` son métricas derivadas, no estados físicos nuevos.

Esta documentación no activa control grid-forming ni cambia el baseline actual.

## Variables de interés para control

Para el diseño futuro del control en el Objetivo 2, las variables relevantes de
la interfaz se agrupan de la siguiente forma:

- Referencias o consignas: `P_ref` y `V_ref`/`v_ln_rms`.
- Señal manipulada hacia la planta: `v_inv_abc`, limitada por `Vdc` y por
  `m_max`/`m_ctrl`.
- Mediciones o estimaciones de planta: `P_e`, `Vdc`, `i1_abc`, `i2_abc` y
  `v_pcc_abc`.
- Estados internos del control: `theta` y `omega`.
- Métricas derivadas de diagnóstico: `freq_hz` y `power_imbalance`.
- Variables del BESS/BMS para restricciones operativas futuras: `SoC`, `SoH`,
  límites de corriente de carga/descarga y límites de potencia DC disponible.

Estas variables permiten trazar qué información debe intercambiarse entre planta,
controlador y BESS/BMS. Las métricas de frecuencia del bloque aislado sirven solo
como diagnóstico preliminar y no deben interpretarse como métricas finales de
desempeño de la tesis hasta que el GFM/VSG se acople a la planta completa.

## Preparación para el Objetivo 2

Esta interfaz deja definidos los elementos mínimos para iniciar el Objetivo 2: determinar la estrategia de control de inercia virtual del inversor grid-forming con el sistema de gestión de baterías de segunda vida.

Elementos ya delimitados para el diseño:

1. Entradas disponibles para el controlador: `P_ref`, `V_ref`/`v_ln_rms` y `m_max`/`m_ctrl`.
2. Mediciones necesarias desde la planta: `P_e`, `Vdc`, `i1_abc`, `i2_abc`, `v_pcc_abc` e `idc_inv`.
3. Estados internos disponibles: `theta` y `omega`.
4. Parámetros de sintonía futura: `f_nom`/`omega_ref`, `theta0`, `P_ref`, `V_ref`/`v_ln_rms`, `M`/`inertia_m`, `D`/`damping_d` y `m_max`/`m_ctrl`.
5. Variables que deberán conectarse con el BESS/BMS: `SoC`, `SoH`, corriente máxima de carga/descarga, potencia máxima de carga/descarga y límites de operación segura del almacenamiento.

Esta etapa no implementa todavía VSG completo, FOVIC ni gestión BESS/BMS. La interfaz queda documentada para que el Objetivo 2 pueda diseñar la estrategia de control sin redefinir la planta.

La siguiente etapa deberá decidir si la estrategia será VSG clásico, FOVIC u otra variante justificada, y cómo los límites del BESS modifican `P_ref`, `M`, `D` o la potencia inercial disponible. No debe afirmarse todavía que la estrategia de inercia virtual está implementada.
