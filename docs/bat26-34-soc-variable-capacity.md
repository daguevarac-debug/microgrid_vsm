# BAT26-34 — Evolución de SoC con capacidad efectiva variable

## Alcance y estado de evidencia

Este documento deriva el significado de SoC cuando el snapshot de capacidad efectiva cambia entre ventanas. Se mantiene la convención del BESS existente `i_bess > 0` para descarga, `i_bess < 0` para carga y se asume eficiencia coulómbica unitaria, tal como en la ecuación actual de conteo de coulombs. No cambia ninguna ecuación ni estado del modelo. La convención aprobada para simulaciones de escenario es conservar SoC fraccional en la frontera. No implica conservación física de energía.

La auditoría del puente BAT26-33 confirma en código que BLAST entrega `q/q0`, `CapacitySnapshot` forma `Q_eff=q_init_case·q/q0` y `SoH=Q_eff/66 Ah`; el modo BLAST usa ese Q fijo durante cada integración y mantiene `z_deg` sólo como diagnóstico. Las pruebas reportadas en el informe BAT26-33 (10 del adaptador, 17 de contrato/snapshot y regresiones descritas allí) respaldan ese alcance de software. La coherencia algebraica y las pruebas internas no validan la transferencia experimental, la temperatura/corriente del grupo 2p ni la energía física disponible. BAT26-33 se deja preparado para cierre, sin marcarlo completado.

## Definiciones y unidades

- `s(t)`: SoC fraccional, adimensional, entre 0 y 1.
- `Q_eff`: capacidad efectiva de carga, Ah.
- `Q_stored := s Q_eff`: carga restante algebraica, Ah. Esta definición es contabilidad de carga disponible bajo el modelo, no estado químico medido directamente.
- `i_bess`: corriente con signo del modelo, A; positiva al descargar.
- `t`: segundos.

SoC no es energía. `s Q_eff` tiene unidad Ah, no Wh. La energía eléctrica que sale por una frontera eléctrica especificada se calcula como `E_out,Wh = (1/3600) ∫ V(t)i_bess(t) dt`, con V en voltios, I en amperios y t en segundos; signo y punto de medición deben declararse. Para una celda ideal en equilibrio, una aproximación de energía electroquímica disponible requeriría integrar OCV sobre carga (`Q_eff ∫ OCV(s) ds`, con escala y condiciones coherentes); no se obtiene multiplicando Ah por SoC solamente. La salida reportada por el modelo en el bus es `p_bess_dc=Vdc·i_bess`; su integral es energía en el puerto DC del modelo, no una medición de energía electroquímica de la pareja Leaf. En el ECM provisional, la tensión terminal incluye caída óhmica y polarización RC, la caracterización y su escala física/topológica tienen incertidumbre, y no hay modelo térmico ni conversión DC/DC detallada. Por eso este documento no afirma conservación ni cuantificación de energía almacenada del sistema real.

## Evolución dentro de una ventana de capacidad fija

En una ventana `k`, `Q_eff,k` es constante. El balance coulómbico, con eficiencia unitaria y la corriente positiva hacia afuera durante descarga, es

```text
dQ_stored/dt = -i_bess/3600                 [Ah/s]
s = Q_stored/Q_eff,k                       [-]
ds/dt = (1/Q_eff,k) dQ_stored/dt
       = -i_bess/(3600 Q_eff,k)              [s^-1]
```

La unidad de la última expresión es `(A)/(3600 s/h · Ah) = 1/s`. Con corriente constante durante `Δt`, `s(t+Δt)=s(t)-i_bess Δt/(3600Q_eff,k)`. Corriente negativa aumenta SoC. Ésta es exactamente la forma de la ODE BESS actual dentro de la ventana; no requiere ni admite un término `dQ_eff/dt` cuando el snapshot permanece fijo.

Si por análisis se definiera capacidad como función continua del tiempo y se mantuviera la identidad `Q_stored=sQ_eff`, la regla del producto da

```text
dQ_stored/dt = Q_eff ds/dt + s dQ_eff/dt
ds/dt = -i_bess/(3600 Q_eff) - (s/Q_eff) dQ_eff/dt.
```

El segundo término corresponde a la evolución de Q elegida en esa formulación continua. No es una corriente terminal medida. La implementación aprobada por ventanas no usa ese modelo continuo ni añade término al solver: congela capacidad en cada ventana y trata la frontera separadamente.

## Actualización discreta entre ventanas

