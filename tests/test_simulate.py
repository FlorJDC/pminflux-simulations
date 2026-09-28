# -*- coding: utf-8 -*-
"""Tests de pminflux_sim.simulate (simulador en dominio temporal) contra el modelo verificado
``pminflux_sim.mixing`` y contra los números verificados de F101-F103/F201 (state.json, R1).

Todas las semillas son fijas. Cada test imprime su p-valor / número de fotones.
"""

import math
import os
import sys
import time
import unittest
import warnings

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pminflux_sim import mixing as mx  # noqa: E402
from pminflux_sim import simulate as sm  # noqa: E402

T, K = 50.0, 4
DT = T / K
SBR21 = 2000.0 / 95.0
LAM4 = np.array([0.4, 0.1, 0.2, 0.3])

# Geometría TCP K = 4 del legado (beams(center=True), L = 100 nm, dona fwhm 360 nm), la misma de F104.
_ang = 2 * np.pi * np.arange(1, 4) / 3
POS = np.vstack([[0.0, 0.0], np.c_[50.0 * np.cos(_ang), 50.0 * np.sin(_ang)]])


def lam_at(x, y, fwhm=360.0):
    u = 4 * np.log(2) * ((x - POS[:, 0]) ** 2 + (y - POS[:, 1]) ** 2) / fwhm ** 2
    lam = u * np.exp(-u)
    return lam / lam.sum()


LAM55 = lam_at(5.0, -5.0)


def _log(name, **kw):
    print("\n[%s] %s" % (name, ", ".join("%s=%s" % (k, v) for k, v in kw.items())))


def _rng(seed):
    return np.random.default_rng(seed)


def _finite_rate(lam, rate, tau, a, b, irf, rule, M_p=1e7):
    return mx.sim_exp_window_probs(lam, 1.0, 0.0, rate * M_p, M_p, tau, T, K, a, b,
                                   rule=rule, irf_fwhm=irf)


class TestSimulateMixing(unittest.TestCase):

    def test_low_rate_matches_mixing_window_probs(self):
        # A 1e-3 fotones/ciclo el simulador (TCSPC real, tiempo muerto 22 ns, fondo compitiendo)
        # coincide con el modelo de mezcla y rechaza el ingenuo (Ec. 3.5, F104).
        cases = [("earliest", 0.3, LAM55, 11), ("earliest", 0.0, LAM55, 12),
                 ("none", 0.3, LAM4, 13), ("earliest", 0.3, LAM4, 14)]
        for tcspc, irf, lam, seed in cases:
            p = sm.SimParams(irf_fwhm=irf, rate_per_cycle=1e-3, tcspc=tcspc)
            c = sm.simulate_counts(lam, 600, 2095, SBR21, p, _rng(seed))
            o = c.sum(axis=0)
            C = mx.mixing_matrix(p.tau, T, K, p.a, p.b, irf)
            pm = mx.window_probs(lam, C, p.b, T, Ns=2000.0, Nb=95.0)
            _, _, pv, dev = mx.pearson_chi2(o, pm)
            _, _, pn, _ = mx.pearson_chi2(o, mx.naive_probs(lam, SBR21))
            _log("low_rate", tcspc=tcspc, irf=irf, photons_in_windows=int(o.sum()),
                 p_mixing="%.3g" % pv, p_naive="%.3g" % pn, dev_se=np.round(dev, 2).tolist())
            self.assertGreater(o.sum(), 1.0e6)
            self.assertGreater(pv, 1e-3)
            self.assertLess(pn, 1e-10)

    def test_irf_negative_start_and_wrap(self):
        # Ventanas periódicas: a < 0 (la ventana 0 toma el final del ciclo) y ventana que cruza T.
        for a, b, seed in [(-0.5, 10.1, 24), (2.0, 12.0, 22), (-1.5, 12.5, 23)]:
            p = sm.SimParams(irf_fwhm=0.3, a=a, b=b, rate_per_cycle=1e-3)
            c, tags = sm.simulate_counts(LAM55, 500, 2095, SBR21, p, _rng(seed), return_tags=True)
            o = c.sum(axis=0)
            C = mx.mixing_matrix(p.tau, T, K, a, b, 0.3)
            _, _, pv, dev = mx.pearson_chi2(o, mx.window_probs(LAM55, C, b, T, Ns=2000.0, Nb=95.0))
            _log("irf_wrap", a=a, b=b, photons_in_windows=int(o.sum()), p_mixing="%.3g" % pv,
                 dev_se=np.round(dev, 2).tolist())
            self.assertGreater(pv, 1e-3)
            m = tags["microtime_ns"]
            if a < 0:
                # la ventana 0 recibe fotones del final del ciclo (plegado), incluida la IRF del haz 0
                n_tail = np.sum(m >= T + a)
                self.assertGreater(n_tail, 0)
                sig0 = (tags["source"] == 0) & (m >= T + a)
                self.assertGreater(np.sum(sig0), 0)       # IRF: fotones del haz 0 antes del pulso
            if (K - 1) * DT + a + b > T:
                self.assertGreater(np.sum(m < (K - 1) * DT + a + b - T), 0)
            # la cuenta periódica recalculada desde los tags coincide exactamente
            for i in range(K):
                inw = np.mod(m - i * DT - a, T) < b
                self.assertEqual(int(np.sum(inw)), int(o[i]))


