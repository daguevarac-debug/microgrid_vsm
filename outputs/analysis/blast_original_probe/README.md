# BAT26-32: prueba aislada de BLAST-Lite original

Ejecutada el 3-11-2026 en Python 3.12.10. Se creó un entorno aislado nuevo porque el Python 3.12 del sistema no tenía instalado BLAST-Lite y el `.venv` del proyecto usa Python 3.14. Comando desde la raíz:

```powershell
& "$env:LOCALAPPDATA\microgrid_blast_probe_312\Scripts\python.exe" outputs/analysis/blast_original_probe/probe.py
```

Paquete PyPI BLAST-Lite 1.1.0, NumPy 1.26.4, pandas 2.2.3, SciPy 1.15.3. El archivo `requirements.txt` registra el entorno observado; la instalación inicial completa se interrumpió y se completaron las dependencias necesarias posteriormente. La ejecución de la prueba pasó sus aserciones. No equivale a validación experimental.

Se ejecutó `update_battery_state` de la clase instalada en `C:\Users\hp\AppData\Local\microgrid_blast_probe_312\Lib\site-packages\blast\models\lmo_gr_NissanLeaf66Ah_2ndLife_2020.py`. SHA-256 de clase `258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844`, base `1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f`. Los Git blobs de la clase `a6c1a8598b2dce455f31ba2c2a263662837cef24` y base `391314fc0eea57d36ace30d79184d065ad754994` coinciden con el commit oficial [b093495b47dc40dd96dba865d91f553619501e94](https://github.com/NatLabRockies/BLAST-Lite/tree/b093495b47dc40dd96dba865d91f553619501e94). La comparación es de esos dos archivos, no de todo el paquete. No se cambió BLAST.

Inicialmente `cap=66 Ah`, `cap_2ndLife=46 Ah`, `q=1`, `qNew=0.7`, `qNew*66=46.2 Ah`. La diferencia 0.2 Ah entre las dos referencias permanece. Para transparencia se calculan ambas escalas, `46*q` y `66*qNew`; el paquete no impone una reconciliación entre ellas.

## Perfiles y resultados

El ciclo sintético va de SoC 1 a 0 y a 1, 1 h por tramo, 25 °C y muestras cada 60 s; su 1C es relativo a la capacidad disponible inicial implícita del perfil SoC. Es una condición nominal compatible con el punto de ensayo cíclico declarado por BLAST, no reproducción de un ensayo real ni un perfil de corriente medida. El reposo dura 30 días a SoC 0.5 y 25 °C. Las ventanas comparten exactamente el punto frontera y reutilizan la misma instancia, sin reiniciar estados. Los tiempos son absolutos y crecientes. `results.json` conserva todas las cifras.

| Caso | q | qNew | qLoss_t | qLoss_EFC | EFC | 66*qNew (Ah) | 46*q (Ah) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Reposo continuo | 0.9812071334 | 0.6868449934 | 0.0187928666 | 0 | 0 | 45.33176956 | 45.13552814 |
| Reposo dos ventanas | 0.9800539828 | 0.6860377880 | 0.0199460172 | 0 | 0 | 45.27849401 | 45.08248321 |
| Ciclo continuo | 0.9986848302 | 0.6990793811 | 0.0012393698 | 0.0000758000 | 1 | 46.13923915 | 45.93950219 |
| Ciclo dos ventanas | 0.9986100377 | 0.6990270264 | 0.0013154189 | 0.0000745434 | 0.9995328171 | 46.13578374 | 45.93606173 |

Con temperatura y SoC constantes en reposo, `k_cal` coincide y EFC es cero, pero `q` difiere −0.0011531506: la actualización de potencia incremental depende del tamaño de ventana. En el ciclo, las dos mitades son simétricas en SoC y `k_cal` coincide; el EFC se reduce en 0.0004671829 porque `_extract_stressors` multiplica el cambio absoluto de SoC por `q` al comienzo de cada llamada. Las pérdidas dependen también del esquema incremental y los exponentes, por lo que no debe atribuirse toda la diferencia a EFC. La frontera compartida no duplica un intervalo de tiempo o cambio de SoC.

Control adicional con el mismo ciclo y rampa de temperatura de 20 a 30 °C: continuo `q=0.9986465880`, dos ventanas `q=0.9983146430`, EFC respectivamente 1 y 0.9996230483; `k_cal` global 0.0040470548, ventanas 0.0031374108 y 0.0049566987. Aísla sensibilidad a la agregación de T conjuntamente con el esquema de actualización y el cambio de `q`: **no** es un caso cíclico experimentalmente validado a temperatura variable. Los resultados no prueban independencia general frente a segmentación o convergencia.

## Hipótesis de adaptación y frontera SoC

Solo como hipótesis, tomando la retención `q_final/q_inicial=0.9986848302` del ciclo continuo: para tesis 44.1 Ah resulta 44.04200101 Ah y SoH 0.66730305; para Braco 43.5 Ah, 43.44279011 Ah y SoH 0.65822409, ambos respecto a 66 Ah. No son capacidades originales del paquete ni constituyen calibración de sus coeficientes para dichos estados iniciales. La transferencia de retención relativa a otra batería requiere justificación y validación.

La trayectoria suministrada a BLAST conserva SoC fraccional en la frontera; la clase no almacena carga ni decide una política física. Ejemplo ilustrativo con el reposo segmentado, caso 44.1 Ah y SoC 0.5: capacidad hipotética 43.49916710 a 43.22038064 Ah. Conservar SoC deja `SoC*Q` de 21.74958355 a 21.61019032 Ah; conservar esa carga algebraica requiere SoC 0.50322517. Esa contabilidad simplificada no demuestra conservación electroquímica ni explica capacidad inaccesible; un rebase puede superar 1 o límites operativos y no debe contarse como transferencia de carga ni EFC artificial. Ninguna política se selecciona aquí.

## Dictamen de contrato

`CapacitySnapshot(66, Q_inicial, q/q0)` puede construirse para los valores observados y cumple algebraicamente su contrato. La conversión NO es inequívoca ni validada físicamente: hace falta elegir y documentar la referencia 46 versus 46.2 Ah, Q inicial y su trazabilidad, instante y estado BLAST inicial `q0`, historial/estado interno completo, escalas y perfil temporal SoC/T, definición de EFC y política de segmentación, política de frontera SoC/carga y tratamiento de límites, dominio de aplicación, comportamiento cuando retención sale de (0,1] o se alcanza el piso de SoH, así como la política de actualización sin doble conteo de la degradación lineal. La prueba no selecciona ninguna de esas decisiones ni conecta el BESS.

Siguiente microtarea: especificar y ensayar fuera de la microrred un protocolo de ventanas con convergencia/sensibilidad, transferencia de retención y frontera SoC explícitas, decidir criterios y evidencia para aceptar su dominio y evitar doble conteo; luego revisar el contrato antes de cualquier integración. BAT26-32 continúa abierta.
