# Experimento Python → Numba → Rust: kernel fotovoltaico

## Límites y procedencia

Rama independiente: experiment/python-rust-perf-20261118. Base inmutable:
PR #57, SHA 740a704f60976427d75c2cbc3f9be3406afdbe74.
Este experimento agrega solo código aislado para perfilado, pruebas
numéricas y medición. No altera src/, las ecuaciones, los estados, las
campañas oficiales ni sus resultados. No equivale a validación física.

El candidato es la función PVArraySingleDiode.ipv_from_vpv de src/pv_model.py,
que resuelve la corriente FV con Newton. La implementación Python se mantiene
como referencia; Numba y Rust son traducciones escalares. SciPy continúa
integrando la ODE global sin modificaciones.

## Dos fases y entornos

La fase profile usa .github/requirements-pr54.txt, los paquetes versionados
en la referencia PR #57. Ejecuta cProfile sobre una simulación GFM de 12
estados durante 0,05 s con RK45, max_step=5e-5, rtol=1e-6, atol=1e-8.

La fase compare corre después de profile y usa NumPy 2.4.2 + Numba 0.65.1,
pues Numba 0.65.1 requiere NumPy < 2.5. SciPy y las demás dependencias
proceden del archivo de la referencia. Todas las aceleraciones comparan
las tres alternativas en el mismo entorno, nunca tiempos entre entornos.
Por tanto, no se extrapolan a la configuración exacta del PR #57.

En compare se ensayan 60 combinaciones de voltaje, irradiancia y temperatura,
con error absoluto de corriente <= 1e-9 A. Después se comparan las trayectorias
de 12 estados usando solve_ivp y la misma malla temporal, y se exige
np.allclose(rtol=2e-9, atol=2e-7). Se registran diferencias máximas
de todos los estados, Vdc y frecuencia. Estas pruebas no reemplazan
las campañas científicas ni las 50 pruebas y 29 subpruebas del PR #57.

Los microbenchmarks usan 1000 entradas repetidas siete veces, tiempos
medianos por evaluación y la sobrecarga de llamadas triviales
Python/Numba/PyO3. La simulación integrada se repite tres veces.
cProfile es diagnóstico y no se usa para calcular aceleraciones.

## Ejecución reproducible

En GitHub Actions, publicar cambios en la rama experimental desencadena
.github/workflows/perf-python-rust.yml. Los artefactos son
perf-python-reference y perf-python-numba-rust.

En dos entornos virtuales independientes con Python 3.12 se ejecuta:

Fase 1:
    python -m pip install -r .github/requirements-pr54.txt
    python scripts/perf_python_rust/benchmark_pv.py --profile-only

Fase 2:
    python -m pip install -r .github/requirements-pr54.txt
    python -m pip install numpy==2.4.2 numba==0.65.1 maturin==1.9.6
    maturin build --release --manifest-path scripts/perf_python_rust/rust_pv/Cargo.toml --out dist
    python -m pip install dist/*.whl
    python scripts/perf_python_rust/benchmark_pv.py --compare

La instalación del wheel en PowerShell requiere especificar su ruta en Windows.
No regenerar ni sobrescribir outputs/validation/ durante este ensayo.

## Criterio de decisión

Migrar el kernel FV es justificable solo si conserva precisión, produce
mejora end-to-end en escenarios representativos, tiene sobrecarga pequeña
y aporta valor incremental frente a Numba. Mejoras únicamente en el
microbenchmark no justifican introducir Rust. Antes de un cambio funcional
se necesitan campañas más largas con 15/16 estados y regresiones PR #57.

## Estado

Pendiente de corroborar resultados ejecutados. No se afirma aceleración
comprobada sin artefactos de un runner o ejecución local reproducible.
