# r01 — Verificador A: la matriz de mezcla (W1) y los hallazgos F101–F111 (W2)

## Método
Escribí todo el código en `work/verify/A/`. No importé `src/pminflux_sim` ni usé los scripts `F1xx` para sacar números. Solo leí F104 para copiar la definición del escenario: el N que usa el CRB y la geometría. El legado lo llamé en solo lectura.
- `v_C.py`: C sin IRF, plegando en el período las masas por bin. `v_C_irf_quad.py`: C con IRF por cuadratura 1-D sobre el desplazamiento gaussiano. Esa ruta es independiente de la forma cerrada EMG que usa W1.
- `v_campaign.py`: mi campaña de `sim_exp`, con λ = [0.40, 0.10, 0.20, 0.30], distinto del de W1, y mis propias semillas. Cuento las ventanas con un contador propio y además con `nMINFLUX`; los dos dan conteos idénticos.
- `v_sweep_pred.py` y `v_campaign_reeval.py`: mi predictor a tasa finita. Descompone cada ciclo por patrón de ocupación, con n_k = Nh·q_k, y aplica dos reglas: 'highest' (lo que hace sim_exp) y 'earliest' (MC del mínimo de 12.5k + Exp).
- `v_F104.py`: sesgo asintótico con BFGS continuo y mi propia dona TCP. Calcula el CRB por Fisher con diferencias finitas. `v_F103b.py` hace lo mismo para ventanas sin pliegue.
- `v_findings.py` y `v_F101hi.py`: reproducen F101–F111 y F105/F151/F153/F154.
- Salidas: `v_*.json` y `camp_*.json`.

## 1. Matriz de mezcla
- **C sin IRF** (τ = 4.21, T = 50, K = 4, ventana [0, 10.1]): C_ii = 0.9092021, C[i][i−1] = 0.0466861, C[i][i−2] = 0.0023973, C[i][i−3] = 0.0001231. Cada columna suma 0.9584086. Coincide con W1 en todos los dígitos, y el MC con 2e7 muestras cae dentro de 1 SE.
- **C con IRF gaussiana de 300 ps FWHM**, centrada en el pulso: por cuadratura da C_ii = 0.8973135 y C[i][i−1] = 0.0467075, idéntico a W1. Las columnas suman 0.94654. El MC da 0.897194 ± 6.8e-5, a 1.8 SE.
  - Mi primera versión por convolución discreta difería en 2e-5. Era un artefacto mío: el kernel quedaba asimétrico.
  - Supuesto que hay que declarar: la IRF está centrada en el pulso y la ventana abre en 0. Por eso cae un 1.2 % fuera de todas las ventanas (≈ σ/(τ√2π)).
- **Mi campaña a baja tasa** (λ = [0.4, 0.1, 0.2, 0.3], Ns = 2000):

  | configuración | fotones | mezcla | ingenuo |
  |---|---|---|---|
  | Nb = 400, SBR = 5, M_p = 2e6 (1.2e-3/ciclo) | 3.14e6 | χ² = 2.81, p = 0.42 | χ² = 2780, p = 0 |
  | Nb = 0 | 1.34e6 | p = 0.61 | χ² = 3593 |
  | Nb = 95, M_p = 2.095e6 (1e-3/ciclo) | 2.99e6 | p = 0.69 | χ² = 5773 |

  La conclusión de W1 queda reproducida con otro λ, otra SBR y otras semillas: la mezcla pasa y el ingenuo de la Ec. 3.5 se rechaza sin ambigüedad. No re-corrí su JSON con su semilla (chi² 5.66, p = 0.129), así que no afirmo esos dígitos exactos.
