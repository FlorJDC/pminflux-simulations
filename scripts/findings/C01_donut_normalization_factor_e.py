# -*- coding: utf-8 -*-
"""C01 (checklist SimuFLUX, item 1) - Normalizacion de la dona y referencia del "cero".

Legado: tools_simulations.doughnut (l.130-157) usa el prefactor 4e*ln2 => pico del anillo = 1
(A0 = 1 de Balzarotti S16). SimuFLUX (PsfDonut2D) usa 4*ln2 sin el factor e => pico del anillo
= 1/e, misma potencia que una gaussiana de pico 1; su `zerooffset` se mide relativo al pico
gaussiano. Este script:
  (a) mide el pico del anillo y la potencia (integral) de ambas convenciones;
  (b) toma el pedestal del ajuste 2D del legado (Resultados/realistic_psf/fit_parameters.csv,
      donut_2d: pedestal + amplitude*dona con pico 1) y lo expresa relativo al pico del anillo
      (pedestal/amplitude) y en la convencion de SimuFLUX (dividir por e);
  (c) expresa zero_ratio (min/max del mapa) en la convencion SimuFLUX;
  (d) chequea que en la grilla de 400 nm el maximo del mapa de una dona ideal (fwhm 343.9) sea el
      pico del anillo (el anillo, r = 206.5 nm, entra al FOV solo por las diagonales).
Run: python scripts/findings/C01_donut_normalization_factor_e.py   (< 5 s)
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEG = os.path.join(ROOT, "legacy", "p-minflux-main")
sys.path.insert(0, LEG)
from tools import tools_simulations as ts  # noqa: E402

LN2 = np.log(2)


def simuflux_donut(r, fwhm):
    return 4 * LN2 * r**2 / fwhm**2 * np.exp(-4 * LN2 * r**2 / fwhm**2)


def main():
    fwhm = 343.9
    r = np.linspace(0, 1500, 300001)
    leg = ts.doughnut(r, fwhm)
    sim = simuflux_donut(r, fwhm)
    gau = ts.gaussian(r, fwhm)
    dr = r[1] - r[0]
    P = lambda f: float(np.sum(2 * np.pi * r * f) * dr)  # noqa: E731
    print("(a) pico del anillo: legado %.6f (en r = %.2f nm), SimuFLUX %.6f (1/e = %.6f)"
          % (leg.max(), r[np.argmax(leg)], sim.max(), np.exp(-1)))
    print("    potencia/potencia gaussiana: legado %.4f, SimuFLUX %.4f  -> factor %.4f (e = %.4f)"
          % (P(leg) / P(gau), P(sim) / P(gau), P(leg) / P(sim), np.e))

    rows = list(csv.DictReader(open(os.path.join(LEG, "Resultados", "realistic_psf",
                                                 "fit_parameters.csv"), encoding="utf-8")))
    ped = np.array([float(x["pedestal"]) for x in rows])
    amp = np.array([float(x["amplitude"]) for x in rows])
    zr = np.array([float(x["zero_ratio_experimental"]) for x in rows])
    eps_ring = ped / amp
    print("(b) pedestal (unidades del max de la imagen):", np.round(ped, 4).tolist())
    print("    pedestal/pico del anillo (Balzarotti):  ", np.round(eps_ring, 4).tolist())
    print("    equivalente zerooffset SimuFLUX (/e):    ", np.round(eps_ring / np.e, 4).tolist())
    print("    SimuFLUX SI Fig.5 zerooffset 0.01 = %.4f del pico del anillo" % (0.01 * np.e))
    print("(c) zero_ratio experimental (min/max mapa):", np.round(zr, 4).tolist(),
          "-> SimuFLUX:", np.round(zr / np.e, 4).tolist())

    PSF = ts.psf([0.0, 0.0], 400.0, 1.0, [0, 0], d="donut", donut_fwhm=fwhm)
    print("(d) grilla 400 nm, dona ideal fwhm %.1f: max del mapa = %.6f, min = %.2e, "
          "radio del anillo = %.1f nm" % (fwhm, PSF.max(), PSF.min(), fwhm / (2 * np.sqrt(LN2))))


if __name__ == "__main__":
    main()
