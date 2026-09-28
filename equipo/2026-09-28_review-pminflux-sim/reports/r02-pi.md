# r02 — PI: plan de la ronda 2 (de 3)

## Estado leído
- `state.json`: 49 afirmaciones de R1, 41 `verified`, 5 `refuted` y 3 `unclear`. Checks en verde (test_mixing 18 OK y los
  tests de mixing de aceptación). Todavía no hay aceptación completa: faltan `results/findings.json` y `report/index.html`.
- `inbox.jsonl`, ronda 2 (PRIORIDAD MÁXIMA):
  - F201 y F202 pasan a **DISENO**. F104 queda **CONCEPTUAL**.
  - El reporte tiene que explicar el **"crimen inverso"**: simular con el mismo modelo directo que usa el estimador, sin fuga
    ni ventanas reales, deja a las simulaciones ciegas al desajuste de modelo. Es lo que une F104 con F201.
  - Se aplican **todas** las correcciones de los verificadores, en forma literal.
  - La autoría queda "no verificable sin historial git", salvo lo que sostiene el verificador A.
- `mixing.py`, verificado en R1. API congelada, que nadie edita en esta ronda: `mixing_matrix(tau,T,K,a,b,irf_fwhm)`,
  `window_expected`, `window_probs(lam,C,b,T,Ns=,Nb=|sbr=)`, `naive_probs(lam,sbr)`, `pearson_chi2`,
  `occupancy_pattern_probs`, `pattern_window_dist(...,rule)` y `sim_exp_window_probs(...,rule='highest'|'earliest'|'ideal')`.
- `test_acceptance.py` exige que **toda** entrada de `findings.json` tenga `status == "verified"`, una clase ∈
  {CONCEPTUAL, IMPLEMENTACION, DISENO} y un `script` que exista. Todo lo demás va a `findings_discarded.json`.

## Cómo resuelvo las afirmaciones vivas (refuted/unclear)
| afirmación | resolución en R2 |
|---|---|
| MIX-NDETECT (refuted) | W1 escribe el texto corregido en `results/mixing_claims.json`: a 5e-3/ciclo bastan ~1e7 fotones y el 3e7 corresponde a 3e-3. |
| F103-num (refuted) | W1 pone 6.84 % / 2.54 % (valores esperados). Los 0.34 nm pasan a ser un "desplazamiento", con el total 0.88 (legado) contra 1.18 nm (periódico) cuando τ = 4.21, y 0.063 nm que sí suman cuando τ = 0.001. |
| F111-comentarios (refuted) | W1 quita de F111 la afirmación de "paridad invertida". Queda solo el IndexError con K = 5 y K = 7. |
| F201 clase (unclear) | Pasa a DISENO (inbox). Además: cociente ≈2.5 contra el CRB con fuga (0.945 nm), 2.75 contra el CRB sin fuga (0.864), y crédito a ESTADO…md:115-117. |
| F202 clase (refuted) | Pasa a DISENO. Se escribe explícito el supuesto "máximo del .npy = potencia del haz" (el orden se repite en 3 calibraciones) y se da crédito a ESTADO…md:116. |
| F203 (refuted) | "100 % en el borde" pasa a valer solo para R ≤ 1.0·L (con 1.25·L es el 71–72 %). Con R = 0.75 y el EBP realista, el ingenuo tiene un 1 % en el borde. |
| F154 (unclear) | Va a `findings_discarded.json` con `status: "unclear"`. Queda como evidencia el ValueError; el 88.5 % y el p = 0.74 no se reprodujeron. |
| AUTORÍA (unclear) | Se resuelve con el default de abajo. Nadie lo declara verificado. |

## Defaults que decido (bifurcaciones chicas, declaradas)
- **Autoría** (campo `author` ∈ {"Masullo-original", "autora", "no verificable"}, más `author_basis` en texto):
  - Hallazgos en `tools_simulations.py`: "no verificable".
  - Excepciones: F111 es "Masullo-original", por el docstring [Lars] de `ebp_centres`. Si las líneas de un hallazgo caen
    dentro del bloque con el comentario "EXACTAMENTE" o del fast path en español, va "autora" con
    `author_basis: "indicio: comentario en español; sin git"`. Eso lo comprueba W1 leyendo el legado.
  - Hallazgos en archivos que el OBJECTIVE atribuye enteros a la autora (ebp.py, realistic_ebp.py,
    simulation_misalignment.py, analyze_realistic_psf.py, documento/): "autora", con `author_basis: "declaración del
    OBJECTIVE; sin git"`.
  - Si el defecto viene de Masullo, se dice en `author_basis`. Ejemplo: en F201, Tlife = 0.001 ya está en
    simulations_example.py:51 (Masullo).
