# -*- coding: utf-8 -*-
"""(2c) chunked grid start: identical results with chunk=13/1 vs default (fixed, free_bg, legacy, free_powers)."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "src")))
from pminflux_sim import estimate as es, mixing as mx, psf, simulate as sim
pos = psf.beam_positions(4, 100.0); C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, 0.3)
rng = np.random.default_rng(3)
cnt = np.vstack([sim.simulate_counts(psf.lambda_beams(np.array(r), pos, 360.0), 20, 400, 21.0,
                 rng=rng) for r in [(5, -5), (-20, 10), (0, 30)]])
out = {}
for name, kw, f in [("fixed", {}, es.mle_mixing), ("free_bg", {"free_bg": True}, es.mle_mixing),
                    ("free_powers", {"free_powers": True}, es.mle_mixing)]:
    a = f(cnt, pos, 360.0, C, 10.1, 50.0, 21.0, 75.0, **kw)
    b = f(cnt, pos, 360.0, C, 10.1, 50.0, 21.0, 75.0, chunk=13, **kw)
    c = f(cnt, pos, 360.0, C, 10.1, 50.0, 21.0, 75.0, chunk=1, **kw)
    out[name] = bool(np.array_equal(a.r, b.r) and np.array_equal(a.r, c.r) and np.array_equal(a.converged, c.converged)
                     and np.array_equal(np.asarray(a.powers), np.asarray(c.powers)))
a = es.mle_legacy(cnt, pos, 360.0, 21.0, 75.0); c = es.mle_legacy(cnt, pos, 360.0, 21.0, 75.0, chunk=1)
out["legacy"] = bool(np.array_equal(a.r, c.r))
try:
    es.mle_mixing(cnt, pos, 360.0, C, 10.1, 50.0, 21.0, 75.0, chunk=0); out["chunk0"] = "no error"
except ValueError:
    out["chunk0"] = "ValueError"
print(out); json.dump(out, open(os.path.join(os.path.dirname(__file__), "v5_chunk.json"), "w"))
