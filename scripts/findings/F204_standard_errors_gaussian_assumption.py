# -*- coding: utf-8 -*-
"""
F204 - Los errores estándar de los estudios (std/√(2n), RMSE/√(2n) y
(RMSE/CRB)/√(2n)) suponen estimaciones normales.  Con N bajo y EBP con
pedestal la distribución del MLE tiene colas (y el borde del disco de
búsqueda): el SE real es varias veces mayor.  Además |sesgo| = ‖media − r0‖
tiene un piso positivo por ruido (≈ 1.25·σ/√n en 2D) que no se descuenta.

Se replica el punto N = 100 de documento/make_fig_eficiencia.py (SBR = 9,
r0 = (5, −5), 250 muestras, R = 0.75·L_eff) muchas veces con semillas
independientes y se compara la dispersión REAL de cada estadístico con el
SE que imprime el script.

Generadores: 'ideal' y 'realistic_fit' (ajuste 2D de ella; las PSF 20260820 no
están en disco) y el sustituto medido 'exp_20260703' (solo lectura).
Conteos multinomiales (equivalentes a sim_exp con Tlife=0.001, b=dt/K).

Uso:  python scripts/findings/F204_standard_errors_gaussian_assumption.py
"""
import os
import sys
import csv
import json

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LEG = os.path.join(ROOT, 'legacy', 'p-minflux-main')
sys.path.insert(0, LEG)
from tools import tools_simulations as ts   # noqa: E402
from tools import ebp as E                   # noqa: E402
from tools import realistic_ebp as R         # noqa: E402

PROXY = r'C:\Data\psf\20260703'


def load_params():
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


class Setup:
    def __init__(self, ebp, sbr, r0_idx, rs):
        lam = ebp.PSFs[:, r0_idx[0], r0_idx[1]].astype(float)
        self.p = (sbr / (sbr + 1)) * lam / lam.sum() + 1 / ((sbr + 1) * 4)
        norm = ebp.PSFs.sum(0)
        pm = (sbr / (sbr + 1)) * ebp.PSFs / norm + 1 / ((sbr + 1) * 4)
        g = ebp.grid
        rows, cols = np.indices(norm.shape)
        mx = cols * g.px_nm - g.size_nm / 2
        my = g.size_nm / 2 - rows * g.px_nm
        roi = np.hypot(mx, my) <= rs
        idx = np.argwhere(roi)
        self.xy = np.column_stack([mx[roi], my[roi]])
        self.logp = np.log(pm[:, roi])
        self.idx = idx

    def sample(self, rng, N, n, chunk=4000):
        out = []
        for s in range(0, n, chunk):
            c = rng.multinomial(N, self.p, size=min(chunk, n - s))
            out.append(self.xy[np.argmax(c @ self.logp, axis=1)])
        return np.concatenate(out)


def author_stats(est, r0, crb):
    n = len(est)
    sd = est.std(0)
    bias = est.mean(0) - r0
    rmse = np.sqrt(0.5 * (sd[0] ** 2 + sd[1] ** 2 + bias[0] ** 2 + bias[1] ** 2))
    return {'std_x': sd[0], 'std_x_se_claimed': sd[0] / np.sqrt(2 * n),
            'rmse': rmse, 'rmse_se_claimed': rmse / np.sqrt(2 * n),
            'ratio': rmse / crb, 'ratio_se_claimed': rmse / crb / np.sqrt(2 * n),
            'bias_abs': np.linalg.norm(bias),
            'bias_se_claimed': np.linalg.norm(sd / np.sqrt(n))}


def main():
    grid = E.Grid(400, 1.0)
    fw = 343.9
    ebps = {'ideal': E.ebp_ideal(grid, L=103.23, K=4, donut_fwhm=fw),
            'realistic_fit': R.ebp_realistic(load_params(), grid)}
    if os.path.isdir(PROXY):
        ebps['exp_20260703'] = E.ebp_experimental(PROXY, K=4)
    sbr, N, n, reps = 9.0, 100, 250, 400
    r0 = np.array([5.0, -5.0])
    r0_idx = grid.to_index(r0)
    rs = 0.75 * 103.23
    out = {}
    print('N=%d SBR=%g, n=%d muestras por corrida, %d corridas independientes' % (N, sbr, n, reps))
    print('%-14s %-10s %9s %11s %11s %8s' % ('EBP', 'estad.', 'media', 'SE_real', 'SE_script', 'cociente'))
    for key, e in ebps.items():
        crb = float(ts.crb_minflux(4, e.PSFs, sbr, 1.0, 400.0, N, method='1')[r0_idx[0], r0_idx[1]])
        st = Setup(e, sbr, r0_idx, rs)
        rng = np.random.RandomState(12345)
        rows = [author_stats(st.sample(rng, N, n), r0, crb) for _ in range(reps)]
        res = {'crb': crb}
        for stat in ('std_x', 'rmse', 'ratio', 'bias_abs'):
            vals = np.array([r[stat] for r in rows])
            claimed = np.array([r[stat + '_se_claimed'] if stat != 'bias_abs'
                                else r['bias_se_claimed'] for r in rows])
            res[stat] = {'mean': float(vals.mean()), 'se_real': float(vals.std(ddof=1)),
                         'se_claimed_median': float(np.median(claimed)),
                         'ratio_real_over_claimed': float(vals.std(ddof=1) / np.median(claimed)),
                         'p05': float(np.percentile(vals, 5)), 'p95': float(np.percentile(vals, 95))}
            print('%-14s %-10s %9.3f %11.3f %11.3f %8.2f' % (
                key, stat, vals.mean(), vals.std(ddof=1), np.median(claimed),
                vals.std(ddof=1) / np.median(claimed)))
        # piso de ruido de |sesgo|: con el sesgo verdadero ~ 0, E|b| ≈ sqrt(pi/2)·σ/√n (2D, σ iguales)
        big = st.sample(np.random.RandomState(7), N, 100000)
        true_bias = np.linalg.norm(big.mean(0) - r0)
        sd = big.std(0)
        floor = np.sqrt(np.pi / 2) * np.sqrt(0.5 * (sd ** 2).sum()) / np.sqrt(n)
        # kurtosis de la distribución de estimaciones
        z = (big - big.mean(0)) / sd
        kurt = (z ** 4).mean(0) - 3
        res['true_bias_abs_1e5'] = float(true_bias)
        res['noise_floor_bias_abs'] = float(floor)
        res['excess_kurtosis_xy'] = kurt.tolist()
        res['frac_on_edge'] = float(np.mean(np.hypot(big[:, 0], big[:, 1]) > rs - 1.5))
        print('%-14s |sesgo| verdadero (1e5 muestras) = %.3f ; piso de ruido con n=%d ≈ %.3f ;'
              ' curtosis exceso = %s ; en el borde %.3f' % (
                  key, true_bias, n, floor, np.round(kurt, 1), res['frac_on_edge']))
        out[key] = res
    fn = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3', 'F204_out.json')
    json.dump(out, open(fn, 'w', encoding='utf-8'), indent=1)
    print('guardado en', fn)


if __name__ == '__main__':
    main()
