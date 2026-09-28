# -*- coding: utf-8 -*-
"""F152 (DESCARTADO) - Suspicions about sim_exp's sampling that do NOT bias the window counts.

 (a) The fast two-step sampler (l.454-465: multinomial over beams, then uniform cycles) is
     claimed equivalent to multinomial(Nh, tile(p/M_p, M_p)) over the K*M_p slots.  Exact by
     factorisation; checked numerically on the occupancy of the slots.
 (b) Background (suspicion v): exactly Nb photons with microtime U[0, dt) (l.559); their cycles
     (l.562-566) are drawn only among cycles without signal and several can share a cycle
     (no TCSPC clip).  The microtimes are drawn independently of the cycles, so the window counts
     of the background are Mult(Nb, (b/dt, ..., b/dt, 1-Kb/dt)) whatever the cycle placement;
     only the returned macrotime trace absTimeBinary is affected (values > 1 possible).  The
     competition a real TCSPC would impose (an earlier background photon hides a signal photon of
     beam k in the same cycle) removes at most (k*dt/K/dt) * Nb/M_p of beam k.
 (c) The modulo-dt fold (l.573) is the periodic model: see the chi2 check in F104
     (p = 0.38 against the periodic mixing matrix at 1e-3 photons/cycle).
Run: python scripts/findings/F152_sampling_and_background_checks.py
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

SEED = 152
K, DT = 4, 50.0
P = np.array([0.12, 0.28, 0.35, 0.25])


def main():
    np.random.seed(SEED)
    out = {}
    # (a) two-step vs full multinomial: distribution of #slots with >= 2 photons, per beam
    M, Nh, reps = 500, 400, 4000
    two, full = np.zeros((reps, K)), np.zeros((reps, K))
    for r in range(reps):
        nk = np.zeros((M, K), int)
        npb = np.random.multinomial(Nh, P)
        for k in range(K):
            np.add.at(nk[:, k], np.random.randint(0, M, npb[k]), 1)
        two[r] = (nk >= 1).sum(0)
        full[r] = (np.random.multinomial(Nh, np.tile(P / M, M)).reshape(M, K) >= 1).sum(0)
    t = [stats.ttest_ind(two[:, k], full[:, k]).pvalue for k in range(K)]
    out["a_occupied_slots_mean_two_step"] = two.mean(0).tolist()
    out["a_occupied_slots_mean_full"] = full.mean(0).tolist()
    out["a_ttest_pvalues"] = [float(x) for x in t]
    # (b) background only: window counts vs Mult(Nb, b/dt) ; absTimeBinary > 1
    psf = P.reshape(K, 1, 1)
    Mp, Ns, Nb = 20000, 200, 2000          # heavy background to make collisions visible
    counts, maxv, ncoll = np.zeros(K), [], 0
    n_calls = 100
    for _ in range(n_calls):
        t_, absT, failed = ts.sim_exp('p_minflux', None, psf, (0, 0), Ns / Nb, Ns, Nb, Mp,
                                      0.001, 1.2, DT)
        assert not failed
        tb = t_[Mp:]                                    # the Nb background microtimes
        counts += ts.nMINFLUX(K, np.arange(K) * DT / K, tb, 0.0, 10.1)
        maxv.append(int(np.max(absT))); ncoll += int(np.sum(absT > 1))
    exp = n_calls * Nb * 10.1 / DT
    chi = float(np.sum((counts - exp) ** 2 / exp))
    out["b_bkg_counts_per_window"] = counts.tolist()
    out["b_bkg_expected_per_window"] = exp
    out["b_chi2_K_dof_pvalue"] = float(stats.chi2.sf(chi, K))
    out["b_absTimeBinary_max"] = int(max(maxv))
    out["b_cycles_with_absTimeBinary_gt1_per_call"] = ncoll / n_calls
    # real-TCSPC competition bound at the studies' rate (Nb = 95 over M_p = 2e5)
    out["b_max_beam_selective_loss_real_TCSPC_studies"] = float((K - 1) / K * 95 / 2e5)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
