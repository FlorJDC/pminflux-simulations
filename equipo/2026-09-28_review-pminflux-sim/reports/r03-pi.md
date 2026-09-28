# r03 — PI: plan de la ronda 3 (de 3, final)

## Estado leído
- `state.json` (ronda 2): el grueso de simulate/estimate/findings está **verificado**. Hay 3 afirmaciones `refuted`
  de R2 y 7 `unclear`. Checks: 50 tests, 49 OK; la única falla es `test_html_report_covers_every_finding`, porque
  todavía no existe `report/index.html`. El hash de `test_acceptance.py` está intacto.
- `inbox.jsonl` (PRIORIDAD MÁXIMA, sin vencimiento):
  - (R1) El pedido de la autora. Hay que ser justos: separar lo heredado de Masullo y reconocer lo que estaba bien.
  - (R2) F104 es CONCEPTUAL; F201 y F202 son DISENO. El reporte tiene que explicar el **"crimen inverso"**, que es
    lo que une F104 con F201.
  - (R2) Se aplican al pie de la letra todas las correcciones de los verificadores. La autoría queda "no verificable
    sin historial git", salvo lo que sostiene el verificador A.
- `test_acceptance.py`: `report/index.html` tiene que contener cada `id` de `findings.json` (son 16: F101–F104,
  F106–F111, F201–F206). También tiene que contener, en minúsculas, "conceptual", "implementaci" y "dise", y no puede
  tener ningún `src="http`.
- En `results/` están disponibles: findings.json (16 entradas, todas con `what_was_right`, `author_basis` y
  `crimen_inverso`), compare_legacy_vs_v2.json (20 casos, source v2sim), mixing_validation.json,
  mixing_rate_sweep.json (6 tasas), dead_time_sweep.json (earliest con d en {0, 22, 50, 100} y highest con d = 0,
  a tasas de 1e-3 a 0.0105 por ciclo), findings_B.json y findings_discarded.json.

## Cómo resuelvo las afirmaciones vivas
| afirmación | resolución en R3 |
|---|---|
| refuted: no hay guard para b > T/K | W1: se levanta `ValueError` explícito en `simulate._check`, `estimate.crb` y `mle_mixing` cuando las ventanas se solapan (b > T/K), salvo con `allow_overlap=True`, que avisa con `warnings.warn`. Test con b = 20. |
| refuted: 11.15 % del doble conteo | W1: la referencia del test pasa a 0.11175 y el comentario cita la cuadratura. En findings.json/build_findings también, si aparece. |
| refuted: "≤0.11 nm, no viene del estimador" | El texto correcto, para README y reporte: la tasa finita induce 0.02–0.035 nm y el MLE tiene un sesgo O(1/N) de ~0.036 nm con N ~ 2000; todo queda ≤0.03 CRB. Esa frase no está en ningún JSON, solo en r02-worker-3.md, así que el writer y W1 usan la versión corregida. |
| unclear: d = n·T | Lo **verificó** el verificador en R2 (prueba + MC con d = 35/50/75/100). Entra al reporte y al README como resultado verificado. |
| unclear: rendimiento de la grilla | W1 parte en bloques el arranque en grilla. El O(n²) del tiempo muerto a saturación se documenta en el README como limitación (fuera del régimen del tracking). |
| unclear: tests débiles | W1 endurece `test_compare_json_complete` (source == "v2sim" y sha256 actuales). F204 SE>0, el umbral frágil de test_low_rate y la fórmula de F102 van al backlog. |
| unclear: docstring free_bg y converged=False en el óptimo | W1 corrige el docstring (el factor es 1.000–1.038x) y marca converged=True cuando dNLL ≤ 1e-6. |
| unclear: highest con fondo a tasa alta | **Default declarado:** se documenta como limitación (v2 fija el SBR incidente y sim_exp el registrado; es un 0.5 % a 0.0105 por ciclo). |
| unclear: n_mode poisson, KS con d>T, etc. | Quedan en "límites" del reporte y en el backlog. No se afirman como verificados. |
| unclear: usabilidad (obligatorio en R3) | Tarea 1 completa. El port de F107 es la última prioridad de W1; si no entra, el reporte dice "no portado". |
| F205 redacción | 0.912 nm es el RMSE correcto (contra el píxel simulado). 0.960 es lo que da el script legado, inflado por el desplazamiento de 0.4455 nm. W1 lo corrige en build_findings.py. |

