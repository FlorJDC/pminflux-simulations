# -*- coding: utf-8 -*-
"""Estudio de desalineación del EBP y de eficiencia con el simulador y el estimador v2.

Reemplaza ``legacy/p-minflux-main/simulation_misalignment.py`` y el estudio de eficiencia
(``documento/make_fig_eficiencia.py``) de la autora, en el SETUP MEDIDO del experimento a 20 MHz
(no con Tlife = 0.001 y b = T/K como los estudios originales, F201):

- simulador ``pminflux_sim.simulate`` (dominio temporal): T = 50 ns, K = 4, tau = 4.21 ns, ventana
  [0, 10.1] ns, IRF gaussiana 0.3 ns FWHM (SUPUESTO), tiempo muerto 22 ns (SUPUESTO), TCSPC
  'earliest', 2.5e-3 fotones/ciclo, conteo periódico, N fijo = Ns + Nb (Ns = 2000, SBR 21).
- PSF: dona ANALÍTICA circular (fwhm 360 nm). Las PSF medidas 20260820 no están en disco; del
  ajuste realista de la autora (``Resultados/realistic_psf/fit_parameters.csv``) se toman solo los
  CENTROS de los haces y sus ``intensity_scale`` como potencias relativas (supuesto de F202).
- Emisores fuera de la grilla (posiciones continuas) y la referencia del sesgo es la posición
  SIMULADA (F205). Cinco posiciones, ajustadas en conjunto (las potencias libres solo son
  identificables con varias posiciones).

Casos: geometría {ideal, desalineada} x estimador:

- ``honesto``: ``mle_mixing`` con la matriz de mezcla C, los centros verdaderos y potencias LIBRES
  (estimadas en conjunto, P_0 = 1).
- ``honesto_P_conocidas``: igual pero con las potencias verdaderas (calibración perfecta).
- ``ingenuo``: ``mle_mixing`` con C pero con la geometría ideal (triángulo regular con el L_eff y
  la orientación del EBP medido) y potencias iguales.
- ``legado``: ``mle_legacy`` (Ec. 3.5: sin fuga, fondo 1/K) con los centros y las potencias
  verdaderos (el mejor caso del estimador del legado: solo le falta la fuga).

Por caso: sesgo, |b|, RMSE_2D, RMSE/CRB (CRB por eje del modelo de mezcla CON fuga y parámetros
conocidos; RMSE/CRB = RMSE_2D/(sqrt2 CRB)), fracción en el borde del disco de búsqueda
(R = 75 nm = 0.75 L) y SE por bootstrap no paramétrico (desvío de las remuestras e intervalo de
percentiles 16-84 %, sin suponer normalidad: F204). El bootstrap remuestrea estimaciones; no
incluye la variabilidad del ajuste global de las potencias.

Barrido de eficiencia: N en {100, 400, 1600} con las mismas geometrías y estimadores.

Nota (resultado del estudio, ver ``NOTE_FREE_POWERS``): las potencias libres compartidas,
estimadas junto con una posición por localización, tienen un sesgo de "parámetros incidentales"
(Neyman-Scott) que no baja al agregar localizaciones, solo al subir N por localización.

Uso (desde la raíz):  python scripts/study_misalignment_v2.py [--seed 20260928] [--n-loc 400]
                      [--n-loc-sweep 200] [--n-boot 300] [--quick] [--out results/study_v2.json]
"""

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time

import numpy as np
import scipy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pminflux_sim import mixing as mx  # noqa: E402
from pminflux_sim import psf  # noqa: E402
from pminflux_sim import estimate as es  # noqa: E402
from pminflux_sim import simulate as sim  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "results", "study_v2.json")
SETUP = dict(T=50.0, K=4, tau=4.21, a=0.0, b=10.1, irf_fwhm=0.3, rate_per_cycle=2.5e-3,
             dead_time=22.0, tcspc="earliest", counting="periodic", n_mode="fixed")
ASSUMPTIONS = ["dead_time = 22 ns es un SUPUESTO (SPAD típico), no medido",
               "IRF gaussiana de 0.3 ns FWHM centrada: SUPUESTO, no medida",
               "PSF: dona analítica circular fwhm 360 nm (las PSF medidas 20260820 no están en disco)",
               "potencias relativas = intensity_scale del ajuste realista (supuesto de F202: el máximo "
               "de cada .npy refleja la potencia del haz)"]
