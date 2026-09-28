# -*- coding: utf-8 -*-
"""Independent C: fold binned arrival-time masses onto the period (no closed-form series),
with and without Gaussian IRF (300 ps FWHM, centred on the pulse).  Also direct MC."""
import numpy as np, json
from scipy.signal import fftconvolve
T, K, tau, a, b = 50.0, 4, 4.21, 0.0, 10.1
h = 1/800.0                       # bin width; 12.5 ns = 10000 bins, 10.1 = 8080 bins
nT = int(round(T/h)); sh = nT//K; nb = int(round(b/h))
def folded(irf):
    edges = np.arange(-4.0, 300.0 + h/2, h)       # exact bin masses of Exp(tau)
    cdf = np.where(edges > 0, 1-np.exp(-np.clip(edges, 0, None)/tau), 0.0)
    m = np.diff(cdf)
    if irf:
        s = irf/(2*np.sqrt(2*np.log(2))); kx = np.arange(-10*s, 10*s + h/2, h)
        g = np.exp(-0.5*(kx/s)**2); g /= g.sum()
        m = fftconvolve(m, g, mode='same')
    start = np.round(edges[:-1]/h).astype(int)     # bin index on absolute line
    return np.bincount(np.mod(start, nT), weights=m, minlength=nT)
def C_of(d):
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            dj = np.roll(d, j*sh)                    # pulse j at phase j*12.5
            s0 = i*sh + int(round(a/h))
            idx = np.mod(np.arange(s0, s0+nb), nT)
            C[i, j] = dj[idx].sum()
    return C
out = {}
for name, fw in [("no_irf", None), ("irf300", 0.3)]:
    d = folded(fw); C = C_of(d); out[name] = C.tolist()
    print(name, "mass", d.sum()); print(np.array2string(C, precision=7)); print("colsum", C.sum(0))
# direct MC of the no-IRF and IRF cases (beam 0 only, circulant)
rng = np.random.default_rng(7); n = 20_000_000
for name, fw in [("no_irf", None), ("irf300", 0.3)]:
    x = rng.exponential(tau, n)
    if fw: x = x + rng.normal(0, fw/2.3548200450309493, n)
    ph = np.mod(x, T)
    c = [np.mean((ph > i*12.5+a) & (ph < i*12.5+a+b)) for i in range(K)]
    print("MC", name, "C[i][0] =", np.round(c, 6), "+-", np.round(np.sqrt(np.array(c)*(1-np.array(c))/n), 6))
    out["MC_"+name+"_col0"] = c
print("closed Cii", (1-np.exp(-b/tau))/(1-np.exp(-T/tau)))
json.dump(out, open("v_C.json", "w"), indent=1)
