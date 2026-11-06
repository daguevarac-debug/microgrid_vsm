# BAT26-49 — Metodología, trazabilidad de ecuaciones y límites de evidencia

**Objeto.** Consolidar una metodología defendible para explicar el BESS Nissan Leaf de segunda vida en la microrred GFM, distinguiendo ecuaciones **publicadas**, definiciones **derivadas**, hipótesis **propuestas para la tesis** y resultados **de simulación**. Este documento NO aporta medición de capacidad, ajuste experimental ni optimización de despacho. Depende de BAT26-38 y BAT26-47; utiliza la interfaz documental BAT26-48.

**Regla de citación.** «Página PDF» se refiere a la página ordinal del archivo comenzando en 1, no necesariamente a la numeración de la revista. Las páginas y figuras de Braco/Tran aquí consignadas se comprobaron directamente en los cuatro PDF aportados por el usuario. Cuando se cita un artículo externo cuyo texto se consultó en HTML, se señala **sección**, sin inventar un número de página. La tabla complementaria es docs/bat26-49-source-evidence-matrix.md.

## A. Frontera física y referencias de capacidad

La unidad física mínima del modelo documental es una **pareja de celdas en paralelo, 2p**, del módulo Nissan Leaf 2s2p; una pareja no es el módulo 2s2p ni el pack. Braco et al. (2020), PDF p. 2, §2 y Fig. 1, identifican 2s2p y el uso de la pareja como unidad ensayada. Braco et al. (2023), PDF p. 4, §3.1, detallan los puertos y la topología; **Tabla 1 de la p. 5** diferencia tensión/capacidad de pack, módulo y pareja: 3.75 V nominales y 66 Ah para la pareja, frente a 7.50 V/66 Ah del módulo. DOI: https://doi.org/10.1016/j.est.2020.101695 y https://doi.org/10.1016/j.apenergy.2022.120235.

La tesis fija la referencia nominal Q_nom_ref = **66 Ah** de pareja 2p y adopta por **escenario** una capacidad inicial Q_case = **44.1 Ah**, por lo que el SoH inicial derivado es 44.1/66 = **0.6681818**. El número 44.1 Ah NO representa la capacidad medida de una pareja identificada de Braco. La referencia nativa del BLAST original cap_2ndLife=46 Ah, con qNew(0)·66=46.2 Ah, tampoco debe confundirse con Q_case. Toda comparación mantiene explícita la base del cociente de capacidad.

## B. Ecuaciones y atribución responsable

### B.1. Definición de SoH, capacidad y estado de carga

La definición de SoH por capacidad es explícita en **Braco et al. (2020), PDF p. 3, §3.2**:

$$
SoH=\frac{Q_{\mathrm{actual}}}{Q_{\mathrm{nominal,referencia}}}.
\tag{49.1}
$$

La trayectoria de la tesis utiliza por convenio local una retención relativa a su **propio** inicio de segunda vida; es una **composición implementada**, NO una ecuación extraída literalmente de Braco:

$$
r_j=\frac{q_j^{\mathrm{BLAST}}}{q_0^{\mathrm{BLAST}}},\qquad
Q_{\mathrm{eff},j}=Q_{\mathrm{case}}\,r_j,\qquad
SoH_j=\frac{Q_{\mathrm{eff},j}}{66\ \mathrm{Ah}}.
\tag{49.2}
$$

Aquí j indexa una **ventana lenta**, q es la retención del BLAST-Lite original verificado y r_0=1. La capacidad inicial de 44.1 Ah ya incluye pérdida de primera vida. Aplicar después el factor nativo 0.7 o la pérdida lineal del modelo sobre el mismo snapshot sería doble contabilización. Código trazable: src/bess/aging_capacity.py; src/bess/blast_lite_adapter.py; src/validation/run_bat26_45_multicycle.py.

Para intervalos operativos cortos con Q_eff constante dentro de la ventana j, se implementa el conteo de Coulomb de corriente **de puerto de pareja 2p**; el resultado procede de conservación de carga, NO de una fórmula reproducida palabra por palabra de Tran:

$$
SoC_{k+1}=SoC_k-\frac{I_{\mathrm{bat},k}\,\Delta t_k}
{3600\,Q_{\mathrm{eff},j}},\qquad
\Delta t_k\ [\mathrm{s}],\quad I_{\mathrm{bat},k}\ [\mathrm A],\quad Q_{\mathrm{eff},j}\ [\mathrm{Ah}].
\tag{49.3}
$$

La corriente positiva descarga; la negativa carga. El denominador 3600 convierte segundos a horas. Los límites 0.10≤SoC≤0.90 y SoH≥0.50 son **políticas de escenario/software**, no rangos de seguridad BMS comprobados experimentalmente. Código: src/bess/model.py y src/validation/bat26_48_dispatch_contract.py. No ajustar SoC artificialmente al actualizar Q_eff sin corriente física o hipótesis explícita de recalibración del estimador.