## Plan: 2 workers + writer, archivos disjuntos
Después vienen el verificador (tareas de W1, figuras de W2) y el code-reviewer (diff de W1). Al final corren
`python -m unittest discover -s tests` y la aceptación.

1. **Worker 1: usabilidad + correcciones.**
   - Archivos: `src/pminflux_sim/{__init__,simulate,estimate}.py`, `src/pminflux_sim/windows.py` (nuevo),
     `tests/test_{simulate,estimate,windows,usability}.py`, `scripts/build_findings.py` → `results/findings.json`,
     `scripts/example_end_to_end.py`, `scripts/study_misalignment_v2.py` → `results/study_v2.json`, `README.md`.
   - **No** toca: `mixing.py`, `legacy/`, `tests/test_acceptance.py`, `report/`.
2. **Worker 2: figuras.**
   - Archivos: `scripts/make_report_figures.py` → `report/figs/*.png` y `report/figs/captions.json`.
   - Solo lee `results/*.json` y `equipo/.../work/w3/*.json`.
3. **Writer: reporte.**
   - Archivos: `scripts/build_report.py` → `report/index.html` y `equipo/2026-09-28_review-pminflux-sim/out/provenance.json`.
   - Construye con placeholders y se vuelve a correr cuando existan las figuras y `study_v2.json`.

### Tarea 1 (Worker 1)
1. Guard b > T/K: `ValueError("ventanas solapadas: b=%g > T/K=%g ...")` en `simulate._check`, `estimate.crb` y
   `estimate.mle_mixing`. `allow_overlap=True` permite seguir con `warnings.warn` (la CRB multinomial deja de ser
   válida). Test: con b = 20, T = 50 y K = 4 levanta el error; con allow_overlap avisa.
2. `tests/test_simulate.py:157-158`: la referencia del doble conteo pasa de 0.1115 a **0.11175** (tolerancia de MC
   sin cambios) y el comentario cita "cuadratura 0.111746".
3. `build_findings.py`, F205: 0.912 nm es el RMSE correcto contra el píxel simulado (-5,-8); 0.960 lo produce el
   script legado, inflado por 0.4455 nm. Regenerar `results/findings.json`. Deben quedar los mismos 16 ids, todos
   `verified`, y los `v2_test` tienen que existir.
4. `__init__.py`: exponer los submódulos `mixing`, `simulate`, `estimate`, `psf` y `windows`, más los nombres
   públicos clave (`SimParams`, `simulate_counts`, `mle_mixing`, `mle_legacy`, `crb`, `mixing_matrix`,
   `window_probs`, `count_windows`) y `__version__ = "2.0.0"`. Mantener todo lo que hoy exporta. Test
   `tests/test_usability.py`: los imports y un ejemplo mínimo de menos de 2 s.
5. Nuevo `src/pminflux_sim/windows.py`: `count_windows(microtime_ns, T=50, K=4, a=0.0, b=10.1, macro_index=None,
   return_outside=False)`. Pliega el microtiempo con `t % T` (maneja a < 0 y ventanas que cruzan T) y devuelve
   conteos por ventana, más los fotones fuera de ventana. Si se pasa `macro_index` (el id de localización), agrupa.
   Usa desigualdades medio abiertas [inicio, fin), así que el 0.0 no tiene tratamiento especial: F102 se evita
   **porque los fotones reales no tienen ceros artificiales**, y se documenta. Validaciones: b > T/K lleva al guard y
   hay un error si el microtiempo no es finito. Tests en `tests/test_windows.py`:
   - las fracciones sobre microtiempos simulados con `return_tags` coinciden con `simulate_counts`, exactas;
   - un caso de ventana que cruza T;
   - un caso con a < 0;
   - las fracciones coinciden con `window_probs` en el límite de baja tasa (χ², p > 1e-3).
6. Arranque en grilla del MLE partido en bloques (`chunk=` por defecto, unos 2e4 locs). Test: el resultado es
   idéntico con y sin chunking.
