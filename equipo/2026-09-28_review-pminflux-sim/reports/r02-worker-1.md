# r02 — Worker 1: registro de hallazgos fusionado y corregido

## Qué hice
- Leí `state.json` (49 afirmaciones), `inbox.jsonl` (decisiones de R2), `r01-verifier-A.md`, `r01-verifier-B.md`,
  `r02-pi.md`, `results/findings_A.json` y `results/findings_B.json`, y en el legado `NOTAS.txt`, `OBJECTIVE.md`
  (autoría), `ESTADO_Y_PLAN_REALISMO_PSF.md:64-67,115-117` (créditos) y los rangos de líneas de `tools_simulations.py` de
  cada hallazgo (para la regla de autoría del PI).
- Escribí `scripts/build_findings.py`. Es determinista: lo corrí dos veces y los tres JSON dan el mismo sha256. Lee los
  borradores y `state.json` sin editarlos y escribe:
  - `results/findings.json`: **16 entradas**, todas `status: "verified"`. Son F101, F102, F103, F104, F106, F107, F108,
    F109, F110, F111, F201, F202, F203, F204, F205 y F206.
  - `results/findings_discarded.json`: **16 entradas**. 15 son `discarded-verified`: F105, F151, F152, F153, D-iv, D-ii,
    D-vi y F290-D1…D8. F154 queda `unclear`, con el campo `missing`.
  - `results/mixing_claims.json`: **10 entradas**. Son las 9 MIX-* verificadas más MIX-NDETECT, con `status:
    "verified-corrected"`, `text_original` y `corrections_applied`.
- Campos de cada hallazgo:
  - los que pide la aceptación: `id`, `title`, `class`, `legacy_location`, `scenario`, `impact`, `fix`, `script` y `status`;
  - `author` y `author_basis`;
  - `what_was_right`, que no queda vacío en ninguna entrada (en F108 y F110 el borrador lo tenía vacío);
  - `verified_by`: el verificador más el texto literal de `state.json`;
  - `corrections_applied`: una lista {from, to, source};
  - `v2_test` (el id fijado del plan), `v2_tests` (con su rol: antes/después) y `v2_fix_status`;
  - `crimen_inverso`, true solo en F104 y F201, que además llevan `crimen_inverso_note`;
  - `draft_source`.
- Las rutas de `legacy_location` llevan todas el prefijo `legacy/p-minflux-main/`.

## Clases (con las decisiones del inbox de R2)
- CONCEPTUAL (1): F104.
- IMPLEMENTACION (9): F101, F102, F103, F107, F108, F109, F110, F111 y F205.
- DISENO (6): F106, F201, F202, F203, F204 y F206.

## Autoría
Apliqué la regla del orquestador para esta tarea, que en la base textual difiere del default de r02-pi.md.

| valor | hallazgos | base |
|---|---|---|
| "autora" | F201–F206 | "declaración de la autora en NOTAS.txt (sin historial git)" |
| "autora" | F107 | "indicio: comentario en español; sin git" (lo sostuvo el verificador A) |
| "Masullo-original" | F111 | docstring "[Lars]", l.250 (sostenido por A) |
| "no verificable" | F101, F102, F103, F104, F106, F108, F109, F110 | tools_simulations.py, sin git |

- **F201–F206.** Hay un matiz declarado en `author_basis`: `NOTAS.txt` solo dice *"tools/tools_analysis.py y
  simulations_example.py son los scripts originales de L. Masullo"*. La atribución a la autora es **por exclusión**, igual
  que en OBJECTIVE.md ("el resto lo escribió o refactorizó la autora").
- **F201.** `author_basis` dice que el defecto viene de Masullo: simulations_example.py:51 (Tlife = 0.001) y :134-136.
- **F107.** La ruta rápida es la de A. Hay un matiz declarado: el comentario propio de la ruta rápida (l.454-457) está en
  inglés; el bloque en español es el anterior (l.423-440).
- **F111.** Lars Richter es coautor del código original, según el encabezado de tools_simulations.py.
- **F104.** Queda "no verificable" para el código. El comentario "EXACTAMENTE" se atribuye como indicio de la autora dentro
  de `author_basis`, y se aclara que ese comentario es correcto en su régimen.
- **Ningún tools_simulations.py queda como "Masullo-original"**, salvo F111.
- La afirmación AUTORÍA (`unclear`) se resuelve con este default y **no** se declara verificada.

## Resolución de las afirmaciones vivas que me tocan
- **MIX-NDETECT (refuted):** corregida en mixing_claims.json. A 5e-3 bastan ~1e7 fotones (A lo detectó con 1.2e7: mezcla
  p = 4.6e-4, 'highest' p = 0.76), y el 3e7 corresponde a 3e-3. El ~2.5e8 a 1e-3 lo derivé de la escala 1/tasa² (W1 dio
  2.6e8, sin re-correr).
- **F103-num (refuted):**
  - La pérdida esperada es 6.84 % / 2.54 %.
  - Los 0.338 nm son un desplazamiento: el sesgo total es 0.88 nm con las ventanas del legado y 1.18 nm con ventanas
    periódicas, con τ = 4.21.
  - Con τ = 0.001 suma 0.063 nm.
  - El doble conteo es 10.9 % (no 11.2 %).
