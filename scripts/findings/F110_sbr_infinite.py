# -*- coding: utf-8 -*-
"""F110 - The no-background limit is not representable: with SBR = inf,
SBR/(SBR+1) = inf/inf = NaN in pos_MINFLUX (l.1041) and crb_minflux (l.649, l.653), so
  * pos_MINFLUX turns the NaN likelihood into -inf everywhere (l.1050) and argmax returns the
    first pixel, (row, col) = (0, 0) = the top-left corner of the FOV, without any warning;
  * crb_minflux returns NaN everywhere.
(With Nb = 0 the natural SBR = Ns/Nb raises ZeroDivisionError for Python ints, so the only way
to request the standard 'no background' check is SBR = np.inf.)  A large finite SBR works, which
shows the limit itself is fine and the failure is only the inf/inf expression.
Scenario: ideal TCP beams(K=4, L=100), fwhm 360, grid 200 nm / 1 nm, emitter (5, -5),
exact expected counts 1000 * p (no noise).
Run: python scripts/findings/F110_sbr_infinite.py
"""
import os
import sys
import json
import warnings

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402

K, L, SIZE, PX = 4, 100.0, 200.0, 1.0


def main():
    warnings.simplefilter("ignore")
    pos = ts.beams(K, L, center=True, d='donut')
    PSF = np.array([ts.psf(pos[i], SIZE, PX, [0, 0], d='donut') for i in range(K)])
    r0 = np.array([5.0, -5.0])
    i0 = ts.spaceToIndex(r0, SIZE, PX)
    lam = PSF[:, i0[0], i0[1]]
    n = 1000 * lam / lam.sum()
    out = {}
    for sbr in (np.inf, 1e12):
        idx = ts.pos_MINFLUX(n, PSF, sbr, px_nm=PX, r_max_nm=0.75 * L)
        crb = ts.crb_minflux(K, PSF, sbr, PX, SIZE, 1000, method='1')
        out["SBR=%g" % sbr] = {"estimate_nm": ts.indexToSpace(idx, SIZE, PX).tolist(),
                               "estimate_index": [int(idx[0]), int(idx[1])],
                               "crb_at_emitter_nm": float(crb[i0[0], i0[1]]),
                               "crb_all_nan": bool(np.all(np.isnan(crb)))}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
