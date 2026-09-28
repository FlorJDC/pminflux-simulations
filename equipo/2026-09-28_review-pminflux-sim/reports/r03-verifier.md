# r03 — Verificador (ronda 3, final)

Leí intent.md, inbox.jsonl, state.json (84 afirmaciones: 66 verified, 10 unclear, 8 refuted), r03-pi/worker-1/worker-2/writer.
Todo mi código está en `work/verify/r03/`: vgeo.py, v1_study.py, v2_freepowers.py, v2b_fp_eval.py, v3_code.py, v3b_tmask.py,
v4_html_text.py, v5_chunk.py, más sus .json/.log. Reutilicé `work/verify/r02/mysim.py` (simulador propio fotón por fotón,
earliest + tiempo muerto no paralizable, numba) y `myest.py` (MLE propio: grilla + Newton por diferencias finitas, CRB propio).
**Ninguno importa `pminflux_sim`** para simular o estimar en (1). No edité nada fuera de `work/verify/r03/` y este reporte.

## Tests
- `python -m unittest discover -s tests` → **Ran 64 tests in 67.8 s, OK** (work/verify/r03/tests_discover.txt).
- `python -m unittest tests.test_acceptance -v` → **6/6 OK**, incluido `test_html_report_covers_every_finding`.
- sha256 de tests/test_acceptance.py = 5ad01fba…d457c, igual al de state.json.
- `check_provenance.py`: 93 tags, 93 entradas, 0 errores.

## (1) study_v2.json — reproducción independiente
Simulador propio (earliest, d = 22 ns, IRF 0.3, 2.5e-3/ciclo, N fijo = bloques de N fotones registrados consecutivos),
C propia (serie de CDF exponnorm), MLE y CRB propios, otra semilla (SeedSequence 31415926). Mismas 5 posiciones continuas,
400 locs/pos (N = 2095) y 200 locs/pos en el barrido.

| caso | máx\|b\| propio | máx\|b\| W1 | RMSE/CRB propio | W1 |
|---|---|---|---|---|
| ideal / mezcla P conocidas | 0.096 | 0.117 | 0.984 | 0.996 |
| desalineada / mezcla P conocidas | 0.059 | 0.086 | 1.002 | 1.003 |
| ideal / legado Ec. 3.5 | 3.107 | 3.116 | 1.638 | 1.671 |
| desalineada / legado | 3.142 | 3.176 | 1.724 | 1.726 |
| desalineada / ingenuo | 8.606 | 8.583 | 4.083 | 4.093 |

- CRB por eje (con fuga): **idéntico a 3 decimales** en las 5 posiciones × 2 geometrías × 4 valores de N (p. ej. ideal
  0.928/0.938/0.985/0.939/1.034; desalineada 0.953/0.973/0.975/1.012/1.089; N = 100 ideal 4.250…4.733).
- Geometría ingenua: L_eff = 103.0686 nm, φ = 1.61107 rad (igual a la del JSON).
- Barrido N = 100/400/1600 (RMSE/CRB medio), propio vs W1: legado ideal 1.185/1.212/1.513 vs 1.216/1.240/1.534;
  legado desalineada 1.151/1.246/1.585 vs 1.098/1.239/1.622; ingenuo 1.416/2.014/3.568 vs 1.365/2.041/3.645;
  mezcla P conocidas ideal 1.095/1.029/0.982 vs 1.067/0.998/0.999, desalineada 1.042/1.027/1.006 vs 1.003/1.003/1.024.
  Diferencias ≤ 0.08 absolutas (≈2–3 SE con 1000 locs por punto); la tendencia (legado e ingenuo empeoran con N; mezcla con
  P conocidas ≈1) se reproduce. Sesgos por posición del ingenuo y del legado coinciden con los del JSON a ≤ 2 SE.
- Fracción en el borde 0 en todos los casos N = 2095 (propio y W1).
- Nota: en study_v2 "ideal/ingenuo" es idéntico a "ideal/honesto_P_conocidas" (mismo modelo): conviene rotularlo o quitarlo.