7. Endurecer `test_compare_json_complete`: exigir `source == "v2sim"` y que los sha256 de `versions` coincidan con
   los archivos actuales de simulate/estimate. Si el cambio de estimate/simulate cambia el sha, **regenerar**
   `results/compare_legacy_vs_v2.json` con `scripts/compare_legacy_vs_v2.py` (misma semilla) y comprobar que los
   números de los 20 casos no cambian más allá de lo esperable (el chunking y el guard no deberían cambiarlos).
   Informar el diff.
8. Docstring de estimate:31. Con free_bg local, el CRB crece 1.000–1.038x en los casos estudiados, no "mucho".
   `converged=True` si dNLL ≤ 1e-6 en el óptimo. Con test.
9. `scripts/example_end_to_end.py`: setup medido (τ = 4.21, [0, 10.1], IRF 0.3, d = 22, a 2.5e-3/ciclo, Ns 2000,
   SBR 21). Cubre simular → contar ventanas → C → MLE de mezcla contra el legado → CRB → imprimir tabla. Tiene que
   correr en menos de 30 s.
10. `scripts/study_misalignment_v2.py` → `results/study_v2.json`. Reemplazo de `simulation_misalignment.py` y del
    estudio de eficiencia de la autora, con el simulador y el estimador v2 en el setup medido:
    - Casos: ideal, EBP desalineado (desplazamientos de haz y potencias distintas, del orden de F202: potencias
      [21.02, 16.65, 22.96, 22.86]) × estimador (honesto con mezcla y potencias libres, ingenuo con la geometría
      ideal, legado Ec. 3.5).
    - Por caso informa |b|, RMSE, RMSE/CRB (CRB con fuga), fracción en el borde y SE por bootstrap (sin suponer
      normalidad, por F204). Barrido de eficiencia en N ∈ {100, 400, 1600}.
    - Emisor fuera de la grilla (continuo), con referencia = posición simulada (F205).
    - Semilla fija, sha del código dentro del JSON y **runtime ≤ 3 min**. Como las PSF 20260820 no están, usa la
      dona analítica y lo declara.
11. `README.md` en español:
    - instalación (`pip install -e .` o `sys.path`; si no existe un `pyproject.toml`/`setup.cfg` mínimo, crearlo);
    - cómo correr tests, ejemplo, estudio, validación y figuras/reporte;
    - convenciones: N = Ns+Nb detectados en el ciclo completo, SBR = Ns/Nb, β, L, fwhm, ventanas
      `[i·T/K + a, +b]` módulo T, CRB por eje;
    - supuestos: tiempo muerto de 22 ns (no medido), IRF gaussiana de 0.3 ns FWHM centrada, fondo uniforme;
    - limitaciones: modelo directo sin distorsión de tasa finita, con sesgo de 0.02–0.035 nm más el sesgo O(1/N)
      del MLE de ~0.036 nm, todo ≤0.03 CRB; 'highest' fija el SBR incidente; tiempo muerto O(n²) a saturación;
      b ≤ T/K;
    - **resultado d = n·T** (el sesgo por tiempo muerto se anula exactamente, con la prueba en una línea);
    - tabla de migración legado → v2: sim_exp → simulate_counts, nMINFLUX → windows.count_windows,
      pos_MINFLUX → mle_mixing (y mle_legacy para comparar), crb_minflux → crb, psf/ebp_centres →
      psf.beam_positions/lambda_beams, cov_ellipse → estimate.cov_ellipse, Tlife = 0.001 → tau real, más la
      convención de parámetros.
12. Última prioridad, solo si hay tiempo: portar F107 (máscara on/off de parpadeo en simulate_counts) con test, y
    actualizar el `v2_test` de F107. Si no entra, se reporta "no portado".
- Cierre: `python -m unittest discover -s tests` completo en verde, salvo el HTML, que depende del writer. Reporte
  en `reports/r03-worker-1.md` con afirmaciones precisas.

### Tarea 2 (Worker 2)
- Crear `scripts/make_report_figures.py` (matplotlib Agg, semilla fija, dpi ~130, ancho ~7 in, rótulos en español
  con unidades). Escribe PNG en `report/figs/` y `report/figs/captions.json`, que es `{archivo: {"title", "caption",
  "source": "results/…json:clave"}}`. Solo lee los JSON existentes: no re-simula salvo el esquema, que es analítico
  con `pminflux_sim.mixing`.
