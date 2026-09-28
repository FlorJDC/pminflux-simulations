# r03 — code-reviewer (ronda 3, final)

Alcance: `git diff 0a0c475 HEAD` (commit ea48b3d, 33 archivos). Leí el ledger (intent, state.json, inbox,
r03-pi, r03-worker-1, r03-writer, r02-code-reviewer) y el diff real de `src/`, tests y scripts. No edité
ningún archivo del proyecto. Todo lo que corrí está en
`equipo/2026-09-28_review-pminflux-sim/work/review/r03/` (clon, venvs, salidas y scripts de prueba).

## 1. Suite completa

| Dónde | Resultado |
|---|---|
| Árbol de trabajo original (`python -m unittest discover -s tests`, Py 3.8.6) | **Ran 64 tests in 118.4 s, OK** |
| Clon nuevo (`git clone` local; `core.autocrlf=true`, el default de Git para Windows) | **Ran 64, FAILED (failures=2)** |

Los que fallan en el clon son `test_estimate.TestCompare.test_compare_json_complete` y
`test_usability.TestStudyV2.test_study_v2_json`. Mensaje: `sha256 ... desactualizado respecto de mixing.py`.

**Defecto real (reproducibilidad).** El sha256 se calcula sobre los bytes crudos de los `.py`. El índice de git
guarda LF (`git ls-files --eol`: `i/lf w/lf`). Un clon con `autocrlf=true` los saca con CRLF y cambian los 6 sha de
`src/pminflux_sim/*.py` y de los scripts (p. ej. mixing.py: e3acbbd2… contra 9cea5a4d…).
- Escenario: la autora clona el repo en Windows, corre los tests tal como dice el README §3 y le fallan 2 sin
  haber tocado nada. El README le dice "después de tocar `src/`, regenerarlos", que es un mensaje engañoso.
- Por la misma razón `build_report.py`, corrido en el clon, reescribe los sha de `provenance.json` (mod-*) y de
  la tabla final del HTML.
- Los números no cambian. Regeneré `study_v2.json` en el clon y sale idéntico campo a campo (0 diferencias). Las
  6 figuras salen idénticas byte a byte. El HTML solo difiere en la marca de tiempo y en los sha.
- Arreglo sugerido: normalizar `\r\n` a `\n` antes de hashear (en `compare_legacy_vs_v2._sha`,
  `test_usability._sha`, el script del estudio y `build_report`), o agregar `*.py text eol=lf` en `.gitattributes`.

## 2. La autora usando el README al pie de la letra

Todo lo de esta sección se hizo en el clon, con un venv aparte para no tocar el Python del sistema.

| Paso del README | Resultado |
|---|---|
| §1 A: `pip install -e .` (con internet) | OK. Deja `src/pminflux_sim.egg-info/` sin trackear (no hay `.gitignore`). |
| §1 A sin internet (`--no-build-isolation`) con el entorno de la autora (setuptools 49.2.1, sin `wheel`) | Falla (`invalid command 'bdist_wheel'`). **El README lo avisa** y remite a la opción B. OK. |
| §1 B (`sys.path`) | OK (es lo que hacen scripts y tests). |
| §2 Inicio rápido, copiado literal y corrido **fuera** del repo | OK en 15.7 s. Sesgo de la mezcla (0.031, 0.043) nm; legado (0.79, −0.30); CRB 0.933; borde 0; n_failed 0. |
| §3 `scripts/example_end_to_end.py` | OK en 7.9 s (el README dice < 10 s). En (−15, 15): mezcla 0.065 / 0.980, legado 2.663 / 2.020 (coincide con W1). |
| §3 `scripts/study_misalignment_v2.py` | OK en 56.8 s (el README dice ~45 s). `results/study_v2.json` sale **idéntico** al commiteado. |
| §3 `make_report_figures.py` / `build_report.py` | OK en 7 s y 0.5 s. PNG idénticos y HTML reproducible (salvo marca de tiempo y sha, ver §1). |
| §3 Tests | Fallan 2 en un clon (ver §1). |
| `count_windows` con time tags | Da exactamente los `counts` del simulador desde `return_tags`. Probé también: bordes medio abiertos (`[0.0, 10.1, 12.5, 22.6]` da `[1,1,0,0]`), tiempos absolutos `macro·50 + micro` hasta 2^40 ns (igual que con el microtiempo), `macro_index` float entero, NaN (da error) y la comparación con el `nMINFLUX` legado (idéntico con a = 0; con a = −1 v2 recupera las 394 cuentas de w0 que el legado pierde, F103). |

