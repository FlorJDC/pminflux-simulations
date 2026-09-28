# -*- coding: utf-8 -*-
"""Ajuste 2D y reconstrucción paramétrica de PSFs p-MINFLUX.

El módulo mantiene separado el pedestal óptico de la PSF del fondo temporal
``Nb`` usado por la simulación de adquisición. Las intensidades se ajustan y
devuelven en unidades relativas al máximo de cada PSF experimental.
"""

import json
import numpy as np
from scipy.optimize import least_squares

from .ebp import EBP, fit_donut_fwhm


def _coordinates(grid):
    rows, cols = np.indices((grid.n_px, grid.n_px))
    x = cols * grid.px_nm - grid.size_nm / 2
    y = grid.size_nm / 2 - rows * grid.px_nm
    return x, y


def refine_minimum_quadratic(psf_2d, grid, center_nm=None, half_window_px=4):
    """Refina un mínimo a resolución subpíxel con una parábola 2D local.

    El ajuste local separa la posición del cero de la forma y el fondo a gran
    escala. Si la Hessiana no es positiva o el vértice sale de la ventana se
    conserva el mínimo discreto.
    """
    image = np.asarray(psf_2d, dtype=float)
    if center_nm is None:
        row, col = np.unravel_index(np.argmin(image), image.shape)
    else:
        row, col = grid.to_index(center_nm)
    rows, cols = np.indices(image.shape)
    mask = ((np.abs(rows - row) <= half_window_px)
            & (np.abs(cols - col) <= half_window_px))
    dx = (cols[mask] - col) * grid.px_nm
    dy = -(rows[mask] - row) * grid.px_nm
    design = np.column_stack((np.ones(mask.sum()), dx, dy, dx ** 2,
                              dx * dy, dy ** 2))
    coef = np.linalg.lstsq(design, image[mask], rcond=None)[0]
    hessian = np.array([[2 * coef[3], coef[4]],
                        [coef[4], 2 * coef[5]]])
    discrete = np.asarray(grid.to_space((row, col)), dtype=float)
    if np.any(np.linalg.eigvalsh(hessian) <= 0):
        return discrete
    shift = -np.linalg.solve(hessian, coef[1:3])
    limit = half_window_px * grid.px_nm
    if np.any(np.abs(shift) > limit):
        return discrete
    return discrete + shift


def donut_2d(params, grid, features=None):
    """Evalúa una dona elíptica, rotada, con pedestal y fondo plano.

    ``features`` permite apagar componentes conservando los parámetros del
    ajuste completo. Las opciones son ``individual_width``, ``pedestal``,
    ``ellipticity`` y ``background``.
    """
    if features is None:
        features = {'individual_width', 'pedestal', 'ellipticity', 'background'}
    features = set(features)
    x, y = _coordinates(grid)
    x0, y0 = params['x0_nm'], params['y0_nm']
    dx, dy = x - x0, y - y0

    if 'individual_width' in features:
        wx, wy = params['fwhm_x_nm'], params['fwhm_y_nm']
    else:
        wx = wy = params.get('shared_fwhm_nm',
                             0.5 * (params['fwhm_x_nm'] + params['fwhm_y_nm']))
    theta = params['theta_rad'] if 'ellipticity' in features else 0.0
    if 'ellipticity' not in features:
        wx = wy = 0.5 * (wx + wy)

    ct, st = np.cos(theta), np.sin(theta)
    xp = ct * dx + st * dy
    yp = -st * dx + ct * dy
    q = (xp / wx) ** 2 + (yp / wy) ** 2
    donut = 4 * np.e * np.log(2) * q * np.exp(-4 * np.log(2) * q)

    pedestal = params['pedestal'] if 'pedestal' in features else 0.0
    result = pedestal + params['amplitude'] * donut
    if 'background' in features:
        result = result + params['gradient_x_per_nm'] * dx
        result = result + params['gradient_y_per_nm'] * dy
    return np.maximum(result, np.finfo(float).eps)


