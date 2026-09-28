# pminflux-sim v2

Simulador y estimador de **p-MINFLUX pulsado** (K haces intercalados en un ciclo TCSPC) que modela
la **fuga entre ventanas**: con 20 MHz (T = 50 ns), K = 4 (un pulso cada 12.5 ns) y un tiempo de
vida τ = 4.21 ns, un 4.7 % de los fotones de cada haz cae en la ventana del haz siguiente. El
paquete reemplaza a `sim_exp` / `nMINFLUX` / `pos_MINFLUX` / `crb_minflux` de
`legacy/p-minflux-main` (copia de solo lectura del código original) y corrige los hallazgos del
reporte (`report/index.html`, `results/findings.json`).

> Trabajo privado y no publicado. No subir a ningún remoto.

---

## 1. Instalación

Requisitos: Python ≥ 3.8, `numpy`, `scipy` (y `matplotlib` para las figuras y para importar el
legado).

Opción A, instalar en modo editable (desde la raíz del proyecto):

```bash
pip install -e .
```

(Usa `pyproject.toml` + `setup.cfg`; pip baja setuptools/wheel en un entorno aislado, así que
necesita internet. Sin internet: `pip install -e . --no-build-isolation`, que requiere tener
instalados `setuptools >= 64` y `wheel`; si no, usar la opción B. Se comprobó que
`pip wheel . --no-deps` arma el paquete con los 6 módulos.)

Opción B, sin instalar nada: agregar `src/` al `sys.path`.

```python
import sys
sys.path.insert(0, r"C:\ruta\a\pminflux-sim-v2\src")
import pminflux_sim as pm
```

Todos los scripts de `scripts/` y los tests ya hacen la opción B por su cuenta.

## 2. Inicio rápido

```python
import numpy as np
import pminflux_sim as pm

pos = pm.beam_positions(4, 100.0)                            # TCP: haz central + 3 en un círculo de L = 100 nm
C = pm.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, irf_fwhm=0.3) # C[i, j] = P(fotón del haz j cae en la ventana i)
r0 = np.array([5.0, -5.0])                                   # emisor (nm), continuo
lam = pm.lambda_beams(r0, pos, 360.0)                        # excitación de cada haz (dona, fwhm 360 nm)

params = pm.SimParams()          # setup medido: tau 4.21, ventana [0, 10.1], IRF 0.3, d = 22, 2.5e-3/ciclo
counts, tags = pm.simulate_counts(lam, 500, 2095, 2000 / 95., params,
                                  rng=np.random.default_rng(1), return_tags=True)

# con datos reales se parte de los microtiempos (ns) y del id de localización de cada fotón:
counts = pm.count_windows(tags["microtime_ns"], T=50.0, K=4, a=0.0, b=10.1,
                          macro_index=tags["loc"], n_loc=500)

est = pm.mle_mixing(counts, pos, 360.0, C, 10.1, 50.0, 2000 / 95., bounds_radius=75.0)
leg = pm.mle_legacy(counts, pos, 360.0, 2000 / 95., bounds_radius=75.0)   # Ec. 3.5, para comparar
sigma = pm.crb(r0, pos, 360.0, C, 10.1, 50.0, 2000 / 95., 2095)          # CRB por eje (nm)

print(est.r.mean(0) - r0, leg.r.mean(0) - r0, sigma, est.boundary_fraction, est.n_failed)
```

`est` es un `MLEResult` (un `dict` con atributos): `r` (n, 2), `converged`, `on_boundary`,
`boundary_fraction`, `n_failed`, `nll`, `n_iter`, `beta`, `powers`, `globals_result`.

El mismo flujo, con tabla de resultados, está en `scripts/example_end_to_end.py` (unos segundos).

## 3. Qué correr

| Qué | Comando (desde la raíz) | Salida | Tiempo aprox. |
|---|---|---|---|
| Tests | `python -m unittest discover -s tests` | consola | ~1–2 min |
| Ejemplo de punta a punta | `python scripts/example_end_to_end.py` | tabla en consola | < 10 s |
| Estudio de desalineación y eficiencia v2 | `python scripts/study_misalignment_v2.py` | `results/study_v2.json` | ~45 s |
| Legado contra v2 (20 casos) | `python scripts/compare_legacy_vs_v2.py` | `results/compare_legacy_vs_v2.json` | ~1 min |
| Validación de la matriz de mezcla contra `sim_exp` | `python scripts/validate_mixing_matrix.py` | `results/mixing_validation.json`, `results/mixing_rate_sweep.json` | largo (usa el legado) |
| Barrido de tiempo muerto | `python scripts/sweep_dead_time.py` | `results/dead_time_sweep.json` | varios min |
| Registro de hallazgos | `python scripts/build_findings.py` | `results/findings.json` (+ descartados) | < 1 s |
| Figuras del reporte | `python scripts/make_report_figures.py` | `report/figs/*.png`, `captions.json` | < 1 min |
| Reporte HTML | `python scripts/build_report.py` | `report/index.html` | < 1 min |