- **Convención de N** (la misma que F104/F201): Ns = 2000 fotones de señal, Nb = Ns/SBR (95 con SBR 21, 333 con SBR 6).
  `N = Ns + Nb` son los detectados en el ciclo completo, antes de aplicar las ventanas.
- **Tasa y tiempo muerto por defecto**: 2.5e-3 fotones/ciclo (50 kHz a 20 MHz, en el rango del tracking de 20–110 kHz).
  Tiempo muerto de 22 ns: es un valor típico de SPAD y es un **supuesto declarado**. Se barre en {0, 22, 50, 100} ns.
- **IRF**: gaussiana de 300 ps FWHM centrada en el pulso (supuesto verificado en MIX-IRF).
  - El estudio comparativo corre primero con `irf_fwhm = 0`, para contrastarlo con los números verificados de F104.
  - Después corre la variante con 0.3 ns.
- **CRB por eje**: σ_CRB = sqrt(½·tr F⁻¹), la misma definición que F104 y crb_minflux. RMSE_2D = sqrt(mean|r̂ − r|²),
  con RMSE/CRB = RMSE_2D/(√2·σ_CRB). Se informan los dos.
- **Geometría**: TCP K = 4, L = 100 nm, center = True, dona con fwhm 360 nm (default del legado, como en F104).
  - Posiciones de F104: (5, −5), (−5.07, −7.56), (20, 0), (−15, 15) y (0, −30) nm.
- `src/pminflux_sim/__init__.py` y `mixing.py` no se tocan. Los submódulos se importan como `from pminflux_sim import simulate`.

## Interfaz acordada simulate ↔ estimate (congelada; W2 la implementa y W3 programa contra ella)
```python
# src/pminflux_sim/simulate.py  (W2)
@dataclass
class SimParams:
    T: float = 50.0; K: int = 4
    tau: float = 4.21
    irf_fwhm: float = 0.3          # ns; 0/None = sin IRF
    a: float = 0.0; b: float = 10.1   # ventana i = [i*T/K + a, i*T/K + a + b] mod T  (a<0 y cruce de T permitidos)
    rate_per_cycle: float = 2.5e-3 # fotones incidentes (señal+fondo) por ciclo, antes de TCSPC/tiempo muerto
    dead_time: float = 22.0        # ns; abarca ciclos; 0 = solo "1 fotón por ciclo"
    tcspc: str = "earliest"        # "earliest" (TCSPC real) | "highest" (emula sim_exp, F101) | "none" (todos los fotones)
    counting: str = "periodic"     # "periodic" | "legacy" (nMINFLUX: '>' estricto, sin pliegue, ceros de ciclos vacíos -> F102/F103)
    n_mode: str = "fixed"          # "fixed" (exactamente N detectados) | "poisson" (N ~ Poisson(N))
    beam_powers: Optional[Sequence[float]] = None   # multiplica lambda (F202); None = iguales

def simulate_counts(lambda_beams, n_loc, N, sbr, params=None, rng=None, return_tags=False):
    """lambda_beams: (K,) o (n_loc, K), excitación relativa (se normaliza por localización después de beam_powers).
    N: fotones detectados por localización (señal+fondo, ciclo completo, después de TCSPC); la media si n_mode='poisson'.
    sbr: Ns/Nb en el ciclo completo (inf = sin fondo). rng: np.random.Generator (obligatorio para reproducir).
    Devuelve counts (n_loc, K) int64 = conteos por ventana. Con return_tags=True devuelve (counts, tags);
    tags = dict de arrays planos: loc, cycle, microtime_ns en [0, T), source (índice de haz, o -1 para el fondo)."""
```
- W3 **no** importa `simulate` en los tests unitarios. Sus tests usan multinomiales sacadas de `mixing`.
- El script comparativo hace `--source v2sim` (default). Si `simulate` no importa, cae a
  `--source multinomial`: multinomial sobre las K ventanas más una categoría "fuera", con probabilidades de
  `mixing.window_expected`. El JSON registra qué fuente se usó. La corrida final **tiene** que ser con `v2sim`: la lanza el
  orquestador una vez que W2 termina, si W3 no pudo.

