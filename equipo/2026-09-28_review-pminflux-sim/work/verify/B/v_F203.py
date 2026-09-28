# -*- coding: utf-8 -*-
"""Verifier B / F203: dependence of naive/low-N results on the search radius. Own MC (multinomial)."""
import json, os
import numpy as np
from v_common import *
from tools import ebp as E
from tools import realistic_ebp as R

grid = E.Grid(NPX, PX)
x, y = coords()
SUB = r'C:\Data\psf\20260703'   # labelled SUBSTITUTE for the missing 20260820
sub = E.ebp_experimental(SUB, K=4, grid=E.grid_from_fit_config(os.path.join(SUB, 'fit_config.txt')), reference=0)
fw_sub = float(np.mean([E.fit_donut_fwhm(sub.PSFs[k], grid)['fwhm'] for k in range(4)]))
print('substitute 20260703: L_eff %.2f fwhm %.1f pos' % (sub.L_eff, fw_sub), sub.pos_nm.tolist())
ideal_sub = my_stack(ideal_pos(sub.L_eff)) if abs(fw_sub - FWHM) < 1e-9 else \
    np.stack([my_donut(x, y, p, fw_sub) for p in ideal_pos(sub.L_eff)])
ideal = my_stack(ideal_pos(L_EFF))
real = my_realistic_stack(realistic_params())

def mc(gen, est, r0, N, sbr, Rmax, S=1000, seed=99):
    rs = np.random.RandomState(seed)
    r, c = int(np.rint(SIZE / 2 - r0[1])), int(np.rint(r0[0] + SIZE / 2))
    rp = np.array([x[r, c], y[r, c]])
    q = naive_p(gen[:, r, c][:, None, None], sbr)[:, 0, 0]
    roi = np.hypot(x, y) <= Rmax
    idx = np.argwhere(roi)
    logp = np.log(naive_p(est, sbr)[:, roi])
    k = np.array([np.argmax(rs.multinomial(N, q) @ logp) for _ in range(S)])
    e = np.column_stack([x[idx[k, 0], idx[k, 1]], y[idx[k, 0], idx[k, 1]]])
    b = e.mean(0) - rp; sd = e.std(0)
    return dict(bias=float(np.linalg.norm(b)), rmse=float(np.sqrt(0.5 * (sd @ sd + b @ b))),
                edge=float(np.mean(np.hypot(e[:, 0], e[:, 1]) > Rmax - 1.5)), r0norm=float(np.linalg.norm(rp)))

res = {}
for fac in (0.5, 0.75, 1.0, 1.25):
    row = {}
    Rm = fac * L_EFF
    row['real_naive_N2095'] = mc(real, ideal, np.array([-5.07, -7.56]), 2095, 2000 / 95, Rm)
    row['sub_naive_N2095'] = mc(sub.PSFs, ideal_sub, np.array([-5.07, -7.56]), 2095, 2000 / 95, fac * sub.L_eff)
    row['real_honest_N100'] = mc(real, real, np.array([5., -5.]), 100, 9.0, Rm, S=2000)
    row['sub_honest_N100'] = mc(sub.PSFs, sub.PSFs, np.array([5., -5.]), 100, 9.0, fac * sub.L_eff, S=2000)
    res[fac] = row
    print(f'R={fac:.2f}L: ' + '  '.join(f"{k}: |b|={v['bias']:.1f} RMSE={v['rmse']:.1f} edge={v['edge']:.2f}" for k, v in row.items()))
json.dump(res, open(os.path.join(os.path.dirname(__file__), 'v_F203.json'), 'w'), indent=1)
