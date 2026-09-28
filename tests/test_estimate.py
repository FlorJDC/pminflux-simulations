# -*- coding: utf-8 -*-
"""Tests de pminflux_sim.psf y pminflux_sim.estimate (ronda 2, W3).

Los datos son multinomiales sacados de ``mixing`` (no se importa ``simulate``). Geometría y
setup de F104: TCP K = 4, L = 100 nm, centro, dona fwhm 360 nm; tau = 4.21 ns, ventana
[0, 10.1] ns, T = 50 ns; Ns = 2000, Nb = 95 (SBR 21) o 333 (SBR 6).
"""

import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from pminflux_sim import mixing as mx  # noqa: E402
from pminflux_sim import psf  # noqa: E402
from pminflux_sim import estimate as es  # noqa: E402

T, K, TAU, A, B = 50.0, 4, 4.21, 0.0, 10.1
FWHM, L, R_SEARCH = 360.0, 100.0, 75.0
NS = 2000
POINTS = [(5.0, -5.0), (-5.07, -7.56), (20.0, 0.0), (-15.0, 15.0), (0.0, -30.0)]
F104_BIAS_SBR21 = [0.85, 1.51, 1.63, 2.69, 2.36]      # nm, verificados en R1 (verifier-A)
POS = psf.beam_positions(K, L, center=True)
C_MEAS = mx.mixing_matrix(TAU, T, K, A, B)


def _legacy():
    sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
    import matplotlib
    matplotlib.use("Agg")
    from tools import tools_simulations as ts
    return ts


def _multinomial(r0, n_loc, Nb, rng, C=C_MEAS, b=B, powers=None):
    """Conteos por ventana: multinomial de N = Ns+Nb sobre K ventanas + 'fuera' (mixing)."""
    lam = psf.lambda_beams(np.asarray(r0, float), POS, FWHM)
    if powers is not None:
        lam = lam * np.asarray(powers)
    e = mx.window_expected(lam, C, b, T, NS, Nb) / float(NS + Nb)
    pr = np.append(e, max(1.0 - e.sum(), 0.0))
    return rng.multinomial(NS + Nb, pr / pr.sum(), size=n_loc)[:, :K]


class TestPSF(unittest.TestCase):

    def test_matches_legacy_beams_and_doughnut(self):
        ts = _legacy()
        leg = ts.beams(4, 100, center=True, d="donut")
        leg = np.array([leg[i] for i in range(4)], dtype=float)
        np.testing.assert_allclose(POS, leg, atol=1e-12)
        np.testing.assert_allclose(psf.beam_positions(4, 100, True), ts.ebp_centres(4, 100, True),
                                   atol=1e-12)
        r = np.linspace(0, 800, 4001)
        np.testing.assert_allclose(psf.donut(r, 360.0), ts.doughnut(r), rtol=1e-13, atol=1e-15)
        np.testing.assert_allclose(psf.donut(r, 250.0), ts.doughnut(r, 250.0), rtol=1e-13, atol=1e-15)
        np.testing.assert_allclose(psf.gaussian(r, 360.0), ts.gaussian(r), rtol=1e-13)
        # lambda_beams contra la grilla del legado ts.psf (px = 1) en nodos enteros
        grid = np.array([ts.psf(POS[i], 200, 1, [0, 0], d="donut") for i in range(4)])
        for (x, y) in [(5, -5), (-5, -8), (20, 0), (-15, 15), (0, -30), (33, 41)]:
            row, col = ts.spaceToIndex(np.array([x, y], float), 200, 1)
            lam = psf.lambda_beams(np.array([x, y], float), POS, 360.0)
            np.testing.assert_allclose(lam, grid[:, row, col], rtol=1e-12)
        # vectorización y gradiente analítico contra diferencias finitas
        rr = np.random.default_rng(0).uniform(-60, 60, size=(7, 3, 2))
        lam, dlam = psf.lambda_beams(rr, POS, 360.0, grad=True)
        self.assertEqual(lam.shape, (7, 3, 4))
        self.assertEqual(dlam.shape, (7, 3, 2, 4))
        h = 1e-5
        for ax in range(2):
            e = np.zeros(2)
            e[ax] = h
            fd = (psf.lambda_beams(rr + e, POS, 360.0) - psf.lambda_beams(rr - e, POS, 360.0)) / (2 * h)
            np.testing.assert_allclose(dlam[..., ax, :], fd, rtol=1e-6, atol=1e-10)

    def test_fwhm_honored_and_any_K(self):
        # F109: la FWHM pedida es la que se obtiene (gaussiano) y el anillo está en 0.6006 fwhm
        for f in (250.0, 360.0, 500.0):
            w, _ = psf.measured_fwhm("gaussian", f)
            self.assertAlmostEqual(w, f, delta=1e-2 * f / 100)
            _, rpk = psf.measured_fwhm("donut", f)
            self.assertAlmostEqual(rpk, f * psf.RING_FACTOR, delta=0.01)
        ts = _legacy()
        # el legado, con d='gaussian', ignora donut_fwhm = 250 (F109, antes)
        g = ts.psf(np.array([0.0, 0.0]), 1000, 1, [0, 0], d="gaussian", donut_fwhm=250)
        prof = g[500, 500:]
        fwhm_leg = 2 * np.sum(prof >= 0.5 * prof.max())
        self.assertGreater(abs(fwhm_leg - 250), 100)
        with self.assertRaises(ValueError):
            psf.beam_profile(1.0, 360.0, kind="sw")
        # F111: cualquier K (el legado da IndexError con K = 5 y 7)
        for Kx in (5, 7):
            with self.assertRaises(IndexError):
                ts.ebp_centres(Kx, 100, True)
        for Kx in (1, 2, 3, 5, 6, 7, 9):
            for center in (True, False):
                p = psf.beam_positions(Kx, 100.0, center=center)
                self.assertEqual(p.shape, (Kx, 2))
                ring = p[1:] if center else p
                if ring.shape[0]:
                    np.testing.assert_allclose(np.hypot(ring[:, 0], ring[:, 1]), 50.0, atol=1e-12)
                    if ring.shape[0] > 1:
                        ang = np.sort(np.mod(np.arctan2(ring[:, 1], ring[:, 0]), 2 * np.pi))
                        gaps = np.diff(np.append(ang, ang[0] + 2 * np.pi))
                        np.testing.assert_allclose(gaps, 2 * np.pi / ring.shape[0], atol=1e-12)
                if center:
                    np.testing.assert_allclose(p[0], 0.0)
        # el estimador funciona con K = 7
        pos7 = psf.beam_positions(7, 100.0, True)
        C7 = mx.mixing_matrix(TAU, T, 7, 0.0, 6.0)
        r0 = np.array([7.0, -3.0])
        pt = es.forward_probs(r0, pos7, FWHM, C7, 6.0, T, 21.0)
        est = es.mle_mixing(pt * 1e9, pos7, FWHM, C7, 6.0, T, 21.0, R_SEARCH)
        np.testing.assert_allclose(est.r, r0, atol=1e-5)
        with self.assertRaises(ValueError):
            psf.beam_positions(0, 100.0)


