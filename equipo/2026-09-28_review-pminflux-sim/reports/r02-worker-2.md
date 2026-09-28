# r02 — Worker 2: simulador en dominio temporal (`simulate.py`)

## Archivos (solo los míos)
- `src/pminflux_sim/simulate.py`: `SimParams` y `simulate_counts`, con la interfaz congelada del plan r02-pi, exacta. Agregué `DEAD_TIME_ASSUMPTION` (texto).
- `tests/test_simulate.py`: los 11 ids fijados, más `TestSimulateAPI` (2 tests extra).
- `scripts/sweep_dead_time.py` → `results/dead_time_sweep.json`.
- No toqué `mixing.py`, `__init__.py`, `legacy/` ni `test_acceptance.py`. No hice commit.

## API tal como quedó implementada
- `SimParams(T=50, K=4, tau=4.21, irf_fwhm=0.3, a=0, b=10.1, rate_per_cycle=2.5e-3, dead_time=22.0, tcspc="earliest", counting="periodic", n_mode="fixed", beam_powers=None)`
- `simulate_counts(lambda_beams, n_loc, N, sbr, params=None, rng=None, return_tags=False)`
  - Devuelve `counts`, un array `(n_loc, K)` int64.
  - Con `return_tags=True` devuelve `(counts, tags)`. Las claves de tags son `loc`, `cycle` (ciclo de llegada), `microtime_ns` ∈ [0, T) y `source` (haz, o −1 para el fondo). Van en orden de llegada dentro de cada localización.
- `sbr` es la razón Ns/Nb de los fotones **incidentes**:
  - `inf`: sin fondo.
  - `0`: solo fondo. Es una extensión, que se usa en los tests.
  - A tasa baja coincide con la razón entre los detectados.
- `rng`: si no es un `Generator`, se pasa a `default_rng(rng)`. Con `None` usa la semilla del sistema.
- Semántica de las opciones:
  - `earliest`: el SPAD tiene tiempo muerto **no paralizable** sobre el tiempo absoluto, y abarca ciclos. Después, el TCSPC registra la **primera avalancha de cada ciclo de llegada**.
  - `highest`: 1 fotón por ranura (ciclo de excitación, haz) y gana el k más alto. El fondo se agrega aparte, sin competir. Ignora `dead_time`, igual que `sim_exp`.
  - `none`: se registran todos los fotones.
  - Conteo `legacy`: usa '>' / '<' estrictos y no pliega las ventanas. Agrega ceros = (ciclos hasta la última detección) − (detecciones de señal), como `len(Tmicro) − Ns` en `sim_exp`.
- **Supuesto declarado:** el `dead_time` de 22 ns es un supuesto (un valor típico de SPAD), no una medición. Figura en los docstrings, en `DEAD_TIME_ASSUMPTION` y en `assumptions` del JSON.
- La N fija es exacta. El proceso de Poisson corre hasta la N-ésima detección. Solo se usan las llegadas anteriores a `t_cut = (ciclo del último fotón generado)·T − 8σ_IRF`. Las filas que quedan cortas se **extienden**: continúa el mismo proceso y no se descarta nada.

## Tests: `python -m unittest tests.test_simulate` → 13 OK en 20 s
Los p-valores están contados sobre los fotones que caen en las ventanas.