## Ids de test fijados (W1 los enlaza sin esperar a W2/W3; W2 y W3 tienen que usar exactamente estos nombres)
`tests/test_simulate.py` (W2):
- `TestSimulateMixing::test_low_rate_matches_mixing_window_probs` → F104 (el modelo directo correcto), MIX-VALID
- `TestSimulateMixing::test_irf_negative_start_and_wrap` → corrección de F102/F103 (ventanas periódicas, a < 0, cruce de T)
- `TestSimulateLegacy::test_highest_overwrite_emulation` → F101, antes
- `TestSimulateTCSPC::test_earliest_matches_mixing_predictor` → F101, después
- `TestSimulateLegacy::test_legacy_counting_zeros_in_window0` → F102, antes y después
- `TestSimulateLegacy::test_legacy_counting_non_periodic` → F103, antes y después
- `TestSimulateLegacy::test_short_lifetime_turns_off_leakage` → F201 (τ = 0.001 y b = 12.5 ⇒ C ≈ I; con τ = 4.21 aparece la fuga)
- `TestSimulateTCSPC::test_dead_time_spanning_cycles`
- `TestSimulateBackground::test_background_uniform_b_over_T`
- `TestSimulateN::test_fixed_and_poisson_N`
- `TestSimulateSpeed::test_throughput`

`tests/test_estimate.py` (W3):
- `TestPSF::test_matches_legacy_beams_and_doughnut`
- `TestPSF::test_fwhm_honored_and_any_K` → F109, F111
- `TestEstimate::test_legacy_mle_bias_matches_F104` → F104, antes
- `TestEstimate::test_mixing_mle_unbiased_at_measured_setup` → F104, después
- `TestEstimate::test_continuous_offgrid_no_quantization` → F106, F205
- `TestEstimate::test_sbr_inf` → F110
- `TestEstimate::test_crb_mixing_and_naive_limit`
- `TestEstimate::test_free_powers_removes_bias` → F202
- `TestEstimate::test_free_background`
- `TestEstimate::test_boundary_fraction_reported` → F203
- `TestEstimate::test_cov_ellipse_orientation` → F108
- `TestCompare::test_compare_json_complete` → F204 (SE bootstrap), F206 (todos los parámetros quedan registrados en el JSON)

Sin test en v2 (`v2_test: null`, con `v2_fix_status` en texto): F107 (t_mask/blinking, no portado; va al backlog).

## Propiedad de archivos (disjunta)
- **W1**: `results/findings.json`, `results/findings_discarded.json`, `results/mixing_claims.json`, `scripts/build_findings.py`.
  Solo lee `findings_A/B.json` y `state.json`, sin editarlos.
- **W2**: `src/pminflux_sim/simulate.py`, `tests/test_simulate.py`, `scripts/sweep_dead_time.py` y `results/dead_time_sweep.json`.
- **W3**: `src/pminflux_sim/psf.py`, `src/pminflux_sim/estimate.py`, `tests/test_estimate.py`,
  `scripts/compare_legacy_vs_v2.py` y `results/compare_legacy_vs_v2.json`.
- Nadie toca `legacy/`, `tests/test_acceptance.py`, `mixing.py`, `__init__.py` ni `test_mixing.py`.

## Tareas de la ronda 2

