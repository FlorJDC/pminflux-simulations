# r02 — code-reviewer

Diff revisado: `git diff 7824f45 HEAD` (commit 9d8b231). Leí completos `simulate.py`, `estimate.py`, `psf.py`,
`tests/test_simulate.py`, `tests/test_estimate.py` y `scripts/compare_legacy_vs_v2.py`, y los encabezados y la salida
de `sweep_dead_time.py` y `build_findings.py`. Contexto: `OBJECTIVE.md`, `intent.md`, `inbox.jsonl`, `r02-pi.md` y
los reportes de W2 y W3. No edité nada del proyecto. Mis scripts de chequeo están en el scratchpad de la sesión
(chk1–chk11.py), fuera del repo.

## Suite completa (salida real)
`python -m unittest discover -s tests` con Python 3.8.6, numpy 1.24.4 y scipy 1.10.1:
`Ran 50 tests in 43.071s — FAILED (errors=1)`. El único error es
`test_acceptance.Acceptance.test_html_report_covers_every_finding`, con
`FileNotFoundError: ...\report\index.html`, que es lo esperable hasta R3. Los otros 49 pasan, incluido
`test_findings_registry_is_complete_and_verified`. `build_findings.py --check` corre bien: 16 entradas en
findings.json, 16 en discarded y 10 afirmaciones de mezcla.

Los sha256 de `simulate.py`, `estimate.py`, `psf.py`, `mixing.py` y del script que registra
`results/compare_legacy_vs_v2.json` coinciden con los archivos actuales. Además `source = "v2sim"`, así que el JSON
no está desactualizado.

## Lo que comprobé por mi cuenta (sin defectos)
1. **Tiempo muerto no paralizable + TCSPC del primer fotón.** `_recorded_earliest` (iteración de punto fijo) da lo
   mismo que una referencia secuencial escrita por mí en 900 filas al azar: n de 2 a 60, d ∈ {0, 5, 22, 60, 120} ns,
   0 discrepancias. El punto fijo es único porque la recursión es triangular, así que la iteración termina en la
   solución correcta.
2. **Truncado con `t_cut` y extensión.** Forcé la rama de extensión (`_efficiency_guess` = 50, n0 mínimo) en
   earliest, highest y none. Resultado: N exacta por fila; homogeneidad χ² contra la corrida normal p = 0.61 en
   earliest (8e6 fotones) y p = 0.26 y 0.12 en los otros; la separación mínima entre registros es ≥ d. El
   razonamiento de `t_cut` es correcto: todo fotón aún no generado llega después de `C·T − 8σ`, y el estado de un
   fotón registrado depende solo de llegadas anteriores. En highest, los ciclos por debajo de `t_cut` están completos.
3. **Bloques.** Con 2000 localizaciones × 2095 fotones hay 4 bloques y las sumas por fila son exactas. No hay
   estado compartido entre bloques.
4. **El fondo compite en el TCSPC.** Con los parámetros por defecto la fracción de fondo detectada es 0.04537, contra
   el nominal 1/(1+SBR) = 0.04535 (SE 0.0002). La convención Ns/Nb de los incidentes es consistente con la β del
   estimador.
5. **Caso `none` de `test_low_rate` (p = 0.0018).** Lo repetí con 10 semillas (13 a 22): con los 1.18e7 fotones
   juntos p = 0.11. Es una fluctuación de la semilla 13, no un sesgo, pero el test queda frágil (ver U2).
6. **CRB con complemento de Schur.** Armé el Fisher conjunto completo por diferencias finitas: 5 posiciones × (x, y)
   más 3 log-potencias, y aparte la misma variante con β compartido. Invertido, coincide con `crb(...,
   free_powers=True[, free_bg='shared'])` a 6 decimales. Con K = 3 y `free_bg=True` (no identificable) devuelve
   `inf`, como dice el docstring. `n_is='cycle'` es correcto: con ventanas periódicas las sumas de columna de C son
   iguales para todos los haces, así que E(r) no depende de r y no se pierde información del total dentro de las
   ventanas.
7. **MLE.** Lo comparé con Nelder–Mead multi-arranque (6 arranques) en 120 localizaciones con N = 10, 30 y 100 y con
   SBR inf, 5 y 21. También con `free_bg` y β verdadero = 0, donde β queda en la cota en el 56 % de los casos. En
   ningún caso la NLL de `mle_mixing` es peor que la del NM (diferencias en r ≤ 9e-5 nm). Borde, conjunto activo y
   cotas de β funcionan.
