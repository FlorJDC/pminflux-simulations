# -*- coding: utf-8 -*-
"""Tests de usabilidad (ronda 3, W1): API pública del paquete, ejemplo mínimo rápido, el ejemplo
de punta a punta y el JSON del estudio v2 (``results/study_v2.json``)."""

import contextlib
import io
import json
import math
import os
import re
import sys
import time
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import pminflux_sim as pm  # noqa: E402


from provenance_sha import sha256_file as _sha  # noqa: E402  (fin de línea normalizado)


class TestPublicAPI(unittest.TestCase):

    def test_imports(self):
        self.assertEqual(pm.__version__, "2.0.0")
        for mod in ("mixing", "simulate", "estimate", "psf", "windows"):
            self.assertTrue(hasattr(pm, mod), mod)
            self.assertIn(mod, pm.__all__)
        for name in ("SimParams", "simulate_counts", "mle_mixing", "mle_legacy", "crb",
                     "mixing_matrix", "window_probs", "count_windows", "beam_positions",
                     "lambda_beams", "cov_ellipse",
                     # lo que ya exportaba la ronda 1
                     "window_expected", "naive_probs", "pearson_chi2", "occupancy_pattern_probs",
                     "sim_exp_window_probs"):
            self.assertTrue(callable(getattr(pm, name)), name)
            self.assertIn(name, pm.__all__)
        for name in pm.__all__:
            self.assertTrue(hasattr(pm, name), name)
        self.assertIs(pm.simulate_counts, pm.simulate.simulate_counts)
        self.assertIs(pm.count_windows, pm.windows.count_windows)
        # `from pminflux_sim import *` no rompe
        ns = {}
        exec("from pminflux_sim import *", ns)
        self.assertIn("mle_mixing", ns)

    def test_readme_api_table_importable(self):
        # R3 (code-reviewer): README §4 dice que todo lo de la tabla se importa de pminflux_sim;
        # antes check_overlap, donut y gaussian daban AttributeError.
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            txt = fh.read()
        sec = txt.split("## 4. Módulos y API", 1)[1].split("\n## 5.", 1)[0]
        names = set()
        for line in sec.splitlines():
            if line.startswith("| `"):
                cols = [c.strip() for c in line.strip().strip("|").split("|")]
                names.update(n for n in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", cols[-1]))
        self.assertGreaterEqual(len(names), 20)
        for n in ("check_overlap", "donut", "gaussian", "mixing_matrix_starts", "window_starts",
                  "mixing_conditioning"):
            self.assertIn(n, names)
        for n in sorted(names):
            self.assertTrue(hasattr(pm, n), "pm.%s no existe (README §4)" % n)
            self.assertIn(n, pm.__all__)
        self.assertIs(pm.donut, pm.psf.donut)
        self.assertIs(pm.check_overlap, pm.windows.check_overlap)

    def test_sha_robust_to_line_endings(self):
        # R3: el sha256 de procedencia no cambia con CRLF (git autocrlf en Windows).
        import hashlib
        import tempfile
        src = os.path.join(ROOT, "src", "pminflux_sim", "mixing.py")
        with open(src, "rb") as fh:
            data = fh.read()
        lf = data.replace(b"\r\n", b"\n")
        with tempfile.TemporaryDirectory() as d:
            p_lf, p_crlf, p_png = (os.path.join(d, n) for n in ("a.py", "b.py", "c.png"))
            with open(p_lf, "wb") as fh:
                fh.write(lf)
            with open(p_crlf, "wb") as fh:
                fh.write(lf.replace(b"\n", b"\r\n"))
            with open(p_png, "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n")
            self.assertEqual(_sha(p_lf), _sha(p_crlf))
            self.assertEqual(_sha(p_lf), hashlib.sha256(lf).hexdigest())   # LF: = bytes crudos
            self.assertEqual(_sha(p_png), hashlib.sha256(b"\x89PNG\r\n\x1a\n").hexdigest())
            self.assertIsNone(_sha(os.path.join(d, "no_existe.py")))
        import compare_legacy_vs_v2 as cmp
        import study_misalignment_v2 as st
        self.assertEqual(cmp._sha(src), _sha(src))
        self.assertEqual(st._sha(src), _sha(src))

    def test_minimal_example_fast(self):
        """El ejemplo del docstring del paquete / README corre en < 2 s y da algo razonable."""
        t0 = time.time()
        pos = pm.beam_positions(4, 100.0)
        C = pm.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, irf_fwhm=0.3)
        r0 = np.array([5.0, -5.0])
        lam = pm.lambda_beams(r0, pos, 360.0)
        counts = pm.simulate_counts(lam, 100, 2095, 2000 / 95., rng=np.random.default_rng(1))
        est = pm.mle_mixing(counts, pos, 360.0, C, 10.1, 50.0, 2000 / 95., bounds_radius=75.0)
        sigma = pm.crb(r0, pos, 360.0, C, 10.1, 50.0, 2000 / 95., 2095)
        el = time.time() - t0
        print("\n[minimal_example] %.2f s, crb %.3f nm, n_failed %d" % (el, sigma, est.n_failed))
        self.assertLess(el, 2.0)
        self.assertEqual(counts.shape, (100, 4))
        self.assertEqual(est.r.shape, (100, 2))
        self.assertEqual(est.n_failed, 0)
        rmse = math.sqrt(np.mean(np.sum((est.r - r0) ** 2, 1)))
        self.assertTrue(0.7 < rmse / (math.sqrt(2) * sigma) < 1.4)

    def test_end_to_end_example(self):
        import example_end_to_end as ex
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rows, el = ex.run(n_loc=150, seed=3, verbose=True)
        self.assertIn("RMSE/CRB", buf.getvalue())
        self.assertLess(el, 30.0)
        mix = [r for r in rows if r["estimador"] == "mezcla"]
        leg = [r for r in rows if r["estimador"] == "legado"]
        self.assertEqual(len(mix), 4)
        # el legado (sin fuga) está sesgado en el setup medido; la mezcla no (F104)
        self.assertTrue(all(r["n_failed"] == 0 for r in rows))
        self.assertGreater(min(r["bias_abs"] for r in leg), 0.5)
        self.assertLess(max(r["bias_abs"] for r in mix), 0.5)