NS, SBR = 2000, 2000.0 / 95.0
FWHM, L_IDEAL, R_SEARCH = 360.0, 100.0, 75.0
# Centros (nm) e intensity_scale del ajuste realista de la autora (fit_parameters.csv, 4 decimales)
FIT_CSV = "legacy/p-minflux-main/Resultados/realistic_psf/fit_parameters.csv"
POS_MEAS = np.array([[0.0399, 0.1078], [-44.1278, -26.6938], [45.2029, -25.7607], [-4.8180, 50.7680]])
POWERS = np.array([21.02, 16.65, 22.96, 22.86])
# Emisores continuos (nm): el R0 experimental de la autora y cuatro más, ninguno sobre la grilla.
POSITIONS = [(-5.07, -7.56), (6.31, -4.87), (12.73, 8.14), (-14.22, 3.37), (2.91, 17.58)]
N_SWEEP = [100, 400, 1600]
NOTE_FREE_POWERS = (
    "Potencias libres (honesto): el MLE conjunto de potencias compartidas + una posición por "
    "localización tiene sesgo de parámetros incidentales (Neyman-Scott). Chequeo aparte (EBP "
    "desalineado, 5 posiciones, verdad P/P0 = 0.792/1.092/1.088): con N = 400 da 0.870/1.179/1.233, "
    "0.854/1.171/1.206 y 0.847/1.160/1.188 con 100/400/1600 localizaciones por posición (no converge "
    "a la verdad); con N = 100 da 1.056/1.408/1.536 con 1600 por posición y es inestable con pocas "
    "(3.0/3.9/9.3 con 100 por posición). Recomendación: calibrar las potencias aparte con N alto y "
    "pasarlas como conocidas (honesto_P_conocidas).")


def _sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except IOError:
        return None


def ideal_like(pos_meas):
    """Triángulo regular con haz central, con el L_eff y la orientación media del EBP medido."""
    ring = pos_meas[1:] - pos_meas[0]
    L_eff = 2.0 * float(np.mean(np.hypot(ring[:, 0], ring[:, 1])))
    th = np.arctan2(ring[:, 1], ring[:, 0]) - 2 * np.pi * np.arange(1, 4) / 3.0
    phi = float(np.angle(np.mean(np.exp(1j * th))))
    return psf.beam_positions(4, L_eff, center=True, phi=phi), L_eff, phi


def _metrics(e, r0, crb_axis):
    d = e - r0
    bias = d.mean(-2)
    rmse = np.sqrt(np.mean(np.sum(d ** 2, -1), -1))
    return {"bias_abs": np.hypot(bias[..., 0], bias[..., 1]), "rmse_2d": rmse,
            "rmse_over_crb": rmse / (math.sqrt(2.0) * crb_axis), "bias_x": bias[..., 0],
            "bias_y": bias[..., 1]}


def summarize(est, r0, crb_axis, rng, n_boot):
    ok = np.all(np.isfinite(est), axis=1)
    e = est[ok]
    m = _metrics(e, r0, crb_axis)
    idx = rng.integers(0, e.shape[0], size=(n_boot, e.shape[0]))
    mb = _metrics(e[idx], r0, crb_axis)
    out = {"n_valid": int(ok.sum())}
    for k in m:
        out[k] = float(m[k])
        out[k + "_se"] = float(np.std(mb[k], ddof=1))
        lo, hi = np.percentile(mb[k], [16.0, 84.0])
        out[k + "_p16_p84"] = [float(lo), float(hi)]
    out["bias_vec"] = [out.pop("bias_x"), out.pop("bias_y")]
    for k in ("bias_x_se", "bias_y_se", "bias_x_p16_p84", "bias_y_p16_p84"):
        out.pop(k)
    return out


