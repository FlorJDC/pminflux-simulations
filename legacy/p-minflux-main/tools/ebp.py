# -*- coding: utf-8 -*-
"""
Construcción de EBPs (Excitation Beam Patterns) para simulaciones p-MINFLUX.
============================================================================

Un EBP queda definido por:
  * una grilla   (n_px, px_nm)          — el espacio muestreado
  * K PSFs       (K, n_px, n_px)        — los mapas de intensidad
  * K posiciones (K, 2) en nm           — los mínimos de cada haz

Este módulo ofrece TRES constructores que devuelven exactamente esa misma
estructura (un objeto `EBP`), de modo que son intercambiables aguas abajo:

  1. `ebp_experimental()` — PSFs medidas, cargadas de archivos .npy
  2. `ebp_analytic()`     — donas analíticas perfectas en posiciones ARBITRARIAS
                            (p.ej. las posiciones experimentales → EBP no ideal
                             con donas perfectas; o cualquier set que quieras probar)
  3. `ebp_ideal()`        — donas analíticas en un triángulo equilátero perfecto

Los tres comparten la misma grilla si se les pasa el mismo objeto `Grid`, lo
cual es imprescindible para que los resultados sean comparables entre sí.

CONVENCIÓN DE COORDENADAS
-------------------------
Una sola, la de `tools_simulations.indexToSpace` / `spaceToIndex`:

    x_nm = col * px_nm - size_nm/2
    y_nm = size_nm/2 - row * px_nm

Verificado que `tools_simulations.psf()` genera arrays con esta misma
convención, y que los .npy experimentales también la respetan.  Por lo tanto
NO se aplica ningún `flipud` en ninguna parte.

Los archivos `Min_positions_*_not_centered.txt` listan, por columna,
X = índice de columna e Y = índice de fila del mínimo (en px = nm si px_nm=1).
Verificado que coinciden exactamente con el `argmin` de los .npy.
"""

import os
import numpy as np
from scipy.ndimage import shift as nd_shift

from .tools_simulations import psf as _psf, indexToSpace, spaceToIndex


# ═══════════════════════════════════════════════════════════════════════════
#  Grilla
# ═══════════════════════════════════════════════════════════════════════════

class Grid:
    """
    Grilla de muestreo. Única fuente de verdad del espacio de la simulación.

    Parameters
    ----------
    n_px  : int   — número de píxeles por lado
    px_nm : float — tamaño del píxel [nm]
    """

    def __init__(self, n_px, px_nm):
        self.n_px = int(n_px)
        self.px_nm = float(px_nm)

    @property
    def size_nm(self):
        """Lado del FOV [nm]."""
        return self.n_px * self.px_nm

    @property
    def extent(self):
        """extent para imshow: [xmin, xmax, ymin, ymax] en nm."""
        h = self.size_nm / 2
        return [-h, h, -h, h]

    @property
    def center_idx(self):
        """Índice (fila, col) del píxel central."""
        c = self.n_px // 2
        return (c, c)

    def to_space(self, index):
        """(fila, col) -> (x, y) en nm."""
        return indexToSpace(index, self.size_nm, self.px_nm)

    def to_index(self, space):
        """(x, y) en nm -> (fila, col)."""
        return spaceToIndex(space, self.size_nm, self.px_nm)

    def __eq__(self, other):
        return (isinstance(other, Grid)
                and self.n_px == other.n_px
                and np.isclose(self.px_nm, other.px_nm))

    def __repr__(self):
        return (f'Grid({self.n_px}x{self.n_px} px, {self.px_nm} nm/px '
                f'-> {self.size_nm:.0f} nm FOV)')


