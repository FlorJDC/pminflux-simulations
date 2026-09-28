# -*- coding: utf-8 -*-
"""Figuras del reporte (report/figs/*.png + report/figs/captions.json).

Solo lee JSON ya producidos y verificados:
  results/mixing_validation.json, results/mixing_rate_sweep.json,
  results/compare_legacy_vs_v2.json, results/dead_time_sweep.json,
  results/findings.json, equipo/2026-09-28_review-pminflux-sim/work/w3/F201_out.json
La única cuenta nueva es el esquema analítico de la línea de tiempo (pminflux_sim.mixing).
Las demás operaciones son de presentación (máximos, cocientes y reescalados de valores del JSON),
declaradas en cada caption.

Uso:  python scripts/make_report_figures.py
"""
from __future__ import print_function

import json
import os
import re
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pminflux_sim import mixing  # noqa: E402

RES = os.path.join(ROOT, "results")
W3 = os.path.join(ROOT, "equipo", "2026-09-28_review-pminflux-sim", "work", "w3")
OUT = os.path.join(ROOT, "report", "figs")

np.random.seed(20260928)  # no hay azar: se fija por reproducibilidad
DPI = 130
WIDTH = 7.2

# Okabe-Ito (seguro para daltonismo); orden fijo por entidad
OI = {"azul": "#0072B2", "naranja": "#E69F00", "verde": "#009E73", "bermellon": "#D55E00",
      "rosa": "#CC79A7", "celeste": "#56B4E9", "amarillo": "#F0E442", "negro": "#000000"}
BEAM_COL = [OI["azul"], OI["bermellon"], OI["verde"], OI["rosa"]]
GRIS = "#6b6b6b"

plt.rcParams.update({
    "font.size": 9.5, "axes.titlesize": 10, "axes.labelsize": 9.5, "legend.fontsize": 8.3,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e3e3e3", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "savefig.facecolor": "white", "figure.facecolor": "white",
})

CAPTIONS = {}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def save(fig, name, title, caption, source):
    fig.savefig(os.path.join(OUT, name), dpi=DPI)
    plt.close(fig)
    CAPTIONS[name] = {"title": title, "caption": caption, "source": source}
    print("escrito", name)


