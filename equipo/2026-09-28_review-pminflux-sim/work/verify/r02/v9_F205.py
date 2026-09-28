# -*- coding: utf-8 -*-
"""(3) F205 direction: per-axis RMSE as analyze_realistic_psf.py:88 computes it (vs R0 = (-5.07,-7.56))
versus against the pixel actually simulated (-5,-8). Own grid MLE (naive model, 1 nm grid), 1e5 samples.
Constants (positions, fwhm 343.9, SBR, N, ROI 0.75 L) as in the legacy run (run_final.log / verifier B)."""
import numpy as np, json, os
g = np.arange(-200, 200) * 1.0
X, Y = np.meshgrid(g, -g + 0.0)                 # x = col - 200, y = 200 - row
POS_GEOM = np.array([[0., 0.], [-44., -27.], [45., -26.], [-5., 51.]])
L_EFF = 2 * np.mean(np.linalg.norm(POS_GEOM[1:], axis=1))
ang = np.radians([210., 330., 90.])
POS_ID = np.vstack([[0, 0], np.c_[L_EFF / 2 * np.cos(ang), L_EFF / 2 * np.sin(ang)]])
FW = 343.9; SBR = 2000 / 95.; N = 2095
R0 = np.array([-5.07, -7.56]); RP = np.array([-5.0, -8.0])
def stack(pos, x, y):
    r2 = (x[None] - pos[:, 0, None]) ** 2 + (y[None] - pos[:, 1, None]) ** 2
    return r2 / FW ** 2 * np.exp(-4 * np.log(2) * r2 / FW ** 2)
roi = np.hypot(X, Y) <= 0.75 * L_EFF
xr, yr = X[roi], Y[roi]
out = {}
rng = np.random.default_rng(205205)
for name, pos in (("ideal", POS_ID), ("geometry", POS_GEOM)):
    P = stack(pos, xr, yr); P = SBR / (SBR + 1) * P / P.sum(0) + 1 / (SBR + 1) / 4
    lp = np.log(P)
    s = stack(pos, RP[:1], RP[1:])[:, 0]; q = SBR / (SBR + 1) * s / s.sum() + 1 / (SBR + 1) / 4
    est = []
    for _ in range(10):
        k = np.argmax(rng.multinomial(N, q, size=10000) @ lp, axis=1)
        est.append(np.c_[xr[k], yr[k]])
    est = np.vstack(est)
    rm = lambda ref: float(np.sqrt(np.mean(np.sum((est - ref) ** 2, 1)) / 2))
    out[name] = dict(rmse_vs_R0_as_line88=rm(R0), rmse_vs_pixel=rm(RP), bias_vs_R0=float(np.linalg.norm(est.mean(0) - R0)),
                     bias_vs_pixel=float(np.linalg.norm(est.mean(0) - RP)), rmse_se_n300=rm(RP) / np.sqrt(600))
    print(name, out[name])
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "v9_F205.json"), "w"), indent=1)
