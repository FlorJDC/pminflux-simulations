# -*- coding: utf-8 -*-
"""(1b) dead-time sweep: first-order analytic predictor + own MC + simulate.py (claim).
Theory: non-paralyzable SPAD, Poisson input with periodic intensity lam(t).
  d >= T : recorded density rho(t) = lam(t) * (1 - int_{t-d}^{t} r(s) ds) EXACTLY (at most one
           avalanche in any window of length d; r = avalanche rate). For d = nT the integral is
           n * (avalanches per period) = const  ->  rho proportional to lam: zero bias at ALL rates.
  d <  T : first order  rho(t) ~ lam(t) * (1 - int_{min(cT, t-d)}^{t} lam)  (alive + first in cycle).
"""
import sys, os, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src"))
from mysim import stream, counts_periodic, my_C, my_probs, chi2p, my_lam, FW2S
from scipy import stats
from pminflux_sim import simulate as sm        # claim

T, K, TAU, A, B, IRF = 50.0, 4, 4.21, 0.0, 10.1, 0.3
lam = my_lam(5.0, -5.0); NS, NB = 2000.0, 95.0; SBR = NS / NB
C = my_C(TAU, A, B, IRF); p_id = my_probs(lam, C, B, NS, NB)
cap = (NS * C.dot(lam) + NB * B / T).sum()
se_loc = np.sqrt(p_id * (1 - p_id) / cap)

# periodic intensity on a fine grid (photons per ns per unit rate)
M = 20000; h = T / M; tg = (np.arange(M) + 0.5) * h
s = IRF * FW2S
dens0 = np.zeros(M)
for m in range(-2, 40):                                   # folded EMG density of beam 0
    dens0 += stats.exponnorm.pdf(tg + m * T, TAU / s, scale=s)
def lam_t(rate):
    fs = SBR / (SBR + 1)
    sig = sum(lam[j] * np.roll(dens0, int(round(j * T / K / h))) for j in range(K))
    return rate * (fs * sig / (sig.sum() * h) + (1 - fs) / T)   # integrates to rate per cycle

def predicted(rate, d):
    L = lam_t(rate)
    cum = np.concatenate([[0], np.cumsum(np.tile(L, 4) * h)])   # 4 periods
    idx = np.arange(M) + 3 * M                                  # t in last period (index of t)
    nd = int(round(d / h))
    if d >= T:
        blk = cum[idx] - cum[idx - nd]
    else:
        back = np.maximum(np.arange(M), nd)                    # max(phase, d) in bins
        blk = cum[idx] - cum[idx - back]
    rho = L * (1 - blk)
    ph = tg
    o = np.array([rho[np.mod(ph - (i * T / K + A), T) < B].sum() for i in range(K)])
    f = o / o.sum()
    return (f - p_id) / se_loc

out = {"se_loc": se_loc.tolist(), "p_ideal": p_id.tolist(), "rows": []}
rng = np.random.default_rng(4242)
for rate, dlist in [(0.0105, [0, 22, 35, 50, 62.5, 75, 100]), (2.5e-3, [0, 22, 50, 100]), (1e-3, [22])]:
    for d in dlist:
        t0 = time.time()
        ncyc = int(1.2e7 / rate)
        st = stream(lam, SBR, rate, ncyc, rng, irf=IRF, d=float(d), tcspc="earliest")
        o = counts_periodic(st["micro"], A, B)
        f = o / o.sum(); mcse = np.sqrt(f * (1 - f) / o.sum()) / se_loc
        c, pv, _ = chi2p(o, p_id)
        pr = predicted(rate, d)
        # claim: simulate.py
        P = sm.SimParams(tau=TAU, irf_fwhm=IRF, a=A, b=B, rate_per_cycle=rate, dead_time=float(d))
        nloc = int(o.sum() / 1970)
        o2 = sm.simulate_counts(lam, nloc, 2095, SBR, P, np.random.default_rng(int(d * 10) + int(rate * 1e5))).sum(0)
        f2 = o2 / o2.sum(); c2, pv2, _ = chi2p(o2, p_id)
        row = dict(rate=rate, d=d, mine_bias_SE=((f - p_id) / se_loc).round(4).tolist(), mine_p=pv,
                   mc_se=float(mcse.max()), pred_first_order=pr.round(4).tolist(),
                   v2_bias_SE=((f2 - p_id) / se_loc).round(4).tolist(), v2_p=pv2,
                   photons=int(o.sum()), v2_photons=int(o2.sum()), sec=round(time.time() - t0, 1))
        out["rows"].append(row); print(json.dumps(row))
json.dump(out, open(os.path.join(HERE, "v2_deadtime.json"), "w"), indent=1)
