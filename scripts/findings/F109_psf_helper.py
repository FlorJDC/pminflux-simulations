# -*- coding: utf-8 -*-
"""F109 - psf() (tools_simulations.py l.160-201) has three latent defects:
  (1) d='gaussian' ignores donut_fwhm (l.196 calls gaussian(Mro) with the module fwhm = 360);
  (2) any other d goes to SW(central_zero, size, wvlen, theta, fov_center) (l.199), but SW and
      theta are not defined anywhere -> NameError;
  (3) fov_center shifts the x grid by -c_x (l.181) but, through meshgrid(x, -y), the y grid by
      +c_y (l.182, l.185): the FOV centre ends up at (-c_x, +c_y) instead of (c_x, c_y).
All scripts in legacy/ call psf with d='donut' and fov_center=[0, 0] (grep), so none of the
published numbers is affected.
Run: python scripts/findings/F109_psf_helper.py
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
from tools import tools_simulations as ts  # noqa: E402


def main():
    out = {}
    size, px = 400.0, 1.0
    # (1) gaussian ignores donut_fwhm: measure the FWHM of the returned profile
    g = ts.psf([0, 0], size, px, [0, 0], d='gaussian', donut_fwhm=250.0)
    row = g[int(size / 2), :]
    x = np.arange(-size / 2, size / 2, px)
    above = x[row >= 0.5 * row.max()]
    out["gaussian_requested_fwhm_nm"] = 250.0
    out["gaussian_measured_fwhm_nm"] = float(above.max() - above.min() + px)
    # (2) SW branch
    try:
        ts.psf([0, 0], size, px, [0, 0], d='sw')
        out["sw_branch"] = "no error"
    except NameError as e:
        out["sw_branch"] = "NameError: %s" % e
    # (3) fov_center sign: zero of a donut at (0, 0) with fov_center = (20, 20)
    c = (20.0, 20.0)
    d = ts.psf([0, 0], size, px, list(c), d='donut')
    i, j = np.unravel_index(np.argmin(d), d.shape)
    # pixel -> coordinate of the grid actually built by psf()
    xg = np.arange(-size / 2 - c[0], size / 2 - c[0], px)
    yg = -np.arange(-size / 2 - c[1], size / 2 - c[1], px)
    out["fov_center_requested_nm"] = list(c)
    out["grid_centre_actual_nm"] = [float(xg.mean()), float(yg.mean())]
    out["zero_pixel_index_rowcol"] = [int(i), int(j)]
    out["zero_pixel_via_indexToSpace_nm"] = ts.indexToSpace((i, j), size, px).tolist()
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