### B.2. Circuito equivalente Thevenin 1RC

El modelo de tensión terminal publicado por **Tran et al. (2021), PDF p. 4, §3.1, Ecuación (1) y Fig. 3**, es:

$$
V_t=OCV(SoC)-I_{\mathrm{bat}}R_0-V_{\mathrm{RC}}.
\tag{49.4}
$$

El mismo artículo, **p. 4, Ecuación (2)**, expresa el cambio discreto de tensión de polarización V_RC como una exponencial de constante de tiempo τ=R_1C_1. Para parámetros localmente constantes y paso corto, el código de la tesis emplea la **forma continua asociada**, que no se atribuye como ecuación textual de Tran:

$$
\dot V_{\mathrm{RC}}=-\frac{V_{\mathrm{RC}}}{R_1C_1}+\frac{I_{\mathrm{bat}}}{C_1}.
\tag{49.5}
$$

La identificación experimental de Tran se realizó sobre **cinco celdas LFP/grafito de 20 Ah nominales**, no sobre Nissan Leaf 2p LMO/LNO–grafito; **PDF p. 3, §2 y Tabla 1**. El procedimiento incluye caracterización OCV cuasiestática y pruebas HPPC, y su evaluación distingue celdas para caracterización y validación. En **PDF pp. 4–5, Figs. 4–7**, la dependencia R0/R1/C1 con SoC, SoH y temperatura se discute experimentalmente, pero sus coeficientes y mapa **no pueden trasplantarse** a nuestra batería Leaf sin reidentificación.

El libro OCV_SOC.xlsx del proyecto contiene 58 registros; su loader reconstruye SoC a partir de Ah/66 e ignora columnas originales SOC/SOH. La tensión rotulada OCV está vinculada a una curva de descarga bajo carga, sin prueba de reposo. R1/C1 carecen de unidades/procedencia experimentales trazables. Esta limitación está registrada en docs/bat26-35-ecm-parameter-evidence.md; por consiguiente, el 1RC **solo es provisional para simulación de escenario**.

La resistencia numérica R0_nom=0.970 mΩ coincide con el dato publicado para **resistencia DC a SoC 50 %** de una pareja Leaf 2p en **Braco et al. (2023), PDF p. 5, Tabla 1**. En **p. 4, §3.2**, dicha R_DC se obtiene con **pulso y lectura transcurridos 10 s**, lo que **no equivale** a identificar la resistencia óhmica instantánea R0 de la Ec. (49.4). La dependencia del código R0(SoH)=R0_nom[1+k_R(1−SoH)] y k_R=1 son **hipótesis de la tesis**, sin calibración física; BAT26-47 solo exploró k_R=0,1,2 como sensibilidad y no como intervalo de confianza.

### B.3. Desgaste y conteos de uso

La ruta lineal de referencia implementa un estado de throughput en Ah y una pendiente de pérdida empírica:

$$
\dot z_{\mathrm{deg}}=\frac{|I_{\mathrm{bat}}|}{3600}\quad [\mathrm{Ah/s}],\qquad
SoH_{\mathrm{lineal}}=\max(SoH_{\min},SoH_0-k_{\mathrm{deg}}z_{\mathrm{deg}}).
\tag{49.6}
$$

El aumento de deterioro con el ciclado está documentado en Braco et al. (2020), **PDF pp. 3–4, Figs. 3–4**, pero el artículo **no** identifica el valor k_deg=1.478×10⁻⁶ de nuestro código ni demuestra linealidad universal. Braco observó que distintas parejas pueden presentar rodillas de degradación diferentes; **PDF p. 6**, lo que impide extrapolar la pendiente sin evaluación.

BLAST-Lite es un **modelo original externo ejecutado en proceso Python 3.12.10 separado**, con hash de las clases auditado y retención por ventanas. Los outputs nativos q, qLoss_t, qLoss_EFC y efc no son series de laboratorio de nuestro par de 44.1 Ah. La historia de BAT26-45 usa SoC sintético 0.5→0.1→0.9→0.5, 25 °C, un ciclo diario de operación y reposo restante. Es un escenario; no una vida de campo ni corriente medida.

**Precisión terminológica detectada en BAT26-49:** deben separarse **tres** contadores. El recorrido fraccional de SoC de un día suma |ΔSoC|=1.6, por lo que sus *ciclos equivalentes de excursión SoC* son 1.6/2=0.8, es decir **800 excursiones equivalentes** en 1000 días. Si se define en cambio un EFC de throughput respecto a una **capacidad de referencia fija** Q_ref, entonces:

$$
EFC_{\mathrm{Ah,ref}}=
\frac{\sum_k |I_{\mathrm{bat},k}|\,\Delta t_k[\mathrm h]}{2Q_{\mathrm{ref}}}.
\tag{49.7}
$$

Con Q_eff variable, cada excursión del 80 % implica aproximadamente 0.8·Q_eff,j/Q_ref EFC_Ah,ref, y **la suma no tiene por qué ser 800**. Finalmente, BAT26-45 reportó **711.452 EFC internos de BLAST**. Por tanto, la denominación histórica «800 EFC nominales» corresponde al **conteo geométrico de excursiones SoC**, no debe presentarse sin matiz como EFC de Ah con denominador nominal fijo. El término «nominal» se conserva en reportes históricos por reproducibilidad, pero debe normalizarse la nomenclatura antes de redactar resultados definitivos. No se altera el ejecutor histórico ni se inventa un valor EFC_Ah,ref que no fue calculado.

### B.4. Degradación y despacho: propuesta económica

**Cheng et al. (2023)**, DOI https://doi.org/10.1016/j.rser.2022.113053, resumen y **secciones 2–3 HTML**, integran SoH variable en un despacho de baterías de segunda vida y comparan estrategias con/sin consideración del envejecimiento. **Collath et al. (2022)**, DOI https://doi.org/10.1016/j.est.2022.105634, **sección 4 HTML**, revisan estrategias con degradación incorporada en programación. **Schade y Egging-Bratseth (2024)**, DOI https://doi.org/10.1002/est2.588, **secciones 4, 4.1 y 4.2 HTML**, modelan costo de desgaste por mecanismo de ciclado y calendario; su **Ecuación (10) de la sección 4.2** valora pérdidas porcentuales de capacidad con un costo de reemplazo expresado en €/kWh y energía nominal en kWh. **No** se ha convertido ni adoptado dicha ecuación como costo de nuestro par 2p, ni se han verificado páginas impresas de estos tres artículos desde un PDF completo.

La tesis **propone**, no atribuye a ellos, un proxy de amortización lineal por pérdida de Ah:

$$
Q_{EOL}^{esc}=66\cdot0.50=33\ \mathrm{Ah},\qquad
C_{deg}^{esc}=\frac{C_{activo}^{esc}-V_{residual}^{esc}}{44.1-33\ \mathrm{Ah}}\,
\max(0,Q_{\mathrm{eff},j}-Q_{\mathrm{eff},j+1}).
\tag{49.8}
$$

Este costo es solo simbólico y exige **la misma escala física del activo y del denominador de capacidad**. No se tiene aún precio en COP ni disposición final validada. No se debe penalizar por EFC y simultáneamente por la **misma** ΔQ sin justificar una descomposición adicional, porque habría doble conteo. La optimización del Objetivo 3 y la traducción física a potencia/kWh de bus o PCC no están desarrolladas.

## C. Resultados verificables hasta BAT26-48

| Etapa | Resultado reportado | Significado correcto |
| --- | --- | --- |
| BAT26-45 | SoH 66.818 % → 54.324 %; Qeff 44.1 → 35.854 Ah en 1000 jornadas; BLAST efc 711.452 | Trayectoria sintética a 25 °C, sin validación de vida en campo |
| BAT26-46 | A +8 A de puerto 2p por 1 h, SoC 0.418592 inicial frente a 0.376870 envejecido; reserva ideal 22.050 → 17.927 Ah | A igual corriente, menor Qeff implica mayor caída de SoC; energía Wh transferida no es energía disponible |
| BAT26-46 GFM | Cuatro escenarios 15 estados: PASS; BESS **solo cargó/absorbió**, no descargó | No demuestra respuesta de soporte en descarga frente a envejecimiento |
| BAT26-47 ECM | 32/32 casos y 6/6 pruebas PASS; máxima diferencia SoC con paso 15s: 1.67×10⁻¹³ pp | Consistencia numérica para casos y tolerancias elegidos, no exactitud experimental |
| BAT26-47 BLAST | Partición 1/2/4 ventanas: SoH final 64.049385/64.038716/64.041229 % a 100 días | Sensibilidad no monótona al particionado, sin convergencia física establecida |
| BAT26-48 | 7/7 pruebas de contrato PASS; exporta campos DC/energía como null cuando falta mapeo | Interfaz de datos, no despacho económico ya resuelto |

Las cifras de las campañas proceden de **informes Codex Cloud comunicados por el estudiante** y consignados en documentación versionada; los archivos summary.json originales en sus carpetas workspace no fueron importados íntegramente a GitHub. El estado de madurez no debe elevarse por el número de pruebas exitosas.

## D. Dominio de validez y puertas científicas pendientes