Todos los scripts tienen semilla fija y escriben en el JSON los parámetros, las semillas, las
versiones y el sha256 del código que los generó. `tests/test_estimate.py` y
`tests/test_usability.py` fallan si `compare_legacy_vs_v2.json` o `study_v2.json` no
corresponden al código actual: después de tocar `src/`, regenerarlos.

## 4. Módulos y API

| Módulo | Qué hace | Funciones principales |
|---|---|---|
| `mixing` | Matriz de mezcla C y modelos de probabilidades por ventana | `mixing_matrix`, `window_expected`, `window_probs`, `naive_probs`, `pearson_chi2`, `sim_exp_window_probs` |
| `simulate` | Simulador fotón por fotón en dominio temporal (TCSPC, tiempo muerto, IRF, fondo, parpadeo) | `SimParams`, `simulate_counts` |
| `windows` | Conteo por ventana desde microtiempos | `count_windows`, `check_overlap` |
| `psf` | Posiciones de los haces y perfiles | `beam_positions`, `lambda_beams`, `donut`, `gaussian` |
| `estimate` | MLE con mezcla, MLE del legado, CRB, elipse | `mle_mixing`, `mle_legacy`, `crb`, `crb_legacy`, `forward_probs`, `cov_ellipse` |

Todo lo anterior se puede importar directamente de `pminflux_sim` (`pm.__version__ == "2.0.0"`).

Opciones útiles:

- `simulate_counts(..., t_mask=m)`: parpadeo del emisor (0/1 por ciclo, extensión periódica); en
  un ciclo apagado no hay señal, el fondo sigue (port de F107).
- `SimParams(tcspc=...)`: `"earliest"` (TCSPC real, default), `"highest"` (emula `sim_exp`, F101),
  `"none"`. `SimParams(counting="legacy")` emula `nMINFLUX` con sus defectos (F102/F103).
- `SimParams(beam_powers=[...])`: potencias relativas de los haces (F202).
- `mle_mixing(..., free_bg=True | "shared")`: fondo libre por localización o compartido.
- `mle_mixing(..., free_powers=True)`: potencias libres compartidas (necesita varias posiciones;
  ver limitaciones).
- `mle_mixing(..., chunk=20000)`: tamaño de bloque del arranque en grilla (solo memoria).
- `crb(..., free_bg=..., free_powers=..., n_is="cycle" | "windows")`.

## 5. Convenciones

- **Unidades**: nm y ns.
- **Ciclo**: período `T` (50 ns a 20 MHz), `K` haces; el pulso del haz `j` sale en `j·T/K`.
- **Ventanas**: ventana `i` = `[i·T/K + a, i·T/K + a + b)` **módulo T** (medio abierta; se admite
  `a < 0` y ventanas que cruzan T). Setup medido: `a = 0`, `b = 10.1` ns. Se exige **b ≤ T/K**
  (ventanas disjuntas): con `b > T/K` todas las funciones levantan `ValueError` salvo
  `allow_overlap=True`, que solo avisa (la verosimilitud y el CRB multinomiales dejan de valer).
- **C**: `C[i, j]` = probabilidad de que un fotón del haz `j` se detecte en la ventana `i`
  (incluye las imágenes periódicas: fuga hacia las ventanas siguientes y el ciclo siguiente). En
  el setup medido `C[i, i] = 0.8973` y `C[i+1, i] = 0.0467`.
- **N** = Ns + Nb = fotones **detectados en el ciclo completo** (después del TCSPC y del tiempo
  muerto), no solo los que caen en ventanas. El CRB usa N × (fracción capturada en ventanas).
- **SBR** = Ns/Nb (del ciclo completo; en el simulador, de los fotones incidentes). `sbr = inf` es
  sin fondo. **β** = Nb/(Ns+Nb) = 1/(1+SBR). El fondo es uniforme: aporta `b/T` por ventana.
- **Modelo directo**: `λ_k = P_k · I(|r − pos_k|)`, `q = λ/Σλ`, `s = C q`,
  `e = (1−β) s + β b/T`, `p = e/Σe`. Con `C = I` y `b/T = 1/K` es la Ec. 3.5 del legado.
- **L** = diámetro del círculo de los haces (TCP con haz central); **fwhm** = FWHM del perfil (en
  la dona, el anillo está en 0.6006·fwhm).
- **CRB**: por eje, `σ = sqrt(tr(F⁻¹)/2)`; la eficiencia se informa como
  `RMSE/CRB = RMSE_2D / (√2 σ)` (1 = eficiente).
- **Emisores**: posición continua (la PSF se evalúa en `r`, sin grilla); el sesgo se mide contra
  la posición simulada.

