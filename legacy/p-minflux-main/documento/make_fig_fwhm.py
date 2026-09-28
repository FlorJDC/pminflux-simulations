# -*- coding: utf-8 -*-
"""
Figura explicativa: cómo se determina el tamaño de las donas medidas.

Tres paneles, sobre la dona del haz 0:
  1. el máximo del anillo cae en el borde del FOV o fuera de él
  2. por eso el argmax del perfil radial satura en el último bin
  3. lo que sí determina el parámetro es el apartamiento de la parábola

No forma parte de `simulation_misalignment.py` porque es material didáctico del
documento, no un resultado de la simulación.
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_HERE = os.path.dirname(os.path.abspath(__file__))     # .../p-minflux-main/documento
_PROJ = os.path.dirname(_HERE)                         # .../p-minflux-main
sys.path.insert(0, _PROJ)

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from tools import ebp as E

ln2 = np.log(2)

# ── configuración ────────────────────────────────────────────────────────────
PSF_FOLDER = r'C:\Data\psf\20260820'
BEAM = 0                      # qué haz se usa para ilustrar
L_REF = 103.23                # [nm] para marcar la región de operación MINFLUX
OUT = os.path.join(_HERE, 'figs', 'explicacion_fwhm.png')

os.makedirs(os.path.dirname(OUT), exist_ok=True)

grid = E.grid_from_fit_config(os.path.join(PSF_FOLDER, 'fit_config.txt'))
exp = E.ebp_experimental(PSF_FOLDER, K=4, grid=grid)

fit = E.fit_donut_fwhm(exp.PSFs[BEAM], grid)
fwhm, C, A = fit['fwhm'], fit['offset'], fit['amplitude']
r_ring = fit['r_ring']
half_fov = grid.size_nm / 2

fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.8))

# ── Panel 1: el anillo cae fuera del campo medido ────────────────────────────
ax = axes[0]
r_ext = np.linspace(0, 2 * half_fov, 800)
m_ext = C + A * (r_ext**2 / fwhm**2) * np.exp(-4 * ln2 * r_ext**2 / fwhm**2)

ax.axvspan(half_fov, 2 * half_fov, color='0.88', zorder=0)
ax.plot(r_ext, m_ext, color='tomato', lw=2, ls='--', label='modelo (extrapolado)')
ax.plot(fit['r'], fit['profile'], color='steelblue', lw=2.6, label='dona medida')
ax.axvline(half_fov, color='k', lw=1.3, ls=':')
ax.plot([r_ring],
        [C + A * (r_ring**2 / fwhm**2) * np.exp(-4 * ln2 * r_ring**2 / fwhm**2)],
        'o', ms=9, color='seagreen', zorder=5)
ax.annotate(f'máximo del anillo\nr = {r_ring:.0f} nm', (r_ring, m_ext.max()),
            xytext=(r_ring + 18, m_ext.max() * 0.80), fontsize=9, color='seagreen',
            arrowprops=dict(arrowstyle='->', color='seagreen'))
ax.text(1.5 * half_fov, m_ext.max() * 0.35, 'sin datos\n(fuera del FOV)',
        ha='center', fontsize=9.5, color='0.3')
ax.text(half_fov - 4, m_ext.max() * 0.97, 'borde del FOV', ha='right', fontsize=9)
ax.set_xlim(0, 2 * half_fov)
ax.set_xlabel('r [nm]')
ax.set_ylabel('intensidad media')
ax.set_title('1. El anillo no entra en el campo medido', fontweight='bold', fontsize=11)
ax.legend(fontsize=8.5, loc='lower right')
ax.grid(alpha=.3)

# ── Panel 2: el perfil es monótono -> argmax degenerado ──────────────────────
ax = axes[1]
ax.plot(fit['r'], fit['profile'], color='steelblue', lw=2.6)
ax.plot([fit['r'][np.argmax(fit['profile'])]], [fit['profile'].max()],
        'v', ms=13, color='crimson', zorder=5)
span = fit['profile'].max() - fit['profile'].min()
ax.annotate('el argmax cae en el BORDE\nsiempre, para cualquier dona',
            (fit['r'][-1], fit['profile'].max()),
            xytext=(0.55 * half_fov, fit['profile'].min() + 0.62 * span),
            fontsize=9, color='crimson',
            arrowprops=dict(arrowstyle='->', color='crimson'))
ax.set_xlabel('r [nm]')
ax.set_ylabel('intensidad media')
ax.set_title('2. Por eso "buscar el máximo" es degenerado',
             fontweight='bold', fontsize=11)
ax.grid(alpha=.3)

# ── Panel 3: lo que sí determina el parámetro ────────────────────────────────
ax = axes[2]
inner = fit['r'] <= 60                       # zona donde la dona es casi parabólica
coef = np.polyfit(fit['r'][inner]**2, fit['profile'][inner], 1)
parab = np.polyval(coef, fit['r']**2)

ax.plot(fit['r'], parab, color='goldenrod', lw=1.9, ls='-.',
        label='parábola pura  C + a·r²')
ax.plot(fit['r'], fit['profile'], color='steelblue', lw=2.6, label='dona medida')
ax.plot(fit['r'], fit['fitted'], color='tomato', lw=1.8, ls='--',
        label='modelo ajustado')
ax.fill_between(fit['r'], parab, fit['profile'],
                where=(parab > fit['profile']), color='gold', alpha=.3)
ax.annotate('este apartamiento\nes lo que fija el FWHM',
            (0.75 * half_fov, np.polyval(coef, (0.75 * half_fov)**2)),
            xytext=(0.19 * half_fov, np.polyval(coef, (0.95 * half_fov)**2) * 0.72),
            fontsize=9.5, color='darkgoldenrod',
            arrowprops=dict(arrowstyle='->', color='darkgoldenrod'))
ax.axvspan(0, L_REF / 2, color='mediumpurple', alpha=.12, zorder=0)
ax.text(L_REF / 4, fit['profile'].min() + 0.05 * span, 'región MINFLUX',
        ha='center', fontsize=8.5, color='rebeccapurple')
ax.set_ylim(fit['profile'].min() * 0.998, fit['profile'].max() * 1.02)
ax.set_xlabel('r [nm]')
ax.set_ylabel('intensidad media')
ax.set_title('3. El FWHM sale del apartamiento de la parábola',
             fontweight='bold', fontsize=11)
ax.legend(fontsize=8.5, loc='lower right')
ax.grid(alpha=.3)

fig.suptitle('Cómo se determina el FWHM de las donas medidas  '
             f'(haz {BEAM}: FWHM = {fwhm:.0f} nm, anillo {r_ring:.0f} nm)',
             fontweight='bold', fontsize=13)
fig.tight_layout()
fig.savefig(OUT, dpi=130, bbox_inches='tight')
print(f'OK -> {OUT}')
