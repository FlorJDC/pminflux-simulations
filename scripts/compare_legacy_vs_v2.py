# -*- coding: utf-8 -*-
"""Estudio comparativo: estimador del legado (Ec. 3.5) contra el MLE con matriz de mezcla (v2).

Datos: simulador v2 en dominio temporal (``pminflux_sim.simulate``, fuente ``v2sim``, default) con
el setup medido (tau = 4.21 ns, ventana [0, 10.1] ns, 20 MHz, K = 4, tasa 2.5e-3/ciclo, tiempo
muerto 22 ns, TCSPC 'earliest', conteo periódico, N fijo). Si ``simulate`` no importa, cae a
``multinomial`` (K ventanas + categoría "fuera", probabilidades de ``mixing.window_expected``) y
lo deja registrado. Ns = 2000, Nb = Ns/SBR con SBR 21 y 6, las 5 posiciones de F104, n_loc
localizaciones por caso, IRF 0 (bloque principal) y 0.3 ns (variante).

Estimadores: ``legacy`` (mle_legacy, Ec. 3.5 continua con sbr = Ns/Nb), ``mixing`` (mle_mixing,
C conocida) y ``mixing_freebg`` (C conocida, beta libre por localización).

Por caso y estimador: sesgo vectorial y |b|, sigma_x, sigma_y, RMSE_2D = sqrt(mean |r̂-r|²),
CRB por eje (modelo de mezcla, N = Ns+Nb del ciclo completo), RMSE/CRB = RMSE_2D/(sqrt2 CRB),
SE bootstrap de cada métrica, fracción en el borde y fallas. Además: sesgo asintótico del legado
(conteos esperados), CRB de crb_minflux, y un chequeo cruzado ts.pos_MINFLUX (px = 1) contra
mle_legacy.

Uso (desde la raíz):  python scripts/compare_legacy_vs_v2.py [--source v2sim|multinomial]
                      [--n-loc 2000] [--seed 20260928] [--n-boot 500] [--quick] [--out PATH]
"""

import argparse
import contextlib
import io
import json
import math
import os
import platform
import sys
import time

import numpy as np
import scipy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pminflux_sim import mixing as mx  # noqa: E402
from pminflux_sim import psf  # noqa: E402
from pminflux_sim import estimate as es  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provenance_sha import sha256_file  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "results", "compare_legacy_vs_v2.json")
POSITIONS = [(5.0, -5.0), (-5.07, -7.56), (20.0, 0.0), (-15.0, 15.0), (0.0, -30.0)]
SETUP = dict(T=50.0, K=4, tau=4.21, a=0.0, b=10.1, rate_per_cycle=2.5e-3, dead_time=22.0,
             tcspc="earliest", counting="periodic", n_mode="fixed", beam_powers=None)
GEOM = dict(L=100.0, center=True, fwhm=360.0, kind="donut", bounds_radius=75.0,
            grid_step=75.0 / 12.0)
NS = 2000
NB = {"SBR21": 95, "SBR6": 333}
IRFS = [0.0, 0.3]
F104_LEGACY_BIAS_SBR21 = [0.85, 1.51, 1.63, 2.69, 2.36]


def _sha(path):
    """sha256 con fin de línea normalizado (CRLF -> LF): robusto a git autocrlf."""
    return sha256_file(path)


def _metrics(est, r0, crb_axis, idx=None):
    """Métricas de un arreglo de estimaciones (n, 2); con idx (B, n) devuelve un arreglo por remuestra."""
    e = est if idx is None else est[idx]                   # (n,2) o (B,n,2)
    d = e - r0
    bias = d.mean(-2)
    sd = e.std(-2, ddof=1)
    rmse = np.sqrt(np.mean(np.sum(d ** 2, -1), -1))
    return {"bias_x": bias[..., 0], "bias_y": bias[..., 1],
            "bias_abs": np.hypot(bias[..., 0], bias[..., 1]),
            "sigma_x": sd[..., 0], "sigma_y": sd[..., 1], "rmse_2d": rmse,
            "rmse_over_crb": rmse / (math.sqrt(2.0) * crb_axis)}