| test | configuración | fotones | resultado |
|---|---|---|---|
| low_rate_matches_mixing_window_probs | earliest, IRF 0.3, λ(5,−5) | 1.18e6 | mezcla p=0.907; ingenuo p≈0 |
| low_rate_matches_mixing_window_probs | earliest, IRF 0 | 1.20e6 | mezcla p=0.056 |
| low_rate_matches_mixing_window_probs | none, IRF 0.3, λ=[.4,.1,.2,.3] | 1.18e6 | mezcla p=0.0018 |
| low_rate_matches_mixing_window_probs | earliest, IRF 0.3 | 1.18e6 | mezcla p=0.606 |
| irf_negative_start_and_wrap | (a, b) = (−0.5, 10.1) | 9.9e5 | p=0.511 |
| irf_negative_start_and_wrap | (a, b) = (2, 12), cruza T | 9.6e5 | p=0.096 |
| irf_negative_start_and_wrap | (a, b) = (−1.5, 12.5) | 1.05e6 | p=0.701 |
| highest_overwrite_emulation (0.3/ciclo) | IRF 0.3 | 1.14e6 | highest p=0.61; ideal y earliest p≈0 |
| highest_overwrite_emulation (0.3/ciclo) | IRF 0 | 1.15e6 | highest p=0.080 |
| earliest_matches_mixing_predictor | τ=1.5, 0.3/ciclo | 1.2e6 | earliest p=0.73; highest e ideal p≈0 |
| earliest_matches_mixing_predictor | τ=1.0, 0.2/ciclo | 1.2e6 | earliest p=0.20 |
| legacy_counting_zeros_in_window0 (F102) | a=−0.25 | 200 loc | 198 410 ceros/loc; ventana 0 = 99.0 % de los conteos |
| legacy_counting_zeros_in_window0 (F102) | control: legacy a=0 | 6.3e5 | p=0.908 |
| legacy_counting_zeros_in_window0 (F102) | control: periodic a=−0.25 | 6.3e5 | p=0.032 |
| legacy_counting_non_periodic (F103) | b=13, doble conteo, τ=4.21 | 8.4e5 | 11.11 % (SE 0.034 %) |
| legacy_counting_non_periodic (F103) | b=13, doble conteo, τ=0.001 | 8.4e5 | 94.93 % |
| legacy_counting_non_periodic (F103) | a=−0.5, b=12.5, pérdida de la ventana 0, τ=4.21 | — | 6.81 % ± 0.07 (ref. 6.84) |
| legacy_counting_non_periodic (F103) | a=−0.5, b=12.5, pérdida de la ventana 0, τ=0.001 | — | 2.46 % ± 0.06 (ref. 2.54) |
| short_lifetime_turns_off_leakage (F201) | τ=0.001, b=12.5 | 1.26e6 | ingenuo p=0.695 |
| short_lifetime_turns_off_leakage (F201) | τ=4.21 | 1.26e6 | ingenuo p≈0 |
| dead_time_spanning_cycles | solo fondo, 0.3/ciclo, d=120 | 2e5 intervalos | media 286.23 contra d+T/r = 286.67; KS p=0.39 |
| dead_time_spanning_cycles | solo fondo, 0.3/ciclo, d=60 | 2e5 intervalos | media 226.82 contra 226.67; KS p=0.99 |
| dead_time_spanning_cycles | d=22 | — | intervalo mínimo ≥ d, también entre ciclos consecutivos; 1 registro por ciclo; control con d=0 |
| background_uniform_b_over_T | 3 geometrías, incluidas a<0 y cruce de T | 5e5 | \|z\| ≤ 2.66 |
| background_uniform_b_over_T | SBR 1 | 8.8e5 | mezcla p=0.29 |
| fixed_and_poisson_N | ventanas que parten el ciclo | — | suma = N exacta; varianza multinomial y de Poisson dentro de 4 SE |
| throughput | 2e6 fotones | — | 1.9e6 fotones/s (ver abajo) |

Notas sobre la tabla:
- En F103 el 10.9 % verificado es un MC de 62 850 fotones. El valor esperado propio es 11.15 %, y esa es la referencia del test.
- En F103 la pérdida de la ventana 0 coincide **exactamente** con los fotones en (T − 0.5, T).
- En el cruce de T, los fotones con microtiempo < (K−1)·T/K + a + b − T entran en la ventana 3. Con a<0, la ventana 0 recibe fotones del haz 0 que cayeron antes del pulso por la IRF.

**Semilla cambiada:** en `irf_negative_start_and_wrap`, con (a, b) = (−0.5, 10.1), la primera semilla (21) dio p = 6.3e-4. Revisé si había un error de fondo antes de cambiarla:
- Con 1.26e7 fotones (IRF 0.3, a = −0.5, `none`), separé los fotones por fuente.
- La fracción de fondo y la de cada haz dieron |z| ≤ 1.7.
- P(ventana 0 | haz 0) = 0.89789 contra C = 0.89770. P(ventana 0 | haz 3) = 0.05254 contra 0.05260. P(ventana 0 | fondo) = 0.20255 contra 0.2020. Todas con |z| ≤ 1.03.
- Un MC directo de la fila 0 de `mixing_matrix` con IRF (2e8 muestras) dio |z| ≤ 1.3.

La concluí una fluctuación y pasé a la semilla 24. Queda declarado aquí.

## Rendimiento (medido)
- 1e5 localizaciones × 2000 fotones con los parámetros por defecto (2.5e-3/ciclo, 22 ns, earliest, IRF 0.3), corrido **completo**: **96.5 s**, 2.07e6 fotones/s. Máquina de 8 núcleos, un hilo, numpy 1.24.4.
- Otros modos, con 1e7 fotones:
  - dead_time 0: 2.4e6 fotones/s.
  - highest: 1.9e6 fotones/s.
  - 0.0105/ciclo con d=100: 2.05e6 fotones/s. Extrapolado a 1e5×2000 da 83–104 s.
