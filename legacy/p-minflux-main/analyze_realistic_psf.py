# -*- coding: utf-8 -*-
"""Ajusta y valida un modelo paramétrico realista de las PSFs p-MINFLUX.

Ejemplo:
    py analyze_realistic_psf.py --psf-folder C:\Data\psf\20260820

Los resultados se guardan por defecto en ``Resultados/realistic_psf``.
"""

import argparse
import copy
import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import tools.tools_simulations as sim
from tools import ebp as E
from tools import realistic_ebp as R


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--psf-folder', default=r'C:\Data\psf\20260820')
    parser.add_argument('--name-template', default='Dona_fit_fwd_{}.npy')
    parser.add_argument('--output', default=os.path.join('Resultados', 'realistic_psf'))
    parser.add_argument('--fit-radius-nm', type=float, default=180.0)
    parser.add_argument('--roi-radius-nm', type=float, default=80.0)
    parser.add_argument('--ns', type=int, default=2000)
    parser.add_argument('--nb', type=int, default=95)
    parser.add_argument('--samples', type=int, default=300)
    parser.add_argument('--seed', type=int, default=20260901)
    parser.add_argument('--emitter-x-nm', type=float, default=-5.07)
    parser.add_argument('--emitter-y-nm', type=float, default=-7.56)
    return parser.parse_args()


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
            mean_width = 0.5 * (p['fwhm_x_nm'] + p['fwhm_y_nm'])
            p['fwhm_x_nm'] = mean_width
            p['fwhm_y_nm'] = mean_width
            p['theta_rad'] = 0.0
    return result


def monte_carlo(ebp_gen, ebp_est, r0_idx, r0_nm, sbr, total, samples, rng,
                search_radius_nm):
    estimates = np.empty((samples, 2), dtype=float)
    k_beams = ebp_gen.K
    signal = ebp_gen.PSFs[:, r0_idx[0], r0_idx[1]].astype(float)
    signal /= np.sum(signal)
    probabilities = (sbr / (sbr + 1)) * signal + 1 / ((sbr + 1) * k_beams)
    # Precalcular el mismo mapa log(p_i) que usa pos_MINFLUX, pero sólo dentro
    # del ROI. Para cada muestra el MLE se reduce entonces a n @ log(p), sin
    # reconstruir K mapas de 400x400. Es algebraicamente idéntico y acelera la
    # validación Monte Carlo varios órdenes de magnitud.
    norm = np.sum(ebp_est.PSFs, axis=0)
    probabilities_map = ((sbr / (sbr + 1)) * ebp_est.PSFs / norm
                         + 1 / ((sbr + 1) * k_beams))
    rows, cols = np.indices(norm.shape)
    size_nm = ebp_est.grid.size_nm
    mx = cols * ebp_est.grid.px_nm - size_nm / 2
    my = size_nm / 2 - rows * ebp_est.grid.px_nm
    roi = np.hypot(mx, my) <= search_radius_nm
    roi_indices = np.argwhere(roi)
    logp = np.log(probabilities_map[:, roi])

    for j in range(samples):
        counts = rng.multinomial(total, probabilities)
        idx = tuple(roi_indices[np.argmax(counts @ logp)])
        estimates[j] = ebp_gen.grid.to_space(idx)
    mean = np.mean(estimates, axis=0)
    std = np.std(estimates, axis=0)
    bias = mean - r0_nm
    rmse = np.sqrt(np.mean(np.sum((estimates - r0_nm) ** 2, axis=1)) / 2)
    return {
        'mean_x_nm': float(mean[0]), 'mean_y_nm': float(mean[1]),
        'std_x_nm': float(std[0]), 'std_y_nm': float(std[1]),
        'bias_x_nm': float(bias[0]), 'bias_y_nm': float(bias[1]),
        'bias_magnitude_nm': float(np.linalg.norm(bias)), 'rmse_nm': float(rmse),
    }