def _summ(est, r0, crb_axis, rng, n_boot):
    ok = np.all(np.isfinite(est), axis=1)
    e = est[ok]
    m = _metrics(e, r0, crb_axis)
    idx = rng.integers(0, e.shape[0], size=(n_boot, e.shape[0]))
    mb = _metrics(e, r0, crb_axis, idx)
    out = {}
    for k in m:
        out[k] = float(m[k])
        out[k + "_se"] = float(np.std(mb[k], ddof=1))
    out["bias_vec"] = [out["bias_x"], out["bias_y"]]
    out["n_valid"] = int(ok.sum())
    return out


def _get_simulator(source):
    if source == "multinomial":
        return None, None
    try:
        from pminflux_sim import simulate as sim  # noqa: F401
        return sim, None
    except Exception as exc:  # pragma: no cover - depende de W2
        return None, "%s: %s" % (type(exc).__name__, exc)


def _counts(sim, lam, n_loc, Nb, irf, rng):
    N = NS + Nb
    if sim is not None:
        p = sim.SimParams(T=SETUP["T"], K=SETUP["K"], tau=SETUP["tau"], irf_fwhm=irf,
                          a=SETUP["a"], b=SETUP["b"], rate_per_cycle=SETUP["rate_per_cycle"],
                          dead_time=SETUP["dead_time"], tcspc=SETUP["tcspc"],
                          counting=SETUP["counting"], n_mode=SETUP["n_mode"],
                          beam_powers=SETUP["beam_powers"])
        return np.asarray(sim.simulate_counts(lam, n_loc, N, NS / float(Nb), params=p, rng=rng))
    C = mx.mixing_matrix(SETUP["tau"], SETUP["T"], SETUP["K"], SETUP["a"], SETUP["b"], irf or None)
    e = mx.window_expected(lam, C, SETUP["b"], SETUP["T"], NS, Nb) / float(N)
    pr = np.append(e, max(1.0 - e.sum(), 0.0))
    return rng.multinomial(N, pr / pr.sum(), size=n_loc)[:, :SETUP["K"]]


def _legacy_crosscheck(counts, sbr, pos, n_check):
    """ts.pos_MINFLUX (grilla de 1 nm) contra mle_legacy sobre las mismas cuentas."""
    sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
    import matplotlib
    matplotlib.use("Agg")
    from tools import tools_simulations as ts
    size = 200
    PSF = np.array([ts.psf(pos[i], size, 1, [0, 0], d="donut") for i in range(pos.shape[0])])
    c = counts[:n_check]
    grid = []
    with contextlib.redirect_stdout(io.StringIO()):
        for row in c:
            idx = ts.pos_MINFLUX(row, PSF, sbr, px_nm=1, r_max_nm=GEOM["bounds_radius"])
            grid.append(ts.indexToSpace(idx, size, 1))
    grid = np.array(grid)
    cont = es.mle_legacy(c, pos, GEOM["fwhm"], sbr, GEOM["bounds_radius"]).r
    d = np.abs(grid - cont)
    dist_round = np.abs(grid - np.rint(cont))
    return {"n": int(c.shape[0]), "max_abs_diff_nm": float(d.max()),
            "mean_abs_diff_nm": [float(v) for v in d.mean(0)],
            "frac_within_0.5px_per_axis": float(np.mean(np.all(d <= 0.5 + 1e-9, axis=1))),
            "frac_within_1px_per_axis": float(np.mean(np.all(d <= 1.0 + 1e-9, axis=1))),
            "frac_grid_equals_rounded_continuous": float(np.mean(np.all(dist_round < 1e-9, axis=1))),
            "legacy_grid": "ts.psf(pos_k, 200, 1, [0,0], 'donut'); pos_MINFLUX(px_nm=1, r_max_nm=75)"}


