# r03 — fix-worker (ronda 3, pasada final de arreglos: código/docs/figuras)

Resuelve los refuted/unclear de r03-code-reviewer y r03-verifier que no son texto del HTML.
No edité `tests/test_acceptance.py` (sha 5ad01fba…d457c intacto), `legacy/`, `src/pminflux_sim/mixing.py`,
`scripts/build_report.py` ni `report/index.html` (`git diff --quiet` sobre esos paths: limpio). Sin commit.

## 1. sha256 robusto a finales de línea
- Nuevo `scripts/provenance_sha.py`: `sha256_file(path)` normaliza CRLF/CR→LF en archivos de texto (binarios por
  extensión: png, npy, npz, docx, pdf, …, tal cual). Con LF da lo mismo que el sha de los bytes crudos.
- `compare_legacy_vs_v2._sha`, `study_misalignment_v2._sha` y `tests/test_usability._sha` lo usan
  (test_estimate usa `cmp._sha`).
- `.gitattributes`: arriba `* text=auto eol=lf` + `binary` para png/npy/npz/docx/pdf. Las reglas de agent-team que
  siguen (`*.cmd`/`*.ps1` CRLF) mantienen la prioridad.
- Chequeo: copias CRLF de los 5 módulos dan los sha guardados en study_v2.json (True). Test nuevo:
  `test_usability.TestPublicAPI.test_sha_robust_to_line_endings`.
- **Para el writer:** `build_report.py:sha256()` hashea bytes crudos. Además `scripts/build_report.py` está hoy con
  CRLF en el árbol de trabajo. Sugerencia: `from provenance_sha import sha256_file` en su helper `sha256`.
  No lo toqué.
- Regenerados `results/compare_legacy_vs_v2.json` (59 s) y `results/study_v2.json` (41 s). Diff campo a campo
  contra la copia previa:
  - compare: 6 diferencias. Son solo `runtime_s` (3) y `versions/sha256` de estimate, simulate y del script.
  - study: 7 diferencias. Son solo `runtime_s` (3) y el sha de windows, estimate, simulate y del script.
  - **0 números cambiados** en los dos.

## 2. F107 / t_mask: semántica del SBR
- `simulate_counts(..., sbr_reference="on"|"total")`. El default `"on"` es el comportamiento actual (sbr de los
  ciclos encendidos). `"total"` reproduce el legado (Ns/Nb del conjunto fijos): usa sbr/f_on en los ciclos
  encendidos, con f_on = mean(t_mask). Con la máscara toda apagada y sbr > 0 da ValueError.
- Test `test_simulate.TestSimulateBlinking.test_t_mask_sbr_reference` (máscara 50 %, sbr 21, tcspc none):
  - fracción de fondo detectada: on = 0.0874 (esperado 1/11.5 = 0.0870); total = 0.0450 (esperado 1/22 = 0.0455);
  - sin t_mask las dos opciones dan el mismo resultado bit a bit;
  - valores inválidos dan ValueError.
- README §4 (opciones de t_mask: el SBR efectivo ≈ sbr·f_on, cómo estimar y cómo reproducir el legado) y §5 (SBR).

## 3. Guía de migración en el README
1. Nueva sección §9 "Emular exactamente sim_exp + nMINFLUX":
   - `tcspc='highest'`, `counting='legacy'`, `irf_fwhm=0`, `dead_time=0`, `tau=0.001`, `b=T/K`,
     `rate_per_cycle=factor·(Ns+Nb)/M_p` y C sin IRF.
   - Chequeo propio (dt = 25, Ns 2000, Nb 200, M_p 2e5, 150 llamadas): cuentas de sim_exp+nMINFLUX contra la
     emulación v2, χ² de homogeneidad **p = 0.85**.
   - Aviso nuevo en `estimate`: `mixing_conditioning(C)` emite un UserWarning si cond > 1e3 o s_min < 1e-2.
     `mle_mixing` y `crb` lo llaman; `COND_MAX` y `SMIN_MIN` están exportados.
   - Caso trampa (tau 0.001, T 25, b 6.25, IRF 0.3): s_min = 0.0063, cond = 160, y avisa. El setup medido
     (cond 1.11, s_min 0.853) y la emulación con IRF 0 (C = I) no avisan.
   - Tests: `test_estimate.TestMixingConditioning` (2).
2. Fórmula `M_p`/`factor` → `rate_per_cycle = factor·(Ns+Nb)/M_p`. Así la tasa de señal incidente es
   factor·Ns/M_p, la de sim_exp; con "highest" el fondo no compite. Está en la tabla de convención.
3. Datos reales:
   - `count_windows(..., starts=)`: comienzos por ventana en ns, en el reloj del TCSPC.
   - `windows.window_starts(T, K, a, t0)`: comienzos equiespaciados corridos por el offset del sync.
   - `windows.mixing_matrix_starts(tau, T, starts, b, pulse_times, irf_fwhm)`: C para comienzos y pulsos
     arbitrarios. No toca mixing.py; usa `decay_cdf`.
   - `check_overlap_starts`: exige ventanas disjuntas por separación circular.
   - Todo exportado en `pm`. README §9 "Datos reales" trae una receta que corrí.
   - Tests `test_windows.TestStarts` (5):
     - con starts por defecto, igual que sin starts y que `mixing_matrix` (1e-13);
     - offset del sync t0 = 7.3: cuentas idénticas y C invariante;
     - MC propio con pulsos no equiespaciados [0.4, 13.6, 24.1, 38.2] (3.7e5 fotones): p = 0.44 contra
       mixing_matrix_starts y p = 7.9e-32 contra la C equiespaciada;
     - MLE con conteos esperados y la C de starts recupera r0 a 1e-4 nm; con la C equiespaciada, sesgo > 0.1 nm;
     - validaciones.
