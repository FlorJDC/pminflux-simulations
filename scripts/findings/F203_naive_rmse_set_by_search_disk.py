# -*- coding: utf-8 -*-
"""
F203 - En los casos "ingenuos" el RMSE/sesgo que reportan los estudios lo fija
en buena parte el radio del disco de búsqueda (R = 0.75·L_eff = 77.4 nm), no el
estimador; y la tabla mezcla un RMSE POR EJE con un |sesgo| 2D (por eso en su
log aparece |sesgo| = 62.76 nm > RMSE = 46.96 nm).

Se repiten los casos "Realista ingenua" y "Experimental ingenua" de
simulation_misalignment.py variando SÓLO R_SEARCH_FACTOR y se reporta la
fracción de estimaciones que quedan pegadas al borde del disco (que los
estudios no reportan).

Generadores:
  - 'realistic_fit' : el ajuste 2D de ella (fit_parameters.csv, 20260820)
  - 'exp_20260703'  : PSFs medidas 20260703 (SUSTITUTO: las 20260820 no están
                      en el disco; L_eff 98.9 nm, ceros 7–10 %).  Solo lectura.
Estimador ingenuo: EBP ideal con el L_eff y fwhm del generador (como ella).
Conteos multinomiales con el modelo de fondo 1/K: con Tlife=0.001 y b=dt/K es
lo que produce sim_exp (ella lo verificó; ver F290 para el chequeo).

Uso:  python scripts/findings/F203_naive_rmse_set_by_search_disk.py
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
from tools import ebp as E              # noqa: E402
from tools import realistic_ebp as R    # noqa: E402

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


def mc(gen, est, r0_idx, r0, sbr, N, rs, samples, seed):
    rng = np.random.RandomState(seed)
    lam = gen.PSFs[:, r0_idx[0], r0_idx[1]].astype(float)
    p_true = (sbr / (sbr + 1)) * lam / lam.sum() + 1 / ((sbr + 1) * 4)
    norm = est.PSFs.sum(0)
    pm = (sbr / (sbr + 1)) * est.PSFs / norm + 1 / ((sbr + 1) * 4)
    g = est.grid
    rows, cols = np.indices(norm.shape)
    mx = cols * g.px_nm - g.size_nm / 2
    my = g.size_nm / 2 - rows * g.px_nm
    roi = np.hypot(mx, my) <= rs
    idx = np.argwhere(roi)
    logp = np.log(pm[:, roi])
    counts = rng.multinomial(N, p_true, size=samples)
    ii = np.argmax(counts @ logp, axis=1)
    est_nm = np.array([g.to_space(tuple(idx[k])) for k in ii])
    r0p = g.to_space(r0_idx)
    bias = est_nm.mean(0) - r0p
    sd = est_nm.std(0)
    rmse_axis = np.sqrt(0.5 * np.sum(sd ** 2 + bias ** 2))   # como ella (Ec. 4.2)
    rmse_2d = np.sqrt(np.sum(sd ** 2 + bias ** 2))
    edge = np.mean(np.hypot(est_nm[:, 0], est_nm[:, 1]) > rs - 1.5)
    return {'rmse_axis': float(rmse_axis), 'rmse_2d': float(rmse_2d),
            'bias_2d': float(np.linalg.norm(bias)), 'std': sd.tolist(),
            'frac_edge': float(edge)}


def main():
    grid = E.Grid(400, 1.0)
    gens = {'realistic_fit': R.ebp_realistic(load_params(), grid)}
    fw = 343.9
    if os.path.isdir(PROXY):
        ex = E.ebp_experimental(PROXY, K=4, label='exp_20260703')
        fwp = float(np.mean([E.fit_donut_fwhm(ex.PSFs[k], ex.grid)['fwhm'] for k in range(4)]))
        gens['exp_20260703'] = ex
    configs = [('A: N=2095 SBR=21', 2095, 2000 / 95, np.array([-5.07, -7.56])),
               ('B: N=100 SBR=9', 100, 9.0, np.array([5.0, -5.0]))]
    factors = [0.5, 0.75, 1.0, 1.25]
    out = {}
    for gname, gen in gens.items():
        L = 103.23 if gname == 'realistic_fit' else gen.L_eff
        fwhm = fw if gname == 'realistic_fit' else fwp
        ide = E.ebp_ideal(grid, L=L, K=4, donut_fwhm=fwhm)
        print('\n== generador %s  (estimador ingenuo: ideal L=%.1f fwhm=%.1f)' % (gname, L, fwhm))
        for cname, N, sbr, r0 in configs:
            r0_idx = grid.to_index(r0)
            print('  ' + cname)
            print('   %6s %7s | %9s %9s %9s %7s | %9s' % ('factor', 'R[nm]', 'RMSEeje', '|b|2D',
                                                       'RMSE2D', 'borde', 'honestoRMSE'))
            for f in factors:
                rs = f * L
                r = mc(gen, ide, r0_idx, r0, sbr, N, rs, 1000, 20260825)
                h = mc(gen, gen, r0_idx, r0, sbr, N, rs, 1000, 20260825)
                out['%s|%s|%.2f' % (gname, cname, f)] = {'naive': r, 'honest': h, 'R_nm': rs}
                print('   %6.2f %7.1f | %9.2f %9.2f %9.2f %7.3f | %9.2f' % (
                    f, rs, r['rmse_axis'], r['bias_2d'], r['rmse_2d'], r['frac_edge'],
                    h['rmse_axis']))
    fn = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3', 'F203_out.json')
    json.dump(out, open(fn, 'w', encoding='utf-8'), indent=1)
    print('\nguardado en', fn)


if __name__ == '__main__':
    main()
