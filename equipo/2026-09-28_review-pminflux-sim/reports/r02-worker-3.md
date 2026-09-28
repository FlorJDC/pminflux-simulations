# r02 — Worker 3: psf.py, estimate.py, test_estimate.py, compare_legacy_vs_v2.py

## Qué hice
- `src/pminflux_sim/psf.py`, `src/pminflux_sim/estimate.py`, `tests/test_estimate.py`, `scripts/compare_legacy_vs_v2.py` → `results/compare_legacy_vs_v2.json`. Sin tocar mixing.py, __init__.py, legacy/, test_acceptance.py. Sin commit.
- Corrida final con **source = v2sim** (simulate.py de W2, sha256 68a1b326…cda8, registrado en el JSON). Si W2 cambia simulate.py después, el orquestador debe re-correr `python scripts/compare_legacy_vs_v2.py` (≈60 s).
- Control: la misma corrida con `--source multinomial` en `work/w3r2/compare_multinomial.json` (tablas en `work/w3r2/table_*.txt|md`).

## API
- psf: `beam_positions(K, L, center=True, phi=0)` (cualquier K, F111), `donut(r,fwhm)`, `gaussian(r,fwhm)` (respeta fwhm, F109), `beam_profile(r,fwhm,kind)` (ValueError si kind inválido), `lambda_beams(r_xy,pos,fwhm,kind,grad=False)` vectorizada (…,K) y gradiente analítico (…,2,K), `measured_fwhm`.
- estimate: `sbr_to_beta`, `forward_probs(r,pos,fwhm,C,b,T,sbr,powers=None,bg=None)`, `legacy_probs`, `capture_fraction`, `neg_loglike`, `mle_mixing(counts,pos,fwhm,C,b,T,sbr,bounds_radius,center,powers,free_bg=False|True|'local'|'shared',free_powers=False,...)`, `mle_legacy(counts,pos,fwhm,sbr,bounds_radius,...)` (Ec. 3.5 continua = C=I, fondo 1/K), `crb(r,...,N,powers,free_bg,free_powers,n_is='cycle'|'windows',return_cov)`, `crb_legacy`, `cov_ellipse(cov,nsig=1,q=None)` → (width,height,angle_deg) convención matplotlib.
- MLE: arranque en grilla del disco (una matmul) + Fisher scoring en lote con búsqueda lineal y conjunto activo (borde parametrizado por ángulo; β congelado en sus cotas). Devuelve r, on_boundary, converged, nll, n_iter, beta, powers, boundary_fraction, n_failed, globals_result. Globales (potencias, β compartido) por verosimilitud perfilada (L-BFGS-B, gradiente por envolvente, re-arranque de grilla en cada evaluación).
- Parametrización de fondo: β = Nb/(Ns+Nb) del ciclo completo; sbr=inf → β=0 (F110 sin NaN).

## Tests (`python -m unittest tests.test_estimate`: 13 OK, 12.7 s)
Los 12 ids fijados + `test_forward_model_consistent_with_mixing`. `test_compare_json_complete` corre el script en modo quick (multinomial, tmp) y además valida `results/compare_legacy_vs_v2.json` completo (20 casos, SE>0, cross-check, F104).

