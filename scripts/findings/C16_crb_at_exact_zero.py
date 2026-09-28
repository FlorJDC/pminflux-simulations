# -*- coding: utf-8 -*-
"""C16 (checklist SimuFLUX, item 16) - CRB en el cero exacto: valor puntual vs limite.

El haz central del TCP tiene su cero en r = 0. Sin fondo, p_0 ~ c r^2 y dp_0/dr ~ 2 c r, asi que
(dp_0)^2/p_0 -> 4c: el aporte del haz central es finito en el limite r -> 0 pero vale 0/0 (y
numericamente 0) en el punto exacto. Con fondo finito p_0(0) = (1-s)/K > 0 y el CRB es continuo.
Se evalua ts.crb_minflux (metodo 1: np.gradient con paso de 1 px, sin regularizador) en el pixel
central y en sus 4 vecinos a 1 nm, contra un Fisher continuo propio en r = 0 exacto y en |r| = 1e-3
nm (el limite), para SBR = 21.05, 1e3, 1e6, 1e12. EBP ideal de los estudios: K = 4, L_eff = 103.23,
fwhm 343.9, grilla 200 nm / 1 nm, N = 2095.
Run: python scripts/findings/C16_crb_at_exact_zero.py   (< 10 s)
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402
from tools import ebp as E  # noqa: E402

LN2 = np.log(2)
FWHM, L, K, N = 343.9, 103.23, 4, 2095
POS = E.ideal_positions(L=L, K=K)


def probs(r, sbr):
    d2 = np.sum((np.asarray(r)[None, :] - POS) ** 2, axis=1)
    I = d2 / FWHM**2 * np.exp(-4 * LN2 * d2 / FWHM**2)
    s = sbr / (sbr + 1)
    return s * I / I.sum() + (1 - s) / K


def grad(r, sbr):
    """Derivada analitica de p respecto de r (exacta, sin diferencias finitas)."""
    r = np.asarray(r, float)
    dv = r[None, :] - POS
    d2 = np.sum(dv**2, axis=1)
    a = 4 * LN2 / FWHM**2
    I = d2 / FWHM**2 * np.exp(-a * d2)
    dI = (2 * dv / FWHM**2 * np.exp(-a * d2)[:, None]) * (1 - a * d2)[:, None]  # (K,2)
    S, dS = I.sum(), dI.sum(axis=0)
    s = sbr / (sbr + 1)
    return s * (dI / S - I[:, None] * dS[None, :] / S**2)  # (K,2)


def crb_cont(r, sbr):
    p = probs(r, sbr)
    g = grad(r, sbr)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.where(p > 0, 1 / p, 0.0)
        F = (g * w[:, None]).T @ g
    return float(np.sqrt(np.trace(np.linalg.inv(F)) / 2 / N))


def main():
    warnings.simplefilter("ignore")
    grid = E.Grid(200, 1.0)
    ide = E.ebp_ideal(grid, L=L, K=K, donut_fwhm=FWHM)
    c = grid.center_idx
    print("pixel central -> %s nm" % (grid.to_space(c),))
    print("%-8s %12s %14s %12s %12s %12s" % ("SBR", "legado r=0", "legado vec.1nm", "cont r=0",
                                              "cont 1e-3nm", "cont 1 nm"))
    for sbr in (2000 / 95, 1e3, 1e6, 1e12):
        m = ts.crb_minflux(K, ide.PSFs, sbr, 1.0, 200.0, N, method="1")
        nb = np.mean([m[c[0] + 1, c[1]], m[c[0] - 1, c[1]], m[c[0], c[1] + 1], m[c[0], c[1] - 1]])
        print("%-8.3g %12.4f %14.4f %12.4f %12.4f %12.4f"
              % (sbr, m[c], nb, crb_cont([0.0, 0.0], sbr), crb_cont([1e-3, 0.0], sbr),
                 crb_cont([1.0, 0.0], sbr)))


if __name__ == "__main__":
    main()
