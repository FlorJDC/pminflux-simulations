# r02 — Verificador: simulador (W2), estimador (W3) y findings.json (W1)

Todo el código propio está en `work/verify/r02/`. Mis números salen de un simulador fotón por fotón
propio (`mysim.py`) y de un estimador propio (`myest.py`). Ninguno de los dos importa `pminflux_sim`.
`simulate.py` y `estimate.py` solo se importan cuando lo que se prueba es su comportamiento, es
decir, la afirmación misma. `mixing.py` (verificado en R1) se usa solo como control cruzado de mi C
(coincide a ≤1e-16) y como el predictor `sim_exp_window_probs` de R1.

## Cómo funciona mi simulador (una ruta distinta de la de W2)
- Genero un único flujo largo de `n_cycles` ciclos.
- Fotones de señal: el total sale de Poisson(tasa·fs·n_cycles). Cada fotón toma un ciclo uniforme
  y un haz ~ q, y llega en `t = ciclo·T + j·T/K + N(0,σ) + Exp(τ)`.
- Fondo: uniforme en el tiempo absoluto.
- Ordeno todo por tiempo absoluto y lo recorro en un bucle **secuencial** por fotón (numba):
  - `earliest`: tiempo muerto no paralizable, que dispara cualquier avalancha. El TCSPC registra
    la primera avalancha del ciclo de llegada.
  - `highest`: por ciclo de excitación queda 1 fotón de señal, del haz más alto; el fondo va aparte.
  - `none`: se registran todos los fotones.
- Recorto 20 ciclos en cada borde.
- C propia: serie de CDFs `exponnorm` de scipy.

## (1) Simulador en dominio temporal (W2)

**Tasa baja (1e-3/ciclo, earliest, d = 22)** (`v1_lowrate.py`):
- Mi simulador contra mi modelo de mezcla, con ~1.5e6 fotones en ventanas:
  - IRF 0.3: p = 0.74.
  - Sin IRF: p = 0.96.
  - `none` con λ = [.4, .1, .2, .3]: p = 0.30.
  - El ingenuo da χ² de 3e3 a 1.6e6, con p = 0.
- Ventanas periódicas, todas con IRF 0.3:
  - a = −0.5, b = 10.1: p = 0.91.
  - (2, 12), que cruza T: p = 0.74.
  - (−1.5, 12.5): p = 0.39.
- `simulate.py` en las mismas 6 configuraciones da p_mezcla = 0.72 / 0.14 / 0.56 / 0.037 / 0.43 / 0.30.
- El test de dos muestras mío contra v2 da p = 0.65 / 0.30 / 0.29 / 0.15 / 0.47 / 0.28.
- **Verificado.**

**Algoritmo de tiempo muerto:**
- Tomé el `_recorded_earliest` de v2 (punto fijo vectorizado) y lo comparé con mi bucle secuencial
  sobre los **mismos** tiempos de llegada.
- Configuraciones: 1800 filas × 400 fotones, d ∈ {0, 5, 22, 35, 49.99, 50, 75, 100, 300}, tasas
  0.01–30/ciclo.
- Resultado: 0 filas distintas, también con cadenas de conflicto largas.

**Tasa alta, emulaciones** (`v3_highrate.py`, 3.3e6–4.5e6 fotones por brazo):
- `highest` a 0.3/ciclo contra el predictor `sim_exp` de R1:
  - Con IRF 0.3: el mío da p = 0.17, v2 da p = 0.86 y el test de dos muestras da p = 0.65.
  - Sin IRF: el mío da p = 0.63, v2 da p = 0.68.
  - Ideal y earliest dan p = 0 en los dos simuladores.
- `earliest` con d = 0 contra el predictor 'earliest':
  - τ = 1.5 a 0.3/ciclo: p = 0.54 (mío) y 0.45 (v2).
  - τ = 1.0 a 0.2/ciclo: p = 0.81 y 0.04.
- Con τ = 4.21 a 0.1/ciclo, **mi simulador independiente también se aparta** del predictor:
  - La desviación es [+1.36e-3, −5.8e-4, −2.5e-4, −5.2e-4] (p = 5e-7). v2 da [+0.95e-3, …].
  - El test de dos muestras mío contra v2 da p = 0.68.
  - A 0.02/ciclo ya no hay diferencia (p = 0.45).
- Esto confirma la explicación de W2: la competencia ocurre en el ciclo de llegada, no en el de
  excitación.

