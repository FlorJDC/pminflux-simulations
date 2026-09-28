# -*- coding: utf-8 -*-
"""Simulador p-MINFLUX pulsado en dominio temporal (fotón por fotón, vectorizado por bloques).

Física (convenciones de ``pminflux_sim.mixing``):

- Ciclo TCSPC de período ``T`` (ns), ``K`` haces intercalados; el pulso del haz ``j`` sale en
  ``j*T/K`` dentro de cada ciclo.
- Llegadas incidentes: proceso de Poisson de ``rate_per_cycle`` fotones por ciclo (señal + fondo,
  antes de TCSPC y tiempo muerto). Por adelgazamiento de Poisson, cada fotón es de señal con
  probabilidad ``sbr/(sbr+1)`` y de fondo con ``1/(sbr+1)``; los de señal eligen el haz ``j`` con
  probabilidad ``q_j = lambda_j*P_j / sum(lambda*P)`` (``P`` = ``beam_powers``).
- Fotón de señal excitado en el ciclo ``m`` por el haz ``j``: llega en el tiempo ABSOLUTO
  ``m*T + j*T/K + X`` con ``X = N(0, sigma_IRF^2) + Exp(tau)``. La cola cae en ventanas
  posteriores y en el ciclo siguiente (fuga), y con IRF un fotón del haz 0 puede caer al final del
  ciclo anterior. El microtiempo registrado es ``tiempo_absoluto mod T``.
- Fondo: uniforme en el tiempo absoluto (uniforme en el ciclo). Compite en el TCSPC igual que la
  señal.

Reglas de registro (``tcspc``):

- ``"earliest"`` (TCSPC real): primero el detector (SPAD) con tiempo muerto NO paralizable
  ``dead_time`` sobre el tiempo absoluto (abarca ciclos: una detección al final de un ciclo ciega el
  comienzo del siguiente); después el TCSPC registra solo la PRIMERA avalancha de cada ciclo de
  llegada. Con ``dead_time = 0`` queda solo "1 fotón por ciclo, gana el más temprano".
  El valor por defecto de 22 ns es un SUPUESTO (valor típico de SPAD), no un valor medido del
  equipo de la autora.
- ``"highest"``: emula ``sim_exp`` del legado (hallazgo F101): los fotones de señal se recortan a 1
  por ranura (ciclo de excitación, haz) y en un ciclo con >= 2 haces ocupados sobrevive el de k más
  alto; el fondo se agrega aparte y no compite. ``dead_time`` se ignora (sim_exp no lo tiene).
- ``"none"``: se registran todos los fotones (sin TCSPC ni tiempo muerto).

Conteo por ventana (``counting``):

- ``"periodic"``: ventana ``i`` = ``[i*T/K + a, i*T/K + a + b)`` plegada módulo ``T`` (se admite
  ``a < 0`` y cruce de ``T``); el mismo criterio que ``mixing.mixing_matrix`` y exactamente la
  misma cuenta que ``windows.count_windows`` sobre los microtiempos de ``return_tags``.
- Ventanas solapadas (``b > T/K``): ``ValueError`` salvo ``SimParams(allow_overlap=True)``, que
  solo avisa (``warnings.warn``); la CRB/verosimilitud multinomial dejan de ser válidas.
- ``"legacy"``: emula ``nMINFLUX`` (F102/F103): desigualdad estricta ``ti < t < tf`` sin pliegue
  (una ventana que cruza ``T`` o empieza antes de 0 pierde lo que cae del otro lado; ventanas que se
  solapan cuentan dos veces) y, como en ``sim_exp``, cada ciclo sin fotón de SEÑAL registrado aporta
  un microtiempo 0.0 (ceros = ciclos transcurridos hasta la última detección - detecciones de señal,
  igual que ``len(Tmicro) - Ns`` en el legado).

``N`` (``n_mode``): ``"fixed"`` = exactamente N fotones registrados (señal + fondo, ciclo
completo, después de TCSPC/tiempo muerto) por localización; ``"poisson"`` = N ~ Poisson(N).
La simulación corre el proceso físico hasta la N-ésima detección (el número de ciclos resulta
aleatorio). Las primeras N detecciones son exactas: solo se usan llegadas anteriores a
``t_cut = (ciclo del último fotón generado)*T - 8 sigma_IRF``, que ya no pueden ser afectadas por
fotones aún no generados; si faltan detecciones, el proceso se extiende (no se descarta nada).

Rendimiento: vectorizado sobre bloques de localizaciones (matrices ``(filas, fotones)``); el tiempo
muerto se resuelve por iteración de punto fijo vectorizada (converge en tantas pasadas como la
cadena de conflictos más larga, 2-4 a tasas de tracking).
"""

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from .windows import check_overlap, window_masks

