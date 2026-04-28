# Baseline de Tesis: Microrred Fotovoltaica + BESS-SLB

## Descripción general
Este repositorio implementa un **baseline de tesis** para una microrred fotovoltaica con simulación dinámica local, acople secuencial **one-way** al sistema de distribución IEEE de 33 nodos, y un modelo dinámico de batería de segunda vida (BESS-SLB).

El objetivo del baseline es mantener una base técnicamente consistente, trazable y extensible para trabajo de investigación posterior.

## Alcance actual (implementado)

### Microrred PV
- Modelo del arreglo fotovoltaico (PV array).
- Modelo FV parametrizado con modulo comercial real de referencia: **LONGi LR7-54HJD-500M**.
- Ajuste STC del modelo FV de un diodo validado contra datasheet.
- Dinámica del bus DC (DC-link).
- Modelo del filtro LCL integrado y validado en etapa baseline (ver `docs/model_assumptions.md`).
- Fuente inversora y control baseline tipo grid-following con PI.
- Modelo de carga agregado AC trifasico balanceado tipo R-L de impedancia constante.
- Carga nominal `P_load_nominal = 3 kW`, `fp = 0.95` inductivo, con perturbaciones nominal, `+20 %` y `+40 %`.
- Simulación dinámica local del sistema de microrred.
- Acople secuencial one-way al sistema IEEE 33 en el PCC.

### BESS-SLB (batería de segunda vida)
- **Modelo dinámico Thevenin 1RC** (`bess/model.py`) ya validado en campañas internas.
- **Degradación de primer orden** (`bess/model.py`) con métricas cuantitativas en Step-3.
- **Carga de parámetros desde Excel** (`bess/characterization.py`):
  - OCV(SoC), R1(SoC), C1(SoC) desde archivo `OCV_SOC.xlsx`.
- **Modelo estático Phase-1** (`bess/phase1.py`):
  - Capacidad nominal, SoH inicial, resistencia interna caracterizada.
- **Integracion preliminar BESS-DC-link** mediante `MicrogridWithBESS`:
  - acople idealizado al bus DC con `dVdc/dt = (ipv + i_bess - idc_inv)/Cdc`;
  - trazabilidad de potencia `p_bess_dc = Vdc * i_bess`.
- **Restricciones operativas baseline**:
  - `soc_min = 0.10`, `soc_max = 0.90`;
  - `i_bess_max_nominal = 66 A`;
  - `p_bess_dc_max_nominal = 22440 W`;
  - saturaciones coherentes de SoC, corriente y potencia.
- **Disponibilidad dependiente de SoH**:
  - `i_bess_max_available = i_bess_max_nominal * SoH`;
  - `p_bess_dc_max_available = min(p_bess_dc_max_nominal, Vdc_ref*i_bess_max_available)`;
  - para `SoH ~= 0.668182`: `i_bess_max_available = 44.1 A` y `p_bess_dc_max_available = 14994 W`.
- **Comparacion de escenarios de SoH** (`src/validation/compare_bess_soh_scenarios.py`):
  - SoH `1.00`, `0.70` y nominal `~= 0.668182` bajo el mismo escalon de carga.
- **Validaciones cuantitativas** (`src/validation/`):
  - Step-2: comportamiento dinámico 1RC sin degradación.
  - Step-3: consistencia de degradación z_deg/SoH/Q_eff/R0.
  - Carga Excel: verificación de lectura correcta desde archivo.
  - Validaciones externas Braco Fig.5(b): comparación `Voltage vs Ah` para SL 0.5C, 1C y 1.5C.

### Convenciones de capacidad (obligatorias)
- `q_nom_ref_ah = 66 Ah` como capacidad nominal de referencia Nissan Leaf 2p.
- `q_init_case_ah` es dependiente del caso; `soh_init_case` se deriva como `q_init_case_ah / q_nom_ref_ah`.
- La trazabilidad completa de ecuaciones protegidas y convenciones se mantiene en `AGENTS.md`.

### Inversor grid-forming mínimo aislado
- Estructura mínima documentada en `docs/grid_forming_minimal_structure.md`.
- Dinámica aislada del bloque GFM con `x_gfm = [theta, omega]`.
- Ecuación de frecuencia tipo swing/VSG reducida:
  `domega/dt = (P_ref - P_e - D*(omega - omega_ref)) / M`.