## Resultados verificables
- Sesgo asintótico del legado (Ec. 3.5) en el setup medido sin IRF, SBR 21: 0.848/1.510/1.625/2.694/2.364 nm en (5,−5),(−5.07,−7.56),(20,0),(−15,15),(0,−30) — F104 reproducido (diferencia <0.001 nm con verifier-A). SBR 6: 0.585/0.729/1.664/2.323/1.933 (rango 0.59–2.32 de F104).
- CRB crb_minflux (N=2095) 0.816–1.222 nm; CRB del modelo de mezcla / CRB ingenuo = 1.0859–1.1349 (F104: 8.6–13.5 %).
- MLE de mezcla sobre conteos esperados: |r̂−r0| < 1e-11 nm en las 5 posiciones.
- forward_probs = mixing.window_probs y legacy_probs = mixing.naive_probs a rtol 1e-12; derivadas analíticas (x,y,β,log-potencias) = diferencias finitas a 1e-5 rel.
- crb con C=I, b=T/K coincide con crb_legacy a 1e-12 (sbr inf, 21.05, 6); ambos coinciden con Fisher por diferencias finitas independiente y con `donutloc.fisher.crb` (rtol 1e-6). CRB con β libre coincide con Fisher 3×3 por diferencias finitas (≤1e-4 nm).
- Cross-check ts.pos_MINFLUX (px=1, R=75) vs mle_legacy, 200 locs (−5.07,−7.56) SBR21 v2sim: 100 % dentro de 1 px por eje, 86 % idéntico al redondeo del continuo, máx |Δ| 0.657 nm.
- F106/F205: emisor (−5.07,−7.56) estimado sin cuantizar (asintótico exacto; MC media dentro de 3 SE; parte fraccionaria uniforme KS p>1e-3); en el nodo (−5,−8) RMSE/CRB ∈ (0.9,1.12), sin supereficiencia.
- F202: con potencias [21.02,16.65,22.96,22.86] y modelo de potencias iguales el sesgo es 2.6–7.9 nm por posición (smoke, 400 locs; el test exige >2 nm con 300); con potencias conocidas ≤0.15 nm; con free_powers (5 posiciones × 300 locs) ≤0.5 nm y potencias recuperadas a 3 %. Con una sola posición las potencias no son identificables: crb(free_powers) = inf.
- F203: fracción en el borde reportada; con R=10 nm y emisor en (20,0), 100 % en el borde y el óptimo coincide con búsqueda angular densa (≤2e-3 nm); con R=75, 0 %.
- F108: cov_ellipse da ángulo exacto (error 0°) y ejes 2√(r2·λ) para φ=0/30/60/120/150/−45°, nsig 1 y 2; el legado da ejes 2 y 6 siempre.
- F110: sbr=inf sin NaN en modelo, CRB y MLE (también con el emisor sobre un cero); el legado da un píxel fuera de r_max (>75 nm).
- β libre corrige un SBR mal supuesto (verdadero 6, supuesto 21) en (−15,15): sesgo < 3 SE (local y compartido), RMSE/CRB(β libre) ∈ [0.88,1.15].

## Tabla legado vs mezcla (v2sim, Ns=2000, n_loc=2000 por caso, SE bootstrap B=500; nm)
RMSE/CRB = RMSE_2D/(√2·CRB_mezcla) para ambos estimadores. Tiempo total 60.2 s (simulación 41.5 s, estimación 16.6 s).

