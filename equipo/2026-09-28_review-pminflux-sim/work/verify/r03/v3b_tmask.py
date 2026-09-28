# -*- coding: utf-8 -*-
"""(2b) t_mask off-fraction with SBR 5: larger runs, both mask phases, several seeds."""
import os, sys, math, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..", "src")))
from pminflux_sim import simulate as sim, psf
pos = psf.beam_positions(4, 100.0, center=True)
lam = psf.lambda_beams(np.array([5.0, -5.0]), pos, 360.0)
M = 1000
out = {}
for name, tm in {"on_first": np.r_[np.ones(500), np.zeros(500)].astype(bool),
                 "off_first": np.r_[np.zeros(500), np.ones(500)].astype(bool),
                 "alt4000": np.r_[np.zeros(2000), np.ones(2000)].astype(bool)}.items():
    for tc in ("none", "earliest"):
        fr = []
        n = 0
        for s in range(5):
            _, tags = sim.simulate_counts(lam, 200, 1000, 5.0, sim.SimParams(tcspc=tc, rate_per_cycle=2.5e-3),
                                          np.random.default_rng(100 + s), return_tags=True, t_mask=tm)
            off = ~tm[tags["cycle"] % tm.size]
            fr.append(off.mean()); n += off.size
        f = float(np.mean(fr)); se = math.sqrt(f * (1 - f) / n)
        out["%s/%s" % (name, tc)] = dict(frac_off=f, se=se, z=(f - 1 / 7.) / se, per_seed=[round(x, 4) for x in fr])
        print(name, tc, out["%s/%s" % (name, tc)])
json.dump(out, open(os.path.join(HERE, "v3b_tmask.json"), "w"), indent=1)
