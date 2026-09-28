# -*- coding: utf-8 -*-
"""Verifier r02: own window-count models, Fisher/CRB and vectorized MLE (no pminflux_sim import)."""
import math
import numpy as np
from mysim import my_C, FW2S

T, K, FWHM, L = 50.0, 4, 360.0, 100.0
_ang = 2 * np.pi * np.arange(1, 4) / 3
POS = np.vstack([[0.0, 0.0], np.c_[L / 2 * np.cos(_ang), L / 2 * np.sin(_ang)]])


def qbeams(x, y):
    """x,y arrays (...) -> normalized excitation (..., K)."""
    x = np.asarray(x, float)[..., None]; y = np.asarray(y, float)[..., None]
    u = 4 * np.log(2) * ((x - POS[:, 0]) ** 2 + (y - POS[:, 1]) ** 2) / FWHM ** 2
    lam = u * np.exp(-u)
    return lam / lam.sum(-1, keepdims=True)


def model_mix(C, b, sbr):
    beta = 1.0 / (sbr + 1.0)          # background fraction of the full cycle
    def p(x, y):
        q = qbeams(x, y)
        e = (1 - beta) * q.dot(C.T) + beta * b / T
        return e / e.sum(-1, keepdims=True)
    return p


def model_naive(sbr):
    def p(x, y):
        q = qbeams(x, y)
        return sbr / (sbr + 1) * q + 1 / (sbr + 1) / K
    return p


def crb(pf, r, N, h=1e-4):
    x, y = r
    p0 = pf(x, y)
    gx = (pf(x + h, y) - pf(x - h, y)) / (2 * h)
    gy = (pf(x, y + h) - pf(x, y - h)) / (2 * h)
    F = N * np.array([[np.sum(gx * gx / p0), np.sum(gx * gy / p0)], [np.sum(gx * gy / p0), np.sum(gy * gy / p0)]])
    return math.sqrt(np.trace(np.linalg.inv(F)) / 2)


def mle(counts, pf, R=75.0, grid=1.0, iters=40, h=1e-3):
    """Grid argmax on the disc + damped Newton with finite-difference derivatives (vectorized)."""
    n = np.asarray(counts, float)
    g = np.arange(-R, R + grid / 2, grid)
    GX, GY = np.meshgrid(g, g); m = np.hypot(GX, GY) <= R
    gx, gy = GX[m], GY[m]
    LP = np.log(pf(gx, gy))                                  # (G, K)
    best = np.argmax(n.dot(LP.T), axis=1)
    x, y = gx[best].copy(), gy[best].copy()
    ll = lambda x, y: np.sum(n * np.log(pf(x, y)), axis=1)
    for _ in range(iters):
        f0 = ll(x, y)
        fxp, fxm, fyp, fym = ll(x + h, y), ll(x - h, y), ll(x, y + h), ll(x, y - h)
        fpp, fmm, fpm, fmp = ll(x + h, y + h), ll(x - h, y - h), ll(x + h, y - h), ll(x - h, y + h)
        Gx, Gy = (fxp - fxm) / (2 * h), (fyp - fym) / (2 * h)
        Hxx = (fxp - 2 * f0 + fxm) / h ** 2; Hyy = (fyp - 2 * f0 + fym) / h ** 2
        Hxy = (fpp + fmm - fpm - fmp) / (4 * h * h)
        det = Hxx * Hyy - Hxy ** 2
        ok = (det > 0) & (Hxx < 0)
        sx = np.where(ok, -(Hyy * Gx - Hxy * Gy) / np.where(ok, det, 1), 0.05 * Gx)
        sy = np.where(ok, -(-Hxy * Gx + Hxx * Gy) / np.where(ok, det, 1), 0.05 * Gy)
        st = np.hypot(sx, sy); c = np.minimum(1.0, 1.0 / np.maximum(st, 1e-300))
        sx, sy = sx * c, sy * c
        # backtracking (one halving pass)
        for _k in range(6):
            nx, ny = x + sx, y + sy
            rr = np.hypot(nx, ny); out = rr > R
            nx = np.where(out, nx * R / rr, nx); ny = np.where(out, ny * R / rr, ny)
            better = ll(nx, ny) >= f0 - 1e-12
            x = np.where(better, nx, x); y = np.where(better, ny, y)
            if better.all():
                break
            sx = np.where(better, 0, sx / 2); sy = np.where(better, 0, sy / 2)
        if np.max(np.hypot(sx, sy)) < 1e-7:
            break
    return x, y, np.hypot(x, y) > R - 1e-6


def asym_mle(ptrue, pf, r0):
    """Asymptotic estimate: argmax sum ptrue log pf(r) (expected-count MLE), started at r0."""
    x, y, _ = mle(ptrue[None, :] * 1e6, pf, R=75.0, grid=0.5)
    return np.array([x[0], y[0]])


def first_order_fracs(q, sbr, rate, d, tau, irf, a, b, M=20000):
    """First-order finite-rate recorded window fractions for earliest TCSPC + non-paralyzable d."""
    from scipy import stats
    h = T / M; tg = (np.arange(M) + 0.5) * h
    s = irf * FW2S if irf else 0.0
    dens0 = np.zeros(M)
    for m in range(-2, 60):
        if s:
            dens0 += stats.exponnorm.pdf(tg + m * T, tau / s, scale=s)
        else:
            tt = tg + m * T
            dens0 += np.where(tt > 0, np.exp(-np.clip(tt, 0, None) / tau) / tau, 0)
    fs = sbr / (sbr + 1)
    sig = sum(q[j] * np.roll(dens0, int(round(j * T / K / h))) for j in range(K))
    Lt = rate * (fs * sig / (sig.sum() * h) + (1 - fs) / T)
    cum = np.concatenate([[0], np.cumsum(np.tile(Lt, 4) * h)])
    idx = np.arange(M) + 3 * M; nd = int(round(d / h))
    back = nd if d >= T else np.maximum(np.arange(M), nd)
    rho = Lt * (1 - (cum[idx] - cum[idx - back]))
    o = np.array([rho[np.mod(tg - (i * T / K + a), T) < b].sum() for i in range(K)])
    o0 = np.array([Lt[np.mod(tg - (i * T / K + a), T) < b].sum() for i in range(K)])
    return o / o.sum(), o0 / o0.sum()