class TestEstimate(unittest.TestCase):

    def test_forward_model_consistent_with_mixing(self):
        """forward_probs = mixing.window_probs; legacy_probs = mixing.naive_probs; derivadas."""
        rng = np.random.default_rng(3)
        for r0 in rng.uniform(-40, 40, size=(6, 2)):
            lam = psf.lambda_beams(r0, POS, FWHM)
            for sbr in (21.05, 6.0, math.inf):
                np.testing.assert_allclose(es.forward_probs(r0, POS, FWHM, C_MEAS, B, T, sbr),
                                           mx.window_probs(lam, C_MEAS, B, T, sbr=sbr), rtol=1e-12)
                np.testing.assert_allclose(es.legacy_probs(r0, POS, FWHM, sbr),
                                           mx.naive_probs(lam, sbr), rtol=1e-12)
            Pw = np.array([21.02, 16.65, 22.96, 22.86])
            np.testing.assert_allclose(
                es.forward_probs(r0, POS, FWHM, C_MEAS, B, T, None, powers=Pw, bg=95 / 2095.),
                mx.window_probs(lam * Pw, C_MEAS, B, T, Ns=2000, Nb=95), rtol=1e-12)
        # derivadas analíticas del modelo (x, y, beta, logpow) contra diferencias finitas
        m = es._Model(POS, FWHM, C_MEAS, B / T)
        r = rng.uniform(-40, 40, size=(5, 2))
        beta = np.full(5, 0.07)
        lp = np.log([1.0, 0.8, 1.1, 1.3])
        p, dp, _ = m.probs_grad(r, beta, lp)
        h = 1e-6
        for k in range(2):
            e = np.zeros(2)
            e[k] = h
            fd = (m.probs(r + e, beta, lp) - m.probs(r - e, beta, lp)) / (2 * h)
            np.testing.assert_allclose(dp[:, k], fd, rtol=1e-5, atol=1e-11)
        fd = (m.probs(r, beta + h, lp) - m.probs(r, beta - h, lp)) / (2 * h)
        np.testing.assert_allclose(dp[:, 2], fd, rtol=1e-5, atol=1e-11)
        for k in range(1, K):
            e = np.zeros(K)
            e[k] = h
            fd = (m.probs(r, beta, lp + e) - m.probs(r, beta, lp - e)) / (2 * h)
            np.testing.assert_allclose(dp[:, 2 + k], fd, rtol=1e-5, atol=1e-11)

    def test_legacy_mle_bias_matches_F104(self):
        """F104 (antes): sesgo asintótico del MLE de la Ec. 3.5 en el setup medido sin IRF."""
        for Nb, ref, tol in ((95, F104_BIAS_SBR21, 0.05), (333, None, None)):
            sbr = NS / float(Nb)
            biases = []
            for r0 in POINTS:
                r0 = np.array(r0)
                pt = es.forward_probs(r0, POS, FWHM, C_MEAS, B, T, sbr)
                est = es.mle_legacy(pt * 1e9, POS, FWHM, sbr, R_SEARCH)
                self.assertTrue(est.converged and not est.on_boundary)
                biases.append(float(np.hypot(*(est.r - r0))))
            if ref is not None:
                np.testing.assert_allclose(biases, ref, atol=tol)
                # CRB de crb_minflux (N = Ns + Nb) 0.82-1.22 nm; el real 8.6-13.5 % mayor (F104)
                cl = es.crb_legacy(np.array(POINTS), POS, FWHM, sbr, NS + Nb)
                cm = es.crb(np.array(POINTS), POS, FWHM, C_MEAS, B, T, sbr, NS + Nb)
                self.assertAlmostEqual(cl.min(), 0.816, delta=0.005)
                self.assertAlmostEqual(cl.max(), 1.222, delta=0.005)
                self.assertAlmostEqual((cm / cl).min(), 1.086, delta=0.002)
                self.assertAlmostEqual((cm / cl).max(), 1.135, delta=0.002)
            else:   # SBR 6: 0.59-2.32 nm (F104)
                self.assertAlmostEqual(min(biases), 0.59, delta=0.05)
                self.assertAlmostEqual(max(biases), 2.32, delta=0.05)
        # la versión continua coincide con el MC: sesgo del legado sobre datos multinomiales
        rng = np.random.default_rng(104)
        r0 = np.array(POINTS[3])
        c = _multinomial(r0, 3000, 95, rng)
        est = es.mle_legacy(c, POS, FWHM, NS / 95., R_SEARCH)
        mean_bias = np.hypot(*(est.r.mean(0) - r0))
        se = np.sqrt(np.sum(est.r.var(0, ddof=1)) / 3000)
        self.assertLess(abs(mean_bias - F104_BIAS_SBR21[3]), 4 * se + 0.05)

    def test_mixing_mle_unbiased_at_measured_setup(self):
        """F104 (después): con C conocida el MLE no tiene sesgo y alcanza el CRB (N = 2095)."""
        rng = np.random.default_rng(20260928)
        n = 2000
        for r0 in POINTS:
            r0 = np.array(r0)
            # asintótico: exactamente la posición verdadera
            pt = es.forward_probs(r0, POS, FWHM, C_MEAS, B, T, NS / 95.)
            np.testing.assert_allclose(es.mle_mixing(pt * 1e9, POS, FWHM, C_MEAS, B, T, NS / 95.,
                                                     R_SEARCH).r, r0, atol=1e-6)
            c = _multinomial(r0, n, 95, rng)
            est = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, NS / 95., R_SEARCH)
            self.assertEqual(est.n_failed, 0)
            self.assertEqual(est.boundary_fraction, 0.0)
            d = est.r - r0
            se = d.std(0, ddof=1) / math.sqrt(n)
            self.assertTrue(np.all(np.abs(d.mean(0)) < 2.5 * se), (r0, d.mean(0), se))
            cr = es.crb(r0, POS, FWHM, C_MEAS, B, T, NS / 95., NS + 95)
            ratio = math.sqrt(np.mean(np.sum(d ** 2, 1))) / (math.sqrt(2) * cr)
            self.assertTrue(0.9 <= ratio <= 1.15, (r0, ratio))

    def test_continuous_offgrid_no_quantization(self):
        """F106/F205: el emisor fuera de la grilla se estima en su lugar, sin cuantizar."""
        r0 = np.array([-5.07, -7.56])
        pt = es.forward_probs(r0, POS, FWHM, C_MEAS, B, T, NS / 95.)
        est = es.mle_mixing(pt * 1e9, POS, FWHM, C_MEAS, B, T, NS / 95., R_SEARCH)
        np.testing.assert_allclose(est.r, r0, atol=1e-6)        # no (-5, -8)
        rng = np.random.default_rng(106)
        n = 3000
        c = _multinomial(r0, n, 95, rng)
        e = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, NS / 95., R_SEARCH).r
        se = e.std(0, ddof=1) / math.sqrt(n)
        self.assertTrue(np.all(np.abs(e.mean(0) - r0) < 3 * se))
        self.assertGreater(np.linalg.norm(e.mean(0) - np.array([-5.0, -8.0])), 0.3)
        # sin acumulación en nodos: la parte fraccionaria es ~uniforme
        frac = np.mod(e, 1.0).ravel()
        self.assertGreater(stats.kstest(frac, "uniform").pvalue, 1e-3)
        self.assertLess(np.mean(np.abs(e - np.rint(e)) < 1e-6), 1e-3)
        # un emisor en un nodo: RMSE/CRB ~ 1 (sin la supereficiencia de la grilla del legado)
        r1 = np.array([-5.0, -8.0])
        e1 = es.mle_mixing(_multinomial(r1, n, 95, rng), POS, FWHM, C_MEAS, B, T, NS / 95., R_SEARCH).r
        ratio = math.sqrt(np.mean(np.sum((e1 - r1) ** 2, 1))) / (
            math.sqrt(2) * es.crb(r1, POS, FWHM, C_MEAS, B, T, NS / 95., NS + 95))
        self.assertTrue(0.9 < ratio < 1.12, ratio)

    def test_sbr_inf(self):
        """F110: sbr = inf sin NaN (modelo, CRB y MLE), también con el emisor sobre un cero."""
        self.assertEqual(es.sbr_to_beta(math.inf), 0.0)
        for r0 in (np.array([5.0, -5.0]), POS[0].copy(), POS[3].copy()):
            pl = es.legacy_probs(r0, POS, FWHM, math.inf)
            pm = es.forward_probs(r0, POS, FWHM, C_MEAS, B, T, math.inf)
            self.assertTrue(np.all(np.isfinite(pl)) and np.all(np.isfinite(pm)))
            cl = es.crb_legacy(r0, POS, FWHM, math.inf, 2000)
            cm = es.crb(r0, POS, FWHM, C_MEAS, B, T, math.inf, 2000)
            self.assertTrue(np.isfinite(cl) and np.isfinite(cm), (r0, cl, cm))
        rng = np.random.default_rng(110)
        r0 = np.array([5.0, -5.0])
        q = psf.lambda_beams(r0, POS, FWHM)
        c = rng.multinomial(2000, q / q.sum(), size=500)
        est = es.mle_legacy(c, POS, FWHM, math.inf, R_SEARCH)
        self.assertTrue(np.all(np.isfinite(est.r)))
        self.assertEqual(est.n_failed, 0)
        self.assertLess(np.max(np.hypot(*(est.r - r0).T)), 10.0)
        # el legado: sbr=inf da (-100, 100) (F110, antes); v2 con 1e12 y con inf coinciden
        e12 = es.mle_legacy(c[:20], POS, FWHM, 1e12, R_SEARCH).r
        np.testing.assert_allclose(est.r[:20], e12, atol=1e-5)
        ts = _legacy()
        PSF = np.array([ts.psf(POS[i], 200, 1, [0, 0], d="donut") for i in range(4)])
        with np.errstate(all="ignore"), contextlib.redirect_stdout(io.StringIO()):
            idx = ts.pos_MINFLUX(c[0], PSF, np.inf, px_nm=1, r_max_nm=R_SEARCH)
        self.assertGreater(np.hypot(*ts.indexToSpace(idx, 200, 1)), 75.0)

    def test_crb_mixing_and_naive_limit(self):
        """CRB: con C = I, b = T/K coincide con el ingenuo; contra Fisher independiente."""
        rng = np.random.default_rng(5)
        rs = rng.uniform(-40, 40, size=(8, 2))
        for sbr in (math.inf, 21.05, 6.0):
            a = es.crb(rs, POS, FWHM, np.eye(K), T / K, T, sbr, 2095)
            b = es.crb_legacy(rs, POS, FWHM, sbr, 2095)
            np.testing.assert_allclose(a, b, rtol=1e-12)
            # Fisher independiente por diferencias finitas sobre mixing.naive_probs
            for r in rs[:3]:
                pf = lambda rr: mx.naive_probs(psf.lambda_beams(rr, POS, FWHM), sbr)
                self.assertAlmostEqual(_fd_crb(pf, r, 2095), b[list(rs[:, 0]).index(r[0])], delta=1e-5)
        # modelo de mezcla: Fisher independiente (diferencias finitas de mixing.window_probs,
        # N en ventanas = N * fracción capturada)
        for r in rs[:4]:
            sbr = 21.05
            pf = lambda rr: mx.window_probs(psf.lambda_beams(rr, POS, FWHM), C_MEAS, B, T, sbr=sbr)
            e = mx.window_expected(psf.lambda_beams(r, POS, FWHM), C_MEAS, B, T, 2000, 95)
            ref = _fd_crb(pf, r, e.sum())
            self.assertAlmostEqual(es.crb(r, POS, FWHM, C_MEAS, B, T, 2000 / 95., 2095), ref, delta=2e-5)
            self.assertAlmostEqual(es.crb(r, POS, FWHM, C_MEAS, B, T, 2000 / 95., e.sum(), n_is="windows"),
                                   ref, delta=2e-5)
            # con beta libre: Fisher 3x3 por diferencias finitas, marginalizado
            def pf3(th):
                return es.forward_probs(th[:2], POS, FWHM, C_MEAS, B, T, None, bg=th[2])
            th = np.array([r[0], r[1], 95 / 2095.])
            ref3 = _fd_crb_nuis(pf3, th, e.sum())
            self.assertAlmostEqual(es.crb(r, POS, FWHM, C_MEAS, B, T, 2000 / 95., 2095, free_bg=True),
                                   ref3, delta=1e-4)
        # referencia independiente verificada (donutloc), si está disponible
        dl = os.path.join(os.path.dirname(ROOT), "donut-beam-localization", "src")
        if os.path.isdir(dl):
            sys.path.insert(0, dl)
            try:
                from donutloc import fisher as dfis
            except Exception:  # pragma: no cover
                dfis = None
            if dfis is not None:
                pf = lambda rr: np.apply_along_axis(
                    lambda v: mx.naive_probs(psf.lambda_beams(v, POS, FWHM), 21.05), -1, rr)
                ref = dfis.crb(pf, rs, 2095)
                np.testing.assert_allclose(es.crb_legacy(rs, POS, FWHM, 21.05, 2095), ref, rtol=1e-6)
        # potencias libres con una sola posición: no identificable -> inf
        self.assertTrue(np.isinf(es.crb(np.array([5.0, -5.0]), POS, FWHM, C_MEAS, B, T, 21.05, 2095,
                                        free_powers=True)))

    def test_free_powers_removes_bias(self):
        """F202: potencias distintas por haz; ignorarlas sesga, estimarlas (compartidas) no."""
        Pw = np.array([21.02, 16.65, 22.96, 22.86])
        rng = np.random.default_rng(202)
        n = 300
        pts = np.array(POINTS)
        R0 = np.repeat(pts, n, axis=0)
        c = np.vstack([_multinomial(r, n, 95, rng, powers=Pw) for r in pts])
        sbr = NS / 95.
        eq = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH)
        kn = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, powers=Pw)
        fr = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, free_powers=True)
        self.assertTrue(fr.globals_result["success"])
        bias = lambda e: np.hypot(*(e.r - R0).reshape(5, n, 2).mean(1).T)
        self.assertGreater(bias(eq).min(), 2.0)                   # sin potencias: sesgo de nm
        self.assertLess(bias(kn).max(), 0.3)                      # potencias conocidas
        self.assertLess(bias(fr).max(), 0.5)                      # potencias estimadas
        np.testing.assert_allclose(fr.powers / fr.powers[0], Pw / Pw[0], rtol=0.03)
        # el CRB conjunto con potencias libres es finito y mayor que con potencias conocidas
        cf = es.crb(R0, POS, FWHM, C_MEAS, B, T, sbr, NS + 95, powers=Pw, free_powers=True)
        ck = es.crb(R0, POS, FWHM, C_MEAS, B, T, sbr, NS + 95, powers=Pw)
        self.assertTrue(np.all(np.isfinite(cf)) and np.all(cf >= ck * (1 - 1e-9)))

    def test_free_background(self):
        """beta libre por localización (y compartido) corrige un SBR mal supuesto."""
        rng = np.random.default_rng(7)
        r0 = np.array([-15.0, 15.0])
        n = 1500
        c = _multinomial(r0, n, 333, rng)                         # SBR verdadero 6
        wrong = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, 21.05, R_SEARCH)   # supone SBR 21
        loc = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, 21.05, R_SEARCH, free_bg=True)
        sh = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, 21.05, R_SEARCH, free_bg="shared")
        for e in (loc, sh):
            d = e.r - r0
            se = d.std(0, ddof=1) / math.sqrt(n)
            self.assertTrue(np.all(np.abs(d.mean(0)) < 3 * se), d.mean(0) / se)
        dw = wrong.r - r0
        self.assertGreater(np.hypot(*dw.mean(0)), 5 * np.hypot(*(dw.std(0, ddof=1) / math.sqrt(n))))
        beta_true = 333 / 2333.
        self.assertAlmostEqual(sh.beta[0], beta_true, delta=0.1 * beta_true)
        self.assertAlmostEqual(float(np.mean(loc.beta)), beta_true, delta=0.1 * beta_true)
        cr = es.crb(r0, POS, FWHM, C_MEAS, B, T, 6.006, NS + 333, free_bg=True)
        ratio = math.sqrt(np.mean(np.sum((loc.r - r0) ** 2, 1))) / (math.sqrt(2) * cr)
        self.assertTrue(0.88 <= ratio <= 1.15, ratio)
        self.assertGreaterEqual(cr, es.crb(r0, POS, FWHM, C_MEAS, B, T, 6.006, NS + 333))

    def test_boundary_fraction_reported(self):
        """F203: la fracción en el borde se informa y el óptimo acotado es el correcto."""
        rng = np.random.default_rng(203)
        r0 = np.array([20.0, 0.0])
        c = _multinomial(r0, 400, 95, rng)
        sbr = NS / 95.
        small = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, 10.0)
        self.assertEqual(small.boundary_fraction, 1.0)
        self.assertTrue(np.all(small.converged))
        np.testing.assert_allclose(np.hypot(*small.r.T), 10.0, atol=1e-9)
        # el óptimo sobre el círculo coincide con una búsqueda densa en el ángulo
        ph = np.linspace(-np.pi, np.pi, 400001)
        G = 10.0 * np.column_stack([np.cos(ph), np.sin(ph)])
        lg = np.log(es.forward_probs(G, POS, FWHM, C_MEAS, B, T, sbr))
        best = G[np.argmax(c[:40].dot(lg.T), axis=1)]
        np.testing.assert_allclose(small.r[:40], best, atol=2e-3)
        big = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH)
        self.assertEqual(big.boundary_fraction, 0.0)
        # interior contra borde mezclados: la fracción es la de las estimaciones libres fuera
        mid = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, 20.3)
        expect = np.mean(np.hypot(*big.r.T) > 20.3)
        self.assertAlmostEqual(mid.boundary_fraction, expect, delta=0.02)
        self.assertTrue(0.1 < mid.boundary_fraction < 0.9)
        inside = ~mid.on_boundary
        np.testing.assert_allclose(mid.r[inside], big.r[inside], atol=1e-4)  # nm
        # localización sin cuentas: NaN y contada como falla
        c2 = c[:5].copy()
        c2[2] = 0
        e2 = es.mle_mixing(c2, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH)
        self.assertTrue(np.all(np.isnan(e2.r[2])))
        self.assertEqual(e2.n_failed, 1)
        with self.assertRaises(ValueError):
            es.mle_mixing(-c[:3], POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH)
        with self.assertRaises(ValueError):
            es.mle_mixing(c[:3], POS, FWHM, C_MEAS, B, T, sbr, 0.0)

    def test_cov_ellipse_orientation(self):
        """F108: eje mayor en la dirección correcta y ejes con el factor chi2(q, 2)."""
        ts = _legacy()
        for phi in (0.0, 30.0, 60.0, 120.0, 150.0, -45.0):
            c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
            Rm = np.array([[c, -s], [s, c]])
            cov = Rm.dot(np.diag([9.0, 1.0])).dot(Rm.T)
            for nsig in (1, 2):
                w, h, ang = es.cov_ellipse(cov, nsig=nsig)
                r2 = stats.chi2.ppf(2 * stats.norm.cdf(nsig) - 1, 2)
                self.assertAlmostEqual(w, 2 * math.sqrt(9 * r2), places=10)
                self.assertAlmostEqual(h, 2 * math.sqrt(r2), places=10)
                err = (ang - phi + 90.0) % 180.0 - 90.0
                self.assertAlmostEqual(err, 0.0, places=8)
            with contextlib.redirect_stdout(io.StringIO()):
                wl, hl, _ = ts.cov_ellipse(cov, nsig=1)
            # el legado: ejes 2 y 6 siempre (sin r2)
            self.assertAlmostEqual(float(np.ravel(wl)[0]) * float(np.ravel(hl)[0]), 12.0, places=8)
        w, h, ang = es.cov_ellipse(np.diag([4.0, 1.0]), q=0.5)
        self.assertAlmostEqual(w, 2 * math.sqrt(4 * stats.chi2.ppf(0.5, 2)), places=12)
        self.assertAlmostEqual(ang, 0.0, places=12)
        self.assertAlmostEqual(es.cov_ellipse(np.diag([1.0, 4.0]))[2], 90.0, places=12)
        for bad in (np.eye(3), np.array([[1.0, 2.0], [0.0, 1.0]]), np.diag([1.0, -1.0])):
            with self.assertRaises(ValueError):
                es.cov_ellipse(bad)