**Traducción de `simulations_example.py` usando solo el README.** Parámetros del legado: dt = 25, K = 4,
Tlife = 0.001, Ns = 90, Nb = 10, L = 100, r0 = (5, −5), 100 muestras, a = 0, b = dt/K.
- Todo tiene equivalente y el script sale en unas 25 líneas.
- Emulando el legado con `SimParams(T=25, tau=0.001, irf_fwhm=0, dead_time=0, tcspc="highest", counting="legacy")`
  + `mle_legacy`, el error 2D es 4.23 nm. Con `mle_mixing` y la C correcta (`irf_fwhm=0`) da lo mismo.

Instrucciones ambiguas, o que me obligaron a leer el código:
1. **Emular `sim_exp`.** §4 dice que `tcspc="highest"` "emula `sim_exp`", pero no dice que además hay que poner
   `irf_fwhm=0` y `dead_time=0`. Los defaults (IRF 0.3, d = 22) no están en `sim_exp`.
   - Escenario: la traducción "literal" deja la IRF por defecto y usa b = T/K = 6.25 con τ = 0.001. La IRF
     centrada en el pulso manda el 49.7 % de cada haz a la ventana anterior. C queda casi singular (autovalor
     0.006) y ningún aviso lo señala.
   - Con esos datos, `mle_mixing` da 15.6 nm de error 2D, sesgo medio (6.3, 7.2) y 3 fallos; `mle_legacy` da
     30.7 nm, con el 92 % en el borde.
   - Si ella construye C con `irf_fwhm=0.3` sobre datos del legado, salen 73 de 100 sin converger.
   - Es física correcta, pero una trampa de migración que el README no marca.
2. **De `M_p`/`factor` a `rate_per_cycle`.** La tabla dice "fotones incidentes por ciclo", sin fórmula. La
   deduje: Ns·factor/M_p = 4.7e-4.
3. **`nMINFLUX(K, τ, ...)` recibe un array `τ` arbitrario de tiempos de pulso**; `count_windows` y `mixing_matrix`
   suponen pulsos en i·T/K exactos, con el pulso del haz 0 en microtiempo 0. El README no dice cómo llevar datos
   reales a esa convención (restar el offset del sync o del pulso 0) ni qué hacer si los retardos medidos no
   están equiespaciados. **Es el paso que la autora más necesita para sus datos TCSPC.**
4. **Qué `N` pasarle a `crb` con datos reales.** §5 dice "N del ciclo completo", pero no indica usar
   `return_outside=True` (N = counts.sum + outside) ni `n_is="windows"`.
5. **§4 dice "Todo lo anterior se puede importar directamente de `pminflux_sim`", y es falso** para
   `check_overlap`, `donut` y `gaussian`: `pm.donut` da AttributeError; hay que usar `pm.psf.donut` o
   `pm.windows.check_overlap`.
6. **`cov_ellipse` cambió el orden de los argumentos.** El legado es `(cov, q, nsig)` y v2 `(cov, nsig, q)`.
   Una llamada posicional `cov_ellipse(cov, q)` del legado mete `q` en `nsig`. La tabla muestra el orden nuevo,
   pero no lo advierte.
7. **`beams(K, L, center=False, d)`.** En el legado pone haz central (compara `center is not None`); en v2
   `center=False` lo quita. Los scripts de la autora usan `center=True`, así que no les afecta; el README no lo
   menciona.

## 3. Afirmaciones del README contra el código

- **Conventions N/SBR/β, ventanas medio abiertas mod T, C.** Las comprobé: `C[i,i] = 0.8973` y
  `C[i+1,i] = 0.0467` con IRF 0.3 (sin IRF: 0.9092, 0.0467, 4.16 % fuera).
- **dead_time 22 ns y IRF 0.3 FWHM centrada.** Son los defaults de `SimParams`; `DEAD_TIME_ASSUMPTION` está
  exportado y el README los marca como no medidos. OK.
- **d = n·T.** Está verificado en R2 (state.json) y el README lo cita bien. La frase "con d ≥ T en un intervalo
  de largo d cabe a lo sumo una avalancha" vale en realidad para cualquier d (tiempo muerto no paralizable,
  avalanchas *registradas*). Es inofensivo.
- **Limitaciones.** El texto corregido del sesgo residual (0.02–0.035 nm + O(1/N) ~0.036 nm, ≤ 0.03 CRB) coincide
  con la corrección del verificador R2.