def run_block(N, n_loc, seed_base, geoms, C, n_boot, verbose=True):
    """Simula las 5 posiciones por geometría y ajusta los 3 estimadores. Devuelve (casos, tiempos)."""
    Nb_equiv = N / (1.0 + SBR)
    out = []
    t_sim = t_est = 0.0
    for gi, (gname, g) in enumerate(geoms.items()):
        p = sim.SimParams(beam_powers=g["powers_true"], **SETUP)
        counts, r_true = [], []
        t0 = time.time()
        for pi, r0 in enumerate(POSITIONS):
            rng = np.random.default_rng([seed_base, int(N), gi, pi])
            lam = psf.lambda_beams(np.asarray(r0, float), g["pos_true"], FWHM)
            counts.append(sim.simulate_counts(lam, n_loc, N, SBR, params=p, rng=rng))
            r_true.append(np.repeat(np.asarray(r0, float)[None], n_loc, axis=0))
        counts = np.vstack(counts)
        r_true = np.vstack(r_true)
        t_sim += time.time() - t0
        t0 = time.time()
        ests = {
            "honesto": es.mle_mixing(counts, g["pos_true"], FWHM, C, SETUP["b"], SETUP["T"], SBR,
                                     R_SEARCH, free_powers=True),
            "honesto_P_conocidas": es.mle_mixing(counts, g["pos_true"], FWHM, C, SETUP["b"],
                                                 SETUP["T"], SBR, R_SEARCH, powers=g["powers_true"]),
            "ingenuo": es.mle_mixing(counts, g["pos_naive"], FWHM, C, SETUP["b"], SETUP["T"], SBR,
                                     R_SEARCH),
            "legado": es.mle_legacy(counts, g["pos_true"], FWHM, SBR, R_SEARCH,
                                    powers=g["powers_true"]),
        }
        t_est += time.time() - t0
        crb_known = es.crb(np.array(POSITIONS), g["pos_true"], FWHM, C, SETUP["b"], SETUP["T"], SBR, N,
                           powers=g["powers_true"])
        crb_freep = es.crb(np.array(POSITIONS), g["pos_true"], FWHM, C, SETUP["b"], SETUP["T"], SBR, N,
                           powers=g["powers_true"], free_powers=True)
        for ei, (ename, res) in enumerate(ests.items()):
            per_pos = []
            for pi, r0 in enumerate(POSITIONS):
                sl = slice(pi * n_loc, (pi + 1) * n_loc)
                brng = np.random.default_rng([seed_base, int(N), gi, pi, 1 + ei])
                m = summarize(res.r[sl], np.asarray(r0, float), float(crb_known[pi]), brng, n_boot)
                m.update({"position_nm": list(r0), "crb_axis_nm": float(crb_known[pi]),
                          "crb_axis_free_powers_nm": float(crb_freep[pi]),
                          "boundary_fraction": float(np.mean(np.asarray(res.on_boundary)[sl])),
                          "n_not_converged": int(np.sum(~np.asarray(res.converged)[sl]))})
                per_pos.append(m)
            case = {"N": int(N), "Nb_equivalent": Nb_equiv, "geometry": gname, "estimator": ename,
                    "n_loc_per_position": int(n_loc),
                    "max_bias_abs_nm": max(m["bias_abs"] for m in per_pos),
                    "mean_bias_abs_nm": float(np.mean([m["bias_abs"] for m in per_pos])),
                    "mean_rmse_2d_nm": float(np.mean([m["rmse_2d"] for m in per_pos])),
                    "mean_rmse_over_crb": float(np.mean([m["rmse_over_crb"] for m in per_pos])),
                    "max_rmse_over_crb": max(m["rmse_over_crb"] for m in per_pos),
                    "boundary_fraction": float(np.mean(res.on_boundary)),
                    "n_failed": int(res.n_failed),
                    "positions": per_pos}
            if ename == "honesto":
                pw = np.asarray(res.powers)
                case["powers_estimated_rel"] = (pw / pw[0]).tolist()
                case["powers_true_rel"] = (np.asarray(g["powers_true"]) / g["powers_true"][0]).tolist()
                case["globals_result"] = res.globals_result
            out.append(case)
            if verbose:
                print("N %5d %-11s %-8s max|b| %6.3f  <RMSE/CRB> %6.3f  borde %.3f"
                      % (N, gname, ename, case["max_bias_abs_nm"], case["mean_rmse_over_crb"],
                         case["boundary_fraction"]))
                sys.stdout.flush()
    return out, t_sim, t_est


