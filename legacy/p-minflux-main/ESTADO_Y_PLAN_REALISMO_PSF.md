# Estado y plan de mejora de las simulaciones p-MINFLUX

Fecha de revisión: 1 de septiembre de 2026.

## Propósito

Este documento registra el estado de las simulaciones de p-MINFLUX pulsado,
resume la comparación entre los patrones de excitación ideales y medidos, y
define una estrategia reproducible para generar donas simuladas más cercanas a
las experimentales. El texto puede utilizarse como base para la sección de
métodos, validación o discusión de una tesis doctoral, pero los valores finales
deben recalcularse con el conjunto completo de calibraciones.

## Estado actual del código

El análisis principal se encuentra en `simulation_misalignment.py`. El programa
compara tres patrones de excitación (EBP):

1. `ideal`: donas analíticas circulares y geometría equilátera.
2. `geom_exp`: donas analíticas circulares colocadas en las posiciones medidas.
3. `exp`: mapas de intensidad experimentales cargados desde archivos NumPy.

Esta separación es conceptualmente valiosa porque permite distinguir el efecto
de la geometría del patrón del efecto de la forma real de las PSFs. La misma
grilla, posición del emisor y estadística de fotones se utiliza en todos los
casos. También se distingue entre un estimador honesto, que conoce el EBP que
generó los fotones, y uno ingenuo, que supone un patrón diferente.

Las PSFs representativas están en `C:\Data\psf\20260820`. Son cuatro arreglos
de 400 x 400 píxeles, con píxel de 1 nm y campo de 400 nm. Según las notas del
experimento corresponden a una medición con una perla de 20 nm; la localización
experimental informada fue (-5,07, -7,56) nm con 2000 fotones.

## Resultado del diagnóstico

La geometría medida es muy próxima a la ideal. Después de centrar el haz 0, las
posiciones son aproximadamente:

| Haz | x (nm) | y (nm) | distancia al haz 0 (nm) |
|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 |
| 1 | -44 | -27 | 51,62 |
| 2 | 45 | -26 | 51,97 |
| 3 | -5 | 51 | 51,24 |

El tamaño efectivo es 103,23 nm y la asimetría geométrica es sólo 0,30 nm. Por
lo tanto, la diferencia principal entre simulación y experimento no proviene
del triángulo de posiciones.

El ajuste radial existente arroja un parámetro FWHM medio de 343,9 nm, que
equivale a un radio de anillo de 206,5 nm. Sin embargo, la intensidad mínima
experimental representa aproximadamente 9,0 %, 8,7 %, 10,4 % y 11,0 % del
máximo para los haces 0 a 3. La dona analítica, en cambio, tiene un cero
perfecto. Además, las imágenes experimentales exhiben fondo inclinado,
asimetría angular y diferencias entre haces que desaparecen al promediar
radialmente.

En la corrida registrada con 2000 fotones de señal y 95 de fondo, el CRB cerca
del emisor fue aproximadamente 0,87 nm para el patrón ideal, 0,88 nm al usar la
geometría medida con donas perfectas y 2,00 nm para las PSFs experimentales. La
geometría por sí sola tiene, en este ejemplo, un efecto pequeño; el pedestal y
la forma de las donas reducen considerablemente la información espacial.

Los logs corresponden a corridas realizadas con configuraciones diferentes y
no deben combinarse como una única tabla cuantitativa. Antes de incorporar
números definitivos a la tesis se debe guardar junto a cada resultado la
configuración completa, la semilla y la versión del código.

## Interpretación física del fondo

Conviene separar dos contribuciones:

- El pedestal de la PSF o intensidad residual en el mínimo es excitación óptica
  correlacionada con el pulso. Debe formar parte de la PSF de señal.
- `Nb` representa fondo temporal no correlacionado, distribuido entre las
  ventanas TCSPC.

Incluir ambos no constituye necesariamente un doble conteo. Sí sería un error
interpretar todo el pedestal de la PSF medida como fondo uniforme y volver a
sumarlo mediante `Nb`. Esta distinción debe verificarse experimentalmente con
mediciones sin fluoróforo o fuera de la muestra.

## Modelo paramétrico propuesto

Para cada haz se propone:

    I_k(x,y) = B_k(x,y) + A_k D_k(x,y)

`D_k` es una dona elíptica y rotada, con centro subpíxel, anchos independientes
en sus ejes y un pedestal no nulo. `B_k` representa el fondo espacial mediante
un plano o, si los residuos lo justifican, un polinomio cuadrático. Una segunda
etapa puede incorporar armónicos angulares de orden 1 y 2 para representar coma
y astigmatismo residual sin copiar el ruido píxel a píxel.

El ajuste debe efectuarse en dos dimensiones. El perfil radial actual sigue
siendo útil para inicializar el ancho, pero no identifica orientación,
elipticidad, gradiente ni aberraciones angulares.

## Plan de implementación

1. Ajustar cada PSF en 2D y estimar amplitud, pedestal, centro subpíxel, FWHM en
   dos ejes, orientación y gradiente de fondo.