8. **compare_legacy_vs_v2.** Usa el simulador y el estimador de forma consistente: la N del simulador es Ns + Nb
   detectados, `sbr = Ns/Nb` en los dos lados, la CRB con N = Ns + Nb (n_is='cycle'), la misma C, `irf or None`, y
   RMSE/CRB con √2·σ. El sesgo asintótico del legado es 0.848/1.510/1.625/2.694/2.364, que reproduce F104. Hubo 0
   fallas y 0 % en el borde en los 60 ajustes. El chequeo cruzado con pos_MINFLUX da 100 % dentro de 1 px.
9. **findings.json.** Las 16 entradas están verificadas, tienen clase válida y el script existe. Todos los `v2_test`
   resuelven a tests existentes y que pasan (F107: null, como está declarado). F104 queda CONCEPTUAL y F201/F202
   quedan DISENO, como pide el inbox.
10. **Python 3.8.** Corre en 3.8.6 y no encontré sintaxis posterior a 3.8.

## Defectos con escenario concreto

**R1 — Ventanas solapadas (b > T/K): el MLE cae en silencio en un óptimo local equivocado y la CRB no es válida.**
Ni `simulate` (conteo periódico), ni `mle_mixing`, ni `crb` rechazan o avisan cuando b > T/K. Con b > T/K las
ventanas se solapan, un fotón cuenta en varias y los conteos dejan de ser multinomiales. Es la misma situación
de F103 (b = 13).
- Escenario: r0 = (−15, 15), TCP K = 4, τ = 4.21, **b = 20**, datos del simulador v2, N = 2095, SBR 21.
  - `mle_mixing` con el `grid_step` por defecto (R/12 = 6.25 nm) termina en un óptimo local equivocado en
    **193/300** localizaciones. La diferencia media con el ajuste de grilla fina (0.5 nm) es 16.7 nm.
  - Todas quedan con `converged=True`, `on_boundary=False` y `n_failed=0`.
  - Incluso con conteos esperados exactos (1e9) devuelve (−13.5, 41.0), aunque la NLL en r0 es menor por 2e5.
  - Con b = 30 el RMSE/CRB da **0.575**: la "cota" es inválida porque el Fisher multinomial con N·E ≈ 2.7 N
    ensayos no describe estos conteos.
- Para b ≤ 16 no hay problema (0/300 peores que la grilla fina).
- Arreglo sugerido para R3:
  - `ValueError` o `warning` si b > T/K en `crb`/`mle_mixing`, o documentarlo explícitamente como fuera de
    alcance.
  - Grilla de arranque más fina o multi-arranque cuando `cond(C)` es alto.

## Puntos abiertos (unclear)
- **U1, trampas de rendimiento.**
  - El arranque en grilla de `_mle_core` arma `counts @ log p_grid` de (n_loc × ~490) sin partir en bloques. Pico
    medido: 36 MB con 1e4 localizaciones y **359 MB con 1e5** (3.9 s); con 1e6 serían unos 3.6 GB. Además
    `free_powers` repite todo eso en cada evaluación de L-BFGS.
  - En el simulador, el punto fijo del tiempo muerto es O(n²) por fila a tasas de saturación. Con d = 500 ns y
    0.3/ciclo tardó **13.3 s para 1e6 fotones, con pico de 448 MB** (contra 0.4 s y 119 MB por defecto).
  - A las tasas del tracking no pasa nada de esto.
- **U2, tests más débiles de lo que dicen.**
  - `test_compare_json_complete` no exige `source == "v2sim"` ni que los sha256 del JSON coincidan con el código
    actual. Si el JSON queda desactualizado o se corrió con la fuente multinomial, el test no lo detecta.
  - F204 ("SE bootstrap") solo comprueba SE > 0.
  - El caso `none` de `test_low_rate` pasa con p = 0.0018 contra un umbral de 1e-3: es frágil ante cambios del
    flujo del RNG.
  - `test_legacy_counting_zeros_in_window0` recalcula los ceros con la misma fórmula que el código. Es
    autorreferencial: la fidelidad frente a `sim_exp` solo está probada en forma transitiva, vía el predictor de
    mixing.