def run(seed=20260928, n_loc=400, n_loc_sweep=200, n_boot=300, quick=False, out=DEFAULT_OUT,
        verbose=True):
    t_start = time.time()
    if quick:
        n_loc, n_loc_sweep, n_boot = min(n_loc, 60), min(n_loc_sweep, 40), min(n_boot, 50)
    pos_ideal = psf.beam_positions(4, L_IDEAL, center=True)
    pos_naive, L_eff, phi = ideal_like(POS_MEAS)
    geoms = {
        "ideal": {"pos_true": pos_ideal, "pos_naive": pos_ideal, "powers_true": np.ones(4)},
        "desalineada": {"pos_true": POS_MEAS, "pos_naive": pos_naive, "powers_true": POWERS},
    }
    C = mx.mixing_matrix(SETUP["tau"], SETUP["T"], SETUP["K"], SETUP["a"], SETUP["b"],
                         SETUP["irf_fwhm"])
    main_cases, ts1, te1 = run_block(NS + 95, n_loc, seed, geoms, C, n_boot, verbose)
    sweep, ts2, te2 = [], 0.0, 0.0
    for N in N_SWEEP:
        c, a_, b_ = run_block(N, n_loc_sweep, seed, geoms, C, n_boot, verbose)
        sweep.extend(c)
        ts2 += a_
        te2 += b_
    files = {k: _sha(os.path.join(ROOT, "src", "pminflux_sim", k + ".py"))
             for k in ("mixing", "psf", "estimate", "simulate", "windows")}
    files["study_misalignment_v2"] = _sha(os.path.abspath(__file__))

    def pick(cases, g, e):
        return [c for c in cases if c["geometry"] == g and c["estimator"] == e]

    summary = {}
    for g in geoms:
        for e in ("honesto", "honesto_P_conocidas", "ingenuo", "legado"):
            c = pick(main_cases, g, e)[0]
            summary["%s/%s" % (g, e)] = {
                "max_bias_abs_nm": c["max_bias_abs_nm"], "mean_rmse_2d_nm": c["mean_rmse_2d_nm"],
                "mean_rmse_over_crb": c["mean_rmse_over_crb"],
                "boundary_fraction": c["boundary_fraction"],
                "efficiency_mean_rmse_over_crb_by_N": {
                    str(s["N"]): s["mean_rmse_over_crb"] for s in pick(sweep, g, e)}}
    result = {
        "description": "Estudio de desalineación del EBP y de eficiencia con simulate + estimate v2 "
                       "en el setup medido (reemplazo de simulation_misalignment.py y del estudio de "
                       "eficiencia de la autora)",
        "setup": dict(SETUP, Ns=NS, sbr=SBR, N_main=NS + 95, bounds_radius_nm=R_SEARCH,
                      fwhm_nm=FWHM, psf_kind="donut (analítica)"),
        "assumptions": ASSUMPTIONS,
        "psf_20260820_available": False,
        "psf_note": "Las PSF medidas 20260820 no están en disco: se usa la dona analítica con los "
                    "centros y potencias del ajuste realista (%s)." % FIT_CSV,
        "N_convention": "N = Ns + Nb detectados en el ciclo completo (después de TCSPC y tiempo "
                        "muerto); SBR = Ns/Nb incidente = 21.05; CRB con N * fracción capturada",
        "crb_definition": "sigma_CRB por eje = sqrt(tr(F^-1)/2) del modelo de mezcla con fuga y "
                          "parámetros conocidos; RMSE/CRB = RMSE_2D/(sqrt2 sigma_CRB); también se "
                          "informa el CRB con potencias libres (crb_axis_free_powers_nm)",
        "reference": "sesgo y RMSE contra la posición SIMULADA (continua, fuera de grilla; F205)",
        "bootstrap": "SE = desvío de %d remuestras de las estimaciones; p16_p84 = percentiles "
                     "(sin suponer normalidad, F204); no incluye la variabilidad del ajuste global "
                     "de potencias" % n_boot,
        "geometry": {
            "ideal": {"beam_positions_nm": pos_ideal.tolist(), "L_nm": L_IDEAL,
                      "powers": [1.0] * 4},
            "desalineada": {"beam_positions_nm": POS_MEAS.tolist(), "powers": POWERS.tolist(),
                            "source": FIT_CSV + " (x0_nm, y0_nm, intensity_scale)",
                            "naive_positions_nm": pos_naive.tolist(), "naive_L_eff_nm": L_eff,
                            "naive_phi_rad": phi,
                            "beam_offsets_from_naive_nm": np.hypot(*(POS_MEAS - pos_naive).T).tolist()},
        },
        "estimators": {
            "honesto": "mle_mixing(C, centros verdaderos, free_powers=True; potencias estimadas en "
                       "conjunto sobre las 5 posiciones)",
            "honesto_P_conocidas": "mle_mixing(C, centros y potencias verdaderos): referencia con "
                                   "la calibración perfecta",
            "ingenuo": "mle_mixing(C, geometría ideal con L_eff y orientación del EBP medido, "
                       "potencias iguales)",
            "legado": "mle_legacy (Ec. 3.5, sin fuga, fondo 1/K) con centros y potencias verdaderos",
        },
        "positions_nm": [list(p) for p in POSITIONS],
        "n_loc_per_position": int(n_loc), "n_loc_per_position_sweep": int(n_loc_sweep),
        "n_boot": int(n_boot), "quick": bool(quick), "seed": int(seed),
        "seed_rule": "simulación: default_rng([seed, N, i_geometría, i_posición]); bootstrap: "
                     "[seed, N, i_geometría, i_posición, 1 + i_estimador]",
        "cases": main_cases,
        "efficiency_sweep": {"N": N_SWEEP, "cases": sweep},
        "summary": summary,
        "note_free_powers": NOTE_FREE_POWERS,
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__, "sha256": files},
        "command": " ".join(sys.argv),
        "runtime_s": {"total": time.time() - t_start, "simulation": ts1 + ts2,
                      "estimation": te1 + te2},
    }
    if out:
        d = os.path.dirname(out)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--n-loc", type=int, default=400)
    ap.add_argument("--n-loc-sweep", type=int, default=200)
    ap.add_argument("--n-boot", type=int, default=300)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    r = run(a.seed, a.n_loc, a.n_loc_sweep, a.n_boot, a.quick, a.out)
    print("runtime %.1f s -> %s" % (r["runtime_s"]["total"], a.out))


if __name__ == "__main__":
    main()
