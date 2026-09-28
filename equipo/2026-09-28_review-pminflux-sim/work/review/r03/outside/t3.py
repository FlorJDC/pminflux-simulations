import numpy as np, pminflux_sim as pm
pos = pm.beam_positions(4, 100.); r0=np.array([-15.,15.]); lam=pm.lambda_beams(r0,pos,360.)
C = pm.mixing_matrix(4.21,50.,4,0.,10.1,irf_fwhm=0.3); p=pm.SimParams(); sbr=21.
mask = np.r_[np.ones(500,bool), np.zeros(500,bool)]   # 50% encendido (parpadeo lento)
c, tags = pm.simulate_counts(lam, 400, 2095, sbr, p, rng=np.random.default_rng(3), return_tags=True, t_mask=mask)
bgfrac = np.mean(tags["source"]==-1); print("fraccion fondo detectada", bgfrac, "-> SBR efectivo", (1-bgfrac)/bgfrac, " (nominal beta", 1/22., ")")
cyc = tags["cycle"]; print("ciclos max", cyc.max(), "frac en ciclos apagados", np.mean(~mask[cyc % mask.size]))
for s in (sbr, (1-bgfrac)/bgfrac):
    e = pm.mle_mixing(c,pos,360.,C,10.1,50.,s,bounds_radius=75.)
    print("sbr usado %.2f"%s, "sesgo", e.r.mean(0)-r0, "SE", e.r.std(0)/np.sqrt(400))
e = pm.mle_mixing(c,pos,360.,C,10.1,50.,sbr,bounds_radius=75., free_bg="shared"); print("free_bg shared", e.r.mean(0)-r0, e.beta)
