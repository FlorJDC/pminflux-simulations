# r03 — writer (pasada final)

Leí: writer.md, state.json (119 afirmaciones: 88 verified, 15 unclear, 16 refuted), inbox.jsonl (sin indicaciones de R3),
r03-verifier.md, r03-fix-worker.md, r03-simuflux-checklist.md, r03-writer.md, r03-worker-1.md y r03-pi.md.
Toqué solo `scripts/build_report.py`, `report/index.html` y `out/provenance.json`. No hice commit.

## Cambios en scripts/build_report.py
- **Fines de línea.** Pasé el archivo de CRLF a LF.
- **Hashes.** `sha256()` ahora usa `provenance_sha.sha256_file`, que normaliza los fines de línea. Saqué `hashlib`.
- **Privacidad.**
  - `scrub()` corre sobre el HTML y sobre las cadenas de provenance.json.
  - La frase "C:\Data\psf\20260820 no existe" pasa a "las PSF de la calibración 20260820 no estaban disponibles".
  - Cualquier otra ruta `X:\Data…` o `X:\Users…` pasa a "(ruta local omitida)".
  - Arriba del documento agregué el banner "Documento privado: contiene datos no publicados; no compartir sin revisar".
- **Arreglos 1–13 de r03-verifier §(4):**
  - (1) Resumen: mezcla |b| ≤ 0.112 nm.
  - (2) Resumen: el máximo de d = n·T se toma sobre todas las tasas, lo que da ≤ 0.034 SE.
  - (3) "fotones en ventanas".
  - (4) §3: "es insesgado y alcanza el CRB asintóticamente". Va en el callout y en "por qué la simulación no lo podía ver".
  - (5) En F201/F205 dice "verificado en R2; TestStudyV2 es de R3, verificado en R3". La nota de study_v2 ahora es verificada y enlaza a §8.
  - (6) F107: portado y verificado en R3, con la fracción 1/7 y |z| ≤ 1.5. Agrega `sbr_reference`, marcado como del fix-worker.
  - (7) §8 study_v2 tiene tabla desde `summary`, con cinco filas:
    - mezcla con P conocidas, ideal y desalineada;
    - legado, ideal y desalineada;
    - ingenuo desalineado.
    
    Cada fila trae max|b|, RMSE, RMSE/CRB, la fracción en el borde y la eficiencia a N = 100/400/1600. Además:
    - una lectura: ≤ 0.12 nm y ≈ 1.00, legado ≈ 3.1 nm, ingenuo ≈ 8.6 nm;
    - la reproducción del verificador (claims 99–101);
    - el párrafo de Neyman-Scott (claim 102): no converge con más localizaciones y el sesgo baja ~1/N;
    - "a N = 100 el ajuste de potencias libres es inestable/degenerado" (claim 103).
    
    **No** usé 1.056/1.408/1.536, 3.0/3.9/9.3 ni `note_free_powers`. Tampoco muestro la fila ideal/ingenuo, que es idéntica a P conocidas.
  - (8) Guard b > T/K verificado en R3, sin guard en forward_probs/window_probs.
  - (9) La lista de refutadas/unclear quedó en dos grupos: "Corregido en esta revisión" y "Sigue abierto". Cada ítem dice cómo se resolvió. Para eso usé la tabla `OPEN_MAP`, que asigna por prefijo; lo que no tiene prefijo cae en abierto.
  - (10) Claim 59: "resuelto: d = n·T verificado en R2 con prueba y MC".
  - (11) §9: "≳10^7 (~10^7 a 5e-3, ~3·10^7 a 3e-3, ~2.5·10^8 a 1e-3)", con la etiqueta MIX-NDETECT.
  - (12) Las leyendas nuevas se toman de captions.json. Cada figura lleva la nota "números verificados en R3 [claim 111]"; en timeline, rate_sweep y dead_time agrega "ajustada en la pasada final".
  - (13) `_r3_pending` pasa a ser `_r3_verified`: las afirmaciones verificadas de R3 que salen del ledger. Excluyo las que tratan del propio documento (95, 97, 114).
- **Pasada final del fix-worker:** en §7 hay un bloque "Agregado en la pasada final" con estos ítems:
  - starts/offset;
  - `mixing_conditioning`;
  - la receta de emulación de sim_exp (p = 0.85);
  - `sbr_reference`;
  - el borde de `_fold`;
  - el sha robusto;
  - la suite de 75 OK.
  
  Todos van rotulados "cubierto por tests; revisión independiente parcial", con `reproduce` = el test correspondiente. La nota del README ahora cita las claims 92/94 del revisor de código.
- **§9: réplica de Nb = 0.** Leo `variant_Nb0_replica` del JSON: p = 0.957, 2.07·10^6 fotones, semilla 20460928, highest p = 0.872. Queda frente al p = 0.008 de `variant_Nb0`, rotulado como no re-verificado por otra ruta.
- **Nueva §10, auditoría contra el checklist SimuFLUX.**
  - Tabla de 21 filas: ítem, pregunta, estado, evidencia (el `numero` en negrita, más evidencia/nota/dónde desplegable), ref (F-ids enlazados y los scripts C0x con etiqueta propia) y verificación.
  - Conteo desde el JSON: 11 aplica-ok, 3 falla, 7 no aplica.
  - Crédito: resumen de lo que ella hizo bien, según r03-simuflux-checklist.md.
  - Las fallas se listan desde el JSON.
  - La columna "verificación" sale de `reports/r03-verifier-checklist.md`. Ese archivo **no existe**, así que dice **pendiente** en todas las filas y el resumen (§1) agrega "(verificación independiente pendiente)".
  - Cuando exista, `_chk_verif()` lee las entradas `CHK-<n>` del bloque claims. Una refutada tacha el estado y muestra el texto del verificador. Lo probé con un bloque falso en memoria.
- **Renumeración.** Límites pasa a ser §11 y el Apéndice §12. Actualicé las referencias a §11.
- **Otros.**
  - Supuestos: la nota de rendimiento dice que el arranque por bloques está resuelto y que queda O(n²).
  - Próximos pasos del PI: "Portar F107" aparece como hecho.
  - study_v2 y simuflux_checklist se agregaron a la tabla de versiones.

## Checks
- `python scripts/build_report.py` genera 857 798 bytes, 146 entradas de procedencia, 12 secciones y 0 placeholders.
- `check_provenance.py` da 146 tags, 146 entradas, 0 errores y 0 warnings.
- `python -m unittest tests.test_acceptance -v` pasa 6/6 OK. El sha de test_acceptance.py sigue siendo 5ad01fba….
- Texto del HTML: 0 "http", 0 "C:\Data", 0 "C:\Users", 0 `src="http`. provenance.json tampoco tiene "C:\Data" ni "http".

## Qué queda
- **Verificación del checklist.** Cuando exista `r03-verifier-checklist.md`, hay que volver a correr `python scripts/build_report.py`.
- **Siguen abiertos:** F154, autoría, tests débiles, n_mode poisson/KS/β libre, "highest" con fondo (documentado como limitación), O(n²) y converged 43→5.
- **Privacidad.** Siguen en el HTML "GithubPRO/p-minflux-main" (claim de autoría), nombres propios y datos no publicados (claim 97). El banner avisa que no se comparta.
