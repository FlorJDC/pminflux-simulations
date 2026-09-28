# -*- coding: utf-8 -*-
"""F101 - sim_exp (p_minflux): in a cycle with photons from >=2 beams, Tmicro[m] is
overwritten and the photon of the HIGHEST beam index survives (tools_simulations.py l.511-531).

A real TCSPC keeps the EARLIEST photon of the cycle.  This script only demonstrates the
mechanism and gives the size of the affected population; the rate sweep and its chi2 impact
are quantified by Worker 1 (results/mixing_rate_sweep.json).

Demonstration: a (4,1,1) PSF stack with lambda = [0.12, 0.28, 0.35, 0.25], Tlife = 0.001 ns
(no leakage), Nb = 0, windows a = 0, b = dt/K.  At a high rate (mu = 0.5 photons/cycle) the
window fractions returned by sim_exp are compared with
  (A) the analytic prediction of "highest k wins"  P(max occupied slot = k)
  (B) the analytic prediction of "earliest wins" (real TCSPC, min k for Tlife << dt/K)
  (C) the true beam probabilities p = lambda / sum(lambda).
Run: python scripts/findings/F101_tmicro_overwrite.py
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

SEED = 101
LAM = np.array([0.12, 0.28, 0.35, 0.25])
K, DT = 4, 50.0
TAU_W = np.arange(K) * DT / K


def occupancy_predictions(mu, p):
    """Poisson approximation of slot occupancy: slot k occupied w.p. o_k = 1 - exp(-mu p_k)."""
    o = 1.0 - np.exp(-mu * p)
    hi = np.array([o[k] * np.prod(1 - o[k + 1:]) for k in range(K)])  # highest k wins
    lo = np.array([o[k] * np.prod(1 - o[:k]) for k in range(K)])       # earliest wins
    return hi / hi.sum(), lo / lo.sum(), o


def run(mu, M_p, n_calls, rng_seed):
    np.random.seed(rng_seed)
    psf = LAM.reshape(K, 1, 1)
    Ns = int(0.6 * mu * M_p)          # keep < number of occupied cycles
    factor = 1.0 / 0.6                # Nh = mu * M_p
    tot = np.zeros(K)
    for _ in range(n_calls):
        t, _, failed = ts.sim_exp('p_minflux', None, psf, (0, 0), np.inf, Ns, 0, M_p,
                                  0.001, factor, DT)
        assert not failed
        tot += ts.nMINFLUX(K, TAU_W, t, 0.0, DT / K)
    return tot


def main():
    p = LAM / LAM.sum()
    out = {"p_true": p.tolist()}
    # high rate: mechanism clearly visible
    mu = 0.5
    obs = run(mu, M_p=20000, n_calls=10, rng_seed=SEED)
    f_obs = obs / obs.sum()
    se = np.sqrt(f_obs * (1 - f_obs) / obs.sum())
    hi, lo, o = occupancy_predictions(mu, p)
    out["high_rate"] = {
        "mu_photons_per_cycle": mu, "n_counted": int(obs.sum()),
        "f_observed": f_obs.tolist(), "se": se.tolist(),
        "pred_highest_k_wins": hi.tolist(), "pred_earliest_wins_TCSPC": lo.tolist(),
        "z_vs_highest_k": ((f_obs - hi) / se).tolist(),
        "z_vs_true_p": ((f_obs - p) / se).tolist(),
    }
    # study configuration of the author: Nh = 2100 photons in M_p = 2e5 cycles
    mu_s = 2100 / 2e5
    hi_s, lo_s, o_s = occupancy_predictions(mu_s, p)
    # fraction of occupied cycles with >= 2 beams (Poisson)
    P0 = np.prod(1 - o_s)
    P1 = sum(o_s[k] * np.prod(np.delete(1 - o_s, k)) for k in range(K))
    frac_multi = (1 - P0 - P1) / (1 - P0)
    out["study_rate"] = {
        "mu_photons_per_cycle": mu_s,
        "frac_occupied_cycles_with_ge2_beams": frac_multi,
        "pred_highest_k_wins": hi_s.tolist(),
        "pred_earliest_wins_TCSPC": lo_s.tolist(),
        "max_abs_diff_highest_vs_true_p": float(np.max(np.abs(hi_s - p))),
        "max_rel_diff_highest_vs_true_p": float(np.max(np.abs(hi_s - p) / p)),
    }
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=1))