def grid_from_fit_config(path):
    """
    Construye una Grid leyendo el `fit_config.txt` que acompaña a las PSFs.

    Formato esperado (INI-like)::

        [FittingParameters]
        scan_range_um = 0.4
        fitted_pixels = 400
        pixel_size_um = 0.001

    Así el tamaño de píxel y la cantidad de píxeles salen del archivo y no
    quedan hardcodeados en el script de análisis.
    """
    vals = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(('[', '#', ';')):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                vals[k.strip()] = v.strip()

    n_px = int(vals['fitted_pixels'])
    px_nm = float(vals['pixel_size_um']) * 1000.0

    # Chequeo de consistencia con scan_range_um si está presente
    if 'scan_range_um' in vals:
        expected = float(vals['scan_range_um']) * 1000.0
        got = n_px * px_nm
        if not np.isclose(expected, got, rtol=1e-6):
            raise ValueError(
                f'{os.path.basename(path)} inconsistente: '
                f'fitted_pixels*pixel_size = {got:.3f} nm pero '
                f'scan_range = {expected:.3f} nm')

    return Grid(n_px, px_nm)


# ═══════════════════════════════════════════════════════════════════════════
#  Estructura EBP
# ═══════════════════════════════════════════════════════════════════════════

class EBP:
    """
    Un patrón de excitación: PSFs + posiciones de sus mínimos + grilla.

    Attributes
    ----------
    PSFs   : (K, n_px, n_px) — mapas de intensidad
    pos_nm : (K, 2)          — [x, y] del mínimo de cada haz [nm]
    grid   : Grid
    label  : str             — nombre para figuras y prints
    """

    def __init__(self, PSFs, pos_nm, grid, label=''):
        PSFs = np.asarray(PSFs, dtype=float)
        pos_nm = np.asarray(pos_nm, dtype=float)

        if PSFs.ndim != 3 or PSFs.shape[1] != PSFs.shape[2]:
            raise ValueError(f'PSFs debe ser (K, M, M), recibí {PSFs.shape}')
        if PSFs.shape[1] != grid.n_px:
            raise ValueError(f'PSFs de {PSFs.shape[1]} px vs grid de {grid.n_px} px')
        if pos_nm.shape != (PSFs.shape[0], 2):
            raise ValueError(f'pos_nm debe ser (K, 2), recibí {pos_nm.shape}')

        self.PSFs = PSFs
        self.pos_nm = pos_nm
        self.grid = grid
        self.label = label

    @property
    def K(self):
        return self.PSFs.shape[0]

    @property
    def L_eff(self):
        """
        Diámetro efectivo del patrón [nm]: 2 x distancia media de los haces
        periféricos al origen.  Para un EBP ideal coincide con L.
        """
        return 2 * np.mean(np.linalg.norm(self.pos_nm[1:], axis=1))

    @property
    def centroid(self):
        """Centroide de los K mínimos [nm]. Mide el descentrado del patrón."""
        return np.mean(self.pos_nm, axis=0)

    @property
    def asymmetry(self):
        """
        Desviación estándar de las distancias haz-0 -> haces periféricos [nm].
        Vale 0 para un triángulo perfecto; crece con la asimetría del EBP.
        """
        d = np.linalg.norm(self.pos_nm[1:] - self.pos_nm[0], axis=1)
        return float(np.std(d))

    def summary(self):
        """Texto de una línea por haz + métricas globales."""
        out = [f'EBP "{self.label}"  |  K={self.K}  |  {self.grid}']
        out.append(f'  {"haz":>4} {"x [nm]":>9} {"y [nm]":>9} {"|r-r0| [nm]":>12}')
        for k in range(self.K):
            d = np.linalg.norm(self.pos_nm[k] - self.pos_nm[0])
            out.append(f'  {k:>4} {self.pos_nm[k,0]:>9.2f} '
                       f'{self.pos_nm[k,1]:>9.2f} {d:>12.2f}')
        out.append(f'  L_eff = {self.L_eff:.2f} nm  |  '
                   f'asimetria = {self.asymmetry:.2f} nm  |  '
                   f'centroide = ({self.centroid[0]:+.2f}, {self.centroid[1]:+.2f}) nm')
        return '\n'.join(out)

    def __repr__(self):
        return f'<EBP "{self.label}" K={self.K} L_eff={self.L_eff:.1f}nm>'


# ═══════════════════════════════════════════════════════════════════════════
#  Utilidades de posiciones
# ═══════════════════════════════════════════════════════════════════════════