__all__ = ["SimParams", "simulate_counts", "DEAD_TIME_ASSUMPTION"]

DEAD_TIME_ASSUMPTION = ("dead_time = 22 ns por defecto es un SUPUESTO (valor típico de SPAD); "
                        "no es un valor medido del detector del experimento")

_FWHM_TO_SIGMA = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))
_CHUNK_ELEMS = 1500000      # fotones por bloque (filas x columnas)
_IRF_CUT_SIGMAS = 8.0


@dataclass
class SimParams:
    """Parámetros del simulador (ns). Ver el docstring del módulo.

    ``dead_time`` = 22 ns por defecto es un SUPUESTO declarado (SPAD típico), no un valor medido.
    """
    T: float = 50.0
    K: int = 4
    tau: float = 4.21
    irf_fwhm: float = 0.3          # ns; 0/None = sin IRF
    a: float = 0.0
    b: float = 10.1                # ventana i = [i*T/K + a, i*T/K + a + b] mod T
    rate_per_cycle: float = 2.5e-3  # fotones incidentes (señal+fondo) por ciclo
    dead_time: float = 22.0        # ns; SUPUESTO; abarca ciclos; 0 = solo "1 fotón por ciclo"
    tcspc: str = "earliest"        # "earliest" | "highest" (sim_exp, F101) | "none"
    counting: str = "periodic"     # "periodic" | "legacy" (nMINFLUX, F102/F103)
    n_mode: str = "fixed"          # "fixed" | "poisson"
    beam_powers: Optional[Sequence[float]] = None   # multiplica lambda (F202); None = iguales
    allow_overlap: bool = False    # b > T/K: ValueError salvo True (entonces solo warnings.warn)


def _check(p):
    if int(p.K) != p.K or p.K < 1:
        raise ValueError("K debe ser un entero >= 1")
    if p.T <= 0 or p.tau <= 0:
        raise ValueError("T y tau deben ser > 0")
    if not (0 < p.b <= p.T):
        raise ValueError("se necesita 0 < b <= T")
    check_overlap(p.b, p.T, p.K, p.allow_overlap)
    if not (p.rate_per_cycle > 0):
        raise ValueError("rate_per_cycle debe ser > 0")
    if p.dead_time is None or p.dead_time < 0:
        raise ValueError("dead_time debe ser >= 0")
    if p.irf_fwhm is not None and p.irf_fwhm < 0:
        raise ValueError("irf_fwhm debe ser >= 0")
    if p.tcspc not in ("earliest", "highest", "none"):
        raise ValueError("tcspc debe ser 'earliest', 'highest' o 'none'")
    if p.counting not in ("periodic", "legacy"):
        raise ValueError("counting debe ser 'periodic' o 'legacy'")
    if p.n_mode not in ("fixed", "poisson"):
        raise ValueError("n_mode debe ser 'fixed' o 'poisson'")


