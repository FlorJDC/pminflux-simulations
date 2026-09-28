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

Datos reales (R3): la convención supone que el pulso del haz 0 está en microtiempo 0 y que los
pulsos están equiespaciados (``j*T/K``). Si el microtiempo del TCSPC está referido al sync con un
corrimiento ``t0`` (retardo del pulso del haz 0), restar ``t0`` a los microtiempos o, lo que es
lo mismo, pasar ``starts = window_starts(T, K, a, t0)`` (= ``t0 + i*T/K + a``). Si los retardos
medidos de los haces no están equiespaciados, pasar ``starts[i]`` = comienzo medido de la
ventana ``i`` (ns, en el reloj del TCSPC) y construir la matriz de mezcla con
``mixing_matrix_starts(tau, T, starts, b, pulse_times, irf_fwhm)`` (los mismos ``starts`` y los
retardos medidos de los pulsos), que se pasa tal cual como ``C`` a ``estimate.mle_mixing`` /
``estimate.crb`` (el fondo sigue aportando ``b/T`` por ventana porque todas tienen ancho ``b``).

Borde de punto flotante: una fase que después del pliegue da exactamente ``T`` (un microtiempo a
~1 ulp por debajo del comienzo de una ventana; o un negativo subnormal) se identifica con 0 (``T == 0 mod T``), igual que
el microtiempo del simulador; ningún fotón queda sin ventana por redondeo.

