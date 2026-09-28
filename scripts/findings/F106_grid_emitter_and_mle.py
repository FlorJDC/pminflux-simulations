# -*- coding: utf-8 -*-
"""F106 - Everything lives on the PSF pixel grid:
  * sim_exp takes the emitter as a pixel INDEX (lambda = psf[i, r0[0], r0[1]], l.444), so a
    continuous emitter position is silently snapped to the nearest node (spaceToIndex, l.93-106);
  * pos_MINFLUX returns the argmax over the same grid (l.1099), px = 1 nm in all studies.
Consequences demonstrated here:
  (a) snapping: the author's emitter (-5.07, -7.56) nm (simulation_misalignment.py R0_NM) is
      simulated at (-5, -8) nm; the MC mean converges to the node, so a bias computed against
      R0_NM contains a spurious 0.45 nm (the script that does that is audited by Worker 3);
  (b) quantization: with the emitter ON a node the grid MLE is super-efficient when the CRB is
      below ~px/2 (RMSE < CRB), and with the emitter OFF a node it adds ~px^2/12 per axis plus a
      deterministic rounding bias.  The author already identified the px^2/12 term (docx 6.3).
Geometry: ideal TCP beams(K=4, L=100), fwhm 360, grid 200 nm / 1 nm, SBR = 21.05 (Ns/Nb = 2000/95).
Counts for (b) are drawn from the multinomial law with the pos_MINFLUX model, which is exact for
the studies' configuration (Tlife = 0.001, a = 0, b = dt/K; see F104 MC check).
Run: python scripts/findings/F106_grid_emitter_and_mle.py
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

SEED = 106
K, L, SIZE, PX, DT = 4, 100.0, 200.0, 1.0, 50.0
NS, NB = 2000, 95
SBR = NS / NB
POS = np.array([ts.beams(K, L, center=True, d='donut')[i] for i in range(K)], dtype=float)


def p_model(r):
    lam = ts.doughnut(np.hypot(r[0] - POS[:, 0], r[1] - POS[:, 1]))
    s = SBR / (SBR + 1)
    return s * lam / lam.sum() + (1 - s) / K


def crb(r, N, h=1e-4):
    g = [(p_model(r + d) - p_model(r - d)) / (2 * h) for d in (np.array([h, 0]), np.array([0, h]))]
    p = p_model(r)
    F = N * np.array([[np.sum(a * b / p) for b in g] for a in g])
    return float(np.sqrt(0.5 * np.trace(np.linalg.inv(F))))


def main():
    np.random.seed(SEED)
    rng = np.random.default_rng(SEED)
    PSF = np.array([ts.psf(POS[i], SIZE, PX, [0, 0], d='donut') for i in range(K)])
    out = {}
    # (a) snapping in sim_exp
    r_req = np.array([-5.07, -7.56])
    idx = ts.spaceToIndex(r_req, SIZE, PX)
    r_node = ts.indexToSpace(idx, SIZE, PX)
    est = []
    for _ in range(200):
        t, _, failed = ts.sim_exp('p_minflux', None, PSF, idx, SBR, NS, NB, int(2e5), 0.001, 1.05, DT)
        n = ts.nMINFLUX(K, np.arange(K) * DT / K, t, 0.0, DT / K)
        est.append(ts.indexToSpace(ts.pos_MINFLUX(n, PSF, SBR, px_nm=PX, r_max_nm=0.75 * L), SIZE, PX))
    est = np.array(est)
    m, se = est.mean(0), est.std(0, ddof=1) / np.sqrt(len(est))
    out["a_snapping"] = {"requested_nm": r_req.tolist(), "simulated_node_nm": r_node.tolist(),
                         "snap_offset_nm": float(np.hypot(*(r_node - r_req))),
                         "mc_mean_estimate_nm": m.tolist(), "mc_se_nm": se.tolist(),
                         "bias_vs_requested_nm": (m - r_req).tolist(),
                         "bias_vs_node_nm": (m - r_node).tolist(), "n_rep": len(est)}
    # (b) grid quantization of the MLE
    res = {}
    for label, r0 in (("on_node_(5,-5)", np.array([5.0, -5.0])),
                      ("off_node_(5.4,-5.3)", np.array([5.4, -5.3]))):
        for N in (2095, 20950, 104750):
            p = p_model(r0)
            n = rng.multinomial(N, p, size=400)
            e = np.array([ts.indexToSpace(ts.pos_MINFLUX(c, PSF, SBR, px_nm=PX, r_max_nm=0.75 * L),
                                          SIZE, PX) for c in n])
            err = e - r0
            rmse = float(np.sqrt(0.5 * np.mean(np.sum(err ** 2, axis=1))))
            c = crb(r0, N)
            res["%s | N=%d" % (label, N)] = {
                "crb_nm": c, "rmse_nm": rmse, "rmse_over_crb": rmse / c,
                "sheppard_prediction_rmse_nm": float(np.sqrt(c ** 2 + PX ** 2 / 12)),
                "mean_error_nm": err.mean(0).tolist(),
                "frac_exact_hits": float(np.mean(np.all(np.abs(err) < 1e-9, axis=1)))}
    out["b_quantization"] = res
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