def _beam_probs(lambda_beams, n_loc, K, powers):
    lam = np.asarray(lambda_beams, dtype=float)
    if lam.ndim == 1:
        lam = np.broadcast_to(lam, (n_loc, lam.size))
    if lam.shape != (n_loc, K):
        raise ValueError("lambda_beams debe ser (K,) o (n_loc, K) con K = %d" % K)
    if powers is not None:
        pw = np.asarray(powers, dtype=float)
        if pw.shape != (K,) or np.any(pw < 0):
            raise ValueError("beam_powers debe ser (K,) no negativo")
        lam = lam * pw
    if np.any(lam < 0) or np.any(~np.isfinite(lam)):
        raise ValueError("lambda_beams debe ser finito y no negativo")
    s = lam.sum(axis=1, keepdims=True)
    if np.any(s <= 0):
        raise ValueError("cada fila de lambda (x potencias) debe tener suma > 0")
    return lam / s


class _Raw(object):
    """Fotones incidentes de un bloque de filas (en orden de tiempo base)."""
    __slots__ = ("base", "arr", "src", "cyc")

    def __init__(self, base, arr, src, cyc):
        self.base, self.arr, self.src, self.cyc = base, arr, src, cyc


def _generate(rng, t0, n, q, p, fs, sigma, mask=None):
    """n fotones incidentes por fila, continuando el proceso de Poisson desde t0 (ns).

    ``mask`` (M,) bool: ciclos en que el emisor está encendido (F107), con extensión periódica
    ``mask[ciclo % M]``. Un fotón de señal excitado en un ciclo apagado se descarta (adelgazamiento
    exacto de Poisson): queda como "fantasma" (arr = inf, src = -2) que nunca se registra. No
    cambia las extracciones del generador aleatorio (con ``mask`` = None o todo 1 el resultado es
    idéntico bit a bit).
    """
    R = t0.size
    gaps = rng.exponential(p.T / p.rate_per_cycle, size=(R, n))
    base = t0[:, None] + np.cumsum(gaps, axis=1)
    cyc = np.floor(base / p.T)
    if fs >= 1.0:
        is_sig = np.ones((R, n), dtype=bool)
    elif fs <= 0.0:
        is_sig = np.zeros((R, n), dtype=bool)
    else:
        is_sig = rng.random((R, n)) < fs
    cq = np.cumsum(q, axis=1)[:, :-1]                     # (R, K-1)
    u = rng.random((R, n))
    beam = (u[:, :, None] >= cq[:, None, :]).sum(axis=2).astype(np.int64)
    X = rng.exponential(p.tau, size=(R, n))
    if sigma:
        X += rng.normal(0.0, sigma, size=(R, n))
    dt = p.T / p.K
    arr = np.where(is_sig, cyc * p.T + beam * dt + X, base)
    src = np.where(is_sig, beam, -1)
    if mask is not None:
        off = is_sig & ~mask[np.mod(cyc.astype(np.int64), mask.size)]
        if np.any(off):
            arr[off] = np.inf
            src[off] = -2
    return _Raw(base, arr, src, cyc)


def _concat(r1, r2):
    return _Raw(*(np.concatenate([getattr(r1, f), getattr(r2, f)], axis=1) for f in _Raw.__slots__))


def _take_rows(r, idx):
    return _Raw(*(getattr(r, f)[idx] for f in _Raw.__slots__))


def _recorded_highest(raw, K):
    """Máscara de registro de sim_exp: 1 por ranura, gana el haz de k más alto; fondo aparte."""
    R, n = raw.src.shape
    sig = raw.src >= 0
    rec = ~sig                                           # el fondo siempre se registra
    rows, cols = np.nonzero(sig)                         # orden fila-mayor; ciclo no decreciente
    if rows.size == 0:
        return rec
    cyc = raw.cyc[rows, cols].astype(np.int64)
    beam = raw.src[rows, cols]
    span = int(cyc.max()) + 2
    g = rows.astype(np.int64) * span + cyc
    starts = np.r_[0, np.nonzero(np.diff(g))[0] + 1]
    gid = np.cumsum(np.r_[False, np.diff(g) != 0])
    gmax = np.maximum.reduceat(beam, starts)[gid]
    cand = beam == gmax
    cs = np.cumsum(cand)
    before = np.r_[0, cs][starts][gid]                   # candidatos antes del grupo
    first = cand & ((cs - before) == 1)
    rec[rows[first], cols[first]] = True
    return rec