- **U3, docstring incorrecto.** En `estimate.py` dice que con `free_bg` local "el CRB crece mucho". Los datos
  propios dicen 1.000–1.038× (0.9453 contra 0.926 nm en (5, −5)).
- **U4, el modelo directo del estimador ignora la distorsión de TCSPC y tiempo muerto a tasa finita.**
  - En el estudio comparativo el sesgo de la mezcla llega a 0.098 ± 0.023 nm, unos 4 SE, en (20, 0) con SBR 6 e
    IRF 0. En multinomial no aparece.
  - Está documentado por W3 y es física, no un bug.
  - La observación de W2 de que "con d = n·T el sesgo desaparece" sigue sin verificar.
- **U5, flags de convergencia falsos negativos con N baja.** Con N entre 10 y 50, el 1.3 % (78/6000) sale
  `converged=False` al llegar a 200 iteraciones. Aun así la NLL está a ≤ 1e-6 del óptimo de NM y r a ≤ 0.03 nm.
  Esto infla `n_failed`, pero no cambia las estimaciones.
- **U6, borde menor.** Con IRF, un fotón del haz 0 en el ciclo 0 puede llegar en el ciclo −1: `tags["cycle"] = −1`,
  79 de 6000 con IRF de 2 ns a 0.5/ciclo. Los ceros de `counting='legacy'` no cuentan ese ciclo. Además el proceso
  arranca sin historia previa (sin tiempo muerto heredado ni fuga del ciclo −1). Es despreciable con N ≥ 100.

## Contra el intent: lo que falta y si la autora puede usar el paquete
**Faltan del OBJECTIVE:**
- `report/index.html`: la aceptación está en rojo.
- `README.md`.

**Como reemplazo de su flujo, hoy no es usable sin leer el código:**
- No hay README, ni ejemplos, ni notas de migración.
- `src/pminflux_sim/__init__.py` sigue diciendo "Ronda 1: solo el modelo de la matriz de mezcla" y no importa
  `simulate`/`estimate`/`psf`, así que `import pminflux_sim; pminflux_sim.estimate` falla.
- No hay empaquetado (pyproject/setup): solo se usa con `sys.path.insert`.
- No hay una función pública para contar microtiempos reales en ventanas periódicas. Esa lógica vive privada dentro
  de `simulate_counts` y la autora la necesita para aplicar `mle_mixing` a sus datos TCSPC.
- No hay un equivalente de `simulations_example.py` (el bucle de estudio con mapas de RMSE por posición, SBR y N).
- F107 (t_mask/blinking) no está portado.

**R3 tiene que agregar:**
1. `report/index.html` (aceptación).
2. `README.md` con:
   - cómo correr los tests y cada script, y cuánto tardan;
   - la convención de N (Ns + Nb detectados en el ciclo completo), de SBR (incidente) y de β;
   - los supuestos: dead_time de 22 ns, IRF de 300 ps, TCSPC de un fotón por ciclo.
3. Un ejemplo mínimo de punta a punta (`examples/quickstart.py` o una sección del README) con la cadena
   `mixing_matrix`, luego `simulate_counts`, luego `mle_mixing` y `crb`. Debería reproducir una fila de la tabla
   del estudio comparativo.
4. Una tabla de migración del legado a v2:

   | legado | v2 |
   |---|---|
   | `sim_exp` | `simulate_counts(..., SimParams(tcspc='highest', counting='legacy'))` para emularlo; los defaults para lo físico |
   | `nMINFLUX` | `counting='periodic'` |
   | `pos_MINFLUX` | `mle_legacy` (Ec. 3.5 continua) / `mle_mixing` |
   | `crb_minflux` | `crb_legacy` / `crb` |
   | `beams` / `ebp_centres` | `psf.beam_positions` |
   | `doughnut` / `psf` | `psf.donut` / `lambda_beams` |
   | `cov_ellipse` | `estimate.cov_ellipse` |

   Con las diferencias de semántica: sbr, N, px y la grilla contra el continuo.
5. Actualizar `__init__.py` para que exponga los submódulos.
6. Una función pública para contar microtiempos en ventanas (o documentar cómo aplicarlo a datos reales).
7. El guard o la documentación de b > T/K (R1).
8. Endurecer `test_compare_json_complete` (source = v2sim y sha256).