| IRF | SBR | posición | N_win | legado: sesgo (x, y) ± SE | legado \|b\| | legado σx/σy | legado RMSE_2D | legado RMSE/CRB | mezcla: sesgo (x, y) ± SE | mezcla \|b\| | mezcla σx/σy | mezcla RMSE_2D | mezcla RMSE/CRB | CRB mezcla | CRB crb_minflux | sesgo asint. legado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 21 | (5, -5) | 1994 | (+0.713±0.022, -0.355±0.024) | 0.796±0.021 | 0.909/1.070 | 1.614±0.018 | 1.233±0.014 | (-0.033±0.020, -0.003±0.022) | 0.033±0.017 | 0.898/0.953 | 1.309±0.014 | 1.000±0.011 | 0.926 | 0.816 | 0.848 |
| 0.0 | 21 | (-5.07, -7.56) | 1993 | (-1.366±0.029, -0.382±0.025) | 1.419±0.025 | 1.332/1.043 | 2.208±0.023 | 1.694±0.017 | (+0.047±0.022, -0.024±0.021) | 0.053±0.022 | 0.947/0.907 | 1.311±0.014 | 1.006±0.011 | 0.922 | 0.849 | 1.510 |
| 0.0 | 21 | (20, 0) | 1993 | (-1.127±0.018, +1.116±0.030) | 1.586±0.025 | 0.766/1.343 | 2.215±0.022 | 1.401±0.014 | (+0.005±0.019, -0.049±0.028) | 0.050±0.026 | 0.884/1.313 | 1.583±0.019 | 1.002±0.012 | 1.117 | 1.004 | 1.625 |
| 0.0 | 21 | (-15, 15) | 1993 | (-2.583±0.030, +0.338±0.022) | 2.605±0.029 | 1.385/0.963 | 3.104±0.027 | 2.000±0.017 | (+0.076±0.028, +0.020±0.022) | 0.079±0.028 | 1.198/0.967 | 1.541±0.017 | 0.993±0.011 | 1.097 | 1.010 | 2.694 |
| 0.0 | 21 | (0, -30) | 1994 | (+2.414±0.026, +0.047±0.035) | 2.415±0.026 | 1.195/1.502 | 3.085±0.025 | 1.573±0.013 | (+0.056±0.027, -0.097±0.034) | 0.112±0.036 | 1.201/1.509 | 1.931±0.023 | 0.985±0.012 | 1.387 | 1.222 | 2.364 |
| 0.0 | 6 | (5, -5) | 2186 | (+0.020±0.021, +0.567±0.025) | 0.567±0.025 | 0.948/1.079 | 1.544±0.018 | 1.122±0.013 | (+0.028±0.022, -0.026±0.022) | 0.038±0.019 | 0.942/1.028 | 1.395±0.016 | 1.013±0.012 | 0.973 | 0.887 | 0.585 |
| 0.0 | 6 | (-5.07, -7.56) | 2186 | (-0.672±0.028, +0.300±0.024) | 0.736±0.030 | 1.190/0.998 | 1.719±0.021 | 1.252±0.015 | (-0.000±0.023, +0.015±0.021) | 0.015±0.015 | 1.014/0.954 | 1.392±0.015 | 1.014±0.011 | 0.971 | 0.909 | 0.729 |
| 0.0 | 6 | (20, 0) | 2186 | (-1.161±0.020, +1.075±0.029) | 1.583±0.024 | 0.890/1.326 | 2.248±0.022 | 1.348±0.013 | (+0.092±0.023, -0.033±0.030) | 0.098±0.023 | 0.997/1.366 | 1.694±0.020 | 1.016±0.012 | 1.179 | 1.070 | 1.664 |
| 0.0 | 6 | (-15, 15) | 2186 | (-2.254±0.033, +0.475±0.022) | 2.303±0.032 | 1.443/1.030 | 2.907±0.028 | 1.762±0.017 | (+0.015±0.028, -0.012±0.023) | 0.019±0.019 | 1.278/1.029 | 1.641±0.019 | 0.995±0.012 | 1.167 | 1.087 | 2.323 |
| 0.0 | 6 | (0, -30) | 2186 | (+1.901±0.030, +0.394±0.038) | 1.942±0.026 | 1.292/1.717 | 2.895±0.029 | 1.370±0.014 | (+0.026±0.029, -0.037±0.037) | 0.045±0.031 | 1.279/1.707 | 2.133±0.027 | 1.009±0.013 | 1.494 | 1.346 | 1.933 |
| 0.3 | 21 | (5, -5) | 1970 | (+0.780±0.021, -0.395±0.024) | 0.875±0.020 | 0.897/1.092 | 1.662±0.017 | 1.260±0.013 | (+0.021±0.020, -0.034±0.021) | 0.040±0.019 | 0.897/0.965 | 1.318±0.016 | 0.999±0.012 | 0.933 | 0.816 | 0.875 |
| 0.3 | 21 | (-5.07, -7.56) | 1970 | (-1.438±0.029, -0.389±0.022) | 1.489±0.025 | 1.335/1.022 | 2.246±0.022 | 1.710±0.017 | (+0.013±0.022, -0.030±0.019) | 0.033±0.017 | 0.952/0.884 | 1.300±0.015 | 0.990±0.011 | 0.928 | 0.849 | 1.545 |
| 0.3 | 21 | (20, 0) | 1970 | (-1.124±0.016, +1.191±0.031) | 1.637±0.025 | 0.757/1.365 | 2.262±0.024 | 1.420±0.015 | (+0.024±0.020, +0.005±0.029) | 0.024±0.018 | 0.880/1.331 | 1.595±0.021 | 1.002±0.013 | 1.126 | 1.004 | 1.647 |
| 0.3 | 21 | (-15, 15) | 1970 | (-2.673±0.034, +0.341±0.021) | 2.694±0.033 | 1.482/0.953 | 3.219±0.030 | 2.059±0.019 | (+0.038±0.028, +0.028±0.022) | 0.047±0.026 | 1.281/0.953 | 1.597±0.019 | 1.022±0.012 | 1.105 | 1.010 | 2.740 |
| 0.3 | 21 | (0, -30) | 1970 | (+2.448±0.027, +0.044±0.036) | 2.448±0.026 | 1.226/1.525 | 3.134±0.028 | 1.585±0.014 | (+0.040±0.027, -0.089±0.034) | 0.097±0.035 | 1.233/1.537 | 1.972±0.027 | 0.998±0.014 | 1.398 | 1.222 | 2.406 |
| 0.3 | 6 | (5, -5) | 2162 | (+0.015±0.020, +0.568±0.025) | 0.568±0.025 | 0.939/1.092 | 1.547±0.017 | 1.115±0.012 | (+0.007±0.020, -0.015±0.023) | 0.017±0.016 | 0.933/1.035 | 1.393±0.016 | 1.004±0.011 | 0.981 | 0.887 | 0.577 |
| 0.3 | 6 | (-5.07, -7.56) | 2162 | (-0.621±0.028, +0.262±0.022) | 0.674±0.029 | 1.214/0.988 | 1.704±0.021 | 1.231±0.015 | (+0.061±0.022, -0.016±0.022) | 0.063±0.021 | 1.032/0.942 | 1.398±0.016 | 1.011±0.011 | 0.978 | 0.909 | 0.749 |
| 0.3 | 6 | (20, 0) | 2162 | (-1.229±0.019, +1.121±0.029) | 1.663±0.023 | 0.873/1.338 | 2.306±0.021 | 1.371±0.012 | (+0.038±0.022, -0.003±0.030) | 0.038±0.021 | 0.981/1.376 | 1.690±0.020 | 1.005±0.012 | 1.189 | 1.070 | 1.688 |
| 0.3 | 6 | (-15, 15) | 2162 | (-2.336±0.035, +0.458±0.023) | 2.381±0.033 | 1.492/1.014 | 2.987±0.030 | 1.796±0.018 | (-0.011±0.029, -0.019±0.023) | 0.022±0.019 | 1.313/1.014 | 1.658±0.019 | 0.997±0.012 | 1.176 | 1.087 | 2.367 |
| 0.3 | 6 | (0, -30) | 2161 | (+1.928±0.029, +0.356±0.037) | 1.960±0.027 | 1.329/1.734 | 2.935±0.027 | 1.377±0.012 | (-0.015±0.031, -0.058±0.038) | 0.060±0.030 | 1.308/1.714 | 2.156±0.027 | 1.012±0.013 | 1.507 | 1.346 | 1.985 |

