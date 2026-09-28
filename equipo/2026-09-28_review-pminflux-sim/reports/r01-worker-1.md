# r01 — Worker 1: validación de la matriz de mezcla contra `sim_exp` y barrido de tasa

## Qué hice
- `src/pminflux_sim/__init__.py`, `src/pminflux_sim/mixing.py`:
  - `mixing_matrix(tau, T, K, a, b, irf_fwhm=None, nwrap=None)`: C periódico. Sin IRF es la suma analítica de exponenciales. Con IRF gaussiana usa la CDF de la exponencial modificada por gaussiana (forma estable con `erfcx`). Suma las imágenes m < 0 y m >= 0, así que admite a < 0 y ventanas que cruzan T. Exige 0 < b <= T.
  - `window_expected` / `window_probs` (modelo de mezcla: Ns·C·λ/Σλ + Nb·b/T, normalizado sobre las ventanas), `naive_probs` (el modelo de pos_MINFLUX/crb_minflux), `pearson_chi2`.
  - Predictor exacto a tasa finita: `occupancy_pattern_probs` (probabilidad de cada patrón de ranuras ocupadas por ciclo, por inclusión-exclusión, exacta para el muestreo de sim_exp), `pattern_window_dist` ('highest' = lo que hace sim_exp; 'earliest' = TCSPC real de primer fotón, por cuadratura de Gauss-Legendre por tramos) y `sim_exp_window_probs(rule='highest'|'earliest'|'ideal')`.
- `tests/test_mixing.py`: 18 tests, todos OK (≈20 s). Cubren:
  - la fórmula del test de aceptación (≤1e-9, 5 configuraciones) y los valores del handoff;
  - que las columnas suman la fracción capturada (contra MC), y la identidad con τ→0 y b = T/K;
  - IRF→0 ⇒ sin IRF, y C con IRF, a < 0 y ventanas que cruzan T contra MC directo (<5 SE);
  - la consistencia de la CDF y la pdf de la EMG, y las entradas inválidas;
  - que la mezcla se reduce al modelo ingenuo sin fuga, y chi² contra scipy;
  - los patrones de ocupación contra una réplica del muestreo de sim_exp, y 'earliest' contra MC;
  - que el sesgo es lineal en la tasa;
  - dos corridas cortas del `sim_exp` real: a baja tasa la mezcla pasa y el ingenuo se rechaza; a 0.3/ciclo el predictor 'highest' pasa y la mezcla y 'earliest' se rechazan.
- `scripts/validate_mixing_matrix.py` escribe `results/mixing_validation.json` y `results/mixing_rate_sweep.json`. Paraleliza en 4 procesos por tramos de 20 llamadas, con `np.random.seed(base + id_tramo)`, y el resultado no depende de la cantidad de procesos. Corrida completa: `python scripts/validate_mixing_matrix.py --n-main 4e6`, ≈20 min con otros procesos corriendo al mismo tiempo. No hice la figura PNG opcional.

## Matriz de mezcla (τ = 4.21, T = 50, K = 4, ventana [0, 10.1]; C[i][j] = ventana i, haz j; circulante)
```
         haz0      haz1      haz2      haz3
w0  0.909202  0.000123  0.002397  0.046686
w1  0.046686  0.909202  0.000123  0.002397
w2  0.002397  0.046686  0.909202  0.000123
w3  0.000123  0.002397  0.046686  0.909202
```
- La suma de cada columna (fracción capturada) es 0.958409.
- Con IRF gaussiana de 300 ps FWHM: C_ii = 0.897314 y C[i][i−1] = 0.046707.

## Validación principal (results/mixing_validation.json)
- Configuración: λ = [0.12, 0.28, 0.35, 0.25], Ns = 2000, Nb = 200 (SBR = 10), M_p = 2.2e6 (rate_per_cycle = 1.0e-3), factor = 1.05, 2000 llamadas sin fallos, semilla base 20260928.
- n_detected_total = 4 156 448.
- Mezcla: chi² = 5.66 con 3 g.l., **p = 0.129**. Desvío por ventana en SE: [−0.56, −1.62, −0.05, +2.16].
- Ingenuo: chi² = 1927, **p = 0 (subdesborde)**. Desvío en SE: [+27.6, −32.8, −10.3, +23.6].
- Chi² por llamada contra la mezcla: media 2.967 (esperado 3), varianza 6.31 (esperado 6), KS de los p-valores por llamada contra la uniforme p = 0.10. La dispersión es la de una multinomial: fijar exactamente Ns y Nb no la distorsiona visiblemente.
- Variante Nb = 0 (2.07e6 fotones): mezcla p = 0.0078 (desvíos [−2.90, +0.01, −0.23, +2.46] SE); ingenuo p = 0. Una réplica independiente, con semilla 20460928 y 4.14e6 fotones (hecha a mano con `run_block`, no está en el JSON), dio **p = 0.62** (desvíos [−0.14, +0.59, +0.71, −1.27] SE). El p = 0.008 fue una fluctuación.
- Contaminación de la ventana 0, según el modelo, en esta configuración: 8.8 % de fuga de otros haces y 14.2 % de fondo.
- Los 4 tests de mixing del test de aceptación pasan: package_imports, mixing_matrix_reported_correctly, reference_configuration, mixing_model_agrees.