- **Una contradicción real: t_mask contra la convención de SBR (defecto de semántica/documentación del port de
  F107).**
  - §5 dice "SBR = Ns/Nb del ciclo completo". Con `t_mask`, el docstring (no el README) dice que `sbr` y
    `rate_per_cycle` se refieren a los ciclos *encendidos*.
  - Escenario: `t_mask` al 50 % (500 ciclos encendidos y 500 apagados), sbr = 21, N = 2095, 400 locs en (−15, 15).
    La fracción de fondo detectada es 0.0869, o sea un **SBR efectivo de 10.5**.
  - `mle_mixing(..., sbr=21)` da un sesgo de (−0.26, −0.36) nm, **5–7 SE** (≈0.48 CRB por localización). Con el
    SBR efectivo, o con `free_bg="shared"`, el sesgo es 0.02–0.03.
  - En el legado la rama cw renormalizaba la señal sobre los ciclos encendidos y Ns y Nb quedaban fijos, así que
    el SBR no cambiaba.
  - La semántica de v2 es defendible (el fondo sigue en los ciclos apagados), pero el README §4/§5 tiene que
    decirlo.
- **§10 study_v2.** Los números del README coinciden con `study_v2.json`, que reproduje idéntico. Su
  verificación independiente todavía está pendiente y el README lo dice.

## 4. Revisión del código nuevo

- **windows.py.** La aritmética de `window_masks` es correcta: para el tramo que cruza T, la condición
  `d < b − T` equivale a fase < i·dt + b − T. `count_windows` valida K, T, b, a, finitud, largo, signo y
  enteridad de `macro_index`, y n_loc.
  - Único borde encontrado, de punto flotante e irrelevante en la práctica: con b = T/K exacto, un microtiempo a
    1 ulp por debajo de `a` (p. ej. `nextafter(0.5, 0)` con a = 0.5, o −1e-17 con a = 0) pliega a fase == T y no
    cae en ninguna ventana (debería ir a la ventana K−1).
  - `n_loc` se ignora en silencio sin `macro_index`.
  - Tests: igualdad exacta con el simulador, cruce de T, a < 0 y χ² p = 0.184 contra `window_probs`. Pasan.
- **Guard de solapamiento.** `simulate_counts`, `crb`, `mle_mixing` y `count_windows` levantan ValueError con
  b = 20 (T = 50, K = 4); con `allow_overlap=True` emiten exactamente 1 UserWarning. b = T/K (también 50/3 con K = 3)
  no da error. **Resuelve el refuted R2 (claims[56]).** El `stacklevel=3` apunta a la línea del usuario desde
  `count_windows`; desde `simulate_counts` apunta a `simulate_counts`, lo cual es cosmético.
- **F107 en `simulate`.** El adelgazamiento de señal en los ciclos apagados es correcto y no toca el RNG: con la
  máscara toda en 1 el resultado es bit a bit el mismo, y hay test. Los fotones fantasma (inf) se manejan con
  `errstate`. Con todo apagado y sbr = inf da ValueError; con fondo simula solo fondo. La diferencia de semántica
  de sbr está descrita en §3.
- **MLE por bloques.** Es un bucle de `argmax` sobre bloques de filas, trivialmente idéntico; el test lo confirma
  bit a bit con chunk 7/1/9 en fijo, free_bg, legacy y free_powers. **Resuelve la parte de memoria del unclear R2
  (claims[57]).** El O(n²) del tiempo muerto queda documentado como limitación.
- **Flag converged.** Con `maxiter` agotado, se marca converged si la NLL bajó ≤ 1e-6 (absoluto) contra la de
  hace 10 iteraciones; con `maxiter < 10` se compara con el arranque.
  - La lógica es correcta y las estimaciones no cambian. El test acota el hueco de NLL a ≤ 1e-5 y la distancia a
    < 0.05 nm respecto de un reajuste largo.
  - Un umbral absoluto se vuelve relativamente más laxo a N baja; a N alta la curvatura lo compensa. Es aceptable.
  - Resuelve el unclear R2 (claims[60]), junto con el docstring 1.000–1.038x.
