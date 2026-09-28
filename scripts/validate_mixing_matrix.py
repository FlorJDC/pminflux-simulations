# -*- coding: utf-8 -*-
"""Validación de la matriz de mezcla de fuga C_ij contra ``sim_exp`` del legado.

Escribe ``results/mixing_validation.json`` (formato del test de aceptación + extras) y
``results/mixing_rate_sweep.json`` (barrido de tasa: sobrescritura por ciclo de sim_exp).

Uso (desde la raíz del proyecto):
    python scripts/validate_mixing_matrix.py              # todo (~15-25 min con 4 procesos)
    python scripts/validate_mixing_matrix.py --only main  # solo la validación principal
    python scripts/validate_mixing_matrix.py --quick      # corrida corta de humo (no escribe results/)

El legado se importa en solo lectura (``legacy/p-minflux-main``); usa el RNG global de numpy, así
que cada tramo ("chunk") de llamadas se siembra con ``np.random.seed(semilla_base + id)``. El
resultado no depende de la cantidad de procesos.
"""

import argparse
import contextlib
import io
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))

from pminflux_sim import mixing as mx  # noqa: E402

# ------------------------------- configuración de referencia --------------------------------
K = 4
T_NS = 50.0                       # 20 MHz
TAU_NS = 4.21                     # medido en los datos 20260707
A_NS = 0.0
B_NS = 10.1
TAU_I = np.arange(K) * T_NS / K   # [0, 12.5, 25, 37.5]
LAM = np.array([0.12, 0.28, 0.35, 0.25])   # posición fuera del centro, ventana 0 débil
SBR = 10.0
CALLS_PER_CHUNK = 20


def _chunk(args):
    """Corre ``ncalls`` llamadas a sim_exp y devuelve los conteos por ventana acumulados."""
    (seed, ncalls, Ns, Nb, M_p, tlife, factor, dt, a, b, lam) = args
    from tools import tools_simulations as ts
    np.random.seed(seed)
    psf = np.asarray(lam, dtype=float).reshape(K, 1, 1)
    tot = np.zeros(K)
    per_call_chi2 = []
    fails = 0
    probs_mix = mx.window_probs(lam, mx.mixing_matrix(tlife, dt, K, a, b), b, dt, Ns=Ns, Nb=Nb)
    for _ in range(ncalls):
        with contextlib.redirect_stdout(io.StringIO()):
            rel, _abs, failed = ts.sim_exp('p_minflux', None, psf, (0, 0), SBR, Ns, Nb, M_p,
                                           tlife, factor, dt)
        if failed:
            fails += 1
            continue
        n = ts.nMINFLUX(K, np.arange(K) * dt / K, rel, a, b)
        tot += n
        per_call_chi2.append(mx.pearson_chi2(n, probs_mix)[0])
    return tot, per_call_chi2, fails, ncalls - fails


def run_block(tag, seed0, n_target, Ns, Nb, M_p, factor, tlife=TAU_NS, dt=T_NS, a=A_NS,
              b=B_NS, lam=LAM, procs=4):
    """Llamadas a sim_exp hasta juntar >= n_target fotones dentro de las ventanas."""
    C = mx.mixing_matrix(tlife, dt, K, a, b)
    per_call = Ns * float(C.dot(LAM / LAM.sum()).sum()) + Nb * K * b / dt
    ncalls = int(np.ceil(1.03 * n_target / per_call))
    nchunks = int(np.ceil(ncalls / float(CALLS_PER_CHUNK)))
    jobs = [(seed0 + c, CALLS_PER_CHUNK, Ns, Nb, M_p, tlife, factor, dt, a, b, lam)
            for c in range(nchunks)]
    t0 = time.time()
    with Pool(procs) as pool:
        res = pool.map(_chunk, jobs, chunksize=1)
    counts = sum(r[0] for r in res)
    chi_calls = [x for r in res for x in r[1]]
    fails = sum(r[2] for r in res)
    ok = sum(r[3] for r in res)
    el = time.time() - t0
    print("[%s] %d llamadas (%d fallidas), %d fotones en ventanas, %.0f s"
          % (tag, ok + fails, fails, counts.sum(), el), flush=True)
    return {
        "counts": counts, "n_calls_ok": ok, "n_calls_failed": fails,
        "per_call_chi2_mean": float(np.mean(chi_calls)) if chi_calls else float("nan"),
        "per_call_chi2_var": float(np.var(chi_calls)) if chi_calls else float("nan"),
        "per_call_ks_pvalue": (float(stats.kstest(stats.chi2.sf(chi_calls, K - 1),
                                                  "uniform").pvalue) if chi_calls else None),
        "runtime_s": el, "seed_base": seed0, "n_chunks": nchunks,
        "calls_per_chunk": CALLS_PER_CHUNK,
    }


