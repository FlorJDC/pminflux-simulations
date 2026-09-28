# -*- coding: utf-8 -*-
"""Verifier B / F205: reference R0_NM vs snapped pixel. Own MC (multinomial, 1e5)."""
import json, os
import numpy as np
from v_common import *
from tools import ebp as E

grid = E.Grid(NPX, PX)
x, y = coords()
R0 = np.array([-5.07, -7.56])
idx0 = grid.to_index(R0); RP = grid.to_space(idx0)
print('pixel', tuple(idx0), '->', RP, ' offset', RP - R0, '|off| = %.4f' % np.linalg.norm(RP - R0))
SBR, N, S = 2000 / 95, 2095, 100000
Rm = 0.75 * L_EFF
E_ = {'ideal': my_stack(ideal_pos(L_EFF)), 'geom': my_stack(POS_GEOM), 'real': my_realistic_stack(realistic_params())}
res = {}
for lab, g, e in (('ideal honest', 'ideal', 'ideal'), ('geom honest', 'geom', 'geom'),
                  ('geom naive (est ideal)', 'geom', 'ideal'), ('real honest', 'real', 'real')):
    q = naive_p(E_[g][:, idx0[0], idx0[1]][:, None, None], SBR)[:, 0, 0]
    roi = np.hypot(x, y) <= Rm; ii = np.argwhere(roi)
    logp = np.log(naive_p(E_[e], SBR)[:, roi])
    rs = np.random.RandomState(5)
    ks = np.concatenate([np.argmax(rs.multinomial(N, q, size=20000) @ logp, axis=1) for _ in range(S // 20000)])
    est = np.column_stack([x[ii[ks, 0], ii[ks, 1]], y[ii[ks, 0], ii[ks, 1]]])
    m = est.mean(0); se = est.std(0) / np.sqrt(S)
    o = dict(bias_vs_pixel=(m - RP).tolist(), norm_vs_pixel=float(np.linalg.norm(m - RP)),
             norm_vs_R0=float(np.linalg.norm(m - R0)), se=se.tolist(),
             se_norm_1000=float(np.linalg.norm(est.std(0)) / np.sqrt(1000)))
    # RMSE inflation by reference (per-axis RMSE as in her scripts)
    sd = est.std(0)
    o['rmse_vs_pixel'] = float(np.sqrt(0.5 * (sd @ sd + (m - RP) @ (m - RP))))
    o['rmse_vs_R0'] = float(np.sqrt(0.5 * (sd @ sd + (m - R0) @ (m - R0))))
    res[lab] = o
    print(f"{lab:24s} vs pixel {np.round(m-RP,3)} |{o['norm_vs_pixel']:.3f}|  vs R0 |{o['norm_vs_R0']:.3f}|  "
          f"SE(|b|,n=1000)~{o['se_norm_1000']:.3f}  RMSE pix {o['rmse_vs_pixel']:.3f} R0 {o['rmse_vs_R0']:.3f}")
json.dump(res, open(os.path.join(os.path.dirname(__file__), 'v_F205.json'), 'w'), indent=1)
