# -*- coding: utf-8 -*-
"""Independent F104: asymptotic bias of the Eq.3.5 (naive) MLE when the data follow the window/leakage
model, and CRB(true window model, N_in_windows) vs CRB(naive, N=Ns+Nb) as crb_minflux is called."""
import numpy as np, json
from scipy.optimize import minimize
T, K = 50.0, 4
FW = 360.0; L = 100.0
ang = 2*np.pi*np.arange(1, 4)/3
POS = np.vstack([[0, 0], np.c_[L/2*np.cos(ang), L/2*np.sin(ang)]])   # TCP K=4 (beams(center=True))
def donut(r): u = 4*np.log(2)*r**2/FW**2; return u*np.exp(-u)
def q(r):
    lam = donut(np.hypot(r[0]-POS[:, 0], r[1]-POS[:, 1])); return lam/lam.sum()
def Cmat(tau, a, b):
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = ((i-j)*T/K) % T; lo, hi = off+a, off+a+b
            # numerical: sum images m=0..40 (independent of the geometric closed form)
            m = np.arange(0, 60)
            C[i, j] = np.sum(np.exp(-(lo+m*T)/tau) - np.exp(-(hi+m*T)/tau))
    return C
def En(r, Ns, Nb, C, b): return Ns*C.dot(q(r)) + Nb*b/T
def pn(r, s): return s/(s+1)*q(r) + 1/(s+1)/K
def fisher_crb(pf, r, N, h=1e-4):
    p = pf(r); g = [(pf(r+d)-pf(r-d))/(2*h) for d in (np.array([h, 0.]), np.array([0., h]))]
    F = N*np.array([[np.sum(gi*gj/p) for gj in g] for gi in g])
    return np.sqrt(np.trace(np.linalg.inv(F))/2)
pts = [(5, -5), (-5.07, -7.56), (20, 0), (-15, 15), (0, -30)]
cfg = {"study": (0.001, 0, 12.5), "b10.1_noleak": (0.001, 0, 10.1), "leak_b12.5": (4.21, 0, 12.5), "measured": (4.21, 0, 10.1)}
out = {}
for Ns, Nb in ([(2000, 95), (2000, 333)] if __name__ == "__main__" else []):
    s = Ns/Nb
    for cn, (tl, a, b) in cfg.items():
        C = Cmat(tl, a, b)
        for r0 in pts:
            r0 = np.array(r0, float); E = En(r0, Ns, Nb, C, b); Nw = E.sum(); pt = E/Nw
            f = lambda r: -np.sum(pt*np.log(pn(r, s)))
            best = None
            for st in [r0, r0+[3, 3], r0-[3, 3]]:
                res = minimize(f, st, method='BFGS', options={'gtol': 1e-12})
                if best is None or res.fun < best.fun: best = res
            bias = best.x - r0
            crb_naive = fisher_crb(lambda r: pn(r, s), r0, Ns+Nb)
            crb_true = fisher_crb(lambda r: En(r, Ns, Nb, C, b)/En(r, Ns, Nb, C, b).sum(), r0, Nw)
            sig_in = Ns*C.dot(q(r0)).sum(); bkg_in = Nb*K*b/T
            cont0 = Ns*(C[0].dot(q(r0)) - C[0, 0]*q(r0)[0])/E[0]
            key = "Ns%d_Nb%d|%s|(%g,%g)" % (Ns, Nb, cn, r0[0], r0[1])
            out[key] = dict(bias_nm=float(np.hypot(*bias)), bias_vec=bias.tolist(), crb_naive=crb_naive, crb_true=crb_true,
                            ratio=crb_true/crb_naive, bias_over_crb_true=float(np.hypot(*bias))/crb_true,
                            bias_over_crb_naive=float(np.hypot(*bias))/crb_naive,
                            SBR_in=sig_in/bkg_in, cont0_pct=100*cont0, Nw=Nw)
            print("%-40s bias %.3f nm  crb_naive %.3f crb_true %.3f ratio %.4f  b/crbN %.2f b/crbT %.2f SBRin %.2f cont0 %.1f%%" % (
                key, np.hypot(*bias), crb_naive, crb_true, crb_true/crb_naive, np.hypot(*bias)/crb_naive, np.hypot(*bias)/crb_true, sig_in/bkg_in, 100*cont0))
if __name__ == "__main__":
    json.dump(out, open("v_F104.json", "w"), indent=1)