- Implementación aislada en `src/controllers/grid_forming.py` mediante `GridFormingFrequencyDynamics`.
- Validaciones aisladas de operación en isla, referencia trifásica de tensión, comportamiento de frecuencia y escalón de carga.
- Interfaz planta-control documentada en `docs/grid_forming_plant_control_interface.md`.
- Este avance es base trazable para el Objetivo 2; no reemplaza todavía el baseline grid-following del modelo principal.

## Funcionalidades no implementadas aún
- La integracion preliminar BESS-DC-link ya existe; falta integracion final con convertidor DC/DC detallado y BMS final.
- Control grid-forming completo integrado al modelo `Microgrid`.
- Estrategia final de inercia virtual VSG/FOVIC.
- Gestion BESS/BMS final para control de inercia virtual con restricciones completas.
- Acople del GFM aislado con PV + BESS + DC-link + LCL + PCC en el modelo principal.

## Estado de validación BESS-SLB
| Validación | Resultado | Estado |
| --- | ---: | --- |
| Braco Fig.5(b) SL 0.5C 25°C | MAPE=6.4201% (`outputs/validation/braco_fig5b_sl_0p5c/metrics_summary.csv`) | PASS |
| Braco Fig.5(b) SL 1C 25°C | MAPE=8.1716% (`outputs/validation/braco_fig5b_sl_1c/metrics_summary.csv`) | PASS |
| Braco Fig.5(b) SL 1.5C 25°C | MAPE=9.3351% (`outputs/validation/braco_fig5b_sl_1p5c/metrics_summary.csv`) | PASS |
| Step-2 1RC dinámico | Validado (ver `src/validation/validate_bess_step2.py`) | PASS |
| Step-3 degradación | Métricas en `outputs/validation/bess_step3/summary_metrics.csv` | PASS |

## Estado de validacion BESS (integracion)
| Validacion | Resultado | Estado |
| --- | --- | --- |
| `validate_bess_power_exchange.py` | `p_bess_dc = Vdc*i_bess` y signos coherentes | PASS |
| `validate_bess_units_scales.py` | Unidades basicas correctas; advertencia de escala `Vdc/vt_bess` | REVIEW |
| `validate_bess_integrated_nominal.py` | Caso nominal integrado estable; REVIEW interpretativo por escala | REVIEW |
| `validate_bess_soc_operational_limits.py` | SoC, corriente, potencia y disponibilidad por SoH | PASS |
| `compare_bess_soh_scenarios.py` | SoH 1.00, 0.70 y nominal; REVIEW interpretativo por escala | REVIEW |

## Actividad 1.3: diagnosticos del sistema completo
- `python src/main.py --with-bess`: simula el caso base completo preliminar PV + DC-link + inversor + LCL + BESS + carga y registra `Vdc`, `frequency_hz`, `p_pv_dc`, `p_bess_dc` e `i_bess`.
- Salida diagnostica principal: `outputs/complete_system_base_signals.png`.
- En este baseline, `frequency_hz = omega_ref/(2*pi)` es fija por el controlador grid-following; no representa todavia dinamica GFM/VSG.
- `p_load` en las figuras de `src/main.py` representa potencia activa demandada `[W]` desde `load_profile(t)`, no resistencia.
- `python src/main.py --compare-bess`: compara sin BESS vs con BESS preliminar. Salidas esperadas: `compare_vdc_bess.png`, `compare_bess_signals.png`, `compare_power_bess.png`.
- Metricas recientes de referencia para la comparacion: sin BESS `max_drop_pre ~= 14.549 V`; con BESS `max_drop_pre ~= 3.111 V`; `t_recovery_s = nan` en ambos casos; `i_bess_mean` post-escalon `~= -0.921 A`; `p_bess_dc_mean` post-escalon `~= -314.981 W`.
- Interpretacion: en ese escenario el BESS modifica el punto de operacion del bus DC y absorbe potencia (`p_bess_dc < 0`); no debe presentarse como prueba final de soporte activo.
- `python src/validation/compare_bess_soh_scenarios.py`: compara SoH `1.00`, `0.70` y nominal `~= 0.668182`.
- Salidas SoH: `outputs/validation/bess_soh_scenarios/bess_soh_scenarios_summary.csv`, `bess_soh_scenarios_vdc.png`, `bess_soh_scenarios_power.png`, `bess_soh_scenarios_current.png`.
- Interpretacion SoH: la disponibilidad de corriente/potencia disminuye con el SoH; las curvas dinamicas quedan casi superpuestas porque el escenario no satura limites del BESS.
- Estas comparaciones son baseline/preliminares y no reemplazan validacion final con DC/DC detallado, BMS final ni control GFM/VSG.

