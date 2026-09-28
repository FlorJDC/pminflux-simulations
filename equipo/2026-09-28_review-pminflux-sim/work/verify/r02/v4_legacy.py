# -*- coding: utf-8 -*-
"""(1d) F102/F103 legacy counting: exact expectations (own quadrature) + own MC + simulate.py (claim)."""
import sys, os, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src"))
from mysim import stream, my_lam
from pminflux_sim import simulate as sm
T, K = 50.0, 4; dt = T / K
lam = my_lam(5.0, -5.0); SBR = 2000 / 95.0; fs = SBR / (SBR + 1)

def mass(tau, intervals):
    """expected fraction of all photons with microtime in union of [lo,hi) subsets of [0,T)."""
    tot = 0.0
    for lo, hi in intervals:
        for j in range(K):
            s = 0.0
            for m in range(-2, 200):
                l, h = lo - j * dt + m * T, hi - j * dt + m * T
                F = lambda x: 1 - math.exp(-x / tau) if x > 0 else 0.0
                s += F(h) - F(l)
            tot += fs * lam[j] * s
        tot += (1 - fs) * (hi - lo) / T
    return tot

out = {}
for tau in (4.21, 0.001):
    dbl = mass(tau, [(12.5, 13), (25, 25.5), (37.5, 38)])
    loss = mass(tau, [(49.5, 50)]) / mass(tau, [(49.5, 50), (0, 12)])
    out[str(tau)] = dict(double_expected=dbl, loss_w0_expected=loss)
    # own MC (tcspc none, like the test)
    rng = np.random.default_rng(int(tau * 1000) + 3)
    st = stream(lam, SBR, 0.0105, int(1.0e8), rng, tau=tau, irf=0.0, d=0.0, tcspc="none")
    m = st["micro"]
    ins = lambda lo, hi: (m > lo) & (m < hi)
    cnt = sum(ins(i * dt, i * dt + 13).sum() for i in range(K))
    dbl_mc = cnt / m.size - 1
    per0 = (ins(-1, 12) | (m >= 49.5)).sum(); leg0 = ins(-0.5, 12).sum()
    out[str(tau)].update(double_mc=dbl_mc, double_mc_se=math.sqrt(dbl_mc * (1 - dbl_mc) / m.size),
                         loss_mc=1 - leg0 / per0, n=int(m.size))
    print(tau, out[str(tau)])
# F102 via simulate (claim): zeros per loc with 'highest', 0.0105, a=-0.25, b=12.5
p = sm.SimParams(tcspc="highest", rate_per_cycle=0.0105, irf_fwhm=0.0, b=12.5, a=-0.25, counting="legacy")
c = sm.simulate_counts(lam, 100, 2095, SBR, p, np.random.default_rng(5))
x = 0.0105 * fs
rec = (1 - math.exp(-x)) + 0.0105 * (1 - fs)
exp_zeros = 2095 / rec - 2095 * (1 - math.exp(-x)) / rec
out["F102"] = dict(v2_window0_frac=float(c[:, 0].sum() / c.sum()), v2_w0_per_loc=float(c[:, 0].mean()),
                   expected_zeros_per_loc=exp_zeros)
print(out["F102"])
json.dump(out, open(os.path.join(HERE, "v4_legacy.json"), "w"), indent=1)