- **Barrido de tasa.** Mi predictor coincide con los números de W1 dentro de 1e-6 en todas las tasas (0.001 a 0.3 y 0.0105), tanto 'highest' como 'earliest' menos la mezcla. También coincide la fracción de ciclos con ≥2 haces (0.36·tasa; 0.123 a 0.3).
  - Con mis datos, sim_exp sigue a 'highest' en todas las tasas: p = 0.79 (1e-3), 0.76 (5e-3, 1.2e7 fotones), 0.77 (0.0105, 1.8e7 fotones) y 0.14 (0.1, 3e6 fotones).
  - Contra la mezcla ideal: p = 0.69, 4.6e-4, 2e-22 y 0. Contra 'earliest': p = 0.53, 1.6e-15, 7e-98 y 0.
  - A 0.3/ciclo, W1 da 'earliest' − mezcla = [+0.0153, +0.0210, −0.0081, −0.0282]; yo obtengo [+0.01532, +0.02104, −0.00812, −0.02824].
  - Un error propio: mi primera corrida a 0.1/ciclo con factor = 1.05 tuvo 74 % de llamadas fallidas. Las llamadas que sobreviven quedan condicionadas y 'highest' dio p = 0.005. La descarté y la repetí con factor = 1.2, sin fallas. Hay que tenerlo en cuenta: a tasas altas, un factor chico sesga por selección.
- **Tamaño del efecto en la configuración de los estudios (0.0105).** Es detectable en conjunto. Por localización de 2000 fotones es ≤ 0.09 SE con el λ de W1 y 0.10 SE con el mío. Entre 1e-3 y 5e-3 el sesgo por ventana va de 1e-4 a 5e-4, es decir ≤ 0.05 SE por localización.
  - **Corrección a W1:** dice que en 1e-3–5e-3 "hacen falta 3e7–2.6e8 fotones" para detectarlo. A 5e-3 lo detecté con 1.2e7 (p = 4.6e-4). N escala como 1/tasa², así que en 5e-3 bastan ~1e7. El 3e7 corresponde a 3e-3.
- **Otras afirmaciones de W1 que reproduje:**
  - La contaminación de la ventana 0 es 8.84 % de fuga y 14.2 % de fondo.
  - El sesgo es lineal en la tasa, ≈ 0.087·tasa en la ventana 3.
  - La configuración literal de los estudios da [−5.29e-4, −6.74e-4, +2.62e-4, +9.41e-4].
  - La fórmula del test de aceptación omite la imagen m = −1 cuando una ventana cruza T. Con K = 3, τ = 8, a = 2, b = 16 faltan 1 − e^(−1.33/8) = 0.153, que confirmé analíticamente. No afecta la configuración de referencia: 37.5 + 10.1 < 50.

## 2. Hallazgos de W2
- **F101: verificado.**
  - A 0.8 fotones/ciclo (60 llamadas, 8e4 fotones), sim_exp coincide con 'highest' (|z| ≤ 1.5) y se aparta de p hasta 47 SE.
  - A 0.0105/ciclo, el 0.379 % de los ciclos ocupados tiene ≥2 haces y el sesgo relativo máximo es 0.461 %.
  - El mecanismo está en l.522–527: `np.nonzero` recorre por filas, así que gana el k más alto. La clase IMPLEMENTACION está bien, y es latente en la práctica.
- **F102: verificado.** relTime tiene 200095 elementos, 198000 de ellos 0.0 exacto. Con a = 0 la ventana 0 cuenta 36.9 fotones y el error medio es 1.25 nm. Con a = −0.25 cuenta 198036.6 y el error medio es 70.0 nm. Las líneas l.517, 569 y 996 son correctas.
- **F103: verificado en el mecanismo, no en un número.**
  - Con b = 13 se cuenta dos veces el 10.9 % de los fotones (τ = 4.21) y el 94.9 % (τ = 0.001).
  - La pérdida **esperada** de la ventana 0 con a = −0.5 es **6.84 %** (τ = 4.21) y **2.54 %** (τ = 0.001). Los 5.9 % y 2.8 % de W2 salen del MC de 30 llamadas. Los valores esperados que reporta W2 (63.45 frente a 68.11) coinciden con los míos, así que solo el porcentaje citado está mal.
  - El "sesgo extra de 0.34 nm" es un desplazamiento entre las dos estimaciones (reproduje 0.338 nm). Con τ = 4.21, el sesgo total con las ventanas del legado es *menor* (0.88 nm) que con ventanas periódicas (1.18 nm): el recorte compensa en parte la fuga. Con τ = 0.001 sí suma 0.063 nm.
