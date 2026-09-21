# Contexto maestro de trabajo

## Estado académico

- Objetivo 1 cerrado como baseline de modelado PV + BESS-SLB + bus DC + LCL +
  carga R-L; grid-following se conserva como regresión.
- Objetivo 2 cerrado para VSG clásico integrado y validado internamente:
  actividad 2.1 `PASS`, 2.2/2.3 `REVIEW` con limitaciones explícitas. Incluye
  restricciones BESS, PI externo, sintonía multi-escenario y pequeña señal
  numérica. Autoridad: `objective_2_activities_2_1_to_2_3_closure.md`.
- El `REVIEW` integrado al 40% y el `FAIL` de factibilidad DC del escenario
  severo extendido de sintonía deben conservarse. No son regresiones nuevas.
- Objetivo 3 es la siguiente fase: aplicar Obj. 1–2 en una red colombiana.
  La red real aún no se recibió; opciones del director: San Andrés o Cundinamarca.
  Puede llegar desde DIgSILENT/PowerFactory o pandapower.

## Reglas y puntos de entrada

Leer `AGENTS.md` antes de cambios. Preservar ecuaciones, estados, signos,
límites BESS, un solver global y `M=80, D=1500`. No alterar Obj. 1–2 sin razón
explícita y regresión. No confundir FOVIC prototipo con el GFM activo.

- Baseline local: `python src/main.py` (`--with-bess` opcional).
- IEEE 33 GFM+BESS: `python src/ieee33_main.py`; acople secuencial one-way.
- Obj. 3: `python src/objective3_main.py ruta/al/contrato.json`.
  Contrato neutral v1 en `src/study_network.py`; fixture únicamente sintético
  en `src/validation/fixtures/objective3_synthetic.json`.
- Ensayo integrado opcional: añadir `--run-baseline --q-pcc-mvar VALOR`.
  Reutiliza escenario local GFM+BESS+PI existente y dos flujos estáticos;
  no valida un caso real ni simula frecuencia dinámica de la red externa.

## Próxima acción

Recibir archivo original, versión, procedencia, unidades/bases, topología/equipos,
P/Q, controles, PCC y flujo fuente convergido. Inventariar equipos y escribir
solo el adaptador necesario hacia el contrato neutral; extenderlo únicamente
si datos reales lo exigen. Validar contra la fuente, acordar escenarios y
criterios finales, y luego ejecutarlos. No inventar redes, ratings ni perfiles.

Guía completa y pruebas: `objective_3_preparation.md`.
Supuestos físicos: `model_assumptions.md`. No hay DC/DC detallado, BMS industrial,
FOVIC final, HIL/validación experimental ni co-simulación dinámica bidireccional.
