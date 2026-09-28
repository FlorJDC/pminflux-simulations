# -*- coding: utf-8 -*-
"""
F201 - Los estudios de la autora apagan la fuga entre pulsos (Tlife = 0.001 ns,
ventanas a = 0, b = dt/K).  ¿Cuánto cambian sesgo, σ y RMSE si se usan los
valores medidos (τ = 4.21 ns, ventana [0, 10.1] ns a 20 MHz)?

Se corren los estudios TAL COMO ELLA LOS CORRE: `sim_exp('p_minflux', ...)` +
`nMINFLUX` + `pos_MINFLUX` del legado, con sus mismos parámetros, semillas y
radio de búsqueda.  Lo único que cambia es (Tlife, b):

    C0  Tlife=0.001, b=12.5   (lo que usan los estudios)
    C1  Tlife=0.001, b=10.1   (sólo cambia la ventana -> fracción de fondo)
    C2  Tlife=4.21,  b=12.5   (sólo fuga, ventana completa)
    C3  Tlife=4.21,  b=10.1   (experimento real)

Estudio A = simulation_misalignment.py (Ns=2000, Nb=95, r0=(-5.07,-7.56) nm,
1000 muestras, semilla 20260825, R = 0.75 L_eff).  Las PSFs 20260820 no están
en el disco, así que se usan los EBP que se pueden reconstruir exactamente:
'ideal', 'geom_exp' (posiciones medidas del log) y 'realistic_fit' (el ajuste
2D de ella, desde Resultados/realistic_psf/fit_parameters.csv).
Estudio B = documento/make_fig_eficiencia.py (SBR=9, r0=(5,-5), 250 muestras
por N, semilla 20260825 re-sembrada en cada punto).

Estimador: el argmax de pos_MINFLUX se evalúa con los log p precomputados en el
disco de búsqueda (lo mismo que hizo la autora en analyze_realistic_psf.py);
la equivalencia exacta con `pos_MINFLUX` se comprueba en las primeras muestras.
Además se calcula el sesgo ASINTÓTICO (N -> inf, conteos esperados) con una
matriz de mezcla calculada aparte, como chequeo independiente del MC.

Uso:  python scripts/findings/F201_leakage_off_in_studies.py [--quick]
"""
import os
import sys
import csv
import json
import time
import argparse

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LEG = os.path.join(ROOT, 'legacy', 'p-minflux-main')
sys.path.insert(0, LEG)
from tools import tools_simulations as ts   # noqa: E402
from tools import ebp as E                   # noqa: E402
from tools import realistic_ebp as R         # noqa: E402

OUTDIR = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3')
K = 4
DT = 50.0
TAU = np.arange(K) / K * DT
CONDS = [('C0', 0.001, DT / K), ('C1', 0.001, 10.1),
         ('C2', 4.21, DT / K), ('C3', 4.21, 10.1)]
GEOM_POS = np.array([[0, 0], [-44, -27], [45, -26], [-5, 51]], float)  # run_final.log
FWHM = 343.9          # ajuste radial de ella (run_final.log)
L_EFF = 103.23


# ─── EBPs reconstruibles ──────────────────────────────────────────────────
def load_realistic_params():
    path = os.path.join(LEG, 'Resultados', 'realistic_psf', 'fit_parameters.csv')
    out = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            p = {}
            for k, v in row.items():
                try:
                    p[k] = float(v)
                except ValueError:
                    p[k] = v
            out.append(p)
    return out


def build_ebps(grid):
    ide = E.ebp_ideal(grid, L=L_EFF, K=K, donut_fwhm=FWHM, label='ideal')
    geo = E.ebp_analytic(GEOM_POS, grid, donut_fwhm=FWHM, label='geom_exp')
    rea = R.ebp_realistic(load_realistic_params(), grid, label='realistic_fit')
    return {'ideal': ide, 'geom_exp': geo, 'realistic_fit': rea}