# ---------------------------------------------------------------- 1. línea de tiempo
def fig_timeline():
    T, K, tau, a, b, irf = 50.0, 4, 4.21, 0.0, 10.1, 0.3
    dT = T / K
    sig = mixing.fwhm_to_sigma(irf)
    C = mixing.mixing_matrix(tau, T, K, a, b, irf_fwhm=None)
    C_st = mixing.mixing_matrix(0.001, T, K, 0.0, 12.5, irf_fwhm=None)
    c10 = C[1, 0]
    t = np.linspace(0, T, 5001)

    def beam_pdf(j, tau_j, sigma):
        # densidad periódica (estado estacionario) del fotón del haz j dentro del ciclo
        out = np.zeros_like(t)
        for m in range(-1, 4):
            out += mixing.decay_pdf(t - j * dT + m * T, tau_j, sigma)
        return out

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(WIDTH, 5.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1.6, 1.0], "hspace": 0.45})
    ymax = 0.26
    for i in range(K):
        s = i * dT + a
        ax1.axvspan(s, s + b, color=BEAM_COL[i], alpha=0.10, lw=0)
        ax1.text(s + b / 2, ymax * 0.965, "ventana %d\n[%.1f, %.1f] ns" % (i, s, s + b),
                 ha="center", va="top", fontsize=7.6, color="#333333")
    for j in range(K):
        y = beam_pdf(j, tau, sig)
        ax1.plot(t, y, color=BEAM_COL[j], lw=1.8, label="haz %d (pulso en %.1f ns)" % (j, j * dT))
    # cola del haz 0 que invade la ventana 1
    y0 = beam_pdf(0, tau, sig)
    m = (t >= dT + a) & (t <= dT + a + b)
    ax1.fill_between(t[m], 0, y0[m], facecolor="none", edgecolor=BEAM_COL[0], hatch="////",
                     lw=0.0)
    ax1.annotate("cola del haz 0 en la ventana 1:\nC[1][0] = %.4f (%.1f %%)" % (c10, 100 * c10),
                 xy=(15.2, 0.012), xytext=(15.6, 0.155), fontsize=8.3,
                 arrowprops=dict(arrowstyle="->", color="#333333", lw=0.9))
    ax1.set_ylim(0, ymax)
    ax1.set_ylabel("densidad del microtiempo (1/ns)")
    ax1.set_title("Setup medido a 20 MHz: τ = 4.21 ns, ventanas [i·12.5, +10.1] ns, IRF 0.3 ns FWHM",
                  loc="left")
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=4, frameon=False,
               fontsize=7.8, handlelength=1.4, columnspacing=0.8)
    # inset: IRF
    ins = ax1.inset_axes([0.105, 0.40, 0.11, 0.30])
    tt = np.linspace(-0.8, 0.8, 600)
    g = np.exp(-0.5 * (tt / sig) ** 2)
    ins.plot(tt, g, color=OI["negro"], lw=1.2)
    ins.set_title("IRF 0.3 ns FWHM", fontsize=7)
    ins.set_xlabel("t − pulso (ns)", fontsize=6.5, labelpad=1)
    ins.tick_params(labelsize=6)
    ins.set_yticks([])
    ins.grid(False)

    # panel 2: supuesto de los estudios
    for i in range(K):
        s = i * dT
        ax2.axvspan(s, s + 12.5, color=BEAM_COL[i], alpha=0.10, lw=0)
        ax2.axvline(s, color=BEAM_COL[i], lw=2.2)
        ax2.text(s + 6.25, 0.5, "ventana %d\n[%.1f, %.1f] ns" % (i, s, s + 12.5),
                 ha="center", va="center", fontsize=7.6, color="#333333")
    offmax = np.max(C_st - np.diag(np.diag(C_st)))
    ax2.set_title("Supuesto de los estudios: Tlife = 0.001 ns, b = 12.5 ns → fuga nula "
                  "(máx. C[i][j≠i] = %.1g)" % offmax, loc="left")
    ax2.set_ylim(0, 1)
    ax2.set_yticks([])
    ax2.set_ylabel("pulsos\n(τ ≈ 0)")
    ax2.set_xlabel("microtiempo dentro del ciclo T = 50 ns (ns)")
    ax2.set_xlim(0, T)
    ax2.set_xticks(np.arange(0, 51, 12.5))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.95, bottom=0.10)
    save(fig, "timeline_20MHz.png", "Línea de tiempo del ciclo a 20 MHz y fuga entre pulsos",
         "Esquema analítico (pminflux_sim.mixing, sin simulación) de un ciclo TCSPC de T = 50 ns con "
         "K = 4 pulsos cada 12.5 ns. Arriba, el setup medido: decaimiento exponencial τ = 4.21 ns con "
         "IRF gaussiana de 0.3 ns FWHM (recuadro) y ventanas [i·12.5, i·12.5 + 10.1] ns. La cola del "
         "haz 0 (rayado) cae dentro de la ventana 1: C[1][0] = %.4f, es decir un %.1f %% de los fotones "
         "del haz 0 se cuentan como del haz 1 (C[i][i] = %.4f). Abajo, el supuesto de los estudios "
         "legados (Tlife = 0.001 ns, b = 12.5 ns): los pulsos son instantáneos y la fuga es nula. Si "
         "se simula así, el estudio no puede ver el desajuste del estimador sin fuga (el \"crimen "
         "inverso\" F104+F201). C sin IRF, igual a results/mixing_validation.json:C_no_irf."
         % (c10, 100 * c10, C[0, 0]),
         "results/mixing_validation.json:C_no_irf (recalculado con pminflux_sim.mixing.mixing_matrix)")
    return C