## Barrido de tasa (results/mixing_rate_sweep.json; Ns = 2000, Nb = 200, factor mínimo con 10 % de margen)
En la tabla, "hi − mix" es el predictor 'highest' menos la mezcla, y "ea − mix" es 'earliest' menos la mezcla, ambos en SE de la N observada.

| tasa (Ns+Nb)/M_p | N en ventanas | ciclos ocupados con ≥2 haces | p mezcla | p 'highest' | hi − mix (SE) | ea − mix (SE) | N para detectar* |
|---|---|---|---|---|---|---|---|
| 1e-3 | 2.08e6 | 3.6e-4 | 0.14 | 0.15 | [−0.18, −0.20, +0.06, +0.27] | opuesto | 2.6e8 |
| 3e-3 | 2.08e6 | 1.1e-3 | 0.60 | 0.76 | [−0.53, −0.59, +0.18, +0.83] | opuesto | 2.9e7 |
| 1e-2 | 4.16e6 | 3.6e-3 | **1.7e-4** | 0.81 | [−2.5, −2.8, +0.85, +3.9] | opuesto | 2.6e6 |
| 3e-2 | 2.08e6 | 1.1e-2 | 3e-26 | 0.15 | [−5.3, −6.0, +1.8, +8.4] | opuesto | 2.8e5 |
| 0.1 | 1.04e6 | 3.7e-2 | 4e-122 | 0.66 | [−12.8, −14.7, +4.2, +20.5] | opuesto | 2.4e4 |
| 0.3 | 1.04e6 | 0.12 | 0 | 0.91 | [−41, −49, +12, +70] | [+46, +48, −17, −66] | 2.1e3 |
| **estudios**: Ns = 2000, Nb = 95, M_p = 2e5, f = 1.05 (Nh/M_p = 0.0105), τ = 4.21, b = 10.1 | 4.12e7 | 3.8e-3 | **2.3e-74** | **0.24** | [−8.7, −9.6, +2.9, +13.4] | opuesto | 2.2e6 |

\* N en ventanas para que el chi² contra la mezcla tenga una potencia de 50 % con α = 1e-3 (no centralidad 14.24).

Lectura:
- El predictor 'highest' describe `sim_exp` en todas las tasas: p entre 0.15 y 0.91, y a 0.0105/ciclo con 4.1e7 fotones p = 0.24, con desvíos observados [−1.2, −1.1, +0.3, +1.7] SE.
- Por eso el sesgo de la sobrescritura queda explicado cuantitativamente. Es lineal en la tasa, alrededor de 0.08·tasa en la fracción de la ventana 3.
- El TCSPC real ('earliest') sesga casi en espejo, con el mismo tamaño y el signo opuesto. En la tabla, "opuesto" marca las filas donde esto se da; en la de 0.3 está el valor explícito.

## ¿Importa la sobrescritura?
- Tracking, de 1e-3 a 5e-3 fotones/ciclo: no. El sesgo absoluto va de ≤8e-5 a ≈4e-4 por ventana. Por localización de 2000 fotones es de 0.01 a 0.05 SE, y hacen falta de 3e7 a 2.6e8 fotones pooled para detectarlo.
- En los estudios de la autora (0.0105/ciclo) es detectable en conjunto: con 4e7 fotones, p = 2e-74 contra la mezcla ideal. Pero por localización es despreciable: el sesgo absoluto es [−4.6e-4, −6.7e-4, +2.2e-4, +9.1e-4], como mucho 0.09 SE con 2000 fotones.
- La diferencia entre sim_exp y un TCSPC real es el doble de eso (≈1.8e-3 en la ventana 3), ≈0.18 SE por localización.
- Con la configuración literal de los estudios (Tlife = 0.001, b = 12.5, C = I) el sesgo por etiqueta es [−5.3e-4, −6.7e-4, +2.6e-4, +9.4e-4], también < 0.1 SE por localización.
- No calculé el sesgo que esto produce en la posición estimada: queda abierto. El orden de magnitud sugiere que es chico frente a σ.
- Recién pesa por localización a ≥0.1/ciclo: de 0.6 a 0.9 SE a 0.1 y hasta 3 SE a 0.3.