def load_positions_txt(path, grid=None, are_indices=False):
    """
    Lee un archivo de posiciones de mínimos (tab-separated, una línea de header).

    Parameters
    ----------
    path        : str
    grid        : Grid | None — necesaria sólo si `are_indices=True`
    are_indices : bool
        False (default) — las columnas ya son coordenadas físicas [nm].
        True            — las columnas son (X=col, Y=fila) en índices de píxel,
                          como los archivos `*_not_centered.txt`; se convierten
                          a nm con la convención de la grilla.

    Returns
    -------
    pos_nm : (K, 2) array [nm]
    """
    data = np.loadtxt(path, skiprows=1)
    if data.ndim == 1:
        data = data[np.newaxis, :]
    if data.shape[1] != 2:
        raise ValueError(f'{path}: esperaba 2 columnas, encontré {data.shape[1]}')

    if not are_indices:
        return data

    if grid is None:
        raise ValueError('are_indices=True requiere pasar una Grid')

    # columna 0 = X = índice de columna ; columna 1 = Y = índice de fila
    pos_nm = np.zeros_like(data)
    for k in range(data.shape[0]):
        row, col = data[k, 1], data[k, 0]
        pos_nm[k] = grid.to_space((row, col))
    return pos_nm


def center_positions(pos_nm, reference=0):
    """
    Cambia el sistema de referencia de un set de posiciones.

    Parameters
    ----------
    pos_nm    : (K, 2) array [nm]
    reference : int | 'centroid'
        int        — índice del haz que pasa a estar en (0, 0)  (default: 0)
        'centroid' — el centroide de los K mínimos pasa a estar en (0, 0)

    Returns
    -------
    pos_centered : (K, 2) array [nm]
    origin       : (2,) array — el punto que se tomó como nuevo origen [nm]
    """
    pos_nm = np.asarray(pos_nm, dtype=float)
    if reference == 'centroid':
        origin = np.mean(pos_nm, axis=0)
    else:
        origin = pos_nm[int(reference)].copy()
    return pos_nm - origin, origin


# ═══════════════════════════════════════════════════════════════════════════
#  Constructor 1 — PSFs experimentales
# ═══════════════════════════════════════════════════════════════════════════