# ---------------------------------------------------------------- 2. validación de la mezcla
def fig_mixing_validation():
    path = os.path.join(RES, "mixing_validation.json")
    d = load(path)
    K = 4
    x = np.arange(K)
    fo = np.array(d["frac_observed"])
    se = np.array(d["frac_observed_se"])
    fm = np.array(d["frac_mixing"])
    fn = np.array(d["frac_naive"])
    dm = np.array(d["dev_se_mixing"])
    dn = np.array(d["dev_se_naive"])
    pm = d["chi2_pvalue_mixing_vs_sim_exp"]
    pn = d["chi2_pvalue_naive_vs_sim_exp"]
    chm, chn = d["chi2_mixing"], d["chi2_naive"]
    ntot = d["n_detected_total"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDTH, 3.5),
                                   gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.32})
    w = 0.26
    pn_txt = "p < 1e-300" if pn == 0 else "p = %.2g" % pn
    ax1.bar(x - w, fo, w, color=GRIS, label="sim_exp (±SE)", yerr=se, capsize=2,
            error_kw=dict(lw=0.8))
    ax1.bar(x, fm, w, color=OI["azul"], label="mezcla (χ² = %.2f, p = %.2f)" % (chm, pm))
    ax1.bar(x + w, fn, w, color=OI["naranja"], hatch="///", edgecolor="white", lw=0,
            label="ingenuo Ec. 3.5 (χ² = %.0f, %s)" % (chn, pn_txt))
    ax1.set_xticks(x)
    ax1.set_xticklabels(["ventana %d" % i for i in x])
    ax1.set_ylabel("fracción de fotones en la ventana")
    ax1.set_ylim(0, 0.52)
    ax1.legend(loc="upper left", frameon=False)
    ax1.set_title("Fracciones por ventana", loc="left")

    ax2.axhspan(-2, 2, color="#dddddd", alpha=0.6, lw=0, label="±2 SE")
    ax2.axhline(0, color="#444444", lw=0.8)
    ax2.bar(x - 0.18, dm, 0.34, color=OI["azul"], label="mezcla")
    ax2.bar(x + 0.18, dn, 0.34, color=OI["naranja"], hatch="///", edgecolor="white", lw=0,
            label="ingenuo")
    for xi, v in zip(x, dn):
        ax2.text(xi + 0.18, v + (0.8 if v >= 0 else -0.8), "%+.1f" % v, ha="center",
                 va="bottom" if v >= 0 else "top", fontsize=7.4)
    for xi, v in zip(x, dm):
        ax2.text(xi - 0.18, v + (0.8 if v >= 0 else -0.8), "%+.1f" % v, ha="center",
                 va="bottom" if v >= 0 else "top", fontsize=7.4, color=OI["azul"])
    ax2.set_xticks(x)
    ax2.set_xticklabels(["v%d" % i for i in x])
    ax2.set_ylabel("(observado − modelo) en SE")
    lo, hi = min(dn.min(), dm.min()), max(dn.max(), dm.max())
    ax2.set_ylim(lo - 5, hi + 5)
    ax2.legend(loc="lower left", frameon=False, ncol=1)
    ax2.set_title("Desvíos por ventana", loc="left")
    fig.suptitle("sim_exp a %.0e fotones/ciclo, %.2e fotones en ventanas (τ = 4.21, [0, 10.1] ns)"
                 % (d["rate_per_cycle"], ntot), fontsize=9.5, x=0.01, ha="left")
    fig.subplots_adjust(left=0.085, right=0.99, top=0.84, bottom=0.10)
    save(fig, "mixing_validation.png", "Validación de la matriz de mezcla contra sim_exp",
         "Fracciones por ventana que produce sim_exp + nMINFLUX del legado (%d llamadas, %.2e fotones "
         "en ventanas, %.0e fotones/ciclo, λ = %s, SBR 10) frente al modelo de mezcla (C con τ = 4.21 "
         "ns y ventanas [0, 10.1] ns) y al modelo ingenuo sin fuga de pos_MINFLUX/crb_minflux (Ec. "
         "3.5). Las barras de ±SE (≈2e-4) son más chicas que el trazo. Derecha: desvío por ventana en "
         "unidades de SE. La mezcla es consistente (χ² = %.2f, 3 g.l., p = %.3f; desvíos entre %.1f y "
         "%+.1f SE) y el ingenuo queda rechazado (χ² = %.0f, desvío de %+.1f SE en la ventana 0). "
         "Conclusión: sim_exp sí tiene fuga entre pulsos y el estimador legado no la modela."
         % (d["n_calls_ok"], ntot, d["rate_per_cycle"], d["lam"], chm, pm, dm.min(), dm.max(), chn,
            dn[0]),
         "results/mixing_validation.json:frac_observed,frac_mixing,frac_naive,dev_se_mixing,"
         "dev_se_naive,chi2_pvalue_mixing_vs_sim_exp,chi2_pvalue_naive_vs_sim_exp")