1. **Worker 1 — registro de hallazgos fusionado y corregido.**
   - Escribí `scripts/build_findings.py` (determinista y reejecutable). Lee `results/findings_A.json` y `findings_B.json` y
     escribe `results/findings.json`: una lista con los 16 hallazgos verificados F101, F102, F103, F104, F106, F107, F108,
     F109, F110, F111, F201, F202, F203, F204, F205 y F206.
   - **Campos de cada entrada:**
     - Los que pide la aceptación: `id`, `title`, `class`, `legacy_location`, `scenario`, `impact`, `fix`, `script`, y
       `status: "verified"`.
     - `author`, con los valores y el default de arriba, y `author_basis`.
     - `what_was_right`.
     - `verified_by`: "verifier-A r01" o "verifier-B r01", más el texto de la afirmación verificada en `state.json`.
     - `corrections_applied`: una lista de {`from`, `to`, `source`}, citando el verificador o el inbox.
     - `v2_test` (el id de la lista fijada, o null), `v2_fix_status` y `crimen_inverso`: bool, true para F104 y F201.
   - **Correcciones que se aplican en forma literal:**
     - F103: 6.84 % / 2.54 %. Los 0.338 nm son un desplazamiento: 0.88 nm con las ventanas del legado contra 1.18 nm con
       ventanas periódicas cuando τ = 4.21.
     - F111: se quitan los comentarios de paridad.
     - F201: DISENO. Cociente ≈2.5 contra el CRB con fuga (0.945 nm) y 2.75 contra el CRB sin fuga. Crédito a
       ESTADO…md:115-117. Se cambia "sin declararlo" por "no declarado en el .docx ni en los scripts".
     - F202: DISENO. El supuesto de potencias queda en `scenario`/`impact`. Crédito a ESTADO…md:116.
     - F203: "100 % en el borde solo para R ≤ 1.0·L (71–72 % con 1.25·L)", más la nota del 1 % con R = 0.75 y el EBP realista.
     - F204: el "±0.13–0.15" queda rotulado como extrapolación desde sustitutos.
     - F205: impacto extra, RMSE de 0.912 → 0.960 nm (analyze_realistic_psf.py:88).
     - F206: la quinta discrepancia ("Experimental ingenua 1/2").
     - F104: los matices del verificador A (domina la fuga; ~2.5 puntos del CRB vienen de los fotones fuera de las
       ventanas; no cambia números publicados porque Tlife = 0.001; 0.92–2.45 veces el CRB real).
     - F101: 0.379 % y 0.461 % a 0.0105/ciclo. Latente a las tasas del tracking (≤0.05 SE).
     - Los números citados salen del texto verificado en `state.json`, no del borrador del worker.
   - **`results/findings_discarded.json`:**
     - F105, F151, F152, F153, D-iv, D-ii, D-vi y F290-D1…D8, con su evidencia y `status: "discarded-verified"`.
     - Correcciones: el margen de D1 es 3/55/76/105 (no "≥77"). En D4 se quita la atribución del +2.6σ a F101.
     - F154 va con `status: "unclear"` y lo que falta.
     - F152 lleva la nota "cota ≤3.6e-4 no verificada".
   - **`results/mixing_claims.json`:** las afirmaciones MIX-* verificadas con su texto, más MIX-NDETECT corregida. Es la fuente
     del reporte R3.
   - **Test de salida:** corré `python -m unittest tests.test_acceptance.Acceptance.test_findings_registry_is_complete_and_verified`
     (tiene que pasar) y `python -m unittest discover -s tests`. El HTML todavía no existe: ese test falla y es esperable.
   - **Afirmaciones que se exigen:**
     - cuántas entradas quedan en cada archivo;
     - que ninguna entrada verificada contradice su texto en `state.json`, con la lista de diferencias numéricas si hay alguna;
     - un diff por hallazgo de las correcciones aplicadas.

