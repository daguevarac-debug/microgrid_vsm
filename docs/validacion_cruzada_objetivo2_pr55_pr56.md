# Validación cruzada del Objetivo 2: PR 55 y PR 56

## Alcance y trazabilidad

Validación numérica interna, no experimental. Base PR 54: `687d24fe596c832c733e9ed621f90f9efa283ab6`; correcciones PR 56: `b63e60268da976ebc937ee2517fe973d8c885907`; auditoría PR 55: `79525d6ab6c23ed3b100e50d73db2584acea5759`. Las ejecuciones cruzadas usaron la rama temporal `temp/cross-validation-pr55-pr56` en `06c393487a8dbbea17f9f1b0f79bf3f9e853aaa6` (PR 56 más los dos scripts de prueba de PR 55). La integración aplica ambos commits sobre la base, sin modificar ecuaciones ni parámetros protegidos. El dossier y la auditoría originales indican explícitamente qué resultados son históricos.

Python 3.12.14, NumPy 2.5.5, SciPy 1.18.1, pytest 9.2.0; dependencias completas fijadas en [requirements-pr54.txt](../.github/requirements-pr54.txt). RK45: paso máximo 50 µs, `rtol=1e-6`, `atol=1e-8`. Horizonte 6,5 s; evento en 0,8 s; preevento 0,7–0,8 s y régimen final 5,5–6,5 s. La frecuencia se calcula de `omega/(2*pi)`; el controlador es `GFMController`, con `M=80`, `D=1500`. Los 13 casos DC/DC usan el modelo de 16 estados `MicrogridWithBESSDCDC`; los seis casos VSG usan `Microgrid` o `MicrogridWithBESSPI`, no el convertidor DC/DC.

Las evidencias consolidadas están en [`outputs/validation/cross_pr55_pr56`](../outputs/validation/cross_pr55_pr56/); sus hashes se verifican con `sha256sum -c SHA256SUMS` desde esa carpeta. Los dos CSV se normalizaron de CRLF a LF sin cambiar campos ni valores para permitir `git diff --check`; los SHA-256 originales verificados fueron `6abee17630f02bd10471ed7c39495bb27565b8faf2c23aa16442246b30263564` (comparación) y `efbec06bedb5742ef393cee322e125506f29773f9e6e203dd58080e1bcabe411` (13 casos). El manifiesto registra los hashes de los archivos normalizados. El JSON del Objetivo 1 conserva resultados y metadatos de ejecución, con rutas convertidas a relativas y el ejecutable a `python`; su SHA-256 original verificado fue `3b201622668086276a202ad2254c58407a42dd7a04fb9f41f442afdf6718a927`. Los valores de tiempo de ejecución y hashes de nuevos resultados pueden variar entre plataformas.

## Resultados y criterios

| Grupo | Estado | Resultado |
|---|---|---|
| Suite integrada | PASS | En la rama de integración se ejecutaron 50 pruebas y 29 subpruebas: los siete archivos de la suite focalizada de PR 56 más `test_audit_post_pr54_sustained_charge.py`. Se incluyen verificaciones de artefactos JSON; no todas regeneran simulaciones. |
| Límites y carga sostenida | PASS | 22 pruebas y 29 subpruebas en la campaña cruzada; matriz adicional de 54 combinaciones de SoC, SoH, tensión y PI. Incluye 10 V < Vmin y ambos signos. La recarga `-40 %` a 50 Hz pasó los balances y conteo de Coulomb. |
| Regresión Objetivo 1 | PASS | LCL, BESS paso 3 y límites de SoC. |
| DC/DC 50 Hz | PASS / REVIEW | Los 13 escenarios se regeneraron: 11 PASS y dos REVIEW con BESS deshabilitado, como antes. El caso de límite de potencia entrega como máximo 1200 W; saturación PI y anti-windup se activan en 87,38 % de las muestras totales. |
| VSG 50/60 Hz | PASS / REVIEW | Se regeneraron seis casos: `+40 %` sin BESS y `+20 %` / `+40 %` con PI, a 50 y 60 Hz. Cuatro PASS y dos REVIEW (sin BESS, +40 %). Los otros cuatro de la campaña original no se regeneraron en esta sesión. |
| GFM integrado | REVIEW | Cuatro simulaciones: régimen y +20 % PASS; +40 % sin BESS REVIEW; comparación con PI PASS. El REVIEW global es la limitación DC documentada. |
| Convergencia del nadir | REVIEW | El par corregido reproduce los mínimos muestreados de L1; la evidencia pre-parche L1/L2 difiere 0,000733 µHz en el mínimo continuo al ajustar tolerancias. Ambos usan `max_step=5e-5`; no demuestra convergencia frente al tamaño de paso. L3/L4 no se ejecutaron. |
| IEEE 906 | REVIEW | El perfil QSTS sintético se genera en `scripts/ieee_europe_lv_906_interface_and_qsts.py` sin dependencia del DC/DC; archivos de generador y evidencias versionadas no cambiaron entre commits. No se repitieron 24 h. La discrepancia IEEE 2015 de 9,54 % persiste; el origen externo mutable no queda fijado por esta comprobación. |
| Evidencia experimental | BLOCKED | Faltan ensayos BESS propios, catálogo de transformador y perfiles medidos; FOVIC sigue fuera de alcance. |