## Sospechas (b) y (c)
- **(b) Pliegue `% dt` al mismo ciclo** (l.573): para los conteos es exactamente periódico. C periódico reproduce sim_exp (p = 0.13 con 4e6 fotones), así que es equivalente a una tasa cualquiera para los conteos. Solo importaría para la competencia TCSPC entre ciclos o el tiempo muerto, que sim_exp no modela (cola del haz 3 contra el pulso del haz 0 del ciclo siguiente). El pliegue tampoco afecta `absTimeBinary`, que no se usa para contar.
- **(c) Fondo solo en ciclos sin señal, y N fijo**:
  - Los microtiempos de fondo son U[0, dt] independientes. El ciclo asignado solo entra en `absTimeBinary`, así que los conteos por ventana reciben exactamente Nb·b/T a cualquier tasa, y la validación lo confirma.
  - La contracara es que el fondo nunca compite con la señal en el TCSPC. A baja tasa da lo mismo; a alta tasa, un TCSPC real sí haría competir al fondo, y eso no está en ningún modelo de esta ronda.
  - Condicionar en Ns y Nb exactos no altera la dispersión del chi² (media 2.97 y varianza 6.31 con 3 g.l.). Para comparar con el CRB con N de Poisson sigue siendo una decisión de diseño (lo trata W2).

## Otros hallazgos
- **La fórmula de referencia del test de aceptación solo suma las imágenes m ≥ 0.** Si la última ventana cruza T (a + (K−1)T/K + b > T), pierde la fracción que cae al comienzo del ciclo. Ejemplo: K = 3, τ = 8, a = 2, b = 16 da una diferencia de 0.15 contra el MC (test `test_acceptance_formula_misses_windows_crossing_T`). En la configuración de referencia (a = 0, b = 10.1) no pasa y el test es correcto. Es un aviso para R2, cuando haya ventanas con a < 0 por la IRF.
- Pile-up dentro de una ranura: n ≥ 2 fotones del mismo pulso, donde el primero tiene τ/n. No está modelado ni por sim_exp ni por el predictor. Es de segundo orden: a 0.01/ciclo afecta ~0.1 % de las ranuras ocupadas.

## Afirmaciones (una por línea, verificables)
- `mixing_matrix(4.21, 50, 4, 0, 10.1)` coincide con la fórmula del test de aceptación con un error máximo de 1.1e-16; C_ii = 0.909202, C[i][i−1] = 0.046686, C[i][i−2] = 0.002397, C[i][i−3] = 0.000123, suma de cada columna = 0.958409.
- Con la IRF gaussiana de 300 ps FWHM, C_ii = 0.897314 y C[i][i−1] = 0.046707.
- `sim_exp` del legado, con 4 156 448 fotones en ventanas a 1.0e-3 fotones/ciclo (Ns = 2000, Nb = 200, λ = [0.12, 0.28, 0.35, 0.25], semilla 20260928), es consistente con el modelo de mezcla: chi² = 5.66 con 3 g.l., p = 0.129, desvíos [−0.56, −1.62, −0.05, +2.16] SE.
- Los mismos datos rechazan el modelo ingenuo de pos_MINFLUX: chi² = 1927, p = 0, desvíos [+27.6, −32.8, −10.3, +23.6] SE.
- Sin fondo, la primera semilla dio p = 0.0078 contra la mezcla; una réplica independiente (semilla 20460928, 4.14e6 fotones) dio p = 0.62.
- El predictor exacto 'highest' de sim_exp (recorte por ranura + gana el k más alto) es consistente con sim_exp entre 1e-3 y 0.3 fotones/ciclo: p entre 0.15 y 0.91, y a 0.0105 con 4.12e7 fotones p = 0.24.
- A 1e-3 y 3e-3 fotones/ciclo, sim_exp no se distingue de la mezcla ideal con 2e6 fotones (p = 0.14 y 0.60). Para detectar el sesgo harían falta ≈2.6e8 y ≈2.9e7 fotones.
- En la configuración de los estudios (M_p = 2e5, Nh = 2100), sim_exp se aparta de la mezcla ideal (p = 2.3e-74 con 4.1e7 fotones). El sesgo absoluto es [−4.6e-4, −6.7e-4, +2.2e-4, +9.1e-4]: ≤ 0.09 SE por localización de 2000 fotones.
- Un TCSPC de primer fotón sesga en espejo respecto de sim_exp: a 0.0105/ciclo, ea − mix ≈ −(hi − mix), y a 0.3/ciclo hi − mix = [−0.0139, −0.0215, +0.0056, +0.0298] frente a ea − mix = [+0.0153, +0.0210, −0.0081, −0.0282].
- La fracción de ciclos ocupados con ≥2 haces es ≈0.36·tasa a baja tasa (3.6e-4 a 1e-3 y 3.6e-3 a 1e-2) y 0.12 a 0.3.
- La fórmula del test de aceptación subestima C cuando una ventana cruza T (K = 3, τ = 8, a = 2, b = 16: diferencia de 0.15 contra MC). No afecta la configuración de referencia.

## Qué no pude resolver / abierto
- El sesgo en la posición estimada (pos_MINFLUX) por la sobrescritura en la configuración de los estudios: solo tengo el sesgo en las fracciones.
- La competencia TCSPC entre ciclos, el tiempo muerto y la competencia del fondo con la señal: quedan para el simulador de R2.
- La figura PNG opcional no la hice.
