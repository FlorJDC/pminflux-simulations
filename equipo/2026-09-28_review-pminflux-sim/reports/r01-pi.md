# r01 — PI: plan de la ronda 1

## Estado leído
- `state.json`: ronda 0, sin afirmaciones, plan ni backlog. No hay afirmaciones `refuted`/`unclear` vivas.
- `inbox.jsonl` (PRIORIDAD MÁXIMA): (1) validar la matriz de mezcla contra `sim_exp`; (2) revisar y mejorar los
  scripts de simulación; (3) reporte HTML que separe lo conceptual, la implementación y el diseño, con la experiencia
  de p-MINFLUX pulsado a 20 MHz. Ser justos: separar lo heredado de Masullo y reconocer lo que estaba bien.
- Presupuesto (intent.md): R1 validación + auditoría; R2 simulador y estimador nuevos; R3 reporte HTML + verificación final.
- `src/pminflux_sim/`, `scripts/findings/`, `results/` y `report/` están vacíos. Todavía no corrí el test de aceptación
  (hoy falla entero: no hay paquete ni resultados).

## Lo que exige el test de aceptación (hash fijo, no se edita)
- `results/mixing_validation.json`: `params` {K=4, T_ns=50, tau_ns=4.21, window_start_ns=0, window_width_ns=10.1};
  `C_no_irf` (4x4, ±1e-6 contra el C periódico sin IRF del test); `n_detected_total` ≥ 1e6; `rate_per_cycle` < 0.01;
  `chi2_pvalue_mixing_vs_sim_exp` > 1e-3; `chi2_pvalue_naive_vs_sim_exp` < 1e-6.
- `results/findings.json`: ≥ 5 entradas con id, title, class ∈ {CONCEPTUAL, IMPLEMENTACION, DISENO}, legacy_location,
  scenario, impact, fix, script (el archivo tiene que existir), status == "verified". En R1 se generan borradores
  `findings_A.json` / `findings_B.json` con status "candidate". La fusión en `findings.json` se hace después de verificar (R2/R3).
- `report/index.html` (R3): tiene que contener cada id y las palabras conceptual/implementaci/dise, y no puede usar `src="http`.

## Lectura rápida del legado (solo para orientar; nada de esto está establecido)
- `sim_exp` rama `p_minflux` (tools_simulations.py l.421–580): Nh = Ns·factor fotones, reparto multinomial por haz, ciclos
  uniformes y recorte a 1 por ranura (ciclo, haz) en l.464. **No** recorta a 1 por ciclo: el recorte efectivo lo hace
  `Tmicro[m1] = k1*Texp + Exp(Tlife)` en l.527, que sobrescribe (np.nonzero recorre por filas, así que gana el k más alto).
  Un TCSPC real se queda con el fotón más **temprano**. Hay que medir si esto sesga.
- l.534–556: borra fotones al azar para dejar exactamente Ns (condiciona en N). l.559–566: exactamente Nb fotones de fondo,
  uniformes en [0, dt], solo en ciclos sin señal, y sin recorte TCSPC entre ellos. l.573: `% dt` pliega la cola de cualquier
  orden hacia ventanas tempranas del **mismo** ciclo, así que para los conteos es periódico.
- `Tmicrot` incluye los M_p−Ns **ceros** de los ciclos vacíos. `nMINFLUX` (l.966) usa desigualdad estricta `relTime > τ_i + a`.
  Con a = 0 los ceros quedan afuera por esa desigualdad. **Sospecha:** con a < 0 (ventana que abre antes del pulso, lo normal con
  una IRF) todos los ciclos vacíos se contarían en la ventana 0. Las ventanas no se pliegan (τ_i + a + b > T).
- `pos_MINFLUX`/`crb_minflux` usan p = SBR/(SBR+1)·λ/Σλ + 1/(SBR+1)/K: sin fuga, y con fondo 1/K por ventana, lo que solo vale
  si las ventanas cubren el ciclo entero (b = T/K).
- **Los scripts de estudio usan `Tlife = 0.001` ns, a = 0 y b = dt/K** (simulation_misalignment.py l.55/99–100,
  simulations_example.py l.51/134–136, documento/make_fig_eficiencia.py l.40/76–77). La fuga está apagada en todos los estudios.
  simulation_misalignment y make_fig_eficiencia usan dt = 50; simulations_example (Masullo) usa dt = 25. El docstring de
  sim_exp dice "typically 25 ns".