```claims
[{"status": "verified", "text": "Suite completa (python -m unittest discover -s tests, Py 3.8.6): 50 tests, 49 OK, 1 error esperado (test_html_report_covers_every_finding: falta report/index.html), 43 s"},
 {"status": "verified", "text": "simulate._recorded_earliest (tiempo muerto no paralizable que abarca ciclos + TCSPC primera avalancha por ciclo) coincide con una referencia secuencial independiente en 900 filas al azar (d en {0,5,22,60,120} ns): 0 discrepancias"},
 {"status": "verified", "text": "Truncado t_cut / N fija / bloques: la rama de extensión forzada da N exacta y la misma distribución que la corrida normal (homogeneidad p=0.61 earliest con 8e6 fotones; 0.26 highest; 0.12 none); con 4 bloques las sumas son exactas; la fracción de fondo detectada es 0.04537 contra 0.04535 nominal (el fondo compite en TCSPC y la convención SBR es consistente con la beta del estimador)"},
 {"status": "verified", "text": "crb con free_powers y con free_powers+beta compartido (complemento de Schur) coincide a 1e-6 con la inversa del Fisher conjunto completo por diferencias finitas en 5 posiciones; K=3 con free_bg devuelve inf"},
 {"status": "verified", "text": "mle_mixing (grilla + Fisher scoring con conjunto activo) nunca da peor NLL que Nelder-Mead multi-arranque en 120 casos (N=10-100, SBR inf/5/21, y free_bg con beta en la cota 0)"},
 {"status": "verified", "text": "compare_legacy_vs_v2.json: source=v2sim, sha256 iguales al código actual, convención N=Ns+Nb/sbr=Ns/Nb consistente entre simulate, estimate y crb, 0 fallas en 60 ajustes, sesgo asintótico del legado 0.848/1.510/1.625/2.694/2.364 nm (F104)"},
 {"status": "verified", "text": "findings.json: 16 entradas verificadas, todos los v2_test resuelven a tests existentes que pasan (F107 null declarado); clases según el inbox (F104 CONCEPTUAL, F201/F202 DISENO)"},
 {"status": "refuted", "text": "Robustez del estimador y del CRB con b > T/K no está garantizada ni avisada: con b=20, r0=(-15,15) y datos v2sim N=2095, mle_mixing (grid_step por defecto) cae en un óptimo local equivocado en 193/300 locs (16.7 nm de error medio) con converged=True y n_failed=0, e incluso con conteos exactos devuelve (-13.5, 41.0); con b=30 RMSE/CRB=0.575 (CRB multinomial inválida con ventanas solapadas). Sin guard en simulate/crb/mle_mixing"},
 {"status": "unclear", "text": "Rendimiento: el arranque en grilla del MLE no está partido en bloques (359 MB con 1e5 locs, ~3.6 GB con 1e6; free_powers lo repite en cada evaluación); el punto fijo del tiempo muerto es O(n^2) a saturación (d=500 ns, 0.3/ciclo: 13.3 s y 448 MB para 1e6 fotones). Bien a las tasas del tracking"},
 {"status": "unclear", "text": "Tests débiles: test_compare_json_complete no exige source==v2sim ni sha256 actuales; F204 solo comprueba SE>0; el caso none de test_low_rate pasa con p=0.0018 contra el umbral 1e-3 (con 10 semillas juntas p=0.11: es una fluctuación, pero frágil); los ceros de F102 se comprueban con la misma fórmula del código"},
 {"status": "unclear", "text": "El modelo directo del estimador no incluye la distorsión de TCSPC y tiempo muerto a tasa finita: el sesgo de la mezcla llega a ~4 SE (0.098 nm) en el estudio v2sim; documentado, no es un bug; la hipótesis de W2 'd = n*T anula el sesgo' no está verificada"},
 {"status": "unclear", "text": "Docstring de estimate: 'con free_bg local el CRB crece mucho' contradice los datos propios (1.000-1.038x). Con N baja el 1.3% sale converged=False aunque está en el óptimo (dNLL<=1e-6)"},
 {"status": "unclear", "text": "Usabilidad como reemplazo: faltan README, ejemplo de punta a punta, notas de migración legado->v2, __init__.py desactualizado (no expone simulate/estimate/psf), empaquetado, una función pública para contar microtiempos reales en ventanas, y el port de F107; report/index.html ausente (aceptación en rojo). Obligatorio en R3"}]
```
