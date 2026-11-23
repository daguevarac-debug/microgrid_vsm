# BAT26-32 — prototipo aislado de contrato BLAST / capacidad

## Alcance y ejecución

El prototipo es de investigación: lee la instancia real de BLAST y crea un `CapacitySnapshot` existente, sin actualizar BLAST, la microrred ni su solver. `ResearchContract` exige aceptación explícita de la hipótesis de transferencia relativa, fija q0 al crear el caso, conserva una referencia a la misma instancia y verifica que los historiales anteriores no cambien, que q y qNew respeten la identidad de la clase, y que capacidad no aumente, EFC y tiempo no retrocedan. La vista y `CapacitySnapshot` son inmutables. Se rechazan incoherencias; no se recorta retención. La comprobación del historial es en memoria, no un mecanismo de persistencia ni un sistema de seguridad contra alteraciones deliberadas.

```powershell
& "$env:LOCALAPPDATA\microgrid_blast_probe_312\Scripts\python.exe" -B outputs/analysis/blast_contract_prototype/run_demo.py
& "$env:LOCALAPPDATA\microgrid_blast_probe_312\Scripts\python.exe" -B -m unittest discover -s outputs/analysis/blast_contract_prototype -p 'test_*.py' -v
```

Ejecutado en Python 3.12.10, BLAST-Lite 1.1.0, NumPy 1.26.4. La demostración verifica los SHA-256 de clase `258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844` y base `1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f`, comparadas anteriormente con el commit oficial `b093495b47dc40dd96dba865d91f553619501e94`. Las seis pruebas pasan. `results.json` conserva cifras y entorno. No se modifica la instalación BLAST ni `aging_capacity.py`.

Primero se elaboró [ERROR_BUDGET.md](ERROR_BUDGET.md), que separa error de discretización observado, incertidumbre física y de transferencia. No hay criterio numérico de aceptación ni declaración de convergencia. El CSV de refinamiento anterior es la fuente de las diferencias; 32→64 ventanas varía retención en 9.9368e-5 reposo, 4.9940e-6 ciclo y 8.3581e-6 rampa. Para Q inicial de 44.1 Ah las diferencias son 0.0043821, 0.0002202 y 0.0003686 Ah; relativas a la pérdida acumulada estimada de 64 ventanas son 0.523 %, 0.370 % y 0.579 %, respectivamente. La sensibilidad no es una cota de error.

## Vista y ejemplo con historial previo

El experimento usa 15 días sintéticos en reposo a SoC 1 y 25 °C, después un ciclo 1→0→1 en dos ventanas de una hora y a 25 °C. El historial previo no representa una historia medida del BESS de tesis o de Braco. La selección 1C está referida al SoC y capacidad disponibles al inicio del ciclo; el modelo usa su propio cálculo de EFC con q previo. Todo es verificación de software.

| Punto | q | qNew | Pérdida calendario | Pérdida cíclica | EFC acumulado | r=q/q0 |
|---|---:|---:|---:|---:|---:|---:|
| Inicio del caso tras reposo | 0.9821226884 | 0.6874858819 | 0.0178773116 | 0 | 0 | 1 |
| Fin de descarga | 0.9820743503 | 0.6874520452 | 0.0178904859 | 0.0000351638 | 0.4910613442 | 0.9999507820 |
| Fin de carga | 0.9820232122 | 0.6874162485 | 0.0179036490 | 0.0000731388 | 0.9820985194 | 0.9998987131 |

La capacidad hipotética de tesis es 44.1 → 44.09553325 Ah y SoH frente a 66 Ah 0.66818182 → 0.66811414. Para Braco es 43.5 → 43.49559402 Ah y SoH 0.65909091 → 0.65902415. Son aplicaciones matemáticas de la misma retención, no resultados de capacidad medidos ni salidas originales directas de BLAST. El historial previo no se vuelve a descontar: `Q_eff=Q_init*(q/q0)`. Tampoco se vuelve a multiplicar por 0.7; `qNew` se conserva solo como salida original. El código no ofrece una opción para incluir degradación lineal adicional, pero no puede impedir que un consumidor externo la aplique: antes de integración se requiere exclusión explícita y prueba integral de esa ruta.

Las referencias se mantienen separadas: `cap=66 Ah`, `cap_2ndLife=46 Ah`, `qNew(0)*66=46.2 Ah`, Q inicial tesis=44.1 Ah y Q inicial Braco=43.5 Ah. La diferencia 0.2 Ah entre dos referencias originales se registra sin reconciliar; el valor `blast_initial_qnew_ah` alude al inicio original de BLAST, no al inicio posterior del caso. BLAST `qNew` y el `soh` del escenario tienen referencias y estado inicial distintos.

