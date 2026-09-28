# -*- coding: utf-8 -*-
"""F108 - cov_ellipse (tools_simulations.py l.53-91):
  * LA.eig returns eigenvectors as COLUMNS, but l.86 reorders ROWS (vec[order], should be
    vec[:, order]);
  * l.90 uses arctan2(*vec[:, 0]) = arctan2(v_x, v_y) (the usual recipe is arctan2(v_y, v_x));
  * the confidence scale r2 = chi2.ppf(q, 2) is computed and printed but not used (l.87-88), so
    q / nsig have no effect: the axes are always 2*sqrt(eigenvalue).
Test: covariances with principal std 3 and 1 nm, major axis at angle phi.  The returned
(w, h, theta) is interpreted as matplotlib.patches.Ellipse(width=w, height=h, angle=theta), the
use the docstring implies; we report the direction of the returned MAJOR axis vs phi, and the
axis lengths vs the correct 2*sqrt(r2*eigenvalue).
The function is not called by any script in legacy/ (grep), so the impact is latent.
Run: python scripts/findings/F108_cov_ellipse.py
"""
import os
import sys
import io
import json
import contextlib

import matplotlib
matplotlib.use("Agg")
import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402


def main():
    out = {}
    for phi in (0.0, 30.0, 60.0, 120.0, 150.0):
        c, s = np.cos(np.radians(phi)), np.sin(np.radians(phi))
        R = np.array([[c, -s], [s, c]])
        cov = R.dot(np.diag([9.0, 1.0])).dot(R.T)
        res = {}
        for nsig in (1, 2):
            with contextlib.redirect_stdout(io.StringIO()):
                w, h, theta = ts.cov_ellipse(cov, nsig=nsig)
            w, h, theta = float(np.ravel(w)[0]), float(np.ravel(h)[0]), float(theta)
            major_dir = theta if w >= h else theta + 90.0      # Ellipse: width along `angle`
            major_dir = (major_dir + 90.0) % 180.0 - 90.0
            err = (major_dir - phi + 90.0) % 180.0 - 90.0
            q = 2 * stats.norm.cdf(nsig) - 1
            r2 = stats.chi2.ppf(q, 2)
            res["nsig=%d" % nsig] = {"w": w, "h": h, "theta_deg": theta,
                                     "returned_major_axis_dir_deg": major_dir,
                                     "angle_error_deg": err,
                                     "correct_major_len": float(2 * np.sqrt(9 * r2)),
                                     "correct_minor_len": float(2 * np.sqrt(1 * r2))}
        out["phi=%g" % phi] = res
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
