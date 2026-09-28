# -*- coding: utf-8 -*-
"""Estimación de posición p-MINFLUX: MLE continuo con matriz de mezcla, MLE del legado (Ec. 3.5),
CRB y elipse de covarianza.

Modelo directo (por localización, condicionado al total de fotones dentro de las ventanas)::

    lam_k(r) = P_k * I(|r - pos_k|)              (P = potencias por haz; I = dona/gaussiano)
    q        = lam / sum(lam)
    s        = C q                               (C = mixing.mixing_matrix: fuga entre ventanas)
    e        = (1 - beta) s + beta * (b/T)       (beta = Nb/(Ns+Nb) en el ciclo completo)
    p        = e / sum(e)

``beta = 1/(1 + sbr)``; ``sbr = inf`` da ``beta = 0`` sin NaN (F110). Es la misma cuenta que
``mixing.window_probs(lam, C, b, T, sbr=sbr)`` (el test lo comprueba). El modelo del legado
(Masullo, Ec. 3.5; ``pos_MINFLUX``/``crb_minflux``) es el caso ``C = I`` y ``b/T = 1/K``:
``p = sbr/(sbr+1) q + 1/(sbr+1)/K`` = ``mixing.naive_probs``.

Estimador: máximo de verosimilitud multinomial, continuo (sin grilla: F106/F205), acotado al
disco ``|r - center| <= bounds_radius`` y vectorizado sobre localizaciones:

1. arranque en una grilla gruesa del disco (una sola multiplicación de matrices ``counts @ log
   p_grid``);
2. Fisher scoring (Newton con la información esperada) en lote, con búsqueda lineal y conjunto
   activo: si el óptimo está en el borde, la posición se reparametriza por el ángulo sobre el
   círculo (y ``beta`` se congela en sus cotas si corresponde). Se informa ``on_boundary`` (F203)
   y ``converged``.

Estorbos opcionales:

- ``free_bg=True`` (o ``'local'``): ``beta`` libre por localización (3 parámetros; con K = 4 hay
  3 grados de libertad, así que queda exactamente identificado). En el setup medido (tau = 4.21,
  [0, 10.1], SBR 6-21, posiciones de F104) el CRB por eje crece solo 1.000-1.038x (p. ej. 0.9453
  contra 0.926 nm en (5, -5)): la fuga entre ventanas ayuda a separar fondo de señal.
- ``free_bg='shared'``: un único ``beta`` para todo el conjunto de localizaciones.
- ``free_powers=True``: potencias relativas por haz (``P_0 = 1``) compartidas por todo el
  conjunto. **No son identificables con emisores en una sola posición** (con K = 4: 2 + 3
  parámetros para 3 grados de libertad); hace falta un conjunto con varias posiciones distintas.
  Los globales se estiman por verosimilitud perfilada (L-BFGS-B sobre los globales; en cada
  evaluación se re-ajustan todas las posiciones, con gradiente exacto por el teorema de la
  envolvente).

Ventanas solapadas (``b > T/K``): ``mle_mixing`` y ``crb`` levantan ``ValueError`` salvo
``allow_overlap=True`` (solo ``warnings.warn``): con solapamiento un fotón cuenta dos veces y la
verosimilitud/CRB multinomiales dejan de ser válidas (además el arranque en grilla puede caer en
un óptimo local equivocado, hallazgo del code-reviewer R2 con b = 20).

``converged``: True si el Fisher scoring terminó por su criterio (paso o mejora relativa de la
NLL por debajo de la tolerancia, o ningún paso mejora), y también si al agotar ``maxiter`` la NLL
mejoró <= 1e-6 (absoluto) en las últimas 10 iteraciones (ya está en el óptimo; U5 de R2).

Memoria: el arranque en grilla se calcula en bloques de ``chunk`` localizaciones (default 2e4),
con resultado idéntico al de un solo bloque.

Convenciones: nm, ns. ``counts`` (n_loc, K) (o (K,)); pueden ser reales (conteos esperados, para
sesgos asintóticos).
"""

import math
import warnings

import numpy as np
from scipy import optimize, stats

from . import psf as _psf
from .windows import check_overlap as _check_overlap

__all__ = ["sbr_to_beta", "forward_probs", "legacy_probs", "neg_loglike", "mle_mixing",
           "mle_legacy", "crb", "crb_legacy", "capture_fraction", "cov_ellipse", "MLEResult",
           "mixing_conditioning", "COND_MAX", "SMIN_MIN"]