**Potencias libres compartidas (Neyman-Scott)**: perfil de verosimilitud propio (Nelder-Mead exterior sobre 3 log-cocientes,
MLE propio interior por localización), conteos multinomiales del modelo de mezcla propio, EBP desalineado, verdad
P/P0 = 0.792/1.092/1.088, NM **arrancado en la verdad** (si algo, favorece a la verdad):

| N | locs/pos | P/P0 estimado | NLL(verdad) − NLL(ĥ) |
|---|---|---|---|
| 400 | 100 | 0.876/1.236/1.211 | 7.6 |
| 400 | 400 | 0.826/1.127/1.137 | 3.9 |
| 400 | 1600 | 0.851/1.172/1.187 | 38.4 |
| 400 | 3200 | 0.856/1.177/1.199 | 87.4 |
| 1600 | 1600 | 0.801/1.106/1.104 | 4.2 |
| 2095 | 400 | 0.791/1.093/1.082 | 0.8 |
| 400 (ideal, verdad 1/1/1) | 1600 | 1.079/1.070/1.073 | 39.6 |
| 100 | 100 (3 semillas) | 1.07/1.59/1.60; 1.01/1.46/1.41; 1.15/1.57/1.76 | 10–15 |
| 100 | 1600 | **3.00/3.97/8.86**, 12 % en el borde, máx\|b\| 25.7 nm | 779 |

- **Confirmado**: a N = 400 las potencias no convergen a la verdad al agregar localizaciones (1600 → 3200/pos: 0.851→0.856 …),
  y la ventaja de verosimilitud de ĥ sobre la verdad crece ~lineal con n (sesgo, no ruido). El número de W1
  (0.847/1.160/1.188 con 1600/pos) coincide con el mío (0.851/1.172/1.187) dentro del ruido. El sesgo baja como ~1/N
  (+7.5–9 % a N = 400 → +1.1–1.5 % a N = 1600 → ≲0.5 % a N = 2095). También pasa en la geometría ideal (+7 % a N = 400),
  coherente con los powers_estimated_rel del propio study_v2. Compatible con el R2 (≤0.8 % a N = 2095).
- **Refutado en el detalle a N = 100**: W1 dice "N = 100: 1.056/1.408/1.536 con 1600 por posición e inestable con pocas
  (3.0/3.9/9.3 con 100)". En mis datos con 1600/pos el máximo del perfil es la solución desbocada 3.00/3.97/8.86; el punto
  de W1 (1.056/1.408/1.536) tiene NLL 626 mayor y NM arrancado desde él (o desde potencias iguales) va a 3.00/3.97/8.86
  (v2b_fp_eval.json). Con 100/pos obtuve óptimos locales 1.0–1.15/1.4–1.6/1.4–1.8 (NM desde la verdad). Lo que sí se
  sostiene: a N = 100 el ajuste de potencias libres es inestable/degenerado (y study_v2 con 200/pos da 2.99/4.08/9.07 y
  26.8 nm, valor que sí está en el JSON). Los números específicos por n que da W1 para N = 100 no se sostienen; la frase
  correcta es "a N = 100 el MLE conjunto se desboca hacia potencias del anillo 3–9× (fracción en el borde ~12 %), tanto más
  cuanto más localizaciones".
- La recomendación (calibrar potencias aparte con N alto y pasarlas como conocidas) queda respaldada.

## (2) Código nuevo
- **Guard b > T/K** (v3_code.json): con b = 20, T = 50, K = 4, `simulate_counts`, `crb`, `mle_mixing` y `count_windows`
  levantan `ValueError("ventanas solapadas: b=20 > T/K=12.5 …")`; con `allow_overlap=True` emiten exactamente un
  UserWarning y siguen; b = 12.5 no avisa; b = 12.5000001 sí levanta. Observación: `estimate.forward_probs` y
  `mixing.window_probs` no tienen guard (funciones de bajo nivel; aceptable, pero no está dicho en la doc).