- **F111-comentarios (refuted):** saqué la paridad del título, del fix y de la ubicación (:273-289). En `what_was_right`
  quedó que los comentarios son correctos.
- **F201 clase (unclear):**
  - Clase DISENO.
  - Cociente ≈2.5 contra el CRB con fuga (0.945 nm) y 2.73–2.75 contra el CRB sin fuga (0.864 nm).
  - Crédito a ESTADO…md:115-117.
  - "no declarado en el .docx ni en los scripts".
- **F202 clase (refuted):**
  - Clase DISENO.
  - El supuesto "máximo del .npy = potencia del haz" quedó explícito en `scenario` y en el título, con el orden repetido en
    3 calibraciones: 245/205/291/253, 6.4/4.8/6.8/5.3 y 21.2/18.4/26.6/19.7.
  - Crédito a ESTADO…md:116.
- **F203 (refuted):** "100 % en el borde" pasa a valer solo para R ≤ 1.0·L (71–72 % con 1.25·L). Agregué la nota del 1 %
  con R = 0.75·L y el EBP realista.
- **F154 (unclear):** va a descartados con `status: "unclear"` y `missing`. Queda confirmado el ValueError; el 88.5 % y el
  p = 0.74 no se reprodujeron.
- **Descartados:**
  - D1: el margen es 3/55/76/105 (no "≥77").
  - D4: quité la atribución del +2.6σ a F101.
  - D3: la línea correcta es l.182-183.
  - F152 lleva la nota "cota ≤3.6e-4 no verificada".

## Diff por hallazgo
El diff completo está en `corrections_applied` de cada entrada. Resumen:

| id | desde → hacia | fuente |
|---|---|---|
| F101 | 0.38 %/0.46 % → 0.379 %/0.461 %; escenario 0.5/ciclo, 25 SE → 0.8/ciclo, \|z\| ≤ 1.5, 47 SE; "ver W1" → latente a las tasas del tracking (≤0.05 SE) | A |
| F102 | 1.28/69.9 nm → 1.25/70 nm; se omite "100 % en el borde, media (74.4, −4.2)" (no verificado) | A |
| F103 | 5.9/2.8 % → 6.84/2.54 %; "sesgo extra 0.34/0.06" → desplazamiento 0.338, total 0.88 contra 1.18, 0.063; 11.2 → 10.9 %; se omite "fondo 0.24" | A + inbox |
| F104 | "1.0–2.7 CRB" → 1.04–2.67 CRB de crb_minflux / 0.92–2.45 CRB real; + matices (domina la fuga, 1.05–2.78 nm con b = 12.5; ~2.5 puntos del CRB son los fotones fuera de ventana; √N; no cambia lo publicado); 46 % → 45.8 %; 26.1 → 26.06; χ² del borrador → MIX-VALID | A + PI |
| F106 | 3.40, (−0.22, 0.25) → ~3.3–3.4, ~(−0.25, 0.25) | A |
| F107 | 51.4 → 51.35 %; se omite "cw: 0" (F154 unclear); autoría → autora (indicio) | A + PI |
| F108 | se omiten los ejes correctos 3.03/9.09… (no verificados); `what_was_right` completado | A |
| F109 | "361 nm; centro (−20.5, 20.5)" → "361 px; índice (120, 120)"; autoría → no verificable | A |
| F110 | se omite "CRB 1.05 nm"; autoría → no verificable; `what_was_right` completado | A |
| F111 | se quita la paridad (título, fix, :273-289); se omiten los ángulos 120/240/0 contra 210/330/90 | A + inbox |
| F201 | CONCEPTUAL → DISENO; 2.75 → 2.73–2.75 (sin fuga) / ≈2.5 (con fuga, 0.945); "sin declararlo" → "no declarado en el .docx ni en los scripts" + ESTADO:115-117; valores → rangos de 2 semillas; 0.25/3.1 → 0.30/3.03; (−0.98, −2.75) → (−1.02, −2.67); eficiencia 1.23/1.65 → 1.19/1.53 | B + inbox |
| F202 | IMPLEMENTACION → DISENO; supuesto explícito; crédito a ESTADO:116; se omite "geom 5.1 → 8.8" (B: 8.5) | B + inbox |
| F203 | 100 % para R ≤ 1.0·L (71–72 % con 1.25), 1 % con R = 0.75 realista; 13.9/51.0/82.1 → 13.2/50.0/81.9; 1.8/52 → 1/50 %; 119 → 118; honesto → 12–26 nm | B + inbox |
| F204 | ±0.13–0.15 rotulado como extrapolación; 1.86/1.55/0.74 → 1.88/1.63/0.77; 6.8/4.7 → 6.6/4.6; 0.34 → ≈0.36; se omite la no monotonía (no verificada) | B + inbox |
| F205 | + RMSE 0.912 → 0.960 (analyze_realistic_psf.py:88); 0.437/0.012, 0.302/0.663 → 0.43/0.02, 0.31/0.67; título 0.445 → desplazamiento 0.4455; se omite honest_bias_nm (no verificado) | B + inbox |
| F206 | 4 → 5 discrepancias ("Experimental ingenua 1/2") | B + inbox |