## 6. Supuestos (declarados, no medidos)

- **Tiempo muerto del detector: 22 ns** (`SimParams.dead_time`), SPAD no paralizable, valor
  típico. **No está medido** en el equipo de la autora (`pm.DEAD_TIME_ASSUMPTION`).
- **IRF gaussiana de 0.3 ns FWHM, centrada en el pulso**. **No está medida.**
- τ = 4.21 ns y la ventana [0, 10.1] ns sí están medidos (datos 20260707).
- Fondo uniforme en el ciclo.
- PSF: dona analítica (Balzarotti S16). Las PSF medidas 20260820 no están en disco; el estudio v2
  usa la dona con los centros y potencias del ajuste realista de la autora.

## 7. Resultado: con d = n·T el tiempo muerto no sesga

Con un SPAD no paralizable y tiempo muerto **d = n·T** (n entero ≥ 1, p. ej. 50 o 100 ns a
20 MHz), el sesgo que el tiempo muerto introduce en las fracciones por ventana es **exactamente
cero a cualquier tasa**.

*Prueba (esbozo).* Con d ≥ T, en un intervalo de largo d cabe a lo sumo una avalancha, así que la
probabilidad de que el detector esté muerto en el instante t es
P(muerto en t) = ∫_{t−d}^{t} r(s) ds, con r(s) la tasa (periódica, de período T) de avalanchas.
Si d = n·T, esa integral abarca n períodos completos y vale n × (avalanchas por período): una
constante que **no depende de la fase** t mod T. La densidad registrada es entonces
ρ(t) = λ(t)·(1 − const) ∝ λ(t), con la misma forma que sin tiempo muerto, y las fracciones por
ventana no cambian. (Con d ≥ T el "1 fotón por ciclo" del TCSPC ya queda implícito.)

Con d = 35 o 75 ns (no múltiplos de T) la integral depende de la fase y el sesgo reaparece. No
aplica a detectores paralizables ni a un TDC con tiempo muerto propio. Verificado en R2 con una
prueba independiente y Monte Carlo (d = 35/50/75/100, `results/dead_time_sweep.json`). El valor
real de d no está medido (ver §6).

## 8. Limitaciones

- **El modelo directo no incluye la distorsión de tasa finita** (TCSPC de 1 fotón por ciclo y
  tiempo muerto). A las tasas del tracking (1e-3–5.5e-3 fotones/ciclo) eso induce un sesgo de
  **0.02–0.035 nm**, al que se suma el sesgo **O(1/N) del MLE, ~0.036 nm con N ~ 2000**; todo junto
  queda **≤ 0.03 CRB**. Con d = n·T la parte del tiempo muerto se anula (§7).
- **`tcspc="highest"`** (emulación de `sim_exp`) fija el SBR de los fotones **incidentes**; `sim_exp`
  fija el de los **registrados**. La diferencia es de un 0.5 % a 0.0105 fotones/ciclo.
- **Tiempo muerto a saturación**: el punto fijo del tiempo muerto es O(n²) en el peor caso
  (p. ej. d = 500 ns y 0.3 fotones/ciclo: 13 s y ~450 MB para 1e6 fotones). No afecta el régimen de
  tracking (2–4 pasadas).
- **b ≤ T/K**: las ventanas solapadas no están soportadas por el estimador ni por el CRB (error
  explícito; `allow_overlap=True` para forzar).
- **Potencias libres (`free_powers=True`)**: no son identificables con emisores en una sola
  posición, y estimadas junto con una posición por localización tienen un sesgo de parámetros
  incidentales (Neyman-Scott) que no baja al agregar localizaciones: con el EBP desalineado y
  N = 400, las potencias relativas salen 0.87/1.18/1.23, 0.85/1.17/1.21 y 0.85/1.16/1.19 con
  100/400/1600 localizaciones por posición, contra 0.79/1.09/1.09 verdaderas; con N = 100 el
  ajuste se desestabiliza (en el estudio v2 el honesto con potencias libres llega a 27 nm de
  sesgo). Conviene calibrarlas aparte con N alto y pasarlas como
  conocidas (`powers=`).
- `n_mode="poisson"`, el caso d > T fuera de n·T y el fondo β libre no tienen una reproducción
  independiente completa (quedan como puntos abiertos del reporte).
- `converged=False` marca localizaciones que agotaron `maxiter` sin llegar al óptimo (a N = 10–50,
  ~0.1 %); si la NLL mejoró ≤ 1e-6 en las últimas 10 iteraciones se marca `converged=True`.

## 9. Migración legado → v2