## Validaciones básicas de DC-link
- Existe integración preliminar/conservadora del BESS al bus DC mediante `MicrogridWithBESS`.
- Ecuación verificada: `dVdc/dt = (ipv + i_bess - idc_inv)/Cdc`.
- Pruebas unitarias de balance/signo: `src/validation/test_dclink_dynamics.py`.
- Criterios internos, supuestos y PASS/FAIL de etapa: `docs/model_assumptions.md`.

## Validaciones básicas del filtro LCL
- Parámetros y ecuaciones baseline documentados en `docs/model_assumptions.md`.
- Frecuencia de resonancia calculada: `f_res ≈ 2250.8 Hz`.
- Verificación preliminar: `f_res > 10*f_g` para `f_g = 60 Hz`.
- Requisito futuro: `f_sw >= 4501.6 Hz` para cumplir `f_res <= 0.5*f_sw`.
- Script de validación: `src/validation/validate_lcl_no_unphysical_oscillations.py`.
- Resultado actual: `PASS`.
- Esta validación no es una demostración formal de estabilidad ni reemplaza el análisis futuro de control/grid-forming.

## Validaciones de carga y escenarios aislados
- `src/validation/validate_microgrid_rl_load.py`: verifica carga R-L balanceada, `P_load_nominal = 3 kW`, `fp = 0.95` inductivo y perturbaciones nominal/`+20 %`/`+40 %`. Resultado actual: `PASS`.
- `src/validation/validate_islanded_operation_scenarios.py`: consolida escenarios aislados `steady_operation`, `load_step_20`, `abrupt_load_change` y `bess_vs_no_bess`. Resultado actual: `PASS`.

## Estado de validación FV
- Módulo de referencia: `LONGi LR7-54HJD-500M`.
- Variables comparadas: `Vmpp`, `Impp`, `Isc`.
- Criterio de aceptación: error absoluto `<= 5 %`.
- Resultado final: `PASS`.
- Errores STC reportados (ajuste restringido): `Vmpp = -0.2423 %`, `Impp = -3.0904 %`, `Isc = -0.0000 %`.
- Supuestos del modelo: `docs/model_assumptions.md`.
- Script de validación: `src/validation/validate_pv_stc_fit.py`.

