# -*- coding: utf-8 -*-
"""Matriz de mezcla de fuga entre ventanas para p-MINFLUX pulsado.

Convenciones (las mismas que ``tests/test_acceptance.py`` y el ``sim_exp`` del legado):

- Período del ciclo TCSPC ``T`` (ns), ``K`` haces intercalados; el pulso del haz ``j`` sale en
  ``j*T/K`` dentro del ciclo (``tau_i = i*T/K``).
- Ventana ``i`` = ``[i*T/K + a, i*T/K + a + b]`` módulo ``T`` (se admite ``a < 0`` y ventanas que
  cruzan ``T``; se exige ``0 < b <= T``).
- El microtiempo de un fotón del haz ``j`` es ``j*T/K + X`` con ``X = IRF + Exp(tau)``; en estado
  estacionario los pulsos se repiten cada ``T``, así que el fotón puede caer en cualquier imagen
  periódica (fuga hacia ventanas posteriores, también las del ciclo siguiente).
- ``C[i][j] = P(fotón excitado por el haz j se detecta en la ventana i)``. La suma de la columna
  ``j`` es la fracción capturada por el conjunto de ventanas (1 si las ventanas cubren el ciclo).

Además de la matriz, el módulo da los modelos de probabilidades por ventana (mezcla e "ingenuo",
el que asumen ``pos_MINFLUX``/``crb_minflux`` del legado) y un predictor exacto, a tasa finita, de
lo que produce ``sim_exp`` (recorte a 1 fotón por ranura (ciclo, haz) y sobrescritura "gana el haz
de k más alto") frente a un TCSPC real ("gana el fotón más temprano").
"""

import itertools
import math

import numpy as np
from scipy import stats
from scipy.special import erfcx, ndtr

__all__ = [
    "fwhm_to_sigma",
    "decay_cdf",
    "decay_pdf",
    "mixing_matrix",
    "window_expected",
    "window_probs",
    "naive_probs",
    "pearson_chi2",
    "occupancy_pattern_probs",
    "pattern_window_dist",
    "sim_exp_window_probs",
]

_SQRT2 = math.sqrt(2.0)
_FWHM_TO_SIGMA = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))


def fwhm_to_sigma(fwhm):
    """sigma de una gaussiana a partir de su FWHM."""
    return float(fwhm) * _FWHM_TO_SIGMA


# ---------------------------------------------------------------------------------------------
# Distribución del retardo X = IRF gaussiana (sigma) + Exp(tau)
# ---------------------------------------------------------------------------------------------

def _emg_tail(t, tau, sigma):
    """exp(-t/tau + sigma^2/(2 tau^2)) * Phi(t/sigma - sigma/tau), estable numéricamente."""
    t = np.asarray(t, dtype=float)
    u = t / sigma - sigma / tau
    out = np.empty_like(t)
    pos = u > 0
    # u > 0: el exponente es <= -sigma^2/(2 tau^2) + ... y Phi(u) ~ 1, forma directa.
    out[pos] = np.exp(-t[pos] / tau + sigma ** 2 / (2 * tau ** 2)) * ndtr(u[pos])
    # u <= 0: Phi(u) = 0.5 erfcx(-u/sqrt2) exp(-u^2/2) y los exponentes se combinan en -t^2/(2 s^2).
    neg = ~pos
    out[neg] = 0.5 * erfcx(-u[neg] / _SQRT2) * np.exp(-t[neg] ** 2 / (2 * sigma ** 2))
    return out


def decay_cdf(t, tau, sigma=None):
    """CDF de X = N(0, sigma^2) + Exp(tau) (sin IRF si sigma es None o 0)."""
    t = np.asarray(t, dtype=float)
    if tau <= 0:
        raise ValueError("tau debe ser > 0")
    if not sigma:
        return np.where(t > 0, -np.expm1(-np.clip(t, 0, None) / tau), 0.0)
    return ndtr(t / sigma) - _emg_tail(t, tau, sigma)