| Legado (`tools/tools_simulations.py`) | v2 | Diferencias |
|---|---|---|
| `sim_exp(key, t_mask, psf, r0, SBR, Ns, Nb, M_p, Tlife, factor, dt)` | `simulate.simulate_counts(lam, n_loc, N, sbr, SimParams(...), rng, return_tags, t_mask)` | tiempo absoluto con fuga entre ciclos; TCSPC "gana el más temprano" + tiempo muerto (F101); IRF; `t_mask` sí se aplica (F107); N detectados en lugar de M_p ciclos |
| `nMINFLUX(K, τ, relTime, a, b)` | `windows.count_windows(microtime_ns, T, K, a, b, macro_index)` | ventanas medio abiertas plegadas módulo T (F103); sin ceros artificiales (F102); error con b > T/K |
| `pos_MINFLUX(n, PSF, SBR, px_nm, r_max_nm)` | `estimate.mle_mixing(counts, pos, fwhm, C, b, T, sbr, bounds_radius)` | continuo (sin grilla, F106/F205), con matriz de mezcla C y fondo b/T (F104); informa `on_boundary` (F203) y `converged` |
| (para comparar con el legado) | `estimate.mle_legacy(counts, pos, fwhm, sbr, bounds_radius)` | la Ec. 3.5 de `pos_MINFLUX`, continua |
| `crb_minflux(K, PSF, SBR, px_nm, size_nm, N)` | `estimate.crb(r, pos, fwhm, C, b, T, sbr, N)` (y `crb_legacy`) | con fuga; N del ciclo completo; estorbos `free_bg`/`free_powers`; `sbr = inf` sin NaN (F110) |
| `psf(...)`, `beams(K, L, center, d)`, `ebp_centres(K, L, center, phi)` | `psf.beam_positions(K, L, center, phi)`, `psf.lambda_beams(r, pos, fwhm, kind)` | cualquier K (F111); la fwhm del gaussiano se respeta (F109); gradiente analítico |
| `cov_ellipse(cov, q, nsig)` | `estimate.cov_ellipse(cov, nsig, q)` | autovectores por columnas y factor χ² aplicado (F108) |
| `Tlife = 0.001` (estudios) | `SimParams(tau=4.21)` | el τ real; con τ ≈ 0 no hay fuga y el estudio no ve el desajuste (F201, "crimen inverso") |
| `dt = 50`, `b = 12.5` | `SimParams(T=50.0, b=10.1)` | ventana medida [0, 10.1] |

Convención de parámetros:

| Legado | v2 |
|---|---|
| `SBR` (Ns/Nb) | `sbr` = Ns/Nb del ciclo completo |
| `Ns`, `Nb` | `N = Ns + Nb` detectados; `sbr = Ns/Nb` |
| `Tlife` | `tau` (ns) |
| `dt` (período) | `T` (ns) |
| `a`, `b` (ventana) | `a`, `b` (ns), ventana `[i·T/K + a, +b)` mod T |
| `M_p` (ciclos), `factor` | `rate_per_cycle` (fotones incidentes por ciclo); la simulación corre hasta N detecciones |
| `px_nm`, `size_nm`, `r_max_nm` | sin grilla; `bounds_radius` (nm) = radio del disco de búsqueda |
| `r0` en índices de píxel | `r` en nm, continuo |
| PSF normalizadas al máximo | `powers` / `beam_powers` = potencias relativas |

## 10. Resultados del estudio v2 (`results/study_v2.json`)

Setup medido, dona analítica, 5 emisores continuos, 400 localizaciones por posición, N = 2095
(SBR 21), disco de búsqueda de 75 nm. EBP desalineado = centros y potencias del ajuste realista
(`Resultados/realistic_psf/fit_parameters.csv`).

| Geometría / estimador | máx. \|b\| (nm) | RMSE/CRB medio |
|---|---|---|
| ideal / mezcla, potencias conocidas | 0.12 | 1.00 |
| ideal / legado (Ec. 3.5) | 3.12 | 1.67 |
| desalineada / mezcla, potencias conocidas | 0.09 | 1.00 |
| desalineada / mezcla, potencias libres | 0.32 | 1.02 |
| desalineada / ingenuo (geometría ideal) | 8.58 | 4.09 |
| desalineada / legado (Ec. 3.5, geometría verdadera) | 3.18 | 1.73 |

El CRB es el del modelo con fuga. Los SE por bootstrap y el barrido N ∈ {100, 400, 1600} están
en el JSON. Verificación independiente de este estudio: pendiente (ronda 3).

## 11. Estructura

```
src/pminflux_sim/    paquete (mixing, simulate, windows, psf, estimate)
tests/               unittest (test_acceptance.py es el test de aceptación: no editar)
scripts/             estudios, validación, hallazgos, figuras y reporte
results/             JSON reproducibles (con semillas y sha256)
report/              reporte HTML autocontenido y figuras
legacy/              copia de solo lectura del código original (no editar)
equipo/              trabajo del equipo de agentes (ledger, reportes por ronda)
```