# ---------------------------------------------------------------- 3. barrido de tasa
def fig_rate_sweep():
    path = os.path.join(RES, "mixing_rate_sweep.json")
    d = load(path)
    pts = sorted(d["points"], key=lambda p: p["rate_per_cycle"])
    r = np.array([p["rate_per_cycle"] for p in pts])
    hi = np.array([np.max(np.abs(p["pred_highest_minus_mixing_in_se_per_2000ph_localization"]))
                   for p in pts])
    # earliest: mismo reescalado que usa el JSON para highest (SE total -> SE por loc. de 2000)
    ea = np.array([np.max(np.abs(p["pred_earliest_minus_mixing_in_se"]))
                   * np.sqrt(2000.0 / p["n_detected_total"]) for p in pts])
    chk = np.array([np.max(np.abs(p["pred_highest_minus_mixing_in_se"]))
                    * np.sqrt(2000.0 / p["n_detected_total"]) for p in pts])
    assert np.allclose(chk, hi, rtol=1e-6), "el reescalado no reproduce la clave per_2000ph"

    fig, ax = plt.subplots(figsize=(WIDTH, 3.6))
    ax.axvspan(1e-3, 5.5e-3, color=OI["amarillo"], alpha=0.35, lw=0,
               label="banda del tracking (1e-3–5.5e-3/ciclo = 20–110 kHz)")
    ax.plot(r, hi, "-o", color=OI["bermellon"], lw=2, ms=6,
            label="'highest' (sim_exp: gana el haz de k más alto)")
    ax.plot(r, ea, "--s", color=OI["azul"], lw=2, ms=6,
            label="'earliest' (TCSPC real: gana el fotón más temprano)")
    sc = d["studies_config"]
    s1 = sc["with_leak_tau4.21_b10.1"]
    s2 = sc["as_in_studies_tau0.001_b12.5"]
    for s, mk, lab in [(s1, "D", "config. de los estudios (Nb 95), τ 4.21, b 10.1"),
                       (s2, "^", "config. de los estudios, τ 0.001, b 12.5")]:
        v = np.max(np.abs(s["pred_highest_minus_mixing_in_se_per_2000ph_localization"]))
        ax.plot([s["rate_per_cycle"]], [v], mk, color=OI["negro"], ms=7, mfc="white", mew=1.4,
                label=lab + " (highest)")
    ax.axhline(1.0, color=GRIS, lw=0.9, ls=":")
    ax.text(1.05e-3, 1.08, "1 SE por localización", fontsize=7.8, color=GRIS)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("tasa detectada (fotones por ciclo TCSPC)")
    ax.set_ylabel("máx. |desvío| vs mezcla\n(SE por localización de 2000 fotones)")
    ax.set_title("Desvío de sim_exp respecto del modelo de mezcla en función de la tasa", loc="left")
    ax.legend(loc="lower right", frameon=True, framealpha=0.95, fontsize=7.8)
    ax.set_ylim(1e-3, 20)
    fig.subplots_adjust(left=0.12, right=0.98, top=0.91, bottom=0.14)
    i1 = int(np.argmin(np.abs(r - 1e-3)))
    i3 = int(np.argmin(np.abs(r - 3e-3)))
    save(fig, "rate_sweep.png", "Desvío por tasa finita: 'highest' y 'earliest' frente a la mezcla",
         "Máximo sobre las 4 ventanas del desvío predicho (exacto a tasa finita, pminflux_sim.mixing) "
         "entre las fracciones por ventana y el modelo de mezcla (tasa → 0), en SE de una localización "
         "de 2000 fotones, frente a la tasa por ciclo (Ns 2000, Nb 200, λ = [0.12, 0.28, 0.35, 0.25], "
         "τ = 4.21, [0, 10.1] ns). 'earliest' se reescaló de SE totales a SE por localización con "
         "√(2000/n_detected_total), el mismo factor que reproduce la clave de 'highest'. Las dos "
         "curvas se superponen: 'earliest' tiene la misma magnitud y el signo opuesto. En los puntos "
         "calculados dentro de la banda del tracking (1e-3–5.5e-3 fotones/ciclo) el desvío es ≤ %.3f SE "
         "(%.3f a 1e-3, %.3f a 3e-3). Crece de forma lineal con la tasa: %.3f a 0.01, %.2f a %.1f y "
         "%.2f a %.1f/ciclo. Los rombos/triángulos son la configuración de los estudios a 0.0105/ciclo "
         "(%.3f y %.3f SE). Conclusión: la sobrescritura por ciclo de sim_exp (F101) existe, pero no "
         "importa en el régimen del tracking."
         % (max(hi[i3], ea[i3]), hi[i1], hi[i3], hi[int(np.argmin(np.abs(r - 1e-2)))], hi[-2], r[-2],
            hi[-1], r[-1],
            np.max(np.abs(s1["pred_highest_minus_mixing_in_se_per_2000ph_localization"])),
            np.max(np.abs(s2["pred_highest_minus_mixing_in_se_per_2000ph_localization"]))),
         "results/mixing_rate_sweep.json:points[*].pred_highest_minus_mixing_in_se_per_2000ph_"
         "localization,points[*].pred_earliest_minus_mixing_in_se,studies_config")


