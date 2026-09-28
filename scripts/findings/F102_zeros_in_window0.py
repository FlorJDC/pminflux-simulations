# -*- coding: utf-8 -*-
"""F102 - sim_exp returns the microtimes of ALL M_p cycles, with an exact 0.0 for every cycle
without a signal photon (Tmicro = np.zeros(M_p), l.517; concatenated at l.569).  nMINFLUX
(l.994-996) only excludes them because the window-0 lower edge is a STRICT inequality with
a = 0 (relTime > tau_0 + a = 0).  Any window that opens before the pulse (a < 0, the natural
choice when there is an IRF / pulse-arrival jitter) counts every empty cycle in window 0.

Scenario (the author's study configuration, simulation_misalignment.py): TCP of beams(K=4,
L=100, center=True), doughnut fwhm = 360 nm, grid 400 nm / 1 nm, emitter (5, -5) nm,
Ns = 2000, Nb = 95, M_p = 2e5, Tlife = 0.001 ns, dt = 50 ns; estimator pos_MINFLUX with
r_max_nm = 0.75 L.  Windows: b = dt/K = 12.5 ns and a = 0 vs a = -0.25 ns.
Run: python scripts/findings/F102_zeros_in_window0.py
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

SEED = 102
K, L, SIZE, PX, DT = 4, 100.0, 400.0, 1.0, 50.0
NS, NB, MP, TLIFE, FACTOR = 2000, 95, int(2e5), 0.001, 1.05
R0_NM = np.array([5.0, -5.0])


def tcp_psfs():
    pos = ts.beams(K, L, center=True, d='donut')
    return np.array([ts.psf(pos[i], SIZE, PX, [0, 0], d='donut') for i in range(K)])


def main(n_rep=20):
    np.random.seed(SEED)
    PSF = tcp_psfs()
    r0 = ts.spaceToIndex(R0_NM, SIZE, PX)
    tau = np.arange(K) * DT / K
    SBR = NS / NB
    res = {"a0": {"n": [], "est": []}, "a_neg": {"n": [], "est": []}}
    nzeros = []
    for _ in range(n_rep):
        t, _, failed = ts.sim_exp('p_minflux', None, PSF, r0, SBR, NS, NB, MP, TLIFE, FACTOR, DT)
        assert not failed
        nzeros.append(int(np.sum(t == 0.0)))
        for key, a in (("a0", 0.0), ("a_neg", -0.25)):
            n = ts.nMINFLUX(K, tau, t, a, DT / K)
            idx = ts.pos_MINFLUX(n, PSF, SBR, px_nm=PX, r_max_nm=0.75 * L)
            res[key]["n"].append(n.tolist())
            res[key]["est"].append(ts.indexToSpace(idx, SIZE, PX).tolist())
    out = {"n_exact_zeros_in_relTime_mean": float(np.mean(nzeros)),
           "len_relTime": MP + NB}
    for key, a in (("a0", 0.0), ("a_neg", -0.25)):
        n = np.array(res[key]["n"]); e = np.array(res[key]["est"])
        out[key] = {"a_ns": a, "mean_counts": n.mean(0).tolist(),
                    "mean_estimate_nm": e.mean(0).tolist(),
                    "mean_error_nm": float(np.mean(np.hypot(*(e - R0_NM).T))),
                    "frac_estimates_on_search_boundary":
                        float(np.mean(np.hypot(*e.T) > 0.75 * L - 1.0))}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
