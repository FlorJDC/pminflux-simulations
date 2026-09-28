# -*- coding: utf-8 -*-
"""
¿Alcanza el estimador el límite de Cramér-Rao?

El CRB es una cota ASINTÓTICA: el estimador de máxima verosimilitud la alcanza
en el límite de muchos fotones, no necesariamente con los pocos fotones de una
localización MINFLUX real.  Este script barre el número de fotones y mide el
cociente RMSE/CRB para dos EBP:

  * ideal        — donas analíticas, cero profundo, modulación completa
  * experimental — donas medidas, cero de ~9 %, modulación parcial

Resultado: el ideal alcanza el CRB en todo el rango; el experimental sólo lo
alcanza a partir de algunos miles de fotones. Es decir, la mala profundidad del
cero cobra DOS veces: sube el CRB, y además impide alcanzarlo con pocos fotones.
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import tools.tools_simulations as tools
from tools import ebp as E

# ── configuración ────────────────────────────────────────────────────────────
PSF_FOLDER = r'C:\Data\psf\20260820'
K = 4
M_p = int(2e5)
dt = 50
Tlife = 0.001
factor = 1.05
SBR = 9.0                       # se mantiene fijo al variar N
R0_NM = np.array([5.0, -5.0])
R_SEARCH_FACTOR = 0.75
N_LIST = [100, 200, 400, 800, 1600, 3200]
SAMPLES = 250
SEED = 20260825
DONUT_FWHM = None               # None -> ajustado a las donas medidas

OUT = os.path.join(_HERE, 'figs', 'eficiencia_vs_fotones.png')
LOG = os.path.join(_HERE, 'eficiencia.log')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# Duplicar la salida al log, para que los números que van al documento sean
# trazables a la corrida que los produjo (misma idea que en run_and_save.py).
_console = sys.stdout
_logfile = open(LOG, 'w', encoding='utf-8')


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)
        return len(data)

    def flush(self):
        for s in self._streams:
            s.flush()


sys.stdout = _Tee(_console, _logfile)

τ = np.arange(K) / K * dt
a, b = 0.0, dt / K

grid = E.grid_from_fit_config(os.path.join(PSF_FOLDER, 'fit_config.txt'))
exp = E.ebp_experimental(PSF_FOLDER, K=K, grid=grid, label='Experimental')

if DONUT_FWHM is None:
    DONUT_FWHM = float(np.mean([E.fit_donut_fwhm(exp.PSFs[k], grid)['fwhm']
                                for k in range(K)]))

ide = E.ebp_ideal(grid, L=exp.L_eff, K=K, donut_fwhm=DONUT_FWHM, label='Ideal')

r0_idx = grid.to_index(R0_NM)
r_search = R_SEARCH_FACTOR * exp.L_eff

print(f'{grid}   FWHM = {DONUT_FWHM:.1f} nm   radio de búsqueda = {r_search:.1f} nm')
print(f'{SAMPLES} muestras por punto, semilla {SEED}\n')
print(f'{"EBP":<14} {"N":>6} {"CRB":>8} {"RMSE":>8} {"RMSE/CRB":>12} {"|sesgo|":>9}')
print('-' * 62)

curves = {}
for ebp in (ide, exp):
    ratios, errs, crbs = [], [], []
    for N in N_LIST:
        Ns = int(round(SBR / (SBR + 1) * N))
        Nb = N - Ns

        crb_map = tools.crb_minflux(K, ebp.PSFs, SBR, grid.px_nm, grid.size_nm,
                                    N, method='1')
        plt.close('all')
        crb = crb_map[r0_idx[0], r0_idx[1]]

        np.random.seed(SEED)
        est = np.full((2, SAMPLES), np.nan)
        for i in range(SAMPLES):
            relTime, _, failed = tools.sim_exp(
                'p_minflux', None, ebp.PSFs, r0_idx, SBR, Ns, Nb,
                M_p, Tlife, factor, dt)
            if failed:
                continue
            n_arr = tools.nMINFLUX(K, τ, relTime, a, b)
            est[:, i] = grid.to_space(
                tools.pos_MINFLUX(n_arr, ebp.PSFs, SBR=SBR,
                                  px_nm=grid.px_nm, r_max_nm=r_search))

        valid = est[:, ~np.isnan(est[0])]
        n_ok = valid.shape[1]
        sd = valid.std(axis=1)
        bias = valid.mean(axis=1) - R0_NM
        rmse = np.sqrt(0.5 * (sd[0]**2 + sd[1]**2 + bias[0]**2 + bias[1]**2))

        ratios.append(rmse / crb)
        errs.append(rmse / crb / np.sqrt(2 * n_ok))   # error estándar del cociente
        crbs.append(crb)
        print(f'{ebp.label:<14} {N:>6} {crb:>8.3f} {rmse:>8.3f} '
              f'{rmse/crb:>8.2f}±{errs[-1]:<4.2f} {np.linalg.norm(bias):>9.3f}')
    curves[ebp.label] = (np.array(ratios), np.array(errs), np.array(crbs))
    print()

# ── figura ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
style = {'Ideal': ('steelblue', 'o', '-'),
         'Experimental': ('tomato', 's', '--')}

ax = axes[0]
# El MLE devuelve un índice ENTERO de píxel, así que su salida está cuantizada.
# Una cuantización uniforme de paso `px` agrega una varianza px²/12. Un
# estimador PERFECTAMENTE eficiente pero cuantizado no daría 1 sino esta curva.
# Sin ella, el ascenso del caso ideal a N grande parece una falla del estimador
# cuando en realidad es un artefacto de la grilla: a N = 3200 el CRB ya es
# menor que el píxel.
_first = True
for label, (rat, err, crbs) in curves.items():
    c, m, ls = style[label]
    quant = np.sqrt(crbs**2 + grid.px_nm**2 / 12) / crbs
    ax.plot(N_LIST, quant, color=c, lw=1.1, ls=':', alpha=.75,
            label='límite por cuantización de la grilla' if _first else None)
    _first = False
    ax.errorbar(N_LIST, rat, yerr=err, color=c, marker=m, ls=ls, lw=2,
                ms=7, capsize=3, label=label)
ax.axhline(1.0, color='k', lw=1.2, ls='-', alpha=.5)
ax.text(N_LIST[0] * 1.05, 1.015, 'estimador eficiente', fontsize=9, color='0.35')
ax.set_xscale('log')
ax.set_xlabel('fotones por localización, N')
ax.set_ylabel('RMSE / CRB')
ax.set_title('¿Se alcanza el límite teórico?', fontweight='bold', fontsize=11)
ax.legend(fontsize=8.5)
ax.grid(alpha=.3, which='both')

ax = axes[1]
for label, (_, _, crbs) in curves.items():
    c, m, ls = style[label]
    ax.plot(N_LIST, crbs, color=c, marker=m, ls=ls, lw=2, ms=7, label=f'CRB {label}')
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlabel('fotones por localización, N')
ax.set_ylabel('σ [nm]')
ax.set_title('El CRB en sí mismo (escala log-log, pendiente −1/2)',
             fontweight='bold', fontsize=11)
ax.legend(fontsize=9)
ax.grid(alpha=.3, which='both')

fig.suptitle('La mala profundidad del cero cobra dos veces: sube el CRB '
             'y además impide alcanzarlo con pocos fotones',
             fontweight='bold', fontsize=12)
fig.tight_layout()
fig.savefig(OUT, dpi=130, bbox_inches='tight')
print(f'OK -> {OUT}')

# Restaurar stdout antes de cerrar el log (si no, el flush final del intérprete
# falla con ValueError sobre un archivo ya cerrado).
sys.stdout.flush()
sys.stdout = _console
_logfile.close()
print(f'[log] {LOG}')
