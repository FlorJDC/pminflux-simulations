# -*- coding: utf-8 -*-
"""F107 - sim_exp documents t_mask as "binary mask of the blinking dynamics" and says it
"can include blinking dynamics", but in the key='p_minflux' branch the fast two-step sampler
(l.454-466) sets _photons_ready = True and the mask block (l.473-491, "only for cw_minflux /
non-fast path") is skipped: the mask is silently ignored.  The cw_minflux branch still honours it.

Demonstration: emitter OFF during the first half of the experiment (t_mask = 0 for cycles
< M_p/2, 1 afterwards), Nb = 0, M_p = 2e5, dt = 50 ns, Ns = 2000.  We count the signal photons
that sim_exp places in the OFF half (should be 0).
Run: python scripts/findings/F107_tmask_ignored_p_minflux.py
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

SEED = 107
K, DT, MP, NS = 4, 50.0, int(2e5), 2000


def main():
    np.random.seed(SEED)
    psf = np.array([0.12, 0.28, 0.35, 0.25]).reshape(K, 1, 1)
    t_mask = np.ones(MP)
    t_mask[:MP // 2] = 0.0
    out = {}
    for key in ("p_minflux", "cw_minflux"):
        t, absT, failed = ts.sim_exp(key, t_mask.copy(), psf, (0, 0), np.inf, NS, 0, MP,
                                     0.001, 1.05, DT, cycle_time=125000)
        assert not failed
        absT = np.asarray(absT)
        out[key] = {"photons_total": int(absT.sum()),
                    "photons_in_OFF_half": int(absT[:MP // 2].sum()),
                    "frac_in_OFF_half": float(absT[:MP // 2].sum() / absT.sum())}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
