# -*- coding: utf-8 -*-
"""C14 (checklist SimuFLUX, item 14) - fwhm del estimador vs fwhm de la PSF que genera los datos.

Legado: simulation_misalignment.py:116-118 y make_fig_eficiencia.py:69-71 ajustan DONUT_FWHM a las
donas medidas (343.9 nm, run_final.log:3) y usan ese MISMO valor para generar (ebp_ideal /
geom_exp) y para estimar: en los casos honestos el desajuste es 0 por construccion. Este script
cuantifica lo que costaria no hacerlo: sesgo asintotico (sin ruido; MLE continuo sobre las
probabilidades esperadas, SBR = 2000/95) del estimador con fwhm_est != fwhm_datos, en el EBP ideal
de los estudios (K = 4, L_eff = 103.23 nm). Casos:
  343.9 / 343.9  (lo que hace el legado)
  343.9 / 360    (default del modulo, tools_simulations.py:38)
  360 / 432 y 360 / 300 (confusion de la convencion x1.2 de sml-ssi, tools_simulations.py:28-36)
  399.3 / 343.9  (fwhm medio del ajuste 2D, shared_fwhm_nm de fit_parameters.csv, frente al
                 radial 343.9 que usa el estimador ideal en 'Realista ingenua'; proxy circular)
Tambien da el CRB (SBR fija, N = 2095) para comparar.
Run: python scripts/findings/C14_estimator_fwhm_mismatch.py   (< 20 s)
"""
import os
import sys

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
import matplotlib  # noqa: E402
matplotlib.use("Agg")
from tools import ebp as E  # noqa: E402

LN2 = np.log(2)
L, K = 103.23, 4
SBR = 2000 / 95
N = 2095
POS = E.ideal_positions(L=L, K=K)


def probs(r, fwhm):
    d2 = np.sum((np.asarray(r)[None, :] - POS) ** 2, axis=1)
    I = d2 / fwhm**2 * np.exp(-4 * LN2 * d2 / fwhm**2)
    s = SBR / (SBR + 1)
    return s * I / I.sum() + (1 - s) / K


def crb(r, fwhm, h=1e-3):
    r = np.asarray(r, float)
    p = probs(r, fwhm)
    g = np.array([(probs(r + h * e, fwhm) - probs(r - h * e, fwhm)) / (2 * h) for e in np.eye(2)])
    return float(np.sqrt(np.trace(np.linalg.inv((g / p) @ g.T)) / 2 / N))


def asym_mle(r0, f_data, f_est):
    pt = probs(r0, f_data)
    f = lambda r: -np.sum(pt * np.log(probs(r, f_est)))  # noqa: E731
    res = minimize(f, np.asarray(r0, float), method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-14, "maxiter": 4000})
    return res.x - np.asarray(r0, float)


def main():
    r0s = [(5.0, -5.0), (-5.0, -8.0), (20.0, 0.0), (0.0, -30.0)]
    cases = [(343.9, 343.9), (343.9, 360.0), (360.0, 432.0), (360.0, 300.0), (399.3, 343.9)]
    print("CRB (fwhm 343.9, SBR 21.05, N 2095):",
          ", ".join("%s %.3f nm" % (r, crb(r, 343.9)) for r in r0s))
    print("%-16s" % "datos/estimador" + "".join("%18s" % str(r) for r in r0s) + "   max|b|/CRB")
    for fd, fe in cases:
        bs = [asym_mle(r, fd, fe) for r in r0s]
        mags = [np.hypot(*b) for b in bs]
        rel = max(m / crb(r, fd) for m, r in zip(mags, r0s))
        print("%-16s" % ("%.1f/%.1f" % (fd, fe))
              + "".join("%18s" % ("|b|=%.3f nm" % m) for m in mags) + "   %.2f" % rel)


if __name__ == "__main__":
    main()