def _fd_crb(pf, r, N, h=1e-4):
    r = np.asarray(r, float)
    g = [(pf(r + e) - pf(r - e)) / (2 * h) for e in (np.array([h, 0]), np.array([0, h]))]
    p = pf(r)
    F = N * np.array([[np.sum(a * b / p) for b in g] for a in g])
    return math.sqrt(0.5 * np.trace(np.linalg.inv(F)))


def _fd_crb_nuis(pf, th, N):
    hs = np.array([1e-4, 1e-4, 1e-6])
    g = []
    for k in range(3):
        e = np.zeros(3)
        e[k] = hs[k]
        g.append((pf(th + e) - pf(th - e)) / (2 * hs[k]))
    p = pf(th)
    F = N * np.array([[np.sum(a * b / p) for b in g] for a in g])
    cov = np.linalg.inv(F)
    return math.sqrt(0.5 * (cov[0, 0] + cov[1, 1]))


class TestChunkAndConvergence(unittest.TestCase):
    """R3: arranque en grilla por bloques (idéntico) y converged=True en el óptimo al agotar maxiter."""

    def test_chunked_grid_start_identical(self):
        rng = np.random.default_rng(66)
        c = np.vstack([_multinomial(r0, 40, 95, rng) for r0 in POINTS])       # 200 locs
        sbr = NS / 95.
        for kw in (dict(), dict(free_bg=True), dict(free_bg="shared")):
            a = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, **kw)
            b = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, chunk=7, **kw)
            np.testing.assert_array_equal(a.r, b.r)
            np.testing.assert_array_equal(a.converged, b.converged)
            np.testing.assert_array_equal(a.beta, b.beta)
        a = es.mle_legacy(c, POS, FWHM, sbr, R_SEARCH)
        b = es.mle_legacy(c, POS, FWHM, sbr, R_SEARCH, chunk=1)
        np.testing.assert_array_equal(a.r, b.r)
        # potencias libres: la grilla se recalcula en cada evaluación del perfil
        c2 = c[::4]
        a = es.mle_mixing(c2, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, free_powers=True)
        b = es.mle_mixing(c2, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, free_powers=True, chunk=9)
        np.testing.assert_array_equal(a.r, b.r)
        np.testing.assert_array_equal(a.powers, b.powers)
        with self.assertRaises(ValueError):
            es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, chunk=0)

    def test_converged_flag_at_optimum_low_N(self):
        # U5 (code-reviewer R2): con N = 10-50, ~0.7 % llegaba a maxiter = 200 con converged=False
        # estando ya en el óptimo. Ahora: converged=True si la NLL mejoró <= 1e-6 en las últimas
        # 10 iteraciones. Las estimaciones no cambian (solo el flag).
        rng = np.random.default_rng(5)
        cs, sb = [], []
        for N in (10, 20, 30, 50):
            for sbr in (math.inf, 5.0, 21.0):
                r0 = rng.uniform(-30, 30, size=(500, 2))
                lam = psf.lambda_beams(r0, POS, FWHM)
                q = lam / lam.sum(1, keepdims=True)
                beta = es.sbr_to_beta(sbr)
                e = (1 - beta) * q.dot(C_MEAS.T) + beta * B / T
                pr = e / e.sum(1, keepdims=True)
                cs.append(np.array([rng.multinomial(N, pp) for pp in pr]))
                sb.append(sbr)
        n_bad = n_at_max = 0
        for c, sbr in zip(cs, sb):
            res = es.mle_mixing(c, POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH)
            n_bad += int(np.sum(~res.converged))
            hit = np.nonzero(res.n_iter >= 200)[0]
            n_at_max += hit.size
            if hit.size:
                ref = es.mle_mixing(c[hit], POS, FWHM, C_MEAS, B, T, sbr, R_SEARCH, maxiter=5000)
                gap = res.nll[hit] - ref.nll
                # los marcados convergidos están a <= 1e-5 del óptimo (y a < 0.05 nm)
                ok = res.converged[hit]
                self.assertTrue(np.all(gap[ok] <= 1e-5), gap[ok])
                self.assertTrue(np.all(np.hypot(*(res.r[hit][ok] - ref.r[ok]).T) < 0.05))
                # los que siguen converged=False de verdad no llegaron (gap > 1e-6)
                self.assertTrue(np.all(gap[~ok] > 1e-6), gap[~ok])
        print("\n[converged_low_N] n=6000 at_maxiter=%d converged_False=%d" % (n_at_max, n_bad))
        self.assertLessEqual(n_bad, 12)                    # antes 43/6000; ahora 5/6000
        # con maxiter = 1 desde la grilla no se declara convergencia falsa
        r1 = es.mle_mixing(cs[-1][:50], POS, FWHM, C_MEAS, B, T, sb[-1], R_SEARCH, maxiter=1)
        self.assertLess(np.mean(r1.converged), 0.5)