def decay_pdf(t, tau, sigma=None):
    """Densidad de X = N(0, sigma^2) + Exp(tau)."""
    t = np.asarray(t, dtype=float)
    if tau <= 0:
        raise ValueError("tau debe ser > 0")
    if not sigma:
        return np.where(t >= 0, np.exp(-np.clip(t, 0, None) / tau) / tau, 0.0)
    return _emg_tail(t, tau, sigma) / tau


def _check_geometry(T, K, b):
    if K < 1 or int(K) != K:
        raise ValueError("K debe ser un entero >= 1")
    if T <= 0:
        raise ValueError("T debe ser > 0")
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T (b = %r, T = %r)" % (b, T))


def _auto_nwrap(tau, T, sigma):
    # cola exp(-n T / tau) < 1e-18, más margen para la IRF.
    return int(math.ceil((42.0 * tau + 10.0 * (sigma or 0.0)) / T)) + 2


def mixing_matrix(tau, T, K, a, b, irf_fwhm=None, nwrap=None):
    """Matriz de mezcla periódica C (K x K), C[i, j] = P(fotón del haz j cae en la ventana i).

    tau, T, a, b en ns. ``irf_fwhm`` (ns): IRF gaussiana; None o 0 = sin IRF.
    ``nwrap``: cantidad de períodos posteriores sumados (auto por defecto). También se suman
    las imágenes anteriores necesarias (m < 0) cuando a < 0 o hay IRF.
    """
    _check_geometry(T, K, b)
    sigma = fwhm_to_sigma(irf_fwhm) if irf_fwhm else None
    if nwrap is None:
        nwrap = _auto_nwrap(tau, T, sigma)
    dt = T / K
    # imágenes anteriores: hacen falta mientras off + a + m T + b pueda ser > -10 sigma
    m_lo = -int(math.ceil((abs(min(a, 0.0)) + b + 10.0 * (sigma or 0.0)) / T)) - 1
    ms = np.arange(m_lo, nwrap)
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = ((i - j) * dt) % T
            t0 = off + a + ms * T
            C[i, j] = np.sum(decay_cdf(t0 + b, tau, sigma) - decay_cdf(t0, tau, sigma))
    return C


# ---------------------------------------------------------------------------------------------
# Modelos de probabilidad por ventana
# ---------------------------------------------------------------------------------------------

def _norm_lam(lam):
    lam = np.asarray(lam, dtype=float)
    s = lam.sum()
    if not np.all(lam >= 0) or s <= 0:
        raise ValueError("lam debe ser no negativo y con suma > 0")
    return lam / s


def window_expected(lam, C, b, T, Ns, Nb):
    """Conteos esperados por ventana (sin normalizar): Ns * C @ (lam/sum lam) + Nb * b/T.

    El fondo es uniforme en el ciclo, así que cada ventana de ancho b recibe una fracción b/T.
    """
    C = np.asarray(C, dtype=float)
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T")
    if Ns < 0 or Nb < 0:
        raise ValueError("Ns y Nb deben ser >= 0")
    return Ns * C.dot(_norm_lam(lam)) + Nb * (b / T) * np.ones(C.shape[0])


def window_probs(lam, C, b, T, Ns=None, Nb=None, sbr=None):
    """Modelo de mezcla p'_i (normalizado sobre las ventanas, condicionado al total en ventanas).

    Dar ``Ns`` y ``Nb`` (fotones de señal y de fondo en el ciclo completo), o bien ``sbr`` = Ns/Nb
    (``sbr = inf`` o ``Nb = 0``: sin fondo).
    """
    if sbr is not None:
        if Ns is not None or Nb is not None:
            raise ValueError("dar sbr o (Ns, Nb), no ambos")
        if sbr <= 0:
            raise ValueError("sbr debe ser > 0")
        Ns, Nb = (1.0, 0.0) if math.isinf(sbr) else (float(sbr), 1.0)
    elif Ns is None or Nb is None:
        raise ValueError("falta sbr o (Ns, Nb)")
    e = window_expected(lam, C, b, T, Ns, Nb)
    return e / e.sum()