def _recorded_earliest(arr_sorted, T, dead):
    """SPAD no paralizable (tiempo muerto abarca ciclos) + TCSPC 1ra avalancha por ciclo."""
    R, n = arr_sorted.shape
    ninf = np.full((R, 1), -np.inf)
    aval = np.ones((R, n), dtype=bool)
    with np.errstate(invalid="ignore"):          # fotones fantasma (t_mask): inf - inf
        return _earliest_loop(arr_sorted, T, dead, ninf, aval, n)


def _earliest_loop(arr_sorted, T, dead, ninf, aval, n):
    """Punto fijo del tiempo muerto (vectorizado; O(n) pasadas en el peor caso, 2-4 en tracking)."""
    prev = None
    for _ in range(n + 1):
        at = np.where(aval, arr_sorted, -np.inf)
        prev = np.concatenate([ninf, np.maximum.accumulate(at, axis=1)[:, :-1]], axis=1)
        if dead <= 0:
            break
        new = (arr_sorted - prev) >= dead
        if np.array_equal(new, aval):
            break
        aval = new
    cyc = np.floor(arr_sorted / T)
    with np.errstate(invalid="ignore"):
        pcyc = np.floor(prev / T)
    return aval & (cyc != pcyc)


def _process(raw, p, sigma):
    """Ordena por llegada y marca registrados; devuelve (arr, src, rec, t_cut) ordenados."""
    if p.tcspc == "highest":
        rec = _recorded_highest(raw, p.K)
    order = np.argsort(raw.arr, axis=1, kind="stable")
    arr = np.take_along_axis(raw.arr, order, axis=1)
    src = np.take_along_axis(raw.src, order, axis=1)
    if p.tcspc == "highest":
        rec = np.take_along_axis(rec, order, axis=1)
    elif p.tcspc == "earliest":
        rec = _recorded_earliest(arr, p.T, p.dead_time)
    else:
        rec = np.ones(arr.shape, dtype=bool)
    t_cut = np.floor(raw.base[:, -1] / p.T) * p.T - _IRF_CUT_SIGMAS * (sigma or 0.0)
    rec &= arr < t_cut[:, None]
    return arr, src, rec


def _efficiency_guess(p, fs):
    r = p.rate_per_cycle
    if p.tcspc == "none":
        return 1.0
    if p.tcspc == "highest":
        return 1.0 / (1.0 + 0.5 * r * fs)
    return 1.0 / (1.0 + r * (0.5 + p.dead_time / p.T))


def _pad(x, width, fill):
    if x.shape[1] >= width:
        return x
    return np.concatenate([x, np.full((x.shape[0], width - x.shape[1]), fill, dtype=x.dtype)], axis=1)


def _run_rows(rng, raw, q, Nrow, p, fs, sigma, extra, mask=None):
    """Procesa filas; las que no llegan a N detecciones se extienden (el proceso continúa)."""
    arr, src, rec = _process(raw, p, sigma)
    short = np.nonzero(rec.sum(axis=1) < Nrow)[0]
    if short.size:
        sub = _take_rows(raw, short)
        add = _generate(rng, sub.base[:, -1].copy(), extra, q[short], p, fs, sigma, mask)
        a2, s2, r2 = _run_rows(rng, _concat(sub, add), q[short], Nrow[short], p, fs, sigma,
                               2 * extra, mask)
        w = a2.shape[1]
        arr, src, rec = _pad(arr, w, np.inf), _pad(src, w, -2), _pad(rec, w, False)
        arr[short], src[short], rec[short] = a2, s2, r2
    return arr, src, rec