class TestMixingConditioning(unittest.TestCase):
    """R3 (code-reviewer): aviso cuando C es casi singular (trampa de migración al emular
    sim_exp con la IRF por defecto: tau = 0.001, b = T/K, IRF 0.3 manda ~50 % de cada haz a la
    ventana anterior)."""

    def _warns(self, fn):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            out = fn()
        return out, [x for x in w if "casi singular" in str(x.message)]

    def test_warns_on_nearly_singular_C(self):
        C_bad = mx.mixing_matrix(0.001, 25.0, K, 0.0, 6.25, irf_fwhm=0.3)
        cond, smin = es.mixing_conditioning(C_bad, warn=False)
        self.assertLess(smin, es.SMIN_MIN)                 # s_min = 0.0063, cond = 160
        pos = psf.beam_positions(K, L, center=True)
        cnt = np.array([[500, 520, 480, 510]])
        _, w = self._warns(lambda: es.mle_mixing(cnt, pos, FWHM, C_bad, 6.25, 25.0, 9.0, 75.0))
        self.assertEqual(len(w), 1)
        self.assertTrue(issubclass(w[0].category, UserWarning))
        _, w = self._warns(lambda: es.crb([5.0, -5.0], pos, FWHM, C_bad, 6.25, 25.0, 9.0, 100))
        self.assertEqual(len(w), 1)
        # umbral de condición: una C bien escalada pero con cond > 1e3 también avisa
        C_cond = np.diag([1.0, 1.0, 1.0, 5e-4])
        self.assertGreater(es.mixing_conditioning(C_cond, warn=False)[0], es.COND_MAX)
        self.assertEqual(len(self._warns(lambda: es.mixing_conditioning(C_cond))[1]), 1)

    def test_no_warning_for_measured_setup_and_sim_exp_emulation(self):
        pos = psf.beam_positions(K, L, center=True)
        for C, b, TT in [(mx.mixing_matrix(TAU, T, K, A, B, irf_fwhm=0.3), B, T),   # setup medido
                         (C_MEAS, B, T),
                         (mx.mixing_matrix(0.001, 25.0, K, 0.0, 6.25), 6.25, 25.0)]:  # sim_exp, IRF 0
            (cond, smin), w = self._warns(lambda: es.mixing_conditioning(C))
            self.assertEqual(w, [])
            self.assertLess(cond, 2.0)
            _, w = self._warns(lambda: es.crb([5.0, -5.0], pos, FWHM, C, b, TT, 21.0, 2095))
            self.assertEqual(w, [])
        # mle_legacy (C = I) nunca avisa
        _, w = self._warns(lambda: es.mle_legacy(np.array([[500, 520, 480, 510]]), pos, FWHM,
                                                 21.0, 75.0))
        self.assertEqual(w, [])