def naive_probs(lam, sbr):
    """Modelo de pos_MINFLUX/crb_minflux: SBR/(SBR+1) lam/sum(lam) + 1/(SBR+1)/K (sin fuga)."""
    p = _norm_lam(lam)
    K = p.size
    if math.isinf(sbr):
        return p
    if sbr <= 0:
        raise ValueError("sbr debe ser > 0")
    return sbr / (sbr + 1.0) * p + 1.0 / (sbr + 1.0) / K


def pearson_chi2(counts, probs):
    """Chi^2 de Pearson de ``counts`` contra ``probs`` (normalizadas), condicionado en el total.

    Devuelve (chi2, dof, p_valor, dev_se) con dof = K - 1 y dev_se[i] = (o_i - e_i)/SE_i,
    SE_i = sqrt(N p_i (1 - p_i)) (desvío de la fracción en unidades de su error binomial).
    """
    o = np.asarray(counts, dtype=float)
    p = np.asarray(probs, dtype=float)
    if o.shape != p.shape or o.ndim != 1 or o.size < 2:
        raise ValueError("counts y probs: vectores de igual largo >= 2")
    if np.any(p <= 0):
        raise ValueError("probs debe ser > 0")
    p = p / p.sum()
    N = o.sum()
    if N <= 0:
        raise ValueError("sin conteos")
    e = N * p
    chi2 = float(np.sum((o - e) ** 2 / e))
    dof = o.size - 1
    dev = (o - e) / np.sqrt(N * p * (1 - p))
    return chi2, dof, float(stats.chi2.sf(chi2, dof)), dev


# ---------------------------------------------------------------------------------------------
# Predictor a tasa finita: qué produce sim_exp (y qué haría un TCSPC real)
# ---------------------------------------------------------------------------------------------

def occupancy_pattern_probs(p, Nh, M_p):
    """P(el conjunto de ranuras ocupadas de un ciclo es exactamente S), exacto para sim_exp.

    En ``sim_exp`` cada uno de los Nh fotones cae en la ranura (haz k, ciclo m) con probabilidad
    p_k/M_p, independiente. Entonces P(ranuras de A vacías) = (1 - sum_{k in A} p_k/M_p)^Nh y
    P(exactamente S) = sum_{U subset S} (-1)^|U| P(S^c U U vacías) (inclusión-exclusión).
    Devuelve un dict {tuple(S): prob} para todo S no vacío.
    """
    p = _norm_lam(p)
    K = p.size
    full = frozenset(range(K))

    def empty(A):
        return (1.0 - sum(p[k] for k in A) / M_p) ** Nh

    out = {}
    for r in range(1, K + 1):
        for S in itertools.combinations(range(K), r):
            Sc = full - set(S)
            tot = 0.0
            for q in range(len(S) + 1):
                for U in itertools.combinations(S, q):
                    tot += (-1) ** q * empty(Sc | set(U))
            out[S] = max(tot, 0.0)
    return out


def _quad_nodes(tau, T, K, a, b, sigma, n_gl=16):
    """Nodos de Gauss-Legendre en tramos cuyos bordes incluyen pulsos y bordes de ventana."""
    dt = T / K
    t_lo = -10.0 * sigma if sigma else 0.0
    t_hi = (K - 1) * dt + 45.0 * tau + 10.0 * (sigma or 0.0)
    br = [t_lo, t_hi] + [j * dt for j in range(K)]
    m_lo = int(math.floor((t_lo - T - abs(a) - b) / T)) - 1
    m_hi = int(math.ceil((t_hi + abs(a) + b) / T)) + 1
    for m in range(m_lo, m_hi + 1):
        for i in range(K):
            br += [i * dt + a + m * T, i * dt + a + b + m * T]
    br = np.unique(np.clip(br, t_lo, t_hi))
    x, w = np.polynomial.legendre.leggauss(n_gl)
    step = min(tau, sigma if sigma else tau) / 4.0
    ts, ws, mids = [], [], []
    for lo, hi in zip(br[:-1], br[1:]):
        if hi - lo <= 0:
            continue
        n = int(math.ceil((hi - lo) / step))
        edges = np.linspace(lo, hi, n + 1)
        for l2, h2 in zip(edges[:-1], edges[1:]):
            half = 0.5 * (h2 - l2)
            c = 0.5 * (h2 + l2)
            ts.append(c + half * x)
            ws.append(half * w)
            mids.append(np.full(n_gl, c))
    return np.concatenate(ts), np.concatenate(ws), np.concatenate(mids)


