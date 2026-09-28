"""Acceptance test -- the definition of "done" for pminflux-sim-v2 (hash-pinned; do not edit).

Recomputes the periodic mixing matrix independently and checks the reported validation,
the findings registry and the HTML report.
Run:  python -m unittest tests.test_acceptance -v
"""

import json
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
CLASSES = {"CONCEPTUAL", "IMPLEMENTACION", "DISENO"}


def _load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as fh:
        return json.load(fh)


def _mixing(tau, T, K, a, b, nwrap=40):
    """C[i][j] = P(photon excited by beam j is detected in window i), exponential decay
    (no IRF), pulses of beam j at j*T/K, window i = [i*T/K + a, i*T/K + a + b], periodic."""
    dt = T / K
    C = [[0.0] * K for _ in range(K)]
    for i in range(K):
        for j in range(K):
            off = ((i - j) * dt) % T          # delay from beam-j pulse to window-i start
            s = 0.0
            for m in range(nwrap):
                t0 = off + a + m * T
                t1 = t0 + b
                lo, hi = max(t0, 0.0), max(t1, 0.0)
                s += math.exp(-lo / tau) - math.exp(-hi / tau)
            C[i][j] = s
    return C


class Acceptance(unittest.TestCase):

    def test_package_imports(self):
        sys.path.insert(0, os.path.join(ROOT, "src"))
        import pminflux_sim  # noqa: F401

    def test_mixing_matrix_reported_correctly(self):
        v = _load("mixing_validation.json")
        p = v["params"]
        ref = _mixing(p["tau_ns"], p["T_ns"], p["K"], p["window_start_ns"], p["window_width_ns"])
        C = v["C_no_irf"]
        for i in range(p["K"]):
            for j in range(p["K"]):
                self.assertAlmostEqual(C[i][j], ref[i][j], delta=1e-6, msg=(i, j))

    def test_reference_configuration_matches_the_measured_setup(self):
        p = _load("mixing_validation.json")["params"]
        self.assertEqual(p["K"], 4)
        self.assertAlmostEqual(p["T_ns"], 50.0)              # 20 MHz
        self.assertAlmostEqual(p["tau_ns"], 4.21, delta=1e-9)
        self.assertAlmostEqual(p["window_start_ns"], 0.0)
        self.assertAlmostEqual(p["window_width_ns"], 10.1, delta=1e-9)

    def test_mixing_model_agrees_with_sim_exp_and_naive_model_does_not(self):
        v = _load("mixing_validation.json")
        self.assertGreaterEqual(v["n_detected_total"], 1_000_000)
        self.assertLess(v["rate_per_cycle"], 0.01, "validate in the low-rate regime")
        self.assertGreater(v["chi2_pvalue_mixing_vs_sim_exp"], 1e-3)
        self.assertLess(v["chi2_pvalue_naive_vs_sim_exp"], 1e-6)

    def test_findings_registry_is_complete_and_verified(self):
        f = _load("findings.json")
        self.assertGreaterEqual(len(f), 5)
        for x in f:
            for k in ("id", "title", "class", "legacy_location", "scenario", "impact",
                      "fix", "script", "status"):
                self.assertIn(k, x, x.get("id"))
            self.assertIn(x["class"], CLASSES, x["id"])
            self.assertEqual(x["status"], "verified", x["id"])
            self.assertTrue(os.path.exists(os.path.join(ROOT, x["script"].split("::")[0])),
                            x["script"])

    def test_html_report_covers_every_finding(self):
        path = os.path.join(ROOT, "report", "index.html")
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        for x in _load("findings.json"):
            self.assertIn(x["id"], html)
        for word in ("conceptual", "implementaci", "dise"):
            self.assertIn(word, html.lower())
        self.assertNotIn("src=\"http", html, "report must be self-contained")


if __name__ == "__main__":
    unittest.main()