class TestSimulateLegacy(unittest.TestCase):

    def test_highest_overwrite_emulation(self):
        # F101 "antes": 'highest' reproduce el predictor exacto de sim_exp a 0.3/ciclo.
        for irf, seed in [(0.3, 31), (0.0, 32)]:
            rate = 0.3
            p = sm.SimParams(tcspc="highest", rate_per_cycle=rate, irf_fwhm=irf)
            c = sm.simulate_counts(LAM4, 600, 2000, math.inf, p, _rng(seed))
            o = c.sum(axis=0)
            ph = _finite_rate(LAM4, rate, p.tau, p.a, p.b, irf, "highest")
            pe = _finite_rate(LAM4, rate, p.tau, p.a, p.b, irf, "earliest")
            pi = _finite_rate(LAM4, rate, p.tau, p.a, p.b, irf, "ideal")
            _, _, pv, dev = mx.pearson_chi2(o, ph)
            _log("highest", irf=irf, rate=rate, photons_in_windows=int(o.sum()),
                 p_highest="%.3g" % pv, p_ideal="%.3g" % mx.pearson_chi2(o, pi)[2],
                 p_earliest="%.3g" % mx.pearson_chi2(o, pe)[2], dev_se=np.round(dev, 2).tolist())
            self.assertGreater(pv, 1e-3)
            self.assertLess(mx.pearson_chi2(o, pi)[2], 1e-10)
            self.assertLess(mx.pearson_chi2(o, pe)[2], 1e-10)

    def test_legacy_counting_zeros_in_window0(self):
        # F102: con counting='legacy' los ciclos vacíos entran como 0.0; con a = -0.25 inflan la
        # ventana 0; con a = 0 la desigualdad estricta los excluye; en 'periodic' no pasa nada.
        rate, N = 0.0105, 2095
        base = dict(tcspc="highest", rate_per_cycle=rate, irf_fwhm=0.0, b=12.5)
        pl = sm.SimParams(counting="legacy", a=-0.25, **base)
        c, tags = sm.simulate_counts(LAM55, 200, N, SBR21, pl, _rng(41), return_tags=True)
        m, loc, cyc, src = tags["microtime_ns"], tags["loc"], tags["cycle"], tags["source"]
        # ceros esperados = ciclos hasta la última detección - detecciones de señal (como sim_exp)
        last = cyc[np.cumsum(np.bincount(loc, minlength=200)) - 1]      # tags en orden de llegada
        nsig = np.bincount(loc[src >= 0], minlength=200)
        zeros = last + 1 - nsig
        strict0 = np.bincount(loc[(m > -0.25) & (m < 12.25)], minlength=200)
        np.testing.assert_array_equal(c[:, 0], strict0 + zeros)
        frac0 = c[:, 0].sum() / c.sum()
        # zeros por localización ~ N/tasa_detectada - Ns (en el legado: 198000 de 200095)
        _log("legacy_zeros", mean_zeros=float(zeros.mean()), frac_window0=round(float(frac0), 4))
        self.assertGreater(zeros.mean(), 0.8 * N / rate - N)
        self.assertGreater(frac0, 0.98)
        # a = 0: sin inflar; coincide con la cuenta periódica (ninguna ventana cruza T)
        for counting, a, seed in [("legacy", 0.0, 42), ("periodic", -0.25, 43)]:
            p = sm.SimParams(counting=counting, a=a, **base)
            o = sm.simulate_counts(LAM55, 300, N, SBR21, p, _rng(seed)).sum(axis=0)
            M = 1e7
            pr = mx.sim_exp_window_probs(LAM55, 2000.0, 95.0, rate * SBR21 / (SBR21 + 1) * M, M,
                                         p.tau, T, K, a, 12.5, rule="highest")
            _, _, pv, _ = mx.pearson_chi2(o, pr)
            _log("legacy_zeros_ctrl", counting=counting, a=a, photons=int(o.sum()), p_mixing="%.3g" % pv)
            self.assertGreater(pv, 1e-3)

    def test_legacy_counting_non_periodic(self):
        # F103: nMINFLUX no pliega ni controla solapamiento. Números verificados (R1, verifier A):
        #   b = 13: cuenta dos veces 10.9 % (tau = 4.21, MC de sim_exp) / 94.9 % (tau = 0.001);
        #   a = -0.5, b = 12.5: la ventana 0 pierde 6.84 % (4.21) / 2.54 % (0.001) (esperado).
        # El 10.9 % del verificador es un MC de 62850 fotones (SE 0.12 puntos); el valor esperado
        # analítico es 11.175 % (cuadratura 0.111746, verificador R2): se usa ese con tolerancia de MC.
        # b = 13 > T/K solapa ventanas: hace falta allow_overlap=True (avisa con warnings.warn).
        for tau, dbl_ref, loss_ref, seed in [(4.21, 0.11175, 0.0684, 51), (0.001, 0.949, 0.0254, 52)]:
            common = dict(tau=tau, irf_fwhm=0.0, tcspc="none", rate_per_cycle=0.0105)
            p = sm.SimParams(counting="legacy", a=0.0, b=13.0, allow_overlap=True, **common)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                c, tags = sm.simulate_counts(LAM55, 400, 2095, SBR21, p, _rng(seed), return_tags=True)
            self.assertTrue(any("ventanas solapadas" in str(x.message) for x in w))
            n = tags["microtime_ns"].size
            dbl = c.sum() / n - 1.0          # a = 0: los ceros no entran (desigualdad estricta)
            se = math.sqrt(dbl * (1 - dbl) / n)
            # periodic con el mismo b = 13 también cuenta dos veces (se solapa), pero pliega
            _log("legacy_b13", tau=tau, photons=n, double=round(dbl, 5), ref=dbl_ref, se=round(se, 5))
            self.assertLess(abs(dbl - dbl_ref), 4 * se + 1e-3)
            # pérdida de la ventana 0 con a = -0.5, b = 12.5 (sin los ceros de F102)
            pl = sm.SimParams(counting="legacy", a=-0.5, b=12.5, **common)
            pp = sm.SimParams(counting="periodic", a=-0.5, b=12.5, **common)
            cl, tl = sm.simulate_counts(LAM55, 2000, 2095, SBR21, pl, _rng(seed + 10), return_tags=True)
            cp, tp = sm.simulate_counts(LAM55, 2000, 2095, SBR21, pp, _rng(seed + 10), return_tags=True)
            np.testing.assert_array_equal(tl["microtime_ns"], tp["microtime_ns"])   # misma realización
            m, loc, cyc, src = tl["microtime_ns"], tl["loc"], tl["cycle"], tl["source"]
            last = cyc[np.cumsum(np.bincount(loc, minlength=2000)) - 1]   # tags en orden de llegada
            zeros = last + 1 - np.bincount(loc[src >= 0], minlength=2000)
            leg0 = cl[:, 0].sum() - zeros.sum()
            per0 = cp[:, 0].sum()
            loss = 1.0 - leg0 / per0
            se_l = math.sqrt(loss * (1 - loss) / per0)
            _log("legacy_loss_w0", tau=tau, window0_periodic=int(per0), loss=round(loss, 5),
                 ref=loss_ref, se=round(se_l, 5))
            self.assertLess(abs(loss - loss_ref), 4 * se_l)
            # lo perdido es exactamente lo que cae en (T - 0.5, T), que la ventana legado no pliega
            self.assertEqual(int(per0 - leg0), int(np.sum(m > T - 0.5)))

    def test_short_lifetime_turns_off_leakage(self):
        # F201: con Tlife = 0.001 y b = 12.5 (los estudios) C ~ I y los conteos siguen a lambda
        # (modelo ingenuo exacto); con tau = 4.21 aparece la fuga y el ingenuo se rechaza.
        C = mx.mixing_matrix(0.001, T, K, 0.0, 12.5)
        self.assertLess(np.abs(C - np.eye(K)).max(), 1e-12)
        res = {}
        for tau, seed in [(0.001, 61), (4.21, 62)]:
            p = sm.SimParams(tau=tau, irf_fwhm=0.0, a=0.0, b=12.5, rate_per_cycle=1e-3)
            o = sm.simulate_counts(LAM55, 600, 2095, SBR21, p, _rng(seed)).sum(axis=0)
            res[tau] = mx.pearson_chi2(o, mx.naive_probs(LAM55, SBR21))[2]
            _log("short_tau", tau=tau, photons=int(o.sum()), p_naive="%.3g" % res[tau])
        self.assertGreater(res[0.001], 1e-3)
        self.assertLess(res[4.21], 1e-10)


