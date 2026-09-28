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


class TestFoldEdge(unittest.TestCase):
    """R3 (code-reviewer, unclear): una fase que al plegar da exactamente T por redondeo."""

    def test_phase_equal_T_maps_to_zero(self):
        # b = T/K: las ventanas cubren el ciclo, así que TODO fotón tiene que caer en alguna.
        cases = [(0.0, -1e-17), (0.5, np.nextafter(0.5, 0.0)), (-0.5, np.nextafter(-0.5, -1.0)),
                 (0.0, np.nextafter(0.0, -1.0)), (0.0, -T * 1e-17)]
        for a, t in cases:
            ph = (t - a) - np.floor((t - a) / T) * T
            c, out = wn.count_windows(np.array([t]), T, K, a, T / K, return_outside=True)
            self.assertEqual(out, 0, (a, t, ph))
            self.assertEqual(int(c.sum()), 1, (a, t))
            if ph >= T or ph < 0:                      # el caso del borde: se identifica con 0
                np.testing.assert_array_equal(c, [1, 0, 0, 0])
        self.assertTrue(any(((t - a) - np.floor((t - a) / T) * T) >= T for a, t in cases))
        self.assertTrue(any(((t - a) - np.floor((t - a) / T) * T) < 0 for a, t in cases))
        # también con starts explícitos
        st = wn.window_starts(T, K, 0.5)
        c = wn.count_windows(np.array([np.nextafter(0.5, 0.0)]), T, K, b=T / K, starts=st)
        self.assertEqual(int(c.sum()), 1)
        # y el camino sin problemas no cambia (máscaras == intervalos explícitos)
        u = np.random.default_rng(3).uniform(-60.0, 60.0, 5000)
        np.testing.assert_array_equal(wn.window_masks(u, T, K, 0.5, T / K), _explicit(u, 0.5, T / K))


