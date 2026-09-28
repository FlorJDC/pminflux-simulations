# -*- coding: utf-8 -*-
"""Verifier B / F204: true SE of RMSE/CRB vs the printed rmse/crb/sqrt(2n). Own replicate MC."""
import json, os
import numpy as np
from scipy import stats
from v_common import *
import tools.tools_simulations as ts
from tools import ebp as E

grid = E.Grid(NPX, PX)
x, y = coords()
SUB = r'C:\Data\psf\20260703'
sub = E.ebp_experimental(SUB, K=4, grid=grid, reference=0)
N, SBR, n, REPS = 100, 9.0, 250, 400
r0 = np.array([5., -5.])
r, c = int(np.rint(SIZE / 2 - r0[1])), int(np.rint(r0[0] + SIZE / 2))
fw_sub = float(np.mean([E.fit_donut_fwhm(sub.PSFs[k], grid)['fwhm'] for k in range(4)]))
ebps = {'ideal': (my_stack(ideal_pos(L_EFF)), 0.75 * L_EFF),
        'realistic_fit': (my_realistic_stack(realistic_params()), 0.75 * L_EFF),
        'substitute_20260703': (sub.PSFs, 0.75 * sub.L_eff)}
res = {}
for nm, (P, Rm) in ebps.items():
    crb = ts.crb_minflux(4, P, SBR, PX, SIZE, N)[r, c]
    q = naive_p(P[:, r, c][:, None, None], SBR)[:, 0, 0]
    roi = np.hypot(x, y) <= Rm
    idx = np.argwhere(roi)
    logp = np.log(naive_p(P, SBR)[:, roi])
    rs = np.random.RandomState(31337)
    ratios, sdx, bn, printed, kx, ky = [], [], [], [], [], []
    for rep in range(REPS):
        cnt = rs.multinomial(N, q, size=n)
        k = np.argmax(cnt @ logp, axis=1)
        e = np.column_stack([x[idx[k, 0], idx[k, 1]], y[idx[k, 0], idx[k, 1]]])
        b = e.mean(0) - np.array([x[r, c], y[r, c]]); sd = e.std(0)
        rmse = np.sqrt(0.5 * (sd @ sd + b @ b))
        ratios.append(rmse / crb); printed.append(rmse / crb / np.sqrt(2 * n))
        sdx.append(sd[0]); bn.append(np.linalg.norm(b))
        kx.append(stats.kurtosis(e[:, 0])); ky.append(stats.kurtosis(e[:, 1]))
    ratios = np.array(ratios)
    o = dict(crb=float(crb), mean_ratio=float(ratios.mean()), true_se=float(ratios.std(ddof=1)),
             printed_se=float(np.mean(printed)), se_factor=float(ratios.std(ddof=1) / np.mean(printed)),
             sdx_true_se=float(np.std(sdx, ddof=1)), sdx_printed=float(np.mean(sdx) / np.sqrt(2 * n)),
             mean_bias_norm=float(np.mean(bn)), exkurt=[float(np.mean(kx)), float(np.mean(ky))])
    res[nm] = o
    print(nm, {k: (round(v, 3) if isinstance(v, float) else [round(t, 2) for t in v]) for k, v in o.items()})
json.dump(res, open(os.path.join(os.path.dirname(__file__), 'v_F204.json'), 'w'), indent=1)
