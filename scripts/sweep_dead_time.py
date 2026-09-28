# -*- coding: utf-8 -*-
"""Barrido de tiempo muerto x tasa: sesgo por ventana del simulador v2 contra la mezcla ideal.

Setup: T = 50, K = 4, tau = 4.21, ventana [0, 10.1], IRF 0.3 ns, SBR 21 (Ns = 2000, Nb = 95),
lambda de la posición (5, -5) nm de F104 (TCP K = 4, L = 100, dona fwhm 360).
Casos: tcspc='earliest' con dead_time en {0, 22, 50, 100} ns (22 ns = SUPUESTO, SPAD típico)
y, como "antes", tcspc='highest' (emulación de sim_exp, F101; sin tiempo muerto).
Sesgo = fracción simulada - window_probs (mezcla ideal, tasa -> 0), en unidades del SE por
localización de 2000 fotones de señal (N = 2095 detectados): SE_i = sqrt(p_i (1 - p_i) / N_w).
Uso: python scripts/sweep_dead_time.py [--n-loc 3000] [--seed 20260928]
"""

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pminflux_sim import mixing as mx  # noqa: E402
from pminflux_sim import simulate as sm  # noqa: E402

T, K, TAU, A, B, IRF = 50.0, 4, 4.21, 0.0, 10.1, 0.3
NS, NB = 2000, 95
N = NS + NB
SBR = NS / float(NB)
DEAD = [0.0, 22.0, 50.0, 100.0]
RATES = [1e-3, 2.5e-3, 5.5e-3, 0.0105]


def lam_at(x, y, fwhm=360.0, L=100.0):
    ang = 2 * np.pi * np.arange(1, 4) / 3
    pos = np.vstack([[0.0, 0.0], np.c_[L / 2 * np.cos(ang), L / 2 * np.sin(ang)]])
    u = 4 * np.log(2) * ((x - pos[:, 0]) ** 2 + (y - pos[:, 1]) ** 2) / fwhm ** 2
    lam = u * np.exp(-u)
    return lam / lam.sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-loc", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "dead_time_sweep.json"))
    args = ap.parse_args()
    lam = lam_at(5.0, -5.0)
    C = mx.mixing_matrix(TAU, T, K, A, B, IRF)
    p_ideal = mx.window_probs(lam, C, B, T, Ns=float(NS), Nb=float(NB))
    capture = float(mx.window_expected(lam, C, B, T, NS, NB).sum())      # fotones en ventanas / loc
    se_loc = np.sqrt(p_ideal * (1 - p_ideal) / capture)
    ss = np.random.SeedSequence(args.seed)
    cases = [("highest", 0.0, r) for r in RATES] + [("earliest", d, r) for d in DEAD for r in RATES]
    seeds = ss.spawn(len(cases))
    rows = []
    t_all = time.time()
    for (tcspc, d, r), sq in zip(cases, seeds):
        p = sm.SimParams(T=T, K=K, tau=TAU, irf_fwhm=IRF, a=A, b=B, rate_per_cycle=r,
                         dead_time=d, tcspc=tcspc)
        t0 = time.time()
        c = sm.simulate_counts(lam, args.n_loc, N, SBR, p, np.random.default_rng(sq))
        el = time.time() - t0
        o = c.sum(axis=0).astype(float)
        f = o / o.sum()
        mc_se = np.sqrt(f * (1 - f) / o.sum())
        bias = f - p_ideal
        chi2, dof, pv, _ = mx.pearson_chi2(o, p_ideal)
        row = {"tcspc": tcspc, "dead_time_ns": d, "rate_per_cycle": r,
               "photons_in_windows": int(o.sum()), "frac": f.tolist(),
               "bias_frac": bias.tolist(), "mc_se_frac": mc_se.tolist(),
               "bias_in_SE_per_loc": (bias / se_loc).tolist(),
               "max_abs_bias_SE_per_loc": float(np.max(np.abs(bias / se_loc))),
               "mc_se_in_SE_per_loc": (mc_se / se_loc).tolist(),
               "chi2_vs_ideal": chi2, "p_vs_ideal": pv, "seconds": el}
        if tcspc == "highest":
            M = 1e7
            ph = mx.sim_exp_window_probs(lam, NS, NB, r * SBR / (SBR + 1) * M, M, TAU, T, K, A, B,
                                         rule="highest", irf_fwhm=IRF)
            row["predicted_bias_highest_SE_per_loc"] = ((ph - p_ideal) / se_loc).tolist()
        rows.append(row)
        print("%-8s d=%5.1f r=%.4f  bias/SE_loc=%s  (MC SE %.3f)  p=%.3g  %.1fs" % (
            tcspc, d, r, np.round(bias / se_loc, 3), np.max(mc_se / se_loc), pv, el))
    out = {
        "description": "Sesgo por ventana del simulador v2 frente a la mezcla ideal (window_probs), "
                       "en SE por localizacion de 2000 fotones de senal",
        "assumptions": [sm.DEAD_TIME_ASSUMPTION,
                        "IRF gaussiana 300 ps FWHM centrada en el pulso",
                        "tiempo muerto no paralizable + TCSPC primer foton por ciclo de llegada",
                        "'highest' = emulacion de sim_exp (F101), sin tiempo muerto"],
        "params": {"T": T, "K": K, "tau": TAU, "a": A, "b": B, "irf_fwhm": IRF, "Ns": NS, "Nb": NB,
                   "N_detected": N, "sbr": SBR, "position_nm": [5.0, -5.0],
                   "lambda": lam.tolist(), "n_loc_per_case": args.n_loc, "seed": args.seed,
                   "dead_times_ns": DEAD, "rates_per_cycle": RATES},
        "p_ideal": p_ideal.tolist(), "photons_in_windows_per_loc": capture,
        "se_per_loc_frac": se_loc.tolist(),
        "rows": rows, "total_seconds": time.time() - t_all,
        "numpy": np.__version__,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("escrito", args.out, "%.0f s" % out["total_seconds"])


if __name__ == "__main__":
    main()
