# -*- coding: utf-8 -*-
"""(2b) Source of the small residual bias of the mixing MLE on simulated data: multinomial vs
own sim with tcspc='none' vs own sim earliest (2.5e-3, d=22) vs earliest d=50 (exact null), 20000 locs each."""
import sys, os, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mysim import stream, my_C
from myest import qbeams, model_mix, mle, asym_mle, first_order_fracs, T, K
A, B, TAU = 0.0, 10.1, 4.21
NL = 20000; CH = 5000
out = []
rng = np.random.default_rng(2718)
for (r0, Nb) in [((0.0, -30.0), 95), ((20.0, 0.0), 333), ((5.0, -5.0), 333)]:
    r0 = np.array(r0); Ns = 2000; N = Ns + Nb; sbr = Ns / Nb
    C = my_C(TAU, A, B, None); pm = model_mix(C, B, sbr); q = qbeams(*r0)
    beta = 1 / (sbr + 1)
    # full-cycle multinomial: K windows + outside
    pw = (1 - beta) * C.dot(q) + beta * B / T
    pfull = np.r_[pw, 1 - pw.sum()]
    res = {"pos": r0.tolist(), "sbr": sbr}
    for src in ("multinomial", "none", "earliest_d22", "earliest_d50"):
        cnt = []
        for c0 in range(0, NL, CH):
            if src == "multinomial":
                cnt.append(rng.multinomial(N, pfull, size=CH)[:, :K])
                continue
            tc, d = ("none", 0.0) if src == "none" else ("earliest", 22.0 if src.endswith("22") else 50.0)
            st = stream(q, sbr, 2.5e-3, int(CH * N / 2.5e-3 * 1.03) + 10000, rng, irf=0.0, d=d, tcspc=tc)
            m = st["micro"][: CH * N].reshape(CH, N)
            cnt.append(np.stack([(np.mod(m - i * T / K, T) < B).sum(1) for i in range(K)], 1))
        cnt = np.vstack(cnt)
        x, y, _ = mle(cnt, pm)
        dx, dy = x - r0[0], y - r0[1]
        f = cnt.sum(0) / cnt.sum()
        pid = pm(*r0)
        res[src] = dict(bias=[dx.mean(), dy.mean()], se=[dx.std() / math.sqrt(NL), dy.std() / math.sqrt(NL)],
                        frac_rel_dev=((f - pid) / pid).tolist(),
                        implied_asym_bias=(asym_mle(f, pm, r0) - r0).tolist())
        print(r0, round(sbr, 2), src, np.round(res[src]["bias"], 4), np.round(res[src]["se"], 4),
              "rel dev", np.round(res[src]["frac_rel_dev"], 5), "implied", np.round(res[src]["implied_asym_bias"], 4), flush=True)
    ffr, fid = first_order_fracs(q, sbr, 2.5e-3, 22.0, TAU, 0.0, A, B)
    res["first_order_rel_dev_d22"] = ((ffr - fid) / fid).tolist()
    res["first_order_implied_bias_d22"] = (asym_mle(ffr, pm, r0) - r0).tolist()
    print("  first-order rel dev", np.round(res["first_order_rel_dev_d22"], 5), "implied", np.round(res["first_order_implied_bias_d22"], 4))
    out.append(res)
json.dump(out, open(os.path.join(HERE, "v6_residual_bias.json"), "w"), indent=1)