class TestStudyV2(unittest.TestCase):

    def test_study_v2_json(self):
        """results/study_v2.json: completo, reproducible (sha del código actual) y con F205/F204."""
        path = os.path.join(ROOT, "results", "study_v2.json")
        if not os.path.exists(path):
            self.skipTest("falta results/study_v2.json (python scripts/study_misalignment_v2.py)")
        with open(path, encoding="utf-8") as fh:
            r = json.load(fh)
        self.assertFalse(r["quick"])
        self.assertLessEqual(r["runtime_s"]["total"], 180.0)
        sha = r["versions"]["sha256"]
        for mod in ("mixing", "psf", "estimate", "simulate", "windows"):
            self.assertEqual(sha[mod], _sha(os.path.join(ROOT, "src", "pminflux_sim", mod + ".py")),
                             "study_v2.json desactualizado respecto de %s.py" % mod)
        self.assertEqual(sha["study_misalignment_v2"],
                         _sha(os.path.join(ROOT, "scripts", "study_misalignment_v2.py")))
        st = r["setup"]
        self.assertEqual((st["tau"], st["a"], st["b"], st["T"], st["K"]), (4.21, 0.0, 10.1, 50.0, 4))
        self.assertEqual((st["irf_fwhm"], st["dead_time"], st["rate_per_cycle"]), (0.3, 22.0, 2.5e-3))
        self.assertFalse(r["psf_20260820_available"])
        self.assertTrue(any("SUPUESTO" in a for a in r["assumptions"]))
        # emisores continuos (fuera de la grilla de 1 nm) y referencia = posición simulada (F205)
        self.assertTrue(any(abs(x - round(x)) > 1e-3 for p in r["positions_nm"] for x in p))
        self.assertIn("SIMULADA", r["reference"])
        combos = {(c["geometry"], c["estimator"]) for c in r["cases"]}
        self.assertEqual(combos, {(g, e) for g in ("ideal", "desalineada")
                                  for e in ("honesto", "honesto_P_conocidas", "ingenuo", "legado")})
        self.assertEqual(sorted({c["N"] for c in r["efficiency_sweep"]["cases"]}), [100, 400, 1600])
        for c in r["cases"] + r["efficiency_sweep"]["cases"]:
            for m in c["positions"]:
                for k in ("bias_abs", "rmse_2d", "rmse_over_crb"):
                    self.assertTrue(np.isfinite(m[k]) and m[k + "_se"] > 0, k)
                    lo, hi = m[k + "_p16_p84"]
                    self.assertLessEqual(lo, hi)
                self.assertIn("boundary_fraction", m)
        s = r["summary"]
        # conclusiones que el reporte puede citar: con fuga modelada y calibración conocida el
        # estimador es eficiente; el legado (sin fuga) y el ingenuo (geometría ideal) no.
        for g in ("ideal", "desalineada"):
            self.assertLess(s[g + "/honesto_P_conocidas"]["max_bias_abs_nm"], 0.3)
            self.assertLess(abs(s[g + "/honesto_P_conocidas"]["mean_rmse_over_crb"] - 1.0), 0.05)
            self.assertGreater(s[g + "/legado"]["max_bias_abs_nm"], 2.0)
        self.assertGreater(s["desalineada/ingenuo"]["max_bias_abs_nm"], 5.0)


if __name__ == "__main__":
    unittest.main()
