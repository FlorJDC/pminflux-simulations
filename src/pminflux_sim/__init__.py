# -*- coding: utf-8 -*-
"""pminflux_sim -- simulador y estimador p-MINFLUX pulsado con fuga entre ventanas (v2).

Submódulos:

- ``mixing``: matriz de mezcla C (fuga entre ventanas) y modelos de probabilidades por ventana.
- ``simulate``: simulador fotón por fotón en dominio temporal (TCSPC, tiempo muerto, IRF, fondo).
- ``windows``: conteo por ventana a partir de microtiempos (reemplazo de ``nMINFLUX``).
- ``psf``: posiciones de los haces y perfiles (dona/gaussiano).
- ``estimate``: MLE con matriz de mezcla, MLE del legado (Ec. 3.5), CRB y elipse de covarianza.

Uso mínimo::

    import numpy as np
    import pminflux_sim as pm
    pos = pm.beam_positions(4, 100.0)
    C = pm.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, irf_fwhm=0.3)
    lam = pm.lambda_beams(np.array([5.0, -5.0]), pos, 360.0)
    counts = pm.simulate_counts(lam, 100, 2095, 2000 / 95., rng=np.random.default_rng(1))
    est = pm.mle_mixing(counts, pos, 360.0, C, 10.1, 50.0, 2000 / 95., bounds_radius=75.0)
    sigma = pm.crb([5.0, -5.0], pos, 360.0, C, 10.1, 50.0, 2000 / 95., 2095)

Ver ``README.md`` (convenciones, supuestos y tabla de migración desde el legado).
"""

__version__ = "2.0.0"

from . import mixing, psf, windows, simulate, estimate  # noqa: F401
from .mixing import (  # noqa: F401
    mixing_matrix,
    window_expected,
    window_probs,
    naive_probs,
    pearson_chi2,
    occupancy_pattern_probs,
    sim_exp_window_probs,
)
from .simulate import SimParams, simulate_counts, DEAD_TIME_ASSUMPTION  # noqa: F401
from .windows import (  # noqa: F401
    count_windows, check_overlap, window_starts, mixing_matrix_starts,
)
from .psf import beam_positions, lambda_beams, donut, gaussian  # noqa: F401
from .estimate import (  # noqa: F401
    mle_mixing,
    mle_legacy,
    crb,
    crb_legacy,
    forward_probs,
    cov_ellipse,
    mixing_conditioning,
    MLEResult,
)

__all__ = [
    "__version__",
    # submódulos
    "mixing", "psf", "windows", "simulate", "estimate",
    # mixing (exportados desde la ronda 1)
    "mixing_matrix",
    "window_expected",
    "window_probs",
    "naive_probs",
    "pearson_chi2",
    "occupancy_pattern_probs",
    "sim_exp_window_probs",
    # v2
    "SimParams", "simulate_counts", "DEAD_TIME_ASSUMPTION",
    "count_windows", "check_overlap", "window_starts", "mixing_matrix_starts",
    "beam_positions", "lambda_beams", "donut", "gaussian",
    "mle_mixing", "mle_legacy", "crb", "crb_legacy", "forward_probs", "cov_ellipse",
    "mixing_conditioning", "MLEResult",
]
