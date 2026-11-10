# BAT26-42 — Auditoría del 1RC, límites dinámicos e identidad energética DC

## Alcance y estado

Se revisan el 1RC vigente y sus límites operativos sin alterar ecuaciones protegidas ni afirmar que exista una interfaz física DC/DC validada. La implementación está en src/bess/model.py y src/microgrid.py; el adaptador algebraico separado está en src/bess/dc_dc_adapter.py. Las decisiones anteriores se documentaron en BAT26-34, BAT26-35, BAT26-37, BAT26-38 y BAT26-41.

**Estado:** cinco pruebas nuevas publicadas para revisión en una rama independiente. No se han ejecutado todavía en el entorno local del usuario, por lo que no se declara PASS ni cierre de BAT26-42.

## Ecuaciones y restricciones vigentes

Para el BESS de tres estados y una capacidad fija dentro de la ventana:

\[
\dot s=-\frac{i_{\mathrm{bess}}}{3600Q_{\mathrm{eff}}},\qquad
\dot V_{rc}=-\frac{V_{rc}}{R_1(s)C_1(s)}+\frac{i_{\mathrm{bess}}}{C_1(s)},\qquad
\dot z_{\mathrm{deg}}=\frac{|i_{\mathrm{bess}}|}{3600}.
\]

\[
V_t=OCV(s)-i_{\mathrm{bess}}R_0(SoH)-V_{rc},\qquad
R_0(SoH)=R_{0,\mathrm{nom}}[1+k_R(1-SoH)].
\]

Los mapas OCV, R1 y C1 y la ley R0(SoH) son provisionales según BAT26-35. La curva denominada OCV no está demostrada como curva de circuito abierto; 0,970 mΩ corresponde numéricamente a resistencia DC de 10 s, no identifica R0 instantánea. El factor k_R no está calibrado. No se añade dependencia térmica ni nuevos coeficientes.

La microrred limita la corriente **equivalente del modelo**, que todavía no ha sido identificada como corriente física de un grupo Leaf 2p:

\[
I_{\mathrm{av}}=\min(I_{\max},\max(0,I_{\max}SoH)),\qquad
P_{\mathrm{av}}=\min(P_{\max},V_{\mathrm{dc,ref}}I_{\mathrm{av}}).
\]

La ruta proporcional respeta el límite de corriente; si Vdc es positiva, aplica además el límite de potencia como P_av/Vdc. Bloquea descarga cuando SoC está en 0,1 o por debajo y carga cuando está en 0,9 o por encima, permitiendo el sentido de recuperación. La ruta PI tiene su propia lógica de saturación. Esas restricciones son hipótesis de simulación y no sustituyen un BMS físico ni garantizan las cotas entre cada muestra del solver.

El caso inicial de 44,1 Ah da SoH=44,1/66; las expresiones anteriores arrojan I_av=44,1 A y P_av=14.994 W con Vdc_ref=340 V. Bajo una retención sintética de 0,9, Qeff pasa a 39,69 Ah, I_av a 39,69 A y P_av a 13.494,6 W. No son capacidades operativas validadas experimentalmente.

## BAT26-38 M10: energía del capacitor DC

La planta implementa

\[
C_{\mathrm{dc}}\dot V_{\mathrm{dc}}=i_{\mathrm{pv}}+i_{\mathrm{bess}}-i_{\mathrm{dc,inv}}.
\]

Con Cdc constante, su identidad energética es

\[
E_{\mathrm{dc}}=\frac12 C_{\mathrm{dc}}V_{\mathrm{dc}}^2,\qquad
\dot E_{\mathrm{dc}}=V_{\mathrm{dc}}(i_{\mathrm{pv}}+i_{\mathrm{bess}}-i_{\mathrm{dc,inv}}).
\]

La prueba src/validation/test_bat26_42_energy_and_limits.py contiene cinco métodos. Los tres primeros verifican la identidad instantánea para corriente neta positiva, negativa y nula; la contribución incremental de i_bess; y una ventana de corrientes constantes cuya tensión es afín en el tiempo y cuya integral trapezoidal de potencia neta es algebraicamente exacta. Esta última comparación no valida la integración numérica de una simulación completa.

Los otros dos métodos evalúan la reducción de los límites de corriente/potencia con el snapshot de SoH y que la derivada de SoC emplee Qeff sin una segunda pérdida lineal dependiente de z_deg. Se utiliza un Kp deliberadamente elevado para activar saturaciones en una prueba puramente sintética; no es una propuesta de control. Se conservan M=80 y D=1500 en el objeto GFM del ensayo.

**Ejecución local requerida:**

~~~powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s src/validation -p test_bat26_42_energy_and_limits.py -v
~~~

Tras cualquier modificación de las ecuaciones de producción deben repetirse las pruebas previas de RC, enlace DC, adaptador DC/DC, signos, snapshots y las regresiones de BAT26-38. No se modificó el código de producción en esta rama, y no se afirma haber ejecutado pruebas desde GitHub.

## Diferencias entre verificación interna y validación física

La tensión terminal Vt se calcula y reporta como diagnóstico, pero la ruta integrada no utiliza los límites de tensión del adaptador DC/DC algebraico separado. Imponer umbrales arbitrarios sin identificar la pareja 2p y la topología alteraría el baseline sin fundamento. Una conexión física requeriría justificar los números de unidades en serie/paralelo, la transformación de corriente, los límites térmicos y de tensión, y las eficiencias medidas en ambos sentidos. Ninguna de estas evidencias está presente.

La identidad del capacitor DC no constituye un balance físico entre terminal de batería y bus. La misma variable i_bess aparece en el ECM y el enlace DC sin transformar tensiones o corrientes entre puertos. La diferencia entre Vt*i_bess y Vdc*i_bess no puede declararse pérdida del convertidor.

**Conclusión:** el 1RC y las restricciones vigentes son verificables como implementación provisional, y se agrega la prueba energética M10 que faltaba. BAT26-42 permanece en curso hasta ejecutar los cinco tests y las regresiones pertinentes. Incluso si pasan, el cierre se limitaría a software; seguirían pendientes la identificación experimental 1RC, la supervisión real de tensión/temperatura y el acoplamiento físico DC/DC–bus. La rama separada no se fusionará automáticamente.
