# -*- coding: utf-8 -*-
"""C03 (checklist SimuFLUX, item 3) - SBR fija por posicion vs fondo constante por exposicion.

Legado: sim_exp fija Ns y Nb (tools_simulations.py:533-559) y crb_minflux/pos_MINFLUX usan una
SBR unica en toda la grilla (lambda_b constante, l.649-653; p de pos_MINFLUX l.1041). Eso equivale
a un fondo que escala con la senal local S(r) = sum_i I_i(r). Con un fondo fisico constante por
exposicion (p-MINFLUX: fondo uniforme en el tiempo -> igual en cada ventana) y Ns fijo, la SBR
real en r es SBR(r) = SBR_0 * S(r)/S(0).

EBP ideal de los estudios: K = 4 (centro + triangulo), L_eff = 103.23 nm, fwhm 343.9 nm;
SBR_0 = 2000/95 en el centro; Ns = 2000.
Imprime: S(r)/S(0) en el patron; CRB con SBR fija (convencion del legado, validado contra
ts.crb_minflux) y con fondo constante; y S(0; L)/S(0; 103.23) para ver como cae la SBR al achicar L.
Run: python scripts/findings/C03_fixed_sbr_vs_constant_background.py   (< 20 s)
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
FWHM, L, K = 343.9, 103.23, 4
NS, NB = 2000, 95
SBR0 = NS / NB


def beams(Lp):
    return E.ideal_positions(L=Lp, K=K)


def intens(r, pos):
    d2 = np.sum((np.asarray(r)[None, :] - pos) ** 2, axis=1)
    return 4 * np.e * LN2 * d2 / FWHM**2 * np.exp(-4 * LN2 * d2 / FWHM**2)


def probs(r, pos, sbr):
    I = intens(r, pos)
    s = sbr / (sbr + 1.0)
    return s * I / I.sum() + (1 - s) / len(pos)


def crb(r, pos, sbr, N, h=1e-3):
    r = np.asarray(r, float)
    p = probs(r, pos, sbr)
    g = np.array([(probs(r + h * e, pos, sbr) - probs(r - h * e, pos, sbr)) / (2 * h)
                  for e in np.eye(2)])
    F = (g / p) @ g.T
    return float(np.sqrt(np.trace(np.linalg.inv(F)) / 2 / N))


def main():
    warnings.simplefilter("ignore")
    pos = beams(L)
    S0 = intens([0, 0], pos).sum()

    # validacion contra el legado (SBR fija, N = Ns + Nb)
    grid = E.Grid(400, 1.0)
    ide = E.ebp_ideal(grid, L=L, K=K, donut_fwhm=FWHM)
    cmap = ts.crb_minflux(K, ide.PSFs, SBR0, 1.0, 400.0, NS + NB, method="1")
    for rr in ([5.0, -5.0], [-5.0, -8.0]):
        i = grid.to_index(np.array(rr))
        print("validacion CRB SBR fija en %s: legado %.4f nm, propio %.4f nm"
              % (rr, cmap[i[0], i[1]], crb(rr, pos, SBR0, NS + NB)))

    print("\nS(r)/S(0) y CRB (Ns = 2000): SBR fija 21.05 vs fondo constante (SBR_0 = 21.05 en r = 0)")
    print("  %-22s %8s %8s %10s %10s %7s" % ("r", "S/S0", "SBR(r)", "CRB_fija", "CRB_fondo", "cociente"))
    pts = [("(5,-5)", [5.0, -5.0]), ("(-5,-8)", [-5.0, -8.0])]
    for rad in (L / 4, L / 2, L):
        for ang in (90.0, 30.0, 270.0):  # hacia un haz, entre haces, opuesto
            a = np.radians(ang)
            pts.append(("|r|=%.1f @%3.0f deg" % (rad, ang), [rad * np.cos(a), rad * np.sin(a)]))
    ratios = []
    for name, rr in pts:
        Sr = intens(rr, pos).sum() / S0
        sbr_r = SBR0 * Sr
        nb_r = NS / sbr_r
        c_fix = crb(rr, pos, SBR0, NS + NB)
        c_bg = crb(rr, pos, sbr_r, NS + nb_r)
        ratios.append(Sr)
        print("  %-22s %8.3f %8.2f %10.3f %10.3f %7.3f" % (name, Sr, sbr_r, c_fix, c_bg, c_bg / c_fix))
    # rango en el disco |r| <= L/2
    th = np.linspace(0, 2 * np.pi, 361)
    rs = np.linspace(0, L / 2, 41)
    vals = np.array([intens([q * np.cos(t), q * np.sin(t)], pos).sum() / S0 for q in rs for t in th])
    print("  rango de S(r)/S(0) en |r| <= L/2: %.3f - %.3f" % (vals.min(), vals.max()))

    print("\nSBR en el centro vs L (fondo constante por exposicion, misma potencia):")
    for Lp in (50.0, 75.0, 103.23, 150.0, 200.0):
        S = intens([0, 0], beams(Lp)).sum()
        print("  L = %6.2f nm: S(0;L)/S(0;103.23) = %.3f   (L^2 ley: %.3f)"
              % (Lp, S / S0, (Lp / L) ** 2))


if __name__ == "__main__":
    main()