def save_csv(path, rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, 'w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    os.makedirs(args.output, exist_ok=True)
    grid = E.grid_from_fit_config(os.path.join(args.psf_folder, 'fit_config.txt'))
    exp = E.ebp_experimental(args.psf_folder, K=4, grid=grid,
                             name_template=args.name_template, reference=0,
                             label='Experimental')
    params = R.fit_ebp_2d(exp, fit_radius_nm=args.fit_radius_nm)
    R.save_fit_json(os.path.join(args.output, 'fit_parameters.json'), params,
                    metadata={'psf_folder': os.path.abspath(args.psf_folder),
                              'fit_radius_nm': args.fit_radius_nm,
                              'grid': repr(grid)})

    shared_fwhm = params[0]['shared_fwhm_nm']
    stages = {
        'geometry': E.ebp_analytic(exp.pos_nm, grid, donut_fwhm=shared_fwhm,
                                   label='Geometría medida'),
        'individual_width': R.ebp_realistic(
            stripped_params(params, {'width'}), grid,
            label='Ancho individual'),
        'pedestal': R.ebp_realistic(
            stripped_params(params, {'width', 'pedestal'}), grid,
            label='+ pedestal'),
        'ellipticity': R.ebp_realistic(
            stripped_params(params, {'width', 'pedestal', 'ellipticity'}), grid,
            label='+ elipticidad'),
        'background': R.ebp_realistic(
            stripped_params(params, {'width', 'pedestal', 'ellipticity',
                                     'background', 'amplitude'}), grid,
            label='+ fondo y amplitud'),
        'experimental': exp,
    }

    metric_rows = []
    sbr = args.ns / args.nb
    total = args.ns + args.nb
    r0_nm = np.array([args.emitter_x_nm, args.emitter_y_nm])
    r0_idx = grid.to_index(r0_nm)
    search_radius_nm = 0.75 * exp.L_eff
    rng = np.random.RandomState(args.seed)
    for name, candidate in stages.items():
        crb = sim.crb_minflux(candidate.K, candidate.PSFs, sbr,
                              grid.px_nm, grid.size_nm, total, method='1')
        mc_honest = monte_carlo(candidate, candidate, r0_idx, r0_nm, sbr,
                                total, args.samples, rng, search_radius_nm)
        mc_ideal = monte_carlo(candidate, stages['geometry'], r0_idx, r0_nm,
                               sbr, total, args.samples, rng, search_radius_nm)
        for row in R.image_metrics(exp, candidate, args.roi_radius_nm):
            row.update({'stage': name,
                        'crb_at_emitter_nm': float(crb[r0_idx[0], r0_idx[1]]),
                        'honest_rmse_nm': mc_honest['rmse_nm'],
                        'honest_bias_nm': mc_honest['bias_magnitude_nm'],
                        'geometry_estimator_rmse_nm': mc_ideal['rmse_nm'],
                        'geometry_estimator_bias_nm': mc_ideal['bias_magnitude_nm']})
            metric_rows.append(row)
    save_csv(os.path.join(args.output, 'comparison_metrics.csv'), metric_rows)

    fit_rows = []
    for beam, p in enumerate(params):
        fit_rows.append(dict({'beam': beam}, **p))
    save_csv(os.path.join(args.output, 'fit_parameters.csv'), fit_rows)

    names = list(stages)
    fig, axes = plt.subplots(len(names), exp.K,
                             figsize=(3 * exp.K, 2.8 * len(names)))
    zoom = args.roi_radius_nm
    for i, name in enumerate(names):
        ebp = stages[name]
        for k in range(exp.K):
            ax = axes[i, k]
            ax.imshow(ebp.PSFs[k] / np.max(ebp.PSFs[k]), extent=grid.extent,
                      origin='upper', cmap='inferno', vmin=0, vmax=1)
            ax.set_xlim(exp.pos_nm[k, 0] - zoom, exp.pos_nm[k, 0] + zoom)
            ax.set_ylim(exp.pos_nm[k, 1] - zoom, exp.pos_nm[k, 1] + zoom)
            if i == 0:
                ax.set_title('haz {}'.format(k))
            if k == 0:
                ax.set_ylabel(ebp.label)
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle('Escalera de realismo de las PSFs p-MINFLUX')
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(os.path.join(args.output, 'model_stages.png'), dpi=180)
    plt.close(fig)

    print('Resultados guardados en {}'.format(os.path.abspath(args.output)))
    for beam, p in enumerate(params):
        print('haz {}: centro=({:.2f},{:.2f}) nm, FWHM=({:.1f},{:.1f}) nm, '
              'elipticidad={:.3f}, pedestal={:.3f}, grad/100nm={:.3f}, '
              'RMSE={:.4f}'.format(
                  beam, p['x0_nm'], p['y0_nm'], p['fwhm_x_nm'],
                  p['fwhm_y_nm'], p['ellipticity'], p['pedestal'],
                  p['gradient_per_100nm'], p['rmse_roi']))


if __name__ == '__main__':
    main()