# ---------------------------------------------------------------- 4. legado vs v2
def fig_legacy_vs_v2():
    path = os.path.join(RES, "compare_legacy_vs_v2.json")
    d = load(path)
    pos = [tuple(p) for p in d["positions_nm"]]
    conds = [("SBR21", 0.0), ("SBR21", 0.3), ("SBR6", 0.0), ("SBR6", 0.3)]
    est = [("legacy", "legado (Ec. 3.5)", OI["bermellon"], "o", 0.0),
           ("mixing", "mezcla", OI["azul"], "s", 0.0),
           ("mixing_freebg", "mezcla + fondo libre", OI["verde"], "^", 0.0)]
    offs = [-0.2, 0.0, 0.2]
    fig, axes = plt.subplots(2, 4, figsize=(WIDTH, 5.4), sharex=True, sharey="row")
    x = np.arange(len(pos))
    for ci, (sbr, irf) in enumerate(conds):
        cases = [c for c in d["cases"] if c["sbr_label"] == sbr and abs(c["irf_fwhm_ns"] - irf) < 1e-9]
        cases = sorted(cases, key=lambda c: pos.index(tuple(c["position_nm"])))
        a0, a1 = axes[0, ci], axes[1, ci]
        asym = [c["legacy_asymptotic_bias_nm"] for c in cases]
        a0.plot(x - 0.2, asym, "_", color=OI["negro"], ms=14, mew=1.6)
        for (k, lab, col, mk, _), o in zip(est, offs):
            b = [c["estimators"][k]["bias_abs"] for c in cases]
            be = [c["estimators"][k]["bias_abs_se"] for c in cases]
            rc = [c["estimators"][k]["rmse_over_crb"] for c in cases]
            re_ = [c["estimators"][k]["rmse_over_crb_se"] for c in cases]
            a0.errorbar(x + o, b, yerr=be, fmt=mk, color=col, ms=5, capsize=1.5, lw=0.9)
            a1.errorbar(x + o, rc, yerr=re_, fmt=mk, color=col, ms=5, capsize=1.5, lw=0.9)
        a1.axhline(1.0, color=GRIS, lw=0.9, ls="--")
        a0.set_title("%s, IRF %.1f ns" % (sbr.replace("SBR", "SBR "), irf), fontsize=9)
        a1.set_xticks(x)
        a1.set_xticklabels(["P%d" % (i + 1) for i in x])
    axes[0, 0].set_ylabel("|sesgo| (nm)")
    axes[1, 0].set_ylabel("RMSE / CRB")
    for a in axes[1]:
        a.set_xlabel("posición")
    axes[0, 0].set_ylim(0, 3.0)
    axes[1, 0].set_ylim(0.9, 2.15)
    handles = [Line2D([], [], color=c, marker=m, ls="none", ms=6, label=l)
               for (_, l, c, m, _) in est]
    handles.append(Line2D([], [], color=OI["negro"], marker="_", ls="none", ms=12, mew=1.6,
                          label="sesgo asintótico del legado"))
    handles.append(Line2D([], [], color=GRIS, ls="--", label="RMSE/CRB = 1"))
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=8)
    ptxt = ", ".join("P%d = (%g, %g)" % (i + 1, p[0], p[1]) for i, p in enumerate(pos))
    fig.suptitle("Legado contra v2 sobre datos del simulador v2 (τ 4.21, [0, 10.1] ns, "
                 "%.1e fotones/ciclo, d = %g ns)" % (d["setup"]["rate_per_cycle"], d["setup"]["dead_time"]),
                 fontsize=9.3, x=0.01, ha="left")
    fig.subplots_adjust(left=0.085, right=0.99, top=0.90, bottom=0.20, wspace=0.12, hspace=0.18)
    # números para el caption
    allc = d["cases"]
    leg_b = [c["estimators"]["legacy"]["bias_abs"] for c in allc]
    leg_r = [c["estimators"]["legacy"]["rmse_over_crb"] for c in allc]
    mix_b = [c["estimators"][k]["bias_abs"] for c in allc for k in ("mixing", "mixing_freebg")]
    mix_r = [c["estimators"][k]["rmse_over_crb"] for c in allc for k in ("mixing", "mixing_freebg")]
    save(fig, "legacy_vs_v2.png", "Estimador legado frente al MLE con matriz de mezcla",
         "|sesgo| (arriba, nm) y RMSE/CRB (abajo) de 2000 localizaciones por caso, con barras de ±SE "
         "por bootstrap (%d remuestreos), para el MLE legado de la Ec. 3.5, el MLE con matriz de mezcla "
         "y el MLE de mezcla con fondo libre por localización. Datos del simulador v2 (source = %s), "
         "Ns = 2000, en 5 posiciones (%s nm), SBR 21/6 e IRF 0/0.3 ns. El legado tiene un sesgo de "
         "%.2f–%.2f nm (RMSE/CRB %.2f–%.2f) que sigue al sesgo asintótico calculado (guion negro); los "
         "dos estimadores de mezcla quedan en %.3f–%.3f nm y RMSE/CRB %.3f–%.3f. El CRB es el del "
         "modelo con fuga (con fondo libre, el suyo). Conclusión: modelar la fuga elimina el sesgo "
         "(F104) y alcanza el CRB con fuga."
         % (d["n_boot"], d["source"], ptxt, min(leg_b), max(leg_b), min(leg_r), max(leg_r),
            min(mix_b), max(mix_b), min(mix_r), max(mix_r)),
         "results/compare_legacy_vs_v2.json:cases[*].estimators.{legacy,mixing,mixing_freebg}."
         "{bias_abs,rmse_over_crb},cases[*].legacy_asymptotic_bias_nm")


