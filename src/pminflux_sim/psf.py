# -*- coding: utf-8 -*-
"""Haces de excitación y geometría del EBP para p-MINFLUX (versión v2).

Corrige, respecto de ``legacy/p-minflux-main/tools/tools_simulations.py``:

- F111: ``ebp_centres`` fija ``L = [L]*4`` y falla (IndexError) con K = 5 o 7. Aquí
  ``beam_positions`` acepta cualquier K >= 1 (con o sin haz central).
- F109: la rama gaussiana de ``psf`` ignora ``donut_fwhm``. Aquí cada perfil recibe su ``fwhm``
  explícito y lo respeta (la FWHM del gaussiano es ``fwhm``; el anillo de la dona está en
  ``fwhm/(2 sqrt(ln 2))`` = 0.6006·fwhm, la convención de Balzarotti S16 que ya usa el legado).
- ``lambda_beams`` está vectorizada sobre muchas posiciones y da también el gradiente analítico,
  que usa el estimador.

Convención de posiciones (la misma que ``ts.beams(K, L, center=True, d='donut')`` con K = 4):
con haz central, ``pos[0] = (0, 0)`` y los ``K-1`` restantes en el círculo de diámetro ``L`` en
los ángulos ``2 pi k/(K-1) + phi`` (k = 1..K-1); sin haz central, los K haces en
``2 pi k/K + phi`` (k = 0..K-1). Con K = 4 y centro, coincide exactamente con el legado.
"""

import math

import numpy as np

__all__ = ["DEFAULT_FWHM", "RING_FACTOR", "beam_positions", "donut", "gaussian",
           "beam_profile", "lambda_beams", "measured_fwhm"]

DEFAULT_FWHM = 360.0                         # nm, default del legado (tools_simulations.fwhm)
RING_FACTOR = 1.0 / (2.0 * math.sqrt(math.log(2.0)))   # radio del anillo / fwhm = 0.6006
_C4 = 4.0 * math.log(2.0)


def beam_positions(K, L, center=True, phi=0.0):
    """Posiciones (K, 2) en nm de los ceros de los K haces (polígono regular de diámetro L).

    ``center=True``: haz 0 en el origen y K-1 haces en el anillo (TCP con K = 4).
    ``phi`` (rad) rota el anillo. Válido para cualquier K entero >= 1 (F111).
    """
    if int(K) != K or K < 1:
        raise ValueError("K debe ser un entero >= 1")
    K = int(K)
    if not (L >= 0):
        raise ValueError("L debe ser >= 0")
    pos = np.zeros((K, 2))
    if center:
        n = K - 1
        if n == 0:
            return pos
        k = np.arange(1, K)
        th = 2.0 * np.pi * k / n + phi
        pos[1:, 0] = 0.5 * L * np.cos(th)
        pos[1:, 1] = 0.5 * L * np.sin(th)
    else:
        k = np.arange(K)
        th = 2.0 * np.pi * k / K + phi
        pos[:, 0] = 0.5 * L * np.cos(th)
        pos[:, 1] = 0.5 * L * np.sin(th)
    return pos


def donut(r, fwhm=DEFAULT_FWHM):
    """Dona 2D de Balzarotti (S16), con pico del anillo = 1: e·u·exp(-u), u = 4 ln2 r²/fwhm²."""
    if not fwhm > 0:
        raise ValueError("fwhm debe ser > 0")
    u = _C4 * np.square(np.asarray(r, dtype=float)) / fwhm ** 2
    return math.e * u * np.exp(-u)


def gaussian(r, fwhm=DEFAULT_FWHM):
    """Haz gaussiano 2D con FWHM = ``fwhm`` (respetada, F109)."""
    if not fwhm > 0:
        raise ValueError("fwhm debe ser > 0")
    u = _C4 * np.square(np.asarray(r, dtype=float)) / fwhm ** 2
    return np.exp(-u)


def beam_profile(r, fwhm=DEFAULT_FWHM, kind="donut"):
    """Perfil radial: ``kind`` = 'donut' | 'gaussian'. Otro valor: ValueError (no NameError)."""
    if kind == "donut":
        return donut(r, fwhm)
    if kind == "gaussian":
        return gaussian(r, fwhm)
    raise ValueError("kind debe ser 'donut' o 'gaussian' (recibido %r)" % (kind,))


def _profile_u(u, kind):
    """I(u) y dI/du para u = 4 ln2 r²/fwhm²."""
    eu = np.exp(-u)
    if kind == "donut":
        return math.e * u * eu, math.e * (1.0 - u) * eu
    if kind == "gaussian":
        return eu, -eu
    raise ValueError("kind debe ser 'donut' o 'gaussian' (recibido %r)" % (kind,))


def lambda_beams(r_xy, pos, fwhm=DEFAULT_FWHM, kind="donut", grad=False):
    """Excitación relativa de cada haz en las posiciones ``r_xy``.

    ``r_xy``: (..., 2) en nm; ``pos``: (K, 2). Devuelve ``lam`` (..., K) sin normalizar (la
    normalización la hace el modelo). Con ``grad=True`` devuelve también ``dlam`` (..., 2, K) =
    derivadas respecto de x e y.
    """
    r = np.asarray(r_xy, dtype=float)
    pos = np.asarray(pos, dtype=float)
    if r.shape[-1] != 2 or pos.ndim != 2 or pos.shape[1] != 2:
        raise ValueError("r_xy debe ser (..., 2) y pos (K, 2)")
    if not fwhm > 0:
        raise ValueError("fwhm debe ser > 0")
    dx = r[..., None, 0] - pos[:, 0]          # (..., K)
    dy = r[..., None, 1] - pos[:, 1]
    k = _C4 / fwhm ** 2
    u = k * (dx * dx + dy * dy)
    lam, dI = _profile_u(u, kind)
    if not grad:
        return lam
    dlam = np.stack([dI * 2.0 * k * dx, dI * 2.0 * k * dy], axis=-2)   # (..., 2, K)
    return lam, dlam


def measured_fwhm(kind, fwhm, n=200001, rmax=None):
    """FWHM medida numéricamente en un corte 1D (para el test de F109).

    Gaussiano: ancho a media altura del pico central. Dona: ancho a media altura del anillo
    (radial, lado externo menos interno); se devuelve también el radio del máximo.
    """
    rmax = rmax or 3.0 * fwhm
    x = np.linspace(0.0, rmax, n)
    I = beam_profile(x, fwhm, kind)
    I = I / I.max()
    above = x[I >= 0.5]
    if kind == "gaussian":
        return 2.0 * above.max(), 0.0
    return above.max() - above.min(), x[np.argmax(I)]