def fit_donut_2d(psf_2d, grid, center_nm=None, fit_radius_nm=180.0,
                 loss='soft_l1'):
    """Ajusta una PSF con una dona elíptica más pedestal y fondo plano.

    El centro inicial puede provenir de la geometría experimental. El ajuste
    devuelve el centro con resolución subpíxel y métricas dentro del ROI.
    """
    image = np.asarray(psf_2d, dtype=float)
    scale = float(np.max(image))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('La PSF debe contener intensidad positiva y finita')
    target = np.maximum(image, 0) / scale
    x, y = _coordinates(grid)
    if center_nm is None:
        row, col = np.unravel_index(np.argmin(target), target.shape)
        center_nm = grid.to_space((row, col))
    center_nm = refine_minimum_quadratic(image, grid, center_nm=center_nm)
    radius = np.hypot(x - center_nm[0], y - center_nm[1])
    mask = radius <= min(float(fit_radius_nm), grid.size_nm / 2 - grid.px_nm)

    radial = fit_donut_fwhm(image, grid, center_nm=center_nm,
                            r_max_nm=fit_radius_nm)
    f0 = float(np.clip(radial['fwhm'], 100.0, 800.0))
    pedestal0 = float(np.clip(radial['offset'] / scale, 0.0, 0.5))
    amp0 = max(0.1, 1.0 - pedestal0)
    p0 = np.array([center_nm[0], center_nm[1], f0, f0, 0.0,
                   pedestal0, amp0, 0.0, 0.0])
    # El centro ya fue estimado localmente. El margen pequeño sólo absorbe la
    # covarianza residual sin permitir que el fondo global arrastre el mínimo.
    center_margin = 0.25 * grid.px_nm
    lower = np.array([center_nm[0] - center_margin,
                      center_nm[1] - center_margin, 0.65 * f0, 0.65 * f0,
                      -np.pi / 2, 0.0, 0.05, -0.01, -0.01])
    upper = np.array([center_nm[0] + center_margin,
                      center_nm[1] + center_margin, 1.50 * f0, 1.50 * f0,
                      np.pi / 2, 0.8, 3.0, 0.01, 0.01])

    xm, ym, tm = x[mask], y[mask], target[mask]

    def residual(v):
        x0, y0, wx, wy, theta, pedestal, amplitude, gx, gy = v
        dx, dy = xm - x0, ym - y0
        ct, st = np.cos(theta), np.sin(theta)
        xp, yp = ct * dx + st * dy, -st * dx + ct * dy
        q = (xp / wx) ** 2 + (yp / wy) ** 2
        donut = 4 * np.e * np.log(2) * q * np.exp(-4 * np.log(2) * q)
        return pedestal + amplitude * donut + gx * dx + gy * dy - tm

    opt = least_squares(residual, p0, bounds=(lower, upper), loss=loss,
                        f_scale=0.02, x_scale='jac', max_nfev=3000)
    v = opt.x
    params = {
        'x0_nm': float(v[0]), 'y0_nm': float(v[1]),
        'fwhm_x_nm': float(v[2]), 'fwhm_y_nm': float(v[3]),
        'theta_rad': float(v[4]), 'theta_deg': float(np.degrees(v[4])),
        'pedestal': float(v[5]), 'amplitude': float(v[6]),
        'gradient_x_per_nm': float(v[7]),
        'gradient_y_per_nm': float(v[8]),
        'gradient_per_100nm': float(100 * np.hypot(v[7], v[8])),
        'ellipticity': float(max(v[2], v[3]) / min(v[2], v[3])),
        'fit_radius_nm': float(fit_radius_nm), 'intensity_scale': scale,
        'success': bool(opt.success), 'message': str(opt.message),
    }
    fitted = donut_2d(params, grid)
    diff = fitted[mask] - target[mask]
    params['rmse_roi'] = float(np.sqrt(np.mean(diff ** 2)))
    params['mae_roi'] = float(np.mean(np.abs(diff)))
    local_zero = np.hypot(x - v[0], y - v[1]) <= 5 * grid.px_nm
    params['zero_ratio_model'] = float(np.min(fitted[local_zero]) /
                                       np.max(fitted))
    params['zero_ratio_experimental'] = float(np.min(target) / np.max(target))
    return params


def fit_ebp_2d(experimental_ebp, fit_radius_nm=180.0):
    """Ajusta independientemente todos los haces de un EBP experimental."""
    params = []
    for k in range(experimental_ebp.K):
        params.append(fit_donut_2d(
            experimental_ebp.PSFs[k], experimental_ebp.grid,
            center_nm=experimental_ebp.pos_nm[k],
            fit_radius_nm=fit_radius_nm))
    shared = float(np.mean([
        0.5 * (p['fwhm_x_nm'] + p['fwhm_y_nm']) for p in params]))
    for p in params:
        p['shared_fwhm_nm'] = shared
    return params


def ebp_realistic(params, grid, features=None, label='Realista ajustado'):
    """Construye un EBP paramétrico a partir de ajustes producidos aquí."""
    psfs = np.stack([donut_2d(p, grid, features=features) for p in params])
    positions = np.array([[p['x0_nm'], p['y0_nm']] for p in params])
    return EBP(psfs, positions, grid, label=label)


def image_metrics(reference_ebp, candidate_ebp, roi_radius_nm=80.0):
    """Métricas de imagen por haz, normalizadas por el máximo de cada mapa."""
    if reference_ebp.grid != candidate_ebp.grid or reference_ebp.K != candidate_ebp.K:
        raise ValueError('Los EBP deben compartir grilla y cantidad de haces')
    x, y = _coordinates(reference_ebp.grid)
    output = []
    for k in range(reference_ebp.K):
        center = reference_ebp.pos_nm[k]
        mask = np.hypot(x - center[0], y - center[1]) <= roi_radius_nm
        ref = reference_ebp.PSFs[k] / np.max(reference_ebp.PSFs[k])
        cand = candidate_ebp.PSFs[k] / np.max(candidate_ebp.PSFs[k])
        delta = cand[mask] - ref[mask]
        zero_mask = np.hypot(x - center[0], y - center[1]) <= 5 * reference_ebp.grid.px_nm
        output.append({
            'beam': k,
            'rmse_roi': float(np.sqrt(np.mean(delta ** 2))),
            'mae_roi': float(np.mean(np.abs(delta))),
            'bias_roi': float(np.mean(delta)),
            'zero_ratio_reference': float(np.min(ref[zero_mask]) / np.max(ref)),
            'zero_ratio_model': float(np.min(cand[zero_mask]) / np.max(cand)),
        })
    return output


def save_fit_json(path, params, metadata=None):
    """Guarda parámetros y metadatos sin depender de tipos NumPy."""
    payload = {'metadata': metadata or {}, 'beams': params}
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
