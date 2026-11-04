# BAT26-37 — restricciones operativas y balance energético del BESS

## Alcance y dictamen

La ruta integrada es consistente **algebraicamente** con sus ecuaciones de SoC, supervisión de corriente/potencia y balance del capacitor DC, bajo sus convenciones. No queda establecido un balance energético físico cerrado entre la unidad de batería y el bus: el ECM y el enlace emplean la misma variable `i_bess`, pero sus tensiones son de escalas distintas y no se integra un convertidor que relacione sus potencias. Tampoco se ha validado una energía electroquímica almacenada ni una eficiencia DC/DC para la batería de tesis.

Este documento identifica la implementación y sus restricciones, no modifica ecuaciones, arquitectura ni parámetros, y no convierte validaciones internas en validación experimental. Fuentes locales: `src/bess/model.py`, `aging_capacity.py`, `dc_dc_adapter.py`, `src/microgrid.py`, `microgrid_bess_pi.py`, ADR-001 y BAT26-34–36. El adaptador DC/DC algebraico se analiza aparte porque **no está conectado** a `MicrogridWithBESS` ni a `MicrogridWithBESSPI`.

## Variables, puertos y signos

| Variable | Unidad | Significado en implementación |
|---|---|---|
| `s`, `SoH` | fracción adimensional | SoC y salud por capacidad; no son energía ni potencia |
| `Q_nom`, `Q_init`, `Q_eff` | Ah | referencia nueva, capacidad inicial de caso y capacidad efectiva |
| `i_bess` | A | variable compartida por la ruta integrada: positiva descarga hacia DC, negativa carga |
| `V_t`, `V_rc`, `OCV` | V | tensión terminal 1RC diagnóstica, polarización RC y mapa de tensión llamado OCV; escala del ECM provisional |
| `R0`, `R1`, `C1` | Ω, Ω, F | parámetros del ECM; sus valores/procedencia son provisionales según BAT26-35 |
| `Vdc`, `ipv`, `idc_inv` | V, A, A | tensión de enlace, corriente FV entrante y corriente extraída por inversor |
| `p_bess_dc=Vdc*i_bess` | W | potencia firmada en puerto DC del modelo: positiva entrega al bus, negativa absorbe del bus |
| `p_t=V_t*i_bess` | W | producto terminal ECM que puede calcularse en escala consistente; no es automáticamente potencia del bus ni salida validada para el banco |
| `z_deg` | Ah | throughput acumulado de la corriente usada por el modelo; no automáticamente throughput físico de una pareja 2p |

Las integrales de potencia en segundos producen energía en J: `E=∫P dt`; dividir por 3600 para Wh. `SoC*Q_eff` está en Ah, no Wh. El signo positivo de `i_bess` implica `ds/dt<0` en descarga y potencia DC positiva si `Vdc>0`.

## Ecuaciones y modos de envejecimiento

Para el estado BESS protegido `[s,V_rc,z_deg]`, con `t` en s y durante una ventana de capacidad fija en modo snapshot:

```text
ds/dt        = -i_bess/(3600 Q_eff)
dV_rc/dt     = -V_rc/(R1(s) C1(s)) + i_bess/C1(s)
dz_deg/dt    = |i_bess|/3600
V_t          = OCV(s) - i_bess R0(SoH) - V_rc
R0(SoH)      = R0_nom [1 + k_R(1-SoH)]
```

En la ruta lineal de tres estados, `SoH=max(soh_min, soh_init-k_deg*z_deg)` y `Q_eff=max(q_eff_min,Q_nom*SoH)`. El estado `z_deg` puede contener historia; su incremento equivale a Ah absolutos del puerto, no a EFC ni a energía. El `rhs` de dos estados conserva su interfaz histórica con SoH externo. En modo BLAST, `CapacitySnapshot` calcula `r=q(t)/q(t0)`, `Q_eff=Q_init*r` y `SoH=Q_eff/Q_nom`; ese valor permanece fijo durante la ventana y `z_deg` sigue solo como diagnóstico, sin pérdida lineal adicional de capacidad. Las alternativas son excluyentes.

