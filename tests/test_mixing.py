# -*- coding: utf-8 -*-
"""Tests de pminflux_sim.mixing (matriz de mezcla, modelos por ventana, predictor a tasa finita)."""

import contextlib
import io
import itertools
import math
import os
import sys
import unittest

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pminflux_sim import mixing as mx  # noqa: E402


def _acceptance_mixing(tau, T, K, a, b, nwrap=40):
    """Copia literal de la fórmula de tests/test_acceptance.py (válida para a >= 0)."""
    dt = T / K
    C = [[0.0] * K for _ in range(K)]
    for i in range(K):
        for j in range(K):
            off = ((i - j) * dt) % T
            s = 0.0
            for m in range(nwrap):
                t0 = off + a + m * T
                t1 = t0 + b
                lo, hi = max(t0, 0.0), max(t1, 0.0)
                s += math.exp(-lo / tau) - math.exp(-hi / tau)
            C[i][j] = s
    return np.array(C)


def _mc_mixing(tau, T, K, a, b, sigma, n, rng):
    """C por Monte Carlo directo: X = N(0, sigma) + Exp(tau), tiempo j*dt + X, ventana mod T."""
    dt = T / K
    C = np.zeros((K, K))
    for j in range(K):
        x = rng.exponential(tau, n) + (rng.normal(0, sigma, n) if sigma else 0.0)
        t = j * dt + x
        for i in range(K):
            C[i, j] = np.mean(np.mod(t - i * dt - a, T) < b)
    return C


