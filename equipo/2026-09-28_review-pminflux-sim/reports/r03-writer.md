# r03 — Writer: reporte HTML (Tarea 3)

## Qué hice
- Escribí `scripts/build_report.py`, que genera `report/index.html` (803 125 bytes) y
  `equipo/2026-09-28_review-pminflux-sim/out/provenance.json` (93 entradas).
  - Lee `results/{findings,findings_discarded,mixing_validation,mixing_claims,mixing_rate_sweep,dead_time_sweep,compare_legacy_vs_v2,study_v2}.json`,
    `report/figs/captions.json`, `state.json`, `README.md` y los bloques `claims` de `reports/r03-worker-{1,2}.md`.
  - Ningún número de resultados está tipeado a mano. Los números vienen de los JSON o se extraen, con una regex, del texto
    verificado del ledger (sesgo residual por tasa finita).
  - Hay una derivación: e^(−T/K/τ) se calcula con los parámetros del JSON.
- La página es autocontenida:
  - CSS y JS inline, sin fuentes externas.
  - Las 6 figuras van embebidas en base64.
  - Hay **0** URLs `http(s)://` en el archivo.
  - Se puede imprimir: al imprimir, los `<details>` se abren solos.
  - Tiene tabla de contenidos con enlaces a cada id de hallazgo, modo claro/oscuro y botones de expandir y contraer.
- Construí primero con placeholders y lo volví a correr cuando estuvieron las figuras (W2), `README.md`, `study_v2.json`,
  `example_end_to_end.py` y el `findings.json` regenerado (W1).

## Secciones
1. Resumen ejecutivo.
2. Cómo se revisó: verificación independiente, conteo del ledger, criterio de clases con tabla, y autoría "no verificable
   sin git" salvo lo que sostiene el verificador A.
3. Crimen inverso (F104 + F201):
   - física a 20 MHz: 12.5 ns entre pulsos, cola del 5.1 %, C_{i,i−1} = 0.0467, C_ii = 0.9092 y 4.16 % fuera de las ventanas;
   - figura de la línea de tiempo;
   - tabla de F104 desde `compare_legacy_vs_v2.json` (sesgo, CRB y cocientes);
   - impacto de F201 y figura;
   - cómo se evita, con crédito a ESTADO…md:115-117 y a Masullo por Tlife = 0.001.
4. Hallazgos por clase. Hay una tarjeta por cada uno de los 16 ids, con clase, latente, crimen inverso, dónde, impacto, qué
   estaba bien, corrección y estado en v2. En un bloque desplegable van el escenario, la autoría con author_basis, el script,
   quién lo verificó y las correcciones aplicadas.
5. Lo que estaba bien. Incluye ESTADO…md:115-117, :116 y :64-67, F290-D7, F151, F152 y F153.
6. Qué podría haber hecho distinto: una tabla con 10 prácticas, cada una enlazada a sus hallazgos.
7. La versión mejorada: módulos (docstrings), las dos tablas de migración de README §9, el inicio rápido del README y los comandos.
8. Legado contra v2: tabla de los 20 casos con SE bootstrap y fracción en el borde, reproducción del verificador y figura.
   study_v2 queda como placeholder (ver abajo).
9. Validación de la matriz de mezcla: C sin IRF y con IRF, tabla de fracciones y χ², contaminación de w0, barrido de tasa,
   afirmaciones MIX-*, dos figuras y la nota MIX-ACCFORMULA.
10. Límites:
    - tabla del barrido de tiempo muerto y figura, resultado d = n·T y sesgo residual con el texto corregido;
    - supuestos (22 ns e IRF 0.3, supuestos), SBR incidente de 'highest', PSF 20260820 ausentes, autoría, rendimiento y guard b > T/K;
    - **Puntos abiertos**: las 18 afirmaciones refuted o unclear del ledger, las afirmaciones de R3 pendientes de verificación y
      la lista de próximos pasos del PI.
11. Apéndice: sospechas descartadas (F154 marcado unclear).
- Al final, sha256 de cada archivo leído.

## Correcciones del verificador, aplicadas literalmente
Hay una caja por tarjeta.
- **F103**: 6.84 % y 2.54 %; es un desplazamiento, 0.88 contra 1.18 nm.
- **F111**: sin "paridad invertida".
- **F201**: ≈2.5 contra el CRB con fuga.
- **F203**: 100 % en el borde solo con R ≤ 1.0·L.
- **F204**: la extrapolación va rotulada.
- **F205**: 0.912 es el valor correcto y 0.960 el inflado. W1 ya lo corrigió en `findings.json`; el builder tiene además un
  reemplazo de respaldo.
- **MIX-NDETECT**: se usa el texto corregido de `mixing_claims.json` (~1e7 a 5e-3).
- **Sesgo residual**: 0.02–0.035 nm + O(1/N) ~0.036 nm, ≤0.03 CRB.
- Clases según el inbox: F104 CONCEPTUAL; F201 y F202 DISEÑO.

## Decisiones de transcripción (solo lo verificado)
- **study_v2.json**: existe, pero no lo verificó nadie. Queda un placeholder visible en §8, sin números. Sus números solo
  aparecen en "Trabajo de la ronda 3 pendiente de verificación" (§10), rotulados como no verificados. Si el verificador sella
  una afirmación que mencione `study_v2`, el builder la transcribe sola al volver a correr.
- **F107**: aparece como "portado en R3 (W1), pendiente de verificación". Los demás v2_tests figuran como "verificado en R2"
  (afirmación W1-R2 de 17 ids). No uso el campo `v2_fix_status` de `findings.json`, que en F205 todavía dice "Test fijado,
  aún no verificado", en contradicción con R2.
- **Figuras y captions** (W2, R3): se dibujan desde JSON verificados, pero cada figura lleva la nota "verificación pendiente".
- **README** (R3): las tablas de migración se toman del README y van rotuladas como "pendiente de revisión independiente".

## Checks
- `python agent-team/bin/check_provenance.py report/index.html equipo/2026-09-28_review-pminflux-sim/out/provenance.json`
  da 93 tags, 93 entradas, 0 errores y 0 warnings.
- `python -m unittest tests.test_acceptance -v` da 6/6 OK, incluido `test_html_report_covers_every_finding`.
- No corrí la suite completa: no me toca a mí. W1 informa 64 OK.

## Qué queda abierto
- Placeholder: los resultados de `study_v2.json` en §8, a la espera del verificador.
- Si el verificador confirma W1/W2 (guard, count_windows, F107, study_v2, figuras), basta con volver a correr
  `python scripts/build_report.py`:
  - la nota de "pendiente" de las figuras desaparece si una afirmación verificada nombra el archivo;
  - study_v2 se transcribe si una afirmación verificada lo menciona.
  - Para F107 y el README hay que tocar el texto a mano: dos líneas en `card()` y `s_v2()`.
- No hice git commit ni publiqué nada.