def ebp_experimental(folder, K=4, grid=None,
                     name_template='Dona_fit_fwd_{}.npy', index_start=1,
                     config_name='fit_config.txt',
                     reference=0, label='Experimental'):
    """
    Carga K PSFs experimentales desde archivos .npy y las centra.

    La grilla se lee de `fit_config.txt` si existe (así el tamaño de píxel no
    queda hardcodeado); se puede forzar pasando `grid` explícitamente.

    El centrado traslada TODAS las PSFs con el mismo desplazamiento rígido, de
    forma que el mínimo del haz `reference` cae en el píxel central.  Los
    píxeles que quedan vacíos se rellenan replicando el borde (`mode='nearest'`),
    no con ceros: un cero haría que sum(PSFs)=0 en el borde y eso produce NaN
    en el estimador de máxima verosimilitud.

    No se aplica flipud: los .npy ya están en la misma convención que
    `indexToSpace` y que `psf()`  (verificado contra `*_not_centered.txt`).

    Parameters
    ----------
    folder        : str  — carpeta con los .npy
    K             : int  — cantidad de haces
    grid          : Grid | None — si None, se lee de `config_name`
    name_template : str  — patrón del nombre, {} se reemplaza por el índice
    index_start   : int  — índice del primer archivo (1 -> _1, _2, ...)
    config_name   : str  — nombre del archivo de configuración del fit
    reference     : int | 'centroid' — qué queda en el origen (ver center_positions)
    label         : str

    Returns
    -------
    EBP
    """
    if grid is None:
        cfg = os.path.join(folder, config_name)
        if not os.path.exists(cfg):
            raise FileNotFoundError(
                f'No encuentro {config_name} en {folder}. '
                f'Pasá una Grid explícita con grid=Grid(n_px, px_nm).')
        grid = grid_from_fit_config(cfg)

    # ── cargar ────────────────────────────────────────────────────────────
    PSFs = np.zeros((K, grid.n_px, grid.n_px))
    for k in range(K):
        fpath = os.path.join(folder, name_template.format(k + index_start))
        raw = np.load(fpath).astype(float)
        if raw.shape != (grid.n_px, grid.n_px):
            raise ValueError(f'{os.path.basename(fpath)}: shape {raw.shape} '
                             f'no coincide con la grilla {grid}')
        PSFs[k] = np.maximum(raw, 0)   # la intensidad no puede ser negativa

    # ── posiciones de los mínimos, ANTES de trasladar ─────────────────────
    # (si se midieran después, el relleno del borde podría confundir al argmin)
    idx_min = np.array([np.unravel_index(np.argmin(PSFs[k]), PSFs[k].shape)
                        for k in range(K)])                      # (K, 2) = (fila, col)
    pos_raw = np.array([grid.to_space(idx_min[k]) for k in range(K)])

    # ── centrar ───────────────────────────────────────────────────────────
    # El desplazamiento de las PSFs es forzosamente ENTERO (son arreglos), así
    # que las posiciones se derivan de ESE MISMO desplazamiento entero y no del
    # origen exacto. Si se calcularan por caminos separados, con un origen no
    # entero —p. ej. reference='centroid'— `pos_nm` diría que los mínimos están
    # hasta medio píxel corridos de donde realmente quedaron en las PSFs, y
    # entonces `ebp_analytic(exp.pos_nm, ...)` colocaría las donas analíticas en
    # lugares distintos que las experimentales, contaminando justo la
    # comparación que el análisis quiere aislar.
    _, origin = center_positions(pos_raw, reference=reference)

    center_row, center_col = grid.center_idx
    origin_row, origin_col = grid.to_index(origin)
    dr = int(center_row - origin_row)
    dc = int(center_col - origin_col)

    if dr != 0 or dc != 0:
        for k in range(K):
            PSFs[k] = nd_shift(PSFs[k], shift=(dr, dc), mode='nearest')

    # Un corrimiento de (dr, dc) píxeles mueve el contenido (+dc·px, −dr·px) nm,
    # con la convención de `indexToSpace` (la fila crece hacia −y).
    pos_nm = pos_raw + np.array([dc * grid.px_nm, -dr * grid.px_nm])

    return EBP(PSFs, pos_nm, grid, label=label)


# ═══════════════════════════════════════════════════════════════════════════
#  Constructor 2 — donas analíticas en posiciones arbitrarias
# ═══════════════════════════════════════════════════════════════════════════

def ebp_analytic(pos_nm, grid, donut_fwhm=None, label='Analítico'):
    """
    Donas analíticas PERFECTAS colocadas en posiciones arbitrarias.

    Éste es el caso que aísla el efecto de la GEOMETRÍA del patrón: cada haz es
    una dona ideal, pero sus mínimos no forman necesariamente un triángulo
    equilátero.  Sirve para, por ejemplo, tomar las posiciones medidas
    experimentalmente y ver cuánta de la pérdida de precisión se explica sólo
    por el desalineamiento, sin la contribución de la forma real de las donas.

    Parameters
    ----------
    pos_nm     : (K, 2) array — posiciones de los mínimos [nm]
    grid       : Grid
    donut_fwhm : float | None — parámetro de escala de la dona [nm], en la
                 convención de la literatura (Balzarotti S16 / Tarkowski ec.[4]
                 / SimuFLUX): entra directo en la fórmula y el radio del anillo
                 resulta 0.6006·donut_fwhm. None usa el default del módulo
                 (360 nm → anillo de 216 nm, el valor de Tarkowski & Stefani).
                 Usá `fit_donut_fwhm` sobre una PSF experimental para obtener
                 el valor que reproduce el tamaño medido.
    label      : str

    Returns
    -------
    EBP
    """
    pos_nm = np.asarray(pos_nm, dtype=float)
    if pos_nm.ndim != 2 or pos_nm.shape[1] != 2:
        raise ValueError(f'pos_nm debe ser (K, 2), recibí {pos_nm.shape}')

    K = pos_nm.shape[0]
    PSFs = np.zeros((K, grid.n_px, grid.n_px))
    for k in range(K):
        PSFs[k] = _psf(pos_nm[k], grid.size_nm, grid.px_nm, [0, 0],
                       d='donut', donut_fwhm=donut_fwhm)

    return EBP(PSFs, pos_nm, grid, label=label)


