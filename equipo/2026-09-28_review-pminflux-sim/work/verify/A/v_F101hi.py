# -*- coding: utf-8 -*-
import os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, *[".."]*5))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts
K, T = 4, 50.0; TAUS = np.arange(K)*T/K; qq = np.array([0.12, 0.28, 0.35, 0.25])
Ns, fac, Mp = 1000, 1.6, 2000     # Nh=1600 -> 0.8 photons/cycle drawn
np.random.seed(1011); tot = np.zeros(K); fails = 0
for _ in range(80):
    t, _, f = ts.sim_exp('p_minflux', None, qq.reshape(K,1,1), (0,0), 1e9, Ns, 0, Mp, 0.001, fac, T)
    if f: fails += 1; continue
    tot += ts.nMINFLUX(K, TAUS, t, 0, 12.5)
rng = np.random.default_rng(0); acc = np.zeros(K); acce = np.zeros(K)
for _ in range(4000):
    n = rng.multinomial(int(Ns*fac), qq); occ = 1-(1-1/Mp)**n
    w = np.array([occ[k]*np.prod(1-occ[k+1:]) for k in range(K)]); acc += w/w.sum()
    we = np.array([occ[k]*np.prod(1-occ[:k]) for k in range(K)]); acce += we/we.sum()   # earliest (Tlife<<dt/K)
hi = acc/4000; ea = acce/4000
fo = tot/tot.sum(); se = np.sqrt(fo*(1-fo)/tot.sum())
print("fails", fails, "N", tot.sum()); print("obs", fo); print("highest", hi, "z", (fo-hi)/se)
print("earliest", ea, "z", (fo-ea)/se); print("z vs p", (fo-qq)/se)