COND_MAX = 1e3                 # C casi singular: número de condición > COND_MAX ...
SMIN_MIN = 1e-2                # ... o valor singular mínimo < SMIN_MIN -> warnings.warn
_P_FLOOR = 1e-300
_BETA_MAX = 0.999
_CHUNK = 20000                 # localizaciones por bloque en el arranque en grilla
_CONV_DNLL = 1e-6              # dNLL absoluto en las últimas 10 iteraciones: en el óptimo
_CONV_WINDOW = 10


def sbr_to_beta(sbr):
    """Fracción de fondo del ciclo completo, beta = Nb/(Ns+Nb) = 1/(1+sbr). inf -> 0 (F110)."""
    sbr = float(sbr)
    if math.isinf(sbr) and sbr > 0:
        return 0.0
    if not sbr > 0:
        raise ValueError("sbr debe ser > 0 (o inf)")
    return 1.0 / (1.0 + sbr)


def _as_C(C, K):
    if C is None:
        return np.eye(K)
    C = np.asarray(C, dtype=float)
    if C.shape != (K, K):
        raise ValueError("C debe ser (K, K) con K = %d" % K)
    return C


def mixing_conditioning(C, warn=True, stacklevel=3):
    """Número de condición y valor singular mínimo de la matriz de mezcla ``C``.

    Con ``warn=True`` emite ``warnings.warn`` (UserWarning) si ``C`` es casi singular
    (``cond > COND_MAX = 1e3`` o ``s_min < SMIN_MIN = 1e-2``): las ventanas no separan los haces
    (p. ej. IRF de 0.3 ns centrada en el pulso con tau ~ 0 y ``b = T/K``, que manda la mitad de
    cada haz a la ventana anterior: al emular ``sim_exp`` hay que usar ``irf_fwhm=0``) y el MLE
    y el CRB con esa C son inestables. ``mle_mixing`` y ``crb`` la llaman. Devuelve
    ``(cond, s_min)``.
    """
    C = np.asarray(C, dtype=float)
    sv = np.linalg.svd(C, compute_uv=False)
    smin = float(sv.min())
    cond = float(sv.max() / smin) if smin > 0 else float("inf")
    if warn and (cond > COND_MAX or smin < SMIN_MIN):
        warnings.warn("matriz de mezcla C casi singular (cond = %.3g, s_min = %.3g): las ventanas "
                      "no separan los haces; revise tau, irf_fwhm, a, b (al emular sim_exp use "
                      "irf_fwhm=0 y dead_time=0)" % (cond, smin), UserWarning,
                      stacklevel=stacklevel)
    return cond, smin


def _logpow(powers, K):
    if powers is None:
        return np.zeros(K)
    P = np.asarray(powers, dtype=float)
    if P.shape != (K,) or not np.all(P > 0):
        raise ValueError("powers debe ser (K,) y > 0")
    lp = np.log(P)
    return lp - lp[0]


# ---------------------------------------------------------------------------------------------
# Modelo directo con derivadas analíticas
# ---------------------------------------------------------------------------------------------