- Con M_p = 2e5 y Nh = 2100, la tasa es ≈ 0.0105 fotones/ciclo, algo por encima del régimen del tracking (1e-3 a 5e-3 a 20 MHz).

## Defaults que decido (bifurcaciones chicas)
- `rate_per_cycle` = fotones detectados (señal + fondo, antes de las ventanas) por ciclo TCSPC = (Ns+Nb)/M_p de cada llamada.
- `n_detected_total` = suma, sobre todas las llamadas, de los fotones que caen **dentro** de las K ventanas.
- "Modelo ingenuo" = el modelo exacto que asumen `pos_MINFLUX`/`crb_minflux`: SBR/(SBR+1)·λ_i/Σλ + 1/(SBR+1)/K con SBR = Ns/Nb.
  Es la comparación justa, porque es lo que usaba la autora.
- "Modelo de mezcla": E[n_i] ∝ Ns·Σ_j C_ij·λ_j/Σλ + Nb·b/T. El chi² de Pearson se toma con K−1 grados de libertad, condicionando
  en el total dentro de las ventanas.
- Configuración primaria: λ distintos, como en una posición fuera del centro con la ventana 0 débil,
  λ = [0.12, 0.28, 0.35, 0.25]; SBR = 10; Tlife = 4.21; dt = 50; a = 0; b = 10.1; τ = [0, 12.5, 25, 37.5].
  Se reporta además la variante con Nb = 0.
- IRF por defecto: gaussiana de 300 ps FWHM (supuesto declarado). Tiempo muerto: parámetro (R2).
- Workers 2 y 3 **no** importan `pminflux_sim` (lo crea W1 en esta ronda). Cada script `F*.py` es autocontenido e importa el
  legado con `sys.path.insert(0, "legacy/p-minflux-main")`. Pueden usar `donutloc` como referencia independiente.
  Semillas fijas, Python 3.8, `# -*- coding: utf-8 -*-`.
- Criterio de clasificación (se escribe en el reporte): CONCEPTUAL = el modelo físico o estadístico está mal
  (el resultado es incorrecto aunque el código haga lo que pretende); IMPLEMENTACION = el código no hace lo que dice o pretende
  (bug); DISENO = decisión defendible que limita el alcance o la validez (parámetro por defecto, supuesto no declarado, tamaño MC).
- Cada hallazgo indica la autoría: Masullo (tools_analysis.py, simulations_example.py y el núcleo de sim_exp/nMINFLUX/pos_MINFLUX
  del paper) o la autora (refactor rápido de sim_exp, ebp.py, realistic_ebp.py, simulation_misalignment.py, analyze_realistic_psf.py,
  documento/). Si hay dudas, se marca "a confirmar" y se mira el historial o los comentarios en español. Cada hallazgo registra
  también lo que estaba bien (p. ej. la autora validó el término de fondo y corrigió spaceToIndex y el radio en px/nm de pos_MINFLUX).
- Nadie edita `legacy/` ni `tests/test_acceptance.py`. Los archivos de cada worker son disjuntos (se listan abajo).

## Tareas de la ronda 1