class MixingMatrix(unittest.TestCase):

    def test_matches_acceptance_formula(self):
        for tau, T, K, a, b in [(4.21, 50.0, 4, 0.0, 10.1), (4.21, 50.0, 4, 0.0, 12.5),
                                (1.0, 25.0, 4, 0.5, 5.0), (8.0, 50.0, 3, 0.0, 16.0),
                                (30.0, 50.0, 4, 0.0, 10.1)]:
            C = mx.mixing_matrix(tau, T, K, a, b)
            ref = _acceptance_mixing(tau, T, K, a, b, nwrap=80)
            self.assertLess(np.abs(C - ref).max(), 1e-9, (tau, T, K, a, b))

    def test_acceptance_formula_misses_windows_crossing_T(self):
        # La fórmula del test de aceptación solo suma imágenes m >= 0: si la última ventana
        # cruza T (a + (K-1) T/K + b > T), pierde la parte que cae al comienzo del ciclo.
        # mixing_matrix la incluye; se contrasta con Monte Carlo directo.
        tau, T, K, a, b = 8.0, 50.0, 3, 2.0, 16.0
        C = mx.mixing_matrix(tau, T, K, a, b)
        ref = _acceptance_mixing(tau, T, K, a, b, nwrap=80)
        self.assertGreater(np.abs(C - ref).max(), 0.1)
        n = 1000000
        Cmc = _mc_mixing(tau, T, K, a, b, None, n, np.random.RandomState(2))
        se = np.sqrt(np.clip(C * (1 - C), 1.0 / n, None) / n)
        self.assertLess(np.max(np.abs(C - Cmc) / se), 5.0)

    def test_handoff_values(self):
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        for i in range(4):
            self.assertAlmostEqual(C[i, i], 0.909, delta=5e-4)
            self.assertAlmostEqual(C[i, (i - 1) % 4], 0.047, delta=5e-4)   # haz anterior
        # circulante: todas las columnas capturan lo mismo
        self.assertLess(np.ptp(C.sum(axis=0)), 1e-12)

    def test_columns_sum_to_captured_fraction(self):
        rng = np.random.RandomState(1)
        tau, T, K, a, b = 4.21, 50.0, 4, 0.0, 10.1
        C = mx.mixing_matrix(tau, T, K, a, b)
        x = np.mod(rng.exponential(tau, 2000000), T)
        dt = T / K
        captured = np.mean(np.any([np.mod(x - i * dt - a, T) < b for i in range(K)], axis=0))
        se = math.sqrt(captured * (1 - captured) / x.size)
        for j in range(K):
            self.assertLess(abs(C[:, j].sum() - captured), 5 * se)
        # ventanas que cubren el ciclo: se captura todo
        Cf = mx.mixing_matrix(tau, T, K, 0.0, T / K)
        np.testing.assert_allclose(Cf.sum(axis=0), 1.0, atol=1e-12)
        Cfi = mx.mixing_matrix(tau, T, K, -1.3, T / K, irf_fwhm=0.8)
        np.testing.assert_allclose(Cfi.sum(axis=0), 1.0, atol=1e-9)

    def test_short_lifetime_full_windows_is_identity(self):
        C = mx.mixing_matrix(1e-3, 50.0, 4, 0.0, 12.5)
        np.testing.assert_allclose(C, np.eye(4), atol=1e-12)

    def test_irf_to_zero_recovers_no_irf(self):
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        Ci = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, irf_fwhm=1e-7)
        self.assertLess(np.abs(C - Ci).max(), 1e-7)
        # con a > 0 (lejos del borde del pulso) la convergencia es aún mejor
        C2 = mx.mixing_matrix(4.21, 50.0, 4, 0.7, 10.1)
        C2i = mx.mixing_matrix(4.21, 50.0, 4, 0.7, 10.1, irf_fwhm=1e-4)
        self.assertLess(np.abs(C2 - C2i).max(), 1e-8)

    def test_irf_negative_start_and_window_crossing_T_vs_montecarlo(self):
        rng = np.random.RandomState(7)
        n = 1000000
        for a, b, fwhm in [(-3.0, 15.0, 2.0), (45.0, 12.5, 0.3), (-0.5, 10.1, 0.3),
                           (10.0, 50.0, 1.0)]:
            C = mx.mixing_matrix(4.21, 50.0, 4, a, b, irf_fwhm=fwhm)
            Cmc = _mc_mixing(4.21, 50.0, 4, a, b, mx.fwhm_to_sigma(fwhm), n, rng)
            se = np.sqrt(np.clip(C * (1 - C), 1.0 / n, None) / n)
            self.assertLess(np.max(np.abs(C - Cmc) / se), 5.0, (a, b, fwhm))
        # b = T: cada ventana captura todo el fotón
        np.testing.assert_allclose(mx.mixing_matrix(4.21, 50.0, 4, 10.0, 50.0, irf_fwhm=1.0),
                                   np.ones((4, 4)), atol=1e-9)

    def test_emg_cdf_pdf_consistency(self):
        t = np.linspace(-5, 80, 200001)
        for sigma in (None, 0.127, 2.0):
            F = mx.decay_cdf(t, 4.21, sigma)
            f = mx.decay_pdf(t, 4.21, sigma)
            self.assertTrue(np.all(np.isfinite(F)) and np.all(np.diff(F) >= -1e-15))
            self.assertAlmostEqual(F[-1], 1.0, delta=1e-8)
            # integral numérica de la densidad = CDF (trapecio), lejos del salto en 0 sin IRF
            Fi = np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(t))])
            k = t > 1.0
            self.assertLess(np.abs(Fi[k] - F[k] + (F[0] if sigma else 0.0)).max(), 1e-4)
        # extremos: sin overflow
        self.assertTrue(np.all(np.isfinite(mx.decay_cdf([-1e3, 1e4], 4.21, 1e-3))))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            mx.mixing_matrix(4.21, 50.0, 4, 0.0, 60.0)
        with self.assertRaises(ValueError):
            mx.mixing_matrix(4.21, 50.0, 4, 0.0, 0.0)
        with self.assertRaises(ValueError):
            mx.mixing_matrix(4.21, 50.0, 0, 0.0, 10.0)
        with self.assertRaises(ValueError):
            mx.mixing_matrix(-1.0, 50.0, 4, 0.0, 10.0)
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        with self.assertRaises(ValueError):
            mx.window_probs([-1, 1, 1, 1], C, 10.1, 50.0, sbr=10)
        with self.assertRaises(ValueError):
            mx.window_probs([0, 0, 0, 0], C, 10.1, 50.0, sbr=10)
        with self.assertRaises(ValueError):
            mx.window_probs([1, 1, 1, 1], C, 10.1, 50.0)
        with self.assertRaises(ValueError):
            mx.window_probs([1, 1, 1, 1], C, 10.1, 50.0, sbr=10, Ns=1, Nb=1)
        with self.assertRaises(ValueError):
            mx.pattern_window_dist(4.21, 50.0, 4, 0.0, 10.1, rule="latest")