Resumen: legado |b| 0.567–2.694 nm, RMSE/CRB 1.115–2.059; mezcla |b| 0.015–0.112 nm, RMSE/CRB 0.985–1.022; mezcla con β libre RMSE/CRB 0.982–1.019 (su CRB es 1.000–1.038× el de β fijo). 0 fallas, 0 % en el borde, en los 60 ajustes (20 casos × 3 estimadores).

## Hallazgo lateral (para W2 / verificador A)
- En v2sim el sesgo del MLE de mezcla supera 2 SE por eje en 6/20 casos (máx 3.99 SE: (20,0) SBR6 IRF0, bx = +0.092±0.023). Con `--source multinomial` y las mismas semillas, máx 1.99 SE en los 20 casos. El sesgo MC coincide con el "sesgo implícito" de las fracciones agregadas por ventana, así que no viene del estimador.
- Chequeo propio (4000×2095 fotones ×3 semillas): a 2.5e-3/ciclo con `tcspc='earliest'` las fracciones por ventana se desvían de mixing.window_probs en ~1e-3 relativo (z hasta 3–4; déficit en la ventana 3). Con `tcspc='none'` o con tasa 1e-4 el desvío desaparece. Es el efecto físico de TCSPC primer fotón / tiempo muerto a tasa finita: ≤0.11 nm, ≤0.08 CRB. Lo tiene que cuantificar dead_time_sweep de W2. No lo verifiqué como un bug.

## Limitaciones / no resuelto
- Globales perfilados (β compartido, potencias) tienen sesgo de Neyman–Scott O(1/N): β compartido estimado 0.0430 contra 0.0453 verdadero (smoke, 2000 locs a (20,0)). Las posiciones siguen sin sesgo apreciable.
- free_powers necesita ≥3 posiciones distintas en el conjunto; el sesgo residual de posición (≤0.25 nm en el smoke) es común a todas las locs, por el error de las potencias.
- Precisión de la posición ~1e-5 nm en localizaciones con NLL casi plana (tolerancia 1e-4 nm en el test).
- beam_positions sin centro usa 2πk/K + phi; el `beams(center=None)` del legado con K par está rotado π/K (reproducible con phi). Con K=4 y centro coincide exactamente.
- La variante "legado" usa el mismo disco R=75 y sbr = Ns/Nb nominal (como F104); no emula la grilla (eso lo da el cross-check).