- **count_windows**: igual bit a bit a los counts de `simulate_counts` desde `return_tags` en 4 setups (a=0,b=10.1 earliest;
  a=5,b=10 none, cruza T; a=−0.5,b=12.5 highest; a=−3,b=12.5 earliest), igual al pasar tiempos absolutos ciclo·T+micro, e
  igual a mi regla propia `mod(t − (iT/K + a), T) < b`; sobre 2e5 tiempos uniformes en [−100, 300) coincide con intervalos
  explícitos en 4 configuraciones. Contra mi propia C a 1e-4/ciclo, con **mi** simulador (3.75e5 fotones): χ² p = 0.67,
  |z| ≤ 0.97. `mixing.window_probs` coincide con mi `my_probs` a 0.0 (máx. diferencia). No reproduje el p = 0.184 exacto de
  W1 (otra ruta, otro dato); sí la conclusión.
- **Chunking**: `mle_mixing` (fijo, free_bg, free_powers) y `mle_legacy` dan r/converged/powers idénticos bit a bit con
  chunk = 1, 13 y el default; chunk = 0 → ValueError.
- **F107 t_mask**: sin fondo, 0 fotones de señal en ciclos apagados **por ciclo de excitación**; por ciclo de llegada aparecen
  los de la cola que cruza el borde de ciclo (máscara alternante 1/0: 1.4 % de la señal llega al ciclo siguiente, que es
  física correcta con τ = 4.21 y el haz 3 a 37.5 ns; el test de W1 excluye ese borde). Con SBR 5, fracción en la mitad
  apagada (5 semillas × 200 locs × 1000): 0.14234/0.14232 (encendido primero, none/earliest), 0.14239/0.14273 (apagado
  primero), 0.14265/0.14268 (bloques de 2000) contra 1/7 = 0.142857: |z| ≤ 1.5. Los conteos por ventana con máscara
  siguen la mezcla con SBR efectiva 21/2 (p = 0.74). Máscara toda 1 = sin máscara, bit a bit.
- **converged**: 6000 locs con N = 10–50 (multinomial, R = 75): 6 converged=False (W1: 5). En 600 casos converged=True
  interiores, Nelder-Mead propio desde la estimación mejora la NLL ≤ 9.3e-8 y mueve ≤ 0.0075 nm; los 6 no convergidos
  están de verdad fuera del óptimo (0.21 nm, dNLL 3.5e-5). El "43 → 5" contra el código anterior no lo pude reproducir
  (no está el código R2).
- compare_legacy_vs_v2.json regenerado: sha256 de mixing/psf/estimate/simulate/script = archivos actuales, source v2sim; los
  100 números (|b|, RMSE/CRB de legado, mezcla y free_bg) coinciden a 3 decimales con `work/compare_rerun.txt` (R2, 10:52).

## (3) Figuras (miré los 6 PNG)
Todos los números de los captions coinciden con los JSON (comprobé cada uno). Sin texto encimado. Observaciones:
1. **timeline_20MHz**: el panel superior dibuja la IRF de 0.3 ns, pero el caption cita C[i][i] = 0.9092 (sin IRF; con IRF es
   0.8973). C[1][0] = 0.0467 vale para ambos. Corrección sugerida: "C[i][i] = 0.9092 sin IRF (0.8973 con la IRF dibujada)".
2. **mixing_validation**: correcto (χ² 5.66/p 0.129; 1927; desvíos −0.6/−1.6/−0.1/+2.2 y +27.6/−32.8/−10.3/+23.6).
3. **rate_sweep**: correcto, pero el título "Desvío de sim_exp respecto del modelo de mezcla" sugiere datos; las curvas son
   **predicciones** (el caption lo dice). Sugerido: "Desvío predicho…". Reescalado √(2000/n) verificado (0.2749·0.0310 = 0.0085).