# ─── matriz de mezcla independiente (modelo periódico = pliegue % dt) ─────
def mixing_matrix(tau_life, a, b, T=DT, nwrap=60):
    """C[i, j] = P(((τ_j + Exp(τ)) mod T) ∈ (τ_i + a, τ_i + a + b))."""
    C = np.zeros((K, K))
    for i in range(K):
        lo, hi = TAU[i] + a, TAU[i] + a + b
        for j in range(K):
            s = 0.0
            for n in range(-1, nwrap):
                x1 = max(lo - TAU[j] + n * T, 0.0)
                x2 = max(hi - TAU[j] + n * T, 0.0)
                s += np.exp(-x1 / tau_life) - np.exp(-x2 / tau_life)
            C[i, j] = s
    return C


def expected_fractions(lam, sbr, tau_life, b, a=0.0):
    """Fracción esperada de cuentas por ventana (señal con fuga + fondo)."""
    lam = np.asarray(lam, float)
    C = mixing_matrix(tau_life, a, b)
    Ns_frac = sbr / (sbr + 1.0)
    Nb_frac = 1.0 / (sbr + 1.0)
    e = Ns_frac * C.dot(lam / lam.sum()) + Nb_frac * (b / DT)
    return e / e.sum()


# ─── estimador: pos_MINFLUX con log p precomputado en el disco ────────────
class FastMLE:
    def __init__(self, ebp, sbr, r_max_nm):
        g = ebp.grid
        norm = ebp.PSFs.sum(axis=0)
        p = (sbr / (sbr + 1)) * ebp.PSFs / norm + (1 / (sbr + 1)) / K
        rows, cols = np.indices(norm.shape)
        mx = cols * g.px_nm - g.size_nm / 2
        my = g.size_nm / 2 - rows * g.px_nm
        roi = np.hypot(mx, my) <= r_max_nm
        self.idx = np.argwhere(roi)
        self.logp = np.log(p[:, roi])
        self.grid = g

    def __call__(self, n):
        return tuple(self.idx[np.argmax(np.asarray(n) @ self.logp)])


# ─── modelo continuo para el sesgo asintótico ─────────────────────────────
def donut_val(pos, x, y, fwhm=FWHM):
    r2 = (x - pos[:, 0]) ** 2 + (y - pos[:, 1]) ** 2
    return 4 * np.e * np.log(2) * r2 / fwhm ** 2 * np.exp(-4 * np.log(2) * r2 / fwhm ** 2)


def realistic_val(params, x, y):
    out = []
    for p in params:
        dx, dy = x - p['x0_nm'], y - p['y0_nm']
        ct, st = np.cos(p['theta_rad']), np.sin(p['theta_rad'])
        xp, yp = ct * dx + st * dy, -st * dx + ct * dy
        q = (xp / p['fwhm_x_nm']) ** 2 + (yp / p['fwhm_y_nm']) ** 2
        d = 4 * np.e * np.log(2) * q * np.exp(-4 * np.log(2) * q)
        v = p['pedestal'] + p['amplitude'] * d + p['gradient_x_per_nm'] * dx \
            + p['gradient_y_per_nm'] * dy
        out.append(max(v, np.finfo(float).eps))
    return np.array(out)


def asymptotic_estimate(model_fun, e_frac, sbr, x0):
    """argmax_r Σ e_i log p_i(r) con el modelo de pos_MINFLUX (continuo)."""
    def negll(r):
        lam = model_fun(r[0], r[1])
        p = (sbr / (sbr + 1)) * lam / lam.sum() + (1 / (sbr + 1)) / K
        return -np.sum(e_frac * np.log(p))
    res = minimize(negll, x0, method='Nelder-Mead',
                   options={'xatol': 1e-6, 'fatol': 1e-14, 'maxiter': 4000})
    return res.x


# ─── Monte Carlo como en los scripts de ella ──────────────────────────────
def run_mc(ebp_gen, est, r0_idx, sbr, Ns, Nb, Tlife, b, samples, seed,
           check_equiv=0, ebp_est=None, r_max=None):
    np.random.seed(seed)
    out = np.full((samples, 2), np.nan)
    fails = 0
    neq = 0
    ncounts = []
    for i in range(samples):
        relTime, _, failed = ts.sim_exp('p_minflux', None, ebp_gen.PSFs, r0_idx,
                                        sbr, Ns, Nb, int(2e5), Tlife, 1.05, DT)
        if failed:
            fails += 1
            continue
        n = ts.nMINFLUX(K, TAU, relTime, 0.0, b)
        ncounts.append(n)
        idx = est(n)
        if i < check_equiv:
            idx2 = ts.pos_MINFLUX(n, ebp_est.PSFs, SBR=sbr, px_nm=1.0, r_max_nm=r_max)
            neq += int(tuple(idx2) == tuple(idx))
        out[i] = ebp_gen.grid.to_space(idx)
    return out, fails, neq, np.array(ncounts)


