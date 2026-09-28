# -*- coding: utf-8 -*-
"""(2) Own reproduction of results/compare_legacy_vs_v2.json: own simulator (earliest, d=22, 2.5e-3),
own estimators (legacy Eq.3.5 = naive model; mixing model with known C), own CRBs. Different seed."""
import sys, os, json, time, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mysim import stream, counts_periodic, my_C
from myest import qbeams, model_mix, model_naive, crb, mle, asym_mle, first_order_fracs, T, K

POS5 = [(5, -5), (-5.07, -7.56), (20, 0), (-15, 15), (0, -30)]
A, B, TAU, RATE, DEAD = 0.0, 10.1, 4.21, 2.5e-3, 22.0
NLOC = 2000
out = []
ss = np.random.SeedSequence(8675309)
seeds = iter(ss.spawn(40))
for irf in (0.0, 0.3):
    C = my_C(TAU, A, B, irf if irf else None)
    for Nb in (95, 333):
        Ns = 2000; N = Ns + Nb; sbr = Ns / Nb
        pm, pn = model_mix(C, B, sbr), model_naive(sbr)
        for r0 in POS5:
            t0 = time.time()
            r0 = np.array(r0, float); q = qbeams(*r0)
            rng = np.random.default_rng(next(seeds))
            ncyc = int(NLOC * N / RATE * 1.03) + 10000
            st = stream(q, sbr, RATE, ncyc, rng, irf=irf, d=DEAD, tcspc="earliest")
            m = st["micro"][: NLOC * N].reshape(NLOC, N)
            cnt = np.stack([(np.mod(m - (i * T / K + A), T) < B).sum(1) for i in range(K)], 1)
            ptrue = pm(*r0)
            Nw = N * ((1 - 1 / (sbr + 1)) * C.sum(0).mean() + 1 / (sbr + 1) * K * B / T)
            crb_mix = crb(pm, r0, Nw); crb_leg = crb(pn, r0, N)
            asym_leg = np.hypot(*(asym_mle(ptrue, pn, r0) - r0))
            # first-order finite-rate fractions -> asymptotic bias of the mixing MLE
            f_fr, f_id = first_order_fracs(q, sbr, RATE, DEAD, TAU, irf, A, B)
            asym_mix_fr = asym_mle(f_fr, pm, r0) - r0
            row = dict(irf=irf, sbr=round(sbr, 3), pos=r0.tolist(), N=N, Nwin_mean=float(cnt.sum(1).mean()),
                       Nwin_expected=Nw, crb_mix=crb_mix, crb_minflux=crb_leg, crb_ratio=crb_mix / crb_leg,
                       asym_bias_legacy=asym_leg, asym_bias_mix_finite_rate=asym_mix_fr.tolist(),
                       frac_rel_dev_finite_rate=((f_fr - f_id) / f_id).tolist())
            for name, pf in (("legacy", pn), ("mix", pm)):
                x, y, onb = mle(cnt, pf)
                dx, dy = x - r0[0], y - r0[1]
                bx, by = dx.mean(), dy.mean()
                rmse = math.sqrt(np.mean(dx ** 2 + dy ** 2))
                row[name] = dict(bias=[bx, by], bias_se=[dx.std() / math.sqrt(NLOC), dy.std() / math.sqrt(NLOC)],
                                 absb=math.hypot(bx, by), sx=dx.std(), sy=dy.std(), rmse2d=rmse,
                                 rmse_over_crb=rmse / (math.sqrt(2) * crb_mix), boundary=float(onb.mean()))
            row["sec"] = time.time() - t0
            out.append(row)
            print("irf %.1f sbr %5.2f %-14s Nw %.0f crb %.3f/%.3f (x%.4f) asymL %.3f | leg |b| %.3f R/C %.3f | mix b (%+.3f±%.3f,%+.3f±%.3f) R/C %.3f | fr-bias %s %.0fs" % (
                irf, sbr, tuple(r0), row["Nwin_mean"], crb_mix, crb_leg, crb_mix / crb_leg, asym_leg,
                row["legacy"]["absb"], row["legacy"]["rmse_over_crb"], row["mix"]["bias"][0], row["mix"]["bias_se"][0],
                row["mix"]["bias"][1], row["mix"]["bias_se"][1], row["mix"]["rmse_over_crb"],
                np.round(asym_mix_fr, 3), row["sec"]))
json.dump(out, open(os.path.join(HERE, "v5_compare.json"), "w"), indent=1)