class WindowModels(unittest.TestCase):
    lam = np.array([0.12, 0.28, 0.35, 0.25])

    def test_mixing_reduces_to_naive_without_leak_and_full_windows(self):
        C = mx.mixing_matrix(1e-3, 50.0, 4, 0.0, 12.5)
        for sbr in (1.0, 10.0, 95.0, float("inf")):
            np.testing.assert_allclose(mx.window_probs(self.lam, C, 12.5, 50.0, sbr=sbr),
                                       mx.naive_probs(self.lam, sbr), atol=1e-12)

    def test_sbr_and_counts_parametrizations_agree(self):
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        np.testing.assert_allclose(mx.window_probs(self.lam, C, 10.1, 50.0, sbr=10.0),
                                   mx.window_probs(self.lam, C, 10.1, 50.0, Ns=2000, Nb=200))
        e = mx.window_expected(self.lam, C, 10.1, 50.0, 2000, 200)
        np.testing.assert_allclose(e, 2000 * C.dot(self.lam / self.lam.sum()) + 200 * 10.1 / 50)
        p0 = mx.window_probs(self.lam, C, 10.1, 50.0, Ns=5, Nb=0)
        np.testing.assert_allclose(p0, C.dot(self.lam) / C.dot(self.lam).sum())

    def test_leak_changes_the_model_substantially(self):
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        pm = mx.window_probs(self.lam, C, 10.1, 50.0, sbr=10.0)
        pn = mx.naive_probs(self.lam, 10.0)
        # la ventana 0 débil recibe fuga del haz 3: +3.5 % relativo con SBR = 10
        self.assertGreater(pm[0] - pn[0], 0.004)
        self.assertLess(pm[2] - pn[2], 0.0)   # el haz más brillante pierde por fuga

    def test_pearson_matches_scipy(self):
        o = np.array([130, 270, 350, 250.])
        p = np.array([0.13, 0.27, 0.35, 0.25])
        chi2, dof, pv, dev = mx.pearson_chi2(o, p)
        ref = stats.chisquare(o, o.sum() * p)
        self.assertAlmostEqual(chi2, ref.statistic, places=10)
        self.assertAlmostEqual(pv, ref.pvalue, places=10)
        self.assertEqual(dof, 3)
        with self.assertRaises(ValueError):
            mx.pearson_chi2([1, 2], [0.5, 0.0])


class FiniteRatePredictor(unittest.TestCase):
    lam = np.array([0.12, 0.28, 0.35, 0.25])

    def test_pattern_probs_exact_vs_replica(self):
        rng = np.random.RandomState(3)
        Nh, M = 3000, 5000
        P = mx.occupancy_pattern_probs(self.lam, Nh, M)
        p = self.lam / self.lam.sum()
        self.assertAlmostEqual(sum(P.values()) + (1 - 1.0 / M) ** Nh, 1.0, places=12)
        # réplica del muestreo de sim_exp
        acc = {}
        reps = 200
        for _ in range(reps):
            nk = np.zeros((M, 4), int)
            npb = rng.multinomial(Nh, p)
            for k in range(4):
                np.add.at(nk[:, k], rng.randint(0, M, npb[k]), 1)
            occ = nk > 0
            code = occ.dot(1 << np.arange(4))
            for c, cnt in zip(*np.unique(code, return_counts=True)):
                acc[c] = acc.get(c, 0) + cnt
        tot = reps * M
        for S, v in P.items():
            c = sum(1 << k for k in S)
            se = math.sqrt(v * (1 - v) / tot)
            self.assertLess(abs(acc.get(c, 0) / tot - v), 5 * se + 1e-9, S)

    def test_pattern_window_dist(self):
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        He = mx.pattern_window_dist(4.21, 50.0, 4, 0.0, 10.1, rule="earliest")
        Hh = mx.pattern_window_dist(4.21, 50.0, 4, 0.0, 10.1, rule="highest")
        self.assertEqual(len(He), 15)
        for k in range(4):
            np.testing.assert_allclose(He[(k,)], C[:, k], atol=1e-10)
        for S in Hh:
            np.testing.assert_allclose(Hh[S], C[:, max(S)])
        # MC del "gana el más temprano" para S = (0, 3) y (1, 2, 3)
        rng = np.random.RandomState(5)
        n = 1000000
        for S in [(0, 3), (1, 2, 3)]:
            t = np.min([k * 12.5 + rng.exponential(4.21, n) for k in S], axis=0)
            mc = np.array([np.mean(np.mod(t - i * 12.5, 50.0) < 10.1) for i in range(4)])
            se = np.sqrt(np.clip(He[S] * (1 - He[S]), 1.0 / n, None) / n)
            self.assertLess(np.max(np.abs(mc - He[S]) / se), 5.0, S)
        # con IRF y a < 0: singletons = columnas de C
        Hi = mx.pattern_window_dist(4.21, 50.0, 4, -0.5, 10.1, irf_fwhm=0.3, rule="earliest")
        Ci = mx.mixing_matrix(4.21, 50.0, 4, -0.5, 10.1, irf_fwhm=0.3)
        for k in range(4):
            np.testing.assert_allclose(Hi[(k,)], Ci[:, k], atol=1e-9)

    def test_rate_to_zero_recovers_mixing(self):
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        pm = mx.window_probs(self.lam, C, 10.1, 50.0, Ns=2000, Nb=200)
        for rule in ("highest", "earliest"):
            d = [np.abs(mx.sim_exp_window_probs(self.lam, 2000, 200, 2100, M, 4.21, 50.0, 4,
                                                0.0, 10.1, rule=rule) - pm).max()
                 for M in (10 ** 7, 10 ** 8)]
            self.assertLess(d[1], 1e-5)
            self.assertAlmostEqual(d[0] / d[1], 10.0, delta=0.1)   # sesgo lineal en la tasa
        # y a tasa alta los dos sesgos van en sentidos opuestos en la ventana 0
        ph = mx.sim_exp_window_probs(self.lam, 2000, 200, 2100, 7333, 4.21, 50.0, 4, 0.0, 10.1,
                                     rule="highest")
        pe = mx.sim_exp_window_probs(self.lam, 2000, 200, 2100, 7333, 4.21, 50.0, 4, 0.0, 10.1,
                                     rule="earliest")
        self.assertLess(ph[0], pm[0])
        self.assertGreater(pe[0], pm[0])


