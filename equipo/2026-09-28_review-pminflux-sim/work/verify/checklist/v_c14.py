# -*- coding: utf-8 -*-
"""C14 independiente: sesgo asintotico del MLE continuo con fwhm del estimador != fwhm de los datos."""
import numpy as np
from scipy.optimize import minimize
exec(open("v_c01_c03_c07_c16.py", encoding="utf-8").read().split("# ---------------- C01")[0])
s = SBR/(SBR+1)
def p(x, y, fw):
    I = I_all(x, y, fwhm=fw); return s*I/I.sum() + (1-s)/K
def bias(r0, fw_true, fw_model):
    pt = p(r0[0], r0[1], fw_true)
    f = lambda v: -np.sum(pt*np.log(p(v[0], v[1], fw_model)))
    res = minimize(f, r0, method="Nelder-Mead", options=dict(xatol=1e-7, fatol=1e-15, maxiter=5000))
    return np.hypot(*(res.x-np.array(r0)))
pts = [(5,-5), (-5,-8), (-5.07,-7.56), (10,0), (0,10), (-10,0), (0,-10), (20,0), (0,20), (14,14), (-20,-10), (30,0), (0,-30)]
for ft, fm, lab in [(343.9, 360, "datos 343.9 / est 360"), (360, 343.9, "datos 360 / est 343.9"), (432, 360, "datos 432 / est 360"), (360, 432, "datos 360 / est 432"), (343.9, 399.3, "datos 343.9 / est 399.3"), (399.3, 343.9, "datos 399.3 / est 343.9")]:
    b = [bias(r, ft, fm) for r in pts]
    print("%-26s  first4 max %.4f ; |r|<=20 max %.4f ; incl 30 nm max %.4f" % (lab, max(b[:4]), max(b[:-2]), max(b)))
    print("   ", np.round(b, 4))
print("CRB at (5,-5):", end=" ")
