# -*- coding: utf-8 -*-
"""C07 (checklist SimuFLUX, item 7) - Cuanto "llena el cero" la perla de calibracion.

Las PSFs 20260820 se midieron con una perla de 20 nm (ESTADO_Y_PLAN_REALISMO_PSF.md:31). La
autora advierte que la perla promedia el cero (ebp.py:547, build_doc.py:684-691) pero no lo
corrige. Aqui se estima el valor en el centro de la dona (legado: pico del anillo = 1, fwhm 343.9)
promediada sobre una esfera uniforme de diametro D (volumen, muestreo Monte Carlo 2e6 puntos; la
dona 2D no depende de z en este modelo), y se compara con el zero_ratio medido (8.7-11.0 %,
fit_parameters.csv / run_final.log:5). Analitico cerca del cero: <I> ~ 4e ln2 <x^2+y^2>/fwhm^2
con <x^2+y^2> = 2 a^2/5 (a = D/2).
Run: python scripts/findings/C07_bead_fills_zero.py   (< 5 s)
"""
import numpy as np

LN2 = np.log(2)
FWHM = 343.9


def donut(r2):
    return 4 * np.e * LN2 * r2 / FWHM**2 * np.exp(-4 * LN2 * r2 / FWHM**2)


def main():
    rng = np.random.default_rng(7)
    for D in (20.0, 40.0, 100.0, 200.0):
        a = D / 2
        v = rng.uniform(-1, 1, (2_000_000, 3))
        v = v[np.sum(v**2, axis=1) <= 1] * a
        fill = float(np.mean(donut(v[:, 0] ** 2 + v[:, 1] ** 2)))
        ana = 4 * np.e * LN2 * (2 * a**2 / 5) / FWHM**2
        print("perla D = %5.0f nm: cero llenado = %.4f %% del pico del anillo (analitico %.4f %%); "
              "fraccion del zero_ratio medido 8.7-11.0 %%: %.1f-%.1f %%"
              % (D, 100 * fill, 100 * ana, 100 * fill / 0.110, 100 * fill / 0.087))


if __name__ == "__main__":
    main()
