# -*- coding: utf-8 -*-
"""Verifier B: independent helpers (own donut, own mixing matrix, own Fisher).
Only the legacy code is imported where the claim is ABOUT the legacy pipeline."""
import os, sys, csv
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
LEG = os.path.join(ROOT, 'legacy', 'p-minflux-main')
if LEG not in sys.path:
    sys.path.insert(0, LEG)

NPX, PX = 400, 1.0
SIZE = NPX * PX
FWHM = 343.9
POS_GEOM = np.array([[0., 0.], [-44., -27.], [45., -26.], [-5., 51.]])  # run_final.log
L_EFF = 2 * np.mean(np.linalg.norm(POS_GEOM[1:], axis=1))


def ideal_pos(L):
    R = L / 2
    out = np.zeros((4, 2))
    for k, ang in zip((1, 2, 3), (210., 330., 90.)):
        out[k] = [R * np.cos(np.radians(ang)), R * np.sin(np.radians(ang))]
    return out


def coords():
    rows, cols = np.indices((NPX, NPX))
    x = cols * PX - SIZE / 2
    y = SIZE / 2 - rows * PX
    return x, y


def my_donut(x, y, pos, w=FWHM):
    r2 = (x - pos[0]) ** 2 + (y - pos[1]) ** 2
    return (r2 / w ** 2) * np.exp(-4 * np.log(2) * r2 / w ** 2)


def my_stack(pos):
    x, y = coords()
    return np.stack([my_donut(x, y, p) for p in pos])


def realistic_params():
    fn = os.path.join(LEG, 'Resultados', 'realistic_psf', 'fit_parameters.csv')
    out = []
    with open(fn) as f:
        for row in csv.DictReader(f):
            d = {}
            for k, v in row.items():
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
            out.append(d)
    return out


def my_realistic_stack(params, power=False):
    """Own re-implementation of donut_2d (full features)."""
    x, y = coords()
    out = []
    for p in params:
        dx, dy = x - p['x0_nm'], y - p['y0_nm']
        ct, st = np.cos(p['theta_rad']), np.sin(p['theta_rad'])
        xp, yp = ct * dx + st * dy, -st * dx + ct * dy
        q = (xp / p['fwhm_x_nm']) ** 2 + (yp / p['fwhm_y_nm']) ** 2
        d = 4 * np.e * np.log(2) * q * np.exp(-4 * np.log(2) * q)
        v = p['pedestal'] + p['amplitude'] * d + p['gradient_x_per_nm'] * dx + p['gradient_y_per_nm'] * dy
        v = np.maximum(v, np.finfo(float).eps)
        if power:
            v = v * p['intensity_scale']
        out.append(v)
    return np.stack(out)


def mixing_matrix(tau, T=50.0, K=4, a=0.0, b=12.5, nwrap=60):
    """C[i,j] = P(photon excited by beam j (at j*T/K) lands in window i (i*T/K+a, +b)) mod T."""
    C = np.zeros((K, K))
    F = lambda t: np.where(t > 0, 1 - np.exp(-np.maximum(t, 0) / tau), 0.0)
    for i in range(K):
        for j in range(K):
            s = 0.0
            for n in range(-1, nwrap):
                lo = i * T / K + a - j * T / K + n * T
                s += F(lo + b) - F(lo)
            C[i, j] = s
    return C


def naive_p(PSF, sbr):
    K = PSF.shape[0]
    return sbr / (sbr + 1) * PSF / PSF.sum(0) + 1 / ((sbr + 1) * K)


def expected_fracs(lam, C, Ns, Nb, b, T=50.0):
    lam = np.asarray(lam, float)
    s = Ns * C @ (lam / lam.sum()) + Nb * b / T
    return s / s.sum(), s.sum()


def asym_argmax(q, PSF_est, sbr, rmax):
    """Asymptotic (expected-count) grid MLE within |r|<rmax. Returns (x,y) nm."""
    x, y = coords()
    P = naive_p(PSF_est, sbr)
    ll = np.tensordot(q, np.log(P), axes=(0, 0))
    ll = np.where(np.hypot(x, y) > rmax, -np.inf, ll)
    r, c = np.unravel_index(np.argmax(ll), ll.shape)
    return np.array([x[r, c], y[r, c]])


def asym_continuous(q, PSF_est, sbr, rmax):
    """Sub-pixel refinement: fit a paraboloid to ll around the grid argmax."""
    x, y = coords()
    P = naive_p(PSF_est, sbr)
    ll = np.tensordot(q, np.log(P), axes=(0, 0))
    ll = np.where(np.hypot(x, y) > rmax, -np.inf, ll)
    r, c = np.unravel_index(np.argmax(ll), ll.shape)
    w = 3
    rr, cc = np.mgrid[r - w:r + w + 1, c - w:c + w + 1]
    dx = (cc - c).ravel() * PX
    dy = -(rr - r).ravel() * PX
    A = np.column_stack([np.ones_like(dx), dx, dy, dx * dx, dx * dy, dy * dy])
    co = np.linalg.lstsq(A, ll[rr, cc].ravel(), rcond=None)[0]
    H = np.array([[2 * co[3], co[4]], [co[4], 2 * co[5]]])
    sh = -np.linalg.solve(H, co[1:3])
    return np.array([x[r, c], y[r, c]]) + sh


def fisher_crb(pfun, r, N, h=0.5):
    """sigma_CRB = sqrt(trace(I^-1)/2) with I = N sum (dp)^2/p; pfun(r)->p (K,)."""
    p0 = pfun(r)
    dpx = (pfun(r + [h, 0]) - pfun(r - [h, 0])) / (2 * h)
    dpy = (pfun(r + [0, h]) - pfun(r - [0, h])) / (2 * h)
    I = N * np.array([[np.sum(dpx * dpx / p0), np.sum(dpx * dpy / p0)],
                      [np.sum(dpx * dpy / p0), np.sum(dpy * dpy / p0)]])
    return np.sqrt(np.trace(np.linalg.inv(I)) / 2)
