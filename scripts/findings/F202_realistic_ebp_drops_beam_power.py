# -*- coding: utf-8 -*-
"""
F202 - `realistic_ebp` normaliza cada PSF por su propio máximo y nunca vuelve a
multiplicar por `intensity_scale`: el modelo "realista" pierde las potencias
relativas de los haces, que en p-MINFLUX fijan directamente p_i = λ_i/Σλ.

Evidencia:
  1. Se reconstruye la "escalera de modelos" de analyze_realistic_psf.py a partir
     de Resultados/realistic_psf/fit_parameters.csv (las PSF 20260820 no están
     en disco).  Se reproducen EXACTAMENTE sus números de
     comparison_metrics.csv (CRB y RMSE Monte Carlo con la misma semilla), lo
     que valida la reconstrucción.
  2. Se repite con cada PSF multiplicada por su `intensity_scale` (el máximo de
     la PSF medida, 16.65 ... 22.96) y se mide cuánto cambian p_i en el emisor,
     el CRB y el sesgo/RMSE del estimador de geometría ("ingenuo").

Uso:  python scripts/findings/F202_realistic_ebp_drops_beam_power.py
"""
import os
import sys
import csv
import copy
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
from tools import tools_simulations as sim   # noqa: E402
from tools import ebp as E                    # noqa: E402
from tools import realistic_ebp as R          # noqa: E402

GEOM_POS = np.array([[0, 0], [-44, -27], [45, -26], [-5, 51]], float)


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


def load_reference_metrics():
    path = os.path.join(LEG, 'Resultados', 'realistic_psf', 'comparison_metrics.csv')
    ref = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            ref[row['stage']] = {k: float(row[k]) for k in
                                 ('crb_at_emitter_nm', 'honest_rmse_nm',
                                  'geometry_estimator_rmse_nm',
                                  'geometry_estimator_bias_nm')}
    return ref


# copia literal de analyze_realistic_psf.stripped_params / monte_carlo
def stripped_params(params, keep):
    result = copy.deepcopy(params)
    for p in result:
        if 'amplitude' not in keep:
            p['amplitude'] = 1.0
        if 'pedestal' not in keep:
            p['pedestal'] = 0.0
        if 'background' not in keep:
            p['gradient_x_per_nm'] = 0.0
            p['gradient_y_per_nm'] = 0.0
        if 'ellipticity' not in keep:
            mw = 0.5 * (p['fwhm_x_nm'] + p['fwhm_y_nm'])
            p['fwhm_x_nm'] = mw
            p['fwhm_y_nm'] = mw
            p['theta_rad'] = 0.0
    return result


def monte_carlo(ebp_gen, ebp_est, r0_idx, r0_nm, sbr, total, samples, rng, rs):
    k_beams = ebp_gen.K
    signal = ebp_gen.PSFs[:, r0_idx[0], r0_idx[1]].astype(float)
    signal /= np.sum(signal)
    probabilities = (sbr / (sbr + 1)) * signal + 1 / ((sbr + 1) * k_beams)
    norm = np.sum(ebp_est.PSFs, axis=0)
    pm = (sbr / (sbr + 1)) * ebp_est.PSFs / norm + 1 / ((sbr + 1) * k_beams)
    rows, cols = np.indices(norm.shape)
    s = ebp_est.grid.size_nm
    mx = cols * ebp_est.grid.px_nm - s / 2
    my = s / 2 - rows * ebp_est.grid.px_nm
    roi_idx = np.argwhere(np.hypot(mx, my) <= rs)
    logp = np.log(pm[:, np.hypot(mx, my) <= rs])
    est = np.empty((samples, 2))
    for j in range(samples):
        c = rng.multinomial(total, probabilities)
        est[j] = ebp_gen.grid.to_space(tuple(roi_idx[np.argmax(c @ logp)]))
    bias = est.mean(0) - r0_nm
    rmse = np.sqrt(np.mean(np.sum((est - r0_nm) ** 2, axis=1)) / 2)
    on_edge = np.mean(np.hypot(est[:, 0], est[:, 1]) > rs - 1.5)
    return {'rmse': float(rmse), 'bias': float(np.linalg.norm(bias)),
            'bias_xy': bias.tolist(), 'frac_on_search_edge': float(on_edge)}


def scaled(ebp, params, label):
    ps = ebp.PSFs * np.array([p['intensity_scale'] for p in params])[:, None, None]
    return E.EBP(ps, ebp.pos_nm, ebp.grid, label=label)


