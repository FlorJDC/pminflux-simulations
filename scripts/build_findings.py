# -*- coding: utf-8 -*-
"""Registro de hallazgos fusionado y corregido (ronda 2, Worker 1; actualizado en R3).

Lee ``results/findings_A.json``, ``results/findings_B.json`` (borradores de R1) y el ledger
``equipo/2026-09-28_review-pminflux-sim/state.json`` (solo lectura) y escribe:

- ``results/findings.json``           : los 16 hallazgos verificados (lo que exige la aceptación).
- ``results/findings_discarded.json`` : las sospechas descartadas (y F154, que sigue ``unclear``).
- ``results/mixing_claims.json``      : las afirmaciones MIX-* verificadas + MIX-NDETECT corregida.

Los textos de ``title``/``scenario``/``impact`` se escriben acá, con los números del texto
verificado en ``state.json`` (no del borrador del worker) y con las correcciones de los
verificadores y del inbox aplicadas en forma literal. Cada entrada registra esas correcciones
en ``corrections_applied``. Es determinista y reejecutable:

    python scripts/build_findings.py            # escribe los tres JSON e imprime la auditoría
    python scripts/build_findings.py --check    # no escribe; solo la auditoría numérica

La auditoría lista, por hallazgo, los números de ``title``+``impact`` que no aparecen en el texto
verificado de ``state.json`` para ese id (para que el verificador los revise uno por uno).
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
JOB = os.path.join(ROOT, "equipo", "2026-09-28_review-pminflux-sim")
LEG = "legacy/p-minflux-main/"

VA = "verifier-A r01"
VB = "verifier-B r01"
INBOX_R2 = "inbox.jsonl ronda 2"

TS = "tools_simulations.py"
# Bases de autoría (defaults del PI en r02-pi.md y del orquestador)
BASIS_AUTORA = ("declaración de la autora en NOTAS.txt (sin historial git): NOTAS.txt nombra como "
                "originales de L. Masullo solo tools/tools_analysis.py y simulations_example.py; "
                "este archivo no está en esa lista (atribución por exclusión)")
BASIS_TS_NV = ("tools_simulations.py (encabezado: Luciano Masullo, Lucía López y Lars Richter) no está "
               "en la lista de originales de NOTAS.txt, así que la autora lo modificó, pero sin "
               "historial git no se puede atribuir la línea concreta")
BASIS_FASTPATH = ("indicio: comentario en español; sin git. El verificador A (r01) sostiene que el "
                  "comentario 'EXACTAMENTE' (l.423-440) y la ruta rápida de 'p_minflux' son de la "
                  "autora; el comentario propio de la ruta rápida (l.454-457) está en inglés")

CRIMEN_INVERSO = (
    "Crimen inverso: los estudios simulan con el mismo modelo directo que usa el estimador (sin fuga "
    "entre pulsos y con ventanas que cubren el ciclo: Tlife = 0.001 ns, b = dt/K). En ese régimen la "
    "Ec. 3.5 es exacta y el MLE alcanza el CRB, así que la simulación no puede detectar el desajuste "
    "de modelo que aparece con τ = 4.21 ns y la ventana [0, 10.1] ns medidos (F104). F201 es la "
    "otra mitad: el mismo supuesto aplicado a los estudios.")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dump(obj, name):
    with open(os.path.join(RES, name), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def state_claims(state, prefix, status=None):
    out = []
    for c in state["claims"]:
        t = c["text"]
        if t.startswith(prefix) and (status is None or c["status"] == status):
            out.append(c)
    return out


def verified_text(state, prefix):
    cs = state_claims(state, prefix, "verified")
    if not cs:
        raise SystemExit("sin afirmación verificada en state.json para %r" % prefix)
    return " || ".join(c["text"] for c in cs)


def C(frm, to, src):
    return {"from": frm, "to": to, "source": src}


# ---------------------------------------------------------------------------------------------
# Hallazgos verificados
# ---------------------------------------------------------------------------------------------

T_SIM = "tests/test_simulate.py::"
T_EST = "tests/test_estimate.py::"
T_WIN = "tests/test_windows.py::"
T_USE = "tests/test_usability.py::"


def refresh_fix_status(txt):
    """R3: 'pendiente R2 (Wn): X. Test fijado, aún no verificado.' -> estado real después de R2.

    En R2 el verificador comprobó que los v2_test existen y pasan (state.json, r02-verifier.md).
    """
    txt = re.sub(r"^pendiente R2 \(([^)]*)\): ", r"implementado en v2 (R2, \1): ", txt)
    txt = re.sub(r" Tests? fijados?, aún no verificados?\.$",
                 " El test v2 existe y pasa (verificado en R2).", txt)
    return txt


def findings_spec():
    """Contenido curado por hallazgo. Lo no listado acá (script, fix...) se toma del borrador."""
    S = {}

    S["F101"] = dict(
        src="A", verifier=VA, state_prefix="F101",
        title="sim_exp: en un ciclo con fotones de ≥2 haces sobrevive el de índice k más alto "
              "(un TCSPC real se queda con el más temprano)",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":511-527 (np.nonzero recorre por filas y "
                        "Tmicro[m1] = k1*Texp + Exp se sobrescribe, l.522-527); recorte a 1 fotón por "
                        "ranura en l.464",
        scenario="Mecanismo: tasa alta, 0.8 fotones/ciclo (verificador A: 60 llamadas, 8e4 fotones). "
                 "Impacto: tasa de los estudios, 0.0105 fotones/ciclo (M_p = 2e5, Nh = 2100), y tasas "
                 "del tracking, 1e-3 a 5e-3 fotones/ciclo.",
        impact="A 0.8/ciclo sim_exp coincide con la regla 'gana el k más alto' (|z| ≤ 1.5) y se aparta "
               "de p hasta 47 SE. A 0.0105/ciclo el 0.379 % de los ciclos ocupados tiene ≥2 haces y el "
               "sesgo relativo máximo es 0.461 %; por localización de 2000 fotones es ≤0.09–0.10 SE "
               "(MIX-STUDY). Latente a las tasas del tracking (1e-3 a 5e-3/ciclo): ≤0.05 SE por "
               "localización (MIX-TRACKING).",
        author="no verificable",
        author_basis=BASIS_TS_NV + ". El bucle de sobrescritura (l.521-527, comentarios en inglés) es "
                     "compatible con el código original; el recorte de l.464 está en la ruta rápida "
                     "(indicio de la autora, verificador A) y conserva el mismo comportamiento.",
        what_was_right="El recorte a 1 fotón por ranura y el muestreo en dos pasos (multinomial por haz "
                       "+ ciclos uniformes) son exactos por factorización (F152); a las tasas de los "
                       "estudios y del tracking el efecto es despreciable por localización.",
        v2_test=T_SIM + "TestSimulateTCSPC::test_earliest_matches_mixing_predictor",
        v2_tests=[T_SIM + "TestSimulateLegacy::test_highest_overwrite_emulation (antes)",
                  T_SIM + "TestSimulateTCSPC::test_earliest_matches_mixing_predictor (después)"],
        v2_fix_status="pendiente R2 (W2): simulate.py con tcspc='earliest' y tiempo muerto; "
                      "tcspc='highest' emula el legado. Test fijado, aún no verificado.",
        corrections=[
            C("0.38 % de ciclos con ≥2 haces; sesgo relativo máximo 0.46 %",
              "0.379 % y 0.461 % a 0.0105/ciclo", VA + " (state.json F101)"),
            C("escenario 0.5 fotones/ciclo, 60000 fotones, hasta 25 SE (borrador W2)",
              "0.8 fotones/ciclo, |z| ≤ 1.5 contra 'highest', hasta 47 SE (números verificados)",
              VA + " (state.json F101)"),
            C("impacto 'ver W1'", "latente a las tasas del tracking (≤0.05 SE por localización)",
              "r02-pi.md Tarea 1 + state.json MIX-TRACKING"),
        ],
    )

    S["F102"] = dict(
        src="A", verifier=VA, state_prefix="F102",
        title="Los ceros de los ciclos vacíos en relTime se cuentan en la ventana 0 si la ventana abre "
              "antes del pulso (a < 0)",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":517 (Tmicro = np.zeros(M_p)), :569 (concatenate), "
                        ":996 (relTime > ti estricto)",
        scenario="TCP beams(K=4, L=100), fwhm 360, emisor (5,−5), Ns = 2000, Nb = 95, M_p = 2e5, "
                 "Tlife = 0.001, dt = 50, b = 12.5; a = 0 frente a a = −0.25 ns; 20 repeticiones.",
        impact="relTime trae 200095 elementos, 198000 de ellos 0.0 exacto (los ciclos vacíos). Con "
               "a = −0.25 ns la ventana 0 cuenta ~198037 fotones y el error medio del MLE es 70 nm "
               "(1.25 nm con a = 0). Con a = 0 funciona solo por la desigualdad estricta. Latente: "
               "todos los estudios usan a = 0.",
        author="no verificable", author_basis=BASIS_TS_NV + ".",
        what_was_right="Con a = 0 y la desigualdad estricta el conteo es correcto: los ceros quedan "
                       "fuera de todas las ventanas.",
        v2_test=T_SIM + "TestSimulateLegacy::test_legacy_counting_zeros_in_window0",
        v2_tests=[T_SIM + "TestSimulateLegacy::test_legacy_counting_zeros_in_window0 (antes y después)",
                  T_SIM + "TestSimulateMixing::test_irf_negative_start_and_wrap (corrección)"],
        v2_fix_status="pendiente R2 (W2): counting='periodic' sin ceros; counting='legacy' reproduce "
                      "el defecto. Test fijado, aún no verificado.",
        corrections=[
            C("error medio 1.28 nm (a = 0) y 69.9 nm (a = −0.25)", "1.25 nm y 70 nm",
              VA + " (state.json F102)"),
            C("'el MLE termina en el borde en el 100 %, estimación media (74.4,−4.2) nm'",
              "se omite: no figura en el texto verificado", "r02-pi.md: números de state.json"),
        ],
    )

    S["F103"] = dict(
        src="A", verifier=VA, state_prefix="F103 (",
        title="nMINFLUX no pliega las ventanas módulo el período ni controla el solapamiento",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":993-997",
        scenario="S1: ceros filtrados, a = −0.5 ns, b = 12.5 ns, τ = 4.21 y 0.001 ns, TCP, emisor "
                 "(5,−5), SBR 21. S2: b = 13 ns > dt/K.",
        impact="S2: se cuenta dos veces el 10.9 % (τ = 4.21 ns) / 94.9 % (τ = 0.001 ns) de los "
               "fotones, sin aviso. S1: la ventana 0 pierde el tramo [49.5, 50) ns; la pérdida esperada "
               "es 6.84 % (τ = 4.21) / 2.54 % (τ = 0.001) de sus cuentas. Con τ = 4.21 la estimación "
               "asintótica se desplaza 0.338 nm respecto de ventanas periódicas. Es un desplazamiento, "
               "no un sesgo que se suma: con τ = 4.21 el sesgo total con las ventanas del legado "
               "(0.88 nm) es menor que con ventanas periódicas (1.18 nm), porque el recorte compensa en "
               "parte la fuga; con τ = 0.001 sí suma 0.063 nm. Latente: los estudios usan a = 0 y "
               "b = dt/K.",
        author="no verificable", author_basis=BASIS_TS_NV + ".",
        what_was_right="Con a = 0 y b ≤ dt/K, que es lo que usan todos los estudios, las ventanas son "
                       "correctas.",
        v2_test=T_SIM + "TestSimulateLegacy::test_legacy_counting_non_periodic",
        v2_tests=[T_SIM + "TestSimulateLegacy::test_legacy_counting_non_periodic (antes y después)",
                  T_SIM + "TestSimulateMixing::test_irf_negative_start_and_wrap (corrección)"],
        v2_fix_status="pendiente R2 (W2): ventanas plegadas módulo T (counting='periodic'). Test "
                      "fijado, aún no verificado.",
        corrections=[
            C("la ventana 0 pierde 5.9 % (τ = 4.21) / 2.8 % (τ = 0.001)",
              "pérdida esperada 6.84 % / 2.54 % (los del borrador eran MC de 30 llamadas)",
              VA + " (state.json F103-num, refuted) + " + INBOX_R2),
            C("sesgo asintótico extra del MLE 0.34 nm (τ = 4.21) y 0.06 nm (τ = 0.001)",
              "desplazamiento de 0.338 nm; sesgo total 0.88 nm (legado) contra 1.18 nm (periódico) "
              "con τ = 4.21; con τ = 0.001 suma 0.063 nm",
              VA + " (state.json F103-num, refuted) + " + INBOX_R2),
            C("fotones contados dos veces: 11.2 % (τ = 4.21)", "10.9 %", VA + " (state.json F103)"),
            C("'fondo 0.24 vs 0.25 del ciclo'", "se omite: no figura en el texto verificado",
              "r02-pi.md: números de state.json"),
        ],
    )

    S["F104"] = dict(
        src="A", verifier=VA, state_prefix="F104",
        title="pos_MINFLUX/crb_minflux (Ec. 3.5: fondo 1/K, sin fuga) no describen ventanas b < T/K ni "
              "la fuga entre pulsos",
        cls="CONCEPTUAL",
        legacy_location=LEG + "tools/" + TS + ":1041 (p de pos_MINFLUX), :649-661 (crb_minflux), "
                        "comentario 'EXACTAMENTE' :433 (bloque :423-440)",
        scenario="TCP beams(K=4, L=100), fwhm 360; setup medido τ = 4.21 ns, ventana [0, 10.1] ns, "
                 "dt = 50 ns; SBR 21 (2000/95) y 6 (2000/333); posiciones (5,−5), (−5.07,−7.56), (20,0), "
                 "(−15,15) y (0,−30) nm. Sesgo asintótico (sin ruido) del MLE con el modelo de "
                 "pos_MINFLUX sobre los conteos esperados exactos de sim_exp+nMINFLUX; la mezcla C se "
                 "validó contra sim_exp en MIX-VALID.",
        impact="Setup medido, SBR 21: sesgo 0.85 / 1.51 / 1.63 / 2.69 / 2.36 nm en las 5 posiciones = "
               "1.04–2.67 veces el CRB de crb_minflux (0.82–1.22 nm), o 0.92–2.45 veces el CRB real. El "
               "CRB real es 8.6–13.5 % mayor que el de crb_minflux; unos 2.5 puntos de ese cociente "
               "vienen de los fotones que caen fuera de las ventanas (√(2095/1993.5) = 1.025). La "
               "ventana 0 en (5,−5) tiene 45.8 % de fotones de otros haces. SBR 6: 0.59–2.32 nm. Domina "
               "la fuga: con b = 12.5 y fuga el sesgo ya es 1.05–2.78 nm; solo b = 10.1 sin fuga da "
               "0.01–0.48 nm (SBR en ventanas 26.06). Es sistemático: en unidades de CRB crece como √N. "
               "En la configuración de los estudios (Tlife = 0.001, b = 12.5) el sesgo es 0, así que no "
               "cambia ningún número publicado; el efecto sobre los estudios es F201.",
        author="no verificable",
        author_basis=BASIS_TS_NV + ". El modelo es la Ec. 3.5 de la tesis de Masullo (crb_minflux cita "
                     "la aproximación de Balzarotti et al. S29, l.651). El comentario de l.423-440 que "
                     "lo declara 'EXACTAMENTE' el modelo es de la autora (" + BASIS_FASTPATH + "), y es "
                     "correcto en el régimen en que ella lo verificó.",
        what_was_right="La autora verificó empíricamente que el fondo uniforme reproduce la Ec. 3.5 con "
                       "b = dt/K y sin fuga, y eso es exacto (sesgo 0 en la configuración de los "
                       "estudios; F290-D4). La Ec. 3.5 es el modelo estándar de la literatura; el "
                       "problema es usarla fuera de ese régimen.",
        v2_test=T_EST + "TestEstimate::test_mixing_mle_unbiased_at_measured_setup",
        v2_tests=[T_EST + "TestEstimate::test_legacy_mle_bias_matches_F104 (antes)",
                  T_EST + "TestEstimate::test_mixing_mle_unbiased_at_measured_setup (después)",
                  T_SIM + "TestSimulateMixing::test_low_rate_matches_mixing_window_probs "
                          "(modelo directo correcto)"],
        v2_fix_status="pendiente R2 (W2/W3): simulador con fuga y estimador con matriz de mezcla C y "
                      "fondo b/T. Tests fijados, aún no verificados.",
        corrections=[
            C("CRB 0.82–1.22 nm (sesgo 1.0–2.7 CRB)",
              "1.04–2.67 veces el CRB de crb_minflux, o 0.92–2.45 veces el CRB real",
              VA + " (r01-verifier-A.md, F104)"),
            C("sin matices", "domina la fuga (con b = 12.5 ya da 1.05–2.78 nm); ~2.5 puntos del "
              "cociente de CRB vienen de los fotones fuera de las ventanas; no cambia números "
              "publicados (Tlife = 0.001)", VA + " (state.json F104) + r02-pi.md"),
            C("46 % de fotones de otros haces; SBR en ventanas 26.1", "45.8 %; 26.06",
              VA + " (state.json F104)"),
            C("'verificado por MC: chi2 p = 0.38 mezcla, chi2 = 2559 ingenuo'",
              "se remite a MIX-VALID (reproducido con otro λ por el verificador A)",
              "r02-pi.md: números de state.json"),
        ],
    )

    S["F106"] = dict(
        src="A", verifier=VA, state_prefix="F106",
        title="Emisor y MLE atados a la grilla de la PSF: el emisor se ajusta al nodo y el argmax "
              "discreto cuantiza",
        cls="DISENO",
        legacy_location=LEG + "tools/" + TS + ":444 (λ = psf[i, r0[0], r0[1]]), :93-106 "
                        "(spaceToIndex), :1099 (argmax)",
        scenario="TCP ideal, fwhm 360, grilla 200 nm / 1 nm, SBR 21. (a) Emisor pedido en (−5.07,−7.56). "
                 "(b) N = 2095 / 20950 / 104750, emisor en el nodo (5,−5) y fuera del nodo.",
        impact="El emisor pedido en (−5.07,−7.56) se simula en el nodo (−5,−8). En el nodo hay "
               "supereficiencia artificial: con N = 104750 el RMSE es 0 (todas las estimaciones caen "
               "exactas en el nodo) con un CRB de 0.115 nm. Fuera del nodo la cuantización da RMSE/CRB "
               "~3.3–3.4 con un sesgo de redondeo de ~(−0.25, 0.25) nm.",
        author="no verificable",
        author_basis=BASIS_TS_NV + ". El diseño de grilla (λ leído en el nodo, argmax discreto) es "
                     "compatible con el código original; el redondeo de spaceToIndex (comentario en "
                     "español, l.100-105) es una corrección posterior.",
        what_was_right="spaceToIndex redondea al píxel más cercano en lugar de truncar (corrección "
                       "verificada en F153) y la autora documentó el término de cuantización px²/12 "
                       "(curva √(CRB² + px²/12) de su figura de eficiencia).",
        v2_test=T_EST + "TestEstimate::test_continuous_offgrid_no_quantization",
        v2_tests=[T_EST + "TestEstimate::test_continuous_offgrid_no_quantization"],
        v2_fix_status="pendiente R2 (W3): λ evaluado en r continuo y MLE continuo acotado. Test "
                      "fijado, aún no verificado.",
        corrections=[
            C("fuera de nodo RMSE/CRB 3.40, sesgo de redondeo (−0.22, 0.25) nm",
              "~3.3–3.4 y ~(−0.25, 0.25) nm", VA + " (state.json F106)"),
        ],
    )

    S["F107"] = dict(
        src="A", verifier=VA, state_prefix="F107",
        title="sim_exp('p_minflux') ignora t_mask (parpadeo) en silencio",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":454-466 (_photons_ready = True en la ruta rápida), "
                        ":473-491 (la máscara solo se aplica en la otra ruta)",
        scenario="t_mask = 0 en la primera mitad de M_p = 2e5 ciclos, Ns = 2000, Nb = 0.",
        impact="p_minflux pone el 51.35 % de los fotones en la mitad apagada: la máscara no tiene "
               "efecto. Latente: todos los estudios pasan t_mask = None.",
        author="autora", author_basis=BASIS_FASTPATH + ".",
        what_was_right="La ruta rápida es estadísticamente equivalente al multinomial original (exacta "
                       "por factorización, F152) y ~100 veces más rápida; el comentario de l.473 "
                       "('only for cw_minflux / non-fast path') deja a la vista que la máscara solo se "
                       "aplica en la otra ruta.",
        v2_test=T_SIM + "TestSimulateBlinking::test_t_mask_blinking_F107",
        v2_tests=[T_SIM + "TestSimulateBlinking::test_t_mask_blinking_F107"],
        v2_fix_status="portado en R3 (W1): simulate_counts(..., t_mask=M ciclos 0/1, extensión "
                      "periódica); en un ciclo apagado no hay fotones de señal (el fondo sigue). "
                      "Con t_mask = 0 en la primera mitad y sin fondo, 0 fotones en la mitad apagada "
                      "(el legado: 51.35 %). Pendiente de verificación en R3.",
        corrections=[
            C("51.4 %", "51.35 %", VA + " (state.json F107)"),
            C("'cw_minflux con la misma máscara: 0'",
              "se omite: la rama cw quedó sin verificar (F154 unclear)", VA + " (state.json F154)"),
            C("autoría 'la autora (refactor), a confirmar'",
              "'autora' con base 'indicio: comentario en español; sin git'", "r02-pi.md defaults"),
        ],
    )

    S["F108"] = dict(
        src="A", verifier=VA, state_prefix="F108",
        title="cov_ellipse ordena mal los autovectores y no usa el nivel de confianza",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":80-90",
        scenario="Covarianza con desvíos 3 y 1 nm y eje mayor a φ = 0, 30, 60, 120 y 150°; nsig = 1 y 2.",
        impact="Usa vec[order] en lugar de vec[:, order]: el eje mayor sale con un error de −90, −90, "
               "−30, +30 y −90° (leído con la convención de matplotlib Ellipse), que no es un cambio de "
               "convención constante. Los ejes salen siempre 2 y 6, sin r2. No se usa en ningún "
               "script: latente.",
        author="no verificable",
        author_basis=BASIS_TS_NV + ". El TODO sobre r2 (l.87) ya marcaba la parte del nivel de "
                     "confianza como pendiente.",
        what_was_right="Los ingredientes son los correctos (autovalores de la covarianza y chi2.ppf "
                       "para r2), y el propio código dejó un TODO sobre r2. La función no se usa en "
                       "ningún script, así que no afectó ningún resultado.",
        v2_test=T_EST + "TestEstimate::test_cov_ellipse_orientation",
        v2_tests=[T_EST + "TestEstimate::test_cov_ellipse_orientation"],
        v2_fix_status="pendiente R2 (W3): cov_ellipse corregido en estimate.py. Test fijado, aún no "
                      "verificado.",
        corrections=[
            C("ejes correctos 3.03/9.09 y 4.97/14.92",
              "se omiten: no figuran en el texto verificado", "r02-pi.md: números de state.json"),
        ],
    )

    S["F109"] = dict(
        src="A", verifier=VA, state_prefix="F109",
        title="psf(): la rama gaussiana ignora donut_fwhm, la rama SW da NameError y fov_center desplaza "
              "x con el signo opuesto a y",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":181-199",
        scenario="psf(d='gaussian', donut_fwhm=250); psf(d='sw'); dona en (0,0) con fov_center = (20,20).",
        impact="La FWHM gaussiana medida es 361 px cuando se piden 250; la rama SW da NameError; con "
               "fov_center (20,20) el cero de una dona en (0,0) cae en el índice (120,120): x se "
               "desplaza con el signo opuesto a y. Latente: todos los usos son d='donut' con "
               "fov_center = [0,0].",
        author="no verificable", author_basis=BASIS_TS_NV + ".",
        what_was_right="La rama 'donut' con fov_center = [0,0], que es la única que se usa, es "
                       "consistente con indexToSpace (F153) y respeta donut_fwhm.",
        v2_test=T_EST + "TestPSF::test_fwhm_honored_and_any_K",
        v2_tests=[T_EST + "TestPSF::test_fwhm_honored_and_any_K",
                  T_EST + "TestPSF::test_matches_legacy_beams_and_doughnut"],
        v2_fix_status="pendiente R2 (W3): psf.donut(r, fwhm) respeta la fwhm. Test fijado, aún no "
                      "verificado.",
        corrections=[
            C("FWHM 361 nm; centro real (−20.5, 20.5)",
              "361 px; cero de (0,0) en el índice (120,120)", VA + " (state.json F109)"),
            C("autoría 'donut_fwhm lo agregó la autora; SW y fov_center: original, a confirmar'",
              "no verificable", "r02-pi.md defaults + " + VA + " (autoría unclear)"),
        ],
    )

    S["F110"] = dict(
        src="A", verifier=VA, state_prefix="F110",
        title="SBR = inf (sin fondo) da NaN: pos_MINFLUX devuelve la esquina del FOV y crb_minflux NaN, "
              "sin aviso",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":1041, :1050, :649-653",
        scenario="TCP ideal, grilla 200/1 nm, emisor (5,−5), cuentas esperadas 1000·p, SBR = inf frente "
                 "a SBR = 1e12.",
        impact="Con SBR = inf pos_MINFLUX devuelve (−100, 100) y crb_minflux es NaN en toda la grilla; "
               "con SBR = 1e12 la estimación es (5,−5). Latente.",
        author="no verificable", author_basis=BASIS_TS_NV + ".",
        what_was_right="Con cualquier SBR finito, incluso 1e12, pos_MINFLUX y crb_minflux funcionan; "
                       "SBR/(SBR+1) es la parametrización estándar, y el reemplazo NaN → −inf para los "
                       "bordes con normPSF = 0 es correcto (D-vi).",
        v2_test=T_EST + "TestEstimate::test_sbr_inf",
        v2_tests=[T_EST + "TestEstimate::test_sbr_inf"],
        v2_fix_status="pendiente R2 (W3): sbr = inf sin NaN. Test fijado, aún no verificado.",
        corrections=[
            C("'CRB 1.05 nm con SBR = 1e12'", "se omite: no figura en el texto verificado",
              "r02-pi.md: números de state.json"),
            C("autoría 'Masullo (expresión original)'", "no verificable",
              "r02-pi.md defaults + " + VA + " (autoría unclear)"),
        ],
    )

    S["F111"] = dict(
        src="A", verifier=VA, state_prefix="F111 (",
        title="ebp_centres falla para K ≠ 4: L = [L, L, L, L] tiene largo fijo",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "tools/" + TS + ":266",
        scenario="ebp_centres(K, 100, center) con K = 4, 5 y 7, center True y False.",
        impact="K = 5 y K = 7 dan IndexError (con center True y False). Con K = 4 coincide con beams(). "
               "Latente: los estudios actuales usan ebp.py.",
        author="Masullo-original",
        author_basis="docstring '[Lars] This is the new version of the old beams() function' (l.250): "
                     "L. Richter, coautor del código original según el encabezado de "
                     "tools_simulations.py; sostenido por el verificador A (r01); sin git",
        what_was_right="Con K = 4 la geometría coincide con beams(). Los comentarios de paridad son "
                       "correctos: en la rama sin centro literalmente, y en la rama con centro si se "
                       "leen para Kθ = K − 1 haces periféricos. La autora centralizó la geometría en "
                       "ebp.py.",
        fix="L = np.full(K, L); un solo generador de geometría (ebp.py / psf.beam_positions).",
        v2_test=T_EST + "TestPSF::test_fwhm_honored_and_any_K",
        v2_tests=[T_EST + "TestPSF::test_fwhm_honored_and_any_K"],
        v2_fix_status="pendiente R2 (W3): psf.beam_positions(K, L, center) para K arbitrario. Test "
                      "fijado, aún no verificado.",
        corrections=[
            C("título: '... y los comentarios de paridad están invertidos'",
              "se quita la afirmación de paridad; queda solo el IndexError con K = 5 y K = 7",
              VA + " (state.json F111-comentarios, refuted) + " + INBOX_R2),
            C("fix: '...; corregir comentarios; ...'", "se quita 'corregir comentarios'",
              VA + " (state.json F111-comentarios, refuted)"),
            C("ubicación ':266, :273-289'", ":266", VA + " (state.json F111)"),
            C("'ángulos 120/240/0 frente a ebp.ideal_positions 210/330/90'",
              "se omite: no figura en el texto verificado", "r02-pi.md: números de state.json"),
        ],
    )

    S["F201"] = dict(
        src="B", verifier=VB, state_prefix="F201:",
        title="Los estudios apagan la fuga entre pulsos (Tlife = 0.001 ns, a = 0, b = dt/K): con "
              "τ = 4.21 ns y la ventana [0, 10.1] ns el ideal honesto pasa de |b| ≈ 0.1 nm a ≈ 3 nm y "
              "de RMSE/CRB 1.07 a ≈2.5 (contra el CRB con fuga)",
        cls="DISENO",
        legacy_location=LEG + "simulation_misalignment.py:55,99-100; " + LEG +
                        "documento/make_fig_eficiencia.py:40,76-77; " + LEG +
                        "simulations_example.py:51,134-136 (Masullo, dt = 25, l.47)",
        scenario="Pipeline legado sim_exp + nMINFLUX + pos_MINFLUX, corrido como lo corre la autora "
                 "(Ns = 2000, Nb = 95, r0 = (−5.07,−7.56) nm, que se simula en el píxel (−5,−8), 1000 "
                 "muestras, R = 0.75·L_eff). Solo cambian (Tlife, b): C0 = (0.001, 12.5), "
                 "C1 = (0.001, 10.1), C2 = (4.21, 12.5), C3 = (4.21, 10.1). Semillas 20260825 (la del "
                 "worker) y 777 (verificador B).",
        impact="Ideal honesto, C0 → C3: |b| 0.06–0.11 → 2.96–2.98 nm; RMSE/CRB 1.07 → 2.73–2.75 contra "
               "el CRB sin fuga (0.864 nm) que usa el estudio, o ≈2.5 contra el CRB de un estimador que "
               "conoce la fuga (0.945 nm). Se reproduce exactamente con la semilla 20260825 y dentro "
               "del ruido con la 777. Realista honesta: |b| 0.13–0.18 → 1.88–1.94 nm. Realista "
               "ingenua: 5.4–5.5 → 10.2–10.9 nm (RMSE 13.0 → 24–25 nm). El sesgo asintótico "
               "independiente (sin MC) en el ideal C3 es (−1.02, −2.67) nm, |b| = 2.85, y coincide con "
               "el MC a 0.1–0.2 nm en los casos honestos. Descomposición: ventana sola 0.30 nm, fuga "
               "sola 3.03 nm (domina la fuga). Eficiencia (ideal, SBR 9): RMSE/CRB 0.97 → 1.19 con "
               "N = 100 y 0.98 → 1.53 con N = 1600. El supuesto τ ≈ 0 no está declarado en el .docx ni "
               "en los scripts, así que la conclusión 'el honesto alcanza el CRB' vale sin fuga pero "
               "no para el experimento a 20 MHz.",
        author="autora",
        author_basis=BASIS_AUTORA + ". El defecto viene de Masullo: Tlife = 0.001 ya está en "
                     "simulations_example.py:51 y b = dt/K en :134-136 (setup de 40 MHz, dt = 25), "
                     "archivo que NOTAS.txt declara original de L. Masullo; la autora lo mantuvo en sus "
                     "estudios a 20 MHz.",
        what_was_right="sim_exp sí modela la fuga con el pliegue periódico (% dt), que para los "
                       "conteos equivale a la matriz de mezcla (C_ii = 0.909 y 0.047 del haz anterior "
                       "con τ = 4.21 y [0, 10.1]). Con Tlife = 0.001 y b = dt/K el fondo reproduce "
                       "exactamente la Ec. 3.5 (ella lo verificó; F290-D4 lo confirma). La separación "
                       "honesto/ingenuo e ideal/geom/exp es un buen diseño y la comparación es justa "
                       "(F290-D7). Ella ya anotó como extensión pendiente 'incorporar drift, blinking, "
                       "IRF y lifetime medidos' (ESTADO_Y_PLAN_REALISMO_PSF.md:115-117).",
        v2_test=T_SIM + "TestSimulateLegacy::test_short_lifetime_turns_off_leakage",
        v2_tests=[T_SIM + "TestSimulateLegacy::test_short_lifetime_turns_off_leakage",
                  T_USE + "TestStudyV2::test_study_v2_json"],
        v2_fix_status="pendiente R2 (W2/W3): el comparativo legado contra v2 corre con τ = 4.21 y "
                      "[0, 10.1]. R3: el estudio de desalineación y de eficiencia se rehízo con v2 en "
                      "el setup medido (scripts/study_misalignment_v2.py -> results/study_v2.json; "
                      "pendiente de verificación en R3).",
        corrections=[
            C("clase CONCEPTUAL", "DISENO", INBOX_R2 + " (recomendación de " + VB + ")"),
            C("RMSE/CRB 2.75 (CRB 0.864 nm); título '~2.9 nm (3.4 CRB) y RMSE/CRB 2.75'",
              "2.73–2.75 contra el CRB sin fuga (0.864 nm); ≈2.5 contra el CRB con fuga (0.945 nm)",
              VB + " (state.json F201 clase, unclear) + " + INBOX_R2),
            C("'sin declararlo' (class_note)",
              "'no declarado en el .docx ni en los scripts' + crédito a "
              "ESTADO_Y_PLAN_REALISMO_PSF.md:115-117", VB + " + r02-pi.md"),
            C("|b| 0.11 → 2.98; realista honesta 0.18 → 1.94; realista ingenua 5.5 → 10.8, RMSE "
              "13.0 → 24.8", "rangos de las dos semillas: 0.06–0.11 → 2.96–2.98; 0.13–0.18 → "
              "1.88–1.94; 5.4–5.5 → 10.2–10.9, RMSE 13.0 → 24–25", VB + " (state.json F201)"),
            C("descomposición ≈0.25 / ≈3.1 nm; asintótico (−0.98, −2.75)",
              "0.30 / 3.03 nm; (−1.02, −2.67), |b| = 2.85", VB + " (state.json F201)"),
            C("eficiencia N = 100 0.97 → 1.23, N = 1600 1.06 → 1.65",
              "0.97 → 1.19 y 0.98 → 1.53 (semilla del verificador; los del worker son compatibles "
              "dentro del ruido MC)", VB + " (state.json F201)"),
        ],
    )

    S["F202"] = dict(
        src="B", verifier=VB, state_prefix="F202:",
        title="realistic_ebp normaliza cada PSF por su propio máximo y descarta intensity_scale: si el "
              "máximo del .npy refleja la potencia del haz, el modelo 'realista' pierde potencias "
              "relativas de hasta ×1.379, que en p-MINFLUX fijan p_i",
        cls="DISENO",
        legacy_location=LEG + "tools/realistic_ebp.py:100-103 (target = image/scale), 152 "
                        "(intensity_scale se guarda y no se usa), 181-185 (ebp_realistic), docstring 5-6; "
                        + LEG + "analyze_realistic_psf.py:122-140",
        scenario="Escalera de modelos reconstruida desde fit_parameters.csv (se reproduce "
                 "comparison_metrics.csv al 4.º decimal con la semilla 20260901). Después, a cada PSF "
                 "se le aplica su intensity_scale (21.02, 16.65, 22.96, 22.86; máx/mín 1.379). Supuesto "
                 "explícito: el máximo de cada .npy refleja la potencia relativa del haz (× la "
                 "eficiencia de detección). Lo apoya que el orden de los máximos se repite en las 3 "
                 "calibraciones disponibles (20260703: 245/205/291/253; 20260707: 6.4/4.8/6.8/5.3; "
                 "20260924: 21.2/18.4/26.6/19.7), pero sigue siendo un supuesto a confirmar con la autora.",
        impact="Bajo ese supuesto, p_señal en el emisor pasa de [0.111, 0.262, 0.314, 0.313] a [0.111, "
               "0.207, 0.342, 0.340]. El CRB casi no cambia (2.348 → 2.333 nm), pero el estimador "
               "realista sin potencias sobre datos con potencias queda sesgado 10.6 nm (asintótico "
               "10.60, MC 10.65). Sin depender del supuesto: la etapa 'experimental' de la escalera usa "
               "los .npy crudos con su escala y las demás no, así que el salto 9.66 → 35.6 nm mezcla "
               "la estructura no modelada con este cambio de normalización. El docstring "
               "(realistic_ebp.py:5-6) declara unidades relativas al máximo de cada PSF: el código "
               "hace lo que dice, y por eso es DISENO.",
        author="autora", author_basis=BASIS_AUTORA + ".",
        what_was_right="Ajuste 2D robusto (soft-L1) con el centro refinado localmente, separación "
                       "explícita pedestal/fondo Nb, escalera reproducible con semilla (se reproduce "
                       "al 4.º decimal) y MC rápido equivalente a pos_MINFLUX. Ella misma recomienda "
                       "'permitir distinta potencia entre haces' (ESTADO_Y_PLAN_REALISMO_PSF.md:116) "
                       "y advierte que las elipticidades son 'parámetros efectivos'; el aporte nuevo "
                       "es cuantificarlo y mostrar que contamina la escalera.",
        v2_test=T_EST + "TestEstimate::test_free_powers_removes_bias",
        v2_tests=[T_EST + "TestEstimate::test_free_powers_removes_bias"],
        v2_fix_status="pendiente R2 (W3): mle_mixing(free_powers=True) y beam_powers en simulate. "
                      "Test fijado, aún no verificado.",
        corrections=[
            C("clase IMPLEMENTACION", "DISENO",
              INBOX_R2 + " + " + VB + " (state.json F202 clase, refuted)"),
            C("supuesto 'máximo del .npy = potencia' solo en el reporte del worker",
              "explícito en scenario e impact, con el orden repetido en 3 calibraciones",
              VB + " (state.json F202 clase, refuted) + " + INBOX_R2),
            C("sin crédito", "crédito a ESTADO_Y_PLAN_REALISMO_PSF.md:116 ('permitir distinta "
              "potencia entre haces')", VB + " + " + INBOX_R2),
            C("'el estimador de geometría pasa de |b| 5.1 a 8.8 nm'",
              "se omite (el verificador obtuvo 8.5 en MC; no figura en el texto verificado)",
              VB + " (r01-verifier-B.md F202)"),
        ],
    )

    S["F203"] = dict(
        src="B", verifier=VB, state_prefix="F203:",
        title="En los casos ingenuos (y en los honestos con N bajo) el RMSE y el |sesgo| dependen del "
              "radio de búsqueda R; no se reporta la fracción de estimaciones en el borde; la tabla "
              "mezcla un RMSE por eje con un |sesgo| 2D",
        cls="DISENO",
        legacy_location=LEG + "simulation_misalignment.py:75,178,222-232,265-277; " + LEG +
                        "documento/make_fig_eficiencia.py:44,89,118-125; " + LEG +
                        "analyze_realistic_psf.py:88,147",
        scenario="Casos 'Realista ingenua' y 'Experimental ingenua' (sustituto medido 20260703, "
                 "rotulado como tal) variando solo R_SEARCH_FACTOR ∈ {0.5, 0.75, 1.0, 1.25}·L; 1000 "
                 "muestras; N = 2095 y N = 100 (SBR 9).",
        impact="Realista ingenua (N = 2095): RMSE 12.1 / 13.2 / 50.0 / 81.9 nm con el 0 / 1 / 50 / 87 % "
               "en el borde para R = 0.5 / 0.75 / 1.0 / 1.25·L. Sustituto 20260703 ingenuo: |b| 48 / 72 "
               "/ 96 / 118 nm ≈ R − |r0|, con el 100 % de las estimaciones en el borde solo para "
               "R ≤ 1.0·L (71–72 % con R = 1.25·L). Con el R de la autora (0.75·L) y el EBP realista, "
               "el ingenuo tiene solo un 1 % en el borde: 'lo fija R' vale para el sustituto "
               "experimental y para R ≥ 1.0·L. Con N = 100 incluso el honesto depende de R (realista "
               "12–26 nm). Métrica: en el log |b| = 62.76 nm > RMSE = 46.96 nm porque el RMSE es por "
               "eje y |b| es la norma 2D.",
        author="autora",
        author_basis=BASIS_AUTORA + ". Ella introdujo r_max_nm, que corrige la búsqueda sin cota; lo "
                     "discutible es cómo se reportan los números.",
        what_was_right="Acotar la búsqueda es físicamente correcto (MINFLUX estima localmente) y "
                       "corrigió máximos espurios; el radio sale del tamaño del patrón y es el mismo en "
                       "todos los casos, así que la comparación es justa (F290-D7).",
        v2_test=T_EST + "TestEstimate::test_boundary_fraction_reported",
        v2_tests=[T_EST + "TestEstimate::test_boundary_fraction_reported"],
        v2_fix_status="pendiente R2 (W3): el estimador devuelve la bandera 'en el borde' y el "
                      "comparativo informa la fracción. Test fijado, aún no verificado.",
        corrections=[
            C("'el 100 % de las estimaciones ingenuas queda en el borde para los cuatro R'",
              "100 % en el borde solo para R ≤ 1.0·L (71–72 % con 1.25·L); con R = 0.75 y el EBP "
              "realista el ingenuo tiene un 1 % en el borde",
              VB + " (state.json F203, refuted) + " + INBOX_R2),
            C("realista ingenua RMSE 12.1/13.9/51.0/82.1 nm con 0/1.8/52/87 % en el borde",
              "12.1/13.2/50.0/81.9 nm con 0/1/50/87 %", VB + " (state.json F203)"),
            C("|b| 48/72/96/119; honesto N = 100 11.4–23.4 (realista) y 14.6–41.4 (sustituto)",
              "|b| 48/72/96/118; honesto realista 12–26 nm", VB + " (state.json F203)"),
        ],
    )

    S["F204"] = dict(
        src="B", verifier=VB, state_prefix="F204:",
        title="Los errores estándar suponen estimaciones normales (std/√(2n), RMSE/√(2n)): con N = 100 y "
              "un EBP con pedestal el SE real de RMSE/CRB es 1.6–1.9 veces el impreso; el |sesgo| no "
              "descuenta su piso de ruido",
        cls="DISENO",
        legacy_location=LEG + "simulation_misalignment.py:239-241,270-277; " + LEG +
                        "documento/make_fig_eficiencia.py:124-131",
        scenario="El punto N = 100 de make_fig_eficiencia (SBR 9, r0 = (5,−5), 250 muestras) replicado "
                 "400 veces con semillas independientes; se compara la dispersión real de cada "
                 "estadístico con el SE que imprime el script.",
        impact="SE real / SE impreso de RMSE/CRB = 1.88 (realistic_fit), 1.63 (sustituto 20260703) y "
               "0.77 (ideal, donde el SE impreso es conservador). Exceso de curtosis de las "
               "estimaciones: 6.6/4.6 (realista) contra 0.2/0.1 (ideal). Piso de ruido de |b| en el "
               "ideal ≈0.36 nm con n = 250. Extrapolación desde EBP sustitutos (no medida con las PSF "
               "20260820, que no están): su '1.89 ± 0.08' pasaría a ± ~0.13–0.15; la conclusión "
               "cualitativa se sostiene.",
        author="autora",
        author_basis=BASIS_AUTORA + ". Agregar SE fue una mejora de ella sobre el original, que no "
                     "tenía incertidumbres.",
        what_was_right="Semillas fijas y SE reportados en todos los estadísticos, que el código "
                       "original no tenía; la curva de cuantización √(CRB² + px²/12) de la figura "
                       "explica bien el ascenso del ideal a N alto.",
        v2_test=T_EST + "TestCompare::test_compare_json_complete",
        v2_tests=[T_EST + "TestCompare::test_compare_json_complete (SE bootstrap)"],
        v2_fix_status="pendiente R2 (W3): el comparativo reporta SE bootstrap de cada métrica. Test "
                      "fijado, aún no verificado.",
        corrections=[
            C("'Su 1.89 ± 0.08 pasa a ± ~0.13–0.15'",
              "rotulado como extrapolación desde EBP sustitutos", VB + " (state.json F204) + " + INBOX_R2),
            C("SE real/impreso 1.86 / 1.55 / 0.74; curtosis 6.8/4.7; piso 0.34 nm",
              "1.88 / 1.63 / 0.77; 6.6/4.6; ≈0.36 nm", VB + " (state.json F204)"),
            C("'la no monotonía 1.20 (N = 200) / 1.27 (N = 400) queda dentro del ruido'",
              "se omite: el verificador no la comprobó por separado (faltan las PSF reales)",
              VB + " (r01-verifier-B.md F204)"),
        ],
    )

    S["F205"] = dict(
        src="B", verifier=VB, state_prefix="F205:",
        title="El sesgo se mide contra R0_NM = (−5.07, −7.56) pero el emisor se simula en el píxel "
              "(−5, −8): el desplazamiento de 0.4455 nm aparece como sesgo espurio (|b| 0.43 contra 0.02 nm) "
              "y además invierte el orden honesto/ingenuo",
        cls="IMPLEMENTACION",
        legacy_location=LEG + "simulation_misalignment.py:67,177,230,256; " + LEG +
                        "analyze_realistic_psf.py:36-37,87-88,145-146; núcleo: sim_exp lee "
                        "psf[:, r0[0], r0[1]] (F106)",
        scenario="Casos honestos e ingenuos con N = 2095 y 1e5 muestras (multinomial, equivalente a "
                 "sim_exp en C0); sesgo medido contra R0_NM y contra el píxel realmente simulado.",
        impact="R0_NM = (−5.07, −7.56) se simula en el píxel (−5, −8), un desplazamiento de 0.4455 nm. "
               "El |b| honesto ideal es 0.43 nm contra R0 y 0.02 contra el píxel; con 1000 muestras el "
               "SE de |b| es ≈0.04, así que el artefacto está a ~10σ. La geométrica ingenua da 0.31 "
               "contra R0 y 0.67 contra el píxel: el orden honesto/ingenuo se invierte según la "
               "referencia. La diferencia vectorial (−0.35, 0.56) nm no depende de la referencia. "
               "Impacto extra: el RMSE de la escalera también se calcula contra R0 "
               "(analyze_realistic_psf.py:88). En el ideal el RMSE correcto, contra el píxel "
               "realmente simulado (−5, −8), es 0.912 nm; los 0.960 nm que produce el script legado "
               "están inflados por el desplazamiento de 0.4455 nm. run_final.log "
               "(r0 = (5,−5), entero) no está afectado.",
        author="autora",
        author_basis=BASIS_AUTORA + ". Ella cambió R0_NM a la localización experimental no entera "
                     "(simulation_misalignment.py:67, analyze_realistic_psf.py:36-37); el redondeo a la "
                     "grilla del núcleo es F106 (no verificable).",
        what_was_right="Ella corrigió spaceToIndex para que redondee en lugar de truncar (F153) y usa "
                       "el mismo r0 y la misma grilla en todos los casos, así que las diferencias "
                       "vectoriales entre casos son correctas.",
        v2_test=T_EST + "TestEstimate::test_continuous_offgrid_no_quantization",
        v2_tests=[T_EST + "TestEstimate::test_continuous_offgrid_no_quantization",
                  T_USE + "TestStudyV2::test_study_v2_json"],
        v2_fix_status="pendiente R2 (W3): emisor con λ en r continuo y sesgo contra la posición "
                      "simulada. Test fijado, aún no verificado. R3: scripts/study_misalignment_v2.py "
                      "simula emisores continuos y mide contra la posición simulada "
                      "(results/study_v2.json).",
        corrections=[
            C("sin el impacto en el RMSE",
              "impacto extra: RMSE de la escalera 0.912 → 0.960 nm (analyze_realistic_psf.py:88)",
              VB + " (state.json F205) + " + INBOX_R2),
            C("'pasa de 0.912 a 0.960 nm en el ideal'",
              "0.912 nm es el RMSE correcto (contra el píxel simulado (−5, −8)); 0.960 nm es lo que "
              "produce el script legado, inflado por el desplazamiento de 0.4455 nm",
              "r02-verifier.md (F205, sentido resuelto) + r03-pi.md"),
            C("|b| 0.437 / 0.012 (ideal), 0.302 / 0.663 (geom ingenua); título '0.445 nm'",
              "0.43 / 0.02 y 0.31 / 0.67; 0.4455 nm", VB + " (state.json F205)"),
            C("'los honest_bias_nm de comparison_metrics.csv (0.434 … 0.519) son casi enteramente "
              "este artefacto'", "se omite: no figura en el texto verificado",
              "r02-pi.md: números de state.json"),
        ],
    )

    S["F206"] = dict(
        src="B", verifier=VB, state_prefix="F206:",
        title="La cadena que arma el documento (run_and_save → run_final.log → build_doc) ya no lo "
              "reproduce: el script, el log y los parámetros escritos a mano corresponden a "
              "configuraciones distintas",
        cls="DISENO",
        legacy_location=LEG + "documento/build_doc.py:19,30-41,535-537,812-821; " + LEG +
                        "documento/run_and_save.py:57; " + LEG + "simulation_misalignment.py:50,57,67,96",
        scenario="Chequeo estático (ast y regex) de simulation_misalignment.py, run_final.log y "
                 "build_doc.py.",
        impact="5 discrepancias: 1000 muestras (script) contra 300 (log); r0 (−5.07,−7.56) contra "
               "(5,−5); Ns/Nb 2000/95 contra 90/10 (el CRB 4.28 nm del log corresponde a N = 100); "
               "INCLUDE_REALISTIC_FIT = True sin filas 'Realista' en el log; y CASES incluye "
               "'Experimental ingenua 1/2', que tampoco están en el log. Los parámetros están escritos "
               "a mano en build_doc.py:535-537 y 812-821. Si hoy se corre la cadena, el .docx sale "
               "con números de una configuración y parámetros de otra.",
        author="autora", author_basis=BASIS_AUTORA + ".",
        what_was_right="El Tee de stdout a log y la cadena documentada en el encabezado de build_doc "
                       "son buena práctica de trazabilidad, eficiencia.log es reproducible, y ella ya "
                       "advierte que los logs vienen de configuraciones distintas y que hay que guardar "
                       "configuración, semilla y versión junto a cada resultado "
                       "(ESTADO_Y_PLAN_REALISMO_PSF.md:64-67).",
        v2_test=T_EST + "TestCompare::test_compare_json_complete",
        v2_tests=[T_EST + "TestCompare::test_compare_json_complete (todos los parámetros en el JSON)"],
        v2_fix_status="pendiente R2 (W3): compare_legacy_vs_v2.json registra parámetros, semillas, "
                      "versión y source. Test fijado, aún no verificado.",
        corrections=[
            C("4 discrepancias", "5: se agrega CASES con 'Experimental ingenua 1/2' ausentes del log",
              VB + " (state.json F206) + " + INBOX_R2),
        ],
    )
    return S


ORDER = ["F101", "F102", "F103", "F104", "F106", "F107", "F108", "F109", "F110", "F111",
         "F201", "F202", "F203", "F204", "F205", "F206"]


def build_findings(state, drafts):
    spec = findings_spec()
    out = []
    for fid in ORDER:
        s = spec[fid]
        d = drafts[fid]
        e = {
            "id": fid,
            "title": s["title"],
            "class": s["cls"],
            "legacy_location": s["legacy_location"],
            "scenario": s["scenario"],
            "impact": s["impact"],
            "fix": s.get("fix", d["fix"]),
            "script": d["script"],
            "status": "verified",
            "author": s["author"],
            "author_basis": s["author_basis"],
            "what_was_right": s["what_was_right"],
            "verified_by": s["verifier"] + ": " + verified_text(state, s["state_prefix"]),
            "corrections_applied": s["corrections"],
            "v2_test": s["v2_test"],
            "v2_tests": s["v2_tests"],
            "v2_fix_status": refresh_fix_status(s["v2_fix_status"]),
            "crimen_inverso": fid in ("F104", "F201"),
            "draft_source": "results/findings_%s.json (R1, borrador)" % s["src"],
        }
        if e["crimen_inverso"]:
            e["crimen_inverso_note"] = CRIMEN_INVERSO
        assert e["author"] in ("Masullo-original", "autora", "no verificable"), fid
        assert e["what_was_right"].strip(), fid
        out.append(e)
    return out


# ---------------------------------------------------------------------------------------------
# Descartados
# ---------------------------------------------------------------------------------------------

def build_discarded(state, A, B):
    da = {x["id"]: x for x in A["discarded"]}
    db = {x["id"]: x for x in B["discarded"]}
    out = []

    def add(did, title, loc, evidence, script, prefix, verifier, corrections=(), status="discarded-verified",
            note=None, missing=None):
        cs = state_claims(state, prefix)
        e = {"id": did, "title": title, "legacy_location": loc, "evidence": evidence,
             "script": script, "status": status,
             "verified_by": verifier + ": " + " || ".join(
                 "[%s] %s" % (c["status"], c["text"]) for c in cs),
             "corrections_applied": list(corrections)}
        if note:
            e["note"] = note
        if missing:
            e["missing"] = missing
        out.append(e)

    add("F105", da["F105"]["title"], da["F105"]["legacy_location"],
        "Real pero despreciable: con Ns y Nb fijos la σ del MLE (sándwich) es 0–0.71 % menor que el "
        "CRB multinomial en los 5 puntos (verificador: 0.993–1.000; 0.990 en (40,0)). RMSE/CRB de los "
        "estudios queda sesgado a la baja < 1 %.", da["F105"]["script"], "F105", VA)
    add("F151", da["F151"]["title"], da["F151"]["legacy_location"],
        "Correcto: crb_minflux (método 1, px = 1) coincide con un Fisher continuo independiente dentro "
        "de 4.4e-4 nm (W2: métodos 1–3 contra donutloc dentro de 5.4e-4 con px = 1, error O(px²)).",
        da["F151"]["script"], "F151", VA)
    add("F152", da["F152"]["title"], da["F152"]["legacy_location"],
        "El fondo aporta exactamente Nb·b/T por ventana (lo confirman las 4 campañas del verificador), "
        "el muestreo en dos pasos es exacto por factorización y el pliegue % dt es periódico para los "
        "conteos.", da["F152"]["script"], "F152", VA,
        note="cota ≤3.6e-4 no verificada (pérdida selectiva por haz que impondría un TCSPC real a la "
             "tasa de los estudios)",
        corrections=[C("'pérdida selectiva por haz ≤ 3.6e-4' como evidencia",
                       "nota 'cota ≤3.6e-4 no verificada'", VA + " (state.json F152) + r02-pi.md")])
    add("F153", da["F153"]["title"], da["F153"]["legacy_location"],
        "spaceToIndex con rint coincide con el mínimo de psf() (0/20 discrepancias); el truncado viejo "
        "sesgaba (−0.50, +0.50) nm con px = 1: la corrección de la autora es correcta.",
        da["F153"]["script"], "F153", VA)
    add("F154", da["F154"]["title"], da["F154"]["legacy_location"],
        "Confirmado: np.reshape falla con ValueError cuando M_p no es múltiplo de cycle_time/dt. "
        "Ningún script usa la rama cw.", da["F154"]["script"], "F154", VA, status="unclear",
        missing="No se reprodujo el 88.5 % de fotones en la ventana 0 con nMINFLUX ni el χ² p = 0.74 "
                "con el haz recuperado del macrotiempo; para decidir hace falta re-correr "
                "scripts/findings/F154_cw_minflux_branch.py con otra semilla y un contador por "
                "macrotiempo independiente.",
        corrections=[C("status 'descartado'", "status 'unclear' (88.5 % y p = 0.74 sin reproducir)",
                       VA + " (state.json F154, unclear) + r02-pi.md")])
    for did, key in (("D-iv", "D-iv"), ("D-ii", "D-ii-edges"), ("D-vi", "D-vi-nan")):
        x = da[key]
        add(did, x["title"], x["legacy_location"], x["evidence"], x["script"] or None, "D-iv/D-ii/D-vi",
            VA)

    ev = {
        "F290-D1": ("sim_exp no falla en las configuraciones de los estudios (0/300 con Ns = 2000); el "
                    "margen mínimo de ciclos es 3 / 55 / 76 / 105 para Ns = 90 / 1440 / 2000 / 2880. "
                    "La tasa de fallos es 0 igual, así que no reportarla no cambia nada.",
                    [C("'margen ≥77' (y mínimos 92/1869/2077/2982 > Ns)",
                       "margen mínimo 3/55/76/105 para Ns = 90/1440/2000/2880",
                       VB + " (state.json F290-D1) + r02-pi.md")]),
        "F290-D2": ("La convención de ejes de psf()/Grid/ebp es consistente: una dona independiente "
                    "coincide con ebp_ideal a 3e-16 y argmin = posición redondeada. La orientación "
                    "física respecto del escáner no se puede comprobar desde el código.", []),
        "F290-D3": ("El reshape tras quitar NaN en simulations_example.py:182-183 conserva los pares "
                    "(x, y), porque los NaN vienen por columnas completas.",
                    [C("l.183-184", "l.182-183", VB + " (state.json F290-D3)")]),
        "F290-D4": ("Con Tlife = 0.001 y b = dt/K las fracciones por ventana de sim_exp coinciden con "
                    "el modelo 1/K (628 500 fotones, |z| ≤ 1.3). La conclusión (equivalencia) se "
                    "mantiene.",
                    [C("'z = (−1.4, −1.0, −0.5, +2.6); el exceso del haz 3 (+0.6 %) es el efecto F101'",
                       "se quita la atribución del +2.6σ a F101: el verificador no lo reproduce "
                       "(parece una fluctuación)", VB + " (state.json F290-D4) + r02-pi.md")]),
        "F290-D5": ("El centrado entero de ebp_experimental deja argmin = pos_nm en los 4 haces "
                    "(PSF 20260703).", []),
        "F290-D6": ("zero_ratio usa min/max del mapa 2D mientras el docstring dice 'del perfil' "
                    "(ebp.py:545 contra :578); es solo una inconsistencia del docstring, y el valor del "
                    "mapa es la mejor estimación.", []),
        "F290-D7": ("La comparación honesta/ingenua es justa: una semilla antes de todos los casos y "
                    "el mismo r0, SBR y R_SEARCH_NM (simulation_misalignment.py:250-256).", []),
        "F290-D8": ("El CRB con N = Ns + Nb es consistente con el MC de N fijo: max|p_crb − p_MC| en "
                    "r0 = 4e-4 y un Fisher independiente da 0.864 nm, igual que el legado.", []),
    }
    for did in sorted(ev):
        x = db[did]
        text, corr = ev[did]
        add(did, x["suspicion"], None, text, x["script"], did, VB, corrections=corr)
    return out


# ---------------------------------------------------------------------------------------------
# Afirmaciones de la matriz de mezcla
# ---------------------------------------------------------------------------------------------

def build_mixing_claims(state):
    out = []
    for c in state["claims"]:
        t = c["text"]
        if not t.startswith("MIX-"):
            continue
        cid = t.split(":", 1)[0].strip()
        e = {"id": cid, "status": c["status"], "round": c["round"], "source": VA, "text": t}
        if cid == "MIX-NDETECT":
            e["status"] = "verified-corrected"
            e["text_original"] = t
            e["text"] = ("MIX-NDETECT (corregida): entre 1e-3 y 5e-3 fotones/ciclo el sesgo de sim_exp "
                         "respecto de la mezcla ideal se puede detectar en conjunto; a 5e-3 bastan ~1e7 "
                         "fotones (el verificador A lo detectó con 1.2e7: mezcla p = 4.6e-4, 'highest' "
                         "p = 0.76). El número necesario escala ~1/tasa², así que el 3e7 corresponde a "
                         "3e-3 (y ~2.5e8 a 1e-3 por la misma escala; W1 dio 2.6e8, sin re-correr). Por "
                         "localización de 2000 fotones sigue siendo ≤0.05 SE (MIX-TRACKING).")
            e["corrections_applied"] = [C("'de 1e-3 a 5e-3 hacen falta 3e7–2.6e8 fotones'",
                                          "a 5e-3 bastan ~1e7 y el 3e7 corresponde a 3e-3",
                                          VA + " (state.json MIX-NDETECT, refuted) + r02-pi.md")]
        out.append(e)
    return out


# ---------------------------------------------------------------------------------------------
# Auditoría numérica
# ---------------------------------------------------------------------------------------------

NUM = re.compile(r"(?<![\w.])[−-]?\d+(?:\.\d+)?(?:e[−-]?\d+)?")


def _nums(s):
    return {m.group(0).replace("−", "-").lstrip("-") for m in NUM.finditer(s)}


def audit(findings, state):
    """Números de title+impact que no aparecen en el texto de state.json del hallazgo (ni en MIX-*)."""
    mix = " ".join(c["text"] for c in state["claims"] if c["text"].startswith("MIX-"))
    rep = {}
    for e in findings:
        ref = e["verified_by"] + " " + mix + " " + " ".join(
            c["text"] for c in state["claims"] if c["text"].startswith(e["id"]))
        refn = _nums(ref)
        miss = sorted(n for n in _nums(e["title"] + " " + e["impact"]) if n not in refn)
        rep[e["id"]] = miss
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; solo audita")
    args = ap.parse_args(argv)

    state = _load(os.path.join(JOB, "state.json"))
    A = _load(os.path.join(RES, "findings_A.json"))
    B = _load(os.path.join(RES, "findings_B.json"))
    drafts = {x["id"]: x for x in A["findings"] + B["findings"]}

    findings = build_findings(state, drafts)
    discarded = build_discarded(state, A, B)
    mixing = build_mixing_claims(state)

    for e in findings:
        assert os.path.exists(os.path.join(ROOT, e["script"].split("::")[0])), e["script"]

    if not args.check:
        _dump(findings, "findings.json")
        _dump(discarded, "findings_discarded.json")
        _dump(mixing, "mixing_claims.json")

    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8")
    print("findings.json: %d entradas; findings_discarded.json: %d; mixing_claims.json: %d"
          % (len(findings), len(discarded), len(mixing)))
    print("clases:", {k: [e["id"] for e in findings if e["class"] == k]
                      for k in ("CONCEPTUAL", "IMPLEMENTACION", "DISENO")})
    print("autoría:", {k: [e["id"] for e in findings if e["author"] == k]
                       for k in ("Masullo-original", "autora", "no verificable")})
    print("auditoría (números de title+impact ausentes del texto verificado de state.json):")
    for fid, miss in audit(findings, state).items():
        print("  %s: %s" % (fid, ", ".join(miss) if miss else "-"))


if __name__ == "__main__":
    main()
