# -*- coding: utf-8 -*-
import numpy as np
from scipy.optimize import minimize
from v_F104 import q, pn
T, K = 50.0, 4; TAUS = np.arange(K)*12.5; NG = 500000; tg = (np.arange(NG)+0.5)*T/NG
def E(r0, tau, wrap, a=-0.5, b=12.5, Ns=2000, Nb=95):
    qv = q(r0); dens = [np.exp(-np.mod(tg-TAUS[j], T)/tau)/tau/(1-np.exp(-T/tau)) for j in range(K)]
    out = np.zeros(K)
    for i in range(K):
        lo, hi = TAUS[i]+a, TAUS[i]+a+b
        m = (tg > lo) & (tg < hi)
        if wrap: m |= (tg > lo+T) & (tg < hi+T)
        out[i] = sum(Ns*qv[j]*dens[j][m].sum()*T/NG for j in range(K)) + Nb*m.sum()/NG
    return out
r0 = np.array([5.0, -5.0])
for tau in (4.21, 0.001):
    ests = []
    for wrap in (False, True):
        e = E(r0, tau, wrap); pt = e/e.sum()
        ests.append(minimize(lambda r: -np.sum(pt*np.log(pn(r, 2000/95))), r0, method='Nelder-Mead', options={'xatol':1e-8,'fatol':1e-15}).x)
    print(tau, "legacy", ests[0], "periodic", ests[1], "extra |d|", np.hypot(*(ests[0]-ests[1])), "bias legacy", np.hypot(*(ests[0]-r0)), "bias periodic", np.hypot(*(ests[1]-r0)))