Las diferencias de los escenarios ensayados entre los resultados originales y corregidos son numéricamente despreciables; no se identificó un cambio físico significativo en sus métricas. Esto no prueba equivalencia para todas las condiciones posibles. La prueba de límites extremos es necesaria precisamente porque los escenarios dinámicos habituales no cubren todo el dominio de operación.

| Máximo absoluto de la diferencia entre las evidencias | Valor |
|---|---:|
| Mínimo Vdc, DC/DC | 1,31e-12 V |
| Mínimo frecuencia, DC/DC | 2,14e-14 Hz |
| RoCoF, DC/DC | 4,98e-10 Hz/s |
| SoC final / SoH final | 2,23e-16 / 0 |
| Corriente banco / bus | 5,26e-11 A / 5,77e-11 A |
| Fracciones de saturación PI / anti-windup / DC/DC | 0 / 0 / 0 |
| Diferencia de residuos de energía bus / DC/DC | 1,34e-10 J / 6,26e-13 J |
| VSG: frecuencia / RoCoF máximos | 7,11e-14 Hz / 7,55e-11 Hz/s |

El mayor residuo absoluto regenerado del balance del condensador fue 0,032191 J; el del DC/DC, 4,55e-13 J; el de la identidad puntual 1RC, 4,55e-13 W. El residuo DC/DC es una identidad algebraica y no sustituye un ensayo físico independiente. El archivo [`comparacion.csv`](../outputs/validation/cross_pr55_pr56/comparacion.csv) contiene valores anteriores, corregidos y diferencias por escenario y métrica. La prueba verifica el signo, el límite de potencia heredado por SoH, límites de corriente del bus y de unidad, SoC, potencia del convertidor y anti-windup; no prueba experimentalmente protecciones BMS.

## Procedimiento reproducible

Desde la raíz de la rama de integración, en Linux con Python 3.12:

```bash
python -m venv .venv-cross
. .venv-cross/bin/activate
python -m pip install -r .github/requirements-pr54.txt
mkdir -p work/cross_validation
python -m pytest -q src/validation/test_microgrid_bess_dcdc.py src/validation/test_dc_dc_adapter.py src/validation/test_vsg_50hz_and_bess_discharge.py scripts/tests/test_ieee_europe_lv_906_interface.py scripts/tests/test_ieee_europe_lv_906_study.py src/validation/test_microgrid_bess_pi_connection.py src/validation/test_microgrid_controller_state_mapping.py src/validation/test_audit_post_pr54_sustained_charge.py
python scripts/cross_validation_obj2/limit_matrix.py
python src/validation/validate_obj1_regression.py
```

El último comando escribe resultados de validación habituales bajo `outputs/validation`; usar un checkout limpio si se desea conservar las salidas versionadas. Para los 13 casos ejecutar una vez por etiqueta, con resultados independientes y atómicos:

```bash
for caso in step40_dcdc_soc0p60_eta0p95 step40_dcdc_soc0p12_below340v step40_dcdc_soc0p88_above340v step40_dcdc_soh1p00 step40_dcdc_soh0p70 step40_dcdc_soh0p55 step40_dcdc_eta1p00 step40_dcdc_eta0p90 step40_dcdc_bess_disabled irrad_drop_dcdc_eta0p95 irrad_drop_dcdc_eta0p90 irrad_drop_dcdc_pmax1200w irrad_drop_dcdc_bess_disabled; do
  python scripts/cross_validation_obj2/run_case.py "$caso" || break
done
for caso in vsg_50_40_0 vsg_60_40_0 vsg_50_20_1 vsg_60_20_1 vsg_50_40_1 vsg_60_40_1; do
  python scripts/cross_validation_obj2/run_case.py "$caso" || break
done
python scripts/cross_validation_obj2/compare.py
```

Los resultados individuales se guardan en `work/cross_validation`. `compare.py` lee los JSON pre-parche versionados y escribe la comparación y su resumen; no declara completa una campaña parcial. Para reconstruir la regresión GFM de cuatro escenarios ejecutar, también por separado:

```bash
for caso in STEADY_SPEC STEP_20_SPEC STEP_40_SPEC STEP_20_BESS_PI_SPEC; do
  python scripts/cross_validation_obj2/run_gfm.py "$caso" || break
done
python scripts/cross_validation_obj2/aggregate_gfm.py
```

El runner del proyecto `python src/validation/validate_gfm_integrated_system.py` realiza la misma campaña de forma monolítica. Las pruebas de JSON versionados verifican artefactos, no regeneran las campañas. La validación sostenida y la matriz de 54 casos no se incluyen en el workflow CI actual; deben añadirse a una campaña automatizada antes de considerar reproducida esta evidencia en GitHub Actions. La auditoría de convergencia de PR 55 dispone de niveles L3/L4 para trabajo posterior; no se afirma que se hayan ejecutado aquí.