**Conteo legado F102/F103** (`v4_legacy.py`, cuadratura propia exacta, MC propio y v2):
- Pérdida esperada de la ventana 0 con a = −0.5, b = 12.5: **6.842 % / 2.535 %**.
  - Eso confirma los 6.84 / 2.54 de R1.
  - Los 6.81 ± 0.07 y 2.46 ± 0.06 de W2 están a 0.4 y 1.3 SE.
- Doble conteo esperado con b = 13 y τ = 4.21: **11.175 %**. Lo confirma mi MC de 1.05e8 fotones,
  que da 11.173 ± 0.003 %.
  - v2 con 1.05e7 fotones da 11.174 ± 0.010 %, así que v2 no tiene sesgo.
  - El 11.11 % del reporte es la semilla 51, con 8.4e5 fotones, que está 1.9 SE abajo.
  - La referencia del test, **11.15 %, está corrida 0.025 puntos**. El valor exacto es 11.175 %.
    El error es menor y el test pasa igual, pero conviene corregir el número citado.
- Con τ = 0.001 el doble conteo esperado es 94.95 %, y W2 da 94.93 %.
- F102: v2 da 99.0 % de los conteos en la ventana 0 y 198 344 ceros por localización. Lo esperado
  analíticamente es 198 480 ± ~300 (ciclos hasta N − señal registrada).

**Barrido de tiempo muerto** (`v2_deadtime.py` con ~1.1e7 fotones por caso, y `v2b_twosample.py`
con 4e7 por brazo):

*La afirmación "el sesgo desaparece con d = 50/100 y vuelve con 35/75" está verificada, y tiene
una explicación exacta.* Con un SPAD no paralizable y d ≥ T:
- En una ventana de largo d cabe como máximo una avalancha. Entonces
  P(muerto en t) = ∫_{t−d}^{t} r(s) ds, donde r es la tasa periódica de avalanchas.
- Con d = n·T esa integral es n × (avalanchas por período), una constante que no depende de la fase.
- Por eso la densidad registrada es ρ(t) = λ(t)(1 − const) ∝ λ(t) **exactamente, a cualquier tasa**:
  el sesgo es cero.
- Si d ≥ T, el TCSPC de 1 por ciclo ya queda implícito.
- Con d = 75 = 1.5T la integral depende de la fase. Con d < T el bloqueo es
  [min(inicio del ciclo, t − d), t) y también depende de la fase.
- La hipótesis de W2 ("un bloqueo de n·T cubre todas las fases por igual") es correcta. Además es
  exacta, no solo de primer orden. No aplica a un detector paralizable ni a un TDC con tiempo muerto
  propio.

Predictor de primer orden propio contra MC (sesgo en SE por localización, a 0.0105/ciclo):

| d (ns) | predicho | mío (4e7) | v2 (4e7) | dos muestras p |
|---|---|---|---|---|
| 0 | [.039,.103,−.023,−.104] | [.045,.090,−.004,−.112] | [.040,.091,−.018,−.096] | 0.33 |
| 35 | [−.001,.038,.011,−.053] | [.009,.030,.003,−.040] | [.000,.033,.015,−.052] | 0.45 |
| 50 | 0 exacto | máx 0.009 (p = 0.88) | máx 0.010 (p = 0.82) | — |
| 75 | [.006,.053,−.018,−.041] | [.005,.047,−.016,−.036] | [.003,.046,−.017,−.034] | 0.99 |
| 100 | 0 exacto | máx 0.011 (p = 0.74) | máx 0.019 (p = 0.43) | — |

- A 2.5e-3/ciclo el sesgo predicho es 0.025 SE (d = 0) y 0.022 SE (d = 22). Con `highest`, el
  predictor de R1 da 0.023.
- Por lo tanto, el "≤0.06 SE a ≤2.5e-3" de W2 es una cota correcta. Parte de ella es ruido del MC
  (SE 0.018): el sesgo real es ≈0.025 SE.
- Los signos opuestos de highest y earliest en los haces 1 y 3 quedan verificados.

**Rendimiento:** 2e4 × 2000 fotones con los parámetros por defecto tardan 17.4 s, o sea 2.3e6
fotones/s. Extrapolado a 1e5 × 2000 da 87 s, contra los 96.5 s medidos por W2. Verificado.

`python -m unittest tests.test_simulate tests.test_estimate tests.test_mixing` da 44 OK.
`discover` da 50 tests con 1 error, que es el esperado (falta `report/index.html`). El sha de
`test_acceptance.py` no cambió.

## (2) Estimador (W3)