4. **legacy_vs_v2**: correcto (legado 0.567–2.694 nm, 1.115–2.059; mezcla 0.011–0.112, 0.982–1.022).
5. **f201_leakage**: correcto (0.114→2.984; 0.924/0.864 = 1.07, 2.376/0.864 = 2.75, 2.376/0.945 = 2.51; 5.50→10.85). Solo
   muestra la semilla 20260825, mientras el texto da rangos de dos semillas: aceptable, el caption lo dice ("1000 muestras").
6. **dead_time_sweep**: correcto; el eje x es logarítmico con marcas en los 4 puntos (no está dicho); "p ≥ 0.30" es 0.296
   redondeado (d = 100, 5.5e-3): escribir "p ≥ 0.29" o "≈0.30". Las curvas d = 0/22 a baja tasa incluyen el piso de ruido MC.

## (4) report/index.html (texto extraído en work/verify/r03/index_text.txt)
Números: todos los que revisé coinciden con los JSON/ledger (resumen, tabla F104 y cocientes, tabla de 20 casos, C con y sin
IRF, tabla de validación, barrido de tasa, barrido de tiempo muerto, tarjetas F101–F206). Clases de las 16 tarjetas =
findings.json (1 CONCEPTUAL, 9 IMPLEMENTACION, 6 DISENO); 7 latentes = las marcadas "latente" en el ledger. Correcciones
literales de los verificadores presentes: F103 6.84/2.54 % y desplazamiento 0.88 vs 1.18; F111 sin paridad invertida;
F201 ≈2.5 contra 0.945; F203 R ≤ 1.0·L (71–72 %); F204 extrapolación rotulada; F205 0.912 correcto/0.960 inflado;
MIX-NDETECT ~1e7 a 5e-3; sesgo residual 0.02–0.035 + O(1/N) 0.036, ≤0.03 CRB. Crédito presente (§5 con 12 ítems, "qué estaba
bien" en cada tarjeta, Masullo para Tlife = 0.001). Tono justo ("el error se atribuye al método"). El "crimen inverso" está
bien explicado (término de problemas inversos; datos simulados con el mismo modelo que se invierte; se aclara que sim_exp sí
tiene el pliegue y que son los parámetros Tlife = 0.001, b = T/K los que lo reducen a la Ec. 3.5).

Arreglos concretos (sección — texto → texto corregido):
1. §1 Resumen, v2: "mezcla |b| ≤ 0.11 nm" → "mezcla |b| ≤ 0.112 nm" (máximo del JSON 0.11197).
2. §1 Resumen, tiempo muerto: "(≤ 0.033 SE, ruido MC)" → "(≤ 0.034 SE, ruido MC)" (d = 100 a 5.5e-3 da 0.0337; la tabla de §10
   del mismo HTML dice 0.034).
3. §1 Resumen, validación: "4.16·10^6 fotones detectados" → "4.16·10^6 fotones en ventanas" (definición de n_detected_total).
4. §3 "En una frase": "por construcción alcanza el CRB" → "por construcción es insesgado y alcanza el CRB asintóticamente"
   (a N = 100 el propio MLE con modelo correcto da RMSE/CRB 1.07).
5. Tarjetas F201 y F205, "En v2": la lista incluye `tests/test_usability.py::TestStudyV2::test_study_v2_json` bajo "los tests
   v2 … existen y pasan (verificado en R2)"; ese test es de R3. → "…(verificado en R2; TestStudyV2 es de R3, verificado en R3)".
6. Tarjeta F107, "En v2": "portado en R3 (Worker 1) … pendiente de verificación" → "portado en R3 y verificado en R3: sin
   señal en ciclos de excitación apagados; con SBR 5 la fracción en la mitad apagada es 1/7 (|z| ≤ 1.5)".
7. §8 "Estudio de desalineación con v2": el placeholder puede reemplazarse por los números verificados de este reporte (tabla
   de (1)), con estas precisiones: potencias libres sesgadas O(1/N) (confirmado a N = 400/1600) y desbocadas a N = 100; NO
   transcribir "1.056/1.408/1.536 con 1600 por posición" ni "3.0/3.9/9.3 con 100 por posición" (refutados en el detalle).
8. §10 "Ventanas solapadas": "en R3 se agrega un ValueError explícito (salvo allow_overlap=True), pendiente de verificación"
   → "…, verificado en R3 (simulate_counts, crb, mle_mixing, count_windows; forward_probs y window_probs no lo tienen)".
9. §10 "Puntos abiertos": el encabezado dice que son afirmaciones "que siguen vivas … pendientes de corrección en esta ronda",
   pero la mayoría ya está corregida en el propio texto (MIX-NDETECT, F103-num, F111, F201 clase, F202 clase, F203, 11.15 %,
   ≤0.11 nm, guard b > T/K, docstring/converged, usabilidad). → separar en "refutadas y ya corregidas en este documento (ver
   tarjeta)" y "siguen abiertas" (F154, autoría, n_mode poisson/KS/β libre, tests débiles, rendimiento O(n²)).