def _simulate_block(rng, q, Nrow, p, fs, sigma, mask=None):
    """Filas de un bloque: devuelve arr, src, take (máscara de las primeras N detecciones)."""
    R = q.shape[0]
    Nmax = int(Nrow.max())
    eff = _efficiency_guess(p, fs)
    if mask is not None:
        eff *= max(fs * float(mask.mean()) + (1.0 - fs), 1e-3)
    n0 = int(math.ceil(Nmax / eff * 1.02 + 6.0 * math.sqrt(Nmax + 1) + 8))
    raw = _generate(rng, np.zeros(R), n0, q, p, fs, sigma, mask)
    arr, src, rec = _run_rows(rng, raw, q, Nrow, p, fs, sigma, max(64, n0 // 4), mask)
    rank = np.cumsum(rec, axis=1)
    take = rec & (rank <= Nrow[:, None])
    return arr, src, take


def simulate_counts(lambda_beams, n_loc, N, sbr, params=None, rng=None, return_tags=False,
                    t_mask=None, sbr_reference="on"):
    """Simula ``n_loc`` localizaciones p-MINFLUX y devuelve los conteos por ventana.

    lambda_beams: (K,) o (n_loc, K), excitación relativa (se normaliza por localización después de
        multiplicar por ``beam_powers``).
    N: fotones detectados por localización (señal+fondo, ciclo completo, después de TCSPC y tiempo
        muerto); la media si ``n_mode='poisson'``.
    sbr: Ns/Nb de los fotones INCIDENTES en el ciclo completo (``inf`` = sin fondo, ``0`` = solo
        fondo). A tasa baja coincide con la razón de los detectados.
    params: ``SimParams`` (por defecto ``SimParams()``; ``dead_time`` = 22 ns es un SUPUESTO).
    rng: ``np.random.Generator`` (obligatorio para reproducir; None = semilla del sistema).

    Devuelve ``counts`` (n_loc, K) int64. Con ``return_tags=True`` devuelve ``(counts, tags)``;
    ``tags`` = dict de arrays planos de los fotones registrados, en orden de llegada por
    localización: ``loc``, ``cycle`` (ciclo de llegada), ``microtime_ns`` en [0, T), ``source``
    (índice de haz, o -1 para el fondo).

    t_mask: None (emisor siempre encendido) o array (M,) de 0/1 (bool): parpadeo del emisor por
        ciclo, contado desde el ciclo 0 de cada localización y con extensión periódica
        ``t_mask[ciclo % M]`` (la simulación corre hasta la N-ésima detección, así que el número de
        ciclos no está fijo). En un ciclo apagado no hay fotones de SEÑAL; el fondo sigue igual
        (port de F107: en el legado ``sim_exp('p_minflux')`` ignoraba la máscara). La tasa
        ``rate_per_cycle`` se refiere a los ciclos encendidos; ``sbr``, según ``sbr_reference``.
    sbr_reference: con ``t_mask``, a qué ciclos se refiere ``sbr``. ``"on"`` (default): Ns/Nb de
        los ciclos ENCENDIDOS; el SBR detectado del conjunto baja con la fracción encendida f_on
        (SBR efectivo ~ sbr * f_on; con f_on = 0.5 y sbr = 21 sale ~10.5 y hay que pasarle ese
        valor, o ``free_bg='shared'``, al estimador). ``"total"``: ``sbr`` = Ns/Nb del conjunto
        de ciclos (lo que hacía el legado, que fijaba Ns y Nb): internamente se usa
        ``sbr/f_on`` en los ciclos encendidos, con ``f_on = mean(t_mask)`` (exacto si el número
        de ciclos simulados es múltiplo de ``len(t_mask)``, aproximado si no). Sin ``t_mask`` las
        dos opciones son idénticas.
    """
    p = params if params is not None else SimParams()
    _check(p)
    mask = None
    if t_mask is not None:
        tm = np.asarray(t_mask)
        if tm.ndim != 1 or tm.size == 0:
            raise ValueError("t_mask debe ser un array 1D no vacío (un valor por ciclo)")
        if tm.dtype != bool:
            if not np.all(np.isin(tm, (0, 1))):
                raise ValueError("t_mask debe ser 0/1 o bool")
            tm = tm.astype(bool)
        if not tm.any() and sbr is not None and math.isinf(float(sbr)):
            raise ValueError("t_mask todo apagado y sin fondo: no hay fotones que detectar")
        mask = tm
    if sbr_reference not in ("on", "total"):
        raise ValueError("sbr_reference debe ser 'on' o 'total'")
    if sbr_reference == "total" and mask is not None and sbr is not None             and not math.isinf(float(sbr)) and float(sbr) > 0:
        f_on = float(mask.mean())
        if f_on <= 0.0:
            raise ValueError("t_mask todo apagado: no hay señal para un sbr total > 0")
        sbr = float(sbr) / f_on
    if rng is None:
        rng = np.random.default_rng()
    elif not isinstance(rng, np.random.Generator):
        rng = np.random.default_rng(rng)
    n_loc = int(n_loc)
    if n_loc < 0:
        raise ValueError("n_loc debe ser >= 0")
    if not (N >= 0) or (p.n_mode == "fixed" and int(N) != N):
        raise ValueError("N debe ser >= 0 (entero si n_mode='fixed')")
    if sbr is None or sbr < 0 or (isinstance(sbr, float) and math.isnan(sbr)):
        raise ValueError("sbr debe ser >= 0 (inf = sin fondo)")
    K = int(p.K)
    q = _beam_probs(lambda_beams, n_loc, K, p.beam_powers)
    fs = 1.0 if math.isinf(sbr) else float(sbr) / (float(sbr) + 1.0)
    sigma = p.irf_fwhm * _FWHM_TO_SIGMA if p.irf_fwhm else 0.0
    if p.n_mode == "fixed":
        Nall = np.full(n_loc, int(N), dtype=np.int64)
    else:
        Nall = rng.poisson(float(N), size=n_loc).astype(np.int64)

    counts = np.zeros((n_loc, K), dtype=np.int64)
    tags = {"loc": [], "cycle": [], "microtime_ns": [], "source": []} if return_tags else None
    dt = p.T / K
    Nmax = int(Nall.max()) if n_loc else 0
    rows_per = max(1, int(_CHUNK_ELEMS // max(1, int(Nmax * 1.1) + 16)))
    for s0 in range(0, n_loc, rows_per):
        s1 = min(n_loc, s0 + rows_per)
        Nrow = Nall[s0:s1]
        if Nrow.max() == 0:
            continue
        arr, src, take = _simulate_block(rng, q[s0:s1], Nrow, p, fs, sigma, mask)
        R = s1 - s0
        rr, cc = np.nonzero(take)                          # fila-mayor = orden de llegada
        at = arr[rr, cc]
        cyc = np.floor(at / p.T)
        micro = at - cyc * p.T
        micro[micro >= p.T] -= p.T                          # redondeo: microtiempo en [0, T)
        micro[micro < 0] = 0.0
        if p.counting == "periodic":
            masks = window_masks(micro, p.T, K, p.a, p.b)   # = windows.count_windows
            for i in range(K):
                counts[s0:s1, i] = np.bincount(rr[masks[i]], minlength=R)
        else:
            ndet = np.bincount(rr, minlength=R)
            last_idx = np.cumsum(ndet) - 1
            ncyc = np.zeros(R, dtype=np.int64)
            ok = ndet > 0
            ncyc[ok] = cyc[last_idx[ok]].astype(np.int64) + 1
            nsig = np.bincount(rr[src[rr, cc] >= 0], minlength=R)
            zeros = np.maximum(ncyc - nsig, 0)
            for i in range(K):
                ti, tf = i * dt + p.a, i * dt + p.a + p.b
                inw = (micro > ti) & (micro < tf)
                counts[s0:s1, i] = np.bincount(rr[inw], minlength=R) + (zeros if (ti < 0.0 < tf) else 0)
        if return_tags:
            tags["loc"].append(rr + s0)
            tags["cycle"].append(cyc.astype(np.int64))
            tags["microtime_ns"].append(micro)
            tags["source"].append(src[rr, cc].astype(np.int64))
    if not return_tags:
        return counts
    tags = {k: (np.concatenate(v) if v else np.zeros(0, dtype=(float if k == "microtime_ns" else np.int64)))
            for k, v in tags.items()}
    return counts, tags