**Reproducción de la tabla completa** (`v5_compare.py`):
- Los 20 casos, con mi simulador (earliest, 2.5e-3, d = 22), mi MLE vectorizado (grilla del disco
  más Newton con derivadas por diferencias finitas), mis CRB y **otra semilla**. n_loc = 2000.
- CRB de la mezcla y crb_minflux: **idénticos a los de la tabla en los 20 casos**, a 3 decimales.
  Por ejemplo 0.926/0.816 y 1.105/1.010.
- Sesgo asintótico del legado:
  - IRF 0, SBR 21: 0.848/1.510/1.625/2.694/2.364.
  - IRF 0, SBR 6: 0.585/0.729/1.664/2.323/1.933.
  - IRF 0.3: 0.875/1.545/1.647/2.740/2.406 y 0.577/0.749/1.688/2.367/1.985.
  - F104 queda reproducido y coincide con la tabla al tercer decimal.
- Legado en MC: |b| de 0.556 a 2.712 y RMSE/CRB de 1.110 a 2.052. La tabla dice 1.115–2.059.
  - El peor caso es (−15, 15), SBR 21, IRF 0.3: 2.052 mío contra 2.059 de la tabla.
- Mezcla: RMSE/CRB de **0.971 a 1.033**, contra 0.985–1.022 de la tabla. |b| ≤ 0.10 nm.
- Cociente CRB_mezcla/crb_minflux:
  - Da **1.0859–1.1349 solo en SBR 21 con IRF 0** (el setup de F104).
  - En los 20 casos el rango es 1.068 (SBR 6) a 1.144 (SBR 21, IRF 0.3).
  - La afirmación vale como está escrita solo para ese setup.

**Hallazgo lateral de W3** (`v6_residual_bias.py`, 20 000 localizaciones por fuente):
- La desviación relativa ~1e-3 de las fracciones, con déficit en la ventana 3, se **confirma**:
  - Mi MC da −0.9e-3 a −1.0e-3 en w3.
  - El primer orden da −0.7e-3 a −1.0e-3.
  - Con d = 50 o con `none` desaparece.
- El sesgo de posición que eso induce es chico:
  - Primer orden: |b| ≈ 0.02–0.035 nm.
  - MC, earliest d = 22 contra multinomial: Δbx ≈ +0.02 nm.
- Por lo tanto, "≤0.11 nm" es una cota verdadera pero ~3 veces holgada. El 0.092 ± 0.023 de
  (20, 0) SBR 6 es ~0.03 real más una fluctuación de 2.6σ.
- La conclusión "no viene del estimador" es **parcialmente falsa**. En (0, −30) SBR 21 el MLE de
  mezcla tiene by = −0.036 ± 0.011 nm **sobre datos multinomiales puros**. Eso es el sesgo O(1/N)
  propio del MLE con N ≈ 2000, no un bug.
  - El −0.05 a −0.10 en y que aparece en (0, −30) en las 4 filas de la tabla (y en las mías) viene
    sobre todo de ese sesgo.
  - Es ≤0.03 CRB y no cambia ninguna conclusión.

**F202** (`v7_F202.py`, datos multinomiales propios, con los mismos 5 puntos × 300 y las potencias
[21.02, 16.65, 22.96, 22.86]):
- Sesgo con el modelo de potencias iguales: asintótico 6.17/5.99/7.83/2.60/7.72 nm, MC
  6.09/5.96/7.79/2.58/7.54 nm. Da **2.6–7.8 nm**, frente al 2.6–7.9 de W3.
- Con las potencias conocidas: ≤0.14 nm.
- Con potencias compartidas libres (mi verosimilitud perfilada con Nelder–Mead sobre 3 log-cocientes):
  - Las potencias se recuperan con un error ≤0.8 %.
  - El sesgo queda en ≤0.17 nm (W3 dice ≤0.5).
- Con una sola posición no es identificable: 3 grados de libertad en las probabilidades contra
  5 parámetros.
- **Verificado.**

**F108 y F110** (comportamiento de `estimate.py`):
- `cov_ellipse`, en 30 covarianzas con φ en {0, 30, 60, 90, 120, 150, −45, ±89.9, 179}° y
  anisotropías 9/1, 4/3.9 y 1/0.01:
  - El error de ángulo es ≤6e-14°.
  - Los puntos del borde de la elipse que devuelve tienen Mahalanobis² = r2 (≤6e-14).
  - La convención queda declarada: nsig = 1 da la región 2D del 68.3 %, con r2 = 2.30, y no ±1σ
    por eje.