10. §10 "Puntos abiertos", el unclear "El modelo directo … la hipótesis de W2 'd = n*T anula el sesgo' no está verificada"
    contradice §10 ("d = n·T anula el sesgo exactamente", verificado en R2). → añadir "(resuelto: d = n·T verificado en R2 con
    prueba y MC)".
11. §9 "Lectura física": "detectables solo sumando ~10^7 fotones" → "detectables solo sumando ≳10^7 fotones (~10^7 a 5e-3,
    ~3·10^7 a 3e-3, ~2.5·10^8 a 1e-3)" (MIX-NDETECT corregida).
12. Leyenda timeline (figura 1): ver (3).1. Título rate_sweep: ver (3).3.
13. "Trabajo de la ronda 3 pendiente de verificación": pasar a verificados los ítems de este reporte (guard, count_windows,
    chunk, converged, F107, study_v2 P conocidas/legado/ingenuo, compare regenerado, tests 64 OK) y marcar refutado el detalle
    N = 100 de potencias libres.

Observación lateral (no es error del HTML, que no lo cita): `mixing_validation.json:variant_Nb0` (λ de W1, Nb = 0, 2.07e6
fotones) da χ² p = 0.0078 para la mezcla (−2.9 SE en w0); el ledger MIX-VALID (verificado con otro λ) da p = 0.61 con Nb = 0.
Probablemente fluctuación, pero si se cita esa variante hay que decirlo.

## Lo que no pude resolver
- "converged=False baja de 43 a 5": no tengo el código anterior; verifiqué el comportamiento actual.
- p = 0.184 exacto del test de ventanas de W1 (reproduje la conclusión con otro camino y otros datos).
- README y tabla de migración: no revisados línea por línea contra la API (fuera de mi tarea explícita); los nombres que usé
  (simulate_counts, count_windows, mle_mixing, mle_legacy, crb, window_probs, beam_positions, lambda_beams) existen y funcionan.