class TestSimulateTCSPC(unittest.TestCase):

    def test_earliest_matches_mixing_predictor(self):
        # F101 "después": TCSPC real de primer fotón (dead_time = 0) contra el predictor 'earliest'.
        # El predictor de mixing compite solo dentro del ciclo de EXCITACIÓN; el simulador compite
        # en el ciclo de LLEGADA (un fotón del haz 3 que fuga al ciclo siguiente compite allí). Esa
        # diferencia es de orden tasa x fuga entre ciclos, así que el acuerdo exacto se prueba con
        # tau corto (fuga entre ciclos ~ exp(-12.5/tau)) y sin IRF; con tau = 4.21 se documenta.
        for tau, rate, seed in [(1.5, 0.3, 71), (1.0, 0.2, 72)]:
            p = sm.SimParams(tau=tau, irf_fwhm=0.0, dead_time=0.0, rate_per_cycle=rate)
            o = sm.simulate_counts(LAM4, 600, 2000, math.inf, p, _rng(seed)).sum(axis=0)
            pe = _finite_rate(LAM4, rate, tau, p.a, p.b, 0.0, "earliest")
            ph = _finite_rate(LAM4, rate, tau, p.a, p.b, 0.0, "highest")
            pi = _finite_rate(LAM4, rate, tau, p.a, p.b, 0.0, "ideal")
            _, _, pv, dev = mx.pearson_chi2(o, pe)
            _log("earliest", tau=tau, rate=rate, photons=int(o.sum()), p_earliest="%.3g" % pv,
                 p_highest="%.3g" % mx.pearson_chi2(o, ph)[2], p_ideal="%.3g" % mx.pearson_chi2(o, pi)[2],
                 dev_se=np.round(dev, 2).tolist())
            self.assertGreater(pv, 1e-3)
            self.assertLess(mx.pearson_chi2(o, ph)[2], 1e-10)
            self.assertLess(mx.pearson_chi2(o, pi)[2], 1e-10)
            # signo del sesgo 'earliest' (MIX-EARLIEST): favorece a los haces tempranos
            self.assertGreater(o[0] / o.sum(), pi[0])
        # tau = 4.21 a 0.1/ciclo: diferencia medible y chica respecto del predictor (competencia
        # entre ciclos); se registra la magnitud (|dif| < 2e-3 en fracción).
        p = sm.SimParams(irf_fwhm=0.0, dead_time=0.0, rate_per_cycle=0.1)
        o = sm.simulate_counts(LAM4, 600, 2000, math.inf, p, _rng(73)).sum(axis=0)
        pe = _finite_rate(LAM4, 0.1, p.tau, p.a, p.b, 0.0, "earliest")
        diff = o / o.sum() - pe
        _log("earliest_tau421", rate=0.1, diff=np.round(diff, 5).tolist())
        self.assertLess(np.abs(diff).max(), 2e-3)

    def test_dead_time_spanning_cycles(self):
        # Fondo solo (proceso de Poisson uniforme, rho = rate/T por ns). Con dead_time d > T todo
        # avalancha es primera de su ciclo y el proceso registrado es de renovación con
        # intervalos d + Exp(1/rho): media d + T/rate y tasa rho/(1 + rho d) (no paralizable).
        rate = 0.3
        for d, seed in [(120.0, 81), (60.0, 82)]:
            p = sm.SimParams(dead_time=d, rate_per_cycle=rate, a=0.0, b=12.5)
            c, tags = sm.simulate_counts(LAM4, 100, 2000, 0.0, p, _rng(seed), return_tags=True)
            t = tags["cycle"] * T + tags["microtime_ns"]
            loc = tags["loc"]
            gaps = np.diff(t)[np.diff(loc) == 0]
            self.assertGreaterEqual(gaps.min(), d - 1e-6)
            excess = gaps - d
            ks = stats.kstest(excess, "expon", args=(0, T / rate))
            _log("dead_time", d=d, n_gaps=gaps.size, mean_gap=round(float(gaps.mean()), 3),
                 expected=round(d + T / rate, 3), ks_p="%.3g" % ks.pvalue)
            self.assertLess(abs(gaps.mean() - (d + T / rate)) / (T / rate / math.sqrt(gaps.size)), 4)
            self.assertGreater(ks.pvalue, 1e-3)
        # d < T: nunca dos registros en el mismo ciclo, separaciones >= d, y la regla abarca el
        # borde del ciclo (hay pares con registro al final de un ciclo y bloqueo al comienzo del
        # siguiente: la separación mínima entre ciclos consecutivos es >= d).
        d = 22.0
        p = sm.SimParams(dead_time=d, rate_per_cycle=rate)
        _, tags = sm.simulate_counts(LAM4, 100, 2000, 1.0, p, _rng(83), return_tags=True)
        t = tags["cycle"] * T + tags["microtime_ns"]
        same = np.diff(tags["loc"]) == 0
        gaps = np.diff(t)[same]
        self.assertGreaterEqual(gaps.min(), d - 1e-6)
        self.assertTrue(np.all(np.diff(tags["cycle"])[same] >= 1))
        consec = (np.diff(tags["cycle"])[same] == 1)
        self.assertGreater(consec.sum(), 0)
        self.assertGreaterEqual(gaps[consec].min(), d - 1e-6)
        # Sin tiempo muerto el mínimo entre ciclos consecutivos sí baja de d (control)
        p0 = sm.SimParams(dead_time=0.0, rate_per_cycle=rate)
        _, t0 = sm.simulate_counts(LAM4, 100, 2000, 1.0, p0, _rng(83), return_tags=True)
        tt = t0["cycle"] * T + t0["microtime_ns"]
        s0 = np.diff(t0["loc"]) == 0
        self.assertLess(np.diff(tt)[s0].min(), d)