- **F104: verificado; todos los números se reproducen de forma independiente.**
  - Setup medido con SBR 21: sesgo 0.848, 1.510, 1.625, 2.694 y 2.364 nm. El CRB de crb_minflux (N = Ns + Nb) va de 0.816 a 1.222 nm. El sesgo es 1.04–2.67 veces ese CRB (0.92–2.45 veces el CRB real).
  - El CRB real es 8.6–13.5 % mayor: la razón va de 1.0859 a 1.1349.
  - La ventana 0 en (5, −5) tiene 45.8 % de fotones de otros haces.
  - Con SBR 6 el sesgo va de 0.585 a 2.323 nm. Con b = 10.1 sin fuga, de 0.011 a 0.478 nm, y la SBR dentro de las ventanas es 26.06. En la configuración de los estudios el sesgo es exactamente 0.
  - La estimación continua en (5, −5) es (5.761, −5.374).
  - **Matices para el reporte:**
    - La causa dominante es la **fuga**. Con b = 12.5 y fuga, el sesgo ya es 1.05–2.78 nm. Que las ventanas no cubran el ciclo (b < T/K) aporta poco.
    - Unos 2.5 puntos del cociente de CRB vienen de los fotones que caen fuera de las ventanas (√(2095/1993.5) = 1.025).
    - Es un sesgo sistemático: en unidades de CRB crece como √N.
  - La clase CONCEPTUAL es defendible: el modelo de la Ec. 3.5 omite la fuga. Pero no cambia ningún número de los estudios, porque usan Tlife = 0.001 (eso es F201 de W3).
  - Las líneas l.1041, 649–661 y 433 (dentro de 423–435) son correctas.
- **F106: verificado.**
  - (−5.07, −7.56) se simula en el nodo (−5, −8).
  - En el nodo con N = 104750, RMSE = 0: el 100 % de las estimaciones cae exacta en el nodo, con CRB 0.115 nm.
  - Fuera del nodo, RMSE/CRB = 3.34 y el error medio es (−0.27, 0.25) nm. W2 da 3.40 y (−0.22, 0.25); la diferencia es de MC. Con N = 2095 en el nodo obtengo 1.11 (W2: 1.09).
- **F107: verificado.** p_minflux pone 51.35 % de los fotones en la mitad apagada.
- **F108: verificado.** Los errores de ángulo son −90, −90, −30, +30 y −90°, leyendo la salida con la convención de `matplotlib.Ellipse`. Los ejes salen siempre 2 y 6.
- **F109: verificado.** La FWHM gaussiana medida es 361 px (se pidieron 250). La rama SW da NameError. Con fov_center (20, 20), el cero de una dona en (0, 0) cae en el índice (120, 120): x tiene el signo opuesto a y.
- **F110: verificado.** Con SBR = inf, la estimación es (−100, 100) y el CRB es NaN en toda la grilla. Con 1e12 la estimación es (5, −5).
- **F111: verificado en parte.**
  - K = 5 y K = 7 dan IndexError con center True y False. Con K = 4 coincide con `beams`.
  - **La afirmación de que "los comentarios de paridad están invertidos" no se sostiene tal como está.** En la rama sin centro los comentarios son correctos. En la rama con centro solo son "incorrectos" si "K" se lee como el número total de haces; si se lee como Kθ = K − 1 (los haces periféricos), son correctos.
