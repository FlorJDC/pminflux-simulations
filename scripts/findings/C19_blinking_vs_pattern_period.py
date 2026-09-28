# -*- coding: utf-8 -*-
"""C19 (checklist SimuFLUX, item 19) - Parpadeo en la escala del barrido del patron.

SimuFLUX (Fig. 2e, SI Fig. 8): con t_on = t_off = 100 us y exposiciones secuenciales (dwell del
patron 400 us) el parpadeo suma sigma_fl independiente de N. En p-MINFLUX los K = 4 haces se
intercalan cada 12.5 ns dentro de un periodo de 50 ns, asi que cualquier parpadeo de us-ms expone a
los 4 haces casi por igual. El legado no simula parpadeo en los estudios (t_mask = None; ademas la
ruta 'p_minflux' lo ignoraria, F107).

Este script calcula el error extra sigma_fl que produce un parpadeo telegrafico (t_on = t_off
exponenciales) solo por el desbalance de exposicion entre haces, propagado linealmente con el
estimador eficiente: dx = (J^T P^-1 J)^-1 J^T P^-1 dp, con dp_i = p_i (w_i - sum_j p_j w_j) y w_i la
exposicion relativa del haz i. EBP ideal de los estudios (K = 4, L_eff = 103.23, fwhm 343.9,
emisor (-5,-8), SBR 21.05, N = 2095). Se compara:
  (A) p-MINFLUX: ranuras en t = c*50 + k*12.5 ns, 2e5 ciclos (10 ms, como M_p de los estudios);
  (B) exposicion secuencial tipo SimuFLUX: 4 exposiciones de 100 us (patron 400 us), 10 ms.
Run: python scripts/findings/C19_blinking_vs_pattern_period.py   (< 30 s)
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
import matplotlib  # noqa: E402
matplotlib.use("Agg")
from tools import ebp as E  # noqa: E402

LN2 = np.log(2)
FWHM, L, K = 343.9, 103.23, 4
SBR, N = 2000 / 95, 2095
POS = E.ideal_positions(L=L, K=K)
R0 = np.array([-5.0, -8.0])
T_TOTAL = 2e5 * 50.0  # ns


def probs(r):
    d2 = np.sum((np.asarray(r)[None, :] - POS) ** 2, axis=1)
    I = d2 / FWHM**2 * np.exp(-4 * LN2 * d2 / FWHM**2)
    s = SBR / (SBR + 1)
    return s * I / I.sum() + (1 - s) / K, s * I / I.sum()


def gain_matrix(h=1e-3):
    p, _ = probs(R0)
    J = np.array([(probs(R0 + h * e)[0] - probs(R0 - h * e)[0]) / (2 * h) for e in np.eye(2)]).T
    Pi = np.diag(1 / p)
    F = J.T @ Pi @ J
    return np.linalg.solve(F, J.T @ Pi), float(np.sqrt(np.trace(np.linalg.inv(F)) / 2 / N))


def on_intervals(rng, t_on, t_off):
    n = int(3 * T_TOTAL / min(t_on, t_off)) + 50
    first_on = rng.random() < 0.5
    d = np.where((np.arange(n) % 2 == 0) == first_on,
                 rng.exponential(t_on, n), rng.exponential(t_off, n))
    edges = np.concatenate(([0.0], np.cumsum(d)))
    assert edges[-1] > T_TOTAL
    t0, t1 = edges[:-1], edges[1:]
    on = (np.arange(n) % 2 == 0) == first_on
    iv = np.column_stack((t0[on], np.minimum(t1[on], T_TOTAL)))
    return iv[iv[:, 0] < T_TOTAL]


def _cum_pmin(t, k):
    """Numero de ranuras del haz k (t = c*50 + k*12.5) en [0, t)."""
    return np.ceil((t - k * 12.5) / 50.0)


def _cum_seq(t, k, dwell=1e5):
    """Tiempo de exposicion del haz k en [0, t) con exposiciones secuenciales de `dwell`."""
    per = K * dwell
    return np.floor(t / per) * dwell + np.clip(np.mod(t, per) - k * dwell, 0, dwell)


def exposure_pminflux(iv):
    return np.array([np.sum(_cum_pmin(iv[:, 1], k) - _cum_pmin(iv[:, 0], k)) for k in range(K)])


def exposure_sequential(iv):
    return np.array([np.sum(_cum_seq(iv[:, 1], k) - _cum_seq(iv[:, 0], k)) for k in range(K)])


def main():
    G, sig_crb = gain_matrix()
    p_tot, p_sig = probs(R0)
    rng = np.random.default_rng(20260928)
    print("sigma_CRB en (-5,-8) = %.3f nm (por eje, promediado)" % sig_crb)
    for t_on in (1e3, 1e5):  # 1 us y 100 us
        for name, fun, nrep in (("p-MINFLUX 50 ns", exposure_pminflux, 400),
                                ("secuencial 4x100 us", exposure_sequential, 400)):
            dx = []
            for _ in range(nrep):
                iv = on_intervals(rng, t_on, t_on)
                w = fun(iv)
                if w.sum() <= 0:
                    continue
                w = w / w.mean()
                ws = p_sig * w
                ptil = ws / ws.sum() * p_sig.sum() + (p_tot - p_sig)  # fondo sin parpadeo
                dx.append(G @ (ptil - p_tot))
            dx = np.array(dx)
            sfl = float(np.sqrt(np.mean(np.var(dx, axis=0) + np.mean(dx, axis=0) ** 2)))
            print("t_on = t_off = %6.0f us, %-20s: sigma_fl = %.2e nm = %.2e sigma_CRB"
                  % (t_on / 1e3, name, sfl, sfl / sig_crb))


if __name__ == "__main__":
    main()