- Figuras:
  1. `timeline_20MHz.png`, un esquema del ciclo de T = 50 ns. Muestra los 4 pulsos cada 12.5 ns, las ventanas
     [i·12.5, +10.1], la cola exponencial τ = 4.21 de un pulso invadiendo la ventana siguiente (sombreado con
     C[i][i-1] = 0.0467 anotado) y la IRF de 0.3 ns. Debe mostrar, en un panel aparte, el supuesto de los estudios
     (Tlife = 0.001, b = 12.5): una fuga nula.
  2. `mixing_validation.png`: las fracciones por ventana de sim_exp (con barras de ±SE) contra el modelo de mezcla
     y contra el ingenuo, más un panel con los desvíos en SE. Pone el p-valor de cada modelo en la leyenda.
  3. `rate_sweep.png`, desde mixing_rate_sweep.json: el desvío highest y earliest contra la mezcla, en SE por
     localización de 2000 fotones, en función de la tasa por ciclo (eje log). Marca la banda del tracking
     (1e-3–5.5e-3/ciclo = 20–110 kHz).
  4. `legacy_vs_v2.png`, desde compare_legacy_vs_v2.json: |b| y RMSE/CRB por posición, para los estimadores legado,
     mezcla y mezcla con free_bg, en paneles SBR 6/21 × IRF 0/0.3. Incluye la línea RMSE/CRB = 1 y el sesgo
     asintótico del legado.
  5. `f201_leakage.png`, desde findings_B.json o work/w3/F201_out.json: el ideal honesto y el realista honesto o
     ingenuo, con fuga (τ = 4.21, [0, 10.1]) y sin ella (Tlife = 0.001, b = 12.5). Muestra |b| y RMSE/CRB, con la
     aclaración de que el CRB no tiene fuga (0.864) y la línea del CRB con fuga (0.945 → cociente ≈2.5).
  6. `dead_time_sweep.png`, desde dead_time_sweep.json: el máximo |sesgo| en SE por localización contra la tasa,
     para d = 0/22/50/100 y para highest. Rotula que d = 50 y d = 100 (n·T) no tienen sesgo, y que 22 ns es un
     supuesto.
- **Mirar cada PNG** con Read. Tiene que ser legible, sin texto encimado, con los ejes rotulados y los números
  consistentes con el JSON (anotar 2–3 valores en el caption). Cada caption dice qué se ve, qué conclusión se saca
  y de dónde sale.
- Reporte en `reports/r03-worker-2.md`, con la lista de figuras y los valores clave leídos de cada JSON.