# ═══════════════════════════════════════════════════════════════════════════
#  Constructor 3 — EBP ideal
# ═══════════════════════════════════════════════════════════════════════════

def ideal_positions(L=100.0, K=4, vertex_up=True):
    """
    Posiciones de un EBP MINFLUX ideal: haz 0 en el centro y los K-1 restantes
    en un polígono regular inscripto en un círculo de diámetro L.

    Para K=4 y vertex_up=True queda el triángulo con un vértice arriba:
        haz 3 -> 90°   (arriba)
        haz 1 -> 210°  (abajo-izquierda)
        haz 2 -> 330°  (abajo-derecha)

    Parameters
    ----------
    L         : float — diámetro del círculo circunscripto [nm]
    K         : int   — cantidad total de haces (1 central + K-1 periféricos)
    vertex_up : bool  — True pone el último haz arriba; False lo pone abajo

    Returns
    -------
    pos_nm : (K, 2) array [nm]
    """
    n_outer = K - 1
    R = L / 2.0
    pos = np.zeros((K, 2))

    # ángulo del haz k = base + k * (360/n_outer), con k = 1 ... n_outer.
    # El último haz (k = n_outer) cae en `base` + 360° = `base`, o sea arriba.
    # Para K=4 y vertex_up:  haz1 -> 210°, haz2 -> 330°, haz3 -> 90°.
    base = 90.0 if vertex_up else -90.0
    for k in range(1, n_outer + 1):
        ang = np.radians(base + k * 360.0 / n_outer)
        pos[k] = [R * np.cos(ang), R * np.sin(ang)]

    return pos


def ebp_ideal(grid, L=100.0, K=4, donut_fwhm=None, vertex_up=True,
              label='Ideal'):
    """
    EBP ideal: donas analíticas perfectas en un triángulo equilátero perfecto.
    Es el caso de referencia contra el cual se contrastan los demás.

    Es simplemente `ebp_analytic(ideal_positions(L, K), ...)`; existe como
    función aparte sólo por comodidad y legibilidad en los scripts.
    """
    return ebp_analytic(ideal_positions(L=L, K=K, vertex_up=vertex_up),
                        grid, donut_fwhm=donut_fwhm, label=label)


# ═══════════════════════════════════════════════════════════════════════════
#  Caracterización de las donas
# ═══════════════════════════════════════════════════════════════════════════

def radial_profile(psf_2d, grid, center_nm=None, r_max_nm=None):
    """
    Perfil radial de una PSF: intensidad media en anillos de 1 píxel de ancho.

    Parameters
    ----------
    psf_2d    : (n_px, n_px) array
    grid      : Grid
    center_nm : (2,) | None  — centro [nm]; None usa el argmin de la PSF
    r_max_nm  : float | None — radio máximo a incluir; None usa medio FOV,
                que es el mayor radio con estadística angular completa

    Returns
    -------
    r    : (n,) array — radio de cada anillo [nm]
    prof : (n,) array — intensidad media del anillo
    """
    if center_nm is None:
        center_nm = grid.to_space(
            np.unravel_index(np.argmin(psf_2d), psf_2d.shape))
    if r_max_nm is None:
        r_max_nm = grid.size_nm / 2

    rows, cols = np.indices(psf_2d.shape)
    x = cols * grid.px_nm - grid.size_nm / 2
    y = grid.size_nm / 2 - rows * grid.px_nm
    r = np.hypot(x - center_nm[0], y - center_nm[1])

    bins = np.arange(0, r_max_nm + grid.px_nm, grid.px_nm)
    idx = np.digitize(r.ravel(), bins) - 1
    keep = (idx >= 0) & (idx < len(bins))

    prof = np.bincount(idx[keep], weights=psf_2d.ravel()[keep], minlength=len(bins))
    cnt = np.bincount(idx[keep], minlength=len(bins))
    valid = cnt > 0
    prof = prof[:len(bins)]
    cnt = cnt[:len(bins)]
    valid = valid[:len(bins)]
    prof[valid] /= cnt[valid]

    return bins[valid], prof[valid]


