# Supuestos simplificados vigentes

Este documento consolida los supuestos activos del baseline para mantener el
README corto y enfocado en ejecución/estado.

## BESS-SLB

- Modelo térmico: no implementado (temperatura constante asumida).
- Degradación: primer orden lineal, sin modelo de rodilla ni efectos no lineales.
- OCV/R1/C1: datos interpolados desde tabla; no incluye histéresis.
- R0 aging: ley empírica simplificada, no copiada textualmente de literatura.
- El BESS-SLB está modelado y validado, pero aún no integrado en la dinámica de la microrred.

## Generador fotovoltaico (baseline actual)

- Se usa el modelo equivalente de un diodo para representar el módulo fotovoltaico.
- El módulo de referencia es el LONGi LR7-54HJD-500M y los datos base provienen de su datasheet oficial en STC.
- Los parámetros tabulados usados como referencia son: Voc, Isc, Vmp, Imp, número de celdas y coeficientes de temperatura.
- Los parámetros no tabulados del modelo de un diodo (n, Rs y Rsh) se estiman mediante ajuste numérico en STC usando únicamente los puntos del datasheet.
- El ajuste de n se restringe a un rango físicamente razonable para silicio (1 <= n <= 2).
- Se imponen Rs > 0 y Rsh > 0; Rsh se acota superiormente para evitar soluciones numéricamente válidas pero poco físicas.
- En esta etapa la validación del modelo PV se realiza solo en STC, comparando Voc, Isc, Vmp e Imp del modelo frente al datasheet.
- No se modelan efectos de sombreado parcial, mismatch entre módulos, suciedad, degradación del módulo FV ni dispersión estadística entre paneles.
- No se implementa un modelo térmico dinámico del módulo; la temperatura de celda se trata como entrada del modelo.
- La curva I-V/P-V del arreglo se obtiene escalando el módulo por el número de módulos en serie y strings en paralelo definidos en config.py.