2. Construir un EBP paramétrico realista sobre la misma grilla.
3. Generar una escalera de modelos: ideal; geometría medida; ancho individual;
   pedestal; elipticidad; fondo estructurado; PSF experimental completa.
4. Comparar cada etapa mediante error de imagen en la región de operación,
   razón mínimo/máximo, elipticidad, gradiente, CRB, sesgo y RMSE Monte Carlo.
5. Guardar parámetros y métricas en formatos legibles por máquina, además de
   figuras comparativas.
6. Repetir el ajuste sobre varias perlas o calibraciones. Reportar distribución
   e incertidumbre de los parámetros, no sólo un ejemplo representativo.

## Extensiones de adquisición recomendadas

Para una simulación integral más realista se recomienda sortear `Ns` y `Nb`
como variables Poisson, permitir distinta potencia entre haces y variación del
SBR entre localizaciones, e incorporar drift, blinking, IRF y lifetime medidos.
La PSF óptica simulada debería convolucionarse con el tamaño finito de la perla
cuando se compara contra la calibración. El ruido de una imagen de calibración
no debe copiarse como si fuera una propiedad física de cada localización; su
efecto se representa mejor como incertidumbre de los parámetros ajustados.

## Criterio de validación

Un modelo se considerará útil si reproduce simultáneamente las imágenes en la
región de operación, la profundidad del mínimo, las probabilidades relativas de
los cuatro haces y el CRB experimental. La mejora visual por sí sola no es
suficiente. También debe comprobarse que, cuando el generador y el estimador
usan el mismo EBP, el Monte Carlo converge al CRB dentro de la incertidumbre de
muestreo, y que los resultados son estables frente a cambios razonables en el
radio de ajuste.

## Implementación realizada

El 2 de septiembre de 2026 se incorporó `tools/realistic_ebp.py`. El módulo
implementa el refinamiento cuadrático local del mínimo, el ajuste robusto 2D,
la reconstrucción paramétrica, las etapas parciales del modelo y las métricas
de imagen. El centro se estima primero en una ventana local para impedir que el
gradiente a gran escala desplace artificialmente la dona.

Se agregó `analyze_realistic_psf.py`, que ejecuta el flujo reproducible completo
y guarda:

- `fit_parameters.json` y `fit_parameters.csv`;
- `comparison_metrics.csv`;
- `model_stages.png`.

El script principal `simulation_misalignment.py` incorpora además el caso
opcional `realistic_fit`, con estimadores honesto e ingenuo. Puede desactivarse
mediante `INCLUDE_REALISTIC_FIT = False`.

El Monte Carlo del nuevo análisis precomputa los mapas de log-probabilidad sólo
dentro del radio de búsqueda. Se comprobó que entrega exactamente el mismo
máximo que `pos_MINFLUX`, pero la corrida de 300 muestras pasó de decenas de
minutos a aproximadamente 22 segundos en el equipo de desarrollo.

## Resultados de la implementación sobre la calibración 20260820

Con ROI de imagen de 80 nm, 2000 fotones de señal, 95 de fondo, 300 muestras y
semilla 20260901 se obtuvo:

| Modelo | RMSE medio de imagen | mínimo/máximo medio | CRB en el emisor (nm) | RMSE honesto (nm) |
|---|---:|---:|---:|---:|
| Geometría medida | 0,0906 | 0 | 0,839 | 0,912 |
| Ancho individual | 0,0907 | 0 | 0,838 | 0,931 |
| Más pedestal | 0,0359 | 0,0884 | 1,760 | 1,819 |
| Más elipticidad | 0,0289 | 0,0884 | 2,428 | 2,484 |
| Más fondo y amplitud | 0,0220 | 0,0990 | 2,348 | 2,392 |
| Experimental | 0 | 0,0976 | 2,156 | 2,204 |

El pedestal produce la mayor mejora de semejanza y el mayor cambio inicial del
CRB. La elipticidad y el fondo estructurado explican otra fracción relevante.
El modelo compacto final reproduce bien la profundidad del mínimo y aproxima
el CRB experimental, aunque conserva un error de imagen de 2,2 %.

El uso de la geometría perfecta como estimador de datos generados por el modelo
realista produjo un RMSE de aproximadamente 9,66 nm; para las PSFs
experimentales completas fue 35,58 nm. Esta diferencia indica que el residuo no
explicado por el modelo paramétrico todavía contiene estructura espacial capaz
de generar sesgo. Por ello los valores ajustados de elipticidad deben
interpretarse inicialmente como parámetros efectivos, no como una medición
aislada de aberraciones ópticas.

Los resultados reproducibles se encuentran en `Resultados/realistic_psf`.
Para regenerarlos desde la raíz del proyecto:

    py analyze_realistic_psf.py --samples 300 --output Resultados\realistic_psf

## Trabajo experimental pendiente

La implementación cubre el ajuste, la escalera de modelos, las métricas, CRB y
Monte Carlo para la calibración disponible. La generalización estadística a
varias perlas queda pendiente porque en el conjunto accesible sólo hay una
calibración representativa. Cuando se incorporen más carpetas, se deben repetir
los ajustes sin cambiar hiperparámetros y reportar media, dispersión e
intervalos de confianza por parámetro.
