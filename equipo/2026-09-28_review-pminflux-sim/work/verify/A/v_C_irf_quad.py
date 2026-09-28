# -*- coding: utf-8 -*-
"""C with Gaussian IRF by 1-D quadrature over the IRF offset x (independent of the EMG closed form)."""
import numpy as np
from scipy.integrate import quad
T, K, tau, a, b = 50.0, 4, 4.21, 0.0, 10.1
s = 0.3/(2*np.sqrt(2*np.log(2)))
F = lambda t: 1-np.exp(-t/tau) if t > 0 else 0.0
def P_in(lo, hi):   # P(X mod T in (lo,hi)), X = x + E, x~N(0,s), E~Exp(tau); lo,hi in [0,T+..]
    def integrand(x):
        tot = 0.0
        for m in range(-2, 8):
            tot += F(hi + m*T - x) - F(lo + m*T - x)
        return tot*np.exp(-0.5*(x/s)**2)/(s*np.sqrt(2*np.pi))
    return quad(integrand, -12*s, 12*s, points=[0.0, lo, hi], limit=400, epsabs=1e-13, epsrel=1e-12)[0]
C = np.zeros((K, K))
for i in range(K):
    for j in range(K):
        off = ((i-j)*T/K) % T
        C[i, j] = P_in(off + a, off + a + b)
np.set_printoptions(precision=7)
print(C); print("colsum", C.sum(0))
