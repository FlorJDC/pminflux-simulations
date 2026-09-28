# -*- coding: utf-8 -*-
"""F105 - sim_exp fixes EXACTLY Ns signal photons (random deletion, l.533-556) and EXACTLY Nb
background photons (l.559), so the window counts are n = Mult(Ns, q) + Mult(Nb, 1/K).
crb_minflux (and pos_MINFLUX) assume n ~ Mult(N, p) with p = s q + (1-s)/K, which is the law
of a real experiment (Poisson signal and background, conditioned on the total N).  Both laws
have the same mean, but the fixed split removes the binomial fluctuation of the signal/
background split: Cov_mult - Cov_fixed = N s (1-s) (q-u)(q-u)^T >= 0.  Hence the Monte-Carlo
sigma of the MLE obtained with sim_exp is SMALLER than what the same estimator gives on real
(Poisson) data, and RMSE/CRB computed from sim_exp is biased low.

Quantified two ways:
 (1) analytically: sandwich covariance A^-1 B A^-1 of the multinomial MLE, B = G^T Cov G;
 (2) Monte-Carlo with the continuous MLE of donutloc (independent reference) on counts drawn
     from both laws (40000 localizations each, seed fixed).
Geometry: TCP beams(K=4, L=100, center=True), doughnut fwhm = 360 nm.
Run: python scripts/findings/F105_fixed_Ns_Nb_vs_multinomial_crb.py
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "donut-beam-localization", "src"))
from tools import tools_simulations as ts  # noqa: E402
from donutloc import estimators  # noqa: E402

SEED = 105
K, L = 4, 100.0
POS = np.array([ts.beams(K, L, center=True, d='donut')[i] for i in range(K)], dtype=float)
U = np.full(K, 1.0 / K)


def q_fn(r):
    r = np.asarray(r, float)
    lam = ts.doughnut(np.hypot(r[..., 0, None] - POS[:, 0], r[..., 1, None] - POS[:, 1]))
    return lam / lam.sum(axis=-1, keepdims=True)


def make_p(sbr):
    s = sbr / (sbr + 1.0)
    return lambda r: s * q_fn(r) + (1 - s) / K


def sandwich(r0, Ns, Nb, h=1e-4):
    N = Ns + Nb
    p_fn = make_p(Ns / Nb)
    p = p_fn(r0)
    grad = np.stack([(p_fn(r0 + d) - p_fn(r0 - d)) / (2 * h)
                     for d in (np.array([h, 0.0]), np.array([0.0, h]))], axis=1)   # (K, 2)
    G = grad / p[:, None]
    A = N * grad.T.dot(G)                                   # Fisher of Mult(N, p)
    q = q_fn(r0)
    cov_mult = N * (np.diag(p) - np.outer(p, p))
    cov_fix = Ns * (np.diag(q) - np.outer(q, q)) + Nb * (np.diag(U) - np.outer(U, U))
    Ai = np.linalg.inv(A)
    V_mult = Ai.dot(G.T.dot(cov_mult).dot(G)).dot(Ai)       # == Ai
    V_fix = Ai.dot(G.T.dot(cov_fix).dot(G)).dot(Ai)
    s = lambda V: float(np.sqrt(0.5 * np.trace(V)))
    return {"crb_minflux_nm": s(Ai), "sigma_mle_mult_nm": s(V_mult),
            "sigma_mle_fixed_split_nm": s(V_fix),
            "ratio_fixed_over_crb": s(V_fix) / s(Ai)}


def mc(r0, Ns, Nb, n_rep, rng):
    p_fn = make_p(Ns / Nb)
    q, p = q_fn(r0), p_fn(r0)
    n_fix = rng.multinomial(Ns, q, size=n_rep) + rng.multinomial(Nb, U, size=n_rep)
    n_mul = rng.multinomial(Ns + Nb, p, size=n_rep)
    out = {}
    for key, n in (("fixed_split", n_fix), ("multinomial", n_mul)):
        est = estimators.mle(n, p_fn, search_radius=0.75 * L)
        err = est - r0
        sig = np.sqrt(0.5 * (np.var(err[:, 0]) + np.var(err[:, 1])))
        out["sigma_" + key + "_nm"] = float(sig)
        out["sigma_" + key + "_se_nm"] = float(sig / np.sqrt(2 * n_rep))
    out["ratio_fixed_over_multinomial"] = out["sigma_fixed_split_nm"] / out["sigma_multinomial_nm"]
    return out


def main():
    rng = np.random.default_rng(SEED)
    configs = {"study_misalignment_Ns2000_Nb95": (2000, 95),
               "study_example_Ns90_Nb10": (90, 10),
               "Edorna_SBR6_Ns2000_Nb333": (2000, 333),
               "low_SBR2_Ns1000_Nb500": (1000, 500)}
    points = {"(5,-5)": (5.0, -5.0), "(-5.07,-7.56)": (-5.07, -7.56), "(20,0)": (20.0, 0.0)}
    out = {"analytic": {}, "mc": {}}
    for ck, (Ns, Nb) in configs.items():
        for pk, r in points.items():
            out["analytic"]["%s | %s" % (ck, pk)] = sandwich(np.array(r), Ns, Nb)
    for ck in ("study_misalignment_Ns2000_Nb95", "low_SBR2_Ns1000_Nb500"):
        Ns, Nb = configs[ck]
        out["mc"][ck + " | (5,-5)"] = mc(np.array([5.0, -5.0]), Ns, Nb, 40000, rng)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