Por defecto `Q_nom=66 Ah`, `Q_init=44.1 Ah` y `SoH_init=0.6681818`. `46 Ah` es el atributo de segunda vida BLAST y `46.2 Ah=0.7*66` otra referencia del paquete; `43.5 Ah` identifica otro caso Braco. No se igualan ni se aplica otra vez 0.7 a `Q_init`. La transferencia `q/q(t0)` al caso es hipótesis de modelado, no calibración de ese ejemplar.

El ECM usa `R1(s)` y `C1(s)` por interpolación, y el mapa `OCV(s)` como proxy provisional; la búsqueda limita el argumento de la tabla a [0,1], lo que **no** es una protección que recorte el estado SoC del solver. No se implementa dependencia térmica de esos parámetros. `R0_nom=0.970 mΩ` coincide numéricamente con DCIR de pulso a 10 s, no demuestra `R0` instantánea. Con `k_R=1`, el valor calculado a `44.1/66` es **1.291864 mΩ**. BAT26-35 cita aproximadamente 1.2929 mΩ; la sustitución directa en la fórmula vigente da 1.291864 mΩ. No se cambia ese documento ni el parámetro, y la relación sigue sin calibrar.

## Restricciones vigentes y sus límites

| Restricción | Implementación integrada y alcance | Estado físico/evidencia |
|---|---|---|
| SoC | `0.1–0.9` valores de caso. Si `s≤0.1`, se bloquea corriente positiva; si `s≥0.9`, se bloquea negativa. Se conserva capacidad de mandar en sentido de recuperación. El helper de frontera rechaza SoC fuera de límites sin clipping. | Límites operativos seleccionados para simulación; la saturación de comando no garantiza por sí sola que cualquier integración o paso numérico mantenga todo estado dentro del rango. No es BMS industrial. |
| Corriente | `I_av=min(I_max,max(0,I_max*SoH))`; por defecto `I_max=66 A`. Se limita `|i_bess|≤I_av`. | 66 Ah/1C tiene respaldo de referencia Leaf; el escalado lineal de corriente con SoH y el uso de esa corriente como variable del bus son simplificaciones, no límites certificados del grupo 2p. |
| Potencia disponible | `P_av=min(P_max,Vdc_ref*I_av)` con `P_max=22440 W`, `Vdc_ref=340 V`; el control proporcional, si `Vdc>0`, limita además `|i_bess|≤P_av/Vdc`. | Cota de interfaz equivalente del bus; 22440=340·66, no potencia medida de una unidad 2p. Para `Vdc≤0` la ruta proporcional no aplica esa división; no se declara protección física de bus. |
| PI externo | Para `Vdc>0` y BESS habilitado, `P_lim=min(P_av,Vdc*I_av)` y `p_ref∈[-P_lim,P_lim]`, con signo bloqueado por límites de SoC. La corriente usa `p_ref/max(Vdc,Vmin)` y se vuelve a limitar; para `Vdc≤0` o BESS deshabilitado, comando cero. | `Vmin=50 V` es salvaguarda numérica para conversión, no umbral electroquímico de batería. Si `0<Vdc<Vmin`, la potencia real `Vdc*i_bess` no tiene por qué igualar `p_ref`. Saturación y anti-windup son lógica de simulación. |
| Capacidad y SoH | `soh_min=0.5`, `q_eff_min=1e-9 Ah`; se rechazan snapshots incompatibles o inferiores a esos mínimos. El modo lineal aplica piso a SoH; BLAST usa snapshot y el adaptador rechaza menor SoH configurado. | Son barreras de simulación, no EoL universal ni protecciones certificadas. `Q_eff>0` evita división por cero. |
| Tensión terminal | `V_t` se calcula y reporta; no se aplican en la ruta integrada límites explícitos `V_t,min/max` al comando de corriente. | Falta supervisión validada de sobretensión/subtensión de celda. Los límites por unidad del adaptador DC/DC separado **no** protegen automáticamente la ruta integrada. |
| Temperatura y degradación | La ruta rápida no incluye estado térmico ni protecciones térmicas; BLAST es lento, externo y solo admite perfiles sintéticos en el adaptador actual. | No hay T de celda ni corriente de grupo 2p acreditadas para operación; ni la ley lineal ni la transferencia BLAST están validadas en la muestra objetivo. |