## Estructura del repositorio
```
microgrid_vsm/
├── AGENTS.md                    # reglas de ingeniería para agentes/asistentes
├── README.md                    # este archivo
├── OCV_SOC.xlsx                 # datos de caracterización OCV/R1/C1
├── docs/
│   ├── model_assumptions.md     # supuestos y criterios internos del baseline
│   ├── grid_forming_minimal_structure.md       # estructura matemática mínima GFM
│   └── grid_forming_plant_control_interface.md # interfaz planta-control GFM
├── src/
│   ├── config.py                # constantes centralizadas del modelo
│   ├── microgrid.py             # modelo compuesto de la microrred
│   ├── main.py                  # punto de entrada: simulación local
│   ├── pv_model.py              # modelo del arreglo PV
│   ├── dclink.py                # dinámica del bus DC
│   ├── lcl_filter.py            # filtro LCL
│   ├── inverter_source.py       # fuente inversora
│   ├── ieee33_base.py           # red IEEE 33
│   ├── ieee33_coupling.py       # acople secuencial one-way
│   ├── ieee33_main.py           # punto de entrada: estudio IEEE 33
│   ├── ieee33_plots.py          # visualización IEEE 33
│   ├── ieee33_reporting.py      # reporte IEEE 33
│   ├── ieee33bus.txt             # datos de topología IEEE 33
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── base.py              # interfaz base de controladores
│   │   ├── grid_following.py    # control grid-following PI
│   │   └── grid_forming.py      # dinámica GFM mínima aislada
│   ├── bess/                    # paquete BESS-SLB
│   │   ├── __init__.py          # re-exports públicos
│   │   ├── validators.py        # validación de entradas numéricas
│   │   ├── capacity.py          # convención de capacidad (q_nom_ref, q_init_case, soh derivado)
│   │   ├── lookup_table.py      # tabla OCV/R1/C1 vs SoC
│   │   ├── phase1.py            # modelo estático Phase-1
│   │   ├── model.py             # modelo dinámico 1RC + degradación
│   │   └── characterization.py  # carga desde Excel
│   ├── bess_second_life.py      # shim backward-compat
│   ├── bess_characterization.py # shim backward-compat
│   └── validation/
│       ├── validate_bess_step2.py   # validación dinámica 1RC
│       ├── validate_bess_step3.py   # validación degradación
│       ├── validate_excel_load.py   # validación carga Excel
│       ├── validate_pv_stc_fit.py   # validación STC del modelo FV contra datasheet
│       ├── validate_microgrid_rl_load.py              # validacion carga R-L agregada
│       ├── validate_islanded_operation_scenarios.py   # escenarios aislados de carga/BESS
│       ├── test_grid_forming_frequency_dynamics.py       # pruebas unitarias GFM mínimo
│       ├── validate_grid_forming_step_response.py        # escalón de carga GFM aislado
│       ├── validate_grid_forming_islanded_operation.py   # operación aislada GFM
│       ├── validate_grid_forming_voltage_regulation.py   # referencia trifásica y límite Vdc
│       ├── validate_grid_forming_frequency_behavior.py   # equilibrio/aumento/reducción de carga
│       ├── braco_fig5b_external_common.py   # helper común de validaciones externas
│       ├── validate_braco_fig5b_sl_0p5c.py  # validación externa SL 0.5C
│       ├── validate_braco_fig5b_sl_1c.py    # validación externa SL 1C
│       └── validate_braco_fig5b_sl_1p5c.py  # validación externa SL 1.5C
└── outputs/
    └── validation/
        ├── bess_step2/          # figuras generadas por step2
        └── bess_step3/          # figuras y CSV generados por step3
```

## Puntos de entrada
```bash
# Simulación dinámica local de la microrred PV
python src/main.py
python src/main.py --with-bess      # simulacion local con BESS preliminar
python src/main.py --compare-bess   # comparacion sin BESS vs con BESS
python src/validation/compare_bess_soh_scenarios.py  # comparacion por SoH

# Estudio de acople secuencial con IEEE 33
python src/ieee33_main.py

# Validaciones BESS-SLB
python src/validation/validate_bess_step2.py      # 1RC dinámico
python src/validation/validate_bess_step3.py      # degradación
python src/validation/validate_excel_load.py       # carga Excel
python src/validation/validate_bess_power_exchange.py          # potencia BESS-DC-link
python src/validation/validate_bess_units_scales.py            # unidades y escalas BESS-DC
python src/validation/validate_bess_integrated_nominal.py      # caso nominal integrado
python src/validation/validate_bess_soc_operational_limits.py  # limites SoC/corriente/potencia
python src/validation/compare_bess_soh_scenarios.py            # escenarios de SoH
python src/validation/validate_pv_stc_fit.py       # validación STC del modelo FV contra datasheet
python -m unittest discover -s src/validation -p "test_dclink_dynamics.py" -v  # pruebas básicas DC-link
python src/validation/validate_lcl_no_unphysical_oscillations.py  # validación práctica de estados LCL
python src/validation/validate_microgrid_rl_load.py                # validacion carga R-L agregada
python src/validation/validate_islanded_operation_scenarios.py     # escenarios aislados de carga/BESS

# Validaciones GFM mínimas aisladas (no acopladas a Microgrid)
python src/validation/test_grid_forming_frequency_dynamics.py
python src/validation/validate_grid_forming_islanded_operation.py
python src/validation/validate_grid_forming_voltage_regulation.py
python src/validation/validate_grid_forming_frequency_behavior.py
python src/validation/validate_grid_forming_step_response.py

python src/validation/validate_braco_fig5b_sl_0p5c.py  # Braco Fig.5(b) SL 0.5C 25C
python src/validation/validate_braco_fig5b_sl_1c.py    # Braco Fig.5(b) SL 1C 25C
python src/validation/validate_braco_fig5b_sl_1p5c.py  # Braco Fig.5(b) SL 1.5C 25C
python src/validation/validate_braco_fig5b_sensitivity.py  # sensibilidad paramétrica externa Braco Fig.5(b)
```

