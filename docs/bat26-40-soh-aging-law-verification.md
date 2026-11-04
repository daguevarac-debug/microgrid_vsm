# BAT26-40 — Verificación de la ley de SoH según uso

**Dictamen:** la ruta de software `blast` aplica la retención `q(t)/q(t0)` del modelo original BLAST-Lite 1.1.0 a la capacidad inicial del caso, y deja `linear` como ruta excluyente. Las pruebas dirigidas pasan. BAT26-40 puede considerarse verificada en alcance de implementación de software; quedan pendientes validación experimental, transferencia de coeficientes y de estado inicial, y validez física para perfiles de la tesis. Esta auditoría no cambia código ni parámetros.

## Fuente primaria y ecuaciones originales

Se inspeccionó directamente la clase instalada `Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery` y su clase base en el entorno Python 3.12.10 con BLAST-Lite 1.1.0. Los SHA-256 observados fueron, respectivamente, `258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844` y `1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f`; coinciden con los hashes fijados por `blast_worker.py` y documentados en BAT26-39. Los dos archivos también se cotejaron con el commit de BLAST-Lite [`b093495b47dc40dd96dba865d91f553619501e94`](https://github.com/NatLabRockies/BLAST-Lite/tree/b093495b47dc40dd96dba865d91f553619501e94). La clase apunta a Braco et al. para envejecimiento calendario ([DOI 10.1109/EEEIC/ICPSEUROPE54979.2022.9854784](https://doi.org/10.1109/EEEIC/ICPSEUROPE54979.2022.9854784)) y cíclico ([DOI 10.1016/j.est.2020.101695](https://doi.org/10.1016/j.est.2020.101695)). La versión y hashes verifican estos fuentes, no todo el paquete ni la reproducción integral de los experimentos.

Estados iniciales del modelo: `qLoss_t=qLoss_EFC=0`, `q=q_t= q_EFC=1`, `qNew=0.7`, tiempo acumulado y EFC cero. En cada actualización:

```text
k_cal(T,SOC) = A_cal exp(B_cal/T_K) exp(C_cal·SOC/T_K)
ΔqLoss_t    = degradation_scalar · update_power(qLoss_t, Δt_days, k_cal, p_cal)
ΔqLoss_EFC  = degradation_scalar · update_power(qLoss_EFC, ΔEFC, A_cyc, p_cyc)
q_t         = 1 − qLoss_t
q_EFC       = 1 − qLoss_EFC
q           = 1 − qLoss_t − qLoss_EFC
qNew        = 0.7·q
```

La función original `update_power(y0, Δx, k, p)` usa `k·Δx^p` si `y0=0`; si el estado ya es positivo, aplica el incremento Euler `k·p·(y0/k)^((p−1)/p)·Δx`. Por tanto, la ley acumulada no es una actualización exacta independiente de la partición; el tamaño de ventana afecta el resultado.

| Componente / coeficiente | Valor original | Unidades e interpretación | Dependencia y condición de aplicación |
|---|---:|---|---|
| `A_cal` (`qcal_A`) | `3.25e8` | `day^-0.464`, con pérdida relativa `qLoss` adimensional | Prefactor calendario empírico |
| `B_cal` (`qcal_B`) | `−7.58e3` | K; argumento exponencial `B/T_K` adimensional | Temperatura absoluta de celda, Arrhenius |
| `C_cal` (`qcal_C`) | `162` | K si SoC es fracción adimensional | Interacción SoC-temperatura: `exp(C·SOC/T_K)` |
| `p_cal` (`qcal_p`) | `0.464` | adimensional | Exponente de tiempo calendario en días |
| `A_cyc` (`qcyc_A`) | `7.58e−5` | `EFC^-1.08` para pérdida relativa adimensional | Coeficiente de pérdida cíclica según EFC interno |
| `p_cyc` (`qcyc_p`) | `1.08` | adimensional | Exponente de uso cíclico |
| `degradation_scalar` | `1` por defecto | adimensional | Escala todas las variaciones de estado |

Las unidades de los prefactores se deducen de las ecuaciones del código para que las pérdidas sean adimensionales. La clase no declara unidades explícitas para esos parámetros.

La clase Nissan 2nd-life declara datos calendario con SoC y temperatura ampliamente variados; su nota del modelo dice que la tasa depende de tiempo, temperatura y SoC medio. Para ciclado declara **una única condición experimental**: 25 °C, 100 % DoD, 1C carga y 1C descarga. Su rango experimental declarado para ciclado es T=20–30 °C, DoD=0.8–1, SoC=0–1 y tasas máximas de carga/descarga 1C. El propio código advierte que la predicción cíclica solo es válida cerca de 25 °C, DoD 100 % y 1C, y que el ciclado depende solo de throughput por falta de datos para otras dependencias. `update_rates` calcula `k_cal` de T/SoC promediados en tiempo; no usa `dod`, `Ua` o `Crate`. `update_states` usa `Δt_days` y `ΔEFC`. La clase base calcula `ΔEFC=0.5·Σ|ΔSoC|·q_previo`. Temperatura de entrada debe ser Celsius; el código la convierte a Kelvin para la ley calendario. El worker actual valida amplitud/continuidad de tiempo, SoC en [0,1], temperatura física finita y unidades declaradas.

Las referencias siguen diferenciadas: `cap=66 Ah`; `cap_2ndLife=46 Ah`; `qNew(0)·66=46.2 Ah`; `Q_case=44.1 Ah` (tesis); `Q_case=43.5 Ah` (experimento Braco). El código BLAST no reconcilia 46 con 46.2 Ah; los casos de 44.1 y 43.5 Ah no son datos de calibración de esa instancia.

## Trazabilidad de implementación

| Requisito | Evidencia local | Resultado de auditoría |
|---|---|---|
| Preservar estados originales BLAST | `blast_worker.py`: una instancia persistente; copia previa para revertir ventana fallida; conserva estados/salidas/historial de la clase original | Conforme en memoria; no hay checkpoint durable |
| SoH por retención desde ancla de caso | `blast_lite_adapter.py`: `CapacitySnapshot(66, Q_case, q/q0)`; worker solo entrega `q`, `qNew`, `qLoss_t`, `qLoss_EFC`, EFC, tiempo y ventanas | `Q_eff=Q_case·q/q0`; `SoH=Q_eff/66`; no aplica `qNew` ni otro `0.7` |
| Pérdidas calendario y cíclica | Salidas `qLoss_t` y `qLoss_EFC` de la clase original; `q=1−qLoss_t−qLoss_EFC` | Sin una segunda ley BLAST ni coeficientes reestimados |
| Ancla e historial | `q0` se fija al iniciar el worker o con `anchor_case()`; anclar no reconstruye ni reinicia estados/EFC | Retención inicial del caso es 1; historia previa permanece en BLAST |
| Exclusividad | `linear` usa la ley original del BESS con `z_deg`; `blast` usa snapshots fijos por ventana y `z_deg` no degrada capacidad | No hay degradación simultánea en la ruta integrada probada |
| Datos de perfil | El adaptador requiere explícitamente clase de perfil `synthetic`, corriente `synthetic_2p_group`, temperatura `synthetic_cell`, signos y unidades | Perfil operativo sin procedencia acreditada continúa rechazado; las etiquetas no validan mediciones |
| Rangos/unidades/signos | Validaciones del adaptador/worker para señales finitas/alineadas, tiempo creciente, SoC, T, signos y unidades | Contrato sintético comprobado; `current_2p_a` se exige con fin documental, pero BLAST calcula EFC de SoC, no de esa corriente |

La adaptación es una transferencia hipotética de retención relativa. Puede conservar el historial de forma coherente en el objeto BLAST y evitar recontar pérdida previa al escalar una capacidad de caso, pero no convierte ese historial ni los coeficientes en una calibración de la batería de 44.1 o 43.5 Ah. Tampoco basta tener una muestra original “segunda vida”: se requieren condiciones iniciales, construcción de grupo, historial y perfiles comparables.

## Sensibilidad numérica y limitaciones

El experimento reproducible `outputs/analysis/blast_temporal_convergence/` aplicó mismas 121 muestras y particiones anidadas de 1 a 64 ventanas, manteniendo una instancia/historial por trayectoria. En reposo 30 días, SoC=0.5 y 25 °C, `q` fue 0.9812071334 (1 ventana), 0.9800539828 (2) y 0.9809930570 (64); la secuencia no es monótona. En el ciclo sintético SoC 1→0→1, 25 °C, 1C, `q` fue 0.9986848302, 0.9986100377 y 0.9986499330. La rampa térmica sintética dio 0.9986465880, 0.9983146430 y 0.9985561090. Estos valores muestran sensibilidad a la partición, no fijan una tolerancia admisible ni establecen convergencia; 64 ventanas es una referencia finita. La causa incluye la actualización incremental Euler de potencias, el EFC reescalado por `q` al inicio de cada ventana y el promedio temporal no lineal de T/SoC.

Riesgos científicos no cubiertos por pruebas de software:

- Ciclado fuera de 25 °C, 100 % DoD y 1C carece de apoyo directo de la clase para predicción cuantitativa, aunque se declare rango de extrapolación esperado.
- No se acredita temperatura real de celda, corriente del grupo 2p, topología/paralelo, historial ni procedencia de perfiles operativos de la tesis.
- La relación de SoC usada por BLAST para EFC no consume la señal de corriente del adaptador; por tanto, dar una corriente sintética no valida el perfil eléctrico.
- La adaptación a 44.1/43.5 Ah, y la correspondencia de esos casos con el estado original `q0`, no están validadas experimentalmente.
- BLAST aquí solo representa envejecimiento de capacidad; no identifica la ley ECM, energía disponible, transferencia batería–DC/DC–bus ni degradación de resistencia.
- Integridad/historial es solo en memoria del proceso; no existe persistencia/recuperación probada tras reinicio.

## Verificaciones ejecutadas

Se usó el Python principal del proyecto para las pruebas y el Python 3.12.10 fijado por BAT26-39 para el worker BLAST:

```powershell
$env:BLAST_LITE_PYTHON = Join-Path $env:LOCALAPPDATA 'microgrid_blast_probe_312\Scripts\python.exe'
.venv\Scripts\python.exe -B -m unittest discover -s src\validation -p test_blast_lite_adapter.py -v
.venv\Scripts\python.exe -B -m unittest discover -s src\validation -p test_aging_capacity_contract.py -v
.venv\Scripts\python.exe -B -m unittest discover -s src\validation -p test_capacity_snapshot_integration.py -v
```

Resultados de esta revisión: **10/10**, **11/11** y **6/6 PASS**, respectivamente (27 en total). Cubren integración con BLAST real, retención inicial y ancla, rechazo de entradas/SoC inválidos, historial sintético, capacidad/SoH del snapshot, inmutabilidad, exclusividad lineal/BLAST y fijación de capacidad por ventana. Son pruebas de implementación y coherencia algebraica, no de validez experimental, convergencia ni energía del sistema.

BAT26-39 aportó comparación de default/`linear` contra commit base con diferencia máxima cero en los casos dirigidos, Objetivo 1 y BESS paso 2 PASS en copias temporales, más evidencia previa de invariantes/PI. Se conserva su `REVIEW` para GFM +40 %/Vdc; esa campaña pesada no se repitió aquí. La advertencia para llamadores de snapshot se mantiene: deben seleccionar explícitamente `aging_mode='blast'` y `blast_profile_kind='synthetic'` en la microrred.

**Conclusión BAT26-40:** criterio de software (unidades/validaciones de interfaz, referencias rastreables, retención, historial y exclusividad) satisfecho en los casos cubiertos. Para uso científico, BLAST sigue como modelo seleccionado metodológicamente, transferido solo como hipótesis de escenario; están pendientes transferencia física, datos operativos acreditados, sensibilidad temporal aceptable definida por aplicación, checkpoint durable y validación energética/experimental. Esta documentación no marca automáticamente BAT26-40 como completada.
