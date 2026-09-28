# -*- coding: utf-8 -*-
"""(1c) N=100, 1600 locs/pos (seed 6 data of v2_freepowers): profile NLL at truth, at W1's reported
point, and at my NM optimum; plus NM restarts from W1's point and from equal powers."""
import os, sys, json
import numpy as np
from scipy.optimize import minimize
sys.argv = [sys.argv[0], "100", "1600", "6"]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "v2_freepowers.py"), encoding="utf-8").read().split("t0 = time.time()")[0]
exec(compile(src, "v2_freepowers_head", "exec"))
pts = {"truth": true_rel, "W1_N100_1600": np.array([1, 1.056, 1.408, 1.536]),
       "mine_NM": np.array([1, 3.002, 3.969, 8.859]), "equal": np.ones(4),
       "W1_N100_100_runaway": np.array([1, 3.0, 3.9, 9.3])}
out = {k: float(nll(np.log(v[1:]))) for k, v in pts.items()}
print(out)
for start in ("W1_N100_1600", "equal"):
    r = minimize(nll, np.log(pts[start][1:]), method="Nelder-Mead", options=dict(xatol=2e-4, fatol=1e-3, maxiter=600))
    out["NM_from_" + start] = dict(hat=np.r_[1, np.exp(r.x)].tolist(), nll=float(r.fun))
    print(start, out["NM_from_" + start])
json.dump(out, open(os.path.join(HERE, "v2b_fp_eval.json"), "w"), indent=1)