class TestSimulateBackground(unittest.TestCase):

    def test_background_uniform_b_over_T(self):
        # Solo fondo: cada ventana recibe la fracción b/T de los detectados (también plegada/cruzando T).
        for a, b, seed in [(0.0, 10.1, 91), (-3.0, 15.0, 92), (4.0, 12.5, 93)]:
            # b = 15 > T/K solapa ventanas (R3: requiere allow_overlap=True, que avisa)
            p = sm.SimParams(a=a, b=b, rate_per_cycle=1e-3, allow_overlap=b > DT)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                c = sm.simulate_counts(LAM4, 250, 2000, 0.0, p, _rng(seed))
            n = 250 * 2000
            f = c.sum(axis=0) / n
            z = (f - b / T) / math.sqrt((b / T) * (1 - b / T) / n)
            _log("background", a=a, b=b, photons=n, z=np.round(z, 2).tolist())
            self.assertLess(np.abs(z).max(), 4.0)
        # fondo + señal (SBR 1): conteos contra window_probs con Ns = Nb
        p = sm.SimParams(rate_per_cycle=1e-3)
        o = sm.simulate_counts(LAM55, 500, 2000, 1.0, p, _rng(94)).sum(axis=0)
        C = mx.mixing_matrix(p.tau, T, K, p.a, p.b, p.irf_fwhm)
        pv = mx.pearson_chi2(o, mx.window_probs(LAM55, C, p.b, T, sbr=1.0))[2]
        _log("background_sbr1", photons=int(o.sum()), p_mixing="%.3g" % pv)
        self.assertGreater(pv, 1e-3)


