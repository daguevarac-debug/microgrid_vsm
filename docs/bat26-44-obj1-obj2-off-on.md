# BAT26-44 — Regresiones Obj1/Obj2 y comparación BESS OFF/ON

## Alcance y criterio de aceptación

Roma exige comparar el sistema con el almacenamiento desactivado y activado, y demostrar que las rutas de los Objetivos 1 y 2 se conservan sin modificar el VSG ni el PI. Esta tarea es una verificación de software y simulaciones sintéticas; no representa validación física del BESS de segunda vida ni del convertidor DC/DC.

El nuevo ejecutor `src/validation/run_bat26_44_regressions.py` realiza tres campañas existentes y una comparación controlada adicional. La primera campaña utiliza `validate_obj1_regression.py`, que agrupa las regresiones protegidas de LCL, BESS paso 3 y límites SoC. La segunda invoca `validate_gfm_integrated_system.py`, que incluye operación estacionaria, escalones +20 % y +40 %, así como comparación histórica de 12 estados sin BESS contra 16 estados con BESS y PI. La tercera invoca `validate_physical_invariants.py`, que comprueba invariantes DC y signos.

## Experimento OFF/ON sin confusión de arquitecturas

El contraste nuevo utiliza **dos instancias distintas** de `MicrogridWithBESSPI` construidas por `validate_dc_link_pi_scenarios.build_model(BASE_SCENARIO)`. Se conserva el mismo vector de 16 estados, planta, condiciones iniciales, recurso FV, carga nominal de 3 kW, escalón +20 %, tiempo de simulación, solver, `GFMController`, `M=80`, `D=1500` y ganancias PI existentes. La única intervención es `model.set_bess_enabled(False)` en OFF y `model.set_bess_enabled(True)` en ON. En OFF, la corriente y la potencia del BESS deben ser cero; en ON se evalúan signos y límites sin exigir una mejora de desempeño como condición de integridad.

La comparación histórica de 12 contra 16 estados se conserva separadamente como regresión de Obj2, **no** como estimador causal puro del BESS, puesto que cambia simultáneamente la arquitectura del regulador. El nuevo par 16/16 elimina esa confusión de configuración. El modelo sigue incluyendo un convertidor DC/DC idealizado.

Las señales principales son desviación máxima del bus DC respecto al evento, caída máxima de frecuencia dinámica calculada desde `omega/(2*pi)`, corriente y potencia del BESS, SoC y SoH. Se reportan las diferencias **ON menos OFF**; un signo negativo en una métrica de desviación expresa una reducción cuantitativa, sin suponer que deba ocurrir.

## Estados e interpretación

**PASS**: regresiones Obj1 e invariantes PASS, GFM sintéticamente válido, dos casos OFF/ON con solver e invariantes correctos y criterios de desempeño satisfechos. **REVIEW**: ejecución válida, sin violación de invariantes, pero al menos un criterio existente de regulación DC o frecuencia no satisfecho. **FAIL**: error de ejecución, regresión protegida incumplida, pérdida de equivalencia de configuración OFF/ON, o violación de restricciones. El escenario histórico +40 % puede mantenerse en REVIEW; **no** se reclasifica automáticamente como fallo.

Se comprueba `i_bess=0` y `p_bess_dc=0` para OFF, `p_bess_dc=Vdc*i_bess` en ambos casos, disponibilidad de corriente/potencia según SoH, límites de SoC/SoH, estado dinámico GFM `omega` y condiciones de integración. El caso ON puede funcionar en absorción de potencia y no se inventa descarga ni mejora.

## Ejecución en Codex Cloud

Trabajar sobre `feat/bat26-44-obj1-obj2-off-on-regressions`, basada en `feat/blast-aging-adapter` después del PR #39. Desde la raíz:

```bash
.venv/bin/python -B src/validation/run_bat26_44_regressions.py
```

Cada ejecución crea una carpeta nueva bajo `outputs/analysis/bat26_44_off_on/run_<UTC>/` con `summary.json`, los informes JSON de las validaciones antiguas y logs por campaña. Se registra el commit y los hashes de entrada. Los validadores existentes pueden además actualizar sus **archivos auxiliares por defecto**, por lo que se debe inspeccionar `git status` y evitar incorporarlos sin revisión; no sobrescribir manualmente registros de BAT26-36, 41 o 43.

La preparación en GitHub **no implica ejecución**. El cierre requiere leer el `summary.json`, revisar las pruebas reales, explicar numéricamente el efecto OFF/ON y documentar cualquier REVIEW. No fusionar el PR ni cerrar Roma por una mera ejecución iniciada o por el éxito nominal del entorno.

## Limitaciones científicas

Los resultados representan simulaciones de la microrred local con interfaz BESS–bus simplificada; no prueban calibración del envejecimiento, comportamiento térmico o eléctrico real del grupo 2p, robustez experimental, ni co-simulación bidireccional IEEE 33. BAT26-45, sobre envejecimiento en ciclos largos, constituye una tarea posterior y separada.
