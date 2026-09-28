# -*- coding: utf-8 -*-
"""
F290 - Sospechas de la auditoría B que NO se sostienen (descartadas), cada una
con su evidencia numérica.

 D1  Fallos de sim_exp descartados sin reportar la tasa: en las configuraciones
     de los estudios la tasa de fallo es 0 (margen de fotones enorme).
 D2  Convención de ejes (flip y/−y): psf(), spaceToIndex/indexToSpace, Grid y
     ebp_experimental son mutuamente consistentes (ida y vuelta exacta).
 D3  simulations_example.py (Masullo): el reshape tras quitar NaN es correcto.
 D4  Con Tlife=0.001 y b=dt/K las fracciones por ventana de sim_exp coinciden
     con el modelo de pos_MINFLUX (lo que ella verificó) -> usar conteos
     multinomiales en F203–F205 es equivalente.
 D5  El centrado entero de ebp_experimental deja cada mínimo donde dice pos_nm.
 D6  zero_ratio de fit_donut_fwhm: min/max del mapa 2D vs del perfil radial.
 D7  Honesto vs ingenuo en simulation_misalignment: mismo r0, SBR, semilla y
     radio de búsqueda en todos los casos (comparación justa; el problema del
     borde es F203).
Uso:  python scripts/findings/F290_discarded_suspicions_B.py
"""
import os
import sys
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

PROXY = r'C:\Data\psf\20260703'
out = {}

# D1 ─ tasa de fallo: sim_exp falla si hay < Ns ciclos con fotón tras recortes
print('D1  fallos de sim_exp')
rng = np.random.RandomState(0)
d1 = {}
for Ns in (90, 1800, 2000, 2880):
    Nh = int(Ns * 1.05)
    M_p = int(2e5)
    ncyc = []
    for _ in range(2000):
        beams = rng.multinomial(Nh, [0.25] * 4)
        cyc = np.concatenate([np.unique(rng.randint(0, M_p, nb)) for nb in beams])
        ncyc.append(len(np.unique(cyc)))
    ncyc = np.array(ncyc)
    d1[Ns] = {'min_cycles': int(ncyc.min()), 'mean': float(ncyc.mean()), 'fail_rate': float(np.mean(ncyc < Ns))}
    print('    Ns=%4d Nh=%4d: ciclos con fotón min=%d media=%.1f -> tasa de fallo %.4f (2000 ensayos)'
          % (Ns, Nh, ncyc.min(), ncyc.mean(), np.mean(ncyc < Ns)))
np.random.seed(1)
nf = sum(ts.sim_exp('p_minflux', None, np.ones((4, 3, 3)), (1, 1), 9, 2880, 320,
                    int(2e5), 0.001, 1.05, 50)[2] for _ in range(50))
print('    sim_exp real, Ns=2880 (N=3200 de eficiencia): %d fallos en 50' % nf)
d1['sim_exp_fails_Ns2880_of50'] = int(nf)
out['D1'] = d1

# D2 ─ convención de ejes
print('D2  convención de ejes')
g = E.Grid(400, 1.0)
pos = np.array([[0, 0], [-44, -27], [45, -26], [-5, 51]], float)
eb = E.ebp_analytic(pos, g, donut_fwhm=343.9)
ok = True
for k in range(4):
    am = np.unravel_index(np.argmin(eb.PSFs[k]), eb.PSFs[k].shape)
    ok &= np.allclose(g.to_space(am), pos[k])
    ok &= tuple(g.to_index(pos[k])) == tuple(am)
rt = all(np.allclose(g.to_space(g.to_index(np.array([x, y]))), [x, y])
         for x in range(-150, 151, 7) for y in range(-150, 151, 11))
print('    argmin(psf) == to_index(pos) para los 4 haces: %s ; ida y vuelta índice<->nm exacta: %s' % (ok, rt))
out['D2'] = {'argmin_matches': bool(ok), 'roundtrip': bool(rt)}

# D3 ─ reshape de simulations_example.py (l.183-184)
arr = np.array([[1., np.nan, 3., 4.], [10., np.nan, 30., 40.]])
fc = 1
flat = arr[~np.isnan(arr)].reshape(2, 4 - fc)
d3 = bool(np.array_equal(flat, np.array([[1, 3, 4], [10, 30, 40.]])))
print('D3  reshape tras quitar NaN conserva (x, y) por columna: %s' % d3)
out['D3'] = d3

# D4 ─ sim_exp (C0) reproduce el modelo 1/K (y por lo tanto multinomial)
print('D4  sim_exp con Tlife=0.001, b=dt/K vs modelo de pos_MINFLUX')
lam = np.array([0.12, 0.28, 0.35, 0.25])
psf = lam[:, None, None] * np.ones((4, 1, 1))
np.random.seed(20260825)
tot = np.zeros(4)
for _ in range(300):
    rt_, _, f = ts.sim_exp('p_minflux', None, psf, (0, 0), 2000 / 95, 2000, 95, int(2e5), 0.001, 1.05, 50)
    tot += ts.nMINFLUX(4, np.arange(4) * 12.5, rt_, 0, 12.5)
sbr = 2000 / 95
model = sbr / (sbr + 1) * lam / lam.sum() + 1 / (sbr + 1) / 4
obs = tot / tot.sum()
se = np.sqrt(model * (1 - model) / tot.sum())
z = (obs - model) / se
print('    obs=%s modelo=%s z=%s (N total %d)' % (np.round(obs, 5), np.round(model, 5), np.round(z, 2), tot.sum()))
out['D4'] = {'obs': obs.tolist(), 'model': model.tolist(), 'z': z.tolist(), 'n': float(tot.sum())}

# D5, D6 ─ con el sustituto 20260703 (solo lectura)
if os.path.isdir(PROXY):
    ex = E.ebp_experimental(PROXY, K=4)
    good = []
    for k in range(4):
        am = np.unravel_index(np.argmin(ex.PSFs[k]), ex.PSFs[k].shape)
        good.append(np.allclose(ex.grid.to_space(am), ex.pos_nm[k]))
    print('D5  ebp_experimental: argmin tras centrar == pos_nm por haz: %s' % good)
    out['D5'] = good
    zr = []
    for k in range(4):
        f = E.fit_donut_fwhm(ex.PSFs[k], ex.grid)
        prof = f['profile']
        zr.append((f['zero_ratio'], float(prof.min() / prof.max())))
    print('D6  zero_ratio mapa 2D vs perfil radial: %s' % ['%.3f / %.3f' % t for t in zr])
    out['D6'] = zr
else:
    print('D5/D6  (no hay PSFs sustitutas en %s: no se corrió)' % PROXY)

# D7 ─ equidad (estático)
src = open(os.path.join(LEG, 'simulation_misalignment.py'), encoding='utf-8').read()
d7 = {'single_seed_before_all_cases': src.count('np.random.seed(SEED)') == 1,
      'same_R_SEARCH_for_all': 'r_max_nm=R_SEARCH_NM' in src,
      'same_SBR_for_all': 'SBR=SBR' in src}
print('D7  simulation_misalignment: %s' % d7)
out['D7'] = d7
fn = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3', 'F290_out.json')
json.dump(out, open(fn, 'w', encoding='utf-8'), indent=1, default=float)
