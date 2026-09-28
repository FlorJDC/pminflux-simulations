# -*- coding: utf-8 -*-
"""(1a) low-rate + periodic windows: own simulator vs own mixing model; simulate.py as the claim."""
import sys, os, json, time
import numpy as np
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src"))
from mysim import stream, counts_periodic, my_C, my_probs, naive, chi2p, my_lam
from pminflux_sim import mixing as mx          # only to cross-check my own C
from pminflux_sim import simulate as sm        # the CLAIM under test

out = {}
lam = my_lam(5.0, -5.0)
SBR = 2000 / 95.0
# my C vs mixing (sanity only)
for irf in (None, 0.3):
    for (a, b) in [(0, 10.1), (-0.5, 10.1), (2, 12), (-1.5, 12.5)]:
        d = np.abs(my_C(4.21, a, b, irf) - mx.mixing_matrix(4.21, 50, 4, a, b, irf)).max()
        print("C diff irf", irf, (a, b), "%.2e" % d)

def two_sample(o1, o2):
    tab = np.vstack([o1, o2]).astype(float)
    c, p, _, _ = stats.chi2_contingency(tab, correction=False)
    return c, p

cases = [("earliest", 0.3, 0.0, 10.1, 22.0, lam), ("earliest", 0.0, 0.0, 10.1, 22.0, lam),
         ("none", 0.3, 0.0, 10.1, 22.0, np.array([.4, .1, .2, .3])),
         ("earliest", 0.3, -0.5, 10.1, 22.0, lam), ("earliest", 0.3, 2.0, 12.0, 22.0, lam),
         ("earliest", 0.3, -1.5, 12.5, 22.0, lam)]
rng = np.random.default_rng(90210)
for k, (tc, irf, a, b, d, q) in enumerate(cases):
    t0 = time.time()
    s = stream(q, SBR, 1e-3, int(1.6e9), rng, irf=irf, d=d, tcspc=tc)
    o = counts_periodic(s["micro"], a, b)
    C = my_C(4.21, a, b, irf)
    pm = my_probs(q, C, b, 2000.0, 95.0)
    cm, pvm, z = chi2p(o, pm)
    cn, pvn, _ = chi2p(o, naive(q, SBR))
    # the claim: simulate.py, same config, same photon budget
    P = sm.SimParams(tau=4.21, irf_fwhm=irf, a=a, b=b, rate_per_cycle=1e-3, dead_time=d, tcspc=tc)
    nloc = int(round(s["micro"].size / 2095))
    o2 = sm.simulate_counts(q, nloc, 2095, SBR, P, np.random.default_rng(1000 + k)).sum(0)
    c2, pv2, z2 = chi2p(o2, pm)
    cts, pts = two_sample(o, o2)
    row = dict(case=[tc, irf, a, b, d], mine_photons=int(o.sum()), mine_p_mix=pvm, mine_z=z.tolist(),
               mine_chi2_naive=cn, mine_p_naive=pvn, v2_photons=int(o2.sum()), v2_p_mix=pv2,
               v2_z=z2.tolist(), two_sample_p=pts, sec=time.time() - t0)
    out[str(k)] = row
    print(json.dumps(row))
json.dump(out, open(os.path.join(HERE, "v1_lowrate.json"), "w"), indent=1)