2. **Worker 2 — simulador en dominio temporal `src/pminflux_sim/simulate.py` + `tests/test_simulate.py`, con la interfaz exacta de arriba.**
   - **Física:**
     - K haces intercalados, con el pulso j en j·T/K.
     - Microtiempo = pulso + IRF gaussiana + Exp(τ), con el tiempo absoluto = ciclo·T + microtiempo, de modo que la fuga cae
       en el ciclo siguiente.
     - Fondo uniforme en el ciclo. Compite en el TCSPC igual que la señal.
     - Llegadas Poisson a `rate_per_cycle`, repartidas según λ·potencias (señal) y SBR (fondo).
     - TCSPC: el primer fotón por ciclo (`earliest`), más un tiempo muerto que abarca ciclos, sobre el tiempo absoluto.
     - `highest` reproduce la sobrescritura de sim_exp (F101).
     - Conteo `periodic` sobre ventanas plegadas módulo T. `legacy` emula nMINFLUX: '>' estricto, sin pliegue, y los
       ciclos vacíos cuentan como microtiempo 0.0 (F102/F103).
     - N `fixed` (exactamente N detectados) o `poisson`.
   - **Rendimiento:** solo se generan los ciclos ocupados (la tasa es baja) y se procesa en bloques. Si hay tiempo muerto, se
     resuelve con pasadas vectorizadas más un bucle solo sobre los conflictos. Meta: ≥1e5 localizaciones × 2000 fotones en
     minutos. Medí el tiempo real e informalo; `test_throughput` usa un tamaño chico y extrapola.
   - **Tests** (los nombres fijados, semillas fijas, cada uno < ~60 s):
     - A tasa baja (1e-3) con `tcspc='none'` o `'earliest'`, los conteos agregados (≥1e6 en ventanas) contra
       `mixing.window_probs`, con y sin IRF, a < 0 y cruce de T: p > 1e-3. El modelo ingenuo se rechaza.
     - `highest` contra `mixing.sim_exp_window_probs(rule='highest')`, y `earliest` con dead_time = 0 contra
       `rule='earliest'`, a tasas de 0.1–0.3. Para Poisson se usan Nh = tasa·M_p con M_p grande.
     - `legacy` reproduce F102: con a = −0.25, la ventana 0 se infla con los ceros. En `periodic` no pasa.
     - `legacy` reproduce F103: con b = 13 cuenta dos veces. Las fracciones esperadas están en los hallazgos verificados.
     - τ = 0.001 y b = 12.5 dan conteos ∝ λ (F201).
     - Con tiempo muerto > T la tasa detectada baja según lo esperado.
     - El fondo cae b/T por ventana.
     - Las varianzas de `fixed` y `poisson` son las correctas.
   - **`scripts/sweep_dead_time.py`** → `results/dead_time_sweep.json`:
     - Sesgo por ventana contra la mezcla ideal para dead_time ∈ {0, 22, 50, 100} ns y tasas {1e-3, 2.5e-3, 5.5e-3, 0.0105}.
     - Tomar λ de la posición (5, −5) de F104, en SE por localización de 2000 fotones. Es el "antes/después" frente a sim_exp.
   - **Afirmaciones que se exigen:** p-valores de cada test de acuerdo con su número de fotones, rendimiento medido
     (fotones/s y tiempo extrapolado para 1e5×2000), la tabla del barrido y las limitaciones.

3. **Worker 3 — estimación `src/pminflux_sim/psf.py` + `estimate.py` + `tests/test_estimate.py` + `scripts/compare_legacy_vs_v2.py`.**
   - **`psf.py`:** `beam_positions(K, L, center=True)` para K arbitrario (corrige F111) y `donut(r, fwhm)` que respeta la fwhm
     (F109). `lambda_beams(r_xy, pos, fwhm)` es vectorizada sobre muchas r. Test: coincide con `ts.beams` y `ts.doughnut` del
     legado con K = 4, L = 100 y fwhm 360.
   - **`estimate.py`:**
     - `forward_probs(r, pos, fwhm, C, b, T, sbr, powers=None, bg=None)`: p' = C·λ(r)/Σ + fondo·b/T, normalizado en las
       ventanas. Tiene que ser consistente con `mixing.window_probs`, que se reusa.
     - `mle_mixing(counts, ..., bounds_radius, free_bg=False, free_powers=False)` y `mle_legacy(counts, ..., sbr)` (Ec. 3.5
       continua, con `mixing.naive_probs`).
     - La optimización es continua y acotada a un disco, y está vectorizada sobre localizaciones (p. ej. un arranque en una
       grilla gruesa más Newton o Gauss-Newton en lote). Devuelve la estimación, la bandera de "en el borde" y la
       convergencia.
     - `crb(r, ..., N, free_bg=False, free_powers=False)`: Fisher multinomial del modelo con los parámetros de estorbo
       marginalizados. Con C = I, b = T/K y sbr = inf coincide con el CRB ingenuo.
     - `cov_ellipse(cov)` corregido (F108).
     - `sbr = inf` sin NaN (F110).
   - **Tests** (los nombres fijados): datos multinomiales sacados de `mixing`, sin importar `simulate`.
     - El sesgo asintótico del legado en el setup medido sin IRF reproduce F104: 0.85/1.51/1.63/2.69/2.36 nm con SBR 21,
       con tolerancia de 0.05 nm.
     - El estimador de mezcla tiene sesgo < 2 SE y RMSE/CRB ∈ [0.9, 1.15] con N = 2095.
     - Una emisora fuera de la grilla no se cuantiza (F106/F205).
     - Con las potencias [21.02, 16.65, 22.96, 22.86], el estimador sin potencias libres se sesga y con `free_powers` no (F202).
     - La fracción en el borde se informa (F203).
   - **`scripts/compare_legacy_vs_v2.py`** → `results/compare_legacy_vs_v2.json`:
     - Datos del simulador v2 (τ = 4.21, [0, 10.1], tasa 2.5e-3, dead_time 22, earliest), Ns = 2000, SBR 21 y 6, las 5
       posiciones de F104, n_loc = 2000 por caso y semilla fija.
     - Bloque principal con irf 0 y variante con irf 0.3.
     - Estimadores: legado (Ec. 3.5) contra el de mezcla (C conocida). Opcional: fondo libre.
     - Por caso: sesgo vectorial y |b|, σx y σy, RMSE_2D, CRB (mezcla), RMSE/CRB, SE bootstrap de cada métrica, fracción en el
       borde y fallas.
     - Todos los parámetros, semillas, versión y `source` quedan registrados (F206).
     - Chequeo cruzado en 200 localizaciones: `ts.pos_MINFLUX` (px = 1) contra `mle_legacy`, que tienen que coincidir dentro
       de la cuantización.
     - Si `simulate` todavía no existe, se corre con `--source multinomial` y se deja dicho. El orquestador lo re-corre con
       `v2sim`.
   - **Afirmaciones que se exigen:** la tabla legado contra v2 por posición y SBR (con el número de fotones y los SE), la
     coincidencia del legado con F104 y el tiempo de corrida.

