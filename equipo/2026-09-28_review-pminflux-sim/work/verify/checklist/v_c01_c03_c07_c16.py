# -*- coding: utf-8 -*-
"""Verificador independiente: checklist C01, C03, C07, C16.
Modelo propio (Balzarotti S16) sin usar los scripts del worker; ts solo para comparar.
"""
import os, sys, csv
import numpy as np

ROOT = r"C:\Users\BANGHO\Documents\GithubPRO\pminflux-sim-v2"
LEG = os.path.join(ROOT, "legacy", "p-minflux-main")
sys.path.insert(0, LEG)
from tools import tools_simulations as ts  # noqa

LN2 = np.log(2)
FWHM = 343.9
L = 103.23
K = 4
Ns, Nb = 2000, 95
SBR = Ns / Nb
N = Ns + Nb


def donut(r2, fwhm=FWHM):  # ring peak = 1
    u = 4 * LN2 * r2 / fwhm**2
    return np.e * u * np.exp(-u)


def centers(L=L):
    R = L / 2
    pos = [(0.0, 0.0)]
    for k in (1, 2, 3):
        a = np.radians(90 + 120 * k)
        pos.append((R * np.cos(a), R * np.sin(a)))
    return np.array(pos)


def I_all(x, y, L=L, fwhm=FWHM):
    c = centers(L)
    return np.array([donut((x - cx)**2 + (y - cy)**2, fwhm) for cx, cy in c])


# ---------------- C01 ----------------
print("=== C01")
r = np.linspace(0, 3000, 600001)
dr = r[1] - r[0]
leg = donut(r**2)
simu = 4 * LN2 * r**2 / FWHM**2 * np.exp(-4 * LN2 * r**2 / FWHM**2)
gau = np.exp(-4 * LN2 * r**2 / FWHM**2)
P = lambda f: np.sum(2 * np.pi * r * f) * dr
print("ring peak legacy %.6f at r=%.2f ; simuflux %.6f (1/e %.6f)" % (leg.max(), r[leg.argmax()], simu.max(), 1 / np.e))
print("power leg/gau %.5f simu/gau %.5f ratio %.5f e=%.5f" % (P(leg) / P(gau), P(simu) / P(gau), P(leg) / P(simu), np.e))
print("ts.doughnut peak check:", ts.doughnut(np.array([FWHM / (2 * np.sqrt(LN2))]), FWHM))
rows = list(csv.DictReader(open(os.path.join(LEG, "Resultados", "realistic_psf", "fit_parameters.csv"), encoding="utf-8")))
ped = np.array([float(x["pedestal"]) for x in rows]); amp = np.array([float(x["amplitude"]) for x in rows])
zr = np.array([float(x["zero_ratio_experimental"]) for x in rows])
print("ped/amp", np.round(ped / amp, 4), " /e", np.round(ped / amp / np.e, 4))
print("zero_ratio", np.round(zr, 4), " /e", np.round(zr / np.e, 4), " zr/(1-zr)/e", np.round(zr / (1 - zr) / np.e, 4))
print("0.01*e =", 0.01 * np.e, "; ratio of converted pedestals to 0.01:", np.round(ped / amp / np.e / 0.01, 2))
# 400 nm grid, 1 nm px, max of single ideal donut map
g = np.arange(-200, 200, 1.0)
X, Y = np.meshgrid(g, g)
print("max of donut on 400 nm grid:", donut(X**2 + Y**2).max(), " ring radius", FWHM / (2 * np.sqrt(LN2)))

# ---------------- C03 ----------------
print("=== C03")
S0 = I_all(0.0, 0.0).sum()


def probs_fixed(x, y):
    I = I_all(x, y); s = SBR / (SBR + 1)
    return s * I / I.sum() + (1 - s) / K


beta = S0 / (K * SBR)


def probs_const(x, y):
    I = I_all(x, y)
    return (I + beta) / (I.sum() + K * beta)


def crb(pf, x, y, h=1e-3, NN=N):
    p = pf(x, y)
    dx = (pf(x + h, y) - pf(x - h, y)) / (2 * h)
    dy = (pf(x, y + h) - pf(x, y - h)) / (2 * h)
    F = np.array([[np.sum(dx * dx / p), np.sum(dx * dy / p)], [np.sum(dx * dy / p), np.sum(dy * dy / p)]])
    return np.sqrt(np.trace(np.linalg.inv(F)) / (2 * NN))


ratios, Sr = [], []
for rr in np.linspace(0, L / 2, 27):
    for th in np.linspace(0, 2 * np.pi, 73)[:-1]:
        x, y = rr * np.cos(th), rr * np.sin(th)
        Sr.append(I_all(x, y).sum() / S0)
        if rr > 0:
            ratios.append(crb(probs_const, x, y) / crb(probs_fixed, x, y))