class TestStarts(unittest.TestCase):
    """R3: ``starts`` por ventana (offset del sync, retardos no equiespaciados) y
    ``mixing_matrix_starts`` (C para comienzos/pulsos arbitrarios)."""

    def test_default_starts_equivalent(self):
        u = np.random.default_rng(4).uniform(-100.0, 200.0, 20000)
        g = np.random.default_rng(5).integers(0, 7, u.size)
        for a, b in [(0.0, 10.1), (-0.5, 12.5), (5.0, 10.0)]:
            c0 = wn.count_windows(u, T, K, a, b, macro_index=g)
            c1 = wn.count_windows(u, T, K, 123.0, b, macro_index=g,
                                  starts=wn.window_starts(T, K, a))   # a se ignora con starts
            np.testing.assert_array_equal(c0, c1)
            C0 = mx.mixing_matrix(4.21, T, K, a, b, irf_fwhm=0.3)
            C1 = wn.mixing_matrix_starts(4.21, T, wn.window_starts(T, K, a), b, irf_fwhm=0.3)
            np.testing.assert_allclose(C1, C0, rtol=0, atol=1e-13)
        np.testing.assert_allclose(wn.mixing_matrix_starts(4.21, T, wn.window_starts(T, K), 10.1),
                                   mx.mixing_matrix(4.21, T, K, 0.0, 10.1), atol=1e-13)

    def test_sync_offset(self):
        # microtiempos del TCSPC con el pulso del haz 0 en t0 = 7.3 ns: restar t0 o pasar starts
        # corridos da lo mismo, y C es invariante ante el corrimiento común.
        t0 = 7.3
        p = sm.SimParams(rate_per_cycle=2.5e-3)
        c, tags = sm.simulate_counts(LAM55, 30, 400, 21.0, p, np.random.default_rng(6),
                                     return_tags=True)
        raw = np.mod(tags["microtime_ns"] + t0, T)          # lo que registraría el TCSPC
        c1 = wn.count_windows(raw, T, K, b=10.1, macro_index=tags["loc"], n_loc=30,
                              starts=wn.window_starts(T, K, 0.0, t0))
        np.testing.assert_array_equal(c1, c)
        np.testing.assert_array_equal(
            wn.count_windows(raw - t0, T, K, 0.0, 10.1, macro_index=tags["loc"], n_loc=30), c)
        C = wn.mixing_matrix_starts(4.21, T, wn.window_starts(T, K, 0.0, t0), 10.1,
                                    pulse_times=t0 + np.arange(K) * T / K, irf_fwhm=0.3)
        np.testing.assert_allclose(C, mx.mixing_matrix(4.21, T, K, 0.0, 10.1, irf_fwhm=0.3),
                                   atol=1e-13)

    def test_non_equispaced_monte_carlo(self):
        # Pulsos medidos no equiespaciados y ventanas que arrancan en cada pulso: fotones sintéticos
        # (retardo = pulso_j + N(0, sigma) + Exp(tau), mod T), sin simulador ni mezcla. Las
        # fracciones siguen C = mixing_matrix_starts (chi^2 p > 1e-3) y no la C equiespaciada.
        rng = np.random.default_rng(7)
        pulses = np.array([0.4, 13.6, 24.1, 38.2])
        starts = pulses + 0.2
        b, tau, fwhm = 10.1, 4.21, 0.3
        q = LAM55 / LAM55.sum()
        n = 400000
        beam = rng.choice(K, size=n, p=q)
        t = pulses[beam] + rng.normal(0.0, fwhm * mx.fwhm_to_sigma(1.0), n) + rng.exponential(tau, n)
        o = wn.count_windows(t, T, K, b=b, starts=starts)
        C = wn.mixing_matrix_starts(tau, T, starts, b, pulse_times=pulses, irf_fwhm=fwhm)
        pr = mx.window_probs(LAM55, C, b, T, sbr=math.inf)
        pv = mx.pearson_chi2(o, pr)[2]
        pw = mx.pearson_chi2(o, mx.window_probs(LAM55, mx.mixing_matrix(tau, T, K, 0.0, b,
                                                                         irf_fwhm=fwhm),
                                                b, T, sbr=math.inf))[2]
        print("\n[starts_non_equispaced] photons=%d p_starts=%.3g p_equispaced=%.3g"
              % (o.sum(), pv, pw))
        self.assertGreater(pv, 1e-3)
        self.assertLess(pw, 1e-6)
        # columnas: fracción capturada por el conjunto de ventanas, <= 1
        self.assertTrue(np.all(C.sum(0) <= 1 + 1e-12) and np.all(C >= 0))

    def test_estimate_with_starts_matrix(self):
        # El C de mixing_matrix_starts se pasa tal cual a mle_mixing/crb: con conteos esperados
        # (asintóticos) del modelo con pulsos no equiespaciados el MLE devuelve la posición exacta;
        # con la C equiespaciada queda sesgado.
        pulses = np.array([0.0, 12.9, 24.6, 37.0])
        starts = pulses.copy()
        C = wn.mixing_matrix_starts(4.21, T, starts, 10.1, pulse_times=pulses, irf_fwhm=0.3)
        r0 = np.array([5.0, -5.0])
        counts = 2095.0 * es.forward_probs(r0, POS, 360.0, C, 10.1, T, 21.0)[None, :]
        est = es.mle_mixing(counts, POS, 360.0, C, 10.1, T, 21.0, 75.0)
        np.testing.assert_allclose(est.r[0], r0, atol=1e-4)
        C_eq = mx.mixing_matrix(4.21, T, K, 0.0, 10.1, irf_fwhm=0.3)
        bad = es.mle_mixing(counts, POS, 360.0, C_eq, 10.1, T, 21.0, 75.0)
        self.assertGreater(np.linalg.norm(bad.r[0] - r0), 0.1)
        self.assertTrue(math.isfinite(es.crb(r0, POS, 360.0, C, 10.1, T, 21.0, 2095)))

    def test_starts_validation(self):
        with self.assertRaises(ValueError):
            wn.count_windows(np.array([1.0]), T, K, b=10.1, starts=[0.0, 12.5, 25.0])
        with self.assertRaises(ValueError):
            wn.count_windows(np.array([1.0]), T, K, b=10.1, starts=[0.0, 12.5, np.nan, 37.5])
        # separación mínima 8 < b = 10.1: solapadas
        with self.assertRaisesRegex(ValueError, "ventanas solapadas"):
            wn.count_windows(np.array([1.0]), T, K, b=10.1, starts=[0.0, 8.0, 25.0, 37.5])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            wn.count_windows(np.array([1.0]), T, K, b=10.1, starts=[0.0, 8.0, 25.0, 37.5],
                             allow_overlap=True)
        self.assertTrue(any("ventanas solapadas" in str(x.message) for x in w))
        # contiguas exactas (b = separación) permitidas; circular: el último con el primero
        wn.count_windows(np.array([1.0]), T, K, b=12.5, starts=[0.0, 12.5, 25.0, 37.5])
        with self.assertRaisesRegex(ValueError, "ventanas solapadas"):
            wn.count_windows(np.array([1.0]), T, K, b=10.1, starts=[5.0, 17.5, 30.0, 45.0])
        with self.assertRaises(ValueError):
            wn.mixing_matrix_starts(4.21, T, wn.window_starts(T, K), 10.1, pulse_times=[0.0, 1.0])
        with self.assertRaises(ValueError):
            wn.mixing_matrix_starts(4.21, T, [0.0, np.inf, 25.0, 37.5], 10.1)
        with self.assertRaises(ValueError):
            wn.mixing_matrix_starts(4.21, T, wn.window_starts(T, K), 0.0)


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
