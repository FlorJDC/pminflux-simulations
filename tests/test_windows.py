# -*- coding: utf-8 -*-
"""Tests de pminflux_sim.windows (conteo por ventana desde microtiempos) y del guard b > T/K
(ventanas solapadas) en simulate, estimate.crb y estimate.mle_mixing (ronda 3, W1)."""

import math
import os
import sys
import unittest
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pminflux_sim import mixing as mx  # noqa: E402
from pminflux_sim import psf  # noqa: E402
from pminflux_sim import simulate as sm  # noqa: E402
from pminflux_sim import estimate as es  # noqa: E402
from pminflux_sim import windows as wn  # noqa: E402

T, K = 50.0, 4
POS = psf.beam_positions(K, 100.0, center=True)
LAM55 = psf.lambda_beams(np.array([5.0, -5.0]), POS, 360.0)


def _explicit(t, a, b):
    """Referencia independiente: pertenencia por intervalos explícitos (sin la fase plegada)."""
    t = np.mod(np.asarray(t, float), T)
    out = np.zeros((K, t.size), dtype=bool)
    for i in range(K):
        s = i * T / K + a
        for shift in (-T, 0.0, T):                     # imágenes periódicas del intervalo
            lo, hi = s + shift, s + b + shift
            out[i] |= (t >= lo) & (t < hi)
    return out


class TestCountWindows(unittest.TestCase):

    def test_matches_simulate_counts_exactly(self):
        # Las cuentas de simulate_counts (conteo 'periodic') salen exactamente de sus microtiempos.
        for a, b, irf, seed in [(0.0, 10.1, 0.3, 1), (-0.5, 12.5, 0.3, 2), (3.0, 9.0, 0.0, 3)]:
            p = sm.SimParams(a=a, b=b, irf_fwhm=irf)
            c, tags = sm.simulate_counts(LAM55, 50, 400, 21.0, p, np.random.default_rng(seed),
                                         return_tags=True)
            cw, out = wn.count_windows(tags["microtime_ns"], T, K, a, b, macro_index=tags["loc"],
                                       n_loc=50, return_outside=True)
            np.testing.assert_array_equal(cw, c)
            np.testing.assert_array_equal(cw.sum(1) + out, np.bincount(tags["loc"], minlength=50))
            tot = wn.count_windows(tags["microtime_ns"], T, K, a, b)
            np.testing.assert_array_equal(tot, c.sum(0))

    def test_window_crossing_T(self):
        # a = 5, b = 10: la ventana 3 es [42.5, 52.5) -> [42.5, 50) U [0, 2.5).
        t = np.array([42.5, 49.999, 0.0, 2.4999, 2.5, 5.0, 14.999, 15.0, 17.5, 27.5, 30.0, 40.0])
        c, out = wn.count_windows(t, T, K, 5.0, 10.0, return_outside=True)
        np.testing.assert_array_equal(c, [2, 1, 1, 4])
        self.assertEqual(out, 4)                       # 2.5, 15.0, 27.5, 40.0
        np.testing.assert_array_equal(wn.window_masks(t, T, K, 5.0, 10.0), _explicit(t, 5.0, 10.0))
        # tiempos absolutos (t + m T) dan lo mismo: se pliega con t mod T
        np.testing.assert_array_equal(wn.count_windows(t + 7 * T, T, K, 5.0, 10.0), c)

    def test_negative_a(self):
        # a = -0.5, b = 12.5: ventana 0 = [49.5, 50) U [0, 12.0); el 0.0 no tiene trato especial.
        t = np.array([49.5, 49.9, 0.0, 11.999, 12.0, 24.4, 36.9, 49.4])
        c = wn.count_windows(t, T, K, -0.5, 12.5)
        np.testing.assert_array_equal(c, [4, 2, 1, 1])
        rng = np.random.default_rng(9)
        u = rng.uniform(-100.0, 100.0, 20000)
        for a, b in [(-0.5, 12.5), (-3.0, 10.1), (0.0, 10.1), (7.0, 12.0)]:
            np.testing.assert_array_equal(wn.window_masks(u, T, K, a, b), _explicit(u, a, b))
        # uniforme: cada ventana recibe b/T
        cu = wn.count_windows(np.mod(u, T), T, K, -0.5, 12.5)
        np.testing.assert_allclose(cu / u.size, 12.5 / T, atol=0.015)

    def test_low_rate_matches_window_probs(self):
        # Límite de baja tasa (1e-4/ciclo): las fracciones de count_windows sobre los microtiempos
        # del simulador siguen el modelo de mezcla (chi^2 de Pearson, p > 1e-3).
        a, b = 0.0, 10.1
        p = sm.SimParams(a=a, b=b, rate_per_cycle=1e-4)
        _, tags = sm.simulate_counts(LAM55, 200, 2095, 2000 / 95., p, np.random.default_rng(21),
                                     return_tags=True)
        o = wn.count_windows(tags["microtime_ns"], T, K, a, b)
        C = mx.mixing_matrix(4.21, T, K, a, b, irf_fwhm=0.3)
        pr = mx.window_probs(LAM55, C, b, T, Ns=2000.0, Nb=95.0)
        _, _, pv, _ = mx.pearson_chi2(o, pr)
        print("\n[windows_low_rate] photons=%d p_mixing=%.3g p_naive=%.3g"
              % (o.sum(), pv, mx.pearson_chi2(o, mx.naive_probs(LAM55, 2000 / 95.))[2]))
        self.assertGreater(pv, 1e-3)
        self.assertLess(mx.pearson_chi2(o, mx.naive_probs(LAM55, 2000 / 95.))[2], 1e-6)

    def test_grouping_and_validation(self):
        t = np.array([1.0, 13.0, 26.0, 38.0, 11.0, 1.0])
        g = np.array([0, 0, 2, 2, 2, 0])
        c, out = wn.count_windows(t, T, K, 0.0, 10.1, macro_index=g, return_outside=True)
        np.testing.assert_array_equal(c, [[2, 1, 0, 0], [0, 0, 0, 0], [0, 0, 1, 1]])
        np.testing.assert_array_equal(out, [0, 0, 1])
        self.assertEqual(wn.count_windows(t, macro_index=g, n_loc=5).shape, (5, K))
        self.assertEqual(wn.count_windows(np.zeros(0)).tolist(), [0, 0, 0, 0])
        self.assertEqual(wn.count_windows(np.zeros(0), macro_index=np.zeros(0, int)).shape, (0, K))
        for bad in [np.array([1.0, np.nan]), np.array([np.inf])]:
            with self.assertRaises(ValueError):
                wn.count_windows(bad)
        with self.assertRaises(ValueError):
            wn.count_windows(t, macro_index=g[:3])
        with self.assertRaises(ValueError):
            wn.count_windows(t, macro_index=-g)
        with self.assertRaises(ValueError):
            wn.count_windows(t, macro_index=g, n_loc=2)
        with self.assertRaises(ValueError):
            wn.count_windows(t, b=0.0)