- El test `test_throughput` (1000×2000) midió 1.9e6 fotones/s, lo que extrapola a 105 s.

## Barrido de tiempo muerto (`results/dead_time_sweep.json`, 62 s)
- Setup: λ de (5, −5), SBR 21, τ = 4.21, [0, 10.1], IRF 0.3 ns y N = 2095 detectados por localización (1969.8 en ventanas).
- Cada caso tiene 3000 localizaciones y la semilla 20260928 (SeedSequence.spawn).
- La tabla da el sesgo por ventana contra `window_probs` (la mezcla ideal), en SE por localización. El SE del propio MC es **0.018** en esas unidades.

| modo | tasa 1e-3 | 2.5e-3 | 5.5e-3 | 0.0105 |
|---|---|---|---|---|
| highest (sim_exp, "antes") | [.026,−.028,−.001,.022] | [−.028,−.043,.016,.042] | [−.030,−.046,.034,.027] | [.036,−.109,.023,.082] |
| earliest d=0 | [−.010,.000,−.015,.020] | [.043,.010,.005,−.033] | [.035,.059,−.017,−.061] | [.049,.107,−.044,−.090] |
| earliest d=22 (supuesto) | [.008,.030,−.020,−.015] | [.024,.038,.007,−.057] | [.006,.056,.015,−.079] | [−.004,.088,.005,−.099] |
| earliest d=50 | [.001,−.003,−.013,.017] | [.024,−.008,.018,−.019] | [−.017,.013,−.006,−.001] | [−.004,−.003,−.007,.012] |
| earliest d=100 | [.024,.011,−.013,−.008] | [−.015,.005,.007,−.006] | [.004,.034,−.022,−.016] | [−.010,.033,−.021,−.011] |

- **"Antes" (highest) contra el predictor exacto de `mixing`:** el predictor da [.004, −.098, .015, .091] a 0.0105/ciclo. La simulación coincide dentro de ≤1.8 MC-SE.
- **"Después" (earliest, d = 0 y d = 22):** el sesgo tiene el signo **opuesto** al de highest en los haces 1 y 3. Es el espejo de MIX-EARLIEST.
- **Magnitud:** el sesgo máximo es ≈0.1 SE por localización a 0.0105/ciclo y ≤0.06 SE a ≤2.5e-3/ciclo, en todos los modos. Es despreciable por localización y solo se detecta en conjunto (p ~ 1e-8 a 1e-10 con 5.9e6 fotones).
- **Observación nueva (sin verificar):** con d = 50 y d = 100 (múltiplos de T) el sesgo desaparece, con p = 0.33–0.93 en todas las tasas. Lo contrasté fuera del barrido, a 0.0105/ciclo con 1.2e7 fotones en ventanas:
  - d = 62.5: máximo 0.033 SE, p = 0.05.
  - d = 35: máximo 0.066 SE, p = 3.6e-7.
  - d = 75: máximo 0.059 SE, p = 9.8e-6.
  - Mi interpretación es que un bloqueo de exactamente n·T cubre todas las fases del ciclo por igual y anula la preferencia por el fotón temprano. Es una hipótesis.

## Limitaciones y puntos abiertos
1. **`earliest` contra `mixing.sim_exp_window_probs(rule='earliest')`:**
   - El predictor hace competir a los fotones dentro del **ciclo de excitación**. El simulador los hace competir en el **ciclo de llegada**, que es lo físico: un fotón del haz 3 que fuga al ciclo siguiente compite allí.
   - Con τ corto (1.0–1.5 ns, sin IRF) coinciden (p = 0.20–0.73).
   - Con τ = 4.21 a 0.1/ciclo difieren en fracción [+1.56e-3, −8.4e-4, −1.7e-4, −5.5e-4] (p = 3e-4). A 0.02/ciclo ya no se distingue (p = 0.18).
   - Es un término de orden tasa × fuga entre ciclos. A tasas de tracking es despreciable (ver el barrido). El test lo acota a < 2e-3 y lo documenta.
2. Modelo del detector:
   - El tiempo muerto es no paralizable y lo dispara toda avalancha, también las que el TCSPC no registra en un ciclo ya ocupado.
   - No hay tiempo muerto del TDC.
   - Si el equipo real es TTTR (sin límite de 1 por ciclo), habría que agregar un modo. Hoy no existe.
