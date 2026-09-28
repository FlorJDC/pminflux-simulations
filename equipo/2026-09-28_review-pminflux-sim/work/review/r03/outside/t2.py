import numpy as np, pminflux_sim as pm
K=4; dt=25.; Tlife=0.001; SBR=9.; L=100; r0=np.array([5.,-5.])
pos = pm.beam_positions(K, L, True); lam = pm.lambda_beams(r0, pos, 360.0); b=dt/K
p_leg = pm.SimParams(T=dt, K=K, tau=Tlife, irf_fwhm=0.0, a=0.0, b=b, rate_per_cycle=90*1.05/2e5, dead_time=0.0, tcspc="highest", counting="legacy")
c1 = pm.simulate_counts(lam, 100, 100, SBR, p_leg, rng=np.random.default_rng(0))
C0 = pm.mixing_matrix(Tlife, dt, K, 0.0, b, irf_fwhm=0.0); print(np.round(C0,4))
C3 = pm.mixing_matrix(Tlife, dt, K, 0.0, b, irf_fwhm=0.3); print(np.round(C3,4)); print(np.linalg.eigvals(C3))
for C in (C0,C3):
    e = pm.mle_mixing(c1, pos, 360., C, b, dt, SBR, bounds_radius=50.)
    err=e.r-r0; print("2D", np.sqrt(0.5*np.nanmean((err**2).sum(1))), "fail", e.n_failed, "conv", e.converged.sum(), "niter", np.max(e.n_iter))
# periodic legacy-like 
p2 = pm.SimParams(T=dt, K=K, tau=Tlife, irf_fwhm=0.0, a=0.0, b=b, rate_per_cycle=90*1.05/2e5, dead_time=0.0, tcspc="highest")
c2 = pm.simulate_counts(lam, 100, 100, SBR, p2, rng=np.random.default_rng(0))
e = pm.mle_mixing(c2, pos, 360., C0, b, dt, SBR, bounds_radius=50.); err=e.r-r0
print("periodic 2D", np.sqrt(0.5*np.nanmean((err**2).sum(1))), "fail", e.n_failed)
e = pm.mle_legacy(c2, pos, 360., SBR, bounds_radius=50.); err=e.r-r0
print("periodic leg 2D", np.sqrt(0.5*np.nanmean((err**2).sum(1))), "fail", e.n_failed)