4. N para `crb` con datos reales: `N = counts.sum(-1) + outside` (con `return_outside=True`, `n_is="cycle"`), o
   `counts.sum(-1)` con `n_is="windows"` (README §5).
5. Importación: `pm.check_overlap`, `pm.donut`, `pm.gaussian` (además de los nuevos) se exportan. El texto del
   README §4 queda preciso. Test `test_readme_api_table_importable`: parsea la última columna de la tabla §4 y
   comprueba que cada nombre está en `pm` y en `__all__`.
6. `cov_ellipse`: el orden de argumentos cambió (legado `(cov, q, nsig)`, v2 `(cov, nsig, q)`), advertido en la
   tabla de migración. También `beams(center=False)`.
- README §10: se reemplazó "verificación pendiente" por los números del verificador R3.

## 4. Borde de punto flotante en count_windows
- `windows._fold`: una fase que tras el pliegue da ≥ T (o un negativo subnormal, que apareció en el test con
  `nextafter(0, -1)`) se mapea a 0.
- `window_masks` lo usa en los dos caminos (también el simulador, que usa `window_masks`; los resultados
  regenerados no cambian).
- Test `TestFoldEdge` con b = T/K: los casos -1e-17, `nextafter(0.5, 0)` con a = 0.5, `nextafter(-0.5, -1)` y
  `nextafter(0, -1)` caen en una ventana (outside = 0; los de borde en la ventana 0). Máscaras = intervalos
  explícitos en 5000 tiempos uniformes.
- Además, `n_loc` sin `macro_index` ahora avisa.

## 5. Figuras (`scripts/make_report_figures.py`, vuelto a correr)
- timeline: el caption dice "C[i][i] = 0.8973 con la IRF de 0.3 ns dibujada (0.9092 sin IRF; C[1][0] es 0.0467 en
  los dos casos)". Solo cambió el caption; el PNG es igual.
- rate_sweep: el título del eje y el de captions pasan a "Desvío predicho …". El PNG cambia (lo miré: el título
  entra bien).
- dead_time: "p del χ² contra la mezcla ≥ 0.29, mínimo 0.296". Es el floor a 2 decimales del mínimo del JSON.
- Cambiaron solo `captions.json` y `rate_sweep.png`. **El writer tiene que volver a correr build_report** para que
  el HTML tome los captions.

## 6. Réplica de Nb = 0
- `validate_mixing_matrix.py --only nb0-replica`, semilla base 20460928, mismo setup (Ns 2000, Nb 0, M_p 2.2e6,
  factor 1.05, τ 4.21, [0, 10.1]).
- 1080 llamadas, 0 fallidas, **2 070 181 fotones en ventanas**, 117 s.
- Mezcla: χ² = 0.316, **p = 0.957**, desvíos +0.33/−0.08/+0.27/−0.47 SE.
- Predicción exacta 'highest' a tasa finita: p = 0.872. Ingenuo: p = 0.
- Guardado en `results/mixing_validation.json:variant_Nb0_replica`. Todas las demás claves quedan idénticas
  (comprobado por comparación de dicts).
- Conclusión: el p = 0.0078 de `variant_Nb0` (semilla 20360928) fue una fluctuación.

## Suite
`python -m unittest discover -s tests` → **Ran 75 tests in 63.045s, OK** (antes 64; 11 nuevos).

```claims
[{"status":"verified","text":"sha256 de procedencia con fin de línea normalizado (scripts/provenance_sha.py) en compare_legacy_vs_v2, study_misalignment_v2 y test_usability; copias CRLF de los módulos dan los sha guardados; .gitattributes '* text=auto eol=lf' + binary png/npy/npz/docx/pdf"},
 {"status":"verified","text":"compare_legacy_vs_v2.json y study_v2.json regenerados: solo cambian runtime_s y versions/sha256; 0 números distintos"},
 {"status":"verified","text":"simulate_counts(sbr_reference='total') reproduce Ns/Nb fijos del legado con t_mask: fondo detectado 0.0450 (1/22) contra 0.0874 (1/11.5) con 'on' (máscara 50 %, sbr 21)"},
 {"status":"verified","text":"estimate.mixing_conditioning avisa (UserWarning) en mle_mixing/crb con cond>1e3 o s_min<1e-2; C trampa (tau 0.001, T 25, b 6.25, IRF 0.3) s_min 0.0063; setup medido cond 1.11 sin aviso"},
 {"status":"verified","text":"emulación de sim_exp (highest, legacy, irf 0, dead 0, tau 0.001, rate=factor(Ns+Nb)/M_p) contra sim_exp+nMINFLUX: chi2 homogeneidad p=0.85"},
 {"status":"verified","text":"count_windows(starts=) + mixing_matrix_starts: iguales a los defaults con starts equiespaciados (1e-13); invariantes ante un offset de sync; MC con pulsos no equiespaciados p=0.44 (C equiespaciada p=7.9e-32)"},
 {"status":"verified","text":"count_windows: una fase plegada a T (o un negativo subnormal) va a la ventana 0; ningún fotón queda sin ventana con b=T/K"},
 {"status":"verified","text":"variant_Nb0_replica (semilla 20460928, 2.07e6 fotones): mezcla p=0.957, highest p=0.872; el p=0.0078 original fue una fluctuación"},
 {"status":"verified","text":"suite completa: 75 tests OK en 63 s"}]
```