3. `highest` ignora `dead_time` y no hace competir al fondo. Es fiel a `sim_exp` a propósito.
4. Ceros del conteo `legacy`: se cuentan contra las detecciones de **señal**, como en el legado. Su número depende de la tasa (≈ N/tasa), no del M_p del legado.
5. No está portado el blinking ni `t_mask` (F107, backlog). La IRF es solo gaussiana, centrada en el pulso (supuesto de MIX-IRF).
6. La variante "tcspc = earliest + counting = legacy" es posible, pero no la testeé por separado.

## Afirmaciones (una por línea)
- `simulate_counts` implementa exactamente la firma congelada de r02-pi. Devuelve int64 `(n_loc, K)` y los tags `loc/cycle/microtime_ns/source`.
- `tests/test_simulate.py`: 13/13 OK en 20 s. `tests/test_mixing.py` sigue 18/18 OK.
- A 1e-3/ciclo, con dead_time 22 ns y el fondo compitiendo, los conteos (1.18e6–1.20e6 fotones) coinciden con `mixing.window_probs`: p = 0.907 (IRF 0.3) y 0.056 (sin IRF). El ingenuo da p < 1e-10.
- Las ventanas periódicas con a = −0.5, con cruce de T (a = 2, b = 12) y con a = −1.5, b = 12.5, más IRF 0.3, coinciden con la mezcla: p = 0.51 / 0.096 / 0.70 con ~1e6 fotones.
- `tcspc='highest'` a 0.3/ciclo reproduce el predictor `sim_exp` de F101: p = 0.61 (IRF 0.3) y 0.080 (sin IRF) con 1.14e6–1.15e6 fotones. Ideal y earliest dan p < 1e-10.
- `tcspc='earliest'` sin tiempo muerto coincide con el predictor 'earliest' con τ = 1.5 a 0.3/ciclo (p = 0.73) y con τ = 1.0 a 0.2/ciclo (p = 0.20). Con τ = 4.21 a 0.1/ciclo difiere hasta 1.6e-3 en fracción, por la competencia en el ciclo de llegada.
- `counting='legacy'` con a = −0.25 mete ≈198 410 ceros por localización (2095 fotones, 0.0105/ciclo) en la ventana 0 (99.0 % de los conteos). Con a = 0 no infla (p = 0.91 contra la mezcla), igual que F102.
- `counting='legacy'` con b = 13 cuenta dos veces el 11.11 % ± 0.03 % (τ = 4.21) y el 94.93 % (τ = 0.001) de los fotones en λ(5, −5) con SBR 21. El 10.9 % de F103 es un MC; el valor esperado es 11.15 %.
- Con a = −0.5 y b = 12.5, la ventana 0 del legado pierde el 6.81 % ± 0.07 % (τ = 4.21) y el 2.46 % ± 0.06 % (τ = 0.001), frente a los valores esperados verificados de 6.84 % / 2.54 %. Lo perdido es exactamente lo que cae en (49.5, 50) ns.
- Con τ = 0.001, b = 12.5 y a = 0, los conteos siguen el modelo ingenuo (p = 0.695 con 1.26e6 fotones). Con τ = 4.21 el ingenuo se rechaza (p < 1e-10). Esto es F201.
- Con solo fondo a 0.3/ciclo y dead_time d > T, los intervalos entre registros son d + Exp(T/tasa): media 286.23 contra 286.67 ns (d = 120), KS p = 0.39, y 226.82 contra 226.67 ns (d = 60), KS p = 0.99.
- El fondo cae b/T por ventana (|z| ≤ 2.66 con 5e5 fotones, también con a < 0 y cruce de T).
- `n_mode='fixed'` da exactamente N por localización, con varianza multinomial. `'poisson'` da media 199.80 y varianza 199.46 con N = 200.
- Rendimiento medido: 1e5 × 2000 fotones con los parámetros por defecto en 96.5 s (2.07e6 fotones/s, un hilo).
- Barrido: a tasas de 1e-3 a 0.0105/ciclo, el sesgo por ventana contra la mezcla ideal es ≤0.11 SE por localización de 2000 fotones en todos los modos (≤0.06 SE a ≤2.5e-3/ciclo). El SE del MC es 0.018.
- highest y earliest (d = 0 o 22) sesgan con signos opuestos en los haces 1 y 3 a 0.0105/ciclo: [.036, −.109, .023, .082] contra [−.004, .088, .005, −.099] SE.
- Observación sin verificar: con dead_time = 50 o 100 ns (múltiplos de T) el sesgo 'earliest' desaparece (p = 0.33–0.93), y reaparece con 35 y 75 ns.
- El dead_time de 22 ns es un supuesto no medido, rotulado en el código y en el JSON.