class _Model(object):
    """Modelo p(r, beta, logpow) para una geometría fija. Parámetros de dp, en este orden:
    x, y, beta, logpow_1..logpow_{K-1}."""

    def __init__(self, pos, fwhm, C, c, kind="donut"):
        self.pos = np.asarray(pos, dtype=float)
        self.K = self.pos.shape[0]
        self.fwhm = float(fwhm)
        self.C = _as_C(C, self.K)
        self.c = float(c)
        self.kind = kind

    def unnorm(self, r, beta, logpow):
        lam = _psf.lambda_beams(r, self.pos, self.fwhm, self.kind) * np.exp(logpow)
        q = lam / lam.sum(-1, keepdims=True)
        s = q.dot(self.C.T)
        return (1.0 - beta)[..., None] * s + beta[..., None] * self.c

    def probs(self, r, beta, logpow):
        e = self.unnorm(r, beta, logpow)
        return e / e.sum(-1, keepdims=True)

    def probs_grad(self, r, beta, logpow):
        """p (n, K) y dp (n, 3 + K-1, K)."""
        K = self.K
        lam0, dlam0 = _psf.lambda_beams(r, self.pos, self.fwhm, self.kind, grad=True)
        P = np.exp(logpow)
        lam = lam0 * P
        dlam_r = dlam0 * P                                   # (n, 2, K)
        S = lam.sum(-1)
        q = lam / S[:, None]
        dq_r = (dlam_r - q[:, None, :] * dlam_r.sum(-1)[..., None]) / S[:, None, None]
        eye = np.eye(K)[1:]                                  # (K-1, K)
        dq_p = q[:, None, 1:].transpose(0, 2, 1) * (eye[None] - q[:, None, :])   # (n, K-1, K)
        s = q.dot(self.C.T)
        ds_r = dq_r.dot(self.C.T)
        ds_p = dq_p.dot(self.C.T)
        om = (1.0 - beta)[:, None, None]
        e = (1.0 - beta)[:, None] * s + beta[:, None] * self.c
        de = np.concatenate([om * ds_r, (self.c - s)[:, None, :], om * ds_p], axis=1)
        E = e.sum(-1)
        p = e / E[:, None]
        dp = (de - p[:, None, :] * de.sum(-1)[..., None]) / E[:, None, None]
        return p, dp, E


def forward_probs(r, pos, fwhm, C, b, T, sbr, powers=None, bg=None, kind="donut"):
    """Probabilidades por ventana del modelo de mezcla, normalizadas sobre las ventanas.

    ``r``: (2,) o (n, 2). ``C``: matriz de mezcla (K, K) (None = identidad). ``b``, ``T``: ancho de
    ventana y período (el fondo aporta b/T por ventana). ``sbr`` = Ns/Nb del ciclo completo.
    ``powers``: potencias relativas por haz (None = iguales). ``bg``: si se da, fracción de fondo
    ``beta`` = Nb/(Ns+Nb) (reemplaza a ``sbr``). Devuelve (K,) o (n, K).
    """
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T")
    pos = np.asarray(pos, dtype=float)
    r = np.asarray(r, dtype=float)
    single = r.ndim == 1
    r2 = np.atleast_2d(r)
    beta = sbr_to_beta(sbr) if bg is None else float(bg)
    if not (0.0 <= beta < 1.0):
        raise ValueError("bg debe estar en [0, 1)")
    m = _Model(pos, fwhm, C, b / float(T), kind)
    p = m.probs(r2, np.full(r2.shape[0], beta), _logpow(powers, m.K))
    return p[0] if single else p


def legacy_probs(r, pos, fwhm, sbr, powers=None, kind="donut"):
    """Modelo de la Ec. 3.5 (pos_MINFLUX/crb_minflux): C = I y fondo 1/K."""
    K = np.asarray(pos).shape[0]
    return forward_probs(r, pos, fwhm, None, 1.0, float(K), sbr, powers=powers, kind=kind)


def capture_fraction(r, pos, fwhm, C, b, T, sbr, powers=None, kind="donut"):
    """Fracción de los fotones detectados del ciclo completo que cae dentro de las ventanas."""
    r2 = np.atleast_2d(np.asarray(r, dtype=float))
    m = _Model(pos, fwhm, C, b / float(T), kind)
    e = m.unnorm(r2, np.full(r2.shape[0], sbr_to_beta(sbr)), _logpow(powers, m.K))
    out = e.sum(-1)
    return out[0] if np.asarray(r).ndim == 1 else out


def _nll(counts, p):
    lp = np.log(np.maximum(p, _P_FLOOR))
    return -np.sum(np.where(counts > 0, counts * lp, 0.0), axis=-1)


def neg_loglike(counts, r, pos, fwhm, C, b, T, sbr, powers=None, bg=None, kind="donut"):
    """-sum_i n_i log p_i(r) (sin la constante multinomial)."""
    p = forward_probs(r, pos, fwhm, C, b, T, sbr, powers=powers, bg=bg, kind=kind)
    return _nll(np.asarray(counts, dtype=float), p)


# ---------------------------------------------------------------------------------------------
# Ajuste en lote
# ---------------------------------------------------------------------------------------------

