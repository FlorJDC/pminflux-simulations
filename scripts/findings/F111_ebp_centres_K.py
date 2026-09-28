# -*- coding: utf-8 -*-
"""F111 - ebp_centres (tools_simulations.py l.246-295) hard-codes L = [L, L, L, L] (l.266), so any
K > 4 (e.g. the hexagonal K = 7 pattern) raises IndexError; the parity comments are swapped
("if K is odd" on the K-even branch, l.273/l.278/l.284/l.289).  For K = 4 it agrees with the
older beams() (both put the peripheral zeros at 120, 240, 0 deg, vertex towards +x), which is
NOT the convention of tools/ebp.ideal_positions (vertex up: 210, 330, 90 deg).  That mismatch was
already documented in donut-beam-localization/docs/private/C_pminflux_practice.md section 5.2;
the author made ebp.py the single source of truth and the current study scripts use it.
Run: python scripts/findings/F111_ebp_centres_K.py
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
from tools import ebp as E  # noqa: E402


def main():
    out = {}
    for K in (4, 5, 7):
        try:
            ts.ebp_centres(K, 100.0, True)
            out["ebp_centres_K=%d" % K] = "ok"
        except IndexError as e:
            out["ebp_centres_K=%d" % K] = "IndexError: %s" % e
    a = ts.ebp_centres(4, 100.0, True)
    b = np.array([ts.beams(4, 100.0, center=True, d='donut')[k] for k in range(4)])
    c = E.ideal_positions(100.0, 4, vertex_up=True)
    ang = lambda P: [float(np.degrees(np.arctan2(p[1], p[0])) % 360) for p in P[1:]]
    out["max_abs_diff_ebp_centres_vs_beams_nm"] = float(np.max(np.abs(a - b)))
    out["peripheral_angles_ebp_centres_deg"] = ang(a)
    out["peripheral_angles_ebp_ideal_positions_deg"] = ang(c)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