def pattern_window_dist(tau, T, K, a, b, irf_fwhm=None, rule="earliest"):
    """Distribución por ventana del fotón que sobrevive en un ciclo con ranuras ocupadas S.

    ``rule='highest'``: la de sim_exp (np.nonzero recorre por filas y la última escritura gana,
    o sea el haz de k más alto): h_S = C[:, max S].
    ``rule='earliest'``: TCSPC real sin tiempo muerto entre ciclos: sobrevive el fotón que llega
    primero en tiempo absoluto dentro del ciclo; su tiempo se pliega módulo T.
    Devuelve {tuple(S): vector de K} (su suma es la fracción capturada por las ventanas).
    """
    _check_geometry(T, K, b)
    C = mixing_matrix(tau, T, K, a, b, irf_fwhm)
    pats = [S for r in range(1, K + 1) for S in itertools.combinations(range(K), r)]
    if rule == "highest":
        return {S: C[:, max(S)].copy() for S in pats}
    if rule != "earliest":
        raise ValueError("rule debe ser 'highest' o 'earliest'")
    sigma = fwhm_to_sigma(irf_fwhm) if irf_fwhm else None
    dt = T / K
    t, w, mid = _quad_nodes(tau, T, K, a, b, sigma)
    # pertenencia a ventanas: constante dentro de cada tramo (se evalúa en su centro)
    member = np.zeros((K, t.size))
    for i in range(K):
        member[i] = (np.mod(mid - i * dt - a, T) < b).astype(float)
    f = np.array([decay_pdf(t - j * dt, tau, sigma) for j in range(K)])
    Sv = np.array([1.0 - decay_cdf(t - j * dt, tau, sigma) for j in range(K)])
    out = {}
    for S in pats:
        h = np.zeros(K)
        for k in S:
            g = f[k].copy()
            for j in S:
                if j != k:
                    g *= Sv[j]
            h += member.dot(g * w)
        out[S] = h
    return out


def sim_exp_window_probs(lam, Ns, Nb, Nh, M_p, tau, T, K, a, b, rule="highest",
                         irf_fwhm=None, return_details=False):
    """Probabilidades por ventana esperadas a tasa finita (condicionadas al total en ventanas).

    ``rule``: 'highest' (lo que hace sim_exp), 'earliest' (TCSPC real de primer fotón) o
    'ideal' (límite de tasa -> 0: el modelo de mezcla). Nh = fotones generados (Ns*factor),
    M_p = ciclos. El borrado al azar hasta Ns de sim_exp es uniforme sobre los ciclos ocupados,
    así que no sesga la composición. El fondo aporta Nb*b/T por ventana.
    """
    p = _norm_lam(lam)
    C = mixing_matrix(tau, T, K, a, b, irf_fwhm)
    if rule == "ideal":
        sig = C.dot(p)
        P = {}
    else:
        P = occupancy_pattern_probs(p, Nh, M_p)
        H = pattern_window_dist(tau, T, K, a, b, irf_fwhm, rule=rule)
        pocc = sum(P.values())
        sig = sum(P[S] * H[S] for S in P) / pocc
    e = Ns * sig + Nb * (b / T)
    probs = e / e.sum()
    if not return_details:
        return probs
    pocc = sum(P.values()) if P else float("nan")
    multi = sum(v for S, v in P.items() if len(S) >= 2) if P else float("nan")
    return probs, {
        "p_cycle_occupied": pocc,
        "frac_occupied_cycles_with_ge2_beams": multi / pocc if P else 0.0,
        "raw_rate_per_cycle": Nh / float(M_p),
    }
