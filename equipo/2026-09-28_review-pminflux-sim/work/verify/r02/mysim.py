# -*- coding: utf-8 -*-
"""Verifier r02: independent photon-level p-MINFLUX simulator (does NOT import pminflux_sim).

Route (different from simulate.py): one long stream of n_cycles cycles.
 - signal photons: total ~ Poisson(rate*fs*n_cycles); each picks a uniform cycle and a beam ~ q,
   absolute time = cycle*T + beam*T/K + N(0,sigma) + Exp(tau)
 - background: uniform on [0, n_cycles*T)
 - sort by absolute time, then a sequential per-photon loop (numba):
   'earliest': non-paralyzable dead time d on absolute time (triggered by every avalanche),
               TCSPC records the first avalanche of each arrival cycle floor(t/T)
   'none'    : every photon recorded
   'highest' : sim_exp emulation: per excitation cycle keep 1 signal photon of the highest beam
               present; background added separately (no competition, no dead time)
 - edges trimmed (first/last 20 cycles of the stream dropped).
Own mixing matrix (series of exponnorm CDFs) for the reference model.
"""
import math
import numpy as np
import numba
from scipy import stats

T0, K0 = 50.0, 4
FW2S = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))


@numba.njit(cache=True)
def _earliest(t, T, d):
    n = t.size
    rec = np.zeros(n, dtype=np.bool_)
    last_av = -1e300
    last_cyc = -1
    for k in range(n):
        tk = t[k]
        if tk - last_av >= d:          # detector alive -> avalanche
            last_av = tk
            c = int(math.floor(tk / T))
            if c != last_cyc:          # first avalanche of this cycle -> TCSPC records it
                rec[k] = True
                last_cyc = c
    return rec


def my_lam(x, y, fwhm=360.0, L=100.0):
    ang = 2 * np.pi * np.arange(1, 4) / 3
    pos = np.vstack([[0.0, 0.0], np.c_[L / 2 * np.cos(ang), L / 2 * np.sin(ang)]])
    u = 4 * np.log(2) * ((x - pos[:, 0]) ** 2 + (y - pos[:, 1]) ** 2) / fwhm ** 2
    lam = u * np.exp(-u)
    return lam / lam.sum()


def stream(q, sbr, rate, n_cycles, rng, T=T0, K=K0, tau=4.21, irf=0.3, d=22.0, tcspc="earliest",
           powers=None):
    """Returns dict with abs time t, microtime, cycle, src of RECORDED photons (time order)."""
    q = np.asarray(q, float)
    if powers is not None:
        q = q * np.asarray(powers, float)
    q = q / q.sum()
    fs = 1.0 if math.isinf(sbr) else sbr / (sbr + 1.0)
    sig = irf * FW2S if irf else 0.0
    ns = rng.poisson(rate * fs * n_cycles)
    nb = rng.poisson(rate * (1 - fs) * n_cycles)
    cyc = rng.integers(0, n_cycles, ns)
    beam = rng.choice(K, size=ns, p=q)
    X = rng.exponential(tau, ns)
    if sig:
        X = X + rng.normal(0.0, sig, ns)
    ts = cyc * T + beam * (T / K) + X
    tb = rng.random(nb) * (n_cycles * T)
    if tcspc == "highest":
        # one signal photon per excitation cycle, from the highest beam present
        o = np.lexsort((-beam, cyc))            # by cycle, then beam descending
        c_s, keep_first = cyc[o], np.r_[True, np.diff(cyc[o]) != 0]
        sel = o[keep_first]
        ts, beam = ts[sel], beam[sel]
        t = np.r_[ts, tb]
        src = np.r_[beam, -np.ones(nb, int)]
        o = np.argsort(t, kind="stable")
        t, src = t[o], src[o]
        rec = np.ones(t.size, bool)
    else:
        t = np.r_[ts, tb]
        src = np.r_[beam, -np.ones(nb, int)]
        o = np.argsort(t, kind="stable")
        t, src = t[o], src[o]
        if tcspc == "earliest":
            rec = _earliest(t, T, float(d))
        elif tcspc == "none":
            rec = np.ones(t.size, bool)
        else:
            raise ValueError(tcspc)
    lo, hi = 20 * T, (n_cycles - 20) * T
    rec &= (t >= lo) & (t < hi)
    t, src = t[rec], src[rec]
    c = np.floor(t / T)
    mt = t - c * T
    return dict(t=t, micro=mt, cycle=c.astype(np.int64), src=src)


def window_index_periodic(micro, a, b, T=T0, K=K0):
    """(K, n) boolean membership in window i = [i T/K + a, +b] mod T."""
    out = np.zeros((K, micro.size), bool)
    for i in range(K):
        ph = np.mod(micro - (i * T / K + a), T)
        out[i] = ph < b
    return out


def counts_periodic(micro, a, b, T=T0, K=K0):
    return window_index_periodic(micro, a, b, T, K).sum(axis=1)


def my_C(tau, a, b, irf=None, T=T0, K=K0):
    """C[i,j] = sum_m P(X in [off_ij + a + mT, +b]) with X = N(0,s)+Exp(tau) (scipy exponnorm)."""
    s = irf * FW2S if irf else 0.0
    ms = np.arange(-3, int(60 * tau / T) + 6)
    if s:
        F = lambda x: stats.exponnorm.cdf(x, tau / s, loc=0.0, scale=s)
    else:
        F = lambda x: np.where(x > 0, 1 - np.exp(-np.clip(x, 0, None) / tau), 0.0)
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = ((i - j) * T / K) % T
            lo = off + a + ms * T
            C[i, j] = np.sum(F(lo + b) - F(lo))
    return C


def my_probs(q, C, b, Ns, Nb, T=T0):
    q = np.asarray(q, float) / np.sum(q)
    e = Ns * C.dot(q) + Nb * b / T
    return e / e.sum()


def naive(q, sbr, K=K0):
    q = np.asarray(q, float) / np.sum(q)
    return sbr / (sbr + 1) * q + 1 / (sbr + 1) / K


def chi2p(o, p):
    o = np.asarray(o, float)
    e = o.sum() * p / p.sum()
    c = float(np.sum((o - e) ** 2 / e))
    return c, float(stats.chi2.sf(c, o.size - 1)), (o / o.sum() - p) / np.sqrt(p * (1 - p) / o.sum())