```claims
[{"status":"verified","text":"R3 suite: python -m unittest discover -s tests = 64 tests OK (67.8 s, Py 3.8); tests.test_acceptance 6/6 OK incluido test_html_report_covers_every_finding; sha256 de test_acceptance.py = 5ad01fba...d457c intacto; check_provenance 93/93 sin errores"},
 {"status":"verified","text":"study_v2 (N=2095, 5 posiciones continuas, setup medido, earliest d=22, IRF 0.3, 2.5e-3/ciclo) reproducido con simulador, MLE y CRB propios y otra semilla: mezcla con potencias conocidas max|b| 0.096 (ideal) / 0.059 nm (desalineada) vs 0.117/0.086, RMSE/CRB 0.984/1.002 vs 0.996/1.003; legado Ec. 3.5 3.107/3.142 nm vs 3.116/3.176, RMSE/CRB 1.638/1.724 vs 1.671/1.726; ingenuo desalineado 8.606 nm y 4.083 vs 8.583 y 4.093; mezcla con P conocidas max|b| <=0.12 nm y RMSE/CRB ~1.00; fraccion en el borde 0"},
 {"status":"verified","text":"study_v2: CRB por eje con fuga identico a 3 decimales en 5 posiciones x 2 geometrias x N=100/400/1600/2095; geometria ingenua L_eff=103.0686 nm, phi=1.61107 rad"},
 {"status":"verified","text":"study_v2 barrido de eficiencia N=100/400/1600 (RMSE/CRB medio) reproducido dentro de <=0.08 (~2-3 SE): legado ideal 1.185/1.212/1.513 (W1 1.216/1.240/1.534), legado desalineada 1.151/1.246/1.585 (1.098/1.239/1.622), ingenuo 1.416/2.014/3.568 (1.365/2.041/3.645), mezcla P conocidas ideal 1.095/1.029/0.982 (1.067/0.998/0.999): el legado y el ingenuo empeoran con N, la mezcla con P conocidas queda ~1"},
 {"status":"verified","text":"Potencias libres compartidas + una posicion por localizacion: sesgo de parametros incidentales (Neyman-Scott) confirmado con perfil de verosimilitud propio (EBP desalineado, verdad 0.792/1.092/1.088): N=400 da 0.851/1.172/1.187 con 1600 locs/pos y 0.856/1.177/1.199 con 3200 (W1 0.847/1.160/1.188), no converge a la verdad y NLL(verdad)-NLL(hat) crece ~lineal con n (38 -> 87); el sesgo baja ~1/N (N=1600: 0.801/1.106/1.104; N=2095: 0.791/1.093/1.082); tambien en la geometria ideal (+7 % a N=400)"},
 {"status":"refuted","text":"W1-R3 'con N=100 las potencias libres dan 1.056/1.408/1.536 con 1600 locs por posicion e inestable con pocas (3.0/3.9/9.3 con 100)' — con datos propios de 1600/pos el maximo del perfil es la solucion desbocada 3.00/3.97/8.86 (12 % en el borde, max|b| 25.7 nm); el punto 1.056/1.408/1.536 tiene NLL 626 mayor y Nelder-Mead desde el (o desde potencias iguales) llega a 3.00/3.97/8.86; con 100/pos se obtienen optimos locales 1.0-1.15/1.4-1.6/1.4-1.8. Lo que se sostiene: a N=100 el ajuste de potencias libres es inestable/degenerado"},
 {"status":"verified","text":"Guard de ventanas solapadas: con b=20, T=50, K=4 simulate_counts, estimate.crb, estimate.mle_mixing y windows.count_windows levantan ValueError 'ventanas solapadas'; con allow_overlap=True emiten un UserWarning y siguen; b=T/K=12.5 no avisa y b=12.5000001 levanta; forward_probs y mixing.window_probs no tienen guard"},
 {"status":"verified","text":"windows.count_windows coincide bit a bit con los counts de simulate_counts desde return_tags (4 setups incl. ventana que cruza T y a<0), da lo mismo con tiempos absolutos, coincide con una regla propia mod(t-(iT/K+a),T)<b y con intervalos explicitos en 2e5 tiempos uniformes; sobre datos del simulador propio a 1e-4/ciclo (3.75e5 fotones) chi2 contra C propia p=0.67; window_probs = modelo propio exacto"},
 {"status":"verified","text":"Arranque en grilla por bloques: mle_mixing (fijo, free_bg, free_powers) y mle_legacy dan r, converged y powers identicos bit a bit con chunk=1, 13 y el default; chunk=0 -> ValueError"},
 {"status":"verified","text":"F107 portado: con t_mask y sin fondo no hay fotones de señal de ciclos de excitacion apagados (por ciclo de llegada aparece solo la cola que cruza el borde de ciclo, 1.4 % de la señal con mascara alternante, fisica correcta); con SBR 5 la fraccion de fotones en la mitad apagada es 1/7 (0.1423-0.1427, |z|<=1.5, dos fases y bloques de 2000 ciclos, none y earliest); mascara toda 1 = sin mascara bit a bit"},
 {"status":"verified","text":"converged: con 6000 locs N=10-50 quedan 6 converged=False (W1: 5); en 600 casos converged=True interiores Nelder-Mead propio mejora la NLL <=9.3e-8 y mueve <=0.0075 nm; los no convergidos estan 0.21 nm y 3.5e-5 de NLL fuera del optimo"},
 {"status":"unclear","text":"W1-R3 'converged=False baja de 43 a 5 con el cambio' — no esta el codigo previo para comparar; solo se verifico el comportamiento actual"},
 {"status":"verified","text":"compare_legacy_vs_v2.json regenerado en R3: source v2sim, sha256 de mixing/psf/estimate/simulate/script iguales a los archivos actuales, y los 100 numeros (|b| y RMSE/CRB de legado, mezcla y free_bg) coinciden a 3 decimales con work/compare_rerun.txt de R2"},
 {"status":"verified","text":"Figuras report/figs: los numeros de los 6 captions coinciden con sus JSON (timeline C[1][0]=0.0467; validacion chi2 5.66 p=0.129 y 1927, desvios +27.6/-32.8; rate_sweep 0.009/0.026/0.086/0.90/3.06 y 0.093/0.097; legacy_vs_v2 0.57-2.69 nm, 1.12-2.06, mezcla 0.011-0.112, 0.982-1.022; f201 0.11->2.98, 1.07->2.75, 2.51 contra 0.945; dead_time d=50 0.012-0.024, d=100 0.015-0.034, d=22 0.030/0.057/0.079/0.099)"},
 {"status":"refuted","text":"Caption de timeline_20MHz 'C[i][i] = 0.9092' junto al panel que dibuja la IRF de 0.3 ns — 0.9092 es sin IRF; con la IRF dibujada es 0.8973 (C[1][0]=0.0467 vale para ambos). Menor"},
 {"status":"refuted","text":"Caption de dead_time_sweep 'p del chi2 contra la mezcla >= 0.30' para d=50/100 — el minimo es 0.296 (d=100, 5.5e-3). Menor"},
 {"status":"verified","text":"report/index.html: las clases de las 16 tarjetas coinciden con findings.json (1 CONCEPTUAL, 9 IMPLEMENTACION, 6 DISENO), las correcciones literales de los verificadores (F103, F111, F201, F203, F204, F205, MIX-NDETECT, sesgo residual) estan aplicadas, hay credito explicito (seccion 5 y 'que estaba bien' por tarjeta, Masullo en F201), el tono atribuye el error al metodo, y el 'crimen inverso' esta bien explicado; tablas F104, 20 casos, C, validacion, barridos de tasa y tiempo muerto coinciden con los JSON"},
 {"status":"refuted","text":"report/index.html resumen 'mezcla |b| <= 0.11 nm' y 'd = n·T ... <= 0.033 SE' — el JSON da max 0.112 nm (0.11197) y 0.034 SE (0.0337; la propia tabla de la seccion 10 dice 0.034)"},
 {"status":"refuted","text":"report/index.html tarjetas F201/F205: 'los tests v2 de los hallazgos existen y pasan (verificado en R2)' incluye tests/test_usability.py::TestStudyV2::test_study_v2_json, que es de R3"},
 {"status":"refuted","text":"report/index.html seccion 10 'Puntos abiertos ... siguen vivas (refutadas y pendientes de correccion en esta ronda)' — la mayoria (MIX-NDETECT, F103-num, F111, clases F201/F202, F203, 11.15 %, <=0.11 nm, guard b>T/K, docstring/converged, usabilidad) ya esta corregida en el mismo documento, y el unclear 'd = n*T no verificada' contradice la seccion 10 que lo da (correctamente) por verificado en R2"},
 {"status":"unclear","text":"mixing_validation.json:variant_Nb0 (lambda de W1, Nb=0, 2.07e6 fotones) da p=0.0078 para la mezcla (-2.9 SE en w0), mientras MIX-VALID con otro lambda da p=0.61; no se cita en el HTML; probablemente fluctuacion, falta una repeticion con otra semilla para decidir"}]
```
