# Baseline de Tesis: Microrred Fotovoltaica Acoplada al IEEE 33

## Descripcion general
Este repositorio implementa un **baseline de tesis** para una microrred fotovoltaica con simulacion dinamica local y acople secuencial **one-way** al sistema de distribucion IEEE de 33 nodos.

El objetivo del baseline es mantener una base tecnicamente consistente, trazable y extensible para trabajo de investigacion posterior.

## Alcance actual (implementado)
- Modelo del arreglo fotovoltaico (PV array).
- Dinamica del bus DC (DC-link).
- Modelo del filtro LCL.
- Fuente inversora y control baseline tipo grid-following con PI.
- Simulacion dinamica local del sistema de microrred.
- Acople secuencial one-way al sistema IEEE 33 en el PCC.

## Funcionalidades no implementadas aun
- Integracion de BESS.
- Modelo operativo de bateria de segunda vida.
- Control grid-forming completo.
- Contribucion final de inercia virtual activa.

## Estructura del repositorio (actual)
- `src/config.py`: constantes y parametros base del modelo.
- `src/microgrid.py`: modelo compuesto de la microrred (`Microgrid`) y dinamica principal.
- `src/controllers/`: logica de control (`base.py`, `grid_following.py`, `grid_forming_scaffold.py`).
- `src/pv_model.py`, `src/dclink.py`, `src/lcl_filter.py`, `src/inverter_source.py`: componentes fisicos del baseline.
- `src/ieee33_base.py`: construccion de la red IEEE 33.
- `src/ieee33_coupling.py`: acople secuencial one-way y clase `IEEE33MicrogridBaseline`.
- `src/ieee33_reporting.py`: reporte de resultados del acople IEEE 33.
- `src/ieee33_plots.py`: generacion y guardado de figuras del flujo IEEE 33.
- `src/main.py`: punto de entrada de simulacion dinamica local.
- `src/ieee33_main.py`: punto de entrada del estudio secuencial IEEE 33 + microrred.
- `outputs/`: carpeta de salida para figuras del flujo IEEE 33.

## Componentes principales del modelo
- **PV array**: generacion fotovoltaica basada en parametros del arreglo.
- **DC-link**: evolucion del voltaje de bus DC segun balance energetico.
- **Filtro LCL**: dinamica electrica trifasica entre inversor y PCC local.
- **Inversor**: sintesis de tension trifasica con limites de modulacion.
- **Control baseline**: esquema grid-following PI para regular operacion en el escenario base.

## Puntos de entrada
- Simulacion dinamica local:

```bash
python src/main.py
```

- Estudio de acople secuencial con IEEE 33:

```bash
python src/ieee33_main.py
```

## Instrucciones basicas de ejecucion
1. Crear y activar un entorno virtual de Python.
2. Instalar dependencias requeridas segun modulos usados en `src/` (por ejemplo `numpy`, `scipy`, `matplotlib`, `pandas`, `pandapower`).
3. Ejecutar el punto de entrada correspondiente.

## Notas de ingenieria
- Este repositorio prioriza **coherencia fisica** y **trazabilidad cientifica** del baseline.
- La arquitectura separa fisica, control, simulacion, plotting y reporte para facilitar analisis de tesis.
- El baseline esta disenado para extenderse en etapas futuras sin reescritura agresiva.

## Advertencias sobre el alcance de tesis
- Este baseline **no** debe interpretarse como implementacion grid-forming completa.
- Este baseline **no** incluye BESS operativo.
- No se debe presentar codigo scaffold o planificado como contribucion final implementada.
