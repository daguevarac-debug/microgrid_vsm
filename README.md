# Baseline de Tesis: Microrred Fotovoltaica + BESS-SLB

## Descripción general
Este repositorio implementa un **baseline de tesis** para una microrred fotovoltaica con simulación dinámica local, acople secuencial **one-way** al sistema de distribución IEEE de 33 nodos, y un modelo dinámico de batería de segunda vida (BESS-SLB).

El objetivo del baseline es mantener una base técnicamente consistente, trazable y extensible para trabajo de investigación posterior.

## Alcance actual (implementado)

### Microrred PV
- Modelo del arreglo fotovoltaico (PV array).
- Dinámica del bus DC (DC-link).
- Modelo del filtro LCL.
- Fuente inversora y control baseline tipo grid-following con PI.
- Simulación dinámica local del sistema de microrred.
- Acople secuencial one-way al sistema IEEE 33 en el PCC.

### BESS-SLB (batería de segunda vida)
- **Modelo dinámico Thevenin 1RC** (`bess/model.py`):
  - Terminal: `V_t = OCV(SoC) - i*R0(SoH) - V_rc`
  - RC: `dV_rc/dt = -V_rc/(R1*C1) + i/C1`
  - SoC: `dSoC/dt = -i/(3600*Q_eff)` (coulomb counting)
- **Degradación de primer orden** (`bess/model.py`):
  - Estado de throughput: `dz_deg/dt = |i|/3600`
  - Ley de desvanecimiento lineal de SoH: `SoH = SoH_0 - k_deg*z_deg`
  - Resistencia dependiente de envejecimiento: `R0 = R0_nom*(1+k*(1-SoH))`
- **Carga de parámetros desde Excel** (`bess/characterization.py`):
  - OCV(SoC), R1(SoC), C1(SoC) desde archivo `OCV_SOC.xlsx`.
- **Modelo estático Phase-1** (`bess/phase1.py`):
  - Capacidad nominal, SoH inicial, resistencia interna caracterizada.
- **Validaciones cuantitativas** (`src/validation/`):
  - Step-2: comportamiento dinámico 1RC sin degradación.
  - Step-3: consistencia de degradación z_deg/SoH/Q_eff/R0.
  - Carga Excel: verificación de lectura correcta desde archivo.
  - Validaciones externas Braco Fig.5(b): comparación `Voltage vs Ah` para SL 0.5C, 1C y 1.5C.

### Convenciones de capacidad (obligatorias)
- `q_nom_ref_ah = 66 Ah` — capacidad nominal de referencia del par 2p Nissan Leaf.
- `q_init_case_ah` — capacidad inicial configurable del caso (no universal).
- `soh_init_case = q_init_case_ah / q_nom_ref_ah` — SoH inicial siempre derivado.
- `Q_eff(0) = q_nom_ref_ah * soh_init_case = q_init_case_ah`.
- Trazabilidad: Braco (2020, 2021) sustenta 66 Ah y la definicion de 1C desde esa referencia.
- Nota: Tran (2021) trabaja con celdas LFP de 20 Ah; no es fuente del valor 66 Ah.

## Funcionalidades no implementadas aún
- Integración del BESS-SLB en la simulación dinámica de la microrred (acople BESS + PV + inversor).
- Control grid-forming completo.
- Contribución final de inercia virtual activa.

## Estructura del repositorio
```
microgrid_vsm/
├── AGENTS.md                    # reglas de ingeniería para agentes/asistentes
├── README.md                    # este archivo
├── OCV_SOC.xlsx                 # datos de caracterización OCV/R1/C1
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
│   │   └── grid_following.py    # control grid-following PI
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

# Estudio de acople secuencial con IEEE 33
python src/ieee33_main.py

# Validaciones BESS-SLB
python src/validation/validate_bess_step2.py      # 1RC dinámico
python src/validation/validate_bess_step3.py      # degradación
python src/validation/validate_excel_load.py       # carga Excel
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

## Instrucciones básicas de ejecución
1. Crear y activar un entorno virtual de Python.
2. Instalar dependencias: `numpy`, `scipy`, `matplotlib`, `pandas`, `openpyxl`, `pandapower`.
3. Ejecutar el punto de entrada correspondiente desde la raíz del repositorio.

## Supuestos simplificados vigentes
- Modelo térmico: no implementado (temperatura constante asumida).
- Degradación: primer orden lineal, sin modelo de rodilla ni efectos no lineales.
- OCV/R1/C1: datos interpolados desde tabla; no incluye histéresis.
- R0 aging: ley empírica simplificada, no copiada textualmente de literatura.
- El BESS-SLB no está aún integrado en la dinámica de la microrred.

## Notas de ingeniería
- Este repositorio prioriza **coherencia física** y **trazabilidad científica**.
- La arquitectura separa física, control, simulación, plotting y reporte.
- El baseline está diseñado para extenderse en etapas futuras sin reescritura agresiva.
- Bibliografía principal: Braco et al. (2023), Tran et al. (2021).

## Advertencias sobre el alcance de tesis
- Este baseline **no** debe interpretarse como implementación grid-forming completa.
- El BESS-SLB está **modelado y validado**, pero **no integrado** en la simulación dinámica de la microrred.
- No se debe presentar código scaffold o planificado como contribución final implementada.