1. **Worker 1 — validación de la matriz de mezcla contra `sim_exp` (el pedido explícito de la autora).**
   Archivos propios: `src/pminflux_sim/__init__.py`, `src/pminflux_sim/mixing.py`, `tests/test_mixing.py`,
   `scripts/validate_mixing_matrix.py`, `results/mixing_validation.json`, `results/mixing_rate_sweep.json` (y una figura PNG
   opcional en `results/`).
   (a) `mixing.py`: `mixing_matrix(tau, T, K, a, b, irf_fwhm=None, nwrap=auto)` para el C_ij periódico (C[i][j] = P(el fotón del
   haz j cae en la ventana i)). Sin IRF: suma analítica de exponenciales; con IRF gaussiana: CDF de la exponencial modificada
   por gaussiana, plegada en el período, que admite a < 0 y ventanas que cruzan T. También
   `window_probs(lam, C, sbr o Ns/Nb, a, b, T)`, que da p' = (s·C·λ/Σλ + fondo·b/T por ventana), normalizado sobre las ventanas,
   y `naive_probs` (el modelo de pos_MINFLUX).
   Tests: coincidencia con la fórmula del test de aceptación (≤1e-9); columnas que suman la fracción capturada; b = T/K con
   τ→0 ⇒ identidad; IRF→0 ⇒ caso sin IRF; con τ = 4.21 y la ventana [0, 10.1], C_ii ≈ 0.909 y C del haz anterior ≈ 0.047
   (valores del handoff).
   (b) `validate_mixing_matrix.py`: muchas llamadas a `ts.sim_exp('p_minflux', None, psf, (0,0), SBR, Ns, Nb, M_p, 4.21, factor, 50)`
   con una pila sintética `psf` de forma (4,1,1) que contiene λ. Conteo con `ts.nMINFLUX(4, τ, relTime, 0, 10.1)`. Semilla global fija
   (`np.random.seed`, porque el legado usa el RNG global). Régimen bajo: p. ej. Ns = 2000, M_p ≈ 2e6 (≈1e-3/ciclo), llamadas hasta
   ≥ 1e6 fotones dentro de las ventanas. Cuidar la memoria (nk_fast es M_p×K int64). Escribir el JSON con el formato exacto de
   aceptación, más extras: fracciones observadas vs mezcla vs ingenuo por ventana con su SE, contaminación de la ventana 0,
   variante con Nb = 0, semilla y tiempo de corrida.
   (c) Barrido de tasa para la sospecha (a) (sobrescritura por ciclo): tasas ≈ 1e-3, 3e-3, 1e-2, 3e-2, 0.1 y 0.3 fotones/ciclo
   (1e-3 a 5e-3 es el tracking de 20 a 110 kHz a 20 MHz), con `factor` ajustado para que no falle. Para cada tasa, dar el p-valor
   del chi² de mezcla, el desvío por ventana en unidades de SE, la fracción de ciclos con ≥2 haces y el sesgo previsto por
   "gana el k más alto" frente a "gana el más temprano" (un TCSPC real), en forma analítica o por MC propio. Decir si la
   configuración de los estudios de la autora (M_p = 2e5, Nh = 2100 ⇒ 0.0105) está afectada. Comentar las sospechas (b) (pliegue
   al mismo ciclo) y (c) (fondo solo en ciclos sin señal; condicionamiento en N): ¿son equivalentes para los conteos a baja tasa?
   Afirmaciones precisas con números y cómo reproducirlas. No corras el test de aceptación completo como criterio (faltan
   findings y HTML); sí sus tres tests de mixing.

2. **Worker 2 — auditoría A: el núcleo de simulación (`legacy/p-minflux-main/tools/tools_simulations.py`).**
   Archivos propios: `scripts/findings/F101_*.py` … `F1xx_*.py`, `results/findings_A.json` (status "candidate").
   Alcance: `sim_exp` (l.298–580: ramas p_minflux, cw_minflux y simplified), `nMINFLUX` (l.966), `pos_MINFLUX` (l.1002),
   `crb_minflux` (l.583), `psf`/`doughnut`/`gaussian`/`ebp_centres`/`beams`, `spaceToIndex`/`indexToSpace`, `cov_ellipse`.
   Candidatos a investigar (confirmar o descartar, con el mismo rigor): (i) ceros de ciclos vacíos en `Tmicrot` + ventana con a < 0 ⇒
   ¿conteos espurios en la ventana 0? (ii) ventanas sin pliegue cuando τ_i + a + b > T, y la desigualdad estricta en los bordes;
   (iii) fondo fijo 1/K en `pos_MINFLUX`/`crb_minflux` cuando b < T/K (la SBR dentro de las ventanas ≠ Ns/Nb) y sin fuga;
   (iv) dt: el docstring dice 25 ns (40 MHz) y el setup usa 50 ns; (v) fondo sin recorte TCSPC y sin competir con la señal;
   exactamente Nb y Ns (N fijo en vez de Poisson); ¿qué implica para comparar con el CRB? (vi) MLE en una grilla: resolución
   px, argmax discreto, NaN→-inf, sesgo de redondeo; (vii) `crb_minflux` contra `donutloc.fisher` para λ del mismo modelo;
   (viii) `psf` con `theta`/`SW` indefinidos y `cov_ellipse` que ordena mal los autovectores (`vec[order]` en lugar de `vec[:, order]`)
   y calcula r2 sin usarlo; (ix) la rama cw_minflux/t_mask. La sobrescritura de Tmicro la cuantifica W1; W2 solo le asigna un id
   (F101) con la ubicación y la clase, y deja el impacto "ver W1".
   Cada hallazgo lleva un script mínimo (entradas del escenario ⇒ salida errónea o sesgada, con número), la ubicación
   archivo:línea, la clase con su criterio, la autoría (Masullo o la autora), la corrección propuesta y "lo que estaba bien".
   Lee antes `GithubPRO/donut-beam-localization/docs/private/C_pminflux_practice.md` para no repetir trabajo (cítalo si coincide).
   Descarta explícitamente lo que no se sostiene. Un hallazgo sin demostración no entra.

