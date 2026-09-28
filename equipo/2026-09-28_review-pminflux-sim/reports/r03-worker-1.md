# r03 — Worker 1: usabilidad + correcciones (Tarea 1, pasos 1–12)

Archivos tocados (solo los asignados): `src/pminflux_sim/{__init__,simulate,estimate,windows(nuevo)}.py`,
`tests/test_{simulate,estimate,windows(nuevo),usability(nuevo)}.py`, `scripts/build_findings.py` →
`results/findings.json`, `scripts/example_end_to_end.py` (nuevo), `scripts/study_misalignment_v2.py` (nuevo) →
`results/study_v2.json`, `README.md` (nuevo), `pyproject.toml` + `setup.cfg` + `setup.py` (nuevos, mínimos).
Regenerado: `results/compare_legacy_vs_v2.json` (paso 7). No se tocó `mixing.py`, `psf.py`, `legacy/`,
`tests/test_acceptance.py` (sha256 5ad01fba… = state.json), `report/`. Sin git commit.

## Cambios por paso

1. **Guard b > T/K.** `windows.check_overlap(b, T, K, allow_overlap)`: `ValueError("ventanas solapadas: b=%g > T/K=%g …")`
   con tolerancia relativa 1e-12 (b = T/K sigue permitido); `allow_overlap=True` → `warnings.warn(UserWarning)`.
   Se llama en `simulate._check` (nuevo campo `SimParams.allow_overlap=False`), `estimate.crb(..., allow_overlap=False)`,
   `estimate.mle_mixing(..., allow_overlap=False)` y `windows.count_windows`. `crb_legacy`/`mle_legacy` (b = T/K implícito) no cambian.
   Tests: `tests/test_windows.py::TestOverlapGuard` (b = 20, T = 50, K = 4 en los 4 puntos; allow_overlap avisa y devuelve).
   Dos tests existentes usaban b > T/K a propósito (`test_legacy_counting_non_periodic` b = 13, `test_background_uniform_b_over_T`
   b = 15): ahora pasan `allow_overlap=True`.
2. `tests/test_simulate.py` doble conteo: referencia 0.1115 → **0.11175**, comentario cita "cuadratura 0.111746"; tolerancia igual.
3. `build_findings.py` F205: el impacto dice ahora "el RMSE correcto, contra el píxel simulado (−5, −8), es 0.912 nm; los 0.960 nm
   que produce el script legado están inflados por el desplazamiento de 0.4455 nm" (+ entrada en `corrections_applied`).
   `findings.json` regenerado: mismos 16 ids en el mismo orden, todos `verified`; 19 ids distintos de v2_test/v2_tests, todos existen.
   Además: `v2_fix_status` "pendiente R2 … Test fijado, aún no verificado" → "implementado en v2 (R2, Wn): … El test v2 existe y pasa
   (verificado en R2)" (función `refresh_fix_status`); F201/F205 citan study_v2 (pendiente de verificación); F107 portado.
   `findings_discarded.json` y `mixing_claims.json` salen byte-idénticos.
4. `__init__.py`: `__version__ = "2.0.0"`; submódulos `mixing, psf, windows, simulate, estimate`; nombres `SimParams, simulate_counts,
   DEAD_TIME_ASSUMPTION, count_windows, beam_positions, lambda_beams, mle_mixing, mle_legacy, crb, crb_legacy, forward_probs,
   cov_ellipse, MLEResult` + los 7 de mixing que ya exportaba. Test `tests/test_usability.py::TestPublicAPI`.
5. **`windows.count_windows(microtime_ns, T=50, K=4, a=0, b=10.1, macro_index=None, return_outside=False, n_loc=None, allow_overlap=False)`**
   y `windows.window_masks`. Medio abierta `[i·T/K + a, +b)`, pliegue `(t − a) mod T` (acepta tiempos absolutos). ValueError con
   microtiempo no finito, macro_index de otro largo/negativo/no entero, n_loc < max+1, b fuera de (0, T]. El 0.0 no tiene trato especial
   (F102 se evita porque los datos reales no tienen ceros de relleno; documentado). `simulate` usa ahora `window_masks` (misma aritmética).
   Tests (`tests/test_windows.py`): igualdad exacta con `simulate_counts` sobre `return_tags` (3 setups), ventana que cruza T
   (a = 5, b = 10), a < 0 (a = −0.5, b = 12.5) + comparación con intervalos explícitos en 20000 tiempos uniformes, y χ² contra
   `window_probs` a 1e-4/ciclo: **p = 0.184** (394059 fotones; ingenuo p = 0).
