# -*- coding: utf-8 -*-
"""Verifier B / F201 efficiency sweep subset (ideal, SBR 9, r0=(5,-5)), legacy pipeline, own seed."""
import json, os
import numpy as np
from v_common import *
import tools.tools_simulations as ts
from tools import ebp as E

grid = E.Grid(NPX, PX)
ide = E.ebp_ideal(grid, L=L_EFF, K=4, donut_fwhm=FWHM)
r0 = np.array([5., -5.]); ri = grid.to_index(r0); rp = grid.to_space(ri)
SBR, S = 9.0, 400
tau = np.arange(4) / 4 * 50
res = {}
for N in (100, 1600):
    Ns = int(round(SBR / (SBR + 1) * N)); Nb = N - Ns
    crb = ts.crb_minflux(4, ide.PSFs, SBR, PX, SIZE, N)[ri[0], ri[1]]
    for cn, (tl, b) in {'C0': (0.001, 12.5), 'C3': (4.21, 10.1)}.items():
        np.random.seed(2024)
        est = []
        for i in range(S):
            rel, _, f = ts.sim_exp('p_minflux', None, ide.PSFs, ri, SBR, Ns, Nb, int(2e5), tl, 1.05, 50)
            n = ts.nMINFLUX(4, tau, rel, 0.0, b)
            est.append(grid.to_space(ts.pos_MINFLUX(n, ide.PSFs, SBR=SBR, px_nm=PX, r_max_nm=0.75 * L_EFF)))
        est = np.array(est); bb = est.mean(0) - rp; sd = est.std(0)
        rmse = np.sqrt(0.5 * (sd @ sd + bb @ bb))
        res[f'{N}|{cn}'] = dict(crb=float(crb), rmse=float(rmse), ratio=float(rmse / crb), bias=bb.tolist())
        print(N, cn, 'CRB %.3f RMSE %.3f ratio %.2f +- %.2f(printed-style) bias %s' % (crb, rmse, rmse / crb, rmse / crb / np.sqrt(2 * S), np.round(bb, 2)), flush=True)
json.dump(res, open(os.path.join(os.path.dirname(__file__), 'v_F201_eff.json'), 'w'), indent=1)
