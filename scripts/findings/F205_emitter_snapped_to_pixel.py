# -*- coding: utf-8 -*-
"""
F205 - El emisor se simula en el PÍXEL más cercano a R0_NM (sim_exp y
monte_carlo leen psf[:, fila, col]), pero el sesgo se mide contra R0_NM.
Con R0_NM = (−5.07, −7.56) nm (la configuración actual de
simulation_misalignment.py y analyze_realistic_psf.py) el píxel es (−5, −8):
aparece un "sesgo" espurio de 0.445 nm, que con 300–1000 muestras
(SE ≈ 0.04–0.2 nm) es significativo.  Los "honest_bias_nm" de
comparison_metrics.csv (0.43, 0.38, 0.47, 0.52, 0.52 nm) son casi todo esto.

Uso:  python scripts/findings/F205_emitter_snapped_to_pixel.py
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


def honest_mean(ebp, r0_idx, sbr, N, rs, n, seed):
    return honest_mean_est(ebp, ebp, r0_idx, sbr, N, rs, n, seed)


def honest_mean_est(gen, ebp, r0_idx, sbr, N, rs, n, seed):
    rng = np.random.RandomState(seed)
    lam = gen.PSFs[:, r0_idx[0], r0_idx[1]].astype(float)
    p = (sbr / (sbr + 1)) * lam / lam.sum() + 1 / ((sbr + 1) * 4)
    norm = ebp.PSFs.sum(0)
    pm = (sbr / (sbr + 1)) * ebp.PSFs / norm + 1 / ((sbr + 1) * 4)
    g = ebp.grid
    rows, cols = np.indices(norm.shape)
    mx = cols * g.px_nm - g.size_nm / 2
    my = g.size_nm / 2 - rows * g.px_nm
    roi = np.hypot(mx, my) <= rs
    xy = np.column_stack([mx[roi], my[roi]])
    logp = np.log(pm[:, roi])
    est = []
    for s in range(0, n, 4000):
        c = rng.multinomial(N, p, size=min(4000, n - s))
        est.append(xy[np.argmax(c @ logp, axis=1)])
    est = np.concatenate(est)
    return est.mean(0), est.std(0)


def main():
    grid = E.Grid(400, 1.0)
    R0 = np.array([-5.07, -7.56])
    idx = grid.to_index(R0)
    pix = grid.to_space(idx)
    off = np.linalg.norm(pix - R0)
    print('R0_NM = %s -> índice %s -> píxel simulado %s ; |desfase| = %.3f nm' % (R0, idx, pix, off))
    ebps = {'ideal': E.ebp_ideal(grid, L=103.23, K=4, donut_fwhm=343.9),
            'realistic_fit': R.ebp_realistic(load_params(), grid)}
    out = {'R0_NM': R0.tolist(), 'pixel_nm': pix.tolist(), 'offset_nm': off}
    for k, e in ebps.items():
        m, sd = honest_mean(e, idx, 2000 / 95, 2095, 0.75 * 103.23, 100000, 1)
        b_R0 = np.linalg.norm(m - R0)
        b_px = np.linalg.norm(m - pix)
        se = np.linalg.norm(sd / np.sqrt(100000))
        se1000 = np.linalg.norm(sd / np.sqrt(1000))
        out[k] = {'bias_vs_R0': b_R0, 'bias_vs_pixel': b_px, 'se_1e5': se,
                  'se_at_1000_samples': se1000}
        print('%-14s honesto, N=2095, 1e5 muestras: |sesgo| vs R0_NM = %.3f nm ; vs píxel = %.3f nm'
              ' (SE %.3f) ; SE con 1000 muestras = %.3f' % (k, b_R0, b_px, se, se1000))
    # honesto vs ingenuo (geom_exp -> ideal): ¿cambia la comparación?
    geo = E.ebp_analytic(np.array([[0, 0], [-44, -27], [45, -26], [-5, 51]], float), grid,
                         donut_fwhm=343.9)
    cmp_ = {}
    for lab, gen, est in (('Geom. honesta', geo, geo), ('Geom. ingenua', geo, ebps['ideal'])):
        m, sd = honest_mean_est(gen, est, idx, 2000 / 95, 2095, 0.75 * 103.23, 100000, 1)
        cmp_[lab] = {'mean': m.tolist(), 'b_R0': float(np.linalg.norm(m - R0)),
                     'b_px': float(np.linalg.norm(m - pix))}
        print('%-14s |b| vs R0_NM = %.3f ; vs píxel = %.3f ; vector vs píxel = %s' % (
            lab, cmp_[lab]['b_R0'], cmp_[lab]['b_px'], np.round(m - pix, 3)))
    dh = np.array(cmp_['Geom. ingenua']['mean']) - np.array(cmp_['Geom. honesta']['mean'])
    print('diferencia ingenua - honesta (vector, no depende de la referencia) = %s, |.|=%.3f'
          % (np.round(dh, 3), np.linalg.norm(dh)))
    out['honest_vs_naive'] = cmp_
    # sus números
    path = os.path.join(LEG, 'Resultados', 'realistic_psf', 'comparison_metrics.csv')
    hb = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['beam'] == '0':
                hb.append((row['stage'], float(row['honest_bias_nm'])))
    print('honest_bias_nm de comparison_metrics.csv:', ', '.join('%s %.3f' % t for t in hb))
    out['author_honest_bias'] = hb
    fn = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3', 'F205_out.json')
    json.dump(out, open(fn, 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    main()
