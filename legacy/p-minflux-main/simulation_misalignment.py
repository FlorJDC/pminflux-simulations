# -*- coding: utf-8 -*-
"""
Efecto del desalineamiento del EBP sobre la precisión de localización p-MINFLUX
==============================================================================

La pregunta: cuánta precisión se pierde cuando el patrón de excitación no es
el triángulo equilátero ideal, y cuánto de esa pérdida se debe a cada causa.

Se separan tres contribuciones, comparando EBPs construidos de tres maneras
distintas pero sobre LA MISMA grilla (ver `tools/ebp.py`):

    ideal      donas analíticas perfectas en un triángulo perfecto
    geom_exp   donas analíticas perfectas en las posiciones MEDIDAS
               -> aísla el efecto de la GEOMETRÍA del patrón
    exp        las PSFs medidas tal cual
               -> agrega el efecto de la FORMA real de cada dona

y dos maneras de estimar:

    honesta    el estimador usa las mismas PSFs que generaron los fotones
               -> el error es sólo varianza; debería alcanzar el CRB
    ingenua    el estimador supone el EBP ideal aunque la física sea otra
               -> aparece un SESGO que no se reduce juntando más fotones

Para probar otras geometrías, editar `EBP_LIBRARY` más abajo: cualquier set de
coordenadas (K,2) en nm se puede pasar a `ebp_analytic`.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

import tools.tools_simulations as tools
from tools import ebp as E
from tools import realistic_ebp as R

plt.close('all')

# ═══════════════════════════════════════════════════════════════════════════
# 1. CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

# ── datos experimentales ──────────────────────────────────────────────────
PSF_FOLDER = r'C:\Data\psf\20260820'
NAME_TMPL  = 'Dona_fit_fwd_{}.npy'
K          = 4

# ── fotofísica y adquisición ──────────────────────────────────────────────
Ns, Nb  = 2000, 95         # fotones de señal y de fondo
SBR     = Ns / Nb         # signal-to-background ratio
N       = Ns + Nb         # fotones totales por localización
M_p     = int(2e5)        # ciclos de excitación
dt      = 50              # período del ciclo TCSPC [ns]
Tlife   = 0.001           # vida media del fluoróforo [ns]
factor  = 1.05
samples = 1000             # localizaciones independientes por caso

# Semilla del generador aleatorio: fija los resultados Monte Carlo para que el
# script sea reproducible. Con `samples` finito los estadísticos tienen su
# propia incertidumbre (~1/√(2·samples) relativo para las desviaciones
# estándar), así que sin semilla los números bailan entre corridas.
# Poner None para muestrear libremente.
SEED = 20260825

# ── posición del emisor: la MISMA en todos los casos (comparabilidad) ─────
R0_NM = np.array([-5.07, -7.56]) #np.array([5.0, -5.0])

# ── radio de búsqueda del estimador ───────────────────────────────────────
# El MLE busca el máximo de verosimilitud sólo dentro de |r| < R_SEARCH_NM.
# Un MINFLUX real estima localmente, así que acotar es lo correcto; sin cota
# el argmax puede irse a un máximo espurio en el borde del FOV (efecto muy
# marcado con PSFs experimentales, cuyo fondo estructurado cubre todo el campo).
# Como referencia se usa el tamaño del patrón, no un número fijo.
R_SEARCH_FACTOR = 0.75    # radio = R_SEARCH_FACTOR * L_eff

# ── visualización ─────────────────────────────────────────────────────────
ZOOM_FACTOR = 1# 1.5         # mapas CRB: ventana de ±ZOOM_FACTOR·L_eff
BEAM_COLORS = ['gold', 'steelblue', 'tomato', 'limegreen']

# ── tamaño de las donas analíticas ────────────────────────────────────────
# Parámetro de escala en la CONVENCIÓN DE LA LITERATURA: entra directo en la
# fórmula de la dona, y el radio del anillo resulta 0.6006·FWHM.
#   Balzarotti et al. 2017, ec. (S16)
#   Tarkowski & Stefani, ACS Photonics 2025, ec. [4]  -> 360 nm (anillo 216 nm)
#   Marin & Ries, Nat. Commun. 2026, SimuFLUX         -> 310 nm (anillo 186 nm)
#
# None       -> se ajusta a las donas experimentales medidas (recomendado)
# un número  -> se fuerza ese valor [nm]
DONUT_FWHM = None

# Modelo 2D intermedio entre las donas perfectas y los mapas experimentales.
# Ajusta por haz pedestal, elipticidad, orientación, amplitud y fondo plano.
# Permite estudiar qué parte del deterioro se explica mediante parámetros
# físicos compactos, sin copiar directamente todos los píxeles medidos.
INCLUDE_REALISTIC_FIT = True
REALISTIC_FIT_RADIUS_NM = 180.0

τ    = np.arange(K) / K * dt
a, b = 0.0, dt / K


# ═══════════════════════════════════════════════════════════════════════════
# 2. CONSTRUIR LOS EBP
# ═══════════════════════════════════════════════════════════════════════════

print('Cargando PSFs experimentales...')
grid = E.grid_from_fit_config(os.path.join(PSF_FOLDER, 'fit_config.txt'))
exp = E.ebp_experimental(PSF_FOLDER, K=K, grid=grid,
                         name_template=NAME_TMPL, reference=0,
                         label='Experimental')
print(f'  {grid}')

# FWHM de las donas simuladas: ajustado al de las medidas, para que la única
# diferencia entre `geom_exp` y `exp` sea la forma real (no el tamaño).
if DONUT_FWHM is None:
    fits = [E.fit_donut_fwhm(exp.PSFs[k], grid) for k in range(K)]
    DONUT_FWHM = float(np.mean([f['fwhm'] for f in fits]))
    R_RING = float(np.mean([f['r_ring'] for f in fits]))
    print(f'  FWHM ajustado a las donas medidas: {DONUT_FWHM:.1f} nm '
          f'(error de ajuste < {max(f["rmse_rel"] for f in fits)*100:.1f}%)')
    print(f'  radio del anillo: {R_RING:.1f} nm   '
          f'[referencias: SimuFLUX 186 nm, Tarkowski & Stefani 216 nm]')
    zeros_txt = ', '.join('{:.1f}%'.format(f['zero_ratio'] * 100) for f in fits)
    print(f'  profundidad del cero por haz: {zeros_txt}   '
          f'[Balzarotti 2017 reporta < 0.2 %]')

# L de referencia para el caso ideal: el mismo tamaño efectivo que el medido,
# así la comparación aísla la FORMA del patrón y no su escala.
L_REF = exp.L_eff

EBP_LIBRARY = {
    'ideal':    E.ebp_ideal(grid, L=L_REF, K=K, donut_fwhm=DONUT_FWHM,
                            label='Ideal'),
    'geom_exp': E.ebp_analytic(exp.pos_nm, grid, donut_fwhm=DONUT_FWHM,
                               label='Geometría medida\n+ donas perfectas'),
    'exp':      exp,
    # Para probar otra geometría, agregar acá. Por ejemplo:
    # 'mi_test': E.ebp_analytic(np.array([[0,0], [-50,-30], [50,-30], [0,55]]),
    #                           grid, donut_fwhm=DONUT_FWHM, label='Mi test'),
}

if INCLUDE_REALISTIC_FIT:
    realistic_params = R.fit_ebp_2d(exp,
                                    fit_radius_nm=REALISTIC_FIT_RADIUS_NM)
    EBP_LIBRARY['realistic_fit'] = R.ebp_realistic(
        realistic_params, grid, label='Ajuste 2D realista')

print()
for e in EBP_LIBRARY.values():
    print(e.summary())
    print()


# ═══════════════════════════════════════════════════════════════════════════
# 3. DEFINICIÓN DE LOS CASOS
# ═══════════════════════════════════════════════════════════════════════════
# Cada caso es (etiqueta, EBP que genera los fotones, EBP que asume el estimador).
# gen == est  -> estimador honesto  |  gen != est -> estimador ingenuo.

CASES = [
    ('Ideal',              'ideal',    'ideal'),
    ('Geom. medida honesta', 'geom_exp', 'geom_exp'),
    ('Geom. medida ingenua', 'geom_exp', 'ideal'),
    ('Experimental honesta', 'exp', 'exp'),
    ('Experimental ingenua', 'exp', 'ideal'),
    ('Experimental ingenua 1', 'exp', 'geom_exp'),
    ('Experimental ingenua 2', 'geom_exp','exp'),
]

if INCLUDE_REALISTIC_FIT:
    CASES.extend([
        ('Realista honesta', 'realistic_fit', 'realistic_fit'),
        ('Realista ingenua', 'realistic_fit', 'ideal'),
    ])

r0_idx = grid.to_index(R0_NM)
R_SEARCH_NM = R_SEARCH_FACTOR * L_REF
print(f'Emisor r0 = {R0_NM} nm  ->  pixel {tuple(r0_idx)}')
print(f'Radio de búsqueda del MLE: {R_SEARCH_NM:.1f} nm')


# ═══════════════════════════════════════════════════════════════════════════
# 4. CRB — límite teórico de precisión para cada EBP
# ═══════════════════════════════════════════════════════════════════════════

print('\nCalculando CRB...')
crb_map = {}
for key, e in EBP_LIBRARY.items():
    crb_map[key] = tools.crb_minflux(K, e.PSFs, SBR, grid.px_nm, grid.size_nm,
                                     N, method='1')
    print(f'  {key:10s} CRB(r0) = {crb_map[key][r0_idx[0], r0_idx[1]]:6.2f} nm')


# ═══════════════════════════════════════════════════════════════════════════
# 5. SIMULACIÓN MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════════

def run_case(label, ebp_gen, ebp_est, r0_idx, r0_true_nm, n_samples):
    """
    Simula `n_samples` localizaciones independientes.

    ebp_gen : EBP que genera los fotones — la física real del microscopio
    ebp_est : EBP que asume el estimador — el modelo que usa el software

    Returns
    -------
    dict con las estimaciones válidas y sus estadísticos.
    """
    est = np.full((2, n_samples), np.nan)
    fails = 0

    for i in range(n_samples):
        if (i + 1) % 25 == 0:
            print(f'    {label}: {i+1}/{n_samples}', flush=True)
        params = [ebp_gen.PSFs, r0_idx, SBR, Ns, Nb, M_p, Tlife, factor, dt]
        relTime, _, failed = tools.sim_exp('p_minflux', None, *params)
        if failed:
            fails += 1
            continue
        n_arr = tools.nMINFLUX(K, τ, relTime, a, b)
        idx = tools.pos_MINFLUX(n_arr, ebp_est.PSFs, SBR=SBR,
                                px_nm=grid.px_nm, r_max_nm=R_SEARCH_NM)
        est[:, i] = grid.to_space(idx)

    valid = est[:, ~np.isnan(est[0])]
    n = valid.shape[1]
    mean = np.mean(valid, axis=1)
    std = np.std(valid, axis=1)
    bias = mean - r0_true_nm
    # RMSE 2D: combina varianza y sesgo, promediando ambos ejes
    rmse = np.sqrt(0.5 * (std[0]**2 + std[1]**2 + bias[0]**2 + bias[1]**2))

    # Incertidumbre de los estadísticos con n muestras finitas:
    #   error estándar de una desviación estándar  ~ std/√(2n)
    #   error estándar de una media                =  std/√n
    # Sin esto los valores no son interpretables: parte de lo que se ve
    # cambiar entre corridas es sólo ruido de muestreo.
    std_err = std / np.sqrt(2 * n)
    bias_err = std / np.sqrt(n)
    rmse_err = rmse / np.sqrt(2 * n)

    return {'label': label, 'valid': valid, 'mean': mean, 'std': std,
            'bias': bias, 'rmse': rmse, 'fails': fails, 'n': n,
            'std_err': std_err, 'bias_err': bias_err, 'rmse_err': rmse_err,
            'gen': ebp_gen, 'est': ebp_est}


print('\nSimulando...')
if SEED is not None:
    np.random.seed(SEED)
    print(f'  semilla = {SEED} (resultados reproducibles)')
results = []
for label, gen_key, est_key in CASES:
    results.append(run_case(label, EBP_LIBRARY[gen_key], EBP_LIBRARY[est_key],
                            r0_idx, R0_NM, samples))


# ═══════════════════════════════════════════════════════════════════════════
# 6. TABLA DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════

W = 86
print('\n' + '=' * W)
print(f'{"caso":<22} {"CRB":>6} {"std_x":>12} {"std_y":>12} '
      f'{"|sesgo|":>13} {"RMSE":>12} {"RMSE/CRB":>9}')
print('-' * W)
for (label, gen_key, _), r in zip(CASES, results):
    crb = crb_map[gen_key][r0_idx[0], r0_idx[1]]
    bmag = np.linalg.norm(r['bias'])
    berr = np.linalg.norm(r['bias_err'])
    print(f'{label:<22} {crb:>6.2f} '
          f'{r["std"][0]:>7.2f}±{r["std_err"][0]:<4.2f} '
          f'{r["std"][1]:>7.2f}±{r["std_err"][1]:<4.2f} '
          f'{bmag:>8.2f}±{berr:<4.2f} '
          f'{r["rmse"]:>7.2f}±{r["rmse_err"]:<4.2f} '
          f'{r["rmse"]/crb:>9.2f}')
print('=' * W)
print(f'{samples} muestras por caso; incertidumbres = error estándar del estadístico.')
print('RMSE/CRB ~ 1  -> el estimador alcanza el límite teórico (sólo varianza)')
print('RMSE/CRB >> 1 -> hay sesgo: no se corrige juntando más fotones')


# ═══════════════════════════════════════════════════════════════════════════
# 7. FIGURAS
# ═══════════════════════════════════════════════════════════════════════════

n_ebp = len(EBP_LIBRARY)
geom_lim = 1.2 * L_REF

# La ventana de zoom no puede exceder el FOV: si L_eff es grande o ZOOM_FACTOR
# alto, sin este tope el recorte para la escala de color se iría fuera del
# arreglo y la normalización saldría de una región equivocada, en silencio.
zoom = min(ZOOM_FACTOR * L_REF, grid.size_nm / 2)

# Colores de los haces: se ciclan para que K > len(BEAM_COLORS) no rompa.
beam_color = lambda k: BEAM_COLORS[k % len(BEAM_COLORS)]

# ── Fig 1: geometría de los patrones ──────────────────────────────────────
fig, axes = plt.subplots(1, n_ebp, figsize=(4.2 * n_ebp, 4.4))
for ax, e in zip(np.atleast_1d(axes), EBP_LIBRARY.values()):
    for k in range(K):
        ax.scatter(*e.pos_nm[k], s=170, c=beam_color(k), edgecolor='k',
                   zorder=3, label=f'haz {k}')
        ax.annotate(str(k), e.pos_nm[k], fontsize=9, ha='center', va='center',
                    zorder=4)
    ax.add_patch(Circle((0, 0), L_REF / 2, fill=False, ls='--',
                        ec='gray', zorder=1))
    ax.scatter(*R0_NM, marker='*', s=220, c='k', zorder=5, label='emisor')
    ax.set_title(f'{e.label}\nL_eff={e.L_eff:.1f} nm  asim={e.asymmetry:.2f} nm',
                 fontsize=10)
    ax.set_xlim(-geom_lim, geom_lim); ax.set_ylim(-geom_lim, geom_lim)
    ax.set_aspect('equal'); ax.grid(alpha=.3)
    ax.set_xlabel('x [nm]')
np.atleast_1d(axes)[0].set_ylabel('y [nm]')
np.atleast_1d(axes)[-1].legend(fontsize=7, loc='upper right')
fig.suptitle('Geometría de los patrones de excitación', fontweight='bold')
fig.tight_layout()

# ── Fig 2: las PSFs ───────────────────────────────────────────────────────
fig, axes = plt.subplots(n_ebp, K, figsize=(3.0 * K, 3.0 * n_ebp))
axes = np.atleast_2d(axes)
for i, e in enumerate(EBP_LIBRARY.values()):
    # misma escala de color por fila -> las donas son comparables entre sí
    vmax = e.PSFs.max()
    for k in range(K):
        ax = axes[i, k]
        ax.imshow(e.PSFs[k], extent=grid.extent, origin='upper',
                  cmap='inferno', vmin=0, vmax=vmax)
        ax.plot(*e.pos_nm[k], 'o', ms=6, mfc='none', mec='cyan', mew=1.6)
        ax.set_xlim(-zoom, zoom); ax.set_ylim(-zoom, zoom)
        if i == 0:
            ax.set_title(f'haz {k}', fontsize=10)
        if k == 0:
            ax.set_ylabel(e.label.replace('\n', ' '), fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
fig.suptitle('PSFs (zoom a la región de operación)', fontweight='bold')
fig.tight_layout()

# ── Fig 3: mapas de CRB ───────────────────────────────────────────────────
# misma escala de color en todos -> los mapas son comparables entre sí
_lo = max(0, int(grid.n_px / 2 - zoom / grid.px_nm))
_hi = min(grid.n_px, int(grid.n_px / 2 + zoom / grid.px_nm))
sl = (slice(_lo, _hi),) * 2
vmax_crb = max(np.nanpercentile(crb_map[k][sl], 99) for k in EBP_LIBRARY)

fig, axes = plt.subplots(1, n_ebp, figsize=(4.6 * n_ebp, 4.2))
for ax, (key, e) in zip(np.atleast_1d(axes), EBP_LIBRARY.items()):
    im = ax.imshow(crb_map[key], extent=grid.extent, origin='upper',
                   cmap='viridis', vmin=0, vmax=vmax_crb)
    ax.add_patch(Circle((0, 0), L_REF / 2, fill=False, ls='--', ec='w'))
    ax.scatter(*R0_NM, marker='*', s=180, c='r', zorder=5)
    ax.set_xlim(-zoom, zoom); ax.set_ylim(-zoom, zoom)
    ax.set_title(f'{e.label}\nCRB(r0) = '
                 f'{crb_map[key][r0_idx[0], r0_idx[1]]:.2f} nm', fontsize=10)
    ax.set_xlabel('x [nm]')
np.atleast_1d(axes)[0].set_ylabel('y [nm]')
fig.colorbar(im, ax=np.atleast_1d(axes), label='σ_CRB [nm]', shrink=.85)
fig.suptitle('Límite de Cramér-Rao', fontweight='bold')

# ── Fig 4: dispersión de las estimaciones ─────────────────────────────────
n_c = len(results)
fig, axes = plt.subplots(1, n_c, figsize=(3.6 * n_c, 4.0), sharex=True, sharey=True)
for ax, r in zip(np.atleast_1d(axes), results):
    ax.scatter(r['valid'][0], r['valid'][1], s=16, alpha=.5,
               c='steelblue', edgecolor='none')
    ax.scatter(*R0_NM, marker='*', s=220, c='k', zorder=5, label='real')
    ax.scatter(*r['mean'], marker='+', s=180, c='r', lw=2, zorder=5, label='media')
    ax.set_title(f'{r["label"]}\nRMSE={r["rmse"]:.1f} nm', fontsize=9)
    ax.set_aspect('equal'); ax.grid(alpha=.3)
    ax.set_xlabel('x [nm]')
np.atleast_1d(axes)[0].set_ylabel('y [nm]')
np.atleast_1d(axes)[0].legend(fontsize=7)
fig.suptitle('Estimaciones individuales (el sesgo separa la cruz de la estrella)',
             fontweight='bold')
fig.tight_layout()

# ── Fig 5: descomposición sesgo / varianza ────────────────────────────────
labels = [r['label'] for r in results]
var_term = np.array([np.sqrt(0.5 * (r['std'][0]**2 + r['std'][1]**2)) for r in results])
bias_term = np.array([np.linalg.norm(r['bias']) for r in results])
crbs = np.array([crb_map[g][r0_idx[0], r0_idx[1]] for _, g, _ in CASES])

fig, ax = plt.subplots(figsize=(1.9 * n_c + 3, 5))
xs = np.arange(n_c)
ax.bar(xs, var_term, .6, label='varianza  (baja con más fotones)',
       color='steelblue')
ax.bar(xs, bias_term, .6, bottom=var_term,
       label='sesgo  (NO baja con más fotones)', color='tomato')
ax.plot(xs, crbs, 'k*--', ms=15, lw=1.4, label='CRB', zorder=5)
ax.set_xticks(xs); ax.set_xticklabels(labels, rotation=18, ha='right', fontsize=9)
ax.set_ylabel('contribución al error [nm]')
ax.set_title('De dónde viene el error en cada caso', fontweight='bold')
ax.legend(); ax.grid(axis='y', alpha=.3)
fig.tight_layout()

# ── Fig 6: forma de las donas, medida vs simulada ─────────────────────────
fig, axes = plt.subplots(1, K, figsize=(3.4 * K, 3.4), sharey=True)
for k, ax in enumerate(np.atleast_1d(axes)):
    fit = E.fit_donut_fwhm(exp.PSFs[k], grid)
    ax.plot(fit['r'], fit['profile'], lw=2, c='steelblue', label='medida')
    ax.plot(fit['r'], fit['fitted'], '--', lw=1.6, c='tomato',
            label=f'modelo  fwhm={fit["fwhm"]:.0f} nm')
    ax.set_title(f'haz {k}', fontsize=10)
    ax.set_xlabel('r [nm]'); ax.grid(alpha=.3)
np.atleast_1d(axes)[0].set_ylabel('intensidad media')
np.atleast_1d(axes)[0].legend(fontsize=8)
fig.suptitle(f'Perfil radial: donas medidas vs modelo  '
             f'(FWHM usado en las simulaciones: {DONUT_FWHM:.0f} nm)',
             fontweight='bold')
fig.tight_layout()

plt.show()
