# -*- coding: utf-8 -*-
"""(1b) Free shared beam powers: own profile likelihood (outer Nelder-Mead over 3 log power ratios,
inner per-localization MLE with own grid+Newton). Multinomial window counts from own mixing model
(misaligned EBP, true powers). Usage: python v2_freepowers.py N nloc seed [geom]"""
import os, sys, json, time, math
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "r02"))
from myest import mle
from vgeo import T, K, POS_MEAS, POWERS, POSITIONS, ring, model_mix, my_C

A, B, TAU, IRF = 0.0, 10.1, 4.21, 0.3
SBR = 2000 / 95.
C = my_C(TAU, A, B, IRF)
N, nloc, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
geom = sys.argv[4] if len(sys.argv) > 4 else "desalineada"
pos, pw = (POS_MEAS, POWERS) if geom == "desalineada" else (ring(100.0), np.ones(4))
rng = np.random.default_rng(seed)
beta = 1 / (SBR + 1)
cnt, R0 = [], []
ptrue = model_mix(pos, pw, C, B, SBR)
for r0 in POSITIONS:
    e = ptrue(*r0)  # normalized over windows
    capt = (1 - beta) * C.sum(0).mean() + beta * K * B / T
    full = np.r_[e * capt, 1 - capt]
    cnt.append(rng.multinomial(N, full, size=nloc)[:, :K]); R0.append(np.repeat([r0], nloc, 0))
cnt = np.vstack(cnt); R0 = np.vstack(R0)
true_rel = pw / pw[0]


def nll(lp, ret=False):
    p = np.r_[1.0, np.exp(lp)]
    pf = model_mix(pos, p, C, B, SBR)
    x, y, onb = mle(cnt, pf, grid=1.5, iters=30)
    v = -np.sum(cnt * np.log(pf(x, y)))
    return (v, x, y, onb) if ret else v


t0 = time.time()
x0 = np.log(true_rel[1:])            # start at the truth (favours the truth, if anything)
res = minimize(nll, x0, method="Nelder-Mead", options=dict(xatol=2e-4, fatol=1e-3, maxiter=600))
v_hat, x, y, onb = nll(res.x, True)
v_true = nll(np.log(true_rel[1:]))
d = np.c_[x, y] - R0
bias = [float(np.hypot(*d[i * nloc:(i + 1) * nloc].mean(0))) for i in range(len(POSITIONS))]
out = dict(N=N, nloc=nloc, seed=seed, geom=geom, hat=np.r_[1, np.exp(res.x)].tolist(),
           true=true_rel.tolist(), nll_hat=float(v_hat), nll_true=float(v_true),
           dnll_true_minus_hat=float(v_true - v_hat), nfev=int(res.nfev), success=bool(res.success),
           edge=float(onb.mean()), max_bias=max(bias), bias=bias, runtime=time.time() - t0)
print(json.dumps(out))
with open(os.path.join(HERE, "v2_fp_%s_N%d_n%d_s%d.json" % (geom, N, nloc, seed)), "w") as fh:
    json.dump(out, fh, indent=1)