def stats(est, r0):
    v = est[~np.isnan(est[:, 0])]
    n = len(v)
    mean = v.mean(0)
    sd = v.std(0)
    bias = mean - r0
    rmse = np.sqrt(0.5 * np.sum(sd ** 2 + bias ** 2))
    return {'n': n, 'bias_x': bias[0], 'bias_y': bias[1],
            'bias_abs': float(np.linalg.norm(bias)),
            'bias_se': float(np.linalg.norm(sd / np.sqrt(n))),
            'std_x': sd[0], 'std_y': sd[1], 'rmse': float(rmse)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    grid = E.Grid(400, 1.0)
    ebps = build_ebps(grid)
    rparams = load_realistic_params()
    model_of = {
        'ideal': lambda x, y: donut_val(ebps['ideal'].pos_nm, x, y),
        'geom_exp': lambda x, y: donut_val(GEOM_POS, x, y),
        'realistic_fit': lambda x, y: realistic_val(rparams, x, y),
    }
    R_MAX = 0.75 * L_EFF
    results = {'meta': {'conds': CONDS, 'R_max_nm': R_MAX, 'fwhm': FWHM}}

    # mezcla: chequeo contra el handoff (0.909 propio, 0.047 anterior)
    C3 = mixing_matrix(4.21, 0.0, 10.1)
    results['C_tau421_b101'] = C3.tolist()
    print('C (tau=4.21, [0,10.1]):  diag=%.4f  prev=%.4f  prev2=%.4f  captured=%.4f'
          % (C3[1, 1], C3[1, 0], C3[2, 0], C3[:, 0].sum()))

    # ── Estudio A: simulation_misalignment ───────────────────────────────
    Ns, Nb = 2000, 95
    sbr = Ns / Nb
    r0 = np.array([-5.07, -7.56])
    r0_idx = grid.to_index(r0)
    r0_pix = grid.to_space(r0_idx)       # el emisor efectivo es el píxel
    samples = 200 if args.quick else 1000
    cases = [('Ideal', 'ideal', 'ideal'),
             ('Geom. medida honesta', 'geom_exp', 'geom_exp'),
             ('Geom. medida ingenua', 'geom_exp', 'ideal'),
             ('Realista honesta', 'realistic_fit', 'realistic_fit'),
             ('Realista ingenua', 'realistic_fit', 'ideal')]
    A = {}
    print('\nEstudio A (simulation_misalignment): Ns=2000 Nb=95 r0=%s px->%s, %d muestras'
          % (r0, r0_pix, samples))
    print('%-22s %-3s %8s %8s %8s %8s %8s %8s | %8s %8s' %
          ('caso', 'C', 'bias_x', 'bias_y', '|b|', 'std_x', 'std_y', 'RMSE',
           'asin_bx', 'asin_by'))
    for label, g, e in cases:
        est = FastMLE(ebps[e], sbr, R_MAX)
        lam = ebps[g].PSFs[:, r0_idx[0], r0_idx[1]]
        per = {}
        base_est = None
        for cname, tl, b in CONDS:
            ests, fails, neq, nc = run_mc(ebps[g], est, r0_idx, sbr, Ns, Nb, tl, b,
                                          samples, 20260825, check_equiv=20,
                                          ebp_est=ebps[e], r_max=R_MAX)
            # sesgo respecto del píxel donde sim_exp pone al emisor (r0_pix);
            # la convención de ella (respecto de R0_NM) se guarda aparte: ver F206
            s = stats(ests, r0_pix)
            s['bias_vs_R0_NM_author_convention'] = stats(ests, r0)['bias_abs']
            s['fails'] = fails
            s['equiv_pos_MINFLUX'] = '%d/20' % neq
            s['mean_counts'] = nc.mean(0).tolist()
            s['mean_total_in_windows'] = float(nc.sum(1).mean())
            # asintótico (independiente del MC)
            efr = expected_fractions(lam, sbr, tl, b)
            s['expected_frac'] = efr.tolist()
            s['obs_frac'] = (nc.sum(0) / nc.sum()).tolist()
            xa = asymptotic_estimate(model_of[e], efr, sbr, r0_pix)
            s['asym_bias_x'] = float(xa[0] - r0_pix[0])
            s['asym_bias_y'] = float(xa[1] - r0_pix[1])
            if base_est is None:
                base_est = ests
            else:
                d = ests - base_est
                d = d[~np.isnan(d[:, 0])]
                s['paired_dmean'] = d.mean(0).tolist()
                s['paired_dmean_se'] = (d.std(0) / np.sqrt(len(d))).tolist()
            per[cname] = s
            print('%-22s %-3s %8.3f %8.3f %8.3f %8.3f %8.3f %8.3f | %8.3f %8.3f  [eq %s, fails %d]'
                  % (label, cname, s['bias_x'], s['bias_y'], s['bias_abs'], s['std_x'],
                     s['std_y'], s['rmse'], s['asym_bias_x'], s['asym_bias_y'],
                     s['equiv_pos_MINFLUX'], fails))
        crb = ts.crb_minflux(K, ebps[g].PSFs, sbr, 1.0, 400.0, Ns + Nb,
                             method='1')[r0_idx[0], r0_idx[1]]
        per['crb'] = float(crb)
        A[label] = per
        print('%-22s CRB(r0) = %.3f nm   RMSE/CRB: %s' % (
            '', crb, '  '.join('%s %.2f' % (c, per[c]['rmse'] / crb) for c, _, _ in CONDS)))
    results['study_A'] = A

    # ── Estudio B: make_fig_eficiencia ───────────────────────────────────
    sbrB = 9.0
    r0B = np.array([5.0, -5.0])
    r0B_idx = grid.to_index(r0B)
    NLIST = [100, 400, 1600] if not args.quick else [100, 1600]
    samplesB = 250 if not args.quick else 100
    B = {}
    print('\nEstudio B (make_fig_eficiencia): SBR=9 r0=(5,-5), %d muestras' % samplesB)
    for ekey in ('ideal', 'realistic_fit'):
        est = FastMLE(ebps[ekey], sbrB, R_MAX)
        lam = ebps[ekey].PSFs[:, r0B_idx[0], r0B_idx[1]]
        B[ekey] = {}
        for N in NLIST:
            Ns_ = int(round(sbrB / (sbrB + 1) * N))
            Nb_ = N - Ns_
            crb = ts.crb_minflux(K, ebps[ekey].PSFs, sbrB, 1.0, 400.0, N,
                                 method='1')[r0B_idx[0], r0B_idx[1]]
            row = {'crb': float(crb)}
            for cname, tl, b in CONDS:
                ests, fails, neq, nc = run_mc(ebps[ekey], est, r0B_idx, sbrB, Ns_, Nb_,
                                              tl, b, samplesB, 20260825)
                s = stats(ests, r0B)
                s['fails'] = fails
                s['rmse_over_crb'] = s['rmse'] / crb
                row[cname] = s
            B[ekey][N] = row
            print('%-14s N=%5d CRB=%.3f  ' % (ekey, N, crb) + '  '.join(
                '%s: RMSE/CRB %.2f |b| %.2f' % (c, row[c]['rmse_over_crb'], row[c]['bias_abs'])
                for c, _, _ in CONDS))
    results['study_B'] = {k: {str(n): v for n, v in d.items()} for k, d in B.items()}

    # asintótico en función de N no depende de N: sólo de p'
    results['runtime_s'] = time.time() - t0
    fn = os.path.join(OUTDIR, 'F201_out%s.json' % ('_quick' if args.quick else ''))
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=1, default=float)
    print('\nguardado en', fn, ' (%.0f s)' % results['runtime_s'])


if __name__ == '__main__':
    main()
