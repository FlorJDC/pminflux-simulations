# Traducción de simulations_example.py usando sólo el README
import numpy as np, time, warnings
import pminflux_sim as pm
K=4; dt=25.; Tlife=0.001; Ns=90; Nb=10; SBR=Ns/Nb; L=100; r0=np.array([5.,-5.]); samples=100
M_p=int(2e5); factor=1.05
pos = pm.beam_positions(K, L, True)
lam = pm.lambda_beams(r0, pos, 360.0)
b = dt/K
rate = Ns*factor/M_p   # README: rate_per_cycle = fotones incidentes por ciclo (lo deduzco)
t0=time.time()
# 1) "como el legado": tcspc highest, sin IRF, sin tiempo muerto, conteo legacy
p_leg = pm.SimParams(T=dt, K=K, tau=Tlife, irf_fwhm=0.0, a=0.0, b=b, rate_per_cycle=rate,
                     dead_time=0.0, tcspc="highest", counting="legacy")
try:
    c1 = pm.simulate_counts(lam, samples, Ns+Nb, SBR, p_leg, rng=np.random.default_rng(0))
    print("legacy-like ok", c1.sum(1)[:5])
except Exception as e:
    print("legacy-like FAIL:", type(e).__name__, e)
# 2) física
p = pm.SimParams(T=dt, K=K, tau=Tlife, a=0.0, b=b, rate_per_cycle=rate)
c = pm.simulate_counts(lam, samples, Ns+Nb, SBR, p, rng=np.random.default_rng(0))
C = pm.mixing_matrix(Tlife, dt, K, 0.0, b, irf_fwhm=p.irf_fwhm)
for name,cc in [("physical",c)]+([("legacylike",c1)] if 'c1' in dir() else []):
    est = pm.mle_mixing(cc, pos, 360.0, C, b, dt, SBR, bounds_radius=L/2)
    leg = pm.mle_legacy(cc, pos, 360.0, SBR, bounds_radius=L/2)
    for n2,e in [("mix",est),("leg",leg)]:
        err = e.r - r0
        print(name, n2, "mean", e.r.mean(0), "2D error", np.sqrt(0.5*np.mean((err**2).sum(1))), "fail", e.n_failed, "bnd", e.boundary_fraction)
print("crb", pm.crb(r0,pos,360.,C,b,dt,SBR,Ns+Nb), pm.crb_legacy(r0,pos,360.,SBR,Ns+Nb))
print("t", time.time()-t0)