class TestCompare(unittest.TestCase):

    REQUIRED_EST = ("bias_x", "bias_y", "bias_abs", "sigma_x", "sigma_y", "rmse_2d", "rmse_over_crb")

    def _check(self, r, n_irf):
        for k in ("source", "source_requested", "setup", "geometry", "Ns", "Nb", "seed", "seed_rule",
                  "n_loc", "n_boot", "versions", "runtime_s", "positions_nm", "irf_fwhm_ns",
                  "legacy_crosscheck_pos_MINFLUX", "N_convention", "crb_definition"):
            self.assertIn(k, r)
        self.assertIn(r["source"], ("v2sim", "multinomial"))
        for k in ("tau", "a", "b", "T", "K", "rate_per_cycle", "dead_time", "tcspc", "counting", "n_mode"):
            self.assertIn(k, r["setup"])
        self.assertEqual(len(r["cases"]), 5 * 2 * n_irf)
        combos = {(c["irf_fwhm_ns"], c["sbr_label"], tuple(c["position_nm"])) for c in r["cases"]}
        self.assertEqual(len(combos), 5 * 2 * n_irf)
        for c in r["cases"]:
            self.assertIn("seed", c)
            for name in ("legacy", "mixing", "mixing_freebg"):
                m = c["estimators"][name]
                for k in self.REQUIRED_EST:
                    self.assertTrue(np.isfinite(m[k]), (name, k))
                    self.assertTrue(np.isfinite(m[k + "_se"]) and m[k + "_se"] > 0, (name, k))
                for k in ("crb_axis_nm", "boundary_fraction", "n_failed", "bias_vec"):
                    self.assertIn(k, m)
        x = r["legacy_crosscheck_pos_MINFLUX"]
        self.assertEqual(x["frac_within_1px_per_axis"], 1.0)
        # F104: el sesgo asintótico del legado (IRF 0, SBR 21) es el verificado
        asym = [c["legacy_asymptotic_bias_nm"] for c in r["cases"]
                if c["irf_fwhm_ns"] == 0.0 and c["sbr_label"] == "SBR21"]
        np.testing.assert_allclose(asym, F104_BIAS_SBR21, atol=0.05)

    def test_compare_json_complete(self):
        """F204 (SE bootstrap) y F206 (todos los parámetros en el JSON)."""
        import compare_legacy_vs_v2 as cmp
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "cmp.json")
            with contextlib.redirect_stdout(io.StringIO()):
                cmp.run(source="multinomial", n_loc=60, seed=1, n_boot=40, quick=True, out=out,
                        irfs=[0.0], verbose=False)
            with open(out, encoding="utf-8") as fh:
                r = json.load(fh)
            self.assertEqual(r["source"], "multinomial")
            self._check(r, 1)
        path = os.path.join(ROOT, "results", "compare_legacy_vs_v2.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                r = json.load(fh)
            self.assertFalse(r["quick"])
            self._check(r, 2)
            self.assertGreaterEqual(r["n_loc"], 2000)
            # R3: el JSON del repositorio tiene que venir del simulador v2 y del código ACTUAL
            self.assertEqual(r["source"], "v2sim")
            self.assertEqual(r["source_requested"], "v2sim")
            sha = r["versions"]["sha256"]
            for mod in ("mixing", "psf", "estimate", "simulate"):
                self.assertEqual(sha[mod], cmp._sha(os.path.join(ROOT, "src", "pminflux_sim",
                                                                  mod + ".py")),
                                 "results/compare_legacy_vs_v2.json desactualizado respecto de "
                                 "%s.py: regenerar con scripts/compare_legacy_vs_v2.py" % mod)
            self.assertEqual(sha["compare_legacy_vs_v2"],
                             cmp._sha(os.path.join(ROOT, "scripts", "compare_legacy_vs_v2.py")))


if __name__ == "__main__":
    unittest.main()