En el punto inicial, `I_av=44.1 A`, `P_av=14994 W`; son resultados de las fórmulas de supervisión, no caracterización de potencia real. Límites de corriente y potencia se aplican a la variable equivalente del modelo, con los matices de `Vdc` de la tabla. El inversor tiene su propia eficiencia/UVLO; no confundirla con eficiencia DC/DC de batería.

## Balance en el enlace DC

La ecuación protegida implementada es

```text
Cdc · dVdc/dt = ipv + i_bess − idc_inv
E_Cdc = 0.5 Cdc Vdc²                              [J]
dE_Cdc/dt = Vdc ipv + Vdc i_bess − Vdc idc_inv  [W]
```

La identidad del capacitor se obtiene multiplicando la ODE por `Vdc`, con `Cdc` constante (`0.002 F` por defecto). Para energía sobre una ventana se integran esos términos. `Vdc*i_bess` es exactamente la inyección DC definida, con signo; el término de inversor es `Vdc*idc_inv` en el puerto DC, no se identifica sin más con potencia PCC debido a inversor, filtro y cargas. Esta identidad no prueba que la energía extraída del ECM sea igual a la suministrada al bus.

En la implementación integrada se introduce la **misma cifra de corriente** en la ecuación ECM y en el bus, sin una transformación de topología o eficiencia. Al comparar formalmente `p_t` y `p_bess_dc` aparece el residuo `(V_t−Vdc)*i_bess`, que no se puede llamar pérdida física del convertidor: no está calculado ni garantizado no negativo y puede mezclar escalas unidad/banco. No hay una eficiencia DC/DC explícita ni una demostración de conservación total en esa ruta. La ley de SoC usa eficiencia coulómbica unitaria de forma implícita; ello **no** justifica eficiencia energética unitaria de batería o convertidor.

## Descomposición de potencia del ECM

Como identidad algebraica en una escala ECM coherente, definiendo `U=OCV(s)` y `i=i_bess`:

```text
U i = V_t i + i² R0 + V_rc i
V_rc i = V_rc²/R1 + C1 V_rc dV_rc/dt
```

`i²R0≥0` es disipación de la resistencia de la abstracción; `V_rc²/R1≥0` es el término resistivo de la rama RC si `R1>0`. `V_rc*i` no es íntegramente pérdida: incluye variación de la rama de polarización. Si `C1` fuera constante, `C1 V_rc dV_rc/dt=d(0.5 C1 V_rc²)/dt`. Aquí `C1=C1(s)` varía; donde sea diferenciable, si se introduce **solo como contabilidad algebraica** `E_RC*=0.5 C1(s)V_rc²`, la regla del producto da

```text
U i = V_t i + i²R0 + V_rc²/R1 + dE_RC*/dt − 0.5 V_rc² dC1/dt.
```

Sin el último término no se obtiene esa identidad cuando C1 cambia. Las derivadas pueden no existir en los nodos de interpolación; se aplica por tramos. Una capacitancia de tabla dependiente de SoC no garantiza que `E_RC*` represente energía física de un capacitor variable ni incorpora necesariamente la potencia necesaria para variar el parámetro. El test matemático comprueba la identidad, no la pasividad física ni una nueva ecuación del ECM.

De manera análoga, para `Q_eff` constante, eficiencia coulómbica unitaria y una función `U(s)` identificada, se puede **definir una referencia algebraica** `E_U(s)=3600 Q_eff ∫ U(s) ds` [J] de modo que `dE_U/dt=−U(s)i`. El mapa llamado OCV es provisional y no está demostrado como potencial de equilibrio de la pareja 2p; por ello esa integral no es energía química medida ni demuestra pérdidas químicas, térmicas o eficiencia real. Si cambia `Q_eff`, aparecen términos de capacidad y condiciones de frontera que no pueden inferirse de esta identidad por ventana.

## Adaptador DC/DC algebraico separado

`bess.dc_dc_adapter.convert_power` resuelve por punto un banco balanceado de `N_s` unidades en serie y `N_p` ramas paralelas idénticas, con parámetros entregados por el llamador. Denotando corriente y tensión por unidad `i_u`, `v_u=OCV−V_rc−R0*i_u`, utiliza `P_bank=N_s N_p v_u i_u`; el bus cumple `P_bus=Vdc*i_bus`. Ambas potencias son firmadas positivas en descarga:

```text
descarga: P_bus = eta_dis * P_bank
carga:    P_bank = eta_ch * P_bus
P_loss = P_bank − P_bus ≥ 0     (0 < eta_dis, eta_ch ≤ 1).
```

Para carga, ambas potencias son negativas y `P_loss` sigue siendo no negativa. El código limita SoC, corriente y tensión por unidad, y corriente/potencia de bus; acepta límites de corriente disponibles externos para representar supervisión SoH. Primero comprueba tensión sin corriente `OCV−V_rc`, OCV y Vdc, y bloquea intercambio si la protección se activa; después usa la raíz de corriente baja de la relación cuadrática. Eso es un **modelo algebraico independiente con eficiencia suministrada**, no eficiencia medida ni parte de la ruta integrada actual.

No modela inductores, semiconductores, conmutación, dinámicas ni controles de un convertidor bidireccional; tampoco identifica topología, distribución de corrientes entre unidades desbalanceadas, sensores, pérdidas variables, térmica o protecciones completas. Para un convertidor dinámico validado se requieren arquitectura y escala justificadas, parámetros y eficiencias medidos en ambos sentidos, estados/control y límites, coherencia con 2p/pack y bus, integración arquitectónica explícita y contraste independiente I/V/potencia/energía. No se añaden topología ni parámetros aquí.

## Actualización entre ventanas y criterios de comprobación

BLAST avanza fuera de la ODE rápida con su propia historia. Entre ventanas se congela un nuevo snapshot y, por ADR-001, se conserva SoC fraccional y el vector físico completo; el evento no genera corriente, `z_deg`, EFC, potencia ni energía intercambiada instantánea. `SoC*Q_eff` cambia algebraicamente, pero no se atribuye esa diferencia a energía descargada o pérdida térmica. Al bajar SoH, la capacidad por ventana y límites `I_av`/`P_av` pueden disminuir y `R0(SoH)` puede aumentar según la ley provisional. No confundir ese efecto con un convertidor o BMS validado. El snapshot se valida contra los mínimos del BESS y el llamador debe usar explícitamente el helper de frontera para rechazar SoC fuera de rango; no existe orquestador que lo imponga automáticamente ni clipping físico inventado.

Para cada campaña deben registrarse puertos y escalas, signos, `Q_eff`/SoH, SoC y mínimos/máximos, corrientes y saturaciones por sentido, `V_t` como diagnóstico, `Vdc`, potencias y sus integrales, estados RC, T y trazabilidad 2p, criterios de ventana y EFC nativo. Comprobar: ecuación DC y energía del capacitor; restricciones por sentido de SoC/corriente/potencia; identidad terminal 1RC y término variable de C1; identidad algebraica de pérdidas del DC/DC **solo si se usa esa herramienta independiente**; continuidad de estado y ausencia de transferencia ficticia en snapshots; consistencia de unidades y separación de fuentes de envejecimiento. Una prueba de igualdad entre terminal y bus requiere una conversión física explícita que hoy falta.

## Evidencia ejecutada y cierre

Tras verificar y cerrar BAT26-36 en Roma por su criterio documental (7 pruebas del contador BLAST/BESS y 4 de frontera repetidas; resultados guardados cotejados), se ejecutaron en `.venv`:

- `test_bess_rc_energy_identity.py`: **1 PASS**, descomposición con `C1(s)` variable en carga y descarga.
- `test_dc_dc_adapter.py`: **15 PASS**, potencia, signos, eficiencias sintéticas, saturaciones y protecciones del adaptador separado.
- `test_bess_sign_coherence.py`: **3 PASS**; `test_dclink_dynamics.py`: **5 PASS**; `test_capacity_snapshot_integration.py`: **6 PASS**.

Las pruebas son algebraicas/de software con parámetros o perfiles sintéticos; no prueban eficiencia, energía o límites reales de la batería. La comparación independiente del EFC y el cierre documental de BAT26-36 no constituyen validación experimental. No se repitieron simulaciones integradas pesadas: el único código nuevo es una prueba matemática aislada.

**Dictamen:** BAT26-37 puede cerrarse **documentalmente** respecto al criterio de Roma —SoC, corrientes, potencia, Qeff, tensión y eficiencia, con pendiente DC/DC explícito—, sujeto a revisión del usuario. No se marca completada automáticamente y no se declara cerrado el balance físico global ni validado el convertidor.