- F110: con `sbr = inf`, `forward_probs`, `crb` (0.899/0.900/1.091 nm, también sobre el cero en
  (0, 0)), `mle_mixing` y `mle_legacy` dan resultados finitos. El sesgo es (−0.008, −0.002) nm.
- `psf.beam_positions(4, 100, center=True)` es idéntico a mi geometría.
- **Verificados.**

`compare_legacy_vs_v2.json`: `source = v2sim`. Los sha256 de simulate y estimate coinciden con los
archivos actuales.

## (3) findings.json

**F205: el sentido queda resuelto** (`v9_F205.py`, MLE de grilla propio, 1e5 muestras, pixel (−5, −8)):
- Ideal: el RMSE por eje **contra R0**, como lo calcula analyze_realistic_psf.py:88, es **0.962**.
  **Contra el píxel simulado** es **0.913**.
- Geometría: 0.948 contra R0 y 0.898 contra el píxel.
- Entonces **0.912 es el valor correcto** (contra el emisor realmente simulado). **0.960 es el que
  produce el script legado**, inflado por el desplazamiento de 0.4455 nm: (0.431² − 0.017²)/2 ≈ 0.090 nm².
- "Pasa de 0.912 a 0.960" describe la inflación (correcto → legado). No es una corrección
  (reportado → corregido).
- Fuente probable de la confusión: el `comparison_metrics.csv` de la autora trae
  `honest_rmse_nm = 0.9122` en la etapa *geometry*. Ese número es un MC chico de la cantidad
  **inflada**, cuyo valor esperado es 0.948 (SE ≈ 0.037 con 300 muestras). Que coincida con 0.912
  es casualidad.
- Texto recomendado para el HTML: "el RMSE se calcula contra R0 (l.88): en el ideal da 0.960 nm,
  contra 0.912 nm respecto del píxel realmente simulado (0.948 contra 0.898 en la geometría medida)."

**v2_test:**
- Las 16 entradas nombran 17 ids distintos entre `v2_test` y `v2_tests`. Todos existen, y
  `python -m unittest <los 17>` da 17 OK en 23 s.
- F107 tiene `v2_test: null`, como estaba previsto.
- Una observación: F205 apunta a `test_continuous_offgrid_no_quantization`. Ese test cubre la no
  cuantización (el núcleo de F106/F205), pero no la referencia del RMSE.

## Lo que no verifiqué de forma independiente
- `n_mode='poisson'`, los intervalos KS del tiempo muerto con d > T y el b/T del fondo en ventanas
  con a < 0. Sus tests pasan, pero no los reproduje por otra ruta. El b/T del fondo queda cubierto
  indirectamente por la coincidencia de la mezcla con SBR 21 y ventanas con a < 0.
- β libre, F203 (fracción en el borde) y el control cruzado con ts.pos_MINFLUX de W3.
- Limitación de `highest` con fondo a tasa alta: v2 fija el SBR **incidente**, y la señal
  registrada se recorta a (1 − e^{−x})/x. sim_exp, en cambio, fija Ns:Nb registrados. A 0.0105/ciclo
  el efecto es 0.5 % del SBR (despreciable). A 0.3/ciclo con fondo sería ~14 %. Los tests de
  `highest` usan sbr = inf, así que no se ven afectados.