Sobre F102 (ceros en la ventana 0): el legado agregaba un microtiempo 0.0 por cada ciclo sin
fotón de señal y los contaba en la ventana 0 cuando ``a < 0``. Aquí el 0.0 no tiene ningún
tratamiento especial (desigualdad medio abierta, como cualquier otro tiempo): F102 se evita
porque los microtiempos REALES no contienen ceros artificiales. No agregue ceros de relleno a los
datos antes de llamar a esta función.
"""

import warnings

import numpy as np

from . import mixing as _mx

__all__ = ["count_windows", "window_masks", "check_overlap", "check_overlap_starts",
           "window_starts", "mixing_matrix_starts"]

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


def check_overlap_starts(starts, b, T, allow_overlap=False):
    """Como ``check_overlap`` para comienzos arbitrarios: las ventanas ``[s_i, s_i + b)`` mod T
    son disjuntas si la separación circular entre comienzos consecutivos es >= b."""
    s = np.sort(np.mod(np.asarray(starts, dtype=float).ravel(), T))
    gaps = np.diff(np.r_[s, s[0] + T]) if s.size > 1 else np.array([float(T)])
    g = float(gaps.min())
    if float(b) > g * (1.0 + _OVERLAP_RTOL) + 1e-12 * T:
        msg = ("ventanas solapadas: b=%g > separación mínima entre comienzos %g (un fotón en el "
               "solapamiento cuenta en dos ventanas; la verosimilitud y el CRB multinomiales "
               "dejan de ser válidos)" % (b, g))
        if not allow_overlap:
            raise ValueError(msg + ". Use ventanas disjuntas o allow_overlap=True.")
        warnings.warn(msg, UserWarning, stacklevel=3)
        return True
    return False


def window_starts(T, K, a=0.0, t0=0.0):
    """Comienzos equiespaciados ``t0 + i*T/K + a`` (ns): la convención por defecto con un
    corrimiento de sync ``t0`` (retardo del pulso del haz 0 en el reloj del TCSPC)."""
    return float(t0) + np.arange(int(K)) * (float(T) / int(K)) + float(a)


def _fold(x, T):
    """x mod T en [0, T): una fase que por redondeo da T (o un negativo subnormal, cuando x/T
    se redondea a -0.0) se identifica con 0 (``T == 0 mod T``)."""
    ph = np.asarray(x - np.floor(x / T) * T, dtype=float)
    ph[(ph >= T) | (ph < 0)] = 0.0
    return ph


def window_masks(micro, T, K, a, b, starts=None):
    """Máscaras (K, n) bool: el microtiempo ``micro`` (ns) cae en la ventana i (medio abierta).

    Misma aritmética que el conteo ``'periodic'`` de ``simulate``: fase ``(t - a) mod T`` y
    ``i*T/K <= fase < i*T/K + b`` (con el tramo que cruza ``T`` plegado al comienzo).
    ``starts`` (K,): comienzos arbitrarios (ns); entonces ventana ``i`` =
    ``[starts[i], starts[i] + b)`` mod T y ``a`` se ignora.
    """
    micro = np.asarray(micro, dtype=float).ravel()
    out = np.empty((int(K), micro.size), dtype=bool)
    if starts is None:
        dt = T / K
        sph = _fold(micro - a, T)                    # fase respecto de la ventana 0, [0, T)
        for i in range(int(K)):
            d = sph - i * dt                         # en (-T, T)
            out[i] = ((d >= 0) & (d < b)) | (d < b - T)
        return out
    st = np.asarray(starts, dtype=float).ravel()
    if st.size != int(K):
        raise ValueError("starts debe tener K = %d valores" % int(K))
    for i in range(int(K)):
        out[i] = _fold(micro - st[i], T) < b
    return out


def mixing_matrix_starts(tau, T, starts, b, pulse_times=None, irf_fwhm=None, nwrap=None):
    """Matriz de mezcla C (K x K) para comienzos de ventana y retardos de pulso arbitrarios.

    ``C[i, j]`` = P(fotón excitado por el pulso ``j`` (en ``pulse_times[j]``, ns) caiga en la
    ventana ``i`` = ``[starts[i], starts[i] + b)`` mod ``T``), sumando las imágenes periódicas
    (fuga hacia ventanas posteriores y el ciclo siguiente; con IRF, también la anterior).
    ``pulse_times`` None = ``j*T/K`` (la convención del paquete). Con ``starts = i*T/K + a`` y los
    pulsos por defecto coincide con ``mixing.mixing_matrix(tau, T, K, a, b, irf_fwhm)``
    (``mixing.py`` no se modifica: se usan sus ``decay_cdf``/``fwhm_to_sigma``). Es invariante
    ante un corrimiento común de ``starts`` y ``pulse_times`` (offset del sync).
    Se pasa como ``C`` a ``estimate.mle_mixing`` / ``estimate.crb`` / ``mixing.window_probs``.
    """
    st = np.asarray(starts, dtype=float).ravel()
    K = st.size
    if K < 1:
        raise ValueError("starts no puede estar vacío")
    T = float(T)
    if not (T > 0 and tau > 0):
        raise ValueError("T y tau deben ser > 0")
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T")
    if pulse_times is None:
        pt = np.arange(K) * (T / K)
    else:
        pt = np.asarray(pulse_times, dtype=float).ravel()
        if pt.size != K:
            raise ValueError("pulse_times debe tener K = %d valores" % K)
    if not (np.all(np.isfinite(st)) and np.all(np.isfinite(pt))):
        raise ValueError("starts y pulse_times deben ser finitos")
    sigma = _mx.fwhm_to_sigma(irf_fwhm) if irf_fwhm else None
    if nwrap is None:
        nwrap = int(np.ceil((42.0 * tau + 10.0 * (sigma or 0.0)) / T)) + 2
    m_lo = -int(np.ceil((b + 10.0 * (sigma or 0.0)) / T)) - 1
    ms = np.arange(m_lo, nwrap)
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = (st[i] - pt[j]) % T                # comienzo de la ventana respecto del pulso
            t0 = off + ms * T
            C[i, j] = np.sum(_mx.decay_cdf(t0 + b, tau, sigma) - _mx.decay_cdf(t0, tau, sigma))
    return C


def count_windows(microtime_ns, T=50.0, K=4, a=0.0, b=10.1, macro_index=None,
                  return_outside=False, n_loc=None, allow_overlap=False, starts=None):
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
    starts: None (ventanas ``i*T/K + a``) o array (K,) de comienzos por ventana (ns, en el reloj
        del TCSPC; ``a`` se ignora): offset de sync o retardos de haz no equiespaciados (ver el
        docstring del módulo y ``mixing_matrix_starts``). Se exige ventanas disjuntas
        (separación circular mínima entre comienzos >= b), salvo ``allow_overlap``.

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
    if starts is None:
        check_overlap(b, T, K, allow_overlap)
    else:
        starts = np.asarray(starts, dtype=float).ravel()
        if starts.size != K or not np.all(np.isfinite(starts)):
            raise ValueError("starts debe tener K = %d valores finitos" % K)
        check_overlap_starts(starts, b, T, allow_overlap)
    if not np.all(np.isfinite(t)):
        raise ValueError("microtime_ns debe ser finito (hay NaN o inf)")
    masks = window_masks(t, T, K, float(a), float(b), starts=starts)
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
