# -*- coding: utf-8 -*-
"""(1b') bigger two-sample test my-sim vs simulate.py at 0.0105/cycle for d in {0, 35, 75} (4e7 photons each)."""
import sys, os, json
import numpy as np
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src"))
from mysim import stream, counts_periodic, my_C, my_probs, chi2p, my_lam
from pminflux_sim import simulate as sm
T, K, TAU, A, B, IRF = 50.0, 4, 4.21, 0.0, 10.1, 0.3
lam = my_lam(5.0, -5.0); NS, NB = 2000.0, 95.0; SBR = NS / NB
C = my_C(TAU, A, B, IRF); p_id = my_probs(lam, C, B, NS, NB)
cap = (NS * C.dot(lam) + NB * B / T).sum(); se_loc = np.sqrt(p_id * (1 - p_id) / cap)
rate = 0.0105; out = []
rng = np.random.default_rng(777)
for d in [0.0, 35.0, 75.0]:
    o = np.zeros(K)
    for rep in range(4):
        st = stream(lam, SBR, rate, int(1e7 / rate), rng, irf=IRF, d=d)
        o += counts_periodic(st["micro"], A, B)
    P = sm.SimParams(tau=TAU, irf_fwhm=IRF, a=A, b=B, rate_per_cycle=rate, dead_time=d)
    o2 = np.zeros(K)
    for rep in range(4):
        o2 += sm.simulate_counts(lam, 5000, 2095, SBR, P, np.random.default_rng([int(d), rep, 5])).sum(0)
    c, p2s, _, _ = stats.chi2_contingency(np.vstack([o, o2]), correction=False)
    f, f2 = o / o.sum(), o2 / o2.sum()
    row = dict(d=d, mine=((f - p_id) / se_loc).round(4).tolist(), v2=((f2 - p_id) / se_loc).round(4).tolist(),
               mc_se=float(np.sqrt(f[1] * (1 - f[1]) / o.sum()) / se_loc[1]), two_sample_p=p2s,
               n=[int(o.sum()), int(o2.sum())])
    out.append(row); print(json.dumps(row))
json.dump(out, open(os.path.join(HERE, "v2b_twosample.json"), "w"), indent=1)
