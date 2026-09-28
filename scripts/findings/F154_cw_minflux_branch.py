# -*- coding: utf-8 -*-
"""F154 (DESCARTADO as a bug; limitation noted) - Suspicion (ix): the cw_minflux branch of sim_exp.
In cw-MINFLUX the beam is encoded in the MACROtime (position inside the cw cycle), not in the
microtime: sim_exp gives Tmicro = Exp(Tlife) only (l.531), so nMINFLUX cannot be used on it (all
photons fall in window 0).  Recovering the beam from absTimeBinary (the only per-cycle output),
beam = floor((m mod n_c) / (n_c/K)) with n_c = cycle_time/dt, the counts follow the model
p = s q + (1-s)/K.  This script checks it (chi2), and that t_mask works here (see F107 for p_minflux).
Also: M_p must be a multiple of cycle_time/dt or np.reshape raises (l.500).
Run: python scripts/findings/F154_cw_minflux_branch.py
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402

SEED = 154
K, DT, CT = 4, 50.0, 125000
LAM = np.array([0.12, 0.28, 0.35, 0.25])


def main():
    np.random.seed(SEED)
    psf = LAM.reshape(K, 1, 1)
    Mp, Ns, Nb = int(2e5), 2000, 200
    nc = int(CT / DT)
    tot = np.zeros(K)
    win0 = 0.0
    for _ in range(40):
        t, absT, failed = ts.sim_exp('cw_minflux', None, psf, (0, 0), Ns / Nb, Ns, Nb, Mp,
                                     4.21, 1.05, DT, cycle_time=CT)
        assert not failed
        absT = np.asarray(absT)
        m = np.repeat(np.arange(Mp), absT.astype(int))
        beam = ((m % nc) // (nc // K)).astype(int)
        tot += np.bincount(beam, minlength=K)
        n = ts.nMINFLUX(K, np.arange(K) * DT / K, t[t > 0], 0.0, DT / K)
        win0 += n[0] / n.sum()
    s = (Ns / Nb) / (Ns / Nb + 1)
    p = s * LAM / LAM.sum() + (1 - s) / K
    N = tot.sum()
    chi = float(np.sum((tot - N * p) ** 2 / (N * p)))
    out = {"counts_from_macrotime": tot.tolist(), "expected": (N * p).tolist(),
           "chi2_pvalue": float(stats.chi2.sf(chi, K - 1)),
           "nMINFLUX_fraction_in_window0": win0 / 40}
    try:
        ts.sim_exp('cw_minflux', None, psf, (0, 0), 10, Ns, Nb, Mp + 1000, 4.21, 1.05, DT,
                   cycle_time=CT)
        out["M_p_not_multiple"] = "no error"
    except ValueError as e:
        out["M_p_not_multiple"] = "ValueError: %s" % str(e)[:80]
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
