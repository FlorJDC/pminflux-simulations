OBJETIVO
========
Revisar críticamente los scripts de simulación de p-MINFLUX que la autora usaba
(`legacy/p-minflux-main`, copia de solo lectura de `GithubPRO/p-minflux-main`) y producir:

1. **Una versión mejorada del simulador** (`src/pminflux_sim/`), para p-MINFLUX pulsado a **20 MHz**
   (T = 50 ns, K = 4 haces intercalados, Δt = 12.5 ns). Debe incluir el dominio temporal:
   microtiempos con τ, IRF, ventanas de detección, fuga entre pulsos con modelo periódico,
   TCSPC con un fotón por ciclo y tiempo muerto, y fondo uniforme en el ciclo. Además, un
   estimador cuya verosimilitud es consistente con ese modelo directo (matriz de mezcla de
   fuga, fondo). Todo validado con tests.
2. **La validación de la matriz de mezcla** C_ij (fracción de fotones del haz j que cae en
   la ventana i) contra `sim_exp` del código legado y contra el simulador nuevo. Es el pedido
   explícito de la autora.
3. **Un reporte HTML autocontenido** (`report/index.html`) que diga, con evidencia
   reproducible:
   - qué estaba mal en la manera de simular;
   - qué se podría haber hecho distinto;
   - cuáles son **errores conceptuales** (modelo físico o estadístico equivocado), cuáles
     son **errores de implementación** (bugs) y cuáles son **decisiones discutibles o de
     diseño** (no son errores, pero limitan).
   Cada hallazgo lleva un script o test que lo demuestra, su impacto cuantificado y la
   corrección aplicada en la versión nueva.

FUENTES
=======
- `legacy/p-minflux-main/`: el código a revisar (`tools/tools_simulations.py` → `sim_exp`,
  `nMINFLUX`, `pos_MINFLUX`, `crb_minflux`; `tools/ebp.py`, `tools/realistic_ebp.py`,
  `simulations_example.py`, `simulation_misalignment.py`, `analyze_realistic_psf.py`,
  `documento/`, `NOTAS.txt`, `ESTADO_Y_PLAN_REALISMO_PSF.md`, `EBP_desalineamiento.docx`).
  `tools_analysis.py` y `simulations_example.py` son originales de L. Masullo; el resto lo
  escribió o refactorizó la autora.
- Handoff con toda la teoría y los números: `C:\Users\BANGHO\Documents\HANDOFF_githubpro-2b_papers_simulaciones.md`
  (papers, ecuaciones con página, fuga medida en los datos: ~12 % en la ventana 0 y 5.2 %
  global con τ = 4.21 ns y ventana [0, 10.1] ns, según `tracking_analysis/PIPELINE.md` §11).
- Proyecto de simulación previo, ya verificado: `GithubPRO/donut-beam-localization`
  (paquete `donutloc`: Fisher/CRB, estimadores, formas cerradas; se puede importar como
  referencia independiente).
- Nota privada con el análisis del código legado: `GithubPRO/donut-beam-localization/docs/private/C_pminflux_practice.md`.
- PDFs: `C:\Users\BANGHO\Documents\Doctorado\Papers` (tesis de Masullo cap. 3–4; Masullo 2021
  p-MINFLUX; Edorna 2025).
- PSF medidas, si hacen falta (solo lectura): `C:\Data\psf\20260820`.

CERCO
=====
- No modificar nada fuera de este proyecto: ni `GithubPRO/p-minflux-main`, ni
  `tracking_analysis`, ni `C:\Data`.
- **Proyecto PRIVADO:** contiene trabajo no publicado de la autora. No se sube a ningún
  remoto ni se publica (tampoco el HTML como artifact público).

LO QUE LAS FUENTES NO DICEN
===========================
- La **IRF**: gaussiana de ~300 ps FWHM (tesis, p. 117) como default, configurable.
- El **tiempo muerto del APD**: parámetro configurable. Su valor no está en las fuentes;
  usar un valor típico declarado como supuesto y barrerlo.
- La **tasa de conteo**: la del tracking (20–110 kHz, tesis/Masullo 2021) para evaluar el
  apilamiento.
- Clasificación de cada hallazgo: CONCEPTUAL / IMPLEMENTACIÓN / DISEÑO, con el criterio
  escrito en el reporte.

DISCIPLINA
==========
- Python 3.8, numpy, scipy y matplotlib. Tests con unittest. Semillas fijas.
- Todo hallazgo del reporte se reproduce con un script (`scripts/findings/F*.py`) o un test,
  y un verificador independiente lo confirma antes de entrar al reporte.
- Ser justo con la autora: distinguir lo heredado del código de Masullo de lo suyo, y
  reconocer lo que estaba bien (ella misma ya corrigió varios bugs y validó el término de
  fondo).
- No editar `tests/test_acceptance.py` (protegido por hash).

DEFINICIÓN DE TERMINADO
=======================
`python -m unittest tests.test_acceptance` pasa, y `python -m unittest discover -s tests`
pasa completo.

ENTREGABLE
==========
- `src/pminflux_sim/`: el simulador y el estimador nuevos.
- `scripts/validate_mixing_matrix.py`: la validación contra `sim_exp`, que escribe
  `results/mixing_validation.json`.
- `scripts/findings/F*.py` y `results/findings.json`: el registro de hallazgos (id, título,
  clase, archivo:línea del legado, escenario que falla, impacto cuantificado, corrección,
  script, estado de verificación).
- `report/index.html`: el reporte autocontenido, en español, con figuras embebidas.
- `README.md`: cómo correr todo.
