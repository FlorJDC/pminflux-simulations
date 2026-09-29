# HANDOFF: cómo retomar este proyecto desde otra sesión o cuenta

Escrito el 2026-09-28 al cerrar la sesión (poca memoria, poco tiempo). Léelo antes que cualquier
otra cosa. Todo lo que se menciona está commiteado en `master`.

## 1. Qué es y en qué estado quedó

- **Proyecto:** revisión crítica del simulador p-MINFLUX de la autora (`legacy/p-minflux-main`,
  solo lectura) y versión mejorada `pminflux_sim` v2 (`src/`). Incluye la validación de la matriz
  de mezcla (fuga entre ventanas) contra `sim_exp` y un reporte HTML de hallazgos. El contrato
  completo está en `OBJECTIVE.md`.
- **Trabajo del equipo:** `equipo/2026-09-28_review-pminflux-sim/` (metodología agent-team: ver
  `AGENTS.md` y `CLAUDE.md`).
- **Estado del ledger** (`state.json`): `status = "done"`, ronda 3 de 3. Checks: 75 tests
  unitarios OK. Aceptación: `tests.test_acceptance` 6/6 OK.
- **Entregable:** `report/index.html`, autocontenido (abrir en el navegador). Tiene 16 hallazgos:
  - CONCEPTUAL: F104.
  - IMPLEMENTACIÓN: F101, F102, F103, F107, F108, F109, F110, F111, F205.
  - DISEÑO: F106, F201, F202, F203, F204, F206.
- **Procedencia:** cada número del reporte lleva `[src:clave]`, que resuelve en
  `equipo/2026-09-28_review-pminflux-sim/out/provenance.json`.
- **Ledger:** 140 afirmaciones, de las cuales 106 están verificadas, 18 refutadas y 16 sin
  decidir (`unclear`). Las refutadas y las `unclear` se resolvieron con correcciones o quedan
  declaradas como límites en el reporte (ver §4).

El trabajo **está terminado** según la definición de la persona. Lo que sigue es opcional: el
backlog de §4 y, si se quiere, integrar el resultado o compartirlo con la autora.

## 2. Poner en marcha en otra máquina o cuenta

```bash
git clone <URL-del-repo-privado> pminflux-sim-v2
cd pminflux-sim-v2
# Python 3.8+ con numpy, scipy y matplotlib
pip install -e .                    # o: sys.path.insert(0, "src")
python -m unittest discover -s tests          # tiene que dar OK (~75 tests, 1-2 min)
python -m unittest tests.test_acceptance -v   # aceptación de la persona: NO editar este archivo
python scripts/example_end_to_end.py          # ejemplo de uso en unos segundos
```

- Los tests comparan sha256 del código con los guardados en `results/*.json`. Desde el fix de R3
  los hashes son robustos a los finales de línea (CRLF o LF), así que un clone con
  `core.autocrlf=true` también da verde.
- Si cambias algo en `src/`, regenera los JSON:
  - `python scripts/compare_legacy_vs_v2.py` (~1 min).
  - `python scripts/study_misalignment_v2.py` (~45 s).
  - Después, `python scripts/make_report_figures.py` y `python scripts/build_report.py`.
- La guía de uso completa, en español, está en `README.md`: instalación, convenciones, supuestos,
  resultado d = n·T y tabla de migración legado → v2.

## 3. Orden de lectura para entender todo

1. `OBJECTIVE.md`: qué pidió la autora.
2. `report/index.html`: el resultado (resumen, "crimen inverso" F104+F201, hallazgos, límites).
3. `README.md`: cómo usar v2.
4. `equipo/2026-09-28_review-pminflux-sim/`:
   - `inbox.jsonl`: indicaciones humanas. **No vencen.**
   - `state.json`: todas las afirmaciones con su estado, el backlog y el historial.
   - `reports/r0N-<rol>.md`: lo que hizo cada rol en cada ronda. Para lo último, leer los de R3:
     `r03-pi.md` (plan), `r03-worker-1.md` (usabilidad y fixes), `r03-worker-2.md` (figuras),
     `r03-writer*.md` (reporte), `r03-verifier*.md` y `r03-code-reviewer.md` (verificación),
     `r03-fix-worker.md` (correcciones posteriores), `r03-simuflux-checklist.md` (auditoría de
     21 ítems).
5. `results/*.json`: los números, todos reproducibles con semilla y sha del código.

## 4. Qué quedó sin terminar (backlog, por prioridad)

1. **Validar v2 contra datos reales 20260707.** Contar los microtiempos con
   `pminflux_sim.count_windows` y comparar con τ y con la fuga medidos (~12 % en w0, 5.2 % global).
   Es la prueba de que el modelo directo describe el instrumento.
2. **Medir el tiempo muerto real del APD.** Los 22 ns son un SUPUESTO. La IRF de 0.3 ns FWHM
   también es supuesta. Con d = n·T el sesgo de tiempo muerto se anula (demostrado).
3. **Rehacer los estudios con las PSF medidas 20260820** cuando estén en disco. Hoy se usa la dona
   analítica con los centros y potencias de `Resultados/realistic_psf/fit_parameters.csv`.
4. **Confirmar con la autora el supuesto de F202** (el máximo de cada `.npy` es la potencia del haz).
5. **Distorsión de tasa finita.** Incluir en el modelo directo la distorsión de TCSPC y tiempo
   muerto a tasa finita. Hoy el sesgo residual es ≤ 0.03 CRB.
6. **Tests débiles.** Quedan F204 (solo comprueba SE > 0), el umbral de `test_low_rate` y F102 con
   una fórmula independiente. Además, `n_mode='poisson'`, el KS con d > T y β libre no tienen una
   ruta de verificación independiente.
7. **Autoría.** No se puede verificar sin el historial git de la autora; hace falta que ella lo
   aporte.
8. **Potencias libres.** Las potencias libres compartidas tienen sesgo de parámetros incidentales
   (Neyman-Scott). Se recomienda calibrarlas aparte. El verificador corrigió los números de N = 100
   que daba W1: los válidos están en `r03-verifier*.md`.

Para trabajar sobre el backlog con la metodología del proyecto, abrir un trabajo **nuevo** (en
Claude Code: `/equipo-nuevo <intent>`) en lugar de reabrir este, que está cerrado. El PI tiene
que leer `state.json` e `inbox.jsonl` de este trabajo como antecedente.

## 5. Reglas que no hay que romper

- **Trabajo PRIVADO y no publicado de la autora.** El repositorio remoto tiene que ser
  **privado**. No publicar artifacts ni páginas.
- No editar `legacy/` ni `tests/test_acceptance.py` (su hash está en `state.json`).
- Lo verificado queda verificado: no se re-deriva. Una afirmación `refuted` o `unclear` sigue viva
  hasta que se resuelva.
- Una ronda por pedido, y la persona decide qué sigue.

## 6. Para subir a GitHub (si todavía no está)

El repositorio local ya tiene todo commiteado en `master`. No tiene remoto porque `CLAUDE.md`
pedía "sin remoto". Para subirlo:

```bash
# 1) Crear en github.com un repositorio PRIVADO vacío, p. ej. pminflux-sim-v2 (sin README).
# 2) Desde esta carpeta:
git remote add origin https://github.com/<usuario>/pminflux-sim-v2.git
git push -u origin master
# 3) Para que otra cuenta lo retome: Settings > Collaborators > agregar la otra cuenta.
```

- `equipo/…/work/review/r03/venv/` (~219 MB, un entorno virtual de verificación) está en el disco
  pero no en git.
- `jobs/` y `__pycache__/` tampoco se versionan (`.gitignore`).