Sensibilidad paramétrica externa Braco Fig.5(b):
- Propósito: cuantificar robustez del modelo frente a perturbaciones razonables sin recalibración manual.
- Parámetros perturbados (one-at-a-time): `q_init_case_ah` (±5%), `r0_nominal_ohm` (±10%), `soc_initial` (0.98, 0.999, 1.0).
- Casos incluidos: SL 0.5C, SL 1C y SL 1.5C a 25°C.

Entrada esperada para validación externa:
- `5b_SL_0p5C_25C.xlsx` en la raíz del repositorio.
- `5b_SL_1C_25C.xlsx` en la raíz del repositorio.
- `5b_SL_1p5C_25C.xlsx` en la raíz del repositorio.

Salida esperada:
- `outputs/validation/braco_fig5b_sl_0p5c/` con figura y CSV (si no hay bloqueo de escritura).
- `outputs/validation/braco_fig5b_sl_1c/` con figura y CSV (si no hay bloqueo de escritura).
- `outputs/validation/braco_fig5b_sl_1p5c/` con figura y CSV (si no hay bloqueo de escritura).
- `outputs/validation/braco_fig5b_sensitivity/` con `sensitivity_runs.csv`, `sensitivity_summary.csv` y `mape_sensitivity_span.png`.

Salidas diagnosticas de Actividad 1.3:
- `outputs/complete_system_base_signals.png`.
- `outputs/compare_vdc_bess.png`.
- `outputs/compare_bess_signals.png`.
- `outputs/compare_power_bess.png`.
- `outputs/validation/bess_soh_scenarios/bess_soh_scenarios_summary.csv`.

## Instrucciones básicas de ejecución
1. Crear y activar un entorno virtual de Python.
2. Instalar dependencias: `numpy`, `scipy`, `matplotlib`, `pandas`, `openpyxl`, `pandapower`.
3. Ejecutar el punto de entrada correspondiente desde la raíz del repositorio.

## Supuestos del modelo
Los supuestos simplificados vigentes del baseline se documentan en:
- `docs/model_assumptions.md`

## Notas de ingeniería
- Este repositorio prioriza **coherencia física** y **trazabilidad científica**.
- La arquitectura separa física, control, simulación, plotting y reporte.
- El baseline está diseñado para extenderse en etapas futuras sin reescritura agresiva.
- Bibliografía principal: Braco et al. (2023), Tran et al. (2021).

## Advertencias sobre el alcance de tesis
- El GFM actual es **mínimo, aislado y validado funcionalmente**; sirve como base para el Objetivo 2.
- El GFM actual **no** debe presentarse como controlador final ni como estrategia de inercia virtual ya implementada.
- El GFM actual **no** reemplaza todavía el baseline grid-following del modelo principal.
- El BESS-SLB esta **modelado y validado** y cuenta con **acople preliminar al bus DC** (`MicrogridWithBESS`), restricciones operativas y disponibilidad dependiente de SoH; todavia no incluye DC/DC detallado, BMS final ni control grid-forming final.
- El modelo de carga R-L y los escenarios aislados son baseline de validacion interna; no representan perfil horario real medido, ZIP completo, cargas no lineales, desbalance ni validacion experimental.
- La comparacion con/sin BESS en escenarios aislados no debe interpretarse todavia como validacion final de soporte dinamico del BESS ni de estrategia VSG/FOVIC.
- La frecuencia no debe interpretarse como metrica final de soporte mientras el modelo principal siga en baseline/grid-following.
- El `REVIEW` por escala `Vdc/vt_bess` es una advertencia interpretativa por falta de escalamiento explicito del banco o DC/DC detallado; no es falla numerica por si mismo.
- No se debe presentar código scaffold o planificado como contribución final implementada.
