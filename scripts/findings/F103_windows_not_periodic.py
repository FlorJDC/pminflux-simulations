# -*- coding: utf-8 -*-
"""F103 - nMINFLUX (tools_simulations.py l.966-999) uses plain intervals (tau_i + a, tau_i + a + b)
on microtimes that live in [0, dt): windows are neither wrapped modulo the period nor checked
for overlap.  Two scenarios (zeros of empty cycles removed first, relTime[relTime > 0], as
simulations_example.py l.157 does, so that F102 does not mask this effect):

 S1 (window opening before the pulse, a = -0.5 ns, b = dt/K = 12.5 ns): the correct periodic
    window 0 is [49.5, 50) U [0, 12); nMINFLUX drops [49.5, 50).  Counts are compared with a
    periodic counter on the SAME microtimes, and the asymptotic (noise-free) bias of
    pos_MINFLUX's model is computed.
 S2 (b > dt/K, overlapping windows, b = 13 ns): photons in the overlap are counted twice and
    sum(n) exceeds the number of photons; no error or warning is raised.

Physics: TCP beams(K=4, L=100), doughnut fwhm = 360, emitter (5, -5) nm, Ns = 2000, Nb = 95,
M_p = 2e5, dt = 50 ns, Tlife = 4.21 ns (measured, 20260707) and 0.001 ns (author's studies).
Run: python scripts/findings/F103_windows_not_periodic.py
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np
from scipy.optimize import minimize

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402

SEED = 103
K, L, SIZE, PX, DT = 4, 100.0, 400.0, 1.0, 50.0
NS, NB, MP, FACTOR = 2000, 95, int(2e5), 1.05
R0_NM = np.array([5.0, -5.0])
POS = np.array([ts.beams(K, L, center=True, d='donut')[i] for i in range(K)], dtype=float)


def lam_at(r):
    return ts.doughnut(np.hypot(r[0] - POS[:, 0], r[1] - POS[:, 1]))


def count_periodic(t, tau, a, b, T):
    """Periodic window counter: window i = {t : (t - tau_i - a) mod T in [0, b)}."""
    return np.array([np.sum(np.mod(t - tau[i] - a, T) < b) for i in range(len(tau))])


def frac_folded_in(lo, hi, tau_j, tl, T, nwrap=60):
    """P(folded microtime of a beam-j photon lies in [lo, hi]) with 0 <= lo < hi <= T.
    sim_exp model: t = tau_j + Exp(tl), then t mod T."""
    F = lambda x: 1.0 - np.exp(-np.maximum(x, 0.0) / tl)
    return sum(F(hi + m * T - tau_j) - F(lo + m * T - tau_j) for m in range(nwrap))


def expected_counts(r, tl, intervals, T=DT):
    """E[n_i] under sim_exp physics for window i = union of intervals[i] (each inside [0, T))."""
    q = lam_at(r); q = q / q.sum()
    tau = np.arange(K) * T / K
    En = np.zeros(K)
    for i, ivs in enumerate(intervals):
        for lo, hi in ivs:
            En[i] += NS * sum(q[j] * frac_folded_in(lo, hi, tau[j], tl, T) for j in range(K))
            En[i] += NB * (hi - lo) / T
    return En


def naive_p(r, sbr):
    q = lam_at(r); q = q / q.sum()
    s = sbr / (sbr + 1.0)
    return s * q + (1 - s) / K


def asympt_estimate(En, sbr, r_start):
    f = lambda r: -np.sum(En * np.log(naive_p(r, sbr)))
    return minimize(f, r_start, method='Nelder-Mead',
                    options={'xatol': 1e-6, 'fatol': 1e-12, 'maxiter': 4000}).x


def main():
    np.random.seed(SEED)
    PSF = np.array([ts.psf(POS[i], SIZE, PX, [0, 0], d='donut') for i in range(K)])
    r0 = ts.spaceToIndex(R0_NM, SIZE, PX)
    tau = np.arange(K) * DT / K
    sbr = NS / NB
    out = {}
    # ---- S1: a < 0, MC on sim_exp microtimes
    a, b = -0.5, DT / K
    for tl in (4.21, 0.001):
        nl, npd = np.zeros(K), np.zeros(K)
        for _ in range(30):
            t, _, failed = ts.sim_exp('p_minflux', None, PSF, r0, sbr, NS, NB, MP, tl, FACTOR, DT)
            assert not failed
            t = t[t > 0]
            nl += ts.nMINFLUX(K, tau, t, a, b)
            npd += count_periodic(t, tau, a, b, DT)
        # analytic expectations, legacy windows vs periodic windows
        leg = [[(max(tau[i] + a, 0.0), min(tau[i] + a + b, DT))] for i in range(K)]
        per = [[(0.0, tau[0] + a + b), (DT + a, DT)]] + leg[1:]
        E_leg, E_per = expected_counts(R0_NM, tl, leg), expected_counts(R0_NM, tl, per)
        est_leg = asympt_estimate(E_leg, sbr, R0_NM)
        est_per = asympt_estimate(E_per, sbr, R0_NM)
        out["S1_a-0.5_b12.5_Tlife%g" % tl] = {
            "mc_counts_nMINFLUX_per_call": (nl / 30).tolist(),
            "mc_counts_periodic_per_call": (npd / 30).tolist(),
            "mc_lost_from_window0_pct": float(100 * (npd[0] - nl[0]) / npd[0]),
            "E_counts_legacy": E_leg.tolist(), "E_counts_periodic": E_per.tolist(),
            "bkg_share_window0_legacy_vs_others": [(tau[0] + a + b) / DT, b / DT],
            "asympt_estimate_legacy_windows_nm": est_leg.tolist(),
            "asympt_estimate_periodic_windows_nm": est_per.tolist(),
            "extra_bias_from_no_wrap_nm": float(np.hypot(*(est_leg - est_per))),
        }
    # ---- S2: overlapping windows b = 13 > dt/K
    b2 = 13.0
    for tl in (4.21, 0.001):
        tot_n, tot_ph = 0.0, 0
        for _ in range(10):
            t, _, failed = ts.sim_exp('p_minflux', None, PSF, r0, sbr, NS, NB, MP, tl, FACTOR, DT)
            t = t[t > 0]
            tot_n += ts.nMINFLUX(K, tau, t, 0.0, b2).sum()
            tot_ph += t.size
        out["S2_a0_b13_Tlife%g" % tl] = {
            "sum_counts_over_windows": tot_n / 10, "photons_in_cycle": tot_ph / 10,
            "double_counted_pct": float(100 * (tot_n - tot_ph) / tot_ph)}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
