# -*- coding: utf-8 -*-
"""Verifier B / F202: realistic_ebp drops intensity_scale. Own numbers."""
import json, os, sys
import numpy as np
from v_common import *
import tools.tools_simulations as ts
from tools import ebp as E
from tools import realistic_ebp as R
import analyze_realistic_psf as A   # only functions; main() not executed

Ns, Nb = 2000, 95
SBR, N = Ns / Nb, Ns + Nb
R0 = np.array([-5.07, -7.56])
grid = E.Grid(NPX, PX)
r0_idx = grid.to_index(R0)
RPIX = grid.to_space(r0_idx)
RMAX = 0.75 * L_EFF
params = realistic_params()
for p in params:
    p['success'] = True
res = {}

# (1) reproduce her ladder (stages up to 'background') with her RNG sequence
shared = params[0]['shared_fwhm_nm']
stages = {
    'geometry': E.ebp_analytic(POS_GEOM, grid, donut_fwhm=shared),
    'individual_width': R.ebp_realistic(A.stripped_params(params, {'width'}), grid),
    'pedestal': R.ebp_realistic(A.stripped_params(params, {'width', 'pedestal'}), grid),
    'ellipticity': R.ebp_realistic(A.stripped_params(params, {'width', 'pedestal', 'ellipticity'}), grid),
    'background': R.ebp_realistic(A.stripped_params(params, {'width', 'pedestal', 'ellipticity', 'background', 'amplitude'}), grid),
}
rng = np.random.RandomState(20260901)
ladder = {}
for nm, c in stages.items():
    crb = ts.crb_minflux(4, c.PSFs, SBR, PX, SIZE, N, method='1')[r0_idx[0], r0_idx[1]]
    h = A.monte_carlo(c, c, r0_idx, R0, SBR, N, 300, rng, RMAX)
    g = A.monte_carlo(c, stages['geometry'], r0_idx, R0, SBR, N, 300, rng, RMAX)
    ladder[nm] = [float(crb), h['rmse_nm'], h['bias_magnitude_nm'], g['rmse_nm'], g['bias_magnitude_nm']]
    print(f'{nm:17s} CRB {crb:.4f} honestRMSE {h["rmse_nm"]:.4f} |b| {h["bias_magnitude_nm"]:.4f} geomRMSE {g["rmse_nm"]:.4f} |b| {g["bias_magnitude_nm"]:.4f}')
res['ladder_repro'] = ladder

# (2) effect of intensity_scale
P0 = my_realistic_stack(params, power=False)
P1 = my_realistic_stack(params, power=True)
scales = np.array([p['intensity_scale'] for p in params])
print('intensity_scale', scales, 'max/min', scales.max() / scales.min())
lam0, lam1 = P0[:, r0_idx[0], r0_idx[1]], P1[:, r0_idx[0], r0_idx[1]]
p0, p1 = lam0 / lam0.sum(), lam1 / lam1.sum()
print('p_signal no-power', np.round(p0, 4), ' with power', np.round(p1, 4), ' rel change', np.round(p1 / p0 - 1, 3))
crb0 = ts.crb_minflux(4, P0, SBR, PX, SIZE, N)[r0_idx[0], r0_idx[1]]
crb1 = ts.crb_minflux(4, P1, SBR, PX, SIZE, N)[r0_idx[0], r0_idx[1]]
print('legacy CRB no-power %.3f  with power %.3f' % (crb0, crb1))
res.update(scales=scales.tolist(), p0=p0.tolist(), p1=p1.tolist(), crb0=float(crb0), crb1=float(crb1))

# (3) data with power, estimator without power: asymptotic + MC (multinomial, own RNG)
q = naive_p(lam1[:, None, None], SBR)[:, 0, 0]
geomP = stages['geometry'].PSFs
for estname, PE in (('realistic_nopower', P0), ('geometry', geomP), ('realistic_power(honest)', P1)):
    ea = asym_continuous(q, PE, SBR, RMAX) - RPIX
    rs = np.random.RandomState(4242)
    x, y = coords()
    roi = np.hypot(x, y) <= RMAX
    idx = np.argwhere(roi)
    logp = np.log(naive_p(PE, SBR)[:, roi])
    est = np.array([[x[tuple(idx[k])], y[tuple(idx[k])]] for k in
                    (np.argmax(rs.multinomial(N, q) @ logp) for _ in range(1000))])
    b = est.mean(0) - RPIX
    sd = est.std(0)
    rmse = np.sqrt(0.5 * (sd @ sd + b @ b))
    print(f'est={estname:24s} asym bias {np.round(ea,2)} |{np.linalg.norm(ea):.2f}|  MC bias {np.round(b,2)} |b|={np.linalg.norm(b):.2f} (vs R0 {np.linalg.norm(est.mean(0)-R0):.2f}) RMSE {rmse:.2f}')
    res['est_' + estname] = dict(asym=ea.tolist(), mc_bias=b.tolist(), mc_rmse=float(rmse),
                                 mc_bias_vs_R0=float(np.linalg.norm(est.mean(0) - R0)))
json.dump(res, open(os.path.join(os.path.dirname(__file__), 'v_F202.json'), 'w'), indent=1)