## Verificación de la ronda (para el orquestador)
- **Verificador A:** W2. MC propio contra `mixing` y una emulación propia de sim_exp. Rompé el tiempo muerto y el cruce de T.
- **Verificador B:** W3. Fisher y MLE propios, más reproducir 2 casos del JSON comparativo con otra semilla.
- **Code-reviewer:** `simulate.py` y `estimate.py` contra la interfaz fijada.
- **W1:** un verificador compara `findings.json` contra `state.json` y el inbox, entrada por entrada.

## Backlog
- **R3:**
  - `report/index.html` autocontenido (figuras en base64, sin `src="http`), en español. Contenido: criterio de clases,
    hallazgos por clase con todos los ids, sección "crimen inverso" (F104 + F201), autoría y lo que estaba bien, qué hacer
    distinto, validación de C, el antes/después del simulador (dead_time_sweep, emulaciones) y la tabla legado contra v2.
    Procedencia `[src:clave]` → `out/provenance.json`.
  - `README.md`: cómo correr todo.
  - Comprobar que cada `v2_test` de `findings.json` resuelve a un test existente que pasa.
  - Aceptación completa y `discover` en verde.
- **R3 opcional:** repetir el estudio de desalineación de la autora (F201 en el ideal y el realista honesto) con simulate + mle_mixing.
- **Sin asignar:** F107 (t_mask/blinking en p_minflux) no está portado a v2.

LO QUE MÁS SE PODRÍA HACER
1. MLE con microtiempos (verosimilitud temporal completa) frente al de ventanas con mezcla. Importa porque recupera la
   información de los fotones que caen fuera de las ventanas (~2.5 puntos del CRB). Costo: medio, 1 worker y 1 ronda.
2. Estudio de desalineación de la autora re-corrido con v2 (fuga, IRF, tiempo muerto) y con el estimador de mezcla. Importa
   porque traduce F201 a sus propias figuras. Costo: medio, con el simulador ya hecho.
3. Corregir la fuga en la reconstrucción de las PSF calibradas (handoff §1.9). Importa para los datos reales. Costo:
   medio-alto, necesita C:\Data.
4. Blinking y deriva dentro de una localización (portar t_mask, F107). Costo: medio.
5. Sensibilidad a errores en τ, la IRF o a (C mal conocida) y estimar τ junto con la posición. Importa porque en el
   experimento C se estima. Costo: bajo-medio.
6. Saturación y tasas altas (> 0.1/ciclo) con el tiempo muerto real del APD, que habría que medir. Costo: bajo con el
   simulador hecho.
7. Aplicar los hallazgos a `tracking_analysis`. Queda fuera del cerco: requiere otro trabajo y el permiso de la autora.