def _compare(counts, probs):
    chi2, dof, p, dev = mx.pearson_chi2(counts, probs)
    return {"chi2": chi2, "dof": dof, "pvalue": p, "dev_se": dev.tolist(),
            "expected_frac": (probs / probs.sum()).tolist()}


def _detect_lambda(alpha=1e-3, power=0.5, dof=K - 1):
    """No-centralidad del chi^2 que da la potencia pedida al nivel alpha."""
    from scipy.optimize import brentq
    crit = stats.chi2.isf(alpha, dof)
    return brentq(lambda l: stats.ncx2.sf(crit, dof, l) - power, 1e-6, 1e4)


def main_validation(n_target, procs, seed=20260928):
    Ns, Nb = 2000, 200                  # SBR = 10
    M_p = 2200000                       # (Ns+Nb)/M_p = 1.0e-3 fotones/ciclo
    factor = 1.05
    C = mx.mixing_matrix(TAU_NS, T_NS, K, A_NS, B_NS)
    Ci = mx.mixing_matrix(TAU_NS, T_NS, K, A_NS, B_NS, irf_fwhm=0.3)
    p_mix = mx.window_probs(LAM, C, B_NS, T_NS, Ns=Ns, Nb=Nb)
    p_naive = mx.naive_probs(LAM, Ns / float(Nb))
    p_hi = mx.sim_exp_window_probs(LAM, Ns, Nb, Ns * factor, M_p, TAU_NS, T_NS, K, A_NS, B_NS,
                                   rule="highest")

    r = run_block("principal", seed, n_target, Ns, Nb, M_p, factor, procs=procs)
    cnt = r["counts"]
    N = cnt.sum()
    obs = cnt / N
    se = np.sqrt(obs * (1 - obs) / N)
    cm, cn, ch = _compare(cnt, p_mix), _compare(cnt, p_naive), _compare(cnt, p_hi)

    # variante sin fondo
    p_mix0 = mx.window_probs(LAM, C, B_NS, T_NS, Ns=Ns, Nb=0)
    r0 = run_block("sin fondo", seed + 100000, max(n_target // 2, 10 ** 6), Ns, 0, M_p, factor,
                   procs=procs)
    c0 = r0["counts"]
    cm0 = _compare(c0, p_mix0)
    cn0 = _compare(c0, mx.naive_probs(LAM, float("inf")))

    out = {
        "params": {"K": K, "T_ns": T_NS, "tau_ns": TAU_NS, "window_start_ns": A_NS,
                   "window_width_ns": B_NS},
        "C_no_irf": C.tolist(),
        "n_detected_total": int(N),
        "rate_per_cycle": (Ns + Nb) / float(M_p),
        "chi2_pvalue_mixing_vs_sim_exp": cm["pvalue"],
        "chi2_pvalue_naive_vs_sim_exp": cn["pvalue"],
        # ------------------------------ extras ------------------------------
        "definitions": {
            "C": "C[i][j] = P(foton del haz j en la ventana i), periodico, sin IRF",
            "rate_per_cycle": "(Ns+Nb)/M_p de cada llamada (fotones detectados por ciclo TCSPC)",
            "n_detected_total": "suma sobre llamadas de fotones dentro de las K ventanas (nMINFLUX)",
            "mixing_model": "p_i ~ Ns*sum_j C_ij lam_j/sum(lam) + Nb*b/T, normalizado en ventanas",
            "naive_model": "pos_MINFLUX/crb_minflux: SBR/(SBR+1) lam_i/sum(lam) + 1/(SBR+1)/K",
            "chi2": "Pearson, K-1 = 3 g.l., condicionado al total en ventanas, conteos sumados",
            "dev_se": "(n_obs - n_esp)/sqrt(N p (1-p)) por ventana",
            "sim_exp_highest_model": "prediccion exacta a tasa finita de sim_exp "
                                     "(recorte por ranura + gana el haz de k mas alto)",
        },
        "sim_exp_call": {"key": "p_minflux", "psf": "pila sintetica (4,1,1) = lam", "r0": [0, 0],
                         "SBR": SBR, "Ns": Ns, "Nb": Nb, "M_p": M_p, "Tlife": TAU_NS,
                         "factor": factor, "dt": T_NS, "nMINFLUX_tau": TAU_I.tolist(),
                         "a": A_NS, "b": B_NS},
        "lam": LAM.tolist(),
        "C_irf_300ps_fwhm": Ci.tolist(),
        "C_column_sums": C.sum(axis=0).tolist(),
        "counts_observed": cnt.tolist(),
        "frac_observed": obs.tolist(),
        "frac_observed_se": se.tolist(),
        "frac_mixing": p_mix.tolist(),
        "frac_naive": p_naive.tolist(),
        "frac_sim_exp_highest_model": p_hi.tolist(),
        "dev_se_mixing": cm["dev_se"],
        "dev_se_naive": cn["dev_se"],
        "chi2_mixing": cm["chi2"],
        "chi2_naive": cn["chi2"],
        "chi2_pvalue_sim_exp_highest_model": ch["pvalue"],
        "window0_contamination": {
            "desc": "fraccion de los fotones de la ventana 0 que no vienen del haz 0 "
                    "(fuga de otros haces + fondo), segun el modelo de mezcla",
            "leak_from_other_beams": float(Ns * (C[0, 1:] * LAM[1:] / LAM.sum()).sum()
                                           / (Ns * C[0].dot(LAM / LAM.sum()) + Nb * B_NS / T_NS)),
            "background": float(Nb * B_NS / T_NS
                                / (Ns * C[0].dot(LAM / LAM.sum()) + Nb * B_NS / T_NS)),
            "observed_frac_w0_minus_naive_in_se": cn["dev_se"][0],
        },
        "variant_Nb0": {
            "Nb": 0, "n_detected_total": int(c0.sum()), "counts_observed": c0.tolist(),
            "frac_observed": (c0 / c0.sum()).tolist(), "frac_mixing": p_mix0.tolist(),
            "chi2_pvalue_mixing": cm0["pvalue"], "dev_se_mixing": cm0["dev_se"],
            "chi2_pvalue_naive": cn0["pvalue"], "dev_se_naive": cn0["dev_se"],
            "n_calls_ok": r0["n_calls_ok"], "n_calls_failed": r0["n_calls_failed"],
            "per_call_chi2_mean": r0["per_call_chi2_mean"], "runtime_s": r0["runtime_s"],
            "seed_base": r0["seed_base"],
        },
        "n_calls_ok": r["n_calls_ok"], "n_calls_failed": r["n_calls_failed"],
        "per_call_chi2_mean_vs_mixing": r["per_call_chi2_mean"],
        "per_call_chi2_var_vs_mixing": r["per_call_chi2_var"],
        "per_call_pvalue_ks_uniform": r["per_call_ks_pvalue"],
        "seed_base": seed, "calls_per_chunk": CALLS_PER_CHUNK, "runtime_s": r["runtime_s"],
        "script": "scripts/validate_mixing_matrix.py",
    }
    return out


def rate_sweep(procs, seed=20260929, scale=1.0):
    Ns, Nb = 2000, 200
    lam_detect = _detect_lambda()
    plan = [  # (tasa nominal (Ns+Nb)/M_p, fotones objetivo en ventanas)
        (1e-3, 2e6), (3e-3, 2e6), (1e-2, 4e6), (3e-2, 2e6), (1e-1, 1e6), (3e-1, 1e6)]
    rows = []
    for idx, (rate, ntar) in enumerate(plan):
        M_p = int(round((Ns + Nb) / rate))
        s = Ns / float(M_p)
        # factor mínimo para que haya >= Ns ciclos ocupados, con 10 % de margen
        factor = max(1.05, 1.10 * (-np.log1p(-s)) / s)
        rows.append(_sweep_point("rate=%g" % rate, seed + 1000 * idx, int(ntar * scale), Ns, Nb,
                                 M_p, factor, TAU_NS, B_NS, lam_detect, procs))
    # configuración exacta de los estudios de la autora (simulation_misalignment.py)
    Ns_s, Nb_s, M_s, f_s = 2000, 95, 200000, 1.05
    studies = {
        "desc": "Ns=2000, Nb=95, M_p=2e5, factor=1.05 (Nh=2100 -> 0.0105 fotones/ciclo), dt=50",
        "with_leak_tau4.21_b10.1": _sweep_point("estudios tau=4.21", seed + 50000,
                                                int(4e7 * scale), Ns_s, Nb_s, M_s, f_s, TAU_NS,
                                                B_NS, lam_detect, procs),
        # la configuración literal de los estudios (Tlife=0.001, b=dt/K): solo predicción,
        # con C = identidad el único efecto es el de la etiqueta de haz
        "as_in_studies_tau0.001_b12.5": _predict_only(Ns_s, Nb_s, M_s, f_s, 0.001, T_NS / K,
                                                      lam_detect),
    }
    return {
        "desc": "Barrido de tasa de sim_exp: recorte 1/ranura + sobrescritura 'gana k mas alto' "
                "(sim_exp) frente a 'gana el mas temprano' (TCSPC real) y al modelo de mezcla "
                "(tasa -> 0). Ns=2000, Nb=200 (SBR=10), lam=%s, tau=4.21, a=0, b=10.1, T=50."
                % LAM.tolist(),
        "detect_noncentrality_alpha1e-3_power0.5": lam_detect,
        "points": rows,
        "studies_config": studies,
        "script": "scripts/validate_mixing_matrix.py",
    }


def _predict(Ns, Nb, M_p, factor, tlife, b, lam_detect, N=None):
    Nh = int(Ns * factor)
    C = mx.mixing_matrix(tlife, T_NS, K, A_NS, b)
    p_mix = mx.window_probs(LAM, C, b, T_NS, Ns=Ns, Nb=Nb)
    p_hi, det = mx.sim_exp_window_probs(LAM, Ns, Nb, Nh, M_p, tlife, T_NS, K, A_NS, b,
                                        rule="highest", return_details=True)
    p_ea = mx.sim_exp_window_probs(LAM, Ns, Nb, Nh, M_p, tlife, T_NS, K, A_NS, b,
                                   rule="earliest")
    out = {"Ns": Ns, "Nb": Nb, "M_p": M_p, "factor": factor, "Nh": Nh, "Tlife": tlife, "b": b,
           "rate_per_cycle": (Ns + Nb) / float(M_p),
           "raw_rate_per_cycle_Nh_over_Mp": Nh / float(M_p),
           "p_cycle_occupied": det["p_cycle_occupied"],
           "frac_all_cycles_with_ge2_beams": det["p_cycle_occupied"]
           * det["frac_occupied_cycles_with_ge2_beams"],
           "frac_occupied_cycles_with_ge2_beams": det["frac_occupied_cycles_with_ge2_beams"],
           "frac_mixing": p_mix.tolist(), "frac_pred_highest": p_hi.tolist(),
           "frac_pred_earliest": p_ea.tolist()}
    for nm, pp in (("highest", p_hi), ("earliest", p_ea)):
        lam1 = float(np.sum((pp - p_mix) ** 2 / p_mix))    # no-centralidad por fotón
        out["pred_%s_minus_mixing_abs" % nm] = (pp - p_mix).tolist()
        out["N_to_detect_%s_vs_mixing" % nm] = lam_detect / lam1 if lam1 > 0 else None
        if N:
            se = np.sqrt(p_mix * (1 - p_mix) / N)
            out["pred_%s_minus_mixing_in_se" % nm] = ((pp - p_mix) / se).tolist()
    se1 = np.sqrt(p_mix * (1 - p_mix) / 2000.0)
    out["pred_highest_minus_mixing_in_se_per_2000ph_localization"] = ((p_hi - p_mix) / se1).tolist()
    out["pred_highest_minus_earliest_abs"] = (p_hi - p_ea).tolist()
    return out, p_mix, p_hi, p_ea


def _predict_only(Ns, Nb, M_p, factor, tlife, b, lam_detect):
    return _predict(Ns, Nb, M_p, factor, tlife, b, lam_detect)[0]


def _sweep_point(tag, seed, ntar, Ns, Nb, M_p, factor, tlife, b, lam_detect, procs):
    r = run_block(tag, seed, ntar, Ns, Nb, M_p, factor, tlife=tlife, b=b, procs=procs)
    cnt = r["counts"]
    N = cnt.sum()
    out, p_mix, p_hi, p_ea = _predict(Ns, Nb, M_p, factor, tlife, b, lam_detect, N=N)
    cm, ch, ce = _compare(cnt, p_mix), _compare(cnt, p_hi), _compare(cnt, p_ea)
    out.update({
        "n_detected_total": int(N), "counts_observed": cnt.tolist(),
        "frac_observed": (cnt / N).tolist(),
        "chi2_pvalue_mixing": cm["pvalue"], "dev_se_mixing": cm["dev_se"],
        "chi2_pvalue_pred_highest": ch["pvalue"], "dev_se_pred_highest": ch["dev_se"],
        "chi2_pvalue_pred_earliest": ce["pvalue"], "dev_se_pred_earliest": ce["dev_se"],
        "n_calls_ok": r["n_calls_ok"], "n_calls_failed": r["n_calls_failed"],
        "per_call_chi2_mean_vs_mixing": r["per_call_chi2_mean"],
        "seed_base": seed, "runtime_s": r["runtime_s"],
    })
    return out


def nb0_replica(procs, seed=20460928, n_target=2 * 10 ** 6):
    """Réplica de ``variant_Nb0`` con otra semilla (R3: la original dio p = 0.0078).

    Mismo setup que la variante sin fondo de ``main_validation`` (Ns = 2000, Nb = 0,
    M_p = 2.2e6, factor 1.05, tau 4.21, [0, 10.1]); se compara contra la mezcla (tasa -> 0) y
    contra la predicción exacta a tasa finita de sim_exp (``sim_exp_window_probs``, 'highest').
    """
    Ns, Nb, M_p, factor = 2000, 0, 2200000, 1.05
    C = mx.mixing_matrix(TAU_NS, T_NS, K, A_NS, B_NS)
    p_mix0 = mx.window_probs(LAM, C, B_NS, T_NS, Ns=Ns, Nb=0)
    p_hi0 = mx.sim_exp_window_probs(LAM, Ns, Nb, Ns * factor, M_p, TAU_NS, T_NS, K, A_NS, B_NS,
                                    rule="highest")
    r0 = run_block("sin fondo, replica", seed, n_target, Ns, Nb, M_p, factor, procs=procs)
    c0 = r0["counts"]
    cm0, ch0 = _compare(c0, p_mix0), _compare(c0, p_hi0)
    cn0 = _compare(c0, mx.naive_probs(LAM, float("inf")))
    return {
        "desc": "replica de variant_Nb0 con otra semilla base (mismo setup); no reemplaza a las "
                "claves de aceptacion",
        "Nb": 0, "Ns": Ns, "M_p": M_p, "factor": factor,
        "n_detected_total": int(c0.sum()), "counts_observed": c0.tolist(),
        "frac_observed": (c0 / c0.sum()).tolist(), "frac_mixing": p_mix0.tolist(),
        "frac_sim_exp_highest_model": p_hi0.tolist(),
        "chi2_mixing": cm0["chi2"], "chi2_pvalue_mixing": cm0["pvalue"],
        "dev_se_mixing": cm0["dev_se"],
        "chi2_pvalue_sim_exp_highest_model": ch0["pvalue"],
        "dev_se_sim_exp_highest_model": ch0["dev_se"],
        "chi2_pvalue_naive": cn0["pvalue"], "dev_se_naive": cn0["dev_se"],
        "n_calls_ok": r0["n_calls_ok"], "n_calls_failed": r0["n_calls_failed"],
        "per_call_chi2_mean": r0["per_call_chi2_mean"], "runtime_s": r0["runtime_s"],
        "seed_base": r0["seed_base"], "script": "scripts/validate_mixing_matrix.py --only nb0-replica",
    }


def _dump(obj, name):
    path = os.path.join(ROOT, "results", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
    print("escrito", path, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["main", "sweep", "nb0-replica"], default=None)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--n-main", type=float, default=2e6)
    ap.add_argument("--quick", action="store_true", help="humo: pocas llamadas, no escribe")
    args = ap.parse_args()
    if args.quick:
        v = main_validation(20000, args.procs)
        print(json.dumps({k: v[k] for k in ("n_detected_total", "rate_per_cycle",
                                            "chi2_pvalue_mixing_vs_sim_exp",
                                            "chi2_pvalue_naive_vs_sim_exp")}, indent=1))
        return
    if args.only == "nb0-replica":
        # agrega results/mixing_validation.json:variant_Nb0_replica sin tocar las demás claves
        path = os.path.join(ROOT, "results", "mixing_validation.json")
        with open(path, encoding="utf-8") as fh:
            prev = json.load(fh)
        prev["variant_Nb0_replica"] = nb0_replica(args.procs)
        _dump(prev, "mixing_validation.json")
        return
    if args.only in (None, "main"):
        _dump(main_validation(int(args.n_main), args.procs), "mixing_validation.json")
    if args.only in (None, "sweep"):
        _dump(rate_sweep(args.procs), "mixing_rate_sweep.json")


if __name__ == "__main__":
    main()
