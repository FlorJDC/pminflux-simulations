# -*- coding: utf-8 -*-
"""C03 detalle: fondo constante fisico (gradiente completo) vs SBR local congelada (metodo del worker)."""
import numpy as np
exec(open("v_c01_c03_c07_c16.py", encoding="utf-8").read().split("# ---------------- C01")[0])
S0 = I_all(0.0, 0.0).sum(); beta = S0/(K*SBR)
def pf_fixed(S):
    def f(x, y):
        I = I_all(x, y); s = S/(S+1); return s*I/I.sum() + (1-s)/K
    return f
def pconst(x, y):
    I = I_all(x, y); return (I+beta)/(I.sum()+K*beta)
def crb(pf, x, y, NN, h=1e-3):
    p = pf(x, y); dx = (pf(x+h, y)-pf(x-h, y))/(2*h); dy = (pf(x, y+h)-pf(x, y-h))/(2*h)
    F = np.array([[np.sum(dx*dx/p), np.sum(dx*dy/p)], [np.sum(dx*dy/p), np.sum(dy*dy/p)]])
    return np.sqrt(np.trace(np.linalg.inv(F))/(2*NN))
res_full, res_frozen = [], []
for rr in np.linspace(0.5, L/2, 60):
    for th in np.linspace(0, 2*np.pi, 181)[:-1]:
        x, y = rr*np.cos(th), rr*np.sin(th)
        Sr = I_all(x, y).sum()/S0; nb = Ns/(SBR*Sr); Nr = Ns+nb
        cf = crb(pf_fixed(SBR), x, y, N)
        res_full.append((crb(pconst, x, y, Nr)/cf, rr, np.degrees(th), Sr))
        res_frozen.append((crb(pf_fixed(SBR*Sr), x, y, Nr)/cf, rr, np.degrees(th), Sr))
for name, R in (("fisico (gradiente completo, N=Ns+Nb(r))", res_full), ("SBR local congelada (worker)", res_frozen)):
    a = np.array(R); i0, i1 = a[:, 0].argmin(), a[:, 0].argmax()
    print(name, ": min %.4f at r=%.1f th=%.0f S/S0=%.3f ; max %.4f at r=%.1f th=%.0f" % (a[i0,0], a[i0,1], a[i0,2], a[i0,3], a[i1,0], a[i1,1], a[i1,2]))
# worker's point set, physical model
for rad in (L/4, L/2, L):
    for ang in (90., 30., 270.):
        t = np.radians(ang); x, y = rad*np.cos(t), rad*np.sin(t)
        Sr = I_all(x, y).sum()/S0; Nr = Ns + Ns/(SBR*Sr)
        cf = crb(pf_fixed(SBR), x, y, N)
        print("|r|=%.1f @%3.0f  S/S0=%.3f  frozen %.3f  full %.3f" % (rad, ang, Sr, crb(pf_fixed(SBR*Sr), x, y, Nr)/cf, crb(pconst, x, y, Nr)/cf))
# absolute CRB values at worst point
a = np.array(res_full); i0 = a[:, 0].argmin(); t = np.radians(a[i0, 2]); x, y = a[i0, 1]*np.cos(t), a[i0, 1]*np.sin(t)
Sr = a[i0, 3]; print("worst point CRB fixed %.4f vs full %.4f nm" % (crb(pf_fixed(SBR), x, y, N), crb(pconst, x, y, Ns+Ns/(SBR*Sr))))
