# -*- coding: utf-8 -*-
import unittest

import numpy as np

from tools.ebp import EBP, Grid
from tools.realistic_ebp import (donut_2d, ebp_realistic, image_metrics,
                                 refine_minimum_quadratic)


class RealisticEbpTests(unittest.TestCase):
    def setUp(self):
        self.grid = Grid(101, 2.0)
        self.params = {
            'x0_nm': 0.4, 'y0_nm': -0.6,
            'fwhm_x_nm': 180.0, 'fwhm_y_nm': 220.0,
            'shared_fwhm_nm': 200.0,
            'theta_rad': 0.3, 'pedestal': 0.1, 'amplitude': 0.8,
            'gradient_x_per_nm': 1e-4, 'gradient_y_per_nm': -2e-4,
        }

    def test_generated_psf_is_positive_and_finite(self):
        psf = donut_2d(self.params, self.grid)
        self.assertEqual(psf.shape, (101, 101))
        self.assertTrue(np.all(np.isfinite(psf)))
        self.assertTrue(np.all(psf > 0))

    def test_quadratic_refinement_finds_synthetic_minimum(self):
        rows, cols = np.indices((101, 101))
        x = cols * self.grid.px_nm - self.grid.size_nm / 2
        y = self.grid.size_nm / 2 - rows * self.grid.px_nm
        expected = np.array([0.35, -0.45])
        image = (x - expected[0]) ** 2 + 1.7 * (y - expected[1]) ** 2
        fitted = refine_minimum_quadratic(image, self.grid)
        np.testing.assert_allclose(fitted, expected, atol=1e-10)

    def test_identity_metrics_are_zero(self):
        params = [dict(self.params) for _ in range(4)]
        for k, p in enumerate(params):
            p['x0_nm'] += k
        ebp = ebp_realistic(params, self.grid)
        metrics = image_metrics(ebp, ebp)
        self.assertTrue(all(row['rmse_roi'] == 0 for row in metrics))

    def test_ebp_constructor_preserves_fitted_centers(self):
        params = [dict(self.params) for _ in range(4)]
        ebp = ebp_realistic(params, self.grid)
        expected = np.array([[self.params['x0_nm'], self.params['y0_nm']]] * 4)
        np.testing.assert_allclose(ebp.pos_nm, expected)
        self.assertIsInstance(ebp, EBP)


if __name__ == '__main__':
    unittest.main()
