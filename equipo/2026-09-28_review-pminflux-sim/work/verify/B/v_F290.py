# -*- coding: utf-8 -*-
"""Verifier B / F290 discarded suspicions D1, D2, D4, D5, D8 (own checks)."""
import os
import numpy as np
from v_common import *
import tools.tools_simulations as ts
from tools import ebp as E

grid = E.Grid(NPX, PX)
# D5 + D2: integer centering / axis convention on the substitute PSFs
SUB = r'C:\Data\psf\20260703'
sub = E.ebp_experimental(SUB, K=4, grid=grid, reference=0)
for k in range(4):
    am = np.unravel_index(np.argmin(sub.PSFs[k]), sub.PSFs[k].shape)
    print('D5 beam', k, 'argmin->nm', grid.to_space(am), 'pos_nm', sub.pos_nm[k])
ide = E.ebp_ideal(grid, L=L_EFF, K=4, donut_fwhm=FWHM)
for k in range(4):
    am = np.unravel_index(np.argmin(ide.PSFs[k]), ide.PSFs[k].shape)
    print('D2 ideal beam', k, 'argmin', grid.to_space(am), 'pos', np.round(ide.pos_nm[k], 2))
# D1 + D4: sim_exp window fractions at C0 vs 1/K model; failures
np.random.seed(11)
r0 = grid.to_index(np.array([-5.07, -7.56]))
Ns, Nb = 2000, 95
tot = np.zeros(4); fails = 0; R = 300
for i in range(R):
    rel, _, f = ts.sim_exp('p_minflux', None, ide.PSFs, r0, Ns / Nb, Ns, Nb, int(2e5), 0.001, 1.05, 50)
    if f: fails += 1; continue
    tot += ts.nMINFLUX(4, np.arange(4) * 12.5, rel, 0.0, 12.5)
lam = ide.PSFs[:, r0[0], r0[1]]
p = (Ns * lam / lam.sum() + Nb / 4) / (Ns + Nb)
Nt = tot.sum()
z = (tot - Nt * p) / np.sqrt(Nt * p * (1 - p))
print('D1 fails', fails, '/', R, ' D4 photons', Nt, ' z', np.round(z, 2), ' rel dev', np.round(tot / (Nt * p) - 1, 4))
# D1 margin for Ns=90 (N=100 SBR 9): min distinct cycles in 2000 draws of Nh=94
rs = np.random.RandomState(3)
for Nsx in (90, 1440, 2000, 2880):
    Nh = int(Nsx * 1.05)
    m = min(len(np.unique(rs.randint(0, int(2e5), Nh))) for _ in range(2000))
    print('D1 Ns', Nsx, 'min distinct cycles', m, 'margin', m - Nsx)
# D8: crb_minflux p (constant lambda_b) vs MC p (constant SBR) at the pixel
SBR = Ns / Nb
l = ide.PSFs[:, r0[0], r0[1]]; c = ide.PSFs[:, 200, 200]
lb = c.sum() / (4 * SBR)
p_crb = (l + lb) / (4 * lb + l.sum())
p_mc = SBR / (SBR + 1) * l / l.sum() + 1 / ((SBR + 1) * 4)
print('D8 max |p_crb - p_mc| at r0 =', np.abs(p_crb - p_mc).max())