- **build_report.py.** Los números vienen de los JSON: los 120 valores |b| y RMSE/CRB de
  `compare_legacy_vs_v2.json` aparecen en el HTML y el p = 0.129 de la mezcla también. `check_provenance` da 93
  tags, 93 entradas y 0 errores.
  - Números tipeados a mano: solo los recuadros de "corrección del verificador" (6.84/2.54, 0.88/1.18, 0.945,
    2.73–2.75, 0.912/0.960/0.4455), que coinciden con `findings.json`; "τ = 4.21" en el texto; y "≤ 0.05 SE" en
    §9 (sin tag propio).
  - La procedencia apunta a `state.json claims[i]` por posición. Funciona mientras la cosecha solo agregue al
    final.
  - Autocontenido: 0 `http(s)://`, 0 `<link>`/`@import`/`url()`, 6 imágenes `data:` y un solo `<script>` inline
    de 5 líneas (`setAll`, `toggleTheme` con `matchMedia` y `beforeprint`), que funciona offline. No hay node
    para un chequeo sintáctico automático; lo revisé a mano.
- **make_report_figures.py.** Es determinista (PNG idénticos al regenerar). Una inconsistencia menor en el
  caption de `timeline_20MHz.png`: dice "τ = 4.21 con IRF gaussiana de 0.3 ns (recuadro) … C[i][i] = 0.9092", pero
  0.9092 es la C **sin** IRF (con IRF es 0.8973). Al final lo aclara ("C sin IRF"). El HTML §3 sí distingue bien
  los dos valores.

## 5. Privacidad (si se compartiera el HTML)

El HTML no contiene nombre de usuario de Windows, email, `C:\Users\…` ni `Cibion`. Sí contiene:
- una ruta local, `C:\Data\psf\20260820`, y el fragmento de carpeta `GithubPRO/p-minflux-main`;
- nombres de terceros (Luciano Masullo, Lucía López y Lars Richter, autores del código original) y 49
  menciones a "la autora";
- **datos experimentales no publicados**:
  - τ = 4.21 ns y la ventana [0, 10.1] ns de 20260707;
  - las fechas de calibración 20260703/0707/0820/0924 y los máximos de PSF (245/205/291/253, 6.4/4.8/6.8/5.3 y
    21.2/18.4/26.6/19.7);
  - los centros y potencias del ajuste realista (21.02/16.65/22.96/22.86);
  - los números "Experimental" de su documento (18.35/62.76/1.89);
- referencias a sus archivos internos: el .docx (4 veces), NOTAS.txt (22), run_final.log (4) y 42 citas
  `archivo.py:línea` con fragmentos de su código;
- el sha256 de cada archivo leído.

No se puede compartir fuera del grupo sin su consentimiento. Si alguna vez se comparte, hay que quitar la ruta
`C:\Data\…`.

## 6. Contra el intent (R3)

Existen `report/index.html` (la aceptación pasa en el árbol original), `README.md`, la tabla de migración, el
ejemplo de punta a punta, el estudio v2, la función pública `count_windows`, `__init__` completo, el empaquetado y
el port de F107.

Lo que falta: que los tests y los sha sean robustos a los finales de línea (§1), y cómo llevar microtiempos
reales con offset o retardos no equiespaciados a la convención de v2 (§2.3).