class TestSimulateN(unittest.TestCase):

    def test_fixed_and_poisson_N(self):
        # Ventanas que parten el ciclo (a = 0, b = T/K): suma por localización = N detectados.
        N, n_loc = 200, 5000
        p = sm.SimParams(a=0.0, b=DT, rate_per_cycle=2.5e-3)
        c = sm.simulate_counts(LAM55, n_loc, N, SBR21, p, _rng(101))
        self.assertTrue(np.all(c.sum(axis=1) == N))
        # varianza multinomial por ventana: N p (1 - p)
        pm = c.sum(axis=0) / c.sum()
        v = c.var(axis=0, ddof=1)
        se_rel = math.sqrt(2.0 / (n_loc - 1))
        rel = v / (N * pm * (1 - pm)) - 1
        _log("fixed", var_rel_dev=np.round(rel, 3).tolist(), se_rel=round(se_rel, 3))
        self.assertLess(np.abs(rel).max(), 4 * se_rel + 0.01)
        pp = sm.SimParams(a=0.0, b=DT, rate_per_cycle=2.5e-3, n_mode="poisson")
        cp = sm.simulate_counts(LAM55, n_loc, N, SBR21, pp, _rng(102))
        tot = cp.sum(axis=1)
        self.assertLess(abs(tot.mean() - N) / math.sqrt(N / n_loc), 4)
        self.assertLess(abs(tot.var(ddof=1) / N - 1), 4 * se_rel)
        # Poisson: varianza por ventana = N p (sin el factor 1 - p)
        pm2 = cp.sum(axis=0) / cp.sum()
        rel2 = cp.var(axis=0, ddof=1) / (N * pm2) - 1
        _log("poisson", mean=float(tot.mean()), var=float(tot.var(ddof=1)), var_rel_dev=np.round(rel2, 3).tolist())
        self.assertLess(np.abs(rel2).max(), 4 * se_rel + 0.01)
        # Poisson con N = 0 en algunas filas: sin fallas y conteos cero
        c0 = sm.simulate_counts(LAM55, 50, 0.5, SBR21, pp, _rng(103))
        self.assertEqual(c0.shape, (50, K))


