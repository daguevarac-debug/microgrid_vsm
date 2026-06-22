# Bucket 4 — Tarea 4.2: escenario base de sintonización

## Decisión

El escenario base para la sintonización inicial de la inercia virtual `M` y el amortiguamiento `D` será un escalón positivo de carga del 20 % en operación aislada.

La definición del escenario es:

| Variable | Valor |
|---|---:|
| Potencia activa inicial | `3000 W` |
| Potencia activa final | `3600 W` |
| Incremento de carga | `20 %` |
| Instante del escalón | `0.8 s` |
| Factor de potencia | `0.95` atrasado |
| Potencia reactiva inicial | `986.052316 var` |
| Potencia reactiva final | `1183.262779 var` |
| Tipo de carga | Trifásica balanceada R-L |
| Modo de operación | Microrred AC aislada |

La carga se define mediante:

```text
p_load(t) = 3000 W,  t < 0.8 s
p_load(t) = 3600 W,  t >= 0.8 s
```

## Papel del BESS en esta tarea

El BESS no es una condición obligatoria del escenario base. La perturbación de referencia es el escalón del 20 %, independientemente de que el modelo se ejecute con o sin almacenamiento.

Para la sintonización inicial de `M` y `D` se usará como caso principal la microrred sin BESS, con el fin de aislar el efecto dinámico del controlador grid-forming/VSG. El mismo escalón con `MicrogridWithBESS` se conservará como variante comparativa para evaluar posteriormente el esfuerzo y la interacción de la batería de segunda vida.

Esta separación evita atribuir al BESS mejoras que todavía no están plenamente demostradas. En la implementación preliminar validada, la batería presentó corriente negativa durante el evento, lo que bajo la convención del repositorio significa absorción de potencia o carga, no descarga para soporte inercial.

## Evidencia de validación

El escenario ya está implementado en `src/validation/validate_islanded_operation_scenarios.py` mediante `validate_load_step_20()` y `validate_bess_vs_no_bess()`.

Resultados reproducidos antes de cerrar esta tarea:

### Caso sin BESS

- estado: `PASS`;
- `Vdc` previa al escalón: `379.309457 V`;
- `Vdc` mínima posterior: `364.760804 V`;
- caída relativa de `Vdc`: `3.835563 %`;
- señales finitas y sin crecimiento sostenido en las ventanas finales.

### Variante con BESS

- estado: `PASS`;
- `Vdc` previa al escalón: `344.801523 V`;
- `Vdc` mínima posterior: `341.690534 V`;
- caída relativa de `Vdc`: `0.902255 %`;
- corriente del BESS entre `-2.459666 A` y `0 A`;
- potencia del BESS entre `-848.386376 W` y `0 W`;
- SoC, SoH, corriente, potencia y tensión terminal dentro de los límites implementados.

Los porcentajes de caída de `Vdc` no deben compararse como prueba definitiva de superioridad del caso con BESS, porque los dos casos parten de tensiones previas diferentes y el BESS preliminar se encontraba absorbiendo potencia.

## Justificación de la selección

El escalón del 20 % se adopta como perturbación moderada porque:

1. ya está implementado y validado de forma reproducible;
2. produce una respuesta dinámica suficientemente visible para comparar combinaciones de `M` y `D`;
3. evita comenzar la sintonización con una perturbación extrema;
4. permite reservar el escalón del 40 % como prueba severa de robustez;
5. reduce el riesgo de escoger parámetros demasiado agresivos para una batería de segunda vida.

El escalón del 40 % produjo una caída de `Vdc` de `14.957581 %`, muy próxima al límite interno de validación del 15 %. Por ello se utilizará después de seleccionar los parámetros candidatos, no como condición inicial de ajuste.

## Métricas que se aplicarán

Cada combinación de parámetros deberá evaluarse con las métricas definidas en la Tarea 4.1:

- caída máxima de frecuencia `<= 0.50 Hz`;
- recuperación dentro de `60 +/- 0.10 Hz` en `<= 5.0 s`, con permanencia de `0.50 s`;
- sobreoscilación positiva del enlace DC `<= 5.0 %`;
- tensión mínima del enlace DC `>= 327.50 V`;
- registro complementario de corriente, potencia, energía intercambiada y variación de SoC del BESS.

## Uso posterior

La secuencia de trabajo será:

1. sintonizar inicialmente `M` y `D` con el escalón del 20 % sin BESS;
2. seleccionar los candidatos que cumplan las métricas de la Tarea 4.1;
3. repetir el mismo escenario con BESS-SLB para comparar esfuerzo eléctrico y respuesta;
4. verificar los candidatos finales con el escalón severo del 40 %;
5. aplicar después el mismo procedimiento a los parámetros adicionales de FOVIC, si corresponde.

## Alcance del cambio

Esta tarea documenta una decisión metodológica. No modifica ecuaciones físicas, parámetros eléctricos, convenciones de signo, orden de estados ni comportamiento del modelo base.
