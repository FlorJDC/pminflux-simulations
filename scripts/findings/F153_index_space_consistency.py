# -*- coding: utf-8 -*-
"""F153 (DESCARTADO) - spaceToIndex / indexToSpace (l.93-114) vs the grid that psf() builds.
Checks, for px = 1 and px = 0.5 nm and FOV 400 nm:
  * a donut whose zero is placed at a node (x, y) has its minimum at spaceToIndex((x, y));
  * indexToSpace(spaceToIndex(r)) - r is within +-px/2 for random r (rounding, the author's fix);
  * the old truncation (dtype=int) would err by up to one pixel, always toward lower indices.
Run: python scripts/findings/F153_index_space_consistency.py
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402

SEED = 153


def main():
    rng = np.random.default_rng(SEED)
    out = {}
    for px in (1.0, 0.5):
        size = 400.0
        mism = 0
        for _ in range(20):
            node = np.round(rng.uniform(-150, 150, 2) / px) * px
            d = ts.psf(node, size, px, [0, 0], d='donut')
            imin = np.unravel_index(np.argmin(d), d.shape)
            mism += int(tuple(ts.spaceToIndex(node, size, px)) != tuple(imin))
        r = rng.uniform(-150, 150, (5000, 2))
        back = np.array([ts.indexToSpace(ts.spaceToIndex(x, size, px), size, px) for x in r])
        err = back - r
        # old truncation
        old = np.array([[int((size / 2 - x[1]) / px), int((x[0] + size / 2) / px)] for x in r])
        back_old = np.array([ts.indexToSpace(i, size, px) for i in old])
        out["px=%g" % px] = {"zero_vs_index_mismatches_of_20": mism,
                             "roundtrip_max_abs_err_over_px": float(np.max(np.abs(err)) / px),
                             "roundtrip_mean_err_nm": err.mean(0).tolist(),
                             "old_truncation_mean_err_nm": (back_old - r).mean(0).tolist(),
                             "old_truncation_max_abs_err_over_px":
                                 float(np.max(np.abs(back_old - r)) / px)}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
