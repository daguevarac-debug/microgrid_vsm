# Baseline de Tesis: Microrred Fotovoltaica Acoplada al IEEE 33

## Descripción general
Este repositorio implementa un **baseline de tesis** para una microrred fotovoltaica con simulación dinámica local y acople secuencial **one-way** al sistema de distribución IEEE de 33 nodos.

El objetivo del baseline es mantener una base técnicamente consistente, trazable y extensible para trabajo de investigación posterior.

## Alcance actual (implementado)
- Modelo del arreglo fotovoltaico (PV array).
- Dinámica del bus DC (DC-link).
- Modelo del filtro LCL.
- Fuente inversora y control baseline tipo grid-following con PI.
- Simulación dinámica local del sistema de microrred.
- Acople secuencial one-way al sistema IEEE 33 en el PCC.

## Funcionalidades no implementadas aún
- Integración de BESS.
- Modelo operativo de batería de segunda vida.
- Control grid-forming completo.
- Contribución final de inercia virtual activa.

## Estructura del repositorio
- `src/config.py`: constantes y parámetros base del modelo.
- `src/models/`: composición del modelo físico y dinámica principal.
- `src/controllers/`: lógica de control (separada de la física).
- `src/networks/`: acople e integración con IEEE 33.
- `src/plots/`: funciones de visualización.
- `src/simulation/`: utilidades de simulación y reporte.
- `src/main.py`: punto de entrada principal para la simulación dinámica local.
- `src/microgrid_model.py`: wrapper de compatibilidad pública (`from microgrid_model import Microgrid`).
- `src/ieee33_microgrid.py`: wrapper/entrypoint para flujo secuencial IEEE 33 + microrred.

## Componentes principales del modelo
- **PV array**: generación fotovoltaica basada en parámetros del arreglo.
- **DC-link**: evolución del voltaje de bus DC según balance energético.
- **Filtro LCL**: dinámica eléctrica trifásica entre inversor y PCC local.
- **Inversor**: síntesis de tensión trifásica con límites de modulación.
- **Control baseline**: esquema grid-following PI para regular operación en el escenario base.

## Punto de entrada principal
El punto de entrada principal es:
- `src/main.py`

Este script ejecuta la simulación dinámica local del baseline y genera gráficas de variables relevantes.

## Instrucciones básicas de ejecución
1. Crear y activar un entorno virtual de Python.
2. Instalar dependencias requeridas (según módulos usados en `src/`, por ejemplo `numpy`, `scipy`, `matplotlib`, `pandas`, `pandapower`).
3. Ejecutar la simulación principal:

```bash
python src/main.py
```

Para ejecutar el estudio de acople secuencial con IEEE 33:

```bash
python src/ieee33_microgrid.py
```

## Notas de ingeniería
- Este repositorio prioriza **coherencia física** y **trazabilidad científica** del baseline.
- La arquitectura separa física, control, simulación, plotting y reporte para facilitar análisis de tesis.
- El baseline está diseñado para extenderse en etapas futuras sin reescritura agresiva.

## Advertencias sobre el alcance de tesis
- Este baseline **no** debe interpretarse como implementación grid-forming completa.
- Este baseline **no** incluye BESS operativo.
- No se debe presentar código scaffold o planificado como contribución final implementada.