print("S(r)/S(0) in |r|<=L/2: %.4f - %.4f" % (min(Sr), max(Sr)))
print("CRB const/fixed in 0<|r|<=L/2: %.4f - %.4f" % (min(ratios), max(ratios)))
SL = [I_all(L * np.cos(t), L * np.sin(t)).sum() / S0 for t in np.linspace(0, 2 * np.pi, 361)]
print("S at |r|=L: %.3f - %.3f" % (min(SL), max(SL)))
rl = [crb(probs_const, L * np.cos(t), L * np.sin(t)) / crb(probs_fixed, L * np.cos(t), L * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 73)]
print("CRB ratio at |r|=L: %.4f - %.4f" % (min(rl), max(rl)))
S0_50 = I_all(0, 0, L=50).sum()
print("S(0;50)/S(0;103.23) = %.4f ; L^2 law %.4f" % (S0_50 / S0, (50 / L)**2))
print("own fixed CRB at (5,-5): %.4f" % crb(probs_fixed, 5, -5))
# legacy crb_minflux on 1 nm grid
size = 400
psf = np.array([ts.psf(c, size, 1, [0, 0], 'donut', donut_fwhm=FWHM) for c in centers()])
C = ts.crb_minflux(K, psf, SBR, 1, size, N, method='1')
# map index of (5,-5): x axis = arange(-200,200), y flipped
ix = 200 + 5; iy = 200 + 5  # row for y=-5 -> -y = 5 -> index of 5 in arange(-200..)
print("legacy crb_minflux at (5,-5): %.4f" % C[iy, ix])

# ---------------- C16 ----------------
print("=== C16")
print("legacy center [200,200]: %.4f ; neighbours: %s" % (C[200, 200], np.round([C[199, 200], C[201, 200], C[200, 199], C[200, 201]], 4)))
print("own continuous at r=0 (h=1e-3): %.4f ; at 1 nm %.4f ; at 1e-3 nm %.4f" % (crb(probs_fixed, 0, 0), crb(probs_fixed, 1, 0), crb(probs_fixed, 1e-2, 1e-2)))
SBR_big = 1e12
Cb = ts.crb_minflux(K, psf, SBR_big, 1, size, N, method='1')
print("legacy SBR 1e12 center %.4f neighbours %s" % (Cb[200, 200], np.round([Cb[199, 200], Cb[201, 200], Cb[200, 199], Cb[200, 201]], 4)))
SBRs = SBR


def probs_fixed_s(x, y, S):
    I = I_all(x, y); s = S / (S + 1)
    return s * I / I.sum() + (1 - s) / K


for rr in [1.0, 0.1, 0.01, 1e-3]:
    print(" own SBR1e12 at r=%g: %.4f" % (rr, crb(lambda a, b: probs_fixed_s(a, b, 1e12), rr, 0.3 * rr, h=rr * 1e-3)))
# point value at exactly 0 with central difference step 1 nm (legacy-like)
print(" own SBR1e12 point at 0 with h=1 nm: %.4f" % crb(lambda a, b: probs_fixed_s(a, b, 1e12), 0, 0, h=1.0))
print(" own SBR1e12 point at 0 with h=1e-3: %.4f" % crb(lambda a, b: probs_fixed_s(a, b, 1e12), 0, 0, h=1e-3))
# analytic limit without background: drop centre term? compute Fisher at r->0 with SBR=inf
# analytic: centre p0 ~ c r^2 -> (dp0)^2/p0 -> 4c (direction-dependent components)

# ---------------- C07 ----------------
print("=== C07")
def bead_fill(D):
    a = D / 2
    # projected uniform sphere: weight sqrt(a^2-rho^2)
    rho = np.linspace(0, a, 200001)
    w = np.sqrt(np.maximum(a**2 - rho**2, 0)) * 2 * np.pi * rho
    return np.sum(w * donut(rho**2)) / np.sum(w)
for D in [20, 100]:
    f = bead_fill(D)
    print("bead %d nm: fill %.4f %% of ring peak; analytic small %.4f %%; / zero_ratio: %.1f - %.1f %%"
          % (D, 100 * f, 100 * 4 * np.e * LN2 * (2 * (D / 2)**2 / 5) / FWHM**2, 100 * f / zr.max(), 100 * f / zr.min()))
# disk (2D uniform) instead of sphere, for sensitivity
a = 10.0; rho = np.linspace(0, a, 100001); w = 2 * np.pi * rho
print("20 nm as uniform disk: %.4f %%" % (100 * np.sum(w * donut(rho**2)) / np.sum(w)))