class TestOverlapGuard(unittest.TestCase):
    """b = 20 > T/K = 12.5: ValueError en todos los puntos de entrada; allow_overlap avisa."""

    def setUp(self):
        self.C = mx.mixing_matrix(4.21, T, K, 0.0, 20.0)

    def test_raises(self):
        with self.assertRaisesRegex(ValueError, "ventanas solapadas"):
            sm.simulate_counts(LAM55, 2, 10, 5.0, sm.SimParams(b=20.0), np.random.default_rng(1))
        with self.assertRaisesRegex(ValueError, "ventanas solapadas"):
            es.crb([5.0, -5.0], POS, 360.0, self.C, 20.0, T, 21.0, 2095)
        with self.assertRaisesRegex(ValueError, "ventanas solapadas"):
            es.mle_mixing(np.array([[500, 500, 500, 500]]), POS, 360.0, self.C, 20.0, T, 21.0, 75.0)
        with self.assertRaisesRegex(ValueError, "ventanas solapadas"):
            wn.count_windows(np.array([1.0]), T, K, 0.0, 20.0)
        # b = T/K exacto sigue permitido (ventanas contiguas, sin solapamiento)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sm.simulate_counts(LAM55, 2, 10, 5.0, sm.SimParams(b=12.5), np.random.default_rng(1))
            es.crb([5.0, -5.0], POS, 360.0, mx.mixing_matrix(4.21, T, K, 0.0, 12.5), 12.5, T, 21.0,
                   2095)
            es.crb_legacy([5.0, -5.0], POS, 360.0, 21.0, 2095)

    def test_allow_overlap_warns(self):
        def warned(fn):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                out = fn()
            self.assertTrue(any(issubclass(x.category, UserWarning) and "ventanas solapadas"
                                in str(x.message) for x in w))
            return out
        c = warned(lambda: sm.simulate_counts(LAM55, 3, 50, 5.0, sm.SimParams(b=20.0, allow_overlap=True),
                                              np.random.default_rng(1)))
        self.assertEqual(c.shape, (3, K))
        s = warned(lambda: es.crb([5.0, -5.0], POS, 360.0, self.C, 20.0, T, 21.0, 2095,
                                  allow_overlap=True))
        self.assertTrue(math.isfinite(s))
        r = warned(lambda: es.mle_mixing(np.array([[500, 500, 500, 500]]), POS, 360.0, self.C, 20.0,
                                         T, 21.0, 75.0, allow_overlap=True))
        self.assertEqual(r.r.shape, (1, 2))
        cw = warned(lambda: wn.count_windows(np.array([15.0]), T, K, 0.0, 20.0, allow_overlap=True))
        np.testing.assert_array_equal(cw, [1, 1, 0, 0])     # en el solapamiento cuenta dos veces


if __name__ == "__main__":
    unittest.main()
