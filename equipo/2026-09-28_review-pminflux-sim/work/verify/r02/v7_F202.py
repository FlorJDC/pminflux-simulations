# -*- coding: utf-8 -*-
"""(2c) F202 in v2: unequal beam powers. Own asymptotic + MC bias with equal-power model, with known
powers, and with free shared powers (own profile likelihood over 3 log-ratios, Nelder-Mead)."""
import sys, os, json, math
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mysim import my_C
from myest import qbeams, mle, asym_mle, T, K
A, B, TAU = 0.0, 10.1, 4.21
PW = np.array([21.02, 16.65, 22.96, 22.86])
PTS = [(5.0, -5.0), (-5.07, -7.56), (20.0, 0.0), (-15.0, 15.0), (0.0, -30.0)]
C = my_C(TAU, A, B, None); Ns, Nb = 2000, 95; sbr = Ns / Nb; beta = 1 / (sbr + 1)

def model(pw):
    pw = np.asarray(pw, float)
    def p(x, y):
        q = qbeams(x, y) * pw; q = q / q.sum(-1, keepdims=True)
        e = (1 - beta) * q.dot(C.T) + beta * B / T
        return e / e.sum(-1, keepdims=True)
    return p

rng = np.random.default_rng(20202)
n = 300
R0 = np.repeat(np.array(PTS), n, axis=0)
cnt = []
for r in PTS:
    pw_ = model(PW)(*r) * 0  # placeholder
    q = qbeams(*r) * PW; q /= q.sum()
    e = (Ns * C.dot(q) + Nb * B / T) / (Ns + Nb)
    cnt.append(rng.multinomial(Ns + Nb, np.r_[e, 1 - e.sum()], size=n)[:, :K])
cnt = np.vstack(cnt)
out = {}
out["asym_bias_equal_model"] = [float(np.hypot(*(asym_mle(model(PW)(*r), model(np.ones(4)), r) - r))) for r in PTS]
def perpos(x, y):
    return np.hypot(*(np.c_[x, y] - R0).reshape(5, n, 2).mean(1).T).tolist()
x, y, _ = mle(cnt, model(np.ones(4))); out["mc_bias_equal"] = perpos(x, y)
x, y, _ = mle(cnt, model(PW)); out["mc_bias_known"] = perpos(x, y)
def nll(lp):
    pw = np.r_[1.0, np.exp(lp)]
    pf = model(pw); x, y, _ = mle(cnt, pf, iters=25)
    return -np.sum(cnt * np.log(pf(x, y)))
res = minimize(nll, np.zeros(3), method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-3, maxiter=400))
pw_hat = np.r_[1.0, np.exp(res.x)]
x, y, _ = mle(cnt, model(pw_hat))
out["free_powers_ratio_hat"] = (pw_hat).tolist(); out["true_ratio"] = (PW / PW[0]).tolist()
out["free_powers_rel_err"] = (pw_hat / (PW / PW[0]) - 1).tolist()
out["mc_bias_free"] = perpos(x, y); out["nm_success"] = bool(res.success); out["nfev"] = int(res.nfev)
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(HERE, "v7_F202.json"), "w"), indent=1)