6. Arranque en grilla en bloques: `chunk=20000` en `mle_mixing`/`mle_legacy`/`_mle_core` (ValueError si < 1). Test
   `TestChunkAndConvergence::test_chunked_grid_start_identical`: r, converged, beta y powers **idénticos bit a bit** con chunk 7/1/9
   (fijo, free_bg local/shared, legacy, free_powers).
7. `test_compare_json_complete` exige `source == source_requested == "v2sim"` y sha256 de mixing/psf/estimate/simulate y del script
   iguales a los archivos actuales. Regenerado `compare_legacy_vs_v2.json` (misma semilla 20260928, 61.7 s): **0 diferencias numéricas**
   en todos los campos (salvo runtime/versions/command) contra el JSON de R2. Antes de regenerar se comprobó que `simulate_counts`
   da conteos y microtiempos bit a bit iguales al código de R2 en 5 configuraciones.
8. Docstring de estimate: free_bg local → "el CRB por eje crece solo 1.000–1.038x (0.9453 contra 0.926 nm en (5, −5))".
   `converged`: si se agota `maxiter` y la NLL mejoró ≤ 1e-6 (absoluto) en las últimas 10 iteraciones → True. Las estimaciones no
   cambian (máx. diferencia 0.0 nm en 6000 ajustes). Con N = 10–50 (6000 locs, semilla 5): converged=False **43 → 5**. Los 5 que
   quedan están de verdad sin converger: con maxiter = 5000 la NLL baja 1e-5–2e-5 y r se mueve 0.03–0.10 nm (coincide con
   Nelder-Mead). Test `test_converged_flag_at_optimum_low_N` (+ maxiter = 1 no declara convergencia falsa).
9. `scripts/example_end_to_end.py`: simular → `count_windows` (assert igual a counts) → C → `mle_mixing` y `mle_legacy` → CRB → tabla.
   **3.5 s** con 500 locs × 4 posiciones. Ej.: (−15, 15) mezcla |b| 0.065 RMSE/CRB 0.980; legado |b| 2.663 RMSE/CRB 2.020.
   Test `test_end_to_end_example` (< 30 s).
10. `scripts/study_misalignment_v2.py` → `results/study_v2.json` (**45.4 s**, semilla 20260928, sha256 de 5 módulos + script).
    Ver números abajo. Test `TestStudyV2::test_study_v2_json` (sha actuales, setup, supuestos, emisores continuos, combinaciones,
    SE > 0, conclusiones).
11. `README.md` (español): instalación (pip -e / sys.path), inicio rápido, qué correr, API, convenciones, supuestos (22 ns e IRF 0.3
    NO medidos), resultado d = n·T con esbozo de prueba, limitaciones (texto corregido del sesgo de tasa finita), migración legado → v2
    y convención de parámetros, resultados de study_v2. `pip wheel . --no-deps` construye el paquete con los 6 módulos (con
    aislamiento; sin internet hace falta `wheel` instalado, documentado).
12. **F107 portado**: `simulate_counts(..., t_mask=None)`; array 1D 0/1 por ciclo, extensión periódica `t_mask[ciclo % M]`; en ciclos
    apagados los fotones de señal se descartan (adelgazamiento de Poisson, sin cambiar las extracciones del RNG), el fondo sigue.
    Test `TestSimulateBlinking::test_t_mask_blinking_F107`: sin fondo, 0 fotones en la mitad apagada con earliest/highest/none
    (legado 51.35 %); con SBR 5, fracción en la mitad apagada 0.1429 (ref 1/7); máscara toda 1 = sin máscara bit a bit; validaciones.
    `findings.json` F107: v2_test = ese test.

## study_v2 (N = 2095, SBR 21, 400 locs × 5 posiciones continuas, R = 75 nm; CRB con fuga)

| geometría / estimador | máx \|b\| nm | RMSE/CRB medio | RMSE/CRB N=100/400/1600 |
|---|---|---|---|
| ideal / honesto (mezcla, P libres) | 0.207 | 1.002 | 1.341 / 1.066 / 1.003 |
| ideal / honesto_P_conocidas | 0.117 | 0.996 | 1.067 / 0.998 / 0.999 |
| ideal / legado (Ec. 3.5) | 3.116 | 1.671 | 1.216 / 1.240 / 1.534 |
| desalineada / honesto (P libres) | 0.324 | 1.017 | 4.496 / 1.020 / 1.033 |
| desalineada / honesto_P_conocidas | 0.086 | 1.003 | 1.003 / 1.003 / 1.024 |
| desalineada / ingenuo (geom. ideal L_eff 103.07 nm) | 8.583 | 4.093 | 1.365 / 2.041 / 3.645 |
| desalineada / legado (geom. y P verdaderas) | 3.176 | 1.726 | 1.098 / 1.239 / 1.622 |