Al pasar de `Q−` a `Q+`, el usuario aprobó mantener `s+=s−`. La identidad contable entonces produce

```text
ΔQ_stored,alg = s−(Q+ − Q−)                 [Ah]
```

Para degradación `Q+<Q−`, esa cantidad algebraica disminuye. No se interpreta como carga extraída por corriente. En la frontera no se añade muestra temporal al perfil BLAST ni se modifica el estado `z_deg`, el throughput, corriente, potencia o energía transferida. `z_deg` conserva su significado de estado integral de `|i_bess|/3600` en la trayectoria eléctrica existente; no corrige ni compensa el salto contable de capacidad.

La alternativa de conservar carga algebraica impondría `Q_stored+=Q_stored−` y por tanto `s+=s− Q−/Q+`. Si hay pérdida de capacidad, SoC salta hacia arriba; puede superar 0.9 (p. ej., 0.9 pasa a 0.900091 en la magnitud ilustrativa reportada en el prototipo). Ese salto no es carga física introducida y no puede convertirse en un delta de SoC para BLAST, porque crearía throughput/EFC ficticio. No es la convención aprobada.

Conservar SoC fraccional tampoco demuestra conservación energética: `Q_stored,alg` cambia, OCV puede depender de SoC, temperatura y estado de la celda, y un snapshot no mide Wh ni una transferencia. Si la corriente real es cero en frontera, la integral terminal `∫V_t i dt` de ese instante/evento es cero por construcción; esto sólo dice que el modelo no reporta intercambio eléctrico, no que la batería conserve energía electroquímica bajo envejecimiento.

## Condiciones de límites operativos

Para cada ventana debe verificarse `0.1 ≤ s(t) ≤ 0.9` en toda la trayectoria, incluida la frontera. Con continuidad de SoC, se exige primero `0.1 ≤ s− ≤ 0.9`; el cambio de Q no altera por sí mismo s. Durante la ventana de capacidad fija, define el throughput algebraico firmado `A(t)=∫[t_k,t] i_bess(τ)dτ` en A·s. Entonces

```text
s(t) = s_k − A(t)/(3600 Q_eff,k)
3600 Q_eff,k (s_k − 0.9) ≤ A(t) ≤ 3600 Q_eff,k (s_k − 0.1)
```

La desigualdad debe cumplirse para cada tiempo intermedio, no sólo al final, especialmente si la corriente cambia de signo. La supervisión de corriente/potencia existente debe seguir activa. En el límite inferior se bloquea descarga (`i_bess>0`); en el superior se bloquea carga (`i_bess<0`). No usar clipping de SoC para recuperar una trayectoria fuera de límites: detener/rechazar la ventana, diagnosticar el incumplimiento o declarar escenario no factible. La función de frontera existente `preserve_window_state` copia el vector y rechaza SoC fuera de límites sin rebase.

## Supuestos y limitaciones

1. El balance `dQ_stored/dt=-i/3600` omite eficiencia coulómbica, relajación, autodescarga y redistribución entre celdas; es la abstracción ya implementada, no una nueva afirmación electroquímica.
2. `Q_eff` del adaptador es hipótesis de transferencia `q/q0` aplicada a Qcase y permanece constante durante una ventana rápida.
3. Los datos del puente son sintéticos; no se dispone de perfil acreditado conjunto de corriente de grupo 2p y temperatura de celda para validar el caso.
4. `Q_stored=sQ_eff` es carga algebraica en Ah; no se ha identificado función experimental de energía vs SoC para la misma unidad 2p ni conversión física al bus DC.
5. No se reinterpreta ni modifica `z_deg`, estados BESS, ecuaciones ECM/VSG/PI/DC/DC ni solver.

## Pruebas pequeñas y reproducibilidad

`src/validation/test_soc_variable_capacity_boundary.py` verifica: corriente con ambos signos y unidades de la derivada actual `rhs`, variación contable `sΔQ` bajo frontera de SoC constante, cambio de SoC que requeriría conservación algebraica de carga, y preservación exacta del estado/frontera sin clipping. Son pruebas de consistencia matemática/de software; no simulan energía química ni validación experimental.

Comando dirigido:

```powershell
\.venv\Scripts\python.exe -m unittest discover -s src/validation -p test_soc_variable_capacity_boundary.py -v
```

Las regresiones amplias de BAT26-33 están documentadas en `docs/bat26-33-blast-capacity-bridge.md`; este trabajo no las vuelve a ejecutar porque no toca el código de la microrred.
