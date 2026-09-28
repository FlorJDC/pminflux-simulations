# -*- coding: utf-8 -*-
"""Ejemplo de punta a punta de pminflux_sim v2 en el setup medido (20 MHz, K = 4).

simular fotones -> contar ventanas desde los microtiempos -> matriz de mezcla C -> MLE con
mezcla y MLE del legado (Ec. 3.5) -> CRB -> tabla.

Setup: T = 50 ns, K = 4, tau = 4.21 ns, ventana [0, 10.1] ns (medidos, datos 20260707);
IRF 0.3 ns FWHM y tiempo muerto 22 ns (SUPUESTOS, no medidos); 2.5e-3 fotones/ciclo;
Ns = 2000, SBR 21 (Nb = 95, N = 2095 detectados en el ciclo completo); TCP L = 100 nm, dona
fwhm 360 nm; disco de búsqueda R = 75 nm.

Uso (desde la raíz):  python scripts/example_end_to_end.py [--n-loc 500] [--seed 1]
Corre en unos segundos.
"""

import argparse
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pminflux_sim as pm  # noqa: E402

T, K, TAU, A, B, IRF, DEAD, RATE = 50.0, 4, 4.21, 0.0, 10.1, 0.3, 22.0, 2.5e-3
NS, NB = 2000, 95
SBR = NS / float(NB)
L, FWHM, R_SEARCH = 100.0, 360.0, 75.0
POSITIONS = [(5.0, -5.0), (-5.07, -7.56), (20.0, 0.0), (-15.0, 15.0)]


def run(n_loc=500, seed=1, verbose=True):
    t0 = time.time()
    pos = pm.beam_positions(K, L, center=True)                   # (4, 2) nm
    params = pm.SimParams(T=T, K=K, tau=TAU, irf_fwhm=IRF, a=A, b=B, rate_per_cycle=RATE,
                          dead_time=DEAD, tcspc="earliest", counting="periodic")
    C = pm.mixing_matrix(TAU, T, K, A, B, irf_fwhm=IRF)          # C[i, j] = P(haz j -> ventana i)
    rows = []
    for i, r0 in enumerate(POSITIONS):
        r0 = np.asarray(r0, float)
        lam = pm.lambda_beams(r0, pos, FWHM)
        rng = np.random.default_rng([seed, i])
        # 1) simular: counts (n_loc, K) y los fotones registrados (microtiempos)
        counts, tags = pm.simulate_counts(lam, n_loc, NS + NB, SBR, params, rng, return_tags=True)
        # 2) contar ventanas desde los microtiempos (lo mismo que se haría con datos reales)
        cw = pm.count_windows(tags["microtime_ns"], T, K, A, B, macro_index=tags["loc"], n_loc=n_loc)
        assert np.array_equal(cw, counts)
        # 3) estimar: MLE con mezcla (C conocida) y MLE del legado (sin fuga)
        mix = pm.mle_mixing(cw, pos, FWHM, C, B, T, SBR, bounds_radius=R_SEARCH)
        leg = pm.mle_legacy(cw, pos, FWHM, SBR, bounds_radius=R_SEARCH)
        # 4) CRB por eje del modelo de mezcla, N = Ns + Nb detectados en el ciclo completo
        s_crb = float(pm.crb(r0, pos, FWHM, C, B, T, SBR, NS + NB))
        for name, est in (("mezcla", mix), ("legado", leg)):
            d = est.r - r0
            bias = d.mean(0)
            rmse = math.sqrt(np.mean(np.sum(d ** 2, 1)))
            rows.append({"r0": tuple(r0), "estimador": name, "bias_abs": float(np.hypot(*bias)),
                         "rmse_2d": rmse, "rmse_over_crb": rmse / (math.sqrt(2) * s_crb),
                         "crb": s_crb, "borde": float(est.boundary_fraction),
                         "n_failed": int(est.n_failed)})
    el = time.time() - t0
    if verbose:
        print("p-MINFLUX v2, setup medido: tau %.2f ns, ventana [%.1f, %.1f] ns, IRF %.1f ns, "
              "tiempo muerto %.0f ns (supuesto), %.1e fot/ciclo, Ns %d, SBR %.1f, %d locs/posición"
              % (TAU, A, A + B, IRF, DEAD, RATE, NS, SBR, n_loc))
        print("C (fila = ventana, columna = haz):")
        print(np.array2string(C, precision=4, suppress_small=True))
        print("%-16s %-8s %8s %8s %8s %9s %6s" % ("r0 (nm)", "estim.", "|b| nm", "RMSE nm",
                                                 "CRB nm", "RMSE/CRB", "borde"))
        for r in rows:
            print("%-16s %-8s %8.3f %8.3f %8.3f %9.3f %6.3f"
                  % ("(%.2f, %.2f)" % r["r0"], r["estimador"], r["bias_abs"], r["rmse_2d"],
                     r["crb"], r["rmse_over_crb"], r["borde"]))
        print("RMSE/CRB = RMSE_2D / (sqrt2 * CRB por eje); 1 = eficiente.  Tiempo: %.1f s" % el)
    return rows, el


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n-loc", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    run(a.n_loc, a.seed)


if __name__ == "__main__":
    main()
