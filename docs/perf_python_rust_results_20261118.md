# Evaluación experimental de migración parcial Python → Rust — 18/11/2026

## Procedencia, ámbito y protección científica

La referencia es el PR #57, commit 740a704f60976427d75c2cbc3f9be3406afdbe74.
La rama exclusivamente experimental es experiment/python-rust-perf-20261118.
Las mediciones finales se ejecutaron desde el commit
22876102d32785fba029990fa9dee42aa681ed10, sin cambiar archivos
src/, ecuaciones, parámetros, estados, los artefactos científicos ni el PR #57.
La prueba sustituye una función por instancia del modelo únicamente en el
proceso experimental; el integrador global sigue siendo SciPy solve_ivp.

GitHub Actions: https://github.com/daguevarac-debug/microgrid_vsm/actions/runs/44373942991
Artefacto comparativo: https://github.com/daguevarac-debug/microgrid_vsm/actions/runs/44373942991/artifacts/14459368846
Ejecución comparativa previa aprobada, para evaluar variabilidad:
https://github.com/daguevarac-debug/microgrid_vsm/actions/runs/44373244901

## Perfil de referencia Python, antes de la comparación

Python 3.12.16, NumPy 2.5.5 y SciPy 1.18.1 (dependencias de PR #57;
diferencia menor de versión de intérprete frente al informe original 3.12.14).
Simulación GFM de 12 estados durante 0,05 s con RK45, max_step=5e-5,
rtol=1e-6, atol=1e-8; 10.688 evaluaciones de derivadas.

cProfile acumulativo: system_dynamics 2,421374 s; _compute_step_control
2,202882 s; GFMController.compute_control 1,167057 s; ipv_from_vpv
0,445211 s; _load_at_time 0,346970 s. Los tiempos de las funciones
anidadas se solapan y no deben sumarse. La participación aparente
de la corriente FV es aproximadamente 18,4 % del acumulado de RHS,
pero cProfile altera el costo relativo; esta fracción no equivale a
una descomposición exacta de tiempo wall-clock.

## Entorno comparativo y reproducibilidad

Las tres implementaciones se midieron dentro de un único runner Linux
con Python 3.12.16, SciPy 1.18.1, NumPy 2.4.2 y Numba 0.65.1;
Maturin 1.9.6, PyO3 0.23.5 y rustc 1.100.0. La incompatibilidad de
Numba 0.65.1 con NumPy 2.5.5 obligó a emplear 2.4.2 para esta fase.
Nunca se calcularon aceleraciones entre el entorno del perfil inicial
y el entorno comparativo.

La extensión Rust fue construida en modo release mediante Maturin.
El mismo conjunto de 60 condiciones FV se comprobó antes del benchmark:
errores máximos observados iguales a 0 A para Numba y Rust. La tolerancia
de aceptación era 1e-9 A. Se ensayaron Vpv = 0, 220, 340, 450, 550 V;
irradiancia = 0, 100, 600, 1000 W/m2 y temperatura = 0, 25, 45 C.

## Microbenchmark FV (medianas, siete repeticiones; ejecución final)

| Variante | Tiempo por evaluación | Aceleración respecto a Python |
|---|---:|---:|
| Python original | 14,518 µs | 1,00x |
| Numba | 0,385 µs | 37,71x |
| Rust / PyO3 | 0,132 µs | 109,62x |

Las cifras incluyen la llamada desde el bucle Python, aunque no incluyen
la conversión de funciones del modelo durante solve_ivp. Una función trivial
medida desde Python registró aproximadamente 32 ns (Python), 57 ns (Numba)
y 46 ns (Rust) por llamada. Estas mediciones triviales son indicativas,
no una estimación completa del costo de transferencia de arreglos. El
benchmark integrado sí incorpora el adaptador experimental y sus llamadas.

## Simulaciones completas del horizonte de benchmark, sin alterar SciPy

Ambos casos utilizan una ventana reducida de 0,05 s, 11 muestras
de salida, tres repeticiones por implementación y el mismo integrador.
No reproducen las campañas físicas ni los horizontes oficiales de 6,5 s.

| Escenario | Python (s) | Numba (s) | Rust (s) | Numba vs Python | Rust vs Python |
|---|---:|---:|---:|---:|---:|
| GFM, 12 estados | 1,047695 | 0,887599 | 0,879114 | 1,1804x | 1,1918x |
| GFM + BESS + DC/DC, 16 estados | 2,169550 | 2,008382 | 1,992230 | 1,0802x | 1,0890x |

GFM 12 estados: 10.688 evaluaciones de RHS. GFM+BESS+DC/DC 16 estados:
10.988 evaluaciones de RHS. En ambos casos NumPy, Numba y Rust dieron
máxima diferencia reportada de 0.0 para todas las trayectorias de estado,
Vdc y frecuencia; en 16 estados también para SoC. Se exigió
np.allclose(rtol=2e-9, atol=2e-7). La concordancia es numérica y local
al dominio y las muestras examinadas; no prueba equivalencia universal.

En el caso de 16 estados Rust redujo el tiempo frente a Python alrededor
de 8,2 %, Numba aproximadamente 7,4 %. La diferencia incremental
Rust frente a Numba fue 0,01615 s, cerca de 0,8 % del tiempo Numba.
La dispersión entre las tres ejecuciones Rust (1,987, 2,057 y 1,992 s)
supera esa diferencia, de modo que no se puede afirmar una ventaja
integrada reproducible estadísticamente frente a Numba. El benchmark
de 12 estados de una corrida previa mostró aceleraciones mayores,
lo que refuerza la cautela sobre variaciones de runner y horizonte.

## Decisión de ingeniería

El primer candidato de compilación es exclusivamente el kernel FV
PVArraySingleDiode.ipv_from_vpv, no el VSG completo ni el DC/DC.
Sin embargo, **no se recomienda migrarlo todavía a Rust en la rama
científica**: Numba captura casi toda la mejora integrada demostrada,
mientras que el margen incremental Rust en el caso 16 estados es
menor que la variabilidad observada. Rust introduce herramientas de
compilación, wheels, interoperabilidad y riesgos de portabilidad
adicionales. No hay evidencia suficiente de que ese costo se compense
en campañas largas de 15/16 estados u optimizaciones múltiples.

La siguiente verificación razonable es perfilar directamente el RHS
de 16 estados, comprobar la política de actualización de capacidades
BLAST sin alterar su worker original y evaluar series de escenarios
representativas. Antes de adoptar Numba o Rust en producción,
repetir las pruebas del PR #57 y los ensayos completos con sus
restricciones de SoC/SoH, signos, potencias y balances energéticos.
Ni este documento ni el benchmark modifican la referencia científica.

## Riesgos y limitaciones de reproducibilidad

Los experimentos usan runners compartidos y solo tres repeticiones
integradas; no existe análisis de intervalos de confianza.
El perfil inicial y la comparación difieren en versión de NumPy;
las aceleraciones solo se calculan dentro del entorno comparativo.
El workflow emplea Rust stable, cuyo número exacto se registra;
para una eventual incorporación productiva se debe fijar toolchain
y Cargo.lock. La implementación Rust no replica todavía todas las
validaciones de entradas inválidas de Python y no constituye una
alternativa pública de API lista para producción.