- **Descartados:**
  - **F105, confirmado el descarte.** Mi sándwich analítico da σ(Ns, Nb fijos)/σ_CRB = 0.993–1.000 en los 5 puntos de W2 (0–0.71 %). En (40, 0) llega a 0.990.
  - **F151, confirmado.** crb_minflux con px = 1 difiere de mi Fisher continuo en ≤ 4.4e-4 nm.
  - **F152, confirmado lo que chequeé.** El fondo aporta Nb·b/T por ventana, y así se ajustan mis 4 campañas. El muestreo en dos pasos es exacto por factorización multinomial. El pliegue es periódico. No verifiqué la cota de pérdida por haz ≤ 3.6e-4.
  - **F153, confirmado.** Hay 0/20 discrepancias.
  - **F154, confirmado en parte.** Reproduje el ValueError cuando M_p no es múltiplo. No reproduje el 88.5 % ni el χ² p = 0.74.
  - **D-iv, confirmado.** simulations_example.py:47 usa dt = 25, los estudios usan dt = 50, y el docstring dice "6.5" donde es 6.25.
  - **D-ii y D-vi, confirmados.** Lo muestran la corrida de F110 y el hecho de que el 0.0 es la única masa puntual.
- **Autoría.** No se puede verificar en ningún caso. La copia en `GithubPRO/p-minflux-main` tampoco tiene historial git. Lo único que sí se sostiene: el docstring "[Lars]" en `ebp_centres`, y que el comentario "EXACTAMENTE" y el fast path están en el español de la autora, lo que es compatible con lo que dice W2. Todo lo marcado "a confirmar" sigue abierto.

## Qué no resolví
- Los dígitos exactos de `mixing_validation.json` con la semilla de W1: no los re-corrí.
- La media de 2.97 y la varianza de 6.31 del χ² por llamada.
- La cota de ≤ 3.6e-4 de F152.
- El 88.5 % de F154.
- La autoría.

