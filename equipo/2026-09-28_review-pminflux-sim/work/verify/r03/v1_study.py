# -*- coding: utf-8 -*-
"""(1) Own reproduction of results/study_v2.json (known-power mixing, legacy Eq.3.5, naive ideal geometry).
Own photon-stream simulator (r02/mysim: earliest TCSPC, d=22, IRF 0.3, 2.5e-3/cycle), own MLE, own CRB.
Different seed. Fixed N = consecutive blocks of N recorded photons."""
import os, sys, json, time, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "r02"))
from mysim import stream, my_C
from myest import mle, crb
from vgeo import (T, K, POS_MEAS, POWERS, POSITIONS, ring, naive_geom, q_of, model_mix, model_legacy,
                  captured)

A, B, TAU, IRF, RATE, DEAD = 0.0, 10.1, 4.21, 0.3, 2.5e-3, 22.0
NS, NB = 2000, 95
SBR = NS / NB
C = my_C(TAU, A, B, IRF)
pos_ideal = ring(100.0)
pos_naive, Leff, phi = naive_geom(POS_MEAS)
print("naive L_eff %.4f phi %.5f" % (Leff, phi))
GEOMS = {"ideal": (pos_ideal, np.ones(4), pos_ideal), "desalineada": (POS_MEAS, POWERS, pos_naive)}
ss = np.random.SeedSequence(31415926)
seeds = iter(ss.spawn(200))


def run(N, nloc):
    res = {}
    for g, (pos, pw, pnaive) in GEOMS.items():
        ests = {"mix_known": model_mix(pos, pw, C, B, SBR),
                "legacy": model_legacy(pos, pw, SBR)}
        if g == "desalineada":
            ests["naive"] = model_mix(pnaive, np.ones(4), C, B, SBR)
        pm = ests["mix_known"]
        rows = {e: [] for e in ests}
        for r0 in POSITIONS:
            r0 = np.array(r0, float)
            q = q_of(r0[0], r0[1], pos, pw)
            rng = np.random.default_rng(next(seeds))
            ncyc = int(nloc * N / RATE * 1.04) + 20000
            st = stream(q, SBR, RATE, ncyc, rng, irf=IRF, d=DEAD, tcspc="earliest")
            assert st["micro"].size >= nloc * N
            m = st["micro"][: nloc * N].reshape(nloc, N)
            cnt = np.stack([(np.mod(m - (i * T / K + A), T) < B).sum(1) for i in range(K)], 1)
            sig = crb(pm, r0, N * captured(C, B, SBR))
            for e, pf in ests.items():
                x, y, onb = mle(cnt, pf)
                d = np.c_[x, y] - r0
                bias = d.mean(0)
                rmse = math.sqrt(np.mean(np.sum(d ** 2, 1)))
                rows[e].append(dict(bias=float(np.hypot(*bias)), rmse=rmse, crb=sig,
                                    ratio=rmse / (math.sqrt(2) * sig), edge=float(onb.mean())))
        for e, rr in rows.items():
            res["%s/%s" % (g, e)] = dict(max_bias=max(r["bias"] for r in rr),
                                         mean_ratio=float(np.mean([r["ratio"] for r in rr])),
                                         edge=float(np.mean([r["edge"] for r in rr])),
                                         crb=[round(r["crb"], 3) for r in rr],
                                         bias=[round(r["bias"], 3) for r in rr])
            print(N, g, e, json.dumps(res["%s/%s" % (g, e)]))
            sys.stdout.flush()
    return res


t0 = time.time()
out = {"L_eff": Leff, "phi": phi, "main": run(NS + NB, 400)}
out["sweep"] = {str(N): run(N, 200) for N in (100, 400, 1600)}
out["runtime"] = time.time() - t0
json.dump(out, open(os.path.join(HERE, "v1_study.json"), "w"), indent=1)
print("runtime", out["runtime"])