## Frontera de capacidad y posibles políticas

La demostración compara el estado de capacidad inicial y final del ejemplo como una frontera algebraica ilustrativa; no trata el ciclo como evento instantáneo. En Q inicial 44.1 Ah y SoC 0.5: conservar SoC da SoC 0.5 y `SoC*Q` 22.05 → 22.04776662 Ah; conservar `SoC*Q` da SoC 0.5000506486 y conserva 22.05 Ah. La primera política deja continuo el estado fraccional pero cambia esa carga algebraica; la segunda mantiene el producto pero cambia instantáneamente la coordenada SoC y puede afectar la continuidad de OCV, tensión y límites. No demuestra que carga accesible electroquímica se conserve.

Con SoC previo 0.9, la segunda política produce 0.9000911675, fuera del límite 0.9, mientras la primera permanece en 0.9. El prototipo reporta el incumplimiento; no recorta ni despacha una reacción física. Si se rebasea, el salto es un evento de coordenadas: cerrar la ventana en el SoC antiguo y comenzar la siguiente en el nuevo, sin convertir el salto en un segmento de corriente ni en EFC. Las pruebas muestran que introducir ese salto en `_extract_stressors` produce EFC falso, y que una lectura repetida no cambia estados/EFC. No hay salidas de corriente o energía en la vista ni se calculan en la frontera; esto prueba que **este prototipo aislado** no las genera, no que una futura integración no lo haga.

## Separación temporal y señales 2p

En una futura arquitectura el solver global integra conjuntamente las dinámicas rápidas del VSG, planta, BESS y, si aplica, PI, con capacidad congelada por intervalo rápido. El procesamiento lento recibe perfiles de un intervalo terminado, actualiza BLAST una vez por la partición elegida y produce una vista para una siguiente ventana. No se integra BLAST con un segundo solver ni se invoca dentro de la derivada. La frecuencia de actualización y tolerancia deben justificarse por los presupuestos de error, duración y señales disponibles; no se seleccionan aquí.

El perfil requeriría tiempos monótonos en segundos y alineados, SoC fraccional de los grupos 2p, temperatura **de celda** en °C y corriente de grupo 2p en A con signo positivo para descarga, además de procedencia/escala de cada señal. Para generar o verificar SoC desde corriente se necesitan Qeff, condiciones iniciales y regla de frontera; para temperatura, medición o modelo térmico justificado. La topología serie/paralelo, conversiones y pérdidas del DC/DC deben establecerse antes de transformar corriente o potencia de bus en corriente 2p: no se interpreta directamente `i_bess` de bus como corriente de celda. La clase BLAST recibe tiempo, SoC y temperatura, no la corriente como argumento; la corriente de grupo se exige aquí para trazabilidad y contraste futuro, no se usa para recalcular silenciosamente el perfil ni forzar el EFC de BLAST.

`validate_physical_profile` rechaza datos ausentes, escalas/unidades declaradas incorrectas, signo no declarado, temperatura ambiente presentada como de celda y corriente identificada como de bus. Estas etiquetas son declaraciones del llamador: el prototipo no puede verificar su procedencia real ni detectar toda cifra mal rotulada, ni comprueba balance I–SoC, muestreo térmico, equivalencia eléctrica, calidad de sensores o límites experimentales. Por ejemplo, una temperatura erróneamente rotulada como °C puede pasar el filtro de finitud; es un bloqueo de datos, no un valor por defecto.

## Resultado y decisiones pendientes

Las seis pruebas verifican retención inicial unitaria, referencias/unidades, inmutabilidad, historial previo y ausencia de doble descuento en la fórmula, monotonía observada con dos ventanas, conservación del historial, EFC ficticio por rebase, límites y rechazo de señales físicas ausentes o mal declaradas. Son casos controlados, no una prueba universal de monotonía, conservación energética, validación física ni prueba de todo el código de integración.

**No existen condiciones suficientes para integrar de manera controlada con el BESS.** Siguen pendientes: justificación y validación de transferencia al estado 44.1/43.5 Ah; historia de cada grupo; temperatura y corriente 2p trazables; decisión de frontera, continuidad y tratamiento de límites; criterio de error y tamaño de ventana/muestreo; exclusión verificable del envejecimiento lineal simultáneo; pruebas de acoplamiento sin saltos artificiales y regresiones de Objetivo 1/GFM. El próximo paso es definir esas decisiones y un protocolo de prueba aislado con datos y tolerancias fundamentados. BAT26-32 permanece abierta.