def main():
    grid = E.Grid(400, 1.0)
    params = load_params()
    ref = load_reference_metrics()
    shared = params[0]['shared_fwhm_nm']
    scales = np.array([p['intensity_scale'] for p in params])
    print('intensity_scale por haz:', np.round(scales, 3),
          ' max/min = %.3f' % (scales.max() / scales.min()))
    stages = {
        'geometry': E.ebp_analytic(GEOM_POS, grid, donut_fwhm=shared),
        'individual_width': R.ebp_realistic(stripped_params(params, {'width'}), grid),
        'pedestal': R.ebp_realistic(stripped_params(params, {'width', 'pedestal'}), grid),
        'ellipticity': R.ebp_realistic(stripped_params(
            params, {'width', 'pedestal', 'ellipticity'}), grid),
        'background': R.ebp_realistic(stripped_params(
            params, {'width', 'pedestal', 'ellipticity', 'background', 'amplitude'}), grid),
    }
    ns, nb, samples = 2000, 95, 300
    sbr, total = ns / nb, ns + nb
    r0 = np.array([-5.07, -7.56])
    r0_idx = grid.to_index(r0)
    rs = 0.75 * 103.23  # 0.75·exp.L_eff (L_eff = 103.23 en su log)

    # 1) reproducción exacta de su corrida (misma semilla, mismo orden de etapas)
    rng = np.random.RandomState(20260901)
    out = {'reproduction': {}, 'with_beam_power': {}}
    print('\n1) reproducción de comparison_metrics.csv')
    print('%-17s %9s %9s | %9s %9s | %9s %9s' % ('etapa', 'CRB', 'ref', 'RMSEhon',
                                                  'ref', 'RMSEgeo', 'ref'))
    for name, cand in stages.items():
        crb = sim.crb_minflux(4, cand.PSFs, sbr, 1.0, 400.0, total, method='1')
        crb = float(crb[r0_idx[0], r0_idx[1]])
        h = monte_carlo(cand, cand, r0_idx, r0, sbr, total, samples, rng, rs)
        g = monte_carlo(cand, stages['geometry'], r0_idx, r0, sbr, total, samples, rng, rs)
        out['reproduction'][name] = {'crb': crb, 'honest': h, 'geometry_est': g,
                                     'ref': ref[name]}
        print('%-17s %9.4f %9.4f | %9.4f %9.4f | %9.4f %9.4f' % (
            name, crb, ref[name]['crb_at_emitter_nm'], h['rmse'], ref[name]['honest_rmse_nm'],
            g['rmse'], ref[name]['geometry_estimator_rmse_nm']))

    # 2) el mismo modelo final con la potencia relativa de cada haz
    full = R.ebp_realistic(params, grid, label='realista (como ella)')
    full_s = scaled(full, params, 'realista x intensity_scale')
    bg = stages['background']
    bg_s = scaled(bg, params, 'background x intensity_scale')
    print('\n2) potencias relativas: p_i en el emisor (señal pura)')
    for e in (bg, bg_s):
        lam = e.PSFs[:, r0_idx[0], r0_idx[1]]
        print('   %-32s p = %s' % (e.label or 'background', np.round(lam / lam.sum(), 4)))
    lam0 = bg.PSFs[:, r0_idx[0], r0_idx[1]]
    lam1 = bg_s.PSFs[:, r0_idx[0], r0_idx[1]]
    dp = lam1 / lam1.sum() / (lam0 / lam0.sum()) - 1
    out['p_rel_change'] = dp.tolist()
    print('   cambio relativo de p_i: %s' % np.round(dp, 3))

    rng2 = np.random.RandomState(20260901)
    for key, e in (('background_as_author', bg), ('background_with_power', bg_s)):
        crb = float(sim.crb_minflux(4, e.PSFs, sbr, 1.0, 400.0, total,
                                    method='1')[r0_idx[0], r0_idx[1]])
        h = monte_carlo(e, e, r0_idx, r0, sbr, total, 1000, rng2, rs)
        g = monte_carlo(e, stages['geometry'], r0_idx, r0, sbr, total, 1000, rng2, rs)
        # y el caso "generador con potencias reales, estimador realista sin ellas"
        out['with_beam_power'][key] = {'crb': crb, 'honest': h, 'geometry_est': g}
        print('   %-24s CRB=%.3f  honesto RMSE=%.3f |b|=%.3f   geometría RMSE=%.3f |b|=%.3f borde=%.2f'
              % (key, crb, h['rmse'], h['bias'], g['rmse'], g['bias'], g['frac_on_search_edge']))
    mm = monte_carlo(bg_s, bg, r0_idx, r0, sbr, total, 1000, rng2, rs)
    out['with_beam_power']['gen_power_est_author_model'] = mm
    print('   generador con potencias, estimador = modelo realista de ella: RMSE=%.3f |b|=%.3f bias_xy=%s'
          % (mm['rmse'], mm['bias'], np.round(mm['bias_xy'], 2)))
    fn = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3', 'F202_out.json')
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    json.dump(out, open(fn, 'w', encoding='utf-8'), indent=1)
    print('guardado en', fn)


if __name__ == '__main__':
    main()
