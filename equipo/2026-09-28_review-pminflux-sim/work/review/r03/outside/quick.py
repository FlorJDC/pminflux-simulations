import numpy as np
import pminflux_sim as pm

pos = pm.beam_positions(4, 100.0)                            # TCP: haz central + 3 en un círculo de L = 100 nm
C = pm.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, irf_fwhm=0.3) # C[i, j] = P(fotón del haz j cae en la ventana i)
r0 = np.array([5.0, -5.0])                                   # emisor (nm), continuo
lam = pm.lambda_beams(r0, pos, 360.0)                        # excitación de cada haz (dona, fwhm 360 nm)

params = pm.SimParams()          # setup medido: tau 4.21, ventana [0, 10.1], IRF 0.3, d = 22, 2.5e-3/ciclo
counts, tags = pm.simulate_counts(lam, 500, 2095, 2000 / 95., params,
                                  rng=np.random.default_rng(1), return_tags=True)

# con datos reales se parte de los microtiempos (ns) y del id de localización de cada fotón:
counts = pm.count_windows(tags["microtime_ns"], T=50.0, K=4, a=0.0, b=10.1,
                          macro_index=tags["loc"], n_loc=500)

est = pm.mle_mixing(counts, pos, 360.0, C, 10.1, 50.0, 2000 / 95., bounds_radius=75.0)
leg = pm.mle_legacy(counts, pos, 360.0, 2000 / 95., bounds_radius=75.0)   # Ec. 3.5, para comparar
sigma = pm.crb(r0, pos, 360.0, C, 10.1, 50.0, 2000 / 95., 2095)          # CRB por eje (nm)

print(est.r.mean(0) - r0, leg.r.mean(0) - r0, sigma, est.boundary_fraction, est.n_failed)
print(pm.__file__, pm.__version__, params)
print(C[0,0], C[1,0], np.diag(C))