# ---------------------------------------------------------------- 5. F201
def fig_f201():
    path = os.path.join(W3, "F201_out.json")
    d = load(path)["study_A"]
    fnd = [f for f in load(os.path.join(RES, "findings.json")) if f["id"] == "F201"][0]
    mcrb = re.search(r"conoce la fuga\s*\((0\.\d+)\s*nm\)", fnd["impact"])
    assert mcrb, "no encuentro el CRB con fuga en findings.json:F201.impact"
    crb_leak = float(mcrb.group(1))
    cases = [("Ideal", "ideal\nhonesto"), ("Geom. medida honesta", "geom.\nhonesto"),
             ("Geom. medida ingenua", "geom.\ningenuo"), ("Realista honesta", "realista\nhonesto"),
             ("Realista ingenua", "realista\ningenuo")]
    conds = [("C0", "sin fuga (Tlife 0.001 ns, b 12.5 ns) — como los estudios", OI["celeste"], None),
             ("C3", "con fuga (τ 4.21 ns, [0, 10.1] ns) — setup medido", OI["bermellon"], "///")]
    x = np.arange(len(cases))
    w = 0.36
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDTH, 3.9), gridspec_kw={"wspace": 0.28})
    for k, (c, lab, col, hatch) in enumerate(conds):
        o = (k - 0.5) * w
        b = [d[n][c]["bias_abs"] for n, _ in cases]
        be = [d[n][c]["bias_se"] for n, _ in cases]
        rr = [d[n][c]["rmse"] / d[n]["crb"] for n, _ in cases]
        ax1.bar(x + o, b, w, yerr=be, capsize=1.5, color=col, hatch=hatch, edgecolor="white",
                lw=0, label=lab, error_kw=dict(lw=0.7))
        ax2.bar(x + o, rr, w, color=col, hatch=hatch, edgecolor="white", lw=0)
        for xi, v in zip(x + o, b):
            ax1.text(xi, v * 1.12, "%.2f" % v, ha="center", va="bottom", fontsize=6.6)
        for xi, v in zip(x + o, rr):
            ax2.text(xi, v * 1.06, "%.2f" % v, ha="center", va="bottom", fontsize=6.6)
    ideal_leak = d["Ideal"]["C3"]["rmse"] / crb_leak
    ax2.plot([x[0] + 0.5 * w], [ideal_leak], "D", color=OI["negro"], mfc="white", ms=6, mew=1.3,
             zorder=5)
    ax2.annotate("%.2f contra el CRB\ncon fuga (%.3f nm)" % (ideal_leak, crb_leak),
                 xy=(x[0] + 0.5 * w + 0.08, ideal_leak), xytext=(0.55, 5.6), fontsize=7.4,
                 arrowprops=dict(arrowstyle="->", lw=0.8))
    ax2.axhline(1.0, color=GRIS, lw=0.9, ls="--")
    for a in (ax1, ax2):
        a.set_xticks(x)
        a.set_xticklabels([l for _, l in cases], fontsize=7.8)
        a.set_yscale("log")
    ax1.set_ylabel("|sesgo| (nm)")
    ax1.set_ylim(0.05, 40)
    ax2.set_ylabel("RMSE / CRB sin fuga")
    ax2.set_ylim(0.5, 30)
    ax1.set_title("Sesgo", loc="left")
    ax2.set_title("RMSE/CRB (CRB sin fuga del estudio)", loc="left")
    fig.legend(loc="lower center", ncol=2, frameon=False, fontsize=8)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.92, bottom=0.25)
    I0, I3 = d["Ideal"]["C0"], d["Ideal"]["C3"]
    save(fig, "f201_leakage.png", "F201: los estudios apagan la fuga",
         "Pipeline legado (sim_exp + nMINFLUX + pos_MINFLUX; Ns 2000, Nb 95, emisor en el píxel "
         "(−5, −8), 1000 muestras) con los parámetros de los estudios (Tlife = 0.001 ns, b = 12.5 ns; "
         "celeste) y con los del experimento (τ = 4.21 ns, ventanas [0, 10.1] ns; rojo rayado), para "
         "cada EBP × estimador (honesto = modelo correcto del EBP; ingenuo = geometría ideal). Ideal "
         "honesto: |sesgo| %.2f → %.2f nm; RMSE/CRB %.2f → %.2f contra el CRB sin fuga (%.3f nm) que usa "
         "el estudio (cociente RMSE/CRB calculado aquí de las claves rmse y crb), o ≈%.1f contra el CRB "
         "con fuga (%.3f nm, rombo). Realista ingenua: %.1f → %.1f nm. Escalas logarítmicas; ±SE de "
         "Monte Carlo en el sesgo. Conclusión: la conclusión \"el honesto alcanza el CRB\" vale sin fuga, "
         "no en el experimento a 20 MHz (clase DISEÑO)."
         % (I0["bias_abs"], I3["bias_abs"], I0["rmse"] / d["Ideal"]["crb"],
            I3["rmse"] / d["Ideal"]["crb"], d["Ideal"]["crb"], ideal_leak, crb_leak,
            d["Realista ingenua"]["C0"]["bias_abs"], d["Realista ingenua"]["C3"]["bias_abs"]),
         "equipo/2026-09-28_review-pminflux-sim/work/w3/F201_out.json:study_A.*.{C0,C3}.{bias_abs,"
         "rmse},study_A.*.crb; results/findings.json:F201.impact (CRB con fuga)")


