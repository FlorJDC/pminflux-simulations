# r01 — Worker 3: auditoría B (scripts de estudio, EBP, metodología estadística)

## Qué hice
- Leí el plan del PI, el handoff, `C_pminflux_practice.md` §5 y todo el alcance B: `ebp.py`, `realistic_ebp.py` y su test, `simulation_misalignment.py`, `analyze_realistic_psf.py`, `simulations_example.py`, `documento/*.py`, los logs, `ESTADO…md`, `NOTAS*` y `Resultados/`.
- Escribí 7 scripts autocontenidos en `scripts/findings/` (F201–F206 y F290 con los descartes). Todos importan el legado en solo lectura. Los números crudos quedan en `work/w3/*.json` y `work/w3/F201_full.log`.
- Registro: `results/findings_B.json`. Tiene 6 hallazgos con status "candidate" y 8 sospechas descartadas.
- **Datos:** `C:\Data\psf\20260820` **no existe** en el disco (solo están 20260703/0707/0924/0925). Por eso usé EBP que se reconstruyen exactamente:
  - ideal y geom_exp, con las posiciones y el fwhm = 343.9 del log;
  - realistic_fit, construido desde `Resultados/realistic_psf/fit_parameters.csv`. F202 reproduce los CRB y los RMSE de ella al 4.º decimal, lo que valida la reconstrucción.
  - Para "experimental" usé las PSF 20260703 como **sustituto**, rotuladas así y leídas en solo lectura.

## Pregunta clave: ¿cuánto cambian sesgo y σ con τ = 4.21 y la ventana [0, 10.1]? (F201)
Usé el legado `sim_exp` + `nMINFLUX` + `pos_MINFLUX` como los usa ella: Ns = 2000, Nb = 95, r0 = (−5.07, −7.56), 1000 muestras, semilla 20260825, R = 0.75 L_eff.

| caso | C0 (Tlife 0.001, b 12.5): \|b\| / RMSE / RMSE/CRB | C3 (τ 4.21, [0, 10.1]): \|b\| / RMSE / RMSE/CRB |
|---|---|---|
| Ideal | 0.11 / 0.92 / 1.07 | 2.98 / 2.38 / 2.75 |
| Geom. honesta | 0.12 / 0.91 / 1.07 | 2.92 / 2.33 / 2.74 |
| Geom. ingenua | 0.61 / 1.03 / 1.21 | 2.59 / 2.15 / 2.52 |
| Realista honesta | 0.18 / 2.34 / 1.00 | 1.94 / 2.88 / 1.23 |
| Realista ingenua | 5.5 / 13.0 / 5.5 | 10.8 / 24.8 / 10.6 |

- En el caso ideal, σ por eje pasa de 0.89/0.95 a 1.02/1.16 nm.
- La diferencia pareada C3 − C0 del ideal, con las mismas semillas, es (−1.00 ± 0.02, −2.70 ± 0.02) nm.
- Descomposición en el ideal: la ventana sola (C1) aporta ≈ 0.25 nm y la fuga sola (C2) ≈ 3.1 nm. Domina la fuga.
- **Chequeo independiente:** calculé aparte una matriz de mezcla propia (C_ii = 0.9092, anterior 0.0467, dos antes 0.0024, como en el handoff) y el argmax con conteos esperados, sin MC. Da un sesgo asintótico de (−0.98, −2.75) nm en el ideal C3, que coincide con el MC dentro de 0.1–0.2 nm en todos los casos honestos. Esto también es coherente con la tesis de Masullo, p. 127: con τ = 4 ns da ~2 nm a L = 100.
- Eficiencia (SBR 9), RMSE/CRB del ideal:

  | N | C0 | C3 |
  |---|---|---|
  | 100 | 0.97 | 1.23 |
  | 400 | 0.98 | 1.28 |
  | 1600 | 1.06 | 1.65 |

  En el realista pasa de 1.02 a 1.12 con N = 1600. Con N bajo la fuga queda tapada por el ruido; con N alto domina.
- El estimador (argmax con log p precomputado) es idéntico a `pos_MINFLUX` en 20/20 muestras por caso. Hubo 0 fallos.

## Hallazgos (candidate)
- **F201 CONCEPTUAL** (frontera con DISENO; lo decide el PI). Los estudios apagan la fuga con Tlife = 0.001 y b = dt/K. Con los valores medidos, el honesto queda sesgado 2.98 nm (3.4 CRB) y RMSE/CRB pasa de 1.07 a 2.75.
  - Autoría: heredado de Masullo (`simulations_example.py:51,134-136`) y mantenido por la autora (`simulation_misalignment.py:55,99-100`, `make_fig_eficiencia.py:40,76-77`).
  - El sesgo del estimador en sí es F104 de W2; F201 cuantifica el impacto en los estudios.
