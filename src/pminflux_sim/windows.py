# -*- coding: utf-8 -*-
"""Conteo de fotones por ventana a partir de microtiempos (reemplazo de ``nMINFLUX`` del legado).

Convención (la misma de ``mixing.mixing_matrix`` y del conteo ``'periodic'`` de ``simulate``):

- Ciclo TCSPC de período ``T`` (ns) y ``K`` haces; la ventana ``i`` es el intervalo MEDIO ABIERTO
  ``[i*T/K + a, i*T/K + a + b)`` plegado módulo ``T``. Se admite ``a < 0`` y ventanas que cruzan
  ``T`` (el tramo que sobra entra por el comienzo del ciclo).
- El microtiempo se pliega con ``t mod T``: se pueden pasar microtiempos en [0, T) o tiempos
  absolutos en ns (el resultado es el mismo).
- Se exige ``b <= T/K`` (ventanas disjuntas). Con ``b > T/K`` un fotón en el solapamiento cuenta
  en dos ventanas y la verosimilitud/CRB multinomial dejan de ser válidas: ``ValueError`` salvo
  ``allow_overlap=True``, que solo avisa con ``warnings.warn``.

Sobre F102 (ceros en la ventana 0): el legado agregaba un microtiempo 0.0 por cada ciclo sin
fotón de señal y los contaba en la ventana 0 cuando ``a < 0``. Aquí el 0.0 no tiene ningún
tratamiento especial (desigualdad medio abierta, como cualquier otro tiempo): F102 se evita
porque los microtiempos REALES no contienen ceros artificiales. No agregue ceros de relleno a los
datos antes de llamar a esta función.
"""

import warnings

import numpy as np

__all__ = ["count_windows", "window_masks", "check_overlap"]

_OVERLAP_RTOL = 1e-12


def check_overlap(b, T, K, allow_overlap=False):
    """``ValueError`` si las ventanas se solapan (``b > T/K``), salvo ``allow_overlap=True``.

    Con ``allow_overlap=True`` emite ``warnings.warn`` (UserWarning) y devuelve ``True``; si las
    ventanas son disjuntas devuelve ``False``.
    """
    dt = float(T) / float(K)
    if float(b) > dt * (1.0 + _OVERLAP_RTOL):
        msg = ("ventanas solapadas: b=%g > T/K=%g (un fotón en el solapamiento cuenta en dos "
               "ventanas; la verosimilitud y el CRB multinomiales dejan de ser válidos)" % (b, dt))
        if not allow_overlap:
            raise ValueError(msg + ". Use b <= T/K o allow_overlap=True.")
        warnings.warn(msg, UserWarning, stacklevel=3)
        return True
    return False


def window_masks(micro, T, K, a, b):
    """Máscaras (K, n) bool: el microtiempo ``micro`` (ns) cae en la ventana i (medio abierta).

    Misma aritmética que el conteo ``'periodic'`` de ``simulate``: fase ``(t - a) mod T`` y
    ``i*T/K <= fase < i*T/K + b`` (con el tramo que cruza ``T`` plegado al comienzo).
    """
    dt = T / K
    sph = micro - a
    sph = sph - np.floor(sph / T) * T                # fase respecto de la ventana 0, [0, T)
    out = np.empty((int(K), sph.size), dtype=bool)
    for i in range(int(K)):
        d = sph - i * dt                             # en (-T, T)
        out[i] = ((d >= 0) & (d < b)) | (d < b - T)
    return out


def count_windows(microtime_ns, T=50.0, K=4, a=0.0, b=10.1, macro_index=None,
                  return_outside=False, n_loc=None, allow_overlap=False):
    """Cuenta fotones por ventana a partir de sus microtiempos.

    microtime_ns: array 1D de microtiempos (ns); se pliegan con ``t mod T``. Deben ser finitos.
    T, K, a, b: período, número de haces, corrimiento y ancho de ventana (ns); ventana ``i`` =
        ``[i*T/K + a, i*T/K + a + b)`` módulo ``T``. Se exige ``0 < b <= T/K`` (ver
        ``allow_overlap``).
    macro_index: None (un solo conjunto) o array de enteros >= 0 del mismo largo (id de
        localización de cada fotón): agrupa por ese índice.
    return_outside: además devuelve cuántos fotones no cayeron en ninguna ventana.
    n_loc: número de grupos (filas) de la salida con ``macro_index``; por defecto ``max + 1``.
    allow_overlap: permite ``b > T/K`` con un ``warnings.warn`` (un fotón puede contar dos veces).

    Devuelve ``counts`` int64, (K,) sin ``macro_index`` o (n_loc, K) con él; con
    ``return_outside=True`` devuelve ``(counts, outside)`` (escalar o (n_loc,)).
    """
    t = np.asarray(microtime_ns, dtype=float).ravel()
    if int(K) != K or K < 1:
        raise ValueError("K debe ser un entero >= 1")
    K = int(K)
    T = float(T)
    if not T > 0:
        raise ValueError("T debe ser > 0")
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T")
    if not np.isfinite(a):
        raise ValueError("a debe ser finito")
    check_overlap(b, T, K, allow_overlap)
    if not np.all(np.isfinite(t)):
        raise ValueError("microtime_ns debe ser finito (hay NaN o inf)")
    masks = window_masks(t, T, K, float(a), float(b))
    outside = ~masks.any(axis=0)
    if macro_index is None:
        counts = masks.sum(axis=1).astype(np.int64)
        return (counts, int(outside.sum())) if return_outside else counts
    g = np.asarray(macro_index).ravel()
    if g.shape != t.shape:
        raise ValueError("macro_index debe tener el mismo largo que microtime_ns")
    if g.size and (not np.issubdtype(g.dtype, np.integer)):
        if not np.all(np.isfinite(g)) or np.any(g != np.round(g)):
            raise ValueError("macro_index debe ser entero")
        g = g.astype(np.int64)
    g = g.astype(np.int64)
    if g.size and g.min() < 0:
        raise ValueError("macro_index debe ser >= 0")
    n = int(g.max()) + 1 if g.size else 0
    if n_loc is not None:
        if int(n_loc) < n:
            raise ValueError("n_loc = %d es menor que max(macro_index) + 1 = %d" % (n_loc, n))
        n = int(n_loc)
    counts = np.zeros((n, K), dtype=np.int64)
    for i in range(K):
        counts[:, i] = np.bincount(g[masks[i]], minlength=n)
    if return_outside:
        return counts, np.bincount(g[outside], minlength=n).astype(np.int64)
    return counts