def fit_donut_fwhm(psf_2d, grid, center_nm=None, r_max_nm=None):
    """
    Estima el `donut_fwhm` de una PSF medida ajustando el modelo analítico.

    ¿Por qué ajustar el modelo y no medir el radio del anillo?  Porque con un
    FOV de 400 nm el anillo (r ~ 250 nm) queda fuera o al borde del campo, así
    que "buscar el máximo" devuelve el borde y no informa nada.  En cambio el
    ajuste usa toda la subida de intensidad alrededor del mínimo, que es
    justamente la región que determina la información de Fisher — o sea, lo
    que de verdad fija la precisión MINFLUX.

    Modelo ajustado (el mismo que usa `tools_simulations.doughnut`, con offset y
    amplitud libres para absorber el fondo y las unidades arbitrarias)::

        I(r) = C + A * (r²/fwhm²) * exp(-4 ln2 * r²/fwhm²)

    `fwhm` va directo en la fórmula, en la convención de la literatura
    (Balzarotti S16 / Tarkowski ec.[4] / SimuFLUX). El radio del anillo que se
    deriva es 0.6006·fwhm, y es la cantidad invariante ante convenciones: si
    vas a reportar un número en un paper, reportá `r_ring`.

    Uso típico::

        res = fit_donut_fwhm(exp.PSFs[0], exp.grid)
        sim = ebp_analytic(exp.pos_nm, exp.grid, donut_fwhm=res['fwhm'])

    Returns
    -------
    dict con:
        'fwhm'      : float — el valor a pasar como `donut_fwhm` [nm]
        'offset'    : float — fondo C ajustado (en unidades de la PSF)
        'amplitude' : float — amplitud A ajustada
        'r_ring'    : float — radio del anillo, 0.6006*fwhm [nm]
        'zero_ratio': float — I(min)/I(max) del perfil medido; la profundidad
                      del cero. Balzarotti 2017 reporta < 0.2 % para un haz
                      bien alineado. OJO: si la PSF se midió con perlas, parte
                      de este valor es promediado por el tamaño de la perla y
                      no calidad del haz (Marin & Ries 2026, param. `beadsize`).
        'rmse_rel'  : float — error relativo del ajuste (0 = perfecto)
        'r'         : array — radios usados
        'profile'   : array — perfil medido
        'fitted'    : array — perfil del modelo ajustado
    """
    from scipy.optimize import curve_fit

    r, prof = radial_profile(psf_2d, grid, center_nm=center_nm, r_max_nm=r_max_nm)

    def model(rr, C, A, fwhm):
        return C + A * (rr**2 / fwhm**2) * np.exp(-4 * np.log(2) * rr**2 / fwhm**2)

    # semillas: fondo = mínimo del perfil, fwhm = default del módulo
    C0 = float(prof.min())
    fwhm0 = 360.0
    span = float(prof.max() - prof.min())
    rr = r[-1]
    denom = (rr**2 / fwhm0**2) * np.exp(-4 * np.log(2) * rr**2 / fwhm0**2)
    A0 = span / denom if denom > 0 else span

    popt, _ = curve_fit(model, r, prof, p0=[C0, A0, fwhm0],
                        bounds=([-np.inf, 0, 10.0], [np.inf, np.inf, 5000.0]),
                        maxfev=20000)
    C, A, fwhm = popt
    fitted = model(r, *popt)
    rmse_rel = float(np.sqrt(np.mean((prof - fitted)**2)) / (prof.max() - prof.min()))

    r_ring = float(fwhm) / (2 * np.sqrt(np.log(2)))      # = 0.6006 * fwhm
    zero_ratio = float(np.min(psf_2d) / np.max(psf_2d))

    return {'fwhm': float(fwhm), 'offset': float(C), 'amplitude': float(A),
            'r_ring': r_ring, 'zero_ratio': zero_ratio, 'rmse_rel': rmse_rel,
            'r': r, 'profile': prof, 'fitted': fitted}