## Auditoría: ¿alguna entrada contradice su texto en state.json?
`build_findings.py` lista los números de `title` + `impact` que **no** aparecen en el texto de `state.json` para ese id (ni
en MIX-*). Los revisé uno por uno y **ninguno contradice** `state.json`. Todos salen de los reportes de los verificadores
de R1, de r02-pi.md o son parámetros:

| id | número | de dónde sale |
|---|---|---|
| F102 | 0.0 | literal |
| F103 | 0.063 | r01-verifier-A.md / r02-pi.md |
| F103 | 49.5 | [49.5, 50) = a = −0.5 |
| F104 | 0.92, 2.45 | r01-verifier-A.md / r02-pi.md |
| F104 | 1.025, 1993.5, 2095 | r01-verifier-A.md |
| F201 | 20 | 20 MHz |
| F202 | 9.66, 35.6 | r01-verifier-B.md |
| F203 | 2095 | N |
| F204 | 0.08 | su SE impreso |
| F204 | 1.6, 1.9 | redondeo de 1.63/1.88 en el título |
| F204 | 20260820 | carpeta |
| F205 | 0.04, ~10σ, 1000 | r01-verifier-B.md |
| F206 | 4.28, N = 100 | r01-verifier-B.md |

## Tests
- `python -m unittest tests.test_acceptance.Acceptance.test_findings_registry_is_complete_and_verified` → `Ran 1 test ...
  OK`.
- `python -m unittest discover -s tests` → 24 tests, 1 error. Es `test_html_report_covers_every_finding`
  (FileNotFoundError: `report/index.html`), que el plan da como esperable. El resto pasa.
- sha256 de `tests/test_acceptance.py` = 5ad01fbabc91fd420ca637bb8791c79c79fd6359d6e6c1b4591a16d4fccd457c: igual al
  guard, así que no se tocó.

## Qué no resolví / queda abierto
- **Los ids de `v2_test` apuntan a tests que todavía no existen** (tests/test_simulate.py y test_estimate.py son de W2 y
  W3). `v2_fix_status` dice "Test fijado, aún no verificado". R3 tiene que comprobar que resuelvan. F107 tiene `v2_test:
  null`.
- **F205:** copié literalmente la frase verificada "el RMSE … pasa de 0.912 a 0.960 nm en el ideal". No la interpreté:
  el r01-verifier-B.md también dice que el RMSE/CRB honesto ≈1.09 "sería ≈1.02 contra el píxel", y eso sugiere el sentido
  contrario (0.912 sería el valor reportado). Conviene que el verificador fije el sentido antes de que entre al HTML.
- **MIX-NDETECT:** el "~2.5e8 a 1e-3" es mi extrapolación por la escala 1/tasa²; no está medido.
- **Autoría:** sigue sin poder verificarse (no hay git). La base de F201–F206 es una declaración por exclusión de NOTAS.txt.

```claims
[{"status":"verified","text":"W1-R2: results/findings.json tiene 16 entradas (F101-F104, F106-F111, F201-F206), todas status verified, clase en {CONCEPTUAL:1 (F104), IMPLEMENTACION:9, DISENO:6 (F106,F201,F202,F203,F204,F206)}, script existente; test_findings_registry_is_complete_and_verified pasa"},
 {"status":"verified","text":"W1-R2: results/findings_discarded.json tiene 16 entradas: 15 discarded-verified (F105,F151,F152,F153,D-iv,D-ii,D-vi,F290-D1..D8) y F154 unclear con 'missing'; D1 margen 3/55/76/105; D4 sin atribución a F101; F152 con nota 'cota ≤3.6e-4 no verificada'"},
 {"status":"verified","text":"W1-R2: results/mixing_claims.json tiene 10 entradas (9 MIX-* verificadas + MIX-NDETECT verified-corrected: a 5e-3 bastan ~1e7, 3e7 corresponde a 3e-3)"},
 {"status":"verified","text":"W1-R2: scripts/build_findings.py es determinista (dos corridas, mismos sha256 de los tres JSON) y no edita findings_A/B.json ni state.json"},
 {"status":"verified","text":"W1-R2: autoría: F111 Masullo-original ([Lars]); F107 autora (indicio, ruta rápida); F201-F206 autora (NOTAS.txt, por exclusión; F201 nota el origen en simulations_example.py:51); F101-F104,F106,F108-F110 no verificable; ningún hallazgo con what_was_right vacío"},
 {"status":"unclear","text":"W1-R2: ninguna entrada contradice su texto en state.json — los números fuera de state.json (F103 0.063; F104 0.92-2.45, 1.025; F202 9.66->35.6; F205 ~10σ; F206 4.28) salen de r01-verifier-A/B.md; falta que un verificador lo confirme entrada por entrada, y fijar el sentido de 'RMSE 0.912 -> 0.960' en F205"}]
```
