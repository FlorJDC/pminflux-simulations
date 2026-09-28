# -*- coding: utf-8 -*-
"""C19 independiente: parpadeo telegrafico vs exposiciones intercaladas (p-MINFLUX) y secuenciales."""
import numpy as np
from scipy.optimize import minimize
exec(open("v_c01_c03_c07_c16.py", encoding="utf-8").read().split("# ---------------- C01")[0])
rng = np.random.default_rng(12345)
s = SBR/(SBR+1)
def pmod(x, y):
    I = I_all(x, y); return s*I/I.sum() + (1-s)/K
def crb_at(r0, h=1e-4):
    x, y = r0; p = pmod(x, y)
    dx = (pmod(x+h, y)-pmod(x-h, y))/(2*h); dy = (pmod(x, y+h)-pmod(x, y-h))/(2*h)
    J = np.stack([dx, dy], 1); F = J.T @ (J/p[:, None]); return J, p, F, np.sqrt(np.trace(np.linalg.inv(F))/(2*N))
def on_intervals(T, ton, toff):
    # stationary start
    t = 0.0; on = rng.random() < ton/(ton+toff); iv = []
    while t < T:
        d = rng.exponential(ton if on else toff)
        if on: iv.append((t, min(t+d, T)))
        t += d; on = not on
    return np.array(iv) if iv else np.zeros((0, 2))
def w_interleaved(T, ton, toff, period=50.0):
    iv = on_intervals(T, ton, toff); tau = np.arange(K)*period/K
    if len(iv) == 0: return None
    a, b = iv[:, 0][:, None], iv[:, 1][:, None]
    n = np.ceil((b-tau)/period) - np.ceil((a-tau)/period)  # pulses t=n*period+tau in [a,b)
    return n.sum(0)
def w_sequential(ton, toff, texp=1e5, reps=1):
    T = K*texp*reps; iv = on_intervals(T, ton, toff); w = np.zeros(K)
    for r in range(reps):
        for i in range(K):
            s0, s1 = (r*K+i)*texp, (r*K+i+1)*texp
            for a, b in iv:
                w[i] += max(0.0, min(b, s1)-max(a, s0))
    return w
def sigma_fl(r0, wfun, nrep, nonlin=False):
    J, p, F, crb = crb_at(r0); ps = (p-(1-s)/K)/s; G = np.linalg.solve(F, (J/p[:, None]).T)
    d = []
    for _ in range(nrep):
        w = wfun()
        if w is None or np.sum(w*ps) <= 0: continue
        pp = s*(w*ps)/np.sum(w*ps) + (1-s)/K
        if nonlin:
            f = lambda v: -np.sum(pp*np.log(pmod(v[0], v[1])))
            res = minimize(f, r0, method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-14))
            d.append(res.x-np.array(r0))
        else:
            d.append(G @ (pp-p))
    d = np.array(d); sig = np.sqrt(np.mean(np.var(d, 0)))
    return sig, crb, len(d)
r0 = (5.0, -5.0)
T = 2e5*50.0
for ton in (1e5, 1e3):
    sig, crb, n = sigma_fl(r0, lambda: w_interleaved(T, ton, ton), 2000)
    print("p-MINFLUX interleaved t_on=t_off=%g ns: sigma_fl %.3e nm, CRB %.4f, ratio %.2e (n=%d)" % (ton, sig, crb, sig/crb, n))
for reps in (1, 25):
    sig, crb, n = sigma_fl(r0, lambda: w_sequential(1e5, 1e5, 1e5, reps), 4000)
    print("sequential 4x100us x%d reps: linear sigma_fl %.3f nm ratio %.2f (n=%d)" % (reps, sig, sig/crb, n))
    sig2, _, n2 = sigma_fl(r0, lambda: w_sequential(1e5, 1e5, 1e5, reps), 600, nonlin=True)
    print("   nonlinear (asymptotic MLE) sigma_fl %.3f nm ratio %.2f (n=%d)" % (sig2, sig2/crb, n2))
