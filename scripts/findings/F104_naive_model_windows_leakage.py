# -*- coding: utf-8 -*-
"""F104 - pos_MINFLUX (l.1041) and crb_minflux (l.649-661) use Masullo's Eq. 3.5,
    p_i = SBR/(SBR+1) * lambda_i/sum(lambda) + 1/(SBR+1) * 1/K,   SBR = Ns/Nb,
and the comment at l.423-435 states that this is EXACTLY what sim_exp produces.  That is true
only if (1) the K windows tile the cycle (b = dt/K) and (2) there is no inter-pulse leakage
(Tlife << dt/K).  With the measured 20 MHz setup (tau = 4.21 ns, window [0, 10.1] ns) both fail:
  * inside the windows the background share is Nb*K*b/T, not Nb, and the signal is
    Ns * sum_ij C_ij q_j, so the effective SBR differs from Ns/Nb;
  * the signal is mixed between windows by C_ij (periodic mixing matrix).
The script computes the ASYMPTOTIC (noise-free) bias of the pos_MINFLUX model, i.e. the argmax
of sum_i E[n_i] ln p_i(r) with E[n] the exact expectation of sim_exp + nMINFLUX, and the
information loss (CRB of the true window model vs the CRB that crb_minflux reports).
A short sim_exp Monte-Carlo checks E[n] (chi2) so that the expectation is not an assumption.

Geometry: TCP beams(K=4, L=100, center=True), doughnut fwhm = 360 nm (module default).
Run: python scripts/findings/F104_naive_model_windows_leakage.py
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np
from scipy.optimize import minimize
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402

SEED = 104
K, L, DT = 4, 100.0, 50.0
POS = np.array([ts.beams(K, L, center=True, d='donut')[i] for i in range(K)], dtype=float)
TAU = np.arange(K) * DT / K


def q_at(r):
    lam = ts.doughnut(np.hypot(r[0] - POS[:, 0], r[1] - POS[:, 1]))
    return lam / lam.sum()


def mixing(tl, a, b, T=DT, nwrap=60):
    """C[i, j] = P(photon of beam j falls in window i), periodic, window i = [tau_i+a, tau_i+a+b]."""
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = ((i - j) * T / K) % T
            for m in range(nwrap):
                lo, hi = max(off + a + m * T, 0.0), max(off + a + b + m * T, 0.0)
                C[i, j] += np.exp(-lo / tl) - np.exp(-hi / tl)
    return C


def p_true(r, Ns, Nb, C, b, T=DT):
    """Exact window fractions of sim_exp + nMINFLUX (conditioned on the in-window total)."""
    En = Ns * C.dot(q_at(r)) + Nb * b / T
    return En / En.sum(), En.sum()


def p_naive(r, sbr):
    s = sbr / (sbr + 1.0)
    return s * q_at(r) + (1 - s) / K


def fisher(pfun, r, N, h=1e-3):
    g = []
    for d in (np.array([h, 0]), np.array([0, h])):
        g.append((pfun(r + d) - pfun(r - d)) / (2 * h))
    p = pfun(r)
    F = np.array([[np.sum(gi * gj / p) for gj in g] for gi in g]) * N
    return np.sqrt(0.5 * np.trace(np.linalg.inv(F)))


def asympt_bias(r0, Ns, Nb, tl, a, b):
    C = mixing(tl, a, b)
    pt, Nwin = p_true(r0, Ns, Nb, C, b)
    sbr = Ns / Nb
    f = lambda r: -np.sum(pt * np.log(p_naive(r, sbr)))
    est = minimize(f, r0, method='Nelder-Mead',
                   options={'xatol': 1e-7, 'fatol': 1e-14, 'maxiter': 4000}).x
    crb_naive = fisher(lambda r: p_naive(r, sbr), r0, Ns + Nb)          # what crb_minflux reports
    crb_true = fisher(lambda r: p_true(r, Ns, Nb, C, b)[0], r0, Nwin)   # information actually there
    sig_cap = Ns * C.dot(q_at(r0)).sum()
    return {"bias_vec_nm": (est - r0).tolist(), "bias_nm": float(np.hypot(*(est - r0))),
            "N_in_windows": float(Nwin), "SBR_nominal": sbr,
            "SBR_in_windows": float(sig_cap / (Nb * K * b / DT)),
            "window0_contamination_from_other_beams_pct":
                float(100 * Ns * (C[0].dot(q_at(r0)) - C[0, 0] * q_at(r0)[0]) / (Nwin * pt[0])),
            "crb_minflux_assumed_nm": float(crb_naive), "crb_true_model_nm": float(crb_true),
            "crb_ratio_true_over_assumed": float(crb_true / crb_naive)}


def mc_check(r0_nm, Ns, Nb, tl, a, b, n_calls, M_p=int(2e6)):
    """Chi2 of sim_exp+nMINFLUX counts against p_true, using a (4,1,1) PSF with the exact lambda.
    Low rate (M_p = 2e6 -> ~1e-3 photons/cycle) so that the F101 overwrite is negligible."""
    lam = ts.doughnut(np.hypot(r0_nm[0] - POS[:, 0], r0_nm[1] - POS[:, 1]))
    psf = lam.reshape(K, 1, 1)
    tot = np.zeros(K)
    for _ in range(n_calls):
        t, _, failed = ts.sim_exp('p_minflux', None, psf, (0, 0), Ns / Nb, Ns, Nb, M_p, tl, 1.05, DT)
        assert not failed
        tot += ts.nMINFLUX(K, TAU, t, a, b)
    C = mixing(tl, a, b)
    pt, _ = p_true(r0_nm, Ns, Nb, C, b)
    pn = p_naive(r0_nm, Ns / Nb)
    N = tot.sum()
    chi_t = np.sum((tot - N * pt) ** 2 / (N * pt)); chi_n = np.sum((tot - N * pn) ** 2 / (N * pn))
    return {"n_counted": int(N), "chi2_true_model": float(chi_t),
            "p_true_model": float(stats.chi2.sf(chi_t, K - 1)),
            "chi2_naive_model": float(chi_n), "p_naive_model": float(stats.chi2.sf(chi_n, K - 1))}


def main():
    np.random.seed(SEED)
    configs = {
        "study_Tlife0.001_a0_b12.5": (0.001, 0.0, 12.5),
        "window10.1_only_Tlife0.001": (0.001, 0.0, 10.1),
        "leak_only_Tlife4.21_b12.5": (4.21, 0.0, 12.5),
        "measured_setup_Tlife4.21_b10.1": (4.21, 0.0, 10.1),
    }
    points = {"(5,-5)": (5.0, -5.0), "(-5.07,-7.56)": (-5.07, -7.56),
              "(20,0)": (20.0, 0.0), "(-15,15)": (-15.0, 15.0), "(0,-30)": (0.0, -30.0)}
    sbrs = {"SBR21_Ns2000_Nb95": (2000, 95), "SBR6_Ns2000_Nb333": (2000, 333)}
    out = {"C_measured_setup": mixing(4.21, 0.0, 10.1).tolist(), "bias": {}}
    for sk, (Ns, Nb) in sbrs.items():
        for ck, (tl, a, b) in configs.items():
            for pk, r in points.items():
                out["bias"]["%s | %s | %s" % (sk, ck, pk)] = asympt_bias(np.array(r), Ns, Nb, tl, a, b)
    # Monte-Carlo check of the expectation used above (measured setup, point (5,-5))
    out["mc_check_measured_setup_(5,-5)_SBR21"] = mc_check(np.array([5.0, -5.0]), 2000, 95,
                                                             4.21, 0.0, 10.1, n_calls=150)
    out["mc_check_study_config_(5,-5)_SBR21"] = mc_check(np.array([5.0, -5.0]), 2000, 95,
                                                           0.001, 0.0, 12.5, n_calls=150)
    # cross-check: the continuous naive model equals pos_MINFLUX on the 1-nm grid
    PSF = np.array([ts.psf(POS[i], 400, 1, [0, 0], d='donut') for i in range(K)])
    C = mixing(4.21, 0.0, 10.1)
    pt, _ = p_true(np.array([5.0, -5.0]), 2000, 95, C, 10.1)
    idx = ts.pos_MINFLUX(1e7 * pt, PSF, 2000 / 95, px_nm=1, r_max_nm=75)
    out["grid_pos_MINFLUX_on_expected_counts_measured_setup_(5,-5)"] = \
        ts.indexToSpace(idx, 400, 1).tolist()
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=1))
