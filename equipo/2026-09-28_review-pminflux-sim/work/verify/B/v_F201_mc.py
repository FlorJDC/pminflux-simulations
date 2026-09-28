# -*- coding: utf-8 -*-
"""Verifier B / F201: MC with the LEGACY pipeline (sim_exp + nMINFLUX + pos_MINFLUX).
Own seed (independent of the worker's 20260825). Usage: python v_F201_mc.py [samples] [seed]"""
import json, os, sys, time
import numpy as np
from v_common import *
import tools.tools_simulations as ts
from tools import ebp as E
from tools import realistic_ebp as R

S = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 777
Ns, Nb, M_p, factor, dt, K = 2000, 95, int(2e5), 1.05, 50, 4
SBR = Ns / Nb
R0 = np.array([-5.07, -7.56])
grid = E.Grid(NPX, PX)
r0_idx = grid.to_index(R0)
RPIX = grid.to_space(r0_idx)
RMAX = 0.75 * L_EFF
ideal = E.ebp_ideal(grid, L=L_EFF, K=4, donut_fwhm=FWHM)
geom = E.ebp_analytic(POS_GEOM, grid, donut_fwhm=FWHM)
real = R.ebp_realistic(realistic_params(), grid)
# sanity: legacy stacks == my stacks up to per-beam scale
for nm, leg, mine in (('ideal', ideal.PSFs, my_stack(ideal_pos(L_EFF))), ('real', real.PSFs, my_realistic_stack(realistic_params()))):
    rr = leg / leg.sum(0) - mine / mine.sum(0)
    print(nm, 'max |p_leg - p_mine| =', np.nanmax(np.abs(rr)))
EB = {'ideal': ideal, 'geom': geom, 'real': real}
cases = [('Ideal', 'ideal', 'ideal'), ('Realista honesta', 'real', 'real'), ('Realista ingenua', 'real', 'ideal')]
if len(sys.argv) > 3:
    cases = [c for c in cases if c[0] in sys.argv[3].split(',')]
configs = {'C0': (0.001, 12.5), 'C3': (4.21, 10.1)}
tau_arr = np.arange(K) / K * dt
out = {'samples': S, 'seed': SEED, 'r_pixel': RPIX.tolist()}
for label, g, e in cases:
    for cn, (tl, b) in configs.items():
        np.random.seed(SEED)  # same seed per config -> paired
        est = np.full((S, 2), np.nan); fails = 0; t0 = time.time()
        for i in range(S):
            rel, _, failed = ts.sim_exp('p_minflux', None, EB[g].PSFs, r0_idx, SBR, Ns, Nb, M_p, tl, factor, dt)
            if failed:
                fails += 1; continue
            n = ts.nMINFLUX(K, tau_arr, rel, 0.0, b)
            idx = ts.pos_MINFLUX(n, EB[e].PSFs, SBR=SBR, px_nm=PX, r_max_nm=RMAX)
            est[i] = grid.to_space(idx)
        v = est[~np.isnan(est[:, 0])]
        bias = v.mean(0) - RPIX
        sd = v.std(0)
        rmse = np.sqrt(0.5 * (sd @ sd + bias @ bias))
        onedge = np.mean(np.hypot(v[:, 0], v[:, 1]) > RMAX - 1.5)
        out[f'{label}|{cn}'] = {'est': v.tolist(), 'bias': bias.tolist(), 'bias_norm': float(np.linalg.norm(bias)),
                                'bias_norm_vs_R0': float(np.linalg.norm(v.mean(0) - R0)),
                                'std': sd.tolist(), 'rmse': float(rmse), 'fails': fails, 'frac_edge': float(onedge)}
        print(f'{label:18s} {cn}: bias {np.round(bias,2)} |b|={np.linalg.norm(bias):.2f} sd {np.round(sd,2)} '
              f'RMSE {rmse:.2f} fails {fails} edge {onedge:.3f}  ({time.time()-t0:.0f}s)', flush=True)
fn = os.path.join(os.path.dirname(__file__), f'v_F201_mc_{SEED}_{S}.json')
json.dump(out, open(fn, 'w'))