- **F202 IMPLEMENTACION** (según el criterio de validación de la propia autora). `realistic_ebp` normaliza cada PSF por su máximo y descarta `intensity_scale` (`realistic_ebp.py:100-103,152,181-185`). Las potencias de los haces difieren hasta ×1.38.
  - p_1 cambia −21 % y p_2, p_3 +9 %.
  - Un estimador con su modelo realista, aplicado a datos con las potencias reales, queda sesgado 10.6 nm. El CRB casi no cambia (2.348 → 2.333 nm).
- **F203 DISENO.** El RMSE y el |b| de los casos ingenuos, y del honesto con N bajo, los fija el radio de búsqueda.
  - Sustituto 20260703, ingenuo, N = 2095: el 100 % de las estimaciones queda en el borde y |b| ≈ R − |r0| (48 / 72 / 96 / 119 nm para R = 0.5 / 0.75 / 1.0 / 1.25 L).
  - Honesto realista, N = 100: RMSE 11.4 / 14.1 / 18.3 / 23.4 nm para los mismos R.
  - Además, la tabla mezcla un RMSE por eje con un |b| 2D; por eso en su log |b| = 62.76 > RMSE = 46.96.
- **F204 DISENO.** Los SE suponen normalidad. A N = 100 el SE real de RMSE/CRB es 1.86× el impreso (realista) y 1.55× (sustituto), con exceso de curtosis de hasta 6.8.
  - Su 1.89 ± 0.08 es en realidad ± ~0.13–0.15. La conclusión se sostiene, pero la no monotonía entre N = 200 y 400 es ruido.
  - El |b| tiene un piso de ruido de 0.34 nm con n = 250, contra un sesgo verdadero de 0.13 nm; los 0.52/0.27 nm del ideal son ruido.
- **F205 IMPLEMENTACION** (autora; referencia el F106 de W2 y cubre el F106a que pidió W2). El sesgo se mide contra R0_NM = (−5.07, −7.56), pero se simula en el píxel (−5, −8).
  - Eso agrega un sesgo espurio de 0.437 nm, unas 10 SE con 1000 muestras. Los honest_bias de comparison_metrics.csv (0.38–0.52) son casi todo este artefacto.
  - **Sí afecta a la comparación honesto/ingenuo:** contra R0_NM el ingenuo parece menos sesgado (0.302 frente a 0.436 nm); contra el píxel es al revés (0.663 frente a 0.013 nm).
  - La diferencia vectorial (−0.35, 0.56) nm no cambia con la referencia. run_final.log no está afectado porque usa r0 entero.
- **F206 DISENO.** La cadena run_and_save → run_final.log → build_doc no reproduce el documento. Hay 4 discrepancias: 1000 vs 300 muestras, r0, Ns/Nb 2000/95 vs 90/10, y casos Realista ausentes del log. Además build_doc escribe los parámetros a mano (l.535, 812-821). Ella ya lo había advertido para los logs sueltos; eficiencia.log sí es consistente.

## Descartadas (F290 y F201)
- **D1:** los fallos de sim_exp son 0 en todas las configuraciones de los estudios; el margen de ciclos es ≥ 77 fotones.
- **D2:** la convención de ejes es consistente (ida y vuelta exacta). La orientación física no se puede comprobar desde el código.
- **D3:** el reshape de Masullo tras quitar NaN es correcto.
- **D4:** multinomial ≡ sim_exp en C0. z = (−1.4, −1.0, −0.5, +2.6); el +0.6 % del haz 3 es el efecto F101 de sobrescritura.
- **D5:** el centrado entero de ebp_experimental es correcto.
- **D6:** zero_ratio es mejor sobre el mapa 2D que sobre el perfil; solo el docstring es inconsistente.
- **D7:** la comparación honesto/ingenuo es justa (misma semilla, r0, SBR y R).
- **D8:** el CRB con N = Ns+Nb es consistente con el MC de N fijo.

## Crédito a la autora (no reportado como abierto)
Ya había corregido tres cosas: la búsqueda sin cota (r_max_nm), la mezcla px/nm y el truncado de spaceToIndex. También validó el fondo contra la Ec. 3.5 y agregó semillas y SE (antes no había). La curva de cuantización px²/12, la separación pedestal/fondo, el MC rápido equivalente, la escalera reproducible y la advertencia sobre los logs también son suyos.

## Para Worker 2 (núcleo, no duplicado aquí)
- El modelo de pos_MINFLUX/crb_minflux sin fuga y con 1/K es F104.
- El redondeo del emisor a la grilla es F106.
- El pequeño exceso del haz 3 en sim_exp confirma F101 a 0.0105 fotones/ciclo.

## Lo que no pude resolver
- Sin las PSF 20260820 no reproduje los casos "Experimental" exactos (18.35 / 62.76 nm). El sustituto 20260703 muestra el mismo mecanismo de borde, pero no los mismos números.
- F202 supone que el máximo de cada `.npy` refleja la potencia relativa del haz. Es plausible, porque las 20260707 conservan maxima distintos (4.75–6.84), pero hay que confirmarlo con la autora.
- No corrí el test de aceptación, que no es mi tarea. No hice commit.
