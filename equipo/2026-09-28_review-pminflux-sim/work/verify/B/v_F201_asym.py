# -*- coding: utf-8 -*-
"""Verifier B / F201: independent asymptotic calculation (no MC, own donut, own C)."""
import json, os
import numpy as np
from v_common import *

Ns, Nb = 2000, 95
SBR = Ns / Nb
N = Ns + Nb
R0 = np.array([-5.07, -7.56])
row, col = int(np.rint(SIZE / 2 - R0[1])), int(np.rint(R0[0] + SIZE / 2))
x, y = coords()
RPIX = np.array([x[row, col], y[row, col]])
RMAX = 0.75 * L_EFF

ebps = {'ideal': my_stack(ideal_pos(L_EFF)), 'geom': my_stack(POS_GEOM),
        'real': my_realistic_stack(realistic_params())}
cases = [('Ideal', 'ideal', 'ideal'), ('Geom honesta', 'geom', 'geom'),
         ('Geom ingenua', 'geom', 'ideal'), ('Realista honesta', 'real', 'real'),
         ('Realista ingenua', 'real', 'ideal')]
configs = {'C0': (0.001, 12.5), 'C1': (0.001, 10.1), 'C2': (4.21, 12.5), 'C3': (4.21, 10.1)}

# point functions for continuous CRB
params = realistic_params()
def lam_at(key, r):
    if key == 'ideal':
        return np.array([my_donut(r[0], r[1], p) for p in ideal_pos(L_EFF)])
    if key == 'geom':
        return np.array([my_donut(r[0], r[1], p) for p in POS_GEOM])
    out = []
    for p in params:
        dx, dy = r[0] - p['x0_nm'], r[1] - p['y0_nm']
        ct, st = np.cos(p['theta_rad']), np.sin(p['theta_rad'])
        xp, yp = ct * dx + st * dy, -st * dx + ct * dy
        q = (xp / p['fwhm_x_nm']) ** 2 + (yp / p['fwhm_y_nm']) ** 2
        out.append(p['pedestal'] + p['amplitude'] * 4 * np.e * np.log(2) * q * np.exp(-4 * np.log(2) * q)
                   + p['gradient_x_per_nm'] * dx + p['gradient_y_per_nm'] * dy)
    return np.array(out)

res = {'r_pixel': RPIX.tolist(), 'C': {}}
for cn, (tl, b) in configs.items():
    C = mixing_matrix(tl, b=b)
    res['C'][cn] = C.tolist()
print('C3 mixing matrix:\n', np.round(np.array(res['C']['C3']), 4))
for label, g, e in cases:
    lam = ebps[g][:, row, col]
    out = {}
    for cn, (tl, b) in configs.items():
        C = np.array(res['C'][cn])
        q, _ = expected_fracs(lam, C, Ns, Nb, b)
        est = asym_argmax(q, ebps[e], SBR, RMAX)
        estc = asym_continuous(q, ebps[e], SBR, RMAX)
        out[cn] = {'grid_bias': (est - RPIX).tolist(), 'cont_bias': (estc - RPIX).tolist(),
                   'cont_bias_norm': float(np.linalg.norm(estc - RPIX)),
                   'cont_bias_vs_R0': float(np.linalg.norm(estc - R0))}
    # CRBs at pixel
    pf_naive = lambda r: naive_p(lam_at(g, r)[:, None, None], SBR)[:, 0, 0]
    crb_naive = fisher_crb(pf_naive, RPIX, N)
    C3 = np.array(res['C']['C3'])
    def pf_leak(r):
        q, _ = expected_fracs(lam_at(g, r), C3, Ns, Nb, 10.1)
        return q
    _, Nin = expected_fracs(lam_at(g, RPIX), C3, Ns, Nb, 10.1)
    crb_leak = fisher_crb(pf_leak, RPIX, Nin)
    out['crb_naive_N2095'] = float(crb_naive)
    out['crb_leak_aware_C3'] = float(crb_leak)
    out['N_in_windows_C3'] = float(Nin)
    res[label] = out
    print(f"{label:18s} crb0={crb_naive:.3f} crbC3(leak-aware)={crb_leak:.3f} Nin={Nin:.0f}")
    for cn in configs:
        o = out[cn]
        print(f"   {cn}: grid bias {np.round(o['grid_bias'],2)}  cont bias {np.round(o['cont_bias'],2)} |b|={o['cont_bias_norm']:.2f}")
json.dump(res, open(os.path.join(os.path.dirname(__file__), 'v_F201_asym.json'), 'w'), indent=1)