# ---------------------------------------------------------------- 6. tiempo muerto
def fig_dead_time():
    path = os.path.join(RES, "dead_time_sweep.json")
    d = load(path)
    rows = d["rows"]
    series = [("earliest", 0.0, "earliest, d = 0 ns", OI["azul"], "-o"),
              ("earliest", 22.0, "earliest, d = 22 ns (SUPUESTO, no medido)", OI["bermellon"], "-s"),
              ("earliest", 50.0, "earliest, d = 50 ns = 1·T (sin sesgo)", OI["verde"], "--^"),
              ("earliest", 100.0, "earliest, d = 100 ns = 2·T (sin sesgo)", OI["rosa"], "--v"),
              ("highest", 0.0, "highest (sim_exp), d = 0", OI["negro"], ":D")]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.9))
    ax.axvspan(1e-3, 5.5e-3, color=OI["amarillo"], alpha=0.35, lw=0,
               label="banda del tracking (1e-3–5.5e-3/ciclo)")
    mcse = np.mean([np.mean(r["mc_se_in_SE_per_loc"]) for r in rows])
    ax.axhspan(0, 2 * mcse, color="#d9d9d9", alpha=0.7, lw=0,
               label="ruido de MC: 2·SE_MC = %.3f" % (2 * mcse))
    vals = {}
    for tc, dt, lab, col, sty in series:
        rr = sorted([r for r in rows if r["tcspc"] == tc and r["dead_time_ns"] == dt],
                    key=lambda r: r["rate_per_cycle"])
        xs = [r["rate_per_cycle"] for r in rr]
        ys = [r["max_abs_bias_SE_per_loc"] for r in rr]
        vals[(tc, dt)] = dict(zip(xs, ys))
        ax.plot(xs, ys, sty, color=col, lw=1.8, ms=6, label=lab, mfc="white" if tc == "highest" else col)
    ax.set_xscale("log")
    ax.set_xlabel("tasa detectada (fotones por ciclo TCSPC)")
    ax.set_ylabel("máx. |sesgo| por ventana\n(SE por localización de 2000 fotones)")
    ax.set_ylim(0, 0.165)
    ax.set_title("Simulador v2: sesgo por tasa finita y tiempo muerto frente a la mezcla ideal",
                 loc="left")
    ax.legend(loc="upper left", frameon=True, framealpha=0.95, fontsize=7.6, ncol=2)
    ax.set_xticks(d["params"]["rates_per_cycle"])
    ax.set_xticklabels(["%g" % v for v in d["params"]["rates_per_cycle"]])
    ax.minorticks_off()
    fig.subplots_adjust(left=0.12, right=0.98, top=0.91, bottom=0.14)
    v22 = vals[("earliest", 22.0)]
    v50 = vals[("earliest", 50.0)]
    v100 = vals[("earliest", 100.0)]
    pmin_nT = min(r["p_vs_ideal"] for r in rows if r["dead_time_ns"] in (50.0, 100.0))
    save(fig, "dead_time_sweep.png", "Sesgo por tiempo muerto y tasa finita en el simulador v2",
         "Máximo |sesgo| sobre las 4 ventanas de las fracciones del simulador v2 frente a la mezcla "
         "ideal (window_probs), en SE de una localización de 2000 fotones (%d localizaciones por punto, "
         "semilla %d, IRF 0.3 ns, SBR 21), para TCSPC 'earliest' con tiempo muerto d = 0/22/50/100 ns y "
         "para 'highest' (emulación de sim_exp). El tiempo muerto de 22 ns es un SUPUESTO (valor típico "
         "de SPAD), no un valor medido. Con d = n·T (50 y 100 ns) el sesgo se anula exactamente "
         "(resultado demostrado y verificado): %.3f–%.3f y %.3f–%.3f SE, dentro del ruido de MC "
         "(franja gris, 2·SE_MC ≈ %.3f; p del χ² contra la mezcla ≥ %.2f). Con d = 22 ns: %.3f SE a 1e-3, %.3f a 5.5e-3 y %.3f a 0.0105 "
         "fotones/ciclo. Conclusión: en el régimen de tracking el sesgo por tasa finita es ≤0.08 SE por "
         "localización."
         % (d["params"]["n_loc_per_case"], d["params"]["seed"], min(v50.values()), max(v50.values()),
            min(v100.values()), max(v100.values()), 2 * mcse, pmin_nT, v22[0.001], v22[0.0055], v22[0.0105]),
         "results/dead_time_sweep.json:rows[*].max_abs_bias_SE_per_loc,rows[*].mc_se_in_SE_per_loc,"
         "assumptions")


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    C = fig_timeline()
    ref = np.array(load(os.path.join(RES, "mixing_validation.json"))["C_no_irf"])
    assert np.allclose(C, ref, atol=1e-10), "C del esquema difiere de mixing_validation.json"
    fig_mixing_validation()
    fig_rate_sweep()
    fig_legacy_vs_v2()
    fig_f201()
    fig_dead_time()
    with open(os.path.join(OUT, "captions.json"), "w", encoding="utf-8") as fh:
        json.dump(CAPTIONS, fh, ensure_ascii=False, indent=1)
    print("escrito captions.json (%d figuras)" % len(CAPTIONS))


if __name__ == "__main__":
    main()