3. **Worker 3 — auditoría B: los scripts de estudio, las herramientas EBP y la metodología estadística.**
   Archivos propios: `scripts/findings/F201_*.py` … `F2xx_*.py`, `results/findings_B.json` (status "candidate").
   Alcance: `tools/ebp.py`, `tools/realistic_ebp.py` (+ `legacy/.../tests/test_realistic_ebp.py`), `simulations_example.py`
   (Masullo), `simulation_misalignment.py`, `analyze_realistic_psf.py`, `documento/*.py` (+ los logs), `NOTAS.txt`,
   `ESTADO_Y_PLAN_REALISMO_PSF.md`, y `tools_analysis.py` solo si lo usan los estudios.
   Candidatos: (i) `Tlife = 0.001` ns en todos los estudios ⇒ fuga apagada. Cuantificar cuánto cambian el sesgo y la σ de los
   estudios con τ = 4.21 y la ventana [0, 10.1] (puede ser el hallazgo DISENO/CONCEPTUAL más importante). (ii) Ventanas
   a = 0, b = dt/K frente a las del experimento. (iii) Tamaños MC, fórmulas de SE (std/√(2n) supone normalidad; RMSE), qué se
   condiciona (N fijo, fallos descartados, `valid` sin reportar la tasa de fallos), semillas. (iv) ¿Es justa la comparación
   honesta/ingenua de desalineación (mismo r0, misma SBR, mismo radio de búsqueda `R_SEARCH_FACTOR·L_eff`, que depende del EBP
   asumido)? (v) Convenciones: fwhm, L_eff, px, orientación de ejes al cargar PSF experimentales (flip y/-y), normalización de
   las PSF y el pedestal. (vi) Que las cifras del documento sean reproducibles a partir de sus scripts. Las PSF medidas
   (`C:\Data\psf\20260820`) son de solo lectura. Si hacen falta y son pesadas, usa un subconjunto o documenta que no
   se corrió. Mismo formato, rigor, autoría, "lo que estaba bien" y lectura previa de `C_pminflux_practice.md`
   que en la tarea 2.

## Backlog (no se descarta; se retoma en R2 y R3)
- R2: el simulador temporal nuevo en `src/pminflux_sim/` (microtiempos, IRF, ventanas plegadas, TCSPC de primer fotón y tiempo muerto
  parametrizable y barrido, fondo uniforme que compite con la señal, N de Poisson opcional) y un MLE con p' de mezcla + su CRB
  (Fisher con fuga), contra `donutloc`. Validar el simulador nuevo contra C (la segunda mitad del punto 2 del OBJECTIVE).
- R2: fusionar findings_A y findings_B en `results/findings.json` solo con los hallazgos verificados por el verifier, cada uno con
  su corrección aplicada en la versión nueva.
- R2: repetir un estudio de la autora (desalineación) con fuga realista y el estimador de mezcla, para cuantificar el impacto.
- R3: `report/index.html` autocontenido (figuras en base64), en español, con criterio de clases, autoría y lo que estaba bien,
  y `README.md`.
- Sin asignar: la fuga en la reconstrucción de las PSF calibradas (handoff §1.9) y la SBR dependiente de la potencia.

LO QUE MÁS SE PODRÍA HACER
1. MLE con microtiempos (verosimilitud temporal completa, tesis p. 128) frente al de ventanas con mezcla: podría recuperar la
   σ perdida por la fuga. Costo: medio (1 worker, 1 ronda).
2. Corregir la fuga en la reconstrucción de las PSF calibradas (§1.9) y medir cuánto del pedestal viene de la fuga. Importa para
   los datos reales. Costo: medio-alto (necesita las PSF de C:\Data).
3. Barrido del tiempo muerto real (< 95 ns, más largo que un ciclo a 20 MHz) con la tasa del tracking, más saturación. Costo: bajo
   una vez que exista el simulador de R2.
4. Blinking y deriva dentro de una localización (rama t_mask de cw_minflux, sin portar a p_minflux). Costo: medio.
5. Aplicar los hallazgos a `tracking_analysis` (fuera del cerco de este trabajo: requiere otro trabajo y el permiso de la autora).