### Tarea 3 (Writer)
- Crear `scripts/build_report.py`, que genera `report/index.html` en español, autocontenido: CSS inline, PNG en
  base64 y **ningún** `src="http`. Los números **se leen** de results/*.json (findings, compare_legacy_vs_v2,
  mixing_validation, mixing_rate_sweep, dead_time_sweep, findings_discarded, study_v2 si existe) y de
  captions.json. Nada tipeado a mano, salvo el texto explicativo. Cada número lleva una etiqueta `[src:clave]` que
  resuelve en `equipo/2026-09-28_review-pminflux-sim/out/provenance.json` con el JSON, la clave y cómo
  reproducirlo. Si falta una figura o study_v2.json, pone un placeholder visible; se vuelve a correr al final.
- Secciones:
  1. Resumen ejecutivo.
  2. Cómo se revisó: agent-team, verificación independiente, qué quiere decir "verified" y el criterio de clases.
  3. **El error conceptual central, el "crimen inverso"** (F104 + F201). Explicación intuitiva con la línea de
     tiempo a 20 MHz: con 12.5 ns entre pulsos y τ = 4.21, un 4.7 % de cada haz cae en la ventana siguiente; si
     se simula con el mismo modelo que usa el estimador, el estudio no puede ver el desajuste.
  4. Hallazgos por clase (CONCEPTUAL / IMPLEMENTACIÓN / DISEÑO), con **todos** los ids de findings.json. Por
     cada uno: escenario, impacto, fix, test v2, autoría, author_basis y what_was_right.
  5. Lo que estaba bien: el crédito, incluidos sus propios fixes y validaciones (el término de fondo validado;
     ESTADO…md:115-117 ya pedía IRF/lifetime medidos; :116 ya recomendaba potencias distintas; :64-67 ya advertía
     F206; la comparación honesta/ingenua justa, F290-D7).
  6. Qué podría haber hecho distinto: prácticas concretas. Simular con un modelo más rico que el del estimador,
     parámetros medidos, emisor fuera de la grilla, referencias correctas, SE por bootstrap, un pipeline
     reproducible que genere el documento y tests.
  7. La versión mejorada: qué cambió, la tabla de migración (la misma del README) y cómo usarla (el ejemplo).
  8. Resultados legado contra v2 (y study_v2 si está verificado).
  9. Validación de la matriz de mezcla.
  10. Límites y supuestos: tiempo muerto de 22 ns supuesto, IRF 0.3 supuesta, sesgo por tasa finita (texto
      corregido: 0.02–0.035 nm + O(1/N) ~0.036 nm, ≤0.03 CRB), d = n·T, 'highest' con SBR incidente, PSF 20260820
      ausentes y sustituto 20260703 rotulado, autoría no verificable sin git, y lo `unclear` sin reproducir.
  11. Apéndice: sospechas descartadas (findings_discarded.json, con F154 marcado `unclear`).
- Usar **solo** contenido verificado del ledger, con las correcciones de los verificadores literales:
  - F103: 6.84/2.54 %; el efecto es un desplazamiento, 0.88 contra 1.18 nm.
  - F111: sin "paridad invertida".
  - F201: ≈2.5 contra el CRB con fuga.
  - F203: 100 % en el borde solo con R ≤ 1.0·L.
  - F204: rotular la extrapolación.
  - F205: 0.912 correcto, 0.960 inflado.
  - MIX-NDETECT: ~1e7 a 5e-3.
- Tono justo y pedagógico: el error se atribuye al método, no a la persona.
- Correr `python -m unittest tests.test_acceptance -v` y abrir el HTML generado para revisarlo.
- Reporte en `reports/r03-writer.md`.

## Condición de corte
Todavía no hay `[[DONE]]`: falta el HTML, falta verificar las tareas 1 y 2, y la aceptación está en rojo. Se puede
declarar DONE cuando pasen `discover -s tests` completo y la aceptación, y el verificador y el code-reviewer
confirmen W1/W2 y el HTML (que los números del HTML coincidan con los JSON).

## LO QUE MÁS SE PODRÍA HACER
1. Validar v2 contra datos reales 20260707: contar microtiempos con `count_windows` y comparar con el τ y la fuga
   medidos (~12 % en w0, 5.2 % global). Es la prueba de que el modelo directo describe el instrumento. Costo: ~1
   ronda (1 worker + verifier).
2. Medir el tiempo muerto real del APD y reemplazar el supuesto de 22 ns. Cambia el sesgo por tasa finita salvo
   con d = n·T. Costo: una medición y un rerun del barrido.
3. Rehacer los estudios con las PSF medidas 20260820 cuando estén en disco. Los números "Experimental"
   (18.35/62.76/1.89) no se reprodujeron. Costo: ~0.5 ronda.
4. Incluir en el modelo directo la distorsión de TCSPC/tiempo muerto a tasa finita, en primer orden. Elimina el
   sesgo residual de ~0.03 CRB a tasas altas. Costo: 1 ronda (worker + verifier).
5. Endurecer los tests débiles (F204 SE>0, el umbral de test_low_rate con varias semillas, F102 con una fórmula
   independiente). Costo: pequeño.
6. Reproducir por otra ruta n_mode = 'poisson', el KS con d > T, beta libre y el control cruzado con pos_MINFLUX
   (siguen `unclear`). Costo: ~0.5 ronda del verificador.
7. Punto fijo del tiempo muerto en O(n log n) para saturación. Solo importa fuera del régimen de tracking. Costo:
   pequeño a medio.
8. Portar F107 (máscara de parpadeo), si W1 no llegó. Costo: pequeño.
9. Recuperar la autoría con el historial de la autora (si ella tiene git o backups), para cerrar el "no
   verificable". Costo: depende de ella.
