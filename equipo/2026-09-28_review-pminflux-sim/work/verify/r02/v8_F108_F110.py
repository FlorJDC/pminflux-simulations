# -*- coding: utf-8 -*-
"""(2d) behaviour tests of estimate.py (the claim): F108 cov_ellipse, F110 sbr=inf."""
import sys, os, math
import numpy as np
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, HERE)
from pminflux_sim import estimate as es, psf, mixing as mx
from myest import POS
rng = np.random.default_rng(1)
worst = 0
for phi in [0, 30, 60, 90, 120, 150, -45, 89.9, -89.9, 179]:
    for (l1, l2) in [(9.0, 1.0), (4.0, 3.9), (1.0, 0.01)]:
        R = np.array([[math.cos(math.radians(phi)), -math.sin(math.radians(phi))], [math.sin(math.radians(phi)), math.cos(math.radians(phi))]])
        cov = R @ np.diag([l1, l2]) @ R.T
        w, h, a = es.cov_ellipse(cov)
        r2 = stats.chi2.ppf(2 * stats.norm.cdf(1) - 1, 2)
        exp_a = (phi + 90) % 180 - 90
        da = min(abs(a - exp_a), 180 - abs(a - exp_a))
        worst = max(worst, da, abs(w - 2 * math.sqrt(r2 * l1)), abs(h - 2 * math.sqrt(r2 * l2)))
        # independent check: points on the ellipse boundary have Mahalanobis^2 = r2
        t = np.linspace(0, 2 * np.pi, 7)
        ar = math.radians(a)
        pts = np.c_[w / 2 * np.cos(t) * math.cos(ar) - h / 2 * np.sin(t) * math.sin(ar), w / 2 * np.cos(t) * math.sin(ar) + h / 2 * np.sin(t) * math.cos(ar)]
        md = np.einsum("ij,jk,ik->i", pts, np.linalg.inv(cov), pts)
        worst = max(worst, np.max(np.abs(md - r2)))
print("F108 worst error (deg / nm / mahal):", worst)
# F110: sbr = inf
C = mx.mixing_matrix(4.21, 50, 4, 0, 10.1)
pos = psf.beam_positions(4, 100.0, center=True)
print("pos vs mine", np.abs(np.asarray(pos) - POS).max())
for r in [(5, -5), (0, 0), (20, 0)]:
    p = es.forward_probs(np.array(r, float), pos, 360.0, C, 10.1, 50.0, math.inf)
    c = es.crb(np.array(r, float), pos, 360.0, C, 10.1, 50.0, math.inf, 2000)
    print("F110 r", r, "probs finite", np.all(np.isfinite(p)), "crb", c)
lam = psf.lambda_beams(np.array([5.0, -5.0]), pos, 360.0)
e = mx.window_expected(lam, C, 10.1, 50, 2000, 0)
cnt = rng.multinomial(2000, np.r_[e / 2000, 1 - e.sum() / 2000], size=200)[:, :4]
fit = es.mle_mixing(cnt, pos, 360.0, C, 10.1, 50.0, math.inf, 75.0)
fl = es.mle_legacy(cnt, pos, 360.0, math.inf, 75.0)
print("F110 mle_mixing finite", np.all(np.isfinite(fit.r)), "bias", fit.r.mean(0) - [5, -5], "legacy finite", np.all(np.isfinite(fl.r)))