| Componente | Alcance demostrable | Lo que falta antes de afirmarlo físicamente |
| --- | --- | --- |
| SoH/BLAST | Retención en un perfil SoC/T sintético con actualización por ventanas | Datos originales de una pareja 2p identificada, corriente, T de celda y RPT comparables, estimación de error y convergencia con criterio |
| 1RC | Ecuaciones numéricas estables; Thevenin respaldado como estructura por Tran | Identificación específica Leaf 2p SoH/T, OCV con protocolo de reposo, R0 instantánea, R1/C1 y transitorios I/V independientes |
| Acople rápido | Invariantes SoC, signos, Vdc y frecuencia bajo pruebas de software | Corriente física 2p → bus DC mediante serie/paralelo, DC/DC, eficiencia, pérdidas y ensayos con descarga positiva |
| IEEE 33 | Posprocesamiento secuencial unidireccional | Escala de potencia representativa, acoplamiento dinámico bidireccional si se pretende atribuirlo |
| Despacho | Contrato y formulación objetivo propuesta | Perfiles horario/PV, restricciones BMS, mapeo energético, costos documentados y solución reproducible del optimizador |

**Clasificación final BAT26-49 de este borrador:** origen de las ecuaciones y unidades trazados; fuentes Braco y Tran respaldadas por páginas del PDF aportado; fuentes económicas externas vinculadas a DOI y secciones editoriales **sin inventar páginas**; modelo de desgaste y precio sin validación experimental, por lo cual la valoración física/económica permanece **REVIEW**. El cierre de BAT26-49 será **documental**, condicionado a cotejo del borrador con código y matriz de evidencia; no equivale a aprobación de vida útil ni de despacho.

## E. Referencias principales (con localización verificable)

Braco, E., San Martín, I., Berrueta, A., Sanchis, P., y Ursúa, A. (2020). *Experimental assessment of cycling ageing of lithium-ion second-life batteries from electric vehicles*. Journal of Energy Storage 32, 101695. DOI https://doi.org/10.1016/j.est.2020.101695. PDF usuario pp. 2–4, 6; fuente directa de capacidad/SoH, ensayo 2p, RPT y rodillas.

Braco, E., San Martín, I., Berrueta, A., Sanchis, P., y Ursúa, A. (2021). *Experimental Assessment of First- and Second-Life Electric Vehicle Batteries: Performance, Capacity Dispersion, and Aging*. IEEE Transactions on Industry Applications 57(4), 4107–4117. DOI https://doi.org/10.1109/TIA.2021.3075180. PDF usuario pp. 3 y 9, protocolo de caracterización y Fig. 13; no es OCV identificada de la pareja de tesis.

Braco, E., San Martín, I., Sanchis, P., y Ursúa, A. (2023). *Fast capacity and internal resistance estimation method for second-life batteries from electric vehicles*. Applied Energy 329, 120235. DOI https://doi.org/10.1016/j.apenergy.2022.120235. PDF usuario pp. 4–5, §3 y Tabla 1; resistencia pulso 10 s ≠ R0 ohmica instantánea.

Tran, M.-K. et al. (2021). *A comprehensive equivalent circuit model for lithium-ion batteries, incorporating the effects of state of health, state of charge, and temperature on model parameters*. Journal of Energy Storage 43, 103252. DOI https://doi.org/10.1016/j.est.2021.103252. PDF usuario pp. 3–5, §2, §3.1, Ec. (1)–(2), Figs. 3–7; muestra LFP 20 Ah, no Leaf 2p.

Cheng, M. et al. (2023), Renewable and Sustainable Energy Reviews 173, 113053, DOI https://doi.org/10.1016/j.rser.2022.113053. Fuentes web editorial, resumen y secciones 2–3, sin páginas PDF verificadas.

Collath, N. et al. (2022), Journal of Energy Storage 55, 105634, DOI https://doi.org/10.1016/j.est.2022.105634. Editorial web, sección 4, sin página PDF cotejada.

Schade, C. y Egging-Bratseth, R. (2024), Energy Storage 6(2), e588, DOI https://doi.org/10.1002/est2.588. Wiley HTML, §4.2, Ec. (10), sin paginación PDF cotejada.

**Advertencia sobre archivos con nombres semejantes:** el PDF aportado **Nguyen (2025).pdf** corresponde a Nguyen, V. T. et al., *Iterative Learning Control for Virtual Inertia* (DOI 10.3390/su17156727), **no** al trabajo de Nguyen, M. Q. et al. (DOI 10.1002/est2.70166) sobre programación económica citado en BAT26-48. El PDF **Wang (2025).pdf** es *Two-Layer Co-Optimization of MPPT and Frequency Support* (DOI 10.3390/en18184805), **no** Wang et al. (2020) DOI 10.1016/j.energy.2020.118228. Ninguno de los dos PDF debe emplearse como si fuera el artículo económico de título parecido; las referencias de despacho correspondientes provienen de sus páginas editoriales, no de estos archivos.