```claims
[{"status": "verified", "text": "Suite completa en el árbol de trabajo original (python -m unittest discover -s tests, Py 3.8.6): Ran 64 tests in 118.4 s, OK"},
 {"status": "refuted", "text": "Reproducibilidad de los tests con sha256: en un git clone nuevo con core.autocrlf=true (default Windows) fallan test_compare_json_complete y test_study_v2_json (64 tests, 2 failures) porque _sha hashea bytes crudos y los .py salen CRLF (mixing.py e3acbbd2 -> 9cea5a4d); los números no cambian (study_v2.json regenerado idéntico, PNG idénticos); build_report reescribe los sha de provenance/HTML. Arreglo: normalizar CRLF->LF antes de hashear o .gitattributes *.py eol=lf"},
 {"status": "verified", "text": "Guard b>T/K: simulate_counts, crb, mle_mixing y count_windows levantan ValueError con b=20,T=50,K=4; allow_overlap=True emite exactamente 1 UserWarning; b=T/K (y 50/3 con K=3) no levanta; resuelve el refuted R2 (claims[56])"},
 {"status": "verified", "text": "count_windows: semántica medio abierta [i·T/K+a, +b) mod T correcta (bordes [0,10.1,12.5,22.6]->[1,1,0,0]; cruce de T; a<0; tiempos absolutos macro·50+micro hasta 2^40 ns idénticos); igual a nMINFLUX con a=0 y recupera las cuentas de w0 que el legado pierde con a=-1 (F103); iguala exactamente los counts del simulador desde return_tags; validaciones de macro_index/NaN funcionan"},
 {"status": "unclear", "text": "count_windows borde de punto flotante: con b=T/K exacto, un microtiempo 1 ulp por debajo de a (nextafter(0.5,0) con a=0.5, o -1e-17 con a=0) se pliega a fase==T y no cae en ninguna ventana (debería ir a K-1); irrelevante con datos reales, sin test"},
 {"status": "verified", "text": "Arranque en grilla del MLE por bloques (chunk): bucle argmax por bloques trivialmente idéntico; el test lo confirma bit a bit en fijo/free_bg/legacy/free_powers"},
 {"status": "verified", "text": "Flag converged: si se agota maxiter con dNLL<=1e-6 en 10 iteraciones se marca True; la lógica es correcta, las estimaciones no cambian y el test acota el hueco de NLL a <=1e-5 y la distancia a <0.05 nm; docstring free_bg 1.000-1.038x corregido; resuelve U R2 claims[60]"},
 {"status": "refuted", "text": "Port de F107 (t_mask) contra la convención de SBR del README §5 (Ns/Nb del ciclo completo): con t_mask 50% encendido y sbr=21 el SBR detectado es 10.5 (fondo 0.0869) y mle_mixing(sbr=21) sesga (-0.26,-0.36) nm = 5-7 SE (~0.48 CRB por loc); en el legado Ns/Nb quedaban fijos. La semántica 'sbr de los ciclos encendidos' está solo en el docstring y hay que documentarla en README §4/§5"},
 {"status": "verified", "text": "README al pie de la letra en un clon + venv: pip install -e . (con internet) OK; el fallo offline con setuptools 49 sin wheel está advertido; inicio rápido §2 corre fuera del repo (15.7 s, sesgo de la mezcla 0.03/0.04 nm, CRB 0.933); example_end_to_end 7.9 s; study_misalignment_v2 56.8 s y study_v2.json idéntico al commiteado; figuras idénticas"},
 {"status": "unclear", "text": "README como guía de migración: (1) no dice que para emular sim_exp hay que poner irf_fwhm=0 y dead_time=0 además de tcspc='highest'; con la IRF por defecto, tau=0.001 y b=T/K, C manda el 49.7% a la ventana anterior (autovalor 0.006): mle_mixing da 15.6 nm y mle_legacy 30.7 nm con 92% en el borde, sin aviso; (2) no da la fórmula de M_p/factor a rate_per_cycle; (3) no explica cómo llevar microtiempos reales (offset del sync o del pulso 0, retardos τ no equiespaciados, que nMINFLUX sí aceptaba) a la convención i·T/K; (4) no aclara qué N pasarle a crb con datos reales (return_outside); (5) dice que check_overlap, donut y gaussian se importan desde pminflux_sim y es falso (AttributeError); (6) el orden de argumentos de cov_ellipse cambió (q y nsig) sin advertencia"},
 {"status": "verified", "text": "Afirmaciones del README contra el código: C[i,i]=0.8973 y C[i+1,i]=0.0467 (IRF 0.3); defaults dead_time=22 e IRF 0.3 centrada marcados como supuestos; d=n·T citado como verificado en R2; texto corregido del sesgo residual; tabla study_v2 igual al JSON"},
 {"status": "verified", "text": "build_report.py: números leídos de los JSON (120/120 valores |b| y RMSE/CRB de compare en el HTML, p=0.129); check_provenance 93/93/0 errores; HTML autocontenido (0 http, 0 link/@import/url(), 6 imágenes data:, un solo script inline de 5 líneas que funciona offline); reproducible salvo marca de tiempo y sha. Tipeados a mano solo los recuadros de corrección del verificador (coinciden con findings.json) y '≤0.05 SE' en §9"},
 {"status": "unclear", "text": "Caption de timeline_20MHz.png (make_report_figures.py): dice 'IRF gaussiana 0.3 ns … C[i][i]=0.9092', pero 0.9092 es C sin IRF (con IRF 0.3 es 0.8973); lo aclara solo al final; la sección 3 del HTML sí distingue ambos"},
 {"status": "verified", "text": "Privacidad del HTML: no contiene usuario de Windows, email ni C:\\Users; sí contiene la ruta C:\\Data\\psf\\20260820, 'GithubPRO/p-minflux-main', nombres de Masullo/López/Richter y datos no publicados de la autora (τ=4.21 y [0,10.1] de 20260707, máximos de PSF de 20260703/0707/0924, potencias 21.02/16.65/22.96/22.86, números Experimental 18.35/62.76/1.89, referencias al .docx, NOTAS.txt, run_final.log y 42 citas archivo.py:línea): no compartir sin su consentimiento"}]
```