class TestSimulateAPI(unittest.TestCase):

    def test_shapes_seed_and_validation(self):
        p = sm.SimParams()
        self.assertEqual(p.dead_time, 22.0)                       # SUPUESTO declarado
        self.assertIn("SUPUESTO", sm.DEAD_TIME_ASSUMPTION)
        c1 = sm.simulate_counts(LAM55, 7, 300, SBR21, p, _rng(5))
        c2 = sm.simulate_counts(LAM55, 7, 300, SBR21, p, _rng(5))
        self.assertEqual(c1.dtype, np.int64)
        self.assertEqual(c1.shape, (7, K))
        np.testing.assert_array_equal(c1, c2)
        # lambda por localización y tags coherentes
        lam2 = np.vstack([LAM4, LAM55, LAM4])
        c, tags = sm.simulate_counts(lam2, 3, 100, math.inf, sm.SimParams(a=0.0, b=DT), _rng(6),
                                     return_tags=True)
        self.assertEqual(set(tags), {"loc", "cycle", "microtime_ns", "source"})
        np.testing.assert_array_equal(np.bincount(tags["loc"], minlength=3), [100, 100, 100])
        self.assertTrue(np.all((tags["microtime_ns"] >= 0) & (tags["microtime_ns"] < T)))
        self.assertTrue(np.all(tags["source"] >= 0))              # sbr = inf: sin fondo
        np.testing.assert_array_equal(c.sum(axis=1), [100, 100, 100])
        for bad in [dict(tcspc="x"), dict(counting="x"), dict(n_mode="x"), dict(b=0.0),
                    dict(b=60.0), dict(dead_time=-1.0), dict(rate_per_cycle=0.0), dict(tau=0.0)]:
            with self.assertRaises(ValueError):
                sm.simulate_counts(LAM4, 2, 10, 5.0, sm.SimParams(**bad), _rng(1))
        with self.assertRaises(ValueError):
            sm.simulate_counts(np.ones(3), 2, 10, 5.0, p, _rng(1))
        with self.assertRaises(ValueError):
            sm.simulate_counts(np.zeros(4), 2, 10, 5.0, p, _rng(1))
        with self.assertRaises(ValueError):
            sm.simulate_counts(LAM4, 2, 10, -1.0, p, _rng(1))

    def test_beam_powers_multiply_lambda(self):
        # F202: las potencias multiplican lambda antes de normalizar.
        pw = np.array([21.02, 16.65, 22.96, 22.86])
        p = sm.SimParams(beam_powers=pw, rate_per_cycle=1e-3, irf_fwhm=0.0, tau=0.001, b=12.5)
        o = sm.simulate_counts(LAM55, 300, 2000, math.inf, p, _rng(7)).sum(axis=0)
        q = LAM55 * pw / np.sum(LAM55 * pw)
        self.assertGreater(mx.pearson_chi2(o, q)[2], 1e-3)
        self.assertLess(mx.pearson_chi2(o, LAM55)[2], 1e-6)