class AgainstLegacySimExp(unittest.TestCase):
    """Llamadas reales (cortas) a sim_exp del legado, importado en solo lectura."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
        from tools import tools_simulations as ts
        cls.ts = ts
        cls.lam = np.array([0.12, 0.28, 0.35, 0.25])

    def _run(self, seed, ncalls, Ns, Nb, M_p, factor):
        np.random.seed(seed)
        psf = self.lam.reshape(4, 1, 1)
        tot = np.zeros(4)
        for _ in range(ncalls):
            with contextlib.redirect_stdout(io.StringIO()):
                rel, _, failed = self.ts.sim_exp('p_minflux', None, psf, (0, 0), 10, Ns, Nb,
                                                 M_p, 4.21, factor, 50)
            self.assertEqual(failed, 0)
            tot += self.ts.nMINFLUX(4, [0, 12.5, 25, 37.5], rel, 0, 10.1)
        return tot

    def test_low_rate_mixing_ok_naive_rejected(self):
        cnt = self._run(11, 60, 2000, 0, 200000, 1.05)
        C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1)
        pm = mx.window_probs(self.lam, C, 10.1, 50.0, Ns=2000, Nb=0)
        ph = mx.sim_exp_window_probs(self.lam, 2000, 0, 2100, 200000, 4.21, 50.0, 4, 0, 10.1)
        self.assertGreater(mx.pearson_chi2(cnt, pm)[2], 1e-3)
        self.assertGreater(mx.pearson_chi2(cnt, ph)[2], 1e-3)
        self.assertLess(mx.pearson_chi2(cnt, mx.naive_probs(self.lam, float("inf")))[2], 1e-6)

    def test_high_rate_overwrite_bias_is_predicted(self):
        Ns, Nb, M_p = 2000, 200, 7333
        s = Ns / float(M_p)
        factor = 1.10 * (-math.log1p(-s)) / s
        Nh = int(Ns * factor)
        cnt = self._run(12, 60, Ns, Nb, M_p, factor)
        ph = mx.sim_exp_window_probs(self.lam, Ns, Nb, Nh, M_p, 4.21, 50.0, 4, 0, 10.1,
                                     rule="highest")
        pe = mx.sim_exp_window_probs(self.lam, Ns, Nb, Nh, M_p, 4.21, 50.0, 4, 0, 10.1,
                                     rule="earliest")
        pm = mx.window_probs(self.lam, mx.mixing_matrix(4.21, 50.0, 4, 0, 10.1), 10.1, 50.0,
                             Ns=Ns, Nb=Nb)
        self.assertGreater(mx.pearson_chi2(cnt, ph)[2], 1e-3)   # el predictor describe sim_exp
        self.assertLess(mx.pearson_chi2(cnt, pm)[2], 1e-6)      # la mezcla ideal no, a 0.3/ciclo
        self.assertLess(mx.pearson_chi2(cnt, pe)[2], 1e-6)      # ni un TCSPC real


if __name__ == "__main__":
    unittest.main()