```claims
[{"status":"verified","text":"W2-R2 simulate.py a 1e-3/ciclo (earliest, dead_time 22) coincide con el modelo de mezcla y rechaza el ingenuo: simulador propio fotón por fotón (ruta independiente) p=0.74 (IRF 0.3) / 0.96 (sin IRF) / 0.30 (none) con ~1.5e6 fotones, ingenuo p=0; v2 en las mismas configuraciones p=0.72/0.14/0.56; dos muestras propio vs v2 p=0.29-0.65"},
 {"status":"verified","text":"W2-R2 ventanas periódicas con IRF 0.3: a=-0.5,b=10.1 / (2,12) cruzando T / (-1.5,12.5): propio p=0.91/0.74/0.39, v2 p=0.037/0.43/0.30, dos muestras p=0.15/0.47/0.28"},
 {"status":"verified","text":"W2-R2 el tiempo muerto no paralizable + TCSPC primer fotón de simulate._recorded_earliest (punto fijo vectorizado) es idéntico a un bucle secuencial propio en 1800 filas x 400 fotones, d en {0..300} ns y tasas 0.01-30/ciclo (0 discrepancias)"},
 {"status":"verified","text":"W2-R2 tcspc='highest' reproduce el predictor sim_exp de F101 a 0.3/ciclo (propio p=0.17/0.63, v2 p=0.86/0.68 con IRF 0.3/0; ideal y earliest p=0); earliest d=0 coincide con el predictor 'earliest' con tau=1.5 a 0.3/ciclo y tau=1.0 a 0.2/ciclo, y con tau=4.21 a 0.1/ciclo se aparta ~1e-3 en fracción (propio +1.36e-3 en w0, p=5e-7; v2 igual, dos muestras p=0.68) por la competencia en el ciclo de llegada; desaparece a 0.02/ciclo"},
 {"status":"verified","text":"W2-R2 conteo legacy F103: pérdida de ventana 0 con a=-0.5,b=12.5 esperada 6.842 % (tau 4.21) / 2.535 % (0.001) por cuadratura propia; los 6.81±0.07 / 2.46±0.06 de v2 son consistentes; F102: v2 con a=-0.25 da 99.0 % en la ventana 0 y 198344 ceros/loc (esperado 198480±~300)"},
 {"status":"refuted","text":"W2-R2 'el valor esperado del doble conteo con b=13, tau=4.21 es 11.15 %' (referencia del test) — el exacto es 11.175 % (cuadratura propia 0.111746; MC propio 1.05e8 fotones 11.173±0.003 %; v2 1.05e7 fotones 11.174±0.010 %, sin sesgo); el 11.11 % reportado es la semilla 51 (8.4e5 fotones, -1.9 SE). Error menor de 0.025 puntos; el test pasa igual"},
 {"status":"verified","text":"W2-R2 barrido de tiempo muerto: el sesgo 'earliest' desaparece exactamente para dead_time = n*T (50, 100 ns) a cualquier tasa — prueba: con SPAD no paralizable y d>=T cabe <=1 avalancha en una ventana de largo d, P(muerto en t)=int_{t-d}^{t} r(s)ds = n*(avalanchas por período) = constante, así que la densidad registrada es proporcional a lambda(t); con d=35 y 75 ns vuelve (a 0.0105/ciclo, predicho a primer orden [-.001,.038,.011,-.053] y [.006,.053,-.018,-.041] SE/loc; MC propio 4e7 [.009,.030,.003,-.040] y [.005,.047,-.016,-.036]; v2 4e7 coincide, dos muestras p=0.45/0.99); d=50/100: propio y v2 p=0.43-0.88"},
 {"status":"verified","text":"W2-R2 sesgo por ventana contra la mezcla ideal <=0.11 SE/loc a 0.0105/ciclo (d=0: predicho [.039,.103,-.023,-.104], propio [.045,.090,-.004,-.112]) y <=0.06 SE a <=2.5e-3/ciclo (el sesgo real predicho es ~0.025 SE; el resto es ruido del MC); highest y earliest con signos opuestos en los haces 1 y 3"},
 {"status":"verified","text":"W2-R2 rendimiento: simulate_counts con los parámetros por defecto da 2.3e6 fotones/s (2e4x2000 en 17.4 s, extrapolado a 1e5x2000 en 87 s; W2 midió 96.5 s)"},
 {"status":"verified","text":"W2/W3-R2 python -m unittest tests.test_simulate tests.test_estimate tests.test_mixing: 44 OK; discover: 50 tests, solo falla test_html_report_covers_every_finding (falta report/index.html, esperado); sha de test_acceptance.py intacto"},
 {"status":"verified","text":"W3-R2 sesgo asintótico del legado (Ec. 3.5) en el setup medido reproduce F104 con código propio: IRF0 SBR21 0.848/1.510/1.625/2.694/2.364 nm, SBR6 0.585/0.729/1.664/2.323/1.933; IRF 0.3: 0.875/1.545/1.647/2.740/2.406 y 0.577/0.749/1.688/2.367/1.985 (igual a la tabla al tercer decimal)"},
 {"status":"verified","text":"W3-R2 tabla compare_legacy_vs_v2 reproducida en los 20 casos con simulador, MLE y CRB propios y otra semilla: CRB_mezcla y crb_minflux idénticos a 3 decimales; legado |b| 0.556-2.712 nm, RMSE/CRB 1.110-2.052 (peor caso (-15,15) SBR21 IRF0.3: 2.052 vs 2.059); MLE de mezcla RMSE/CRB 0.971-1.033, |b|<=0.10 nm"},
 {"status":"verified","text":"W3-R2 CRB_mezcla/crb_minflux = 1.0859-1.1349 en el setup de F104 (SBR 21, IRF 0); en los 20 casos el rango es 1.068 (SBR 6) - 1.144 (SBR 21, IRF 0.3)"},
 {"status":"verified","text":"W3-R2 hallazgo lateral: a 2.5e-3/ciclo con TCSPC earliest (d=22) las fracciones por ventana se desvían ~1e-3 relativo de window_probs con déficit en la ventana 3 (MC propio -0.9e-3 a -1.0e-3 en w3; primer orden -0.7e-3 a -1.0e-3; desaparece con d=50 o tcspc none); es física de tasa finita, no un bug"},
 {"status":"refuted","text":"W3-R2 'el sesgo MC del MLE de mezcla en v2sim coincide con el sesgo implícito de las fracciones, así que no viene del estimador; <=0.11 nm' — el sesgo inducido por la tasa finita es ~0.02-0.035 nm (primer orden y MC con 20000 locs: +0.02 nm en x frente a multinomial); en (0,-30) SBR21 el MLE tiene by=-0.036±0.011 nm también con datos multinomiales puros (sesgo O(1/N) del MLE a N~2000, no un bug); el 0.092±0.023 de (20,0) SBR6 es ~0.03 real más una fluctuación de 2.6 sigma. La cota <=0.11 nm es verdadera pero ~3 veces holgada; todo es <=0.03 CRB"},
 {"status":"verified","text":"W3-R2 F202 en v2: con potencias [21.02,16.65,22.96,22.86] el modelo de potencias iguales se sesga 2.6-7.8 nm (asintótico propio 6.17/5.99/7.83/2.60/7.72; MC 300 locs 6.09/5.96/7.79/2.58/7.54); con potencias conocidas <=0.14 nm; con potencias compartidas libres (perfilado propio sobre 5 posiciones x 300) las potencias se recuperan a <=0.8 % y el sesgo queda en <=0.17 nm"},
 {"status":"verified","text":"W3-R2 F108 corregido: estimate.cov_ellipse da ángulo exacto (error <=6e-14 grados en 30 covarianzas, incluidas casi isótropas y casi degeneradas) y los puntos del borde tienen Mahalanobis^2 = r2 = chi2.ppf(0.683,2) = 2.30 (convención: región 2D del 68.3 %, no ±1 sigma por eje)"},
 {"status":"verified","text":"W3-R2 F110 corregido: con sbr=inf forward_probs, crb (0.899/0.900/1.091 nm en (5,-5),(0,0),(20,0)), mle_mixing y mle_legacy son finitos; el MLE de mezcla sin sesgo (-0.008,-0.002 nm, 200 locs)"},
 {"status":"verified","text":"W1-R2 F205, sentido resuelto: analyze_realistic_psf.py:88 calcula el RMSE contra R0=(-5.07,-7.56); con 1e5 muestras (MLE de grilla propio) da 0.962 nm en el ideal (0.948 en la geometría), mientras que contra el píxel realmente simulado (-5,-8) da 0.913 (0.898). 0.912 es el valor correcto y 0.960 el que produce el script legado (inflado por el desplazamiento de 0.4455 nm); 'pasa de 0.912 a 0.960' describe la inflación, no una corrección. El honest_rmse_nm=0.9122 (etapa geometry) del CSV de la autora es un MC chico de la cantidad inflada (esperado 0.948, SE~0.037); que coincida es casualidad"},
 {"status":"verified","text":"W1-R2 findings.json: los 17 ids distintos de v2_test/v2_tests de las 16 entradas existen y pasan (python -m unittest: 17 OK); F107 tiene v2_test null; compare_legacy_vs_v2.json tiene source v2sim y sha256 de simulate/estimate iguales a los archivos actuales"},
 {"status":"unclear","text":"W2-R2 n_mode='poisson' (media/varianza), los intervalos KS del tiempo muerto con d>T, beta libre, la fracción en el borde de F203 y el control cruzado con ts.pos_MINFLUX — sus tests pasan pero no los reproduje por otra ruta"},
 {"status":"unclear","text":"W2-R2 'highest reproduce sim_exp' con fondo a tasa alta — v2 fija el SBR incidente y recorta la señal registrada por (1-e^-x)/x, mientras sim_exp fija Ns:Nb registrados; a 0.0105/ciclo es 0.5 % del SBR (despreciable) y a 0.3/ciclo con fondo ~14 %; los tests de highest usan sbr=inf. Falta decidir si se documenta como limitación"}]
```