```claims
[{"status":"verified","text":"MIX-C: C periodico sin IRF (tau=4.21, T=50, K=4, [0,10.1]) C_ii=0.9092021, C[i][i-1]=0.0466861, C[i][i-2]=0.0023973, C[i][i-3]=0.0001231, suma de columna 0.9584086 (plegado numerico propio + MC 2e7)"},
 {"status":"verified","text":"MIX-IRF: con IRF gaussiana 300 ps FWHM centrada en el pulso, C_ii=0.8973135, C[i][i-1]=0.0467075, suma de columna 0.94654 (cuadratura propia; MC 0.897194+-6.8e-5). Supuesto a declarar: IRF centrada en el pulso y ventana que abre en 0"},
 {"status":"verified","text":"MIX-VALID: a ~1e-3 fotones/ciclo sim_exp+nMINFLUX es consistente con el modelo de mezcla y rechaza el ingenuo (Ec. 3.5); reproducido de forma independiente con lambda=[0.4,0.1,0.2,0.3]: SBR 5, 3.14e6 fotones, mezcla p=0.42 vs ingenuo chi2=2780; Nb=0 p=0.61 vs 3593; Nb=95 a 1e-3 p=0.69 vs 5773. Los digitos exactos de W1 (chi2 5.66, p=0.129) no se re-corrieron"},
 {"status":"verified","text":"MIX-HIGHEST: el predictor 'gana el k mas alto' (recorte por ranura + sobrescritura) describe sim_exp de 1e-3 a 0.3/ciclo; datos propios: p=0.79 (1e-3), 0.76 (5e-3), 0.77 (0.0105, 1.8e7 fotones), 0.14 (0.1); predictor propio por patrones = numeros de W1 dentro de 1e-6"},
 {"status":"verified","text":"MIX-STUDY: a 0.0105/ciclo (M_p=2e5, Nh=2100) sim_exp se aparta de la mezcla ideal de forma detectable en conjunto (propio: p=2e-22 con 1.8e7 fotones), pero por localizacion de 2000 fotones es <=0.09 SE (lambda de W1) / 0.10 SE (lambda propio); sesgo [-4.58e-4,-6.67e-4,+2.16e-4,+9.09e-4] para el lambda de W1"},
 {"status":"verified","text":"MIX-TRACKING: de 1e-3 a 5e-3/ciclo el sesgo por ventana es 1e-4 a 5e-4, <=0.05 SE por localizacion de 2000 fotones"},
 {"status":"refuted","text":"MIX-NDETECT: 'de 1e-3 a 5e-3 hacen falta 3e7-2.6e8 fotones para detectar el sesgo' — a 5e-3 se detecto con 1.2e7 fotones (mezcla p=4.6e-4, 'highest' p=0.76); N escala ~1/tasa^2, asi que en 5e-3 bastan ~1e7 (3e7 corresponde a 3e-3)"},
 {"status":"verified","text":"MIX-EARLIEST: un TCSPC de primer foton sesga en espejo respecto de sim_exp; a 0.3/ciclo ea-mix=[+0.0153,+0.0210,-0.0081,-0.0282] (propio: +0.01532,+0.02104,-0.00812,-0.02824); los datos de sim_exp rechazan 'earliest' (p=1.6e-15 a 5e-3)"},
 {"status":"verified","text":"MIX-MISC: fraccion de ciclos ocupados con >=2 haces = 0.36*tasa (0.123 a 0.3); sesgo lineal ~0.087*tasa en la ventana 3; contaminacion de la ventana 0 en la configuracion de W1: 8.84 % de fuga y 14.2 % de fondo; configuracion literal de los estudios: [-5.29e-4,-6.74e-4,+2.62e-4,+9.41e-4]"},
 {"status":"verified","text":"MIX-ACCFORMULA: la formula de C del test de aceptacion omite la imagen m=-1 cuando la ventana cruza T (K=3, tau=8, a=2, b=16: falta 1-exp(-1.33/8)=0.153); no afecta la configuracion de referencia"},
 {"status":"verified","text":"F101 (IMPLEMENTACION, l.522-527/464): en un ciclo con >=2 haces sobrevive el k mas alto; a 0.8/ciclo sim_exp coincide con 'highest' (|z|<=1.5) y se aparta de p hasta 47 SE; a 0.0105: 0.379 % de ciclos con >=2 haces, sesgo relativo maximo 0.461 %"},
 {"status":"verified","text":"F102 (IMPLEMENTACION latente, l.517/569/996): relTime trae 198000 ceros de 200095; con a=-0.25 la ventana 0 cuenta ~198037 y el error medio del MLE es 70 nm (1.25 nm con a=0); a=0 funciona solo por la desigualdad estricta"},
 {"status":"verified","text":"F103 (IMPLEMENTACION latente, l.993-997): nMINFLUX no pliega ventanas ni controla solapamiento; con b=13 cuenta dos veces el 10.9 % (tau=4.21) / 94.9 % (tau=0.001) de los fotones; con a=-0.5 la estimacion asintotica se desplaza 0.338 nm (tau=4.21)"},
 {"status":"refuted","text":"F103-num: 'la ventana 0 pierde 5.9 % (tau=4.21) / 2.8 % (0.001)' — la perdida esperada es 6.84 % / 2.54 % (los valores de W2 son MC de 30 llamadas); ademas el '0.34 nm de sesgo extra' es un desplazamiento: con tau=4.21 el sesgo total con las ventanas del legado (0.88 nm) es menor que con ventanas periodicas (1.18 nm)"},
 {"status":"verified","text":"F104 (CONCEPTUAL, l.1041, 649-661, comentario l.433): en el setup medido (tau=4.21, [0,10.1], SBR 21) el sesgo asintotico del MLE de la Ec. 3.5 es 0.85/1.51/1.63/2.69/2.36 nm en las 5 posiciones = 1.04-2.67 veces el CRB de crb_minflux (0.82-1.22 nm); el CRB real es 8.6-13.5 % mayor; la ventana 0 en (5,-5) tiene 45.8 % de fotones de otros haces; SBR 6: 0.59-2.32 nm; solo b=10.1: 0.01-0.48 nm (SBR en ventanas 26.06); configuracion de los estudios: 0. Matices: domina la fuga (con b=12.5 ya da 1.05-2.78 nm); ~2.5 puntos del cociente de CRB vienen de los fotones fuera de las ventanas; no cambia numeros publicados (Tlife=0.001)"},
 {"status":"verified","text":"F106 (DISENO, l.444/93-106/1099): el emisor (-5.07,-7.56) se simula en el nodo (-5,-8); supereficiencia en el nodo (RMSE=0 con N=104750, CRB 0.115 nm); cuantizacion fuera del nodo RMSE/CRB ~3.3-3.4 con sesgo de redondeo ~(-0.25,0.25) nm"},
 {"status":"verified","text":"F107 (IMPLEMENTACION latente, l.454-466/473-491): sim_exp('p_minflux') ignora t_mask; 51.35 % de los fotones en la mitad apagada. Autoria a confirmar"},
 {"status":"verified","text":"F108 (IMPLEMENTACION latente, l.80-90): cov_ellipse usa vec[order] en lugar de vec[:,order]; error del eje mayor -90/-90/-30/+30/-90 grados (convencion matplotlib Ellipse); ejes siempre 2 y 6, sin r2"},
 {"status":"verified","text":"F109 (IMPLEMENTACION latente, l.181-199): la rama gaussiana ignora donut_fwhm (FWHM 361 cuando se piden 250); la rama SW da NameError; fov_center desplaza x con el signo opuesto a y (cero de (0,0) en el indice (120,120) con fov_center (20,20))"},
 {"status":"verified","text":"F110 (IMPLEMENTACION latente, l.1041/1050/649-653): con SBR=inf, pos_MINFLUX devuelve (-100,100) y crb_minflux es NaN en toda la grilla; con 1e12 da (5,-5)"},
 {"status":"verified","text":"F111 (IMPLEMENTACION latente, l.266): ebp_centres da IndexError con K=5 y K=7 (center True y False); con K=4 coincide con beams()"},
 {"status":"refuted","text":"F111-comentarios: 'los comentarios de paridad estan invertidos' — en la rama sin centro son correctos; en la rama con centro solo son incorrectos si K se lee como el total de haces (son correctos para Ktheta=K-1)"},
 {"status":"verified","text":"F105 (descartado): con Ns y Nb fijos la sigma del sandwich es 0-0.71 % menor que el CRB multinomial en los 5 puntos (propio: 0.993-1.000; 0.990 en (40,0)); despreciable"},
 {"status":"verified","text":"F151 (descartado): crb_minflux metodo 1 con px=1 coincide con un Fisher continuo independiente dentro de 4.4e-4 nm; correcto"},
 {"status":"verified","text":"F152 (descartado): el fondo aporta exactamente Nb*b/T por ventana (lo confirman las 4 campanas propias), el muestreo en dos pasos es exacto por factorizacion y el pliegue %dt es periodico para los conteos. No verificada la cota de perdida por haz <=3.6e-4"},
 {"status":"verified","text":"F153 (descartado): spaceToIndex con rint coincide con el minimo de psf() (0/20 discrepancias)"},
 {"status":"unclear","text":"F154 (descartado): se confirma el ValueError cuando M_p no es multiplo de cycle_time/dt; no reproduje el 88.5 % en la ventana 0 ni el chi2 p=0.74 con el haz recuperado del macrotiempo"},
 {"status":"verified","text":"D-iv/D-ii/D-vi (descartados): dt=25 es el setup de 40 MHz de Masullo (simulations_example.py:47) y los estudios usan 50; errata 6.5 en vez de 6.25; el borde estricto solo importa para el 0.0 (F102); NaN->-inf solo es patologico con SBR=inf (F110)"},
 {"status":"unclear","text":"AUTORIA F101-F111: no se puede verificar; no hay historial git (tampoco en GithubPRO/p-minflux-main). Solo se sostiene el docstring [Lars] de ebp_centres y que el comentario 'EXACTAMENTE' y el fast path estan en el espanol de la autora"}]
```