class MLEResult(dict):
    """dict con atributos: r (n,2), on_boundary, converged, nll, n_iter, beta (n,), powers (K,),
    boundary_fraction, n_failed, globals_result."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


def _disk_grid(center, R, step):
    n = int(math.ceil(R / step))
    g = np.arange(-n, n + 1) * step
    X, Y = np.meshgrid(g, g)
    m = X ** 2 + Y ** 2 <= R ** 2 * (1 + 1e-12)
    pts = np.column_stack([X[m], Y[m]])
    return pts + np.asarray(center, dtype=float)


def _project(r, center, R):
    d = r - center
    rho = np.hypot(d[:, 0], d[:, 1])
    f = np.where(rho > R, R / np.maximum(rho, 1e-300), 1.0)
    return center + d * f[:, None]


def _fit_local(model, counts, r0, beta0, logpow, center, R, free_beta, maxiter=200,
               xtol=1e-9, ftol=1e-13):
    """Fisher scoring en lote con conjunto activo (borde del disco y cotas de beta)."""
    n = counts.shape[0]
    r = r0.copy()
    beta = beta0.copy()
    N = counts.sum(-1)
    nloc_par = 3 if free_beta else 2
    active = np.ones(n, dtype=bool)
    converged = np.zeros(n, dtype=bool)
    n_iter = np.zeros(n, dtype=int)
    lp_full = logpow
    p_all = model.probs(r, beta, lp_full)
    f = _nll(counts, p_all)
    f_hist = [f.copy()]
    for it in range(maxiter):
        idx = np.nonzero(active)[0]
        if idx.size == 0:
            break
        n_iter[idx] += 1
        ra, ba, ca, Na, fa = r[idx], beta[idx], counts[idx], N[idx], f[idx]
        p, dp, _ = model.probs_grad(ra, ba, lp_full)
        dp = dp[:, :nloc_par, :]
        pf = np.maximum(p, 1e-15)
        w = ca / pf
        g = -np.einsum("nk,npk->np", w, dp)                  # gradiente de la NLL
        H = Na[:, None, None] * np.einsum("npk,nqk,nk->npq", dp, dp, 1.0 / pf)
        d = ra - center
        rho = np.hypot(d[:, 0], d[:, 1])
        on_edge = (rho >= R * (1 - 1e-10)) & (-(g[:, 0] * d[:, 0] + g[:, 1] * d[:, 1]) > 0)
        # coordenadas reducidas: interior (x, y[, beta]) o borde (phi[, beta])
        m = idx.size
        J = np.zeros((m, nloc_par, nloc_par))
        J[:, 0, 0] = 1.0
        J[:, 1, 1] = 1.0
        if free_beta:
            J[:, 2, 2] = 1.0
        # en el borde: columna 0 = dr/dphi = (-dy, dx), columna 1 = 0
        J[on_edge, 0, 0] = -d[on_edge, 1]
        J[on_edge, 1, 0] = d[on_edge, 0]
        J[on_edge, 0, 1] = 0.0
        J[on_edge, 1, 1] = 0.0
        gr = np.einsum("npq,np->nq", J, g)
        Hr = np.einsum("npq,nps,nsr->nqr", J, H, J)
        # curvatura del círculo: d2r/dphi2 = -d  ->  + g_r . (-d)
        Hr[on_edge, 0, 0] += -(g[on_edge, 0] * d[on_edge, 0] + g[on_edge, 1] * d[on_edge, 1])
        freeze = np.zeros((m, nloc_par), dtype=bool)
        freeze[on_edge, 1] = True
        if free_beta:
            freeze[:, 2] = ((ba <= 0.0) & (gr[:, 2] > 0)) | ((ba >= _BETA_MAX) & (gr[:, 2] < 0))
        gr = np.where(freeze, 0.0, gr)
        Hr = np.where(freeze[:, :, None] | freeze[:, None, :], 0.0, Hr)
        Hr = Hr + np.eye(nloc_par)[None] * (freeze[:, :, None] * 1.0)
        # regularización mínima (Levenberg) para que Hr sea definida positiva
        tr = np.trace(Hr, axis1=1, axis2=2)
        Hr = Hr + np.eye(nloc_par)[None] * (1e-10 * np.abs(tr) + 1e-300)[:, None, None]
        try:
            step = -np.linalg.solve(Hr, gr[..., None])[..., 0]
        except np.linalg.LinAlgError:
            step = -gr / np.maximum(np.abs(np.diagonal(Hr, axis1=1, axis2=2)), 1e-12)
        bad = ~np.all(np.isfinite(step), axis=1) | (np.einsum("np,np->n", step, gr) > 0)
        if np.any(bad):
            step[bad] = -gr[bad] / np.maximum(np.abs(np.diagonal(Hr[bad], axis1=1, axis2=2)), 1e-12)
        phi0 = np.arctan2(d[:, 1], d[:, 0])
        alpha = np.ones(m)
        accepted = np.zeros(m, dtype=bool)
        r_new = ra.copy()
        b_new = ba.copy()
        f_new = fa.copy()
        todo = np.ones(m, dtype=bool)
        for _ in range(45):
            t = np.nonzero(todo)[0]
            if t.size == 0:
                break
            st = step[t] * alpha[t, None]
            rc = ra[t] + st[:, :2]
            e_t = on_edge[t]
            if np.any(e_t):
                ph = phi0[t][e_t] + st[e_t, 0]
                rc[e_t] = center + R * np.column_stack([np.cos(ph), np.sin(ph)])
            rc = _project(rc, center, R)
            bc = ba[t].copy()
            if free_beta:
                bc = np.clip(bc + st[:, 2], 0.0, _BETA_MAX)
            fc = _nll(ca[t], model.probs(rc, bc, lp_full))
            ok = fc <= fa[t] + ftol * (1.0 + np.abs(fa[t]))
            ok &= np.isfinite(fc)
            gi = t[ok]
            r_new[gi], b_new[gi], f_new[gi] = rc[ok], bc[ok], fc[ok]
            accepted[gi] = True
            todo[gi] = False
            alpha[t[~ok]] *= 0.5
        dx = np.max(np.abs(np.column_stack([r_new - ra, (b_new - ba) * 100.0])), axis=1)
        df = fa - f_new
        # "poca mejora" solo cuenta como convergencia si el paso fue (casi) completo; un paso
        # muy recortado por la búsqueda lineal no prueba que se llegó al óptimo.
        done = (~accepted) | (dx < xtol) | ((df < ftol * (1.0 + np.abs(fa))) & (alpha >= 0.25))
        r[idx], beta[idx], f[idx] = r_new, b_new, f_new
        converged[idx[done & accepted]] = True
        # sin paso aceptable: es un óptimo local a la precisión de la máquina
        converged[idx[~accepted]] = True
        active[idx[done]] = False
        f_hist.append(f.copy())
        if len(f_hist) > _CONV_WINDOW + 1:
            f_hist.pop(0)
    # agotó maxiter: si la NLL no mejoró más de 1e-6 en las últimas iteraciones, está en el óptimo
    left = active & ~converged
    if np.any(left):
        converged[left] = (f_hist[0][left] - f[left]) <= _CONV_DNLL
    d = r - center
    on_b = np.hypot(d[:, 0], d[:, 1]) >= R * (1 - 1e-7)
    return r, beta, f, converged, on_b, n_iter


def _mle_core(counts, pos, fwhm, C, c, sbr, bounds_radius, center, powers, free_bg,
              free_powers, kind, x0, grid_step, maxiter, chunk=_CHUNK):
    counts = np.asarray(counts, dtype=float)
    single = counts.ndim == 1
    counts = np.atleast_2d(counts)
    pos = np.asarray(pos, dtype=float)
    K = pos.shape[0]
    if counts.shape[1] != K:
        raise ValueError("counts debe tener K = %d columnas" % K)
    if np.any(counts < 0) or np.any(~np.isfinite(counts)):
        raise ValueError("counts debe ser finito y >= 0")
    R = float(bounds_radius)
    if not R > 0:
        raise ValueError("bounds_radius debe ser > 0")
    center = np.asarray(center, dtype=float)
    model = _Model(pos, fwhm, C, c, kind)
    n = counts.shape[0]
    if free_bg is True:
        free_bg = "local"
    if free_bg not in (False, None, "local", "shared"):
        raise ValueError("free_bg: False, True/'local' o 'shared'")
    free_beta_local = free_bg == "local"
    beta_init = sbr_to_beta(sbr) if sbr is not None else 0.05
    lp = _logpow(powers, K)
    beta = np.full(n, beta_init)
    empty = counts.sum(-1) <= 0
    # arranque en grilla
    G = _disk_grid(center, R, grid_step or R / 12.0)

    if chunk is None or int(chunk) < 1:
        raise ValueError("chunk debe ser un entero >= 1")
    chunk = int(chunk)

    def grid_start(lp_, beta_g):
        pg = model.probs(G, np.full(G.shape[0], beta_g), lp_)
        lpg = np.log(np.maximum(pg, _P_FLOOR)).T                     # (K, G)
        best = np.empty(n, dtype=np.int64)
        for s0 in range(0, n, chunk):                                # (chunk, G) por bloque
            best[s0:s0 + chunk] = np.argmax(counts[s0:s0 + chunk].dot(lpg), axis=1)
        return G[best]

    if x0 is None:
        r0 = grid_start(lp, beta_init)
    else:
        r0 = _project(np.atleast_2d(np.asarray(x0, dtype=float)).copy(), center, R)
        if r0.shape[0] == 1 and n > 1:
            r0 = np.repeat(r0, n, axis=0)

    n_glob_p = (K - 1) if free_powers else 0
    use_glob = bool(free_powers) or free_bg == "shared"
    state = {"r": r0.copy(), "beta": beta.copy()}
    ok = ~empty

    def inner(lp_, beta_vec, restart=False):
        # con globales libres se re-arranca de la grilla en cada evaluación: así la verosimilitud
        # perfilada es una función determinista de los globales (no depende del camino).
        if restart and x0 is None:
            state["r"][:] = grid_start(lp_, float(np.median(beta_vec)))
        r, b, f, conv, onb, nit = _fit_local(model, counts[ok], state["r"][ok], beta_vec[ok],
                                             lp_, center, R, free_beta_local, maxiter=maxiter)
        state["r"][ok], state["beta"][ok] = r, b
        return f, conv, onb, nit

    glob_res = None
    if not use_glob:
        f, conv, onb, nit = inner(lp, beta)
    else:
        # vector global: [logpow_1..K-1][, beta_shared]
        x_init = list(lp[1:]) if free_powers else []
        bnds = [(-4.0, 4.0)] * n_glob_p
        if free_bg == "shared":
            x_init.append(beta_init)
            bnds.append((0.0, _BETA_MAX))
        x_init = np.array(x_init, dtype=float)

        def unpack(x):
            lp_ = lp.copy()
            if free_powers:
                lp_[1:] = x[:n_glob_p]
            bvec = np.full(n, x[-1]) if free_bg == "shared" else state["beta"].copy()
            return lp_, bvec

        def obj(x):
            lp_, bvec = unpack(x)
            if free_bg == "shared":
                state["beta"][:] = bvec
            f, conv, onb, nit = inner(lp_, bvec, restart=True)
            # gradiente por la envolvente: derivada parcial respecto de los globales
            p, dp, _ = model.probs_grad(state["r"][ok], state["beta"][ok], lp_)
            w = counts[ok] / np.maximum(p, 1e-15)
            gall = -np.einsum("nk,npk->p", w, dp)        # (3 + K-1,)
            g = []
            if free_powers:
                g.extend(gall[3:])
            if free_bg == "shared":
                g.append(gall[2])
            return float(np.sum(f)), np.array(g)

        glob_res = optimize.minimize(obj, x_init, jac=True, method="L-BFGS-B", bounds=bnds,
                                     options={"maxiter": 200, "ftol": 1e-14, "gtol": 1e-7})
        lp, bvec = unpack(glob_res.x)
        if free_bg == "shared":
            state["beta"][:] = bvec
        f, conv, onb, nit = inner(lp, state["beta"], restart=True)

    r_out = state["r"].copy()
    nll = np.full(n, np.nan)
    converged = np.zeros(n, dtype=bool)
    on_boundary = np.zeros(n, dtype=bool)
    n_iter = np.zeros(n, dtype=int)
    nll[ok], converged[ok], on_boundary[ok], n_iter[ok] = f, conv, onb, nit
    r_out[empty] = np.nan
    res = MLEResult(
        r=r_out[0] if single else r_out,
        on_boundary=on_boundary[0] if single else on_boundary,
        converged=converged[0] if single else converged,
        nll=nll[0] if single else nll,
        n_iter=n_iter[0] if single else n_iter,
        beta=(state["beta"][0] if single else state["beta"].copy()),
        powers=np.exp(lp),
        boundary_fraction=float(np.mean(on_boundary[ok])) if np.any(ok) else float("nan"),
        n_failed=int(np.sum(~converged[ok]) + np.sum(empty)),
        globals_result=(None if glob_res is None else
                        {"success": bool(glob_res.success), "nit": int(glob_res.nit),
                         "message": str(glob_res.message)}),
    )
    return res


def mle_mixing(counts, pos, fwhm, C, b, T, sbr, bounds_radius, center=(0.0, 0.0), powers=None,
               free_bg=False, free_powers=False, kind="donut", x0=None, grid_step=None,
               maxiter=200, chunk=_CHUNK, allow_overlap=False):
    """MLE continuo con el modelo de mezcla (C conocida). Ver el docstring del módulo.

    ``sbr``: Ns/Nb del ciclo completo (valor conocido, o arranque si ``free_bg``).
    ``powers``: potencias relativas conocidas (o arranque si ``free_powers``).
    Devuelve un ``MLEResult`` (r, on_boundary, converged, nll, n_iter, beta, powers,
    boundary_fraction, n_failed, globals_result). Localizaciones sin cuentas: r = NaN.
    ``chunk``: localizaciones por bloque del arranque en grilla (solo memoria; mismo resultado).
    ``allow_overlap``: con ``b > T/K`` (ventanas solapadas) levanta ``ValueError`` salvo True
    (entonces solo ``warnings.warn``).
    """
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T")
    if C is None:
        raise ValueError("mle_mixing necesita C (use mle_legacy para el modelo sin fuga)")
    _check_overlap(b, T, np.asarray(pos).shape[0], allow_overlap)
    mixing_conditioning(_as_C(C, np.asarray(pos).shape[0]))
    return _mle_core(counts, pos, fwhm, C, b / float(T), sbr, bounds_radius, center, powers,
                     free_bg, free_powers, kind, x0, grid_step, maxiter, chunk)


def mle_legacy(counts, pos, fwhm, sbr, bounds_radius, center=(0.0, 0.0), powers=None,
               free_bg=False, free_powers=False, kind="donut", x0=None, grid_step=None,
               maxiter=200, chunk=_CHUNK):
    """MLE continuo de la Ec. 3.5 (``pos_MINFLUX`` sin la grilla): C = I, fondo 1/K."""
    K = np.asarray(pos).shape[0]
    return _mle_core(counts, pos, fwhm, None, 1.0 / K, sbr, bounds_radius, center, powers,
                     free_bg, free_powers, kind, x0, grid_step, maxiter, chunk)


# ---------------------------------------------------------------------------------------------
# Cota de Cramér-Rao
# ---------------------------------------------------------------------------------------------

def crb(r, pos, fwhm, C, b, T, sbr, N, powers=None, free_bg=False, free_powers=False,
        kind="donut", n_is="cycle", return_cov=False, allow_overlap=False):
    """CRB por eje sigma = sqrt(tr(Cov_xy)/2) del modelo de mezcla (multinomial en las ventanas).

    ``N``: fotones por localización. ``n_is='cycle'`` (default, la convención del plan): N = Ns+Nb
    detectados en el ciclo completo; el total en ventanas es N * capture_fraction. ``'windows'``:
    N ya es el total dentro de las ventanas.
    Estorbos: ``free_bg`` (True/'local': beta por localización; 'shared': beta común a todas las
    ``r``) y ``free_powers`` (potencias comunes a todas las ``r``, P_0 = 1). Los globales se
    marginalizan con el complemento de Schur sobre el Fisher conjunto de todas las filas de
    ``r`` (cada una con N fotones). Sin identificabilidad devuelve inf.
    Con C = I, b = T/K y sbr = inf coincide con el CRB ingenuo (``crb_minflux``).
    Con ``b > T/K`` (ventanas solapadas, la multinomial deja de valer) levanta ``ValueError``
    salvo ``allow_overlap=True`` (solo ``warnings.warn``).
    """
    if not (0 < b <= T):
        raise ValueError("se necesita 0 < b <= T")
    _check_overlap(b, T, np.asarray(pos).shape[0], allow_overlap)
    r = np.asarray(r, dtype=float)
    single = r.ndim == 1
    r2 = np.atleast_2d(r)
    n = r2.shape[0]
    pos = np.asarray(pos, dtype=float)
    K = pos.shape[0]
    if C is not None:
        mixing_conditioning(_as_C(C, K))
    model = _Model(pos, fwhm, C, b / float(T), kind)
    beta = np.full(n, sbr_to_beta(sbr))
    lp = _logpow(powers, K)
    p, dp, E = model.probs_grad(r2, beta, lp)
    if n_is == "cycle":
        Nw = float(N) * E
    elif n_is == "windows":
        Nw = np.full(n, float(N))
    else:
        raise ValueError("n_is: 'cycle' o 'windows'")
    if free_bg is True:
        free_bg = "local"
    loc = [0, 1] + ([2] if free_bg == "local" else [])
    glob = (list(range(3, 3 + K - 1)) if free_powers else []) + ([2] if free_bg == "shared" else [])
    pf = np.maximum(p, 1e-300)
    F = Nw[:, None, None] * np.einsum("npk,nqk,nk->npq", dp, dp, 1.0 / pf)
    A = F[:, loc][:, :, loc]
    cov = np.full((n, 2, 2), np.inf)
    with np.errstate(all="ignore"):
        try:
            Ainv = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            Ainv = np.linalg.pinv(A)
        if not glob:
            cov = Ainv[:, :2, :2]
        else:
            B = F[:, loc][:, :, glob]                       # (n, l, g)
            D = F[:, glob][:, :, glob]
            G = D.sum(0) - np.einsum("nlg,nlm,nmh->gh", B, Ainv, B)
            if np.linalg.cond(G) < 1e12:
                Ginv = np.linalg.inv(G)
                AB = np.einsum("nlm,nmg->nlg", Ainv, B)
                full = Ainv + np.einsum("nlg,gh,nmh->nlm", AB, Ginv, AB)
                cov = full[:, :2, :2]
    sig = np.sqrt(0.5 * np.trace(cov, axis1=1, axis2=2))
    sig = np.where(np.isfinite(sig), sig, np.inf)
    if return_cov:
        return (sig[0], cov[0]) if single else (sig, cov)
    return sig[0] if single else sig


def crb_legacy(r, pos, fwhm, sbr, N, powers=None, kind="donut", return_cov=False):
    """CRB que reporta ``crb_minflux`` (Ec. 3.5, N = Ns + Nb)."""
    K = np.asarray(pos).shape[0]
    return crb(r, pos, fwhm, None, 1.0, float(K), sbr, N, powers=powers, kind=kind,
               return_cov=return_cov)


# ---------------------------------------------------------------------------------------------
# Elipse de covarianza (F108 corregido)
# ---------------------------------------------------------------------------------------------

def cov_ellipse(cov, nsig=1.0, q=None):
    """Ejes y orientación de la elipse de confianza de una covarianza 2x2.

    Devuelve (width, height, angle_deg) en la convención de ``matplotlib.patches.Ellipse``:
    ``width`` = eje mayor completo = 2 sqrt(r2 * lambda_max), a lo largo de ``angle`` (grados,
    en (-90, 90]); ``height`` = eje menor. ``r2 = chi2.ppf(q, 2)`` con ``q`` dado o
    ``q = 2 Phi(nsig) - 1``. Corrige F108: autovectores por columnas (``vec[:, order]``),
    ``arctan2(v_y, v_x)`` y el factor r2 que el legado calculaba pero no usaba.
    """
    cov = np.asarray(cov, dtype=float)
    if cov.shape != (2, 2) or not np.allclose(cov, cov.T, rtol=1e-10, atol=1e-12):
        raise ValueError("cov debe ser 2x2 simétrica")
    if q is None:
        if nsig is None or not nsig > 0:
            raise ValueError("dar nsig > 0 o q en (0, 1)")
        q = 2.0 * stats.norm.cdf(nsig) - 1.0
    if not (0 < q < 1):
        raise ValueError("q debe estar en (0, 1)")
    r2 = stats.chi2.ppf(q, 2)
    val, vec = np.linalg.eigh(cov)                 # ascendente, autovectores en columnas
    if val[0] < -1e-12 * max(abs(val[1]), 1.0):
        raise ValueError("cov no es semidefinida positiva")
    val = np.clip(val, 0.0, None)
    vmaj = vec[:, 1]
    ang = math.degrees(math.atan2(vmaj[1], vmaj[0]))
    ang = (ang + 90.0) % 180.0 - 90.0
    if ang == -90.0:
        ang = 90.0
    return 2.0 * math.sqrt(r2 * val[1]), 2.0 * math.sqrt(r2 * val[0]), ang
