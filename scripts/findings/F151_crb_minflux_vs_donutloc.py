# -*- coding: utf-8 -*-
"""F151 (DESCARTADO) - Suspicion (vii): crb_minflux could disagree with an independent Fisher/CRB.
Check: crb_minflux methods 1, 2 and 3 (grid gradients, np.gradient with spacing (-dy, dx)) vs
donutloc.fisher.crb (independently verified package, analytic model + centred differences
h = 1e-3 nm), same model: TCP beams(K=4, L=100) (legacy convention), LG doughnut fwhm = 360
(Eq. S17 in both codes), SBR = 21.05, N = 2095.  Also checks the claim of l.602-607 that
lambda_b is a constant (does not depend on the central pixel).
Run: python scripts/findings/F151_crb_minflux_vs_donutloc.py
"""
import os
import sys
import io
import json
import contextlib

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "donut-beam-localization", "src"))
from tools import tools_simulations as ts  # noqa: E402
from donutloc import beams, photons, fisher  # noqa: E402

K, L, SBR, N = 4, 100.0, 2000 / 95, 2095


def main():
    pos = np.array([ts.beams(K, L, center=True, d='donut')[i] for i in range(K)], dtype=float)
    p_fn = photons.make_model(pos, beams.make_beam("donut", fwhm=360.0), sbr=SBR)
    out = {}
    pts = [(5.0, -5.0), (20.0, 0.0), (-15.0, 15.0), (0.0, -30.0), (30.0, 30.0)]
    for size, px in ((200.0, 1.0), (100.0, 0.5)):
        PSF = np.array([ts.psf(pos[i], size, px, [0, 0], d='donut') for i in range(K)])
        c1 = ts.crb_minflux(K, PSF, SBR, px, size, N, method='1')
        with contextlib.redirect_stdout(io.StringIO()):
            c2 = ts.crb_minflux(K, PSF, SBR, px, size, N, method='2')[0]
            c3 = ts.crb_minflux(K, PSF, SBR, px, size, N, method='3')[0]
        rel = {"m1": [], "m2": [], "m3": []}
        for r in pts:
            if max(abs(r[0]), abs(r[1])) >= size / 2 - 2:
                continue
            i, j = ts.spaceToIndex(r, size, px)
            ref = float(fisher.crb(p_fn, np.array(r), N))
            for key, c in (("m1", c1), ("m2", c2), ("m3", c3)):
                rel[key].append(float(c[i, j] / ref - 1))
        out["grid_%gnm_px%g" % (size, px)] = {k: {"max_abs_rel_diff": float(np.max(np.abs(v))),
                                                  "rel_diffs": v} for k, v in rel.items()}
        # lambda_b constancy: sum_i lambda_i must be N*SBR/(SBR+1) on the whole grid
        lam = N * (SBR / (SBR + 1)) * PSF / np.sum(PSF, axis=0)
        s = lam.sum(axis=0)
        out["grid_%gnm_px%g" % (size, px)]["sum_lambda_rel_spread"] = \
            float((s.max() - s.min()) / s.mean())
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