class TestSimulateBlinking(unittest.TestCase):

    def test_t_mask_blinking_F107(self):
        # F107 (port R3): en el legado sim_exp('p_minflux') ignoraba t_mask y ponía el 51.35 % de
        # los fotones en la mitad apagada. En v2 un ciclo apagado no tiene fotones de señal.
        M = 4000
        mask = np.r_[np.zeros(M // 2, bool), np.ones(M // 2, bool)]
        for tcspc, seed in [("earliest", 71), ("highest", 72), ("none", 73)]:
            p = sm.SimParams(tcspc=tcspc, rate_per_cycle=2.5e-3)
            c, tags = sm.simulate_counts(LAM55, 40, 500, math.inf, p, _rng(seed), return_tags=True,
                                         t_mask=mask)
            off = ~mask[np.mod(np.floor(tags["cycle"]).astype(np.int64), M)]
            # la cola de un fotón del ciclo M-1 (encendido) puede llegar en el ciclo M = 0 (mod M,
            # apagado): se admite solo ese borde (tags["cycle"] es el ciclo de LLEGADA)
            edge = np.mod(tags["cycle"], M) == 0
            self.assertEqual(int(np.sum(off & ~edge)), 0, tcspc)
            np.testing.assert_array_equal(np.bincount(tags["loc"], minlength=40), 500)
        # con fondo (sbr 5): la fracción de fotones en la mitad apagada es la del fondo, 1/7
        p = sm.SimParams(rate_per_cycle=2.5e-3)
        _, tags = sm.simulate_counts(LAM55, 200, 1000, 5.0, p, _rng(74), return_tags=True,
                                     t_mask=mask)
        f_off = np.mean(~mask[np.mod(tags["cycle"], M)])
        se = math.sqrt(f_off * (1 - f_off) / tags["cycle"].size)
        _log("t_mask", photons=tags["cycle"].size, frac_off=round(f_off, 4), ref=round(1 / 7., 4))
        self.assertLess(abs(f_off - 1 / 7.), 5 * se + 2e-3)
        # máscara toda encendida = sin máscara, bit a bit (no cambia las extracciones aleatorias)
        c0 = sm.simulate_counts(LAM55, 30, 300, SBR21, sm.SimParams(), _rng(75))
        c1 = sm.simulate_counts(LAM55, 30, 300, SBR21, sm.SimParams(), _rng(75),
                                t_mask=np.ones(17, bool))
        np.testing.assert_array_equal(c0, c1)
        for bad in [np.zeros((2, 3)), np.zeros(0), np.array([0, 2, 1])]:
            with self.assertRaises(ValueError):
                sm.simulate_counts(LAM55, 2, 10, 5.0, sm.SimParams(), _rng(1), t_mask=bad)
        with self.assertRaises(ValueError):
            sm.simulate_counts(LAM55, 2, 10, math.inf, sm.SimParams(), _rng(1), t_mask=np.zeros(5))

    def test_t_mask_sbr_reference(self):
        # R3 (code-reviewer): con t_mask, sbr='on' se refiere a los ciclos encendidos (el SBR
        # detectado baja con f_on); sbr_reference='total' reproduce el legado (Ns/Nb fijos del
        # conjunto). Máscara 50 % en bloques de 1000 ciclos; 'none' para medir fracciones sin
        # distorsión de tasa; sbr = 21.
        M = 2000
        mask = np.r_[np.ones(M // 2, bool), np.zeros(M // 2, bool)]
        p = sm.SimParams(tcspc="none", rate_per_cycle=2.5e-3)
        res = {}
        for ref, seed in [("on", 81), ("total", 82)]:
            _, tags = sm.simulate_counts(LAM55, 200, 1000, 21.0, p, _rng(seed), return_tags=True,
                                         t_mask=mask, sbr_reference=ref)
            f_bg = float(np.mean(tags["source"] == -1))
            se = math.sqrt(f_bg * (1 - f_bg) / tags["source"].size)
            res[ref] = (f_bg, se)
        _log("sbr_reference", on=round(res["on"][0], 4), total=round(res["total"][0], 4),
             ref_on=round(1 / (1 + 21 * 0.5), 4), ref_total=round(1 / 22., 4))
        # 'on': fondo detectado = 1/(1 + sbr f_on) = 0.0870; 'total': 1/(1 + sbr) = 0.0455
        self.assertLess(abs(res["on"][0] - 1 / (1 + 10.5)), 5 * res["on"][1] + 1.5e-3)
        self.assertLess(abs(res["total"][0] - 1 / 22.), 5 * res["total"][1] + 1.5e-3)
        # sin t_mask las dos referencias son idénticas bit a bit
        c0 = sm.simulate_counts(LAM55, 20, 200, SBR21, sm.SimParams(), _rng(83))
        c1 = sm.simulate_counts(LAM55, 20, 200, SBR21, sm.SimParams(), _rng(83),
                                sbr_reference="total")
        np.testing.assert_array_equal(c0, c1)
        with self.assertRaises(ValueError):
            sm.simulate_counts(LAM55, 2, 10, 5.0, sm.SimParams(), _rng(1), sbr_reference="x")
        with self.assertRaises(ValueError):
            sm.simulate_counts(LAM55, 2, 10, 5.0, sm.SimParams(), _rng(1), t_mask=np.zeros(5),
                               sbr_reference="total")


class TestSimulateSpeed(unittest.TestCase):

    def test_throughput(self):
        # Tamaño chico, parámetros por defecto (tasa 2.5e-3, dead_time 22 ns, earliest, IRF 0.3).
        n_loc, N = 1000, 2000
        t0 = time.time()
        sm.simulate_counts(LAM55, n_loc, N, SBR21, sm.SimParams(), _rng(111))
        el = time.time() - t0
        rate = n_loc * N / el
        extrap = 1e5 * 2000 / rate
        _log("throughput", photons=n_loc * N, seconds=round(el, 2), photons_per_s="%.3g" % rate,
             extrapolated_1e5x2000_s=round(extrap, 1))
        self.assertGreater(rate, 2e5)            # meta: 1e5 x 2000 en minutos (< 1000 s)


if __name__ == "__main__":
    unittest.main()