def run(source="v2sim", n_loc=2000, seed=20260928, n_boot=500, quick=False, out=DEFAULT_OUT,
        n_check=200, irfs=None, verbose=True):
    t_start = time.time()
    irfs = IRFS if irfs is None else irfs
    positions = POSITIONS
    if quick:
        n_boot = min(n_boot, 50)
        n_check = min(n_check, 20)
    sim, fallback = _get_simulator(source)
    used = "v2sim" if sim is not None else "multinomial"
    pos = psf.beam_positions(SETUP["K"], GEOM["L"], GEOM["center"])
    cases = []
    ci = 0
    t_sim = t_est = 0.0
    crosscheck = None
    for irf in irfs:
        C = mx.mixing_matrix(SETUP["tau"], SETUP["T"], SETUP["K"], SETUP["a"], SETUP["b"],
                             irf or None)
        for sk, Nb in NB.items():
            sbr = NS / float(Nb)
            for r0 in positions:
                r0 = np.array(r0, dtype=float)
                case_seed = [int(seed), ci]
                rng = np.random.default_rng(case_seed)
                lam = psf.lambda_beams(r0, pos, GEOM["fwhm"], GEOM["kind"])
                t0 = time.time()
                counts = _counts(sim, lam, n_loc, Nb, irf, rng)
                t_sim += time.time() - t0
                t0 = time.time()
                crb_mix = float(es.crb(r0, pos, GEOM["fwhm"], C, SETUP["b"], SETUP["T"], sbr, NS + Nb))
                crb_mix_bg = float(es.crb(r0, pos, GEOM["fwhm"], C, SETUP["b"], SETUP["T"], sbr,
                                          NS + Nb, free_bg=True))
                crb_leg = float(es.crb_legacy(r0, pos, GEOM["fwhm"], sbr, NS + Nb))
                p_exp = es.forward_probs(r0, pos, GEOM["fwhm"], C, SETUP["b"], SETUP["T"], sbr)
                asym_leg = es.mle_legacy(p_exp * 1e9, pos, GEOM["fwhm"], sbr, GEOM["bounds_radius"]).r
                ests = {
                    "legacy": (es.mle_legacy(counts, pos, GEOM["fwhm"], sbr, GEOM["bounds_radius"],
                                             grid_step=GEOM["grid_step"]), crb_mix),
                    "mixing": (es.mle_mixing(counts, pos, GEOM["fwhm"], C, SETUP["b"], SETUP["T"], sbr,
                                             GEOM["bounds_radius"], grid_step=GEOM["grid_step"]), crb_mix),
                    "mixing_freebg": (es.mle_mixing(counts, pos, GEOM["fwhm"], C, SETUP["b"], SETUP["T"],
                                                    sbr, GEOM["bounds_radius"], free_bg=True,
                                                    grid_step=GEOM["grid_step"]), crb_mix_bg),
                }
                brng = np.random.default_rng([int(seed), ci, 1])
                res = {}
                for name, (r, cr) in ests.items():
                    m = _summ(r.r, r0, cr, brng, n_boot)
                    m.update({"crb_axis_nm": cr, "boundary_fraction": r.boundary_fraction,
                              "n_failed": r.n_failed,
                              "n_not_converged": int(np.sum(~np.asarray(r.converged)))})
                    if name == "mixing_freebg":
                        m["beta_mean"] = float(np.mean(r.beta))
                        m["beta_true"] = Nb / float(NS + Nb)
                    res[name] = m
                t_est += time.time() - t0
                case = {"irf_fwhm_ns": irf, "sbr_label": sk, "Ns": NS, "Nb": Nb, "sbr": sbr,
                        "position_nm": r0.tolist(), "n_loc": int(n_loc), "seed": case_seed,
                        "bootstrap_seed": [int(seed), ci, 1],
                        "n_in_windows_mean": float(counts.sum(1).mean()),
                        "n_in_windows_expected_model": float((NS + Nb) * es.capture_fraction(
                            r0, pos, GEOM["fwhm"], C, SETUP["b"], SETUP["T"], sbr)),
                        "counts_mean": counts.mean(0).tolist(),
                        "crb_mixing_axis_nm": crb_mix, "crb_mixing_freebg_axis_nm": crb_mix_bg,
                        "crb_minflux_legacy_axis_nm": crb_leg,
                        "legacy_asymptotic_bias_vec_nm": (asym_leg - r0).tolist(),
                        "legacy_asymptotic_bias_nm": float(np.hypot(*(asym_leg - r0))),
                        "estimators": res}
                cases.append(case)
                if verbose:
                    print("irf %.1f %s %-14s | legacy |b| %.3f RMSE/CRB %.3f | mixing |b| %.3f "
                          "RMSE/CRB %.3f | freebg RMSE/CRB %.3f"
                          % (irf, sk, tuple(r0), res["legacy"]["bias_abs"],
                             res["legacy"]["rmse_over_crb"], res["mixing"]["bias_abs"],
                             res["mixing"]["rmse_over_crb"], res["mixing_freebg"]["rmse_over_crb"]))
                    sys.stdout.flush()
                if crosscheck is None and irf == 0.0 and sk == "SBR21" and np.allclose(r0, (-5.07, -7.56)):
                    crosscheck = _legacy_crosscheck(counts, sbr, pos, n_check)
                ci += 1
    files = {k: _sha(os.path.join(ROOT, "src", "pminflux_sim", k + ".py"))
             for k in ("mixing", "psf", "estimate", "simulate")}
    files["compare_legacy_vs_v2"] = _sha(os.path.abspath(__file__))
    result = {
        "description": "legado (Ec. 3.5) contra MLE con matriz de mezcla sobre datos del simulador v2",
        "source_requested": source, "source": used, "source_fallback_reason": fallback,
        "setup": SETUP, "geometry": dict(GEOM, beam_positions_nm=pos.tolist()),
        "Ns": NS, "Nb": NB, "N_convention": "N = Ns + Nb detectados en el ciclo completo; "
                                           "CRB con N * fraccion capturada en ventanas",
        "crb_definition": "sigma_CRB por eje = sqrt(tr(F^-1)/2); RMSE/CRB = RMSE_2D/(sqrt2 sigma_CRB)",
        "irf_fwhm_ns": irfs, "positions_nm": [list(p) for p in positions], "n_loc": int(n_loc),
        "seed": int(seed), "seed_rule": "caso i: default_rng([seed, i]); bootstrap: [seed, i, 1]",
        "n_boot": int(n_boot), "quick": bool(quick),
        "estimators": {"legacy": "estimate.mle_legacy (Ec. 3.5 continua, sbr = Ns/Nb, R = 75 nm)",
                       "mixing": "estimate.mle_mixing (C = mixing_matrix(tau, T, K, a, b, irf))",
                       "mixing_freebg": "estimate.mle_mixing(free_bg=True) (beta por localizacion)"},
        "f104_reference_legacy_bias_sbr21_nm": F104_LEGACY_BIAS_SBR21,
        "legacy_crosscheck_pos_MINFLUX": crosscheck,
        "cases": cases,
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__, "sha256": files},
        "command": " ".join(sys.argv),
        "runtime_s": {"total": time.time() - t_start, "simulation": t_sim, "estimation": t_est},
    }
    if out:
        d = os.path.dirname(out)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", choices=["v2sim", "multinomial"], default="v2sim")
    ap.add_argument("--n-loc", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--quick", action="store_true", help="corrida corta (n_loc 100, 1 IRF)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    n_loc = min(a.n_loc, 100) if a.quick else a.n_loc
    irfs = [0.0] if a.quick else None
    r = run(a.source, n_loc, a.seed, a.n_boot, a.quick, a.out, irfs=irfs)
    print("source=%s  runtime %.1f s  -> %s" % (r["source"], r["runtime_s"]["total"], a.out))


if __name__ == "__main__":
    main()