Fracción en el borde 0 en todos los casos de N = 2095; SE bootstrap de |b| 0.03–0.07 nm. EBP desalineado: centros y
intensity_scale de `Resultados/realistic_psf/fit_parameters.csv` sobre la dona analítica (PSF 20260820 ausentes, declarado);
desplazamientos respecto del ideal ajustado 0.11/1.02/1.86/2.84 nm y potencias 21.02/16.65/22.96/22.86.

**Hallazgo nuevo (no estaba en el plan):** las potencias libres compartidas + una posición por localización sufren sesgo de
parámetros incidentales (Neyman-Scott). Chequeo aparte (desalineada, N = 400): P/P0 = 0.870/1.179/1.233, 0.854/1.171/1.206,
0.847/1.160/1.188 con 100/400/1600 locs por posición (verdad 0.792/1.092/1.088): no converge a la verdad. N = 100: 1.056/1.408/1.536
con 1600 por posición e inestable con pocas (3.0/3.9/9.3). En study_v2 el honesto con P libres a N = 100 llega a 26.8 nm.
Recomendación en README: calibrar potencias aparte con N alto. Está en `study_v2.json:note_free_powers`.

## Tests

`python -m unittest discover -s tests` → **Ran 64 tests in 61.8 s, OK** (incluye `test_acceptance` y el HTML del writer que ya
existe). Tests nuevos: 7 (test_windows) + 2 (TestChunkAndConvergence) + 1 (TestSimulateBlinking) + 4 (test_usability).

## Qué queda abierto
- Todo lo de R3 está pendiente de verificación independiente (verificador + code-reviewer).
- n_mode='poisson', KS con d > T, beta libre, highest con fondo a tasa alta: no tocados (limitaciones del README).
- F204 SE>0, umbral de test_low_rate, F102 con fórmula independiente: backlog (no tocados).
- Tiempo muerto O(n²) a saturación: documentado, no cambiado.
- Si alguien cambia `src/` o los scripts de estudio, `compare_legacy_vs_v2.json` y `study_v2.json` deben regenerarse (los tests fallan a propósito).

```claims
[{"status":"unclear","text":"W1-R3 guard b>T/K: simulate_counts, crb, mle_mixing y count_windows levantan ValueError 'ventanas solapadas' con b=20,T=50,K=4; con allow_overlap=True emiten UserWarning y siguen; b=T/K no avisa"},
 {"status":"unclear","text":"W1-R3 compare_legacy_vs_v2.json regenerado con el código R3 (semilla 20260928): 0 diferencias numéricas contra el de R2; sha256 de simulate/estimate actuales; test_compare_json_complete exige v2sim y sha"},
 {"status":"unclear","text":"W1-R3 count_windows reproduce exactamente los counts de simulate_counts desde return_tags; a 1e-4/ciclo chi2 contra window_probs p=0.184 (394059 fotones)"},
 {"status":"unclear","text":"W1-R3 arranque en grilla por bloques (chunk) da r/converged/beta/powers idénticos bit a bit"},
 {"status":"unclear","text":"W1-R3 converged: con N=10-50 (6000 locs) converged=False baja de 43 a 5 sin cambiar las estimaciones; los 5 restantes están a 1e-5-2e-5 de NLL y 0.03-0.10 nm del óptimo"},
 {"status":"unclear","text":"W1-R3 F107 portado: con t_mask=0 en la mitad y sin fondo, 0 fotones de señal en la mitad apagada; con SBR 5 la fracción apagada es 0.1429 (1/7)"},
 {"status":"unclear","text":"W1-R3 study_v2 (N=2095): mezcla con P conocidas máx|b| 0.117 (ideal) / 0.086 nm (desalineada), RMSE/CRB 0.996/1.003; legado 3.116/3.176 nm, 1.671/1.726; ingenuo desalineado 8.583 nm, 4.093; runtime 45.4 s"},
 {"status":"unclear","text":"W1-R3 potencias libres sesgadas por parámetros incidentales: N=400 desalineada P/P0 0.847/1.160/1.188 con 1600 locs/pos contra 0.792/1.092/1.088"},
 {"status":"unclear","text":"W1-R3 findings.json: 16 ids iguales, todos verified, 19 v2_test(s) existen; F205 dice 0.912 correcto y 0.960 inflado por 0.4455 nm"},
 {"status":"unclear","text":"W1-R3 discover -s tests: 64 tests OK en 61.8 s; sha256 de test_acceptance.py intacto"}]
```
