# -*- coding: utf-8 -*-
"""(1c) 'highest' (sim_exp emulation) and 'earliest' d=0 at high rate: own emulation vs simulate.py
vs the R1-verified predictor mixing.sim_exp_window_probs."""
import sys, os, json
import numpy as np
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src"))
from mysim import stream, counts_periodic, chi2p
from pminflux_sim import mixing as mx
from pminflux_sim import simulate as sm
T, K = 50.0, 4
LAM4 = np.array([.4, .1, .2, .3])
out = []
rng = np.random.default_rng(31337)
def pred(rule, rate, tau, irf, b=10.1):
    Mp = 1e7
    return mx.sim_exp_window_probs(LAM4, 1.0, 0.0, rate * Mp, Mp, tau, T, K, 0.0, b, rule=rule, irf_fwhm=irf)
for (tc, rate, tau, irf) in [("highest", 0.3, 4.21, 0.3), ("highest", 0.3, 4.21, 0.0), ("earliest", 0.3, 1.5, 0.0),
                             ("earliest", 0.2, 1.0, 0.0), ("earliest", 0.1, 4.21, 0.0), ("earliest", 0.02, 4.21, 0.0)]:
    ncyc = int(4e6 / rate)
    st = stream(LAM4, np.inf, rate, ncyc, rng, tau=tau, irf=irf, d=0.0, tcspc=tc)
    o = counts_periodic(st["micro"], 0.0, 10.1)
    P = sm.SimParams(tau=tau, irf_fwhm=irf, rate_per_cycle=rate, dead_time=0.0, tcspc=tc)
    o2 = sm.simulate_counts(LAM4, int(o.sum() / 1600), 2000, np.inf, P, np.random.default_rng(int(rate * 1000) + int(tau * 10))).sum(0)
    row = dict(tc=tc, rate=rate, tau=tau, irf=irf, n=[int(o.sum()), int(o2.sum())])
    for rule in ("highest", "earliest", "ideal"):
        pr = pred(rule, rate, tau, irf)
        row["mine_p_" + rule] = chi2p(o, pr)[1]
        row["v2_p_" + rule] = chi2p(o2, pr)[1]
    row["mine_minus_pred_%s" % tc] = (o / o.sum() - pred(tc, rate, tau, irf)).round(5).tolist()
    row["v2_minus_pred_%s" % tc] = (o2 / o2.sum() - pred(tc, rate, tau, irf)).round(5).tolist()
    row["two_sample_p"] = stats.chi2_contingency(np.vstack([o, o2]), correction=False)[1]
    out.append(row); print(json.dumps(row))
json.dump(out, open(os.path.join(HERE, "v3_highrate.json"), "w"), indent=1)
