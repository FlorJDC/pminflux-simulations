# -*- coding: utf-8 -*-
"""pminflux_sim -- simulador y estimador p-MINFLUX pulsado con fuga entre ventanas.

Ronda 1: solo el modelo de la matriz de mezcla (``pminflux_sim.mixing``).
"""

from .mixing import (  # noqa: F401
    mixing_matrix,
    window_expected,
    window_probs,
    naive_probs,
    pearson_chi2,
    occupancy_pattern_probs,
    sim_exp_window_probs,
)

__all__ = [
    "mixing_matrix",
    "window_expected",
    "window_probs",
    "naive_probs",
    "pearson_chi2",
    "occupancy_pattern_probs",
    "sim_exp_window_probs",
]
