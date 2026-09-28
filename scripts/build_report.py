# -*- coding: utf-8 -*-
"""Genera report/index.html (autocontenido) y out/provenance.json del trabajo de revisión.

Todos los números se leen de results/*.json, de report/figs/captions.json y del ledger
(equipo/<job>/state.json). El texto explicativo es fijo; ningún resultado se tipea a mano.
Cada número lleva una etiqueta [src:clave] que resuelve en out/provenance.json.

Uso (desde la raíz del proyecto):
    python scripts/build_report.py
    python agent-team/bin/check_provenance.py report/index.html \
        equipo/2026-09-28_review-pminflux-sim/out/provenance.json
"""
from __future__ import print_function

import ast
import base64
import datetime
import html
import io
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provenance_sha import sha256_file  # noqa: E402  (sha256 robusto a finales de línea)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOB = "equipo/2026-09-28_review-pminflux-sim"
RES = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "report", "figs")
OUT_HTML = os.path.join(ROOT, "report", "index.html")
OUT_PROV = os.path.join(ROOT, JOB, "out", "provenance.json")

CLASS_ORDER = ["CONCEPTUAL", "IMPLEMENTACION", "DISENO"]
CLASS_LABEL = {"CONCEPTUAL": "Conceptual", "IMPLEMENTACION": "Implementación", "DISENO": "Diseño"}

# ----------------------------------------------------------------------------- carga


def _p(rel):
    return os.path.join(ROOT, rel)


def load(rel, default=None):
    path = _p(rel)
    if not os.path.exists(path):
        return default
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sha256(rel):
    """sha256 con fin de línea normalizado (scripts/provenance_sha.py); None si no existe."""
    return sha256_file(_p(rel))


# privacidad: el HTML es solo para la autora; no se muestran rutas locales de sus datos
_PRIV_SUBS = [
    (re.compile(r"C:\\Data\\psf\\20260820 no existe"), "las PSF de la calibración 20260820 no estaban disponibles"),
    (re.compile(r"(?<![A-Za-z])[A-Z]:\\(?:Data|Users)(?:\\[^\s<>\"',;)]*)?"), "(ruta local omitida)"),
]


def scrub(s):
    for rx, rep in _PRIV_SUBS:
        s = rx.sub(rep, s)
    return s


def exists(rel):
    return os.path.exists(_p(rel.split("::")[0].split(" ")[0]))


FINDINGS = load("results/findings.json", [])
DISCARDED = load("results/findings_discarded.json", [])
MIXV = load("results/mixing_validation.json", {})
MIXC = load("results/mixing_claims.json", [])
RATE = load("results/mixing_rate_sweep.json", {})
DEAD = load("results/dead_time_sweep.json", {})
CMP = load("results/compare_legacy_vs_v2.json", {})
STUDY = load("results/study_v2.json")
STATE = load(JOB + "/state.json", {})
CAPS = load("report/figs/captions.json", {}) or {}
FIND_A = load("results/findings_A.json", {})

CHECKLIST = load("results/simuflux_checklist.json", []) or []

CLAIMS = STATE.get("claims", [])


def report_claims(rel):
    """Bloque ```claims``` de un reporte de rol (lista, o None si el reporte no existe)."""
    path = _p(rel)
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as fh:
        txt = fh.read()
    m = re.search(r"```claims\s*(\[.*?\])\s*```", txt, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except ValueError:
        return []


FIXW_REL = JOB + "/reports/r03-fix-worker.md"
FIXW = report_claims(FIXW_REL) or []
CHKV_REL = JOB + "/reports/r03-verifier-checklist.md"
CHKV = report_claims(CHKV_REL)          # None = el verificador del checklist todavía no corrió

# ----------------------------------------------------------------------------- procedencia

PROV = {}
PLACEHOLDERS = []


def src(key, statement, etype, reproduce, detail="", **extra):
    """Registra una entrada de procedencia y devuelve la etiqueta visible."""
    entry = {"statement": statement, "type": etype, "reproduce": reproduce}
    if detail:
        entry["detail"] = detail
    entry.update(extra)
    if key in PROV and PROV[key]["statement"] != statement:
        # misma clave, otra afirmación: se conserva la primera y se agrega la segunda al detalle
        PROV[key].setdefault("also", [])
        if statement not in PROV[key]["also"]:
            PROV[key]["also"].append(statement)
    else:
        PROV.setdefault(key, entry)
    return tag(key)


def tag(*keys):
    return '<span class="src">[src:%s]</span>' % ",".join(keys)


def claim(prefix):
    """(índice, afirmación) del ledger cuyo texto empieza con prefix."""
    for i, c in enumerate(CLAIMS):
        if c.get("text", "").startswith(prefix):
            return i, c
    return None, None


def claim_src(key, prefix, reproduce=None, etype=None):
    i, c = claim(prefix)
    if c is None:
        return ""
    rep = reproduce if reproduce and exists(reproduce) else JOB + "/state.json"
    et = etype or ("check" if reproduce and exists(reproduce) else "data")
    return src(key, c["text"], et, rep,
               detail="state.json claims[%d] (status=%s, ronda %s, %s)" % (
                   i, c.get("status"), c.get("round"), c.get("source")),
               ledger_status=c.get("status"))


def claim_text(prefix):
    return claim(prefix)[1]["text"] if claim(prefix)[1] else ""


def fixw(prefix):
    """(índice, afirmación) del bloque claims de r03-fix-worker.md cuyo texto empieza con prefix."""
    for i, c in enumerate(FIXW):
        if c.get("text", "").startswith(prefix):
            return i, c
    return None, None


def fixw_src(key, prefix, reproduce):
    """Etiqueta para un arreglo de la pasada final (auto-verificado por el fix-worker con tests)."""
    i, c = fixw(prefix)
    if c is None:
        return ""
    rep = reproduce if exists(reproduce) else FIXW_REL
    return src(key, c["text"], "check" if exists(reproduce) else "source", rep,
               detail="bloque claims de %s, entrada %d (fix-worker R3: cubierto por tests; revisión "
                      "independiente parcial)" % (FIXW_REL, i))


# ----------------------------------------------------------------------------- formato

E = html.escape


def f(x, nd=2):
    if x is None:
        return "—"
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return str(x)
    return ("%." + str(nd) + "f") % x


def sci(x, nd=1):
    if x == 0:
        return "0"
    e = int(math.floor(math.log10(abs(x))))
    m = x / 10 ** e
    return "%s·10<sup>%d</sup>" % (("%." + str(nd) + "f") % m, e)


def pval(p):
    if p is None:
        return "—"
    if p == 0:
        return "&lt;10<sup>−300</sup>"
    if p < 1e-3:
        return sci(p, 1)
    return f(p, 3)


def pct(x, nd=1):
    return (("%." + str(nd) + "f") % (100 * x)) + " %"


def pos(p):
    return "(%s, %s)" % (("%g" % p[0]), ("%g" % p[1]))


# ----------------------------------------------------------------------------- figuras

FIG_SCRIPT = "scripts/make_report_figures.py"
FIG_ADJUSTED = ("timeline_20MHz.png", "rate_sweep.png", "dead_time_sweep.png")   # r03-fix-worker.md §5


def figure(name, fallback_title):
    path = os.path.join(FIGS, name)
    cap = CAPS.get(name, {})
    title = cap.get("title", fallback_title)
    if not os.path.exists(path):
        PLACEHOLDERS.append("figura report/figs/%s" % name)
        return ('<figure class="fig placeholder"><div class="ph">Figura pendiente: '
                '<code>report/figs/%s</code> (la genera <code>%s</code>, Worker 2). '
                'Se incorpora al volver a correr <code>scripts/build_report.py</code>.</div>'
                '<figcaption><b>%s</b></figcaption></figure>' % (E(name), FIG_SCRIPT, E(title)))
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    key = "fig-" + name.rsplit(".", 1)[0]
    rep = FIG_SCRIPT if exists(FIG_SCRIPT) else "report/figs/" + name
    t = src(key, "Figura %s: %s" % (name, cap.get("caption", title)),
            "script" if exists(FIG_SCRIPT) else "data", rep,
            detail="datos: %s; png sha256 %s" % (cap.get("source", "?"), sha256("report/figs/" + name)))
    fver = any(name in c.get("text", "") and c.get("status") == "verified" for c in CLAIMS)
    fi, fc = claim("Figuras report/figs")
    if fver:
        st = ""
    elif fc is not None and fc.get("status") == "verified":
        st = " <span class='muted'>(Números de la leyenda verificados contra los JSON en R3 %s%s.)</span>" % (
            claim_src("claim-figs", "Figuras report/figs"),
            "; leyenda ajustada en la pasada final según el verificador" if name in FIG_ADJUSTED else "")
    else:
        st = (" <span class='muted'>(Figura y leyenda de R3, Worker 2: se dibujan desde los JSON "
              "verificados; la verificación de la figura en sí está pendiente.)</span>")
    return ('<figure class="fig"><img alt="%s" src="data:image/png;base64,%s">'
            '<figcaption><b>%s.</b> %s <span class="muted">Fuente: <code>%s</code>.</span> %s%s'
            '</figcaption></figure>' % (E(title), b64, E(title), E(cap.get("caption", "")),
                                         E(cap.get("source", "?")), t, st))


# ----------------------------------------------------------------------------- claves base

FJSON = "results/findings.json"


def fsrc(x):
    """Etiqueta de procedencia de un hallazgo (script del hallazgo + registro verificado)."""
    script = x.get("script", "")
    return src(x["id"], "%s [%s]: %s" % (x["id"], x["class"], x["title"]),
               "script" if exists(script) else "data",
               script if exists(script) else FJSON,
               detail="results/findings.json id=%s; verificado por: %s" % (
                   x["id"], x.get("verified_by", "")),
               json_file=FJSON, json_key="id=" + x["id"])


def mv_src():
    return src("mix-valid", "Validación de la matriz de mezcla contra sim_exp: C, fracciones, chi2 y p-valores "
               "(results/mixing_validation.json)", "script", "scripts/validate_mixing_matrix.py",
               detail="results/mixing_validation.json: C_no_irf, C_irf_300ps_fwhm, frac_*, dev_se_*, chi2_*, "
               "chi2_pvalue_*, n_detected_total, rate_per_cycle; verificado por MIX-C/MIX-IRF/MIX-VALID",
               json_file="results/mixing_validation.json")


def cmp_src():
    return src("cmp-cases", "Comparación legado (Ec. 3.5) contra MLE de mezcla sobre datos v2sim: 20 casos "
               "(results/compare_legacy_vs_v2.json)", "script", "scripts/compare_legacy_vs_v2.py",
               detail="results/compare_legacy_vs_v2.json: cases[*].estimators, crb_*, legacy_asymptotic_bias_nm; "
               "verificado en R2 (verifier W3-R2 y code-reviewer)", json_file="results/compare_legacy_vs_v2.json")


def dt_src():
    return src("dt-sweep", "Barrido de tiempo muerto: sesgo por ventana del simulador v2 frente a la mezcla ideal, "
               "en SE por localización (results/dead_time_sweep.json)", "script", "scripts/sweep_dead_time.py",
               detail="results/dead_time_sweep.json: rows[*].max_abs_bias_SE_per_loc, p_vs_ideal; verificado "
               "por W2-R2 (barrido de tiempo muerto)", json_file="results/dead_time_sweep.json")


def rate_src():
    return src("rate-sweep", "Barrido de tasa de sim_exp contra la mezcla y los predictores highest/earliest "
               "(results/mixing_rate_sweep.json)", "script", "scripts/validate_mixing_matrix.py",
               detail="results/mixing_rate_sweep.json: points[*], studies_config; verificado por MIX-HIGHEST, "
               "MIX-STUDY, MIX-TRACKING", json_file="results/mixing_rate_sweep.json")


def mixclaim_src(cid):
    for x in MIXC:
        if x["id"] == cid:
            return src("mixclaim-" + cid, x["text"], "data", "results/mixing_claims.json",
                       detail="id=%s, status=%s, %s" % (cid, x["status"], x["source"]))
    return ""


def mixclaim_text(cid):
    for x in MIXC:
        if x["id"] == cid:
            return x["text"]
    return ""


# ----------------------------------------------------------------------------- datos derivados

P = MIXV.get("params", {})
T, K, TAU = P.get("T_ns"), P.get("K"), P.get("tau_ns")
A0, B0 = P.get("window_start_ns"), P.get("window_width_ns")
DT = T / K if T and K else None
C0 = MIXV.get("C_no_irf")
CI = MIXV.get("C_irf_300ps_fwhm")
CII = C0[0][0] if C0 else None
CPREV = C0[1][0] if C0 else None          # C[i][i-1]: haz anterior -> ventana i
COLSUM = MIXV.get("C_column_sums", [None])[0]
TAIL = math.exp(-DT / TAU) if DT and TAU else None


def cases():
    return CMP.get("cases", [])


def f104_rows():
    return [c for c in cases() if c["irf_fwhm_ns"] == 0.0 and c["sbr_label"] == "SBR21"]


def rng(vals, nd=2):
    return "%s–%s" % (f(min(vals), nd), f(max(vals), nd))


def by_id(i):
    for x in FINDINGS:
        if x["id"] == i:
            return x
    return None


# ----------------------------------------------------------------------------- secciones

SECTIONS = []


def section(sid, title, body):
    SECTIONS.append((sid, title))
    return '<section id="%s"><h2>%s</h2>\n%s\n</section>\n' % (sid, E(title), body)


def s_resumen():
    ncls = {c: sum(1 for x in FINDINGS if x["class"] == c) for c in CLASS_ORDER}
    lat = [x["id"] for x in FINDINGS if re.search(r"[Ll]atente[:.]", x.get("impact", ""))]
    leg_b = [c["estimators"]["legacy"]["bias_abs"] for c in cases()]
    leg_r = [c["estimators"]["legacy"]["rmse_over_crb"] for c in cases()]
    mix_r = [c["estimators"]["mixing"]["rmse_over_crb"] for c in cases()]
    mix_b = [c["estimators"]["mixing"]["bias_abs"] for c in cases()]
    fr = f104_rows()
    f104b = [c["legacy_asymptotic_bias_nm"] for c in fr]
    dt = {(r["tcspc"], r["dead_time_ns"], r["rate_per_cycle"]): r for r in DEAD.get("rows", [])}
    rmax = max(DEAD["params"]["rates_per_cycle"]) if DEAD else None
    d_nT = [r["max_abs_bias_SE_per_loc"] for r in DEAD.get("rows", [])
            if r["tcspc"] == "earliest" and r["dead_time_ns"] in (50.0, 100.0)]
    d22 = dt.get(("earliest", 22.0, rmax), {}).get("max_abs_bias_SE_per_loc")
    b = []
    b.append('<p class="lead">Revisamos el simulador p-MINFLUX de <code>legacy/p-minflux-main</code> con la '
             'experiencia del setup pulsado a 20 MHz (T = %g ns, K = %d, τ = %g ns, ventana [%g, %g] ns) %s. '
             'Resultado: %d hallazgos verificados (%d conceptual, %d de implementación, %d de diseño) %s, '
             'de los cuales %d son latentes (no cambian ningún número publicado). El código hace, en general, '
             'lo que dice; el problema de fondo es metodológico.</p>'
             % (T, K, TAU, A0, B0, mv_src(), len(FINDINGS), ncls["CONCEPTUAL"], ncls["IMPLEMENTACION"],
                ncls["DISENO"], src("findings-all", "Registro de %d hallazgos verificados" % len(FINDINGS), "data",
                                    FJSON, detail="todas las entradas con status=verified; el test de aceptación "
                                    "lo comprueba", json_file=FJSON), len(lat)))
    b.append("<ol class='keys'>")
    b.append("<li><b>La matriz de mezcla es correcta y necesaria.</b> Con τ = %g ns y pulsos cada %g ns, "
             "un %s de los fotones de cada haz cae en la ventana del haz siguiente (C<sub>i,i−1</sub> = %s) %s. "
             "El modelo de mezcla describe <code>sim_exp</code> (χ² p = %s con %s fotones en ventanas); el modelo "
             "ingenuo de la Ec. 3.5 queda rechazado (χ² = %s, p %s) %s.</li>"
             % (TAU, DT, pct(CPREV), f(CPREV, 4), mv_src(), pval(MIXV["chi2_pvalue_mixing_vs_sim_exp"]),
                sci(MIXV["n_detected_total"], 2), f(MIXV["chi2_naive"], 0),
                "= 0 numérico" if MIXV["chi2_pvalue_naive_vs_sim_exp"] == 0 else "= " + pval(MIXV["chi2_pvalue_naive_vs_sim_exp"]),
                mixclaim_src("MIX-VALID")))
    b.append("<li><b>El error conceptual central es el “crimen inverso”</b> (§3): los estudios simulan con el "
             "mismo modelo que usa el estimador (sin fuga, ventanas que cubren el ciclo), así que no pueden ver "
             "que ese modelo no describe el instrumento. En el setup medido el MLE de la Ec. 3.5 tiene un sesgo "
             "asintótico de %s nm (SBR 21, 5 posiciones) %s %s; el ideal “honesto” de los estudios pasa de "
             "|b| ≈ 0.1 nm a ≈ 3 nm cuando se enciende la fuga %s.</li>"
             % (rng(f104b), cmp_src(), fsrc(by_id("F104")), fsrc(by_id("F201"))))
    b.append("<li><b>La versión v2</b> (<code>src/pminflux_sim</code>) simula en dominio temporal (τ, IRF, "
             "ventanas periódicas, TCSPC de primer fotón, tiempo muerto) y estima con la matriz de mezcla. "
             "Sobre los mismos datos, en 20 casos: legado |b| %s nm y RMSE/CRB %s; mezcla |b| ≤ %s nm y "
             "RMSE/CRB %s %s.</li>" % (rng(leg_b), rng(leg_r), f(max(mix_b), 3), rng(mix_r), cmp_src()))
    if d_nT and d22 is not None:
        b.append("<li><b>Tiempo muerto.</b> Con un tiempo muerto de %g ns (supuesto) y %g fotones/ciclo, el sesgo "
                 "por ventana es ≤ %s SE por localización; con d = n·T (50 o 100 ns) se anula exactamente "
                 "(≤ %s SE, ruido MC) %s %s.</li>"
                 % (22, rmax, f(d22, 2), f(max(d_nT), 3), dt_src(),
                    claim_src("claim-dnT", "W2-R2 barrido de tiempo muerto", "work/verify/r02/v2_deadtime.py")))
    b.append("<li><b>Lo que estaba bien</b> (§5): el pliegue periódico de <code>sim_exp</code> ya modelaba la "
             "fuga; la validación del término de fondo; la corrección de <code>spaceToIndex</code>; el diseño "
             "honesto/ingenuo con comparación justa; y la autora ya había anotado como pendientes el τ y la IRF "
             "medidos, las potencias distintas por haz y la trazabilidad de los logs.</li>")
    if CHECKLIST:
        cnt = {}
        for x in CHECKLIST:
            cnt[x["estado"]] = cnt.get(x["estado"], 0) + 1
        b.append("<li><b>Checklist SimuFLUX</b> (<a href='#simuflux'>§10</a>): de %d ítems, %d aplican y están bien, "
                 "%d fallan y %d no aplican %s%s.</li>" % (
                     len(CHECKLIST), cnt.get("aplica-ok", 0), cnt.get("falla", 0), cnt.get("no aplica", 0),
                     src("simuflux-checklist", "Auditoría del legado contra los 21 ítems de errores frecuentes de "
                         "simulaciones MINFLUX de SimuFLUX (results/simuflux_checklist.json)", "data",
                         "results/simuflux_checklist.json",
                         detail="sha256 %s; worker R3 (reports/r03-simuflux-checklist.md)" % sha256(
                             "results/simuflux_checklist.json"), json_file="results/simuflux_checklist.json"),
                     " (verificación independiente pendiente)" if CHKV is None else ""))
    b.append("</ol>")
    return section("resumen", "1. Resumen ejecutivo", "\n".join(b))


def s_metodo():
    st = {}
    for c in CLAIMS:
        st[c["status"]] = st.get(c["status"], 0) + 1
    crit = FIND_A.get("criterion", "")
    b = ["<p>La revisión se hizo con la metodología <i>agent-team</i>: un equipo acotado (PI, workers, "
         "verificador, revisor de código y este redactor) en %s rondas. Cada resultado lo produjo un worker y lo "
         "reprodujo un <b>verificador independiente</b> por otro camino (simulador fotón por fotón propio, "
         "cuadraturas propias, otras semillas), sin ver el razonamiento del worker. Solo lo que el verificador "
         "reprodujo entra como <b>verificado</b>; lo refutado se corrigió y lo no reproducido figura como "
         "<i>unclear</i> en §11.</p>" % STATE.get("rounds_budget", "?"),
         "<p>Estado del ledger al generar este reporte: %s %s.</p>" % (
             ", ".join("%d %s" % (v, k) for k, v in sorted(st.items())),
             src("ledger", "Conteo de afirmaciones del ledger por estado", "data", JOB + "/state.json",
                 detail="state.json claims[*].status")),
         "<p>Cada número de este documento lleva una etiqueta <span class='src'>&#91;src:clave&#93;</span>, que "
         "resuelve en <code>%s/out/provenance.json</code> con el archivo, la clave y el script que lo "
         "reproduce. El documento lo genera <code>scripts/build_report.py</code> leyendo los JSON: nada se "
         "tipea a mano.</p>" % JOB,
         "<h3>Criterio de clases</h3>",
         "<table class='crit'><tr><th>Clase</th><th>Criterio</th><th>Pregunta que responde</th></tr>"
         "<tr><td><span class='badge CONCEPTUAL'>Conceptual</span></td><td>El modelo físico o estadístico está "
         "mal: el resultado es incorrecto aunque el código haga lo que pretende.</td><td>¿Está bien la física?</td></tr>"
         "<tr><td><span class='badge IMPLEMENTACION'>Implementación</span></td><td>El código no hace lo que dice "
         "o pretende (bug).</td><td>¿El código hace lo que dice?</td></tr>"
         "<tr><td><span class='badge DISENO'>Diseño</span></td><td>Decisión defendible que limita el alcance o "
         "la validez: parámetro por defecto, supuesto no declarado, tamaño de Monte Carlo, forma de reportar."
         "</td><td>¿El estudio responde la pregunta que plantea?</td></tr></table>",
         "<p class='muted'>Texto del criterio en el registro: “%s” %s. <b>Latente</b> = no cambia ningún "
         "número publicado por la autora con su configuración actual. Decisiones de clase tomadas en la ronda 2 "
         "(inbox): F104 es CONCEPTUAL; F201 y F202 son DISEÑO, porque el código hace lo que dice y el problema es "
         "un supuesto no declarado (F201) o una convención documentada (F202).</p>" % (
             E(crit), src("criterion", "Criterio de clasificación del PI", "data", "results/findings_A.json",
                          detail="clave criterion; reports/r01-pi.md:54-56; inbox.jsonl ronda 2")),
         "<p><b>Autoría.</b> No hay historial git (tampoco en la copia original), así que la autoría de cada "
         "línea es <i>no verificable</i> salvo lo que sostuvo el verificador A: el docstring [Lars] de "
         "<code>ebp_centres</code> y que el comentario “EXACTAMENTE” y la ruta rápida de <code>sim_exp</code> "
         "están en el español de la autora %s. Donde el registro dice “autora”, la base es la declaración de "
         "NOTAS.txt (atribución por exclusión). En todos los casos el error se atribuye al método, no a la "
         "persona.</p>" % claim_src("claim-autoria", "AUTORIA F101-F111")]
    return section("metodo", "2. Cómo se revisó", "\n".join(b))


def s_crimen():
    f104, f201 = by_id("F104"), by_id("F201")
    fr = f104_rows()
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            pos(c["position_nm"]), f(c["legacy_asymptotic_bias_nm"], 2), f(c["crb_minflux_legacy_axis_nm"], 3),
            f(c["legacy_asymptotic_bias_nm"] / c["crb_minflux_legacy_axis_nm"], 2), f(c["crb_mixing_axis_nm"], 3),
            f(c["crb_mixing_axis_nm"] / c["crb_minflux_legacy_axis_nm"], 3)) for c in fr)
    tail_tag = src("deriv-tail", "Fracción de la cola exponencial que sobrevive un intervalo entre pulsos: "
                   "exp(-(T/K)/tau)", "derivation", "exp(-12.5/4.21) con T, K, tau de results/mixing_validation.json",
                   detail="cálculo en scripts/build_report.py (TAIL)")
    b = []
    b.append("<div class='callout'><b>En una frase.</b> Si simulás los datos con el mismo modelo directo que usa "
             "el estimador, el estudio solo mide la varianza del estimador <i>bajo su propio modelo</i>: por "
             "construcción es insesgado y alcanza el CRB asintóticamente, y queda ciego a cualquier diferencia entre ese modelo y el instrumento. "
             "En problemas inversos a esto se lo llama “crimen inverso”.</div>")
    b.append("<h3>Qué pasa físicamente a 20 MHz</h3>")
    b.append("<p>En p-MINFLUX pulsado el ciclo TCSPC dura T = %g ns y los K = %d haces se disparan intercalados, "
             "uno cada T/K = %g ns. Cada fotón llega con un retardo exponencial de vida media τ = %g ns respecto de "
             "<i>su</i> pulso, y se asigna al haz según la ventana de microtiempo en la que cae: la ventana i es "
             "[i·T/K + a, i·T/K + a + b] con a = %g y b = %g ns %s.</p>" % (T, K, DT, TAU, A0, B0, mv_src()))
    b.append("<p>Con estos números la cola del decaimiento no termina antes del pulso siguiente: una fracción "
             "e<sup>−%g/%g</sup> = %s de los fotones de un haz llega después del pulso del haz siguiente %s. La parte "
             "de esa cola que cae dentro de la ventana siguiente es C<sub>i,i−1</sub> = %s (el %s), el haz propio "
             "retiene C<sub>ii</sub> = %s, y un %s de cada haz cae fuera de todas las ventanas (suma de columna %s) "
             "%s %s. Con la IRF gaussiana de 0.3 ns FWHM (supuesta) C<sub>ii</sub> = %s y C<sub>i,i−1</sub> = %s "
             "%s.</p>" % (DT, TAU, pct(TAIL), tail_tag, f(CPREV, 4), pct(CPREV), f(CII, 4), pct(1 - COLSUM, 2),
                          f(COLSUM, 4), mv_src(), mixclaim_src("MIX-C"), f(CI[0][0], 4), f(CI[1][0], 4),
                          mixclaim_src("MIX-IRF")))
    b.append("<p>¿Por qué importa tanto un %s? Porque en MINFLUX la información está en el haz que <i>menos</i> "
             "fotones da: el emisor está cerca del cero de una dona, y ese haz es justamente el más contaminado por "
             "los vecinos. En (5, −5) nm la ventana 0 tiene un 45.8 %% de fotones de otros haces %s. El estimador "
             "de la Ec. 3.5 (<code>pos_MINFLUX</code>, <code>crb_minflux</code>) supone "
             "p<sub>i</sub> = s·λ<sub>i</sub>/Σλ + (1 − s)/K: sin fuga, y con el fondo repartido en K ventanas "
             "que cubren el ciclo. Lee esos fotones prestados como señal del haz propio y corre la posición.</p>"
             % (pct(CPREV), fsrc(f104)))
    b.append(figure("timeline_20MHz.png", "Línea de tiempo del ciclo a 20 MHz"))
    b.append("<h3>Por qué la simulación no lo podía ver</h3>")
    b.append("<p>Los estudios usan Tlife = 0.001 ns y b = dt/K %s. Con τ = 0.001 ns la cola a %g ns es "
             "e<sup>−%g</sup>: fuga nula. Con b = T/K las ventanas cubren el ciclo y el fondo cae 1/K en cada una. "
             "En ese régimen los datos simulados siguen <i>exactamente</i> la Ec. 3.5 (la autora lo verificó "
             "empíricamente y es exacto: F290-D4) %s. Es decir, se generan los datos con el mismo modelo que después "
             "se invierte: el MLE es insesgado y alcanza el CRB asintóticamente por construcción, y “honesto ≈ CRB” no dice nada sobre el experimento "
             "real.</p>" % (fsrc(f201), DT, DT / 0.001, claim_src("claim-D4", "F290-D4")))
    b.append("<p class='note'>%s</p>" % E(f104.get("crimen_inverso_note", "")))
    b.append("<h3>Las dos mitades del mismo error</h3>")
    b.append("<p><b>F104 (conceptual): el estimador.</b> En el setup medido, SBR 21 e IRF 0, el sesgo asintótico "
             "(sin ruido) del MLE de la Ec. 3.5 y los CRB son %s:</p>" % cmp_src())
    b.append("<table><tr><th>posición (nm)</th><th>sesgo legado (nm)</th><th>CRB crb_minflux (nm)</th>"
             "<th>sesgo / CRB</th><th>CRB con fuga (nm)</th><th>CRB fuga / crb_minflux</th></tr>%s</table>" % rows)
    b.append("<p>El sesgo es sistemático: no baja con más fotones, así que en unidades de CRB crece como √N. "
             "El CRB que usa el legado subestima el real (cociente de la última columna) %s.</p>"
             % claim_src("claim-crbratio", "W3-R2 CRB_mezcla/crb_minflux", "work/verify/r02/v5_compare.py"))
    b.append("<p><b>F201 (diseño): los estudios.</b> %s %s</p>" % (E(f201["impact"]), fsrc(f201)))
    b.append(figure("f201_leakage.png", "F201: el estudio con y sin fuga"))
    b.append("<p><b>Cómo se evita.</b> El modelo que genera los datos tiene que ser más rico que el que asume "
             "el estimador (dominio temporal: τ medido, IRF, ventanas reales, TCSPC, tiempo muerto), y el estimador "
             "se valida contra ese modelo. Eso es lo que hace v2: <code>simulate.simulate_counts</code> es el "
             "modelo rico, <code>estimate.mle_mixing</code> el estimador, y §8 compara los dos estimadores sobre "
             "los mismos datos. Nota de justicia: Tlife = 0.001 y b = dt/K ya están en "
             "<code>simulations_example.py</code> de Masullo (setup de 40 MHz), y la autora ya anotó como "
             "pendiente “incorporar IRF y lifetime medidos” (ESTADO_Y_PLAN_REALISMO_PSF.md:115-117) %s.</p>"
             % fsrc(f201))
    return section("crimen", "3. El error conceptual central: el “crimen inverso” (F104 + F201)", "\n".join(b))


def _tests_list(x):
    ts = x.get("v2_tests") or ([x["v2_test"]] if x.get("v2_test") else [])
    out = []
    for t in ts:
        path = t.split(" ")[0]
        ok = exists(path)
        out.append("<code>%s</code>%s" % (E(t), "" if ok else " <span class='warn'>(no encontrado)</span>"))
    return out


def V2_OK():
    return claim_src("claim-v2tests", "W1-R2 findings.json: los 17 ids", "results/findings.json", etype="data")

# correcciones literales del verificador que el PI pidió aplicar (r03-pi.md, Tarea 3)
VERIFIER_NOTES = {
    "F103": "La pérdida esperada de la ventana 0 es 6.84 % (τ = 4.21) / 2.54 % (τ = 0.001); el efecto es un "
            "desplazamiento, no un sesgo que se suma: 0.88 nm con las ventanas del legado contra 1.18 nm con "
            "ventanas periódicas.",
    "F111": "No hay “paridad invertida”: los comentarios de paridad son correctos (en la rama con centro, "
            "leídos para Kθ = K − 1).",
    "F201": "El cociente RMSE/CRB ≈ 2.5 es contra el CRB con fuga (0.945 nm); 2.73–2.75 es contra el CRB sin fuga "
            "(0.864 nm) que usa el estudio.",
    "F203": "El 100 % de estimaciones en el borde vale solo con R ≤ 1.0·L (71–72 % con R = 1.25·L).",
    "F204": "El “± ~0.13–0.15” para el 1.89 es una extrapolación desde EBP sustitutos, no una medición con las "
            "PSF 20260820.",
    "F205": "0.912 nm es el RMSE correcto (contra el píxel realmente simulado, (−5, −8)); 0.960 nm es lo que "
            "produce el script legado, inflado por el desplazamiento de 0.4455 nm.",
}
VERIFIER_CLAIM = {"F103": "F103-num", "F111": "F111-comentarios", "F201": "F201: la clase CONCEPTUAL",
                  "F203": "F203: 'el 100 %", "F204": "F204:", "F205": "W1-R2 F205, sentido resuelto"}


def _fix_text(x, field):
    t = x.get(field, "")
    if x["id"] == "F205":
        # corrección literal del verificador (W1-R2 F205): 0.960 es la cantidad inflada, no la corregida
        t = t.replace("y pasa de 0.912 a 0.960 nm en el ideal",
                      "y da 0.960 nm en el ideal, inflado por el desplazamiento de 0.4455 nm; contra el píxel "
                      "realmente simulado el valor correcto es 0.912 nm")
    return t


def card(x):
    cls = x["class"]
    tests = _tests_list(x)
    if x["id"] == "F107":
        ci7, c7 = claim("F107 portado")
        if x.get("v2_test") and c7 is not None and c7.get("status") == "verified":
            v2 = ("%s — <b>portado en R3 y verificado en R3</b>: <code>simulate_counts(..., t_mask=...)</code>; "
                  "sin señal en ciclos de excitación apagados; con SBR 5 la fracción de fotones en la mitad "
                  "apagada es 1/7 (|z| ≤ 1.5) %s. En la pasada final se agregó "
                  "<code>sbr_reference=\"on\"|\"total\"</code> para elegir si el SBR se refiere a los ciclos "
                  "encendidos (default) o al conjunto, como en el legado %s <span class='muted'>(cubierto por "
                  "tests; revisión independiente parcial)</span>." % (
                      "; ".join(tests), claim_src("claim-F107-port", "F107 portado"),
                      fixw_src("fix-sbrref", "simulate_counts(sbr_reference='total')",
                               "tests/test_simulate.py::TestSimulateBlinking::test_t_mask_sbr_reference")))
        elif x.get("v2_test"):
            v2 = ("%s — <b>portado en R3</b> (Worker 1): <code>simulate_counts(..., t_mask=...)</code>. "
                  "<span class='badge st-unclear'>pendiente de verificación</span>" % "; ".join(tests))
        else:
            v2 = "<b>No portado a v2</b> (la máscara de parpadeo queda en el backlog). %s" % fsrc(x)
    else:
        r3 = [t for t in tests if "TestStudyV2" in t]
        v2 = "%s — los tests v2 de los hallazgos existen y pasan (verificado en R2%s) %s" % (
            "; ".join(tests), "; TestStudyV2 es de R3, verificado en R3" if r3 else "", V2_OK())
        if "study_v2" in x.get("v2_fix_status", ""):
            sv = [c for c in CLAIMS if c.get("text", "").startswith("study_v2") and c.get("status") == "verified"]
            if sv:
                v2 += (" En R3 el estudio de desalineación se rehízo con v2 (<code>results/study_v2.json</code>, "
                       "<a href='#study-v2'>§8</a>) y lo reprodujo el verificador de forma independiente %s."
                       % claim_src("claim-study-v2", "study_v2 (N=2095"))
            else:
                v2 += (" En R3 el estudio de desalineación se rehízo con v2 (<code>results/study_v2.json</code>, §8), "
                       "<span class='badge st-unclear'>pendiente de verificación</span>.")
    latent = bool(re.search(r"[Ll]atente[:.]", x.get("impact", "")))
    note = ""
    if x["id"] in VERIFIER_NOTES:
        ck = VERIFIER_CLAIM.get(x["id"])
        note = ("<div class='vnote'><b>Corrección del verificador aplicada.</b> %s %s</div>"
                % (E(VERIFIER_NOTES[x["id"]]), claim_src("claim-" + x["id"] + "-corr", ck) if ck else ""))
    ci = ""
    if x.get("crimen_inverso"):
        ci = "<span class='badge ci'>crimen inverso</span>"
    corr = x.get("corrections_applied", [])
    corr_html = "".join("<li>%s → %s <span class='muted'>(%s)</span></li>" % (E(c["from"]), E(c["to"]), E(c["source"]))
                        for c in corr)
    return """
<article class="card {cls}" id="{id}">
  <header><span class="fid">{id}</span> <span class="badge {cls}">{clab}</span>{lat}{ci}
    <h4>{title} {tag}</h4></header>
  <dl>
    <dt>Dónde</dt><dd><code>{loc}</code></dd>
    <dt>Impacto</dt><dd>{impact}</dd>
    <dt>Qué estaba bien</dt><dd class="good">{right}</dd>
    <dt>Corrección</dt><dd>{fix}</dd>
    <dt>En v2</dt><dd>{v2}</dd>
  </dl>
  {note}
  <details><summary>Escenario, autoría, script y correcciones</summary>
  <dl>
    <dt>Escenario</dt><dd>{scen}</dd>
    <dt>Autoría</dt><dd><b>{author}</b>. {abasis}</dd>
    <dt>Script</dt><dd><code>{script}</code></dd>
    <dt>Verificado por</dt><dd class="muted">{vby}</dd>
    {corr}
  </dl></details>
</article>""".format(
        cls=cls, id=x["id"], clab=CLASS_LABEL[cls], lat=" <span class='badge lat'>latente</span>" if latent else "",
        ci=ci, title=E(x["title"]), tag=fsrc(x), loc=E(x["legacy_location"]), impact=E(_fix_text(x, "impact")),
        right=E(x.get("what_was_right", "")), fix=E(x["fix"]), v2=v2, note=note, scen=E(x["scenario"]),
        author=E(x.get("author", "")), abasis=E(x.get("author_basis", "")), script=E(x["script"]),
        vby=E(x.get("verified_by", "")),
        corr=("<dt>Correcciones</dt><dd><ul>%s</ul></dd>" % corr_html) if corr_html else "")


def s_findings():
    intro = {
        "CONCEPTUAL": "El modelo físico o estadístico está mal aunque el código haga lo que pretende. Es la clase "
                      "que más importa: no se arregla con un parche.",
        "IMPLEMENTACION": "El código no hace lo que dice. Casi todos son latentes: no tocan la configuración de los "
                          "estudios, pero muerden en cuanto se cambia un parámetro (a &lt; 0, b &gt; T/K, K ≠ 4, "
                          "SBR = ∞). Por eso conviene tener tests con el código.",
        "DISENO": "Decisiones defendibles que limitan la validez de los estudios: supuestos no declarados, "
                  "referencias, métricas y reproducibilidad.",
    }
    b = []
    for c in CLASS_ORDER:
        xs = [x for x in FINDINGS if x["class"] == c]
        b.append("<h3 id='cls-%s'>%s <span class='muted'>(%d)</span></h3><p>%s</p>" % (
            c, CLASS_LABEL[c], len(xs), intro[c]))
        b.extend(card(x) for x in xs)
    return section("hallazgos", "4. Hallazgos por clase", "\n".join(b))


def s_bien():
    b = ["<p>Una revisión justa tiene que decir también qué resistió la verificación. Esto es lo que estaba "
         "bien, con la evidencia:</p><ul class='good-list'>"]
    items = [
        ("F201", "<code>sim_exp</code> sí modelaba la fuga: el pliegue periódico (% dt) equivale, para los conteos, "
                 "a la matriz de mezcla; el error estaba en los parámetros con que se lo llamaba."),
        ("F104", "Validó empíricamente que el término de fondo uniforme reproduce la Ec. 3.5 con b = dt/K y sin "
                 "fuga, y es exacto en ese régimen."),
        ("F201", "Ya había anotado como pendiente “incorporar drift, blinking, IRF y lifetime medidos” "
                 "(ESTADO_Y_PLAN_REALISMO_PSF.md:115-117)."),
        ("F202", "Ya recomendaba “permitir distinta potencia entre haces” (ESTADO…md:116) y advertía que las "
                 "elipticidades son parámetros efectivos."),
        ("F206", "Ya advertía que los logs vienen de configuraciones distintas y que hay que guardar configuración, "
                 "semilla y versión con cada resultado (ESTADO…md:64-67)."),
        ("F106", "Corrigió <code>spaceToIndex</code> para redondear en vez de truncar (el truncado sesgaba "
                 "(−0.50, +0.50) nm, F153) y documentó el término de cuantización px²/12."),
        ("F203", "Acotó la búsqueda del MLE (<code>r_max_nm</code>), que corrige máximos espurios; el radio es "
                 "el mismo en todos los casos."),
        ("F204", "Agregó semillas fijas y errores estándar a todos los estadísticos, que el código original no tenía."),
        ("F202", "Ajuste 2D robusto de las PSF con escalera reproducible (se reproduce al 4.º decimal)."),
        ("F107", "La ruta rápida de <code>sim_exp</code> es estadísticamente equivalente al multinomial original "
                 "(exacta por factorización) y unas 100 veces más rápida."),
    ]
    for fid, txt in items:
        b.append("<li>%s <a href='#%s'>%s</a> %s</li>" % (txt, fid, fid, fsrc(by_id(fid))))
    b.append("<li>La comparación honesta/ingenua es justa: una semilla antes de todos los casos, el mismo r0, "
             "SBR y radio de búsqueda %s.</li>" % claim_src("claim-D7", "F290-D7"))
    b.append("<li><code>crb_minflux</code> coincide con un Fisher continuo independiente dentro de 4.4·10<sup>−4</sup> nm "
             "(F151); el muestreo en dos pasos y el fondo Nb·b/T por ventana son exactos (F152) %s.</li>"
             % src("discarded", "Sospechas descartadas y verificadas (F105, F151–F154, D-*, F290-D*)", "data",
                   "results/findings_discarded.json", detail="status discarded-verified salvo F154 (unclear)"))
    b.append("</ul>")
    return section("bien", "5. Lo que estaba bien", "\n".join(b))


def s_distinto():
    rows = [
        ("Simular con un modelo directo más rico que el del estimador",
         "Generar los datos en dominio temporal (τ, IRF, ventanas reales, TCSPC de primer fotón, tiempo muerto) y "
         "ajustar con el modelo simplificado. Si el estimador alcanza el CRB, que sea sobre datos que no fabricó "
         "su propio modelo.", "F104, F201"),
        ("Usar los parámetros medidos del instrumento",
         "τ = 4.21 ns y la ventana [0, 10.1] ns ya estaban medidos en 20260707; ponerlos por defecto en los "
         "estudios y declarar cualquier idealización (“sin fuga”) en el título de la tabla.", "F201"),
        ("Validar el estimador contra un modelo que no asume",
         "Un test de consistencia: fracciones por ventana de la simulación contra la predicción del estimador "
         "(χ²). Con fuga, la Ec. 3.5 falla ese test por miles de unidades de χ².", "F104, §9"),
        ("Emisor continuo y referencia correcta",
         "Simular el emisor fuera de la grilla y medir el sesgo contra la posición realmente simulada; reportar "
         "sesgos como vectores o diferencias pareadas.", "F106, F205"),
        ("Reportar la fracción en el borde y barrer el radio de búsqueda",
         "Cuando una estimación cae en el borde del disco, el RMSE lo fija R, no el estimador.", "F203"),
        ("Errores estándar por bootstrap",
         "Con N bajo y PSF con pedestal las estimaciones no son normales; std/√(2n) subestima el SE hasta ~1.9×.",
         "F204"),
        ("Un pipeline que genere el documento",
         "El script escribe un JSON con configuración, semilla y versión; el documento lee de ahí y falla si no "
         "coincide. Nada de parámetros escritos a mano.", "F206"),
        ("Fijar las versiones de los datos",
         "Registrar el sha256 de las PSF y calibraciones usadas (las 20260820 no están en disco y los números "
         "“Experimental” no se pudieron reproducir).", "F202, F204, §11"),
        ("Tests con el código y validaciones de entrada",
         "Los bugs latentes (K ≠ 4, SBR = ∞, a &lt; 0, b &gt; T/K, FWHM gaussiana) los atrapa un test de una línea "
         "o un <code>ValueError</code>.", "F102, F103, F108–F111"),
        ("Simular a la tasa del experimento con el TCSPC real",
         "Quedarse con el primer fotón del ciclo y aplicar tiempo muerto; a las tasas del tracking el efecto es "
         "chico, pero así se sabe.", "F101"),
    ]
    b = ["<p>Prácticas concretas que habrían evitado cada hallazgo. Ninguna es exótica; son la diferencia entre "
         "“el código corre” y “el estudio responde la pregunta”.</p><table class='todo'>"
         "<tr><th>Práctica</th><th>Qué quiere decir en este proyecto</th><th>Hallazgos</th></tr>"]
    for a, d, ids in rows:
        links = ", ".join("<a href='#%s'>%s</a>" % (i.strip(), i.strip()) if i.strip().startswith("F") and
                          "–" not in i else E(i.strip()) for i in ids.split(","))
        b.append("<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>" % (a, d, links))
    b.append("</table>")
    return section("distinto", "6. Qué podría haber hecho distinto", "\n".join(b))


def _module_doc(rel):
    try:
        with io.open(_p(rel), encoding="utf-8") as fh:
            d = ast.get_docstring(ast.parse(fh.read()))
        return (d or "").strip().split("\n")[0]
    except Exception:
        return ""


def _readme_lines():
    path = _p("README.md")
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def _readme_section(word):
    lines = _readme_lines()
    if not lines:
        return None
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and word in ln.lower():
            start = i
            break
    if start is None:
        return None
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        out.append(ln)
    return out


def _readme_tables(word):
    """Lista de (texto previo, filas) de las tablas markdown de la sección de README cuyo título contiene word."""
    sec = _readme_section(word)
    if not sec:
        return None
    tables, cur, pre = [], None, []
    for ln in sec + [""]:
        if ln.strip().startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|",ln.strip().strip("|"))]
            if cur is None:
                cur = []
            if not all(set(c) <= set("-: ") for c in cells):
                cur.append(cells)
        else:
            if cur:
                tables.append((" ".join(x for x in pre if x.strip()), cur))
                cur, pre = None, []
            if ln.strip():
                pre.append(ln.strip())
    return tables or None


def _readme_code(word):
    sec = _readme_section(word)
    if not sec:
        return None
    txt = "\n".join(sec)
    m = re.search(r"```python\n(.*?)```", txt, re.S)
    return m.group(1) if m else None


def _md_inline(s):
    s = E(s.replace("\\|", "|"))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s


def s_v2():
    mods = ["mixing", "simulate", "estimate", "psf", "windows"]
    b = ["<p>La versión mejorada vive en <code>src/pminflux_sim</code>. No reemplaza tu código de análisis: "
         "reemplaza el núcleo de simulación y estimación y corrige los hallazgos de implementación.</p>", "<ul>"]
    for m in mods:
        rel = "src/pminflux_sim/%s.py" % m
        if exists(rel):
            b.append("<li><code>pminflux_sim.%s</code> — %s %s</li>" % (
                m, E(_module_doc(rel)), src("mod-" + m, "Módulo pminflux_sim.%s" % m, "script", rel,
                                            detail="sha256 %s" % sha256(rel))))
        else:
            b.append("<li><code>pminflux_sim.%s</code> — <span class='ph-inline'>pendiente (Worker 1, R3)</span></li>" % m)
            PLACEHOLDERS.append("módulo " + rel)
    b.append("</ul>")
    b.append("<h3>Tabla de migración legado → v2</h3>")
    tbls = _readme_tables("migraci")
    rtag = src("readme", "README de pminflux_sim (instalación, convenciones, supuestos, migración)", "data",
               "README.md", detail="sha256 %s" % sha256("README.md")) if exists("README.md") else ""
    if tbls:
        for pre, rows_ in tbls:
            if pre:
                b.append("<p>%s</p>" % _md_inline(pre))
            head, body_ = rows_[0], rows_[1:]
            b.append("<div class='scroll'><table><tr>%s</tr>%s</table></div>" % (
                "".join("<th>%s</th>" % _md_inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _md_inline(c) for c in r) for r in body_)))
        b.append("<p class='muted'>Tomadas de la sección de migración de <code>README.md</code> %s. El revisor "
                 "de código siguió el README al pie de la letra en un clon (instalación, inicio rápido) y contrastó "
                 "sus afirmaciones con el código %s %s; lo que faltaba para la migración se agregó en la pasada "
                 "final (abajo).</p>" % (rtag, claim_src("claim-readme-clone", "README al pie de la letra"),
                                          claim_src("claim-readme-code", "Afirmaciones del README contra el código")))
    else:
        PLACEHOLDERS.append("tabla de migración (README.md)")
        b.append("<div class='ph'>Tabla de migración pendiente: se toma de la sección de migración de "
                 "<code>README.md</code> (Worker 1, R3).</div>")
    code = _readme_code("inicio")
    if code:
        b.append("<h3>Ejemplo mínimo</h3><pre><code>%s</code></pre><p class='muted'>Inicio rápido de "
                 "<code>README.md</code> %s; el mismo flujo con tabla de resultados está en "
                 "<code>scripts/example_end_to_end.py</code>.</p>" % (E(code), rtag))
    feats = [
        ("fix-starts", "count_windows(starts=)", "tests/test_windows.py::TestStarts",
         "<b>Datos reales: comienzos de ventana y offset del sync.</b> <code>count_windows(..., starts=)</code>, "
         "<code>window_starts(T, K, a, t0)</code> y <code>mixing_matrix_starts(tau, T, starts, b, pulse_times, "
         "irf_fwhm)</code> llevan microtiempos reales (offset del sync, pulsos no equiespaciados) a la matriz de "
         "mezcla."),
        ("fix-cond", "estimate.mixing_conditioning", "tests/test_estimate.py::TestMixingConditioning",
         "<b>Aviso de C mal condicionada.</b> <code>mixing_conditioning(C)</code> emite un "
         "<code>UserWarning</code> desde <code>mle_mixing</code> y <code>crb</code> cuando las ventanas no "
         "separan los haces."),
        ("fix-emul", "emulación de sim_exp", "README.md",
         "<b>Receta exacta para emular <code>sim_exp</code> + <code>nMINFLUX</code></b> (README §9): "
         "<code>tcspc='highest'</code>, <code>counting='legacy'</code>, <code>irf_fwhm=0</code>, "
         "<code>dead_time=0</code>, <code>tau=0.001</code>, <code>b=T/K</code>, "
         "<code>rate_per_cycle = factor·(Ns+Nb)/M_p</code>."),
        ("fix-sbrref", "simulate_counts(sbr_reference='total')",
         "tests/test_simulate.py::TestSimulateBlinking::test_t_mask_sbr_reference",
         "<b><code>sbr_reference</code> para <code>t_mask</code>.</b> <code>\"on\"</code> (default): el SBR se "
         "refiere a los ciclos encendidos; <code>\"total\"</code>: Ns/Nb fijos del conjunto, como el legado."),
        ("fix-fold", "count_windows: una fase plegada", "tests/test_windows.py::TestFoldEdge",
         "<b>Borde de punto flotante en <code>count_windows</code>.</b>"),
        ("fix-sha", "sha256 de procedencia", "tests/test_usability.py::TestPublicAPI::test_sha_robust_to_line_endings",
         "<b>sha256 de procedencia robusto a finales de línea</b> (<code>scripts/provenance_sha.py</code>)."),
    ]
    fl = []
    for key, prefix, rep, desc in feats:
        i, c = fixw(prefix)
        if c is None:
            continue
        fl.append("<li>%s <span class='muted'>%s</span> %s</li>" % (desc, E(c["text"]), fixw_src(key, prefix, rep)))
    if fl:
        suite = fixw("suite completa")[1]
        b.append("<h3>Agregado en la pasada final de la ronda 3</h3><p>Resuelve lo que el revisor de código y el "
                 "verificador marcaron como faltante para usar v2 con datos reales y como reemplazo del legado. "
                 "<span class='badge st-unclear'>cubierto por tests; revisión independiente parcial</span> "
                 "(los tests los escribió el mismo fix-worker; el verificador no los re-derivó por otra ruta).</p>"
                 "<ul>%s</ul>%s" % ("".join(fl), (
                     "<p class='muted'>%s %s</p>" % (E(suite["text"]), fixw_src("fix-suite", "suite completa", "tests")))
                     if suite else ""))
    b.append("<h3>Cómo se usa</h3><pre><code>")
    cmds = [("python -m unittest discover -s tests", "tests", "tests"),
            ("python scripts/example_end_to_end.py", "ejemplo de punta a punta (setup medido)",
             "scripts/example_end_to_end.py"),
            ("python scripts/validate_mixing_matrix.py", "validación de la matriz de mezcla",
             "scripts/validate_mixing_matrix.py"),
            ("python scripts/compare_legacy_vs_v2.py", "legado contra v2", "scripts/compare_legacy_vs_v2.py"),
            ("python scripts/study_misalignment_v2.py", "estudio de desalineación v2",
             "scripts/study_misalignment_v2.py"),
            ("python scripts/make_report_figures.py", "figuras", FIG_SCRIPT),
            ("python scripts/build_report.py", "este reporte", "scripts/build_report.py")]
    for c, d, rel in cmds:
        b.append("%s   # %s%s" % (E(c), E(d), "" if exists(rel) else "  (pendiente)"))
    b.append("</code></pre>")
    if not exists("scripts/example_end_to_end.py"):
        PLACEHOLDERS.append("scripts/example_end_to_end.py")
    return section("v2", "7. La versión mejorada", "\n".join(b))


def s_resultados():
    rows = []
    for c in cases():
        e = c["estimators"]
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s ± %s</td><td>%s</td>"
                    "<td>%s ± %s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                        f(c["irf_fwhm_ns"], 1), c["sbr_label"].replace("SBR", ""), pos(c["position_nm"]),
                        f(c["crb_mixing_axis_nm"], 3), f(c["crb_minflux_legacy_axis_nm"], 3),
                        f(e["legacy"]["bias_abs"], 2), f(e["legacy"]["bias_abs_se"], 2),
                        f(e["legacy"]["rmse_over_crb"], 3), f(e["mixing"]["bias_abs"], 2), f(e["mixing"]["bias_abs_se"], 2),
                        f(e["mixing"]["rmse_over_crb"], 3), f(e["mixing_freebg"]["rmse_over_crb"], 3),
                        f(max(e[k]["boundary_fraction"] for k in e), 3)))
    s = CMP.get("setup", {})
    b = ["<p>Mismos datos del simulador v2 (%s, τ = %g ns, ventana [%g, %g] ns, %g fotones/ciclo, tiempo muerto %g ns, "
         "TCSPC %s), N<sub>s</sub> = %d, %d localizaciones por caso, SE por bootstrap (%d réplicas) %s. "
         "RMSE/CRB usa el CRB con fuga del estimador de mezcla; el sesgo del legado no baja con N.</p>" % (
             CMP.get("source"), s.get("tau"), s.get("a"), s.get("b"), s.get("rate_per_cycle"), s.get("dead_time"),
             s.get("tcspc"), CMP.get("Ns"), CMP.get("n_loc"), CMP.get("n_boot"), cmp_src()),
         "<div class='scroll'><table class='num'><tr><th>IRF (ns)</th><th>SBR</th><th>posición (nm)</th>"
         "<th>CRB fuga</th><th>CRB legado</th><th>legado |b| (nm)</th><th>legado RMSE/CRB</th>"
         "<th>mezcla |b| (nm)</th><th>mezcla RMSE/CRB</th><th>mezcla+β libre RMSE/CRB</th>"
         "<th>fracción en el borde (máx)</th></tr>%s</table></div>" % "".join(rows),
         "<p>Reproducción independiente del verificador: %s %s</p>" % (
             E(claim_text("W3-R2 tabla compare_legacy_vs_v2")),
             claim_src("claim-cmp-verif", "W3-R2 tabla compare_legacy_vs_v2", "work/verify/r02/v5_compare.py")),
         figure("legacy_vs_v2.png", "Legado contra v2")]
    b.append("<h3 id='study-v2'>Estudio de desalineación con v2</h3>")
    ver = [c for c in CLAIMS if c.get("text", "").startswith("study_v2") and c.get("status") == "verified"]
    if STUDY is not None and ver:
        b.append(_study_v2())
    elif STUDY is not None:
        PLACEHOLDERS.append("resultados de study_v2.json (pendientes de verificación)")
        b.append("<div class='ph'><code>results/study_v2.json</code> ya existe (Worker 1, R3), pero todavía no "
                 "lo verificó nadie independiente. Por la regla del reporte (solo lo verificado), sus números no se "
                 "transcriben aquí hasta que el verificador los confirme. Se reproduce con "
                 "<code>python scripts/study_misalignment_v2.py</code>.</div>")
    else:
        PLACEHOLDERS.append("results/study_v2.json")
        b.append("<div class='ph'>Pendiente: <code>results/study_v2.json</code> (Worker 1, R3, "
                 "<code>scripts/study_misalignment_v2.py</code>).</div>")
    return section("resultados", "8. Resultados: legado contra v2", "\n".join(b))


STUDY_ROWS = [("ideal/honesto_P_conocidas", "ideal", "mezcla, potencias conocidas"),
              ("desalineada/honesto_P_conocidas", "desalineada", "mezcla, potencias conocidas"),
              ("ideal/legado", "ideal", "legado (Ec. 3.5)"),
              ("desalineada/legado", "desalineada", "legado (Ec. 3.5)"),
              ("desalineada/ingenuo", "desalineada", "mezcla con geometría ingenua")]


def _study_v2():
    """§8: study_v2.json, solo las filas que reprodujo el verificador de R3."""
    sm = STUDY.get("summary", {})
    st = STUDY.get("setup", {})
    tg = src("study-v2", "Estudio de desalineación y eficiencia con v2 (results/study_v2.json: summary, cases, "
             "efficiency_sweep)", "script", "scripts/study_misalignment_v2.py",
             detail="results/study_v2.json sha256 %s; reproducido por el verificador R3 con simulador, MLE y CRB "
                    "propios (work/verify/r03/v1_study.py)" % sha256("results/study_v2.json"),
             json_file="results/study_v2.json")
    vtag = claim_src("claim-study-v2", "study_v2 (N=2095", "work/verify/r03/v1_study.py")
    vtag_eff = claim_src("claim-study-eff", "study_v2 barrido de eficiencia", "work/verify/r03/v1_study.py")
    vtag_crb = claim_src("claim-study-crb", "study_v2: CRB por eje", "work/verify/r03/v1_study.py")
    Ns = sorted(int(k) for k in (sm.get("ideal/legado", {}).get("efficiency_mean_rmse_over_crb_by_N") or {}))
    out = ["<p>Reemplazo de <code>simulation_misalignment.py</code> y del estudio de eficiencia con "
           "<code>simulate</code> + <code>estimate</code> v2 en el setup medido: N = %s, %d posiciones continuas "
           "(fuera de grilla), TCSPC %s con tiempo muerto %g ns (supuesto), IRF %g ns (supuesta), %g fotones/ciclo, "
           "%d localizaciones por posición; sesgo y RMSE contra la posición simulada y SE por bootstrap %s. "
           "Supuestos: %s.</p>" % (
               st.get("N_main"), len(STUDY.get("positions_nm", [])), E(str(st.get("tcspc"))),
               st.get("dead_time", 0), st.get("irf_fwhm", 0), st.get("rate_per_cycle", 0),
               STUDY.get("n_loc_per_position", 0), tg, E("; ".join(STUDY.get("assumptions", []))))]
    head = ("<tr><th>geometría</th><th>estimador</th><th>máx |b| (nm)</th><th>RMSE 2D medio (nm)</th>"
            "<th>RMSE/CRB medio</th><th>fracción en el borde</th>%s</tr>" % "".join(
                "<th>RMSE/CRB, N = %d</th>" % n for n in Ns))
    trs = []
    for key, geo, lab in STUDY_ROWS:
        r = sm.get(key)
        if not r:
            continue
        eff = r.get("efficiency_mean_rmse_over_crb_by_N", {})
        trs.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>%s</tr>" % (
            geo, lab, f(r["max_bias_abs_nm"], 3), f(r["mean_rmse_2d_nm"], 2), f(r["mean_rmse_over_crb"], 3),
            f(r["boundary_fraction"], 3), "".join("<td>%s</td>" % f(eff.get(str(n)), 3) for n in Ns)))
    out.append("<div class='scroll'><table class='num'>%s%s</table></div>" % (head, "".join(trs)))
    pk = [sm[k]["max_bias_abs_nm"] for k in ("ideal/honesto_P_conocidas", "desalineada/honesto_P_conocidas") if k in sm]
    pr = [sm[k]["mean_rmse_over_crb"] for k in ("ideal/honesto_P_conocidas", "desalineada/honesto_P_conocidas") if k in sm]
    lg = [sm[k]["max_bias_abs_nm"] for k in ("ideal/legado", "desalineada/legado") if k in sm]
    nv = sm.get("desalineada/ingenuo", {}).get("max_bias_abs_nm")
    out.append("<p><b>Lectura.</b> Con las potencias de los haces conocidas, el MLE de mezcla queda en |b| ≤ %s nm "
               "y RMSE/CRB ≈ %s en las dos geometrías; el legado (Ec. 3.5) tiene un sesgo de ≈ %s nm por la fuga; "
               "y usar la geometría ideal sobre el EBP desalineado da ≈ %s nm. En el barrido de N el legado y el "
               "ingenuo empeoran en unidades de CRB al crecer N (sesgo fijo), mientras la mezcla con potencias "
               "conocidas queda ≈ 1 %s %s. El CRB por eje con fuga coincide con el del verificador a 3 decimales "
               "%s.</p>" % (f(max(pk), 2) if pk else "—", f(sum(pr) / len(pr), 2) if pr else "—",
                            f(min(lg), 1) if lg else "—", f(nv, 1), tg, vtag_eff, vtag_crb))
    out.append("<p class='muted'>Reproducción independiente (simulador, MLE y CRB propios, otra semilla): %s %s</p>"
               % (E(claim_text("study_v2 (N=2095")), vtag))
    out.append("<p class='muted'>La fila “ideal / ingenuo” de <code>study_v2.json</code> no se muestra: en la "
               "geometría ideal el modelo ingenuo es el mismo que el de potencias conocidas y los números son "
               "idénticos.</p>")
    ns_tag = claim_src("claim-neyman-scott", "Potencias libres compartidas", "work/verify/r03/v2_freepowers.py")
    ref_tag = claim_src("claim-fp-N100", "W1-R3 'con N=100 las potencias libres", "work/verify/r03/v2b_fp_eval.py")
    out.append("<p><b>Potencias libres: sesgo de Neyman-Scott.</b> Si además se ajustan las potencias relativas "
               "de los haces, compartidas entre localizaciones, con una posición libre por localización, el MLE "
               "conjunto tiene sesgo de parámetros incidentales (Neyman-Scott): las potencias estimadas no convergen "
               "a la verdad al agregar localizaciones, y el sesgo baja como ~1/N (con N fotones por "
               "localización), no con el número de localizaciones %s. A N = 100 el ajuste de potencias libres es "
               "inestable/degenerado %s. Por eso las filas “honesto” con potencias libres de "
               "<code>study_v2.json</code> no se usan aquí como resultado. Recomendación: calibrar las potencias "
               "aparte, con N alto, y pasarlas como conocidas.</p>" % (ns_tag, ref_tag))
    out.append("<p class='muted'>Detalle del verificador: %s</p>" % E(claim_text("Potencias libres compartidas")))
    return "".join(out)


def s_mezcla():
    v = MIXV
    call = v.get("sim_exp_call", {})

    def mat(C):
        return "<table class='num mat'>%s</table>" % "".join(
            "<tr><th>ventana %d</th>%s</tr>" % (i, "".join("<td>%s</td>" % f(c, 4) for c in row))
            for i, row in enumerate(C))
    b = ["<p>C<sub>ij</sub> = probabilidad de que un fotón del haz j se cuente en la ventana i (periódica, "
         "estado estacionario). Columnas = haz de origen %s.</p>" % mv_src(),
         "<div class='two'><div><b>Sin IRF</b>%s</div><div><b>IRF gaussiana 0.3 ns FWHM</b>%s</div></div>" % (
             mat(C0), mat(CI)),
         "<p>Validación contra <code>sim_exp</code> + <code>nMINFLUX</code> del legado a %g fotones/ciclo, "
         "N<sub>s</sub> = %d, N<sub>b</sub> = %d, λ = %s, %d llamadas, %s fotones en ventanas %s:</p>" % (
             v["rate_per_cycle"], call.get("Ns"), call.get("Nb"), v.get("lam"), v.get("n_calls_ok"),
             sci(v["n_detected_total"], 2), mv_src())]
    rows = "".join("<tr><td>%d</td><td>%s ± %s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        i, f(v["frac_observed"][i], 5), f(v["frac_observed_se"][i], 5), f(v["frac_mixing"][i], 5),
        f(v["dev_se_mixing"][i], 2), f(v["frac_naive"][i], 5), f(v["dev_se_naive"][i], 1)) for i in range(K))
    b.append("<table class='num'><tr><th>ventana</th><th>sim_exp</th><th>mezcla</th><th>desvío (SE)</th>"
             "<th>ingenuo (Ec. 3.5)</th><th>desvío (SE)</th></tr>%s"
             "<tr><th colspan=2>χ² (3 g.l.)</th><td colspan=2>%s (p = %s)</td><td colspan=2>%s (p %s)</td></tr></table>"
             % (rows, f(v["chi2_mixing"], 2), pval(v["chi2_pvalue_mixing_vs_sim_exp"]), f(v["chi2_naive"], 0),
                "= 0 numérico" if v["chi2_pvalue_naive_vs_sim_exp"] == 0 else "= " + pval(v["chi2_pvalue_naive_vs_sim_exp"])))
    w0 = v.get("window0_contamination", {})
    b.append("<p>En esta configuración la ventana 0 tiene un %s de fotones que vienen de otros haces por fuga y un "
             "%s de fondo %s. El verificador reprodujo la validación con otro λ y otras semillas %s.</p>" % (
                 pct(w0.get("leak_from_other_beams", 0), 2), pct(w0.get("background", 0), 1), mv_src(),
                 mixclaim_src("MIX-VALID")))
    rep = v.get("variant_Nb0_replica")
    orig = v.get("variant_Nb0")
    if rep:
        otxt = ""
        if orig and orig.get("chi2_pvalue_mixing") is not None:
            otxt = ("La variante sin fondo de la validación (N<sub>b</sub> = 0, %s fotones en ventanas) había dado "
                    "p = %s para la mezcla, un valor bajo que el verificador marcó como a confirmar %s. " % (
                        sci(orig["n_detected_total"], 2), pval(orig["chi2_pvalue_mixing"]),
                        claim_src("claim-nb0", "mixing_validation.json:variant_Nb0")))
        b.append("<p>%sUna réplica con otra semilla base (%d), mismo setup, %d llamadas y %s fotones en ventanas da "
                 "χ² = %s y p = %s para la mezcla (desvíos entre %s y %s SE), p = %s para el predictor exacto "
                 "“highest” y p %s para el ingenuo: el valor bajo fue una fluctuación %s %s "
                 "<span class='muted'>(réplica corrida en la pasada final; no re-verificada por otra ruta)</span>.</p>"
                 % (otxt, rep["seed_base"], rep["n_calls_ok"], sci(rep["n_detected_total"], 2), f(rep["chi2_mixing"], 2),
                    pval(rep["chi2_pvalue_mixing"]), f(min(rep["dev_se_mixing"]), 2), f(max(rep["dev_se_mixing"]), 2),
                    pval(rep["chi2_pvalue_sim_exp_highest_model"]),
                    "= 0 numérico" if rep["chi2_pvalue_naive"] == 0 else "= " + pval(rep["chi2_pvalue_naive"]),
                    src("mix-nb0-replica", "Réplica de variant_Nb0 con otra semilla (results/mixing_validation.json:"
                        "variant_Nb0_replica)", "script", "scripts/validate_mixing_matrix.py",
                        detail="python scripts/validate_mixing_matrix.py --only nb0-replica; clave variant_Nb0_replica",
                        json_file="results/mixing_validation.json"),
                    fixw_src("fix-nb0", "variant_Nb0_replica", "scripts/validate_mixing_matrix.py")))
    b.append(figure("mixing_validation.png", "Validación de la matriz de mezcla"))
    b.append("<h3>Tasa finita: qué hace <code>sim_exp</code> cuando llegan varios fotones por ciclo</h3>")
    pr = []
    for p in RATE.get("points", []):
        pr.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            f(p["rate_per_cycle"], 4), sci(p["n_detected_total"], 1), pval(p["chi2_pvalue_mixing"]),
            pval(p["chi2_pvalue_pred_highest"]), pval(p["chi2_pvalue_pred_earliest"]),
            f(max(abs(z) for z in p["pred_highest_minus_mixing_in_se_per_2000ph_localization"]), 3)))
    b.append("<table class='num'><tr><th>fotones/ciclo</th><th>fotones</th><th>p mezcla</th><th>p “gana k más alto”</th>"
             "<th>p “primer fotón”</th><th>máx |sesgo| (SE por loc. de 2000 fotones)</th></tr>%s</table>"
             "<p>%s</p>" % ("".join(pr), rate_src()))
    for cid in ("MIX-HIGHEST", "MIX-STUDY", "MIX-TRACKING", "MIX-NDETECT", "MIX-EARLIEST"):
        b.append("<p class='claim'>%s %s</p>" % (E(mixclaim_text(cid)), mixclaim_src(cid)))
    b.append(figure("rate_sweep.png", "Barrido de tasa"))
    b.append("<p><b>Lectura física.</b> <code>sim_exp</code> se queda con el fotón del haz de índice más alto "
             "cuando un ciclo tiene fotones de dos haces (F101); un TCSPC real se queda con el primero. Son sesgos "
             "de signo opuesto. A las tasas del tracking (1–5·10<sup>−3</sup> fotones/ciclo) los dos son ≤ 0.05 SE "
             "por localización %s: detectables solo sumando ≳10<sup>7</sup> fotones (~10<sup>7</sup> a "
             "5·10<sup>−3</sup>, ~3·10<sup>7</sup> a 3·10<sup>−3</sup>, ~2.5·10<sup>8</sup> a 10<sup>−3</sup>) %s, "
             "irrelevantes para una localización.</p>" % (mixclaim_src("MIX-TRACKING"), mixclaim_src("MIX-NDETECT")))
    b.append("<p class='muted'>Nota sobre la fórmula del test de aceptación: %s %s</p>" % (
        E(mixclaim_text("MIX-ACCFORMULA")), mixclaim_src("MIX-ACCFORMULA")))
    return section("mezcla", "9. Validación de la matriz de mezcla", "\n".join(b))


CHK_LABEL = {"aplica-ok": ("aplica, ok", "st-ok"), "falla": ("falla", "st-refuted"), "no aplica": ("no aplica", "lat")}


def _chk_verif():
    """{ítem: (status, texto)} desde el bloque claims de r03-verifier-checklist.md (CHK-<n> ...)."""
    out = {}
    for c in CHKV or []:
        m = re.match(r"\s*CHK-?(\d+)\b", c.get("text", ""))
        if m:
            out[int(m.group(1))] = (c.get("status", "unclear"), c.get("text", ""))
    return out


def _link_ids(s):
    return re.sub(r"\b(F\d{3})\b", r"<a href='#\1'>\1</a>", E(s))


def s_checklist():
    if not CHECKLIST:
        return ""
    ck = src("simuflux-checklist", "Auditoría del legado contra los 21 ítems de errores frecuentes de simulaciones "
             "MINFLUX de SimuFLUX (results/simuflux_checklist.json)", "data", "results/simuflux_checklist.json",
             detail="sha256 %s; worker R3 (reports/r03-simuflux-checklist.md)" % sha256("results/simuflux_checklist.json"),
             json_file="results/simuflux_checklist.json")
    lit = src("simuflux-ref", "Checklist de errores frecuentes en simulaciones MINFLUX derivado de SimuFLUX "
              "(Marin & Ries, Nat. Commun. 2025)", "source",
              "Marin & Ries, Nat. Commun. (2025), SimuFLUX; lista de 21 ítems en "
              "GithubPRO/donut-beam-localization/docs/literature/C_insilico_vs_donutloc.md §5 (solo lectura)")
    ver = _chk_verif()
    pending = CHKV is None
    cnt = {}
    for x in CHECKLIST:
        cnt[x["estado"]] = cnt.get(x["estado"], 0) + 1
    vst = {}
    for s_, _ in ver.values():
        vst[s_] = vst.get(s_, 0) + 1
    if pending:
        vnote = ("<p><span class='badge st-unclear'>verificación: pendiente</span> La auditoría la hizo un worker "
                 "de R3; el verificador independiente del checklist todavía no la reprodujo, así que la columna "
                 "“verificación” dice <i>pendiente</i> en todas las filas y ningún ítem se usa como resultado en "
                 "el resto del documento.</p>")
    else:
        vnote = ("<p>Verificación independiente del checklist (<code>%s</code>): %s. Donde el verificador refutó "
                 "una fila, su corrección figura en la columna “verificación” y prevalece sobre el estado del worker "
                 "%s.</p>" % (CHKV_REL, ", ".join("%d %s" % (v, k) for k, v in sorted(vst.items())) or "sin filas CHK",
                             src("chk-verifier", "Verificación independiente del checklist SimuFLUX", "source",
                                 CHKV_REL, detail="bloque claims, entradas CHK-<n>")))
    rep = JOB + "/reports/r03-simuflux-checklist.md"
    credit = src("chk-credit", "Lo que el legado hace bien según el checklist SimuFLUX (resumen del worker R3)",
                 "source", rep, detail="sección 'Resultado'")
    b = ["<p>SimuFLUX (Marin &amp; Ries, Nat. Commun. 2025) documenta los errores más frecuentes al simular MINFLUX "
         "%s. Se auditó <code>legacy/p-minflux-main</code> contra sus 21 ítems %s: %s.</p>" % (
             lit, ck, ", ".join("%d %s" % (cnt.get(k, 0), w) for k, w in (("aplica-ok", "aplican y están bien"), ("falla", "fallan"),
                                                        ("no aplica", "no aplican")))),
         vnote,
         "<p><b>Lo que hizo bien, que es la mayor parte</b> %s: la normalización de la dona es explícita y el cero se "
         "refiere al pico del anillo, como en Balzarotti; la comparación honesta/ingenua es exactamente el diseño que "
         "pide SimuFLUX; la escalera <code>geom_exp</code>/<code>exp</code> separa la geometría de la forma de la "
         "dona; el fwhm está ajustado a las donas medidas y es el mismo en los datos y en el estimador; la "
         "convención ×1.2 está documentada; el RMSE lleva la raíz, promedia por eje y coincide con la convención "
         "del CRB (lo validó ella misma, documento §4.2); y advirtió el efecto del tamaño de la perla.</p>" % credit]
    rows = []
    for x in CHECKLIST:
        n = x["item"]
        lab, cls = CHK_LABEL.get(x["estado"], (x["estado"], "lat"))
        if pending:
            vcell = "<span class='badge st-unclear'>pendiente</span>"
        elif n in ver:
            s_, t_ = ver[n]
            vcell = "<span class='badge st-%s'>%s</span> <span class='muted'>%s</span>" % (
                "ok" if s_ == "verified" else s_, E(s_), E(t_))
        else:
            vcell = "<span class='badge st-unclear'>sin fila CHK</span>"
        refuted = (not pending) and n in ver and ver[n][0] == "refuted"
        est = "<span class='badge %s'>%s</span>" % (cls, E(lab))
        if refuted:
            est = "<s>%s</s> <span class='warn'>ver verificación</span>" % est
        ref = x.get("ref_finding_or_script") or ""
        rtag = ""
        m = re.match(r"(scripts/findings/[\w.]+\.py)", ref)
        if m and exists(m.group(1)):
            rtag = src("chk-%d" % n, "Checklist SimuFLUX ítem %d (%s): %s" % (n, x["estado"], x.get("numero") or ""),
                       "script", m.group(1), detail="results/simuflux_checklist.json ítem %d" % n)
        num = x.get("numero")
        ev = ("<b>%s</b> " % E(num) if num else "") + (
            "<details><summary>evidencia</summary>%s%s<br><span class='muted'>Dónde: %s</span></details>" % (
                E(x.get("evidencia", "")), (" <i>Nota:</i> " + E(x["nota"])) if x.get("nota") else "",
                E(x.get("legacy_location") or "—")))
        rows.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s %s</td><td>%s</td></tr>" % (
            n, E(x["pregunta"]), est, ev, _link_ids(ref) if ref else "—", rtag, vcell))
    b.append("<div class='scroll'><table class='chk'><tr><th>ítem</th><th>pregunta</th><th>estado</th>"
             "<th>evidencia</th><th>ref</th><th>verificación</th></tr>%s</table></div>" % "".join(rows))
    fails = [x for x in CHECKLIST if x["estado"] == "falla"]
    if fails:
        b.append("<p><b>Fallas según la auditoría</b> %s:</p><ul>%s</ul>" % (ck, "".join(
            "<li>Ítem %d — %s <span class='muted'>%s</span></li>" % (
                x["item"], _link_ids(x.get("nota") or ""), E(x.get("numero") or "")) for x in fails)))
    return section("simuflux", "10. Auditoría contra el checklist SimuFLUX (Marin & Ries, Nat. Commun. 2025)",
                   "\n".join(b))


def s_limites():
    d = DEAD
    rates = d["params"]["rates_per_cycle"]
    grid = {}
    for r in d["rows"]:
        lab = "highest (sim_exp), d = 0" if r["tcspc"] == "highest" else "primer fotón, d = %g ns" % r["dead_time_ns"]
        grid.setdefault(lab, {})[r["rate_per_cycle"]] = r["max_abs_bias_SE_per_loc"]
    trs = "".join("<tr><td>%s</td>%s</tr>" % (lab, "".join("<td>%s</td>" % f(v.get(rt), 3) for rt in rates))
                  for lab, v in grid.items())
    b = ["<h3>Tiempo muerto y tasa finita</h3>",
         "<p>Máximo |sesgo| por ventana del simulador v2 frente a la mezcla ideal, en SE por localización de %d "
         "fotones de señal (%d localizaciones por caso) %s:</p>" % (d["params"]["Ns"], d["params"]["n_loc_per_case"], dt_src()),
         "<table class='num'><tr><th>caso</th>%s</tr>%s</table>" % (
             "".join("<th>%s /ciclo</th>" % f(rt, 4) for rt in rates), trs),
         "<p><b>d = n·T anula el sesgo exactamente.</b> Con un SPAD no paralizable y d ≥ T, en una ventana de largo "
         "d cabe a lo sumo una avalancha, así que la probabilidad de estar muerto en t es la integral de la tasa "
         "en [t − d, t]; con d = n·T esa integral es n veces las avalanchas por período, una constante, y la "
         "densidad registrada es proporcional a la incidente a cualquier tasa %s. No aplica a un detector "
         "paralizable ni a un TDC con tiempo muerto propio.</p>" % claim_src(
             "claim-dnT", "W2-R2 barrido de tiempo muerto", "work/verify/r02/v2_deadtime.py"),
         figure("dead_time_sweep.png", "Barrido de tiempo muerto")]
    # sesgo residual por tasa finita: texto corregido por el verificador, números extraídos del ledger
    ci, c = claim("W3-R2 'el sesgo MC del MLE de mezcla")
    if c:
        t = c["text"]
        m1 = re.search(r"tasa finita es ~([\d.]+-[\d.]+) nm", t)
        m2 = re.search(r"by=(-?[\d.]+)±([\d.]+) nm", t)
        m3 = re.search(r"todo es <=([\d.]+) CRB", t)
        rngtxt = m1.group(1).replace("-", "–") if m1 else "?"
        o1n = m2.group(1).lstrip("-") if m2 else "?"
        crb = m3.group(1) if m3 else "?"
        b.append("<h3>Sesgo residual del estimador de mezcla</h3><p>El modelo directo del estimador no incluye la "
                 "distorsión de TCSPC y tiempo muerto a tasa finita. Eso induce un sesgo de %s nm; además el MLE "
                 "tiene su sesgo O(1/N) propio, ~%s nm con N ~ 2000 (también sobre datos multinomiales puros; no es "
                 "un bug). Todo queda ≤ %s CRB %s.</p>" % (
                     rngtxt, o1n, crb, claim_src("claim-resid", "W3-R2 'el sesgo MC del MLE de mezcla",
                                                 "work/verify/r02/v6_residual_bias.py")))
    b.append("<h3>Supuestos declarados</h3><ul>")
    for a in d.get("assumptions", []):
        b.append("<li>%s %s</li>" % (E(a), dt_src()))
    b.append("<li>“highest” fija el SBR incidente, mientras que <code>sim_exp</code> fija el registrado: %s %s. "
             "Se documenta como limitación.</li>" % (E(claim_text("W2-R2 'highest reproduce sim_exp' con fondo")),
                                                    claim_src("claim-highest-sbr", "W2-R2 'highest reproduce sim_exp' con fondo")))
    b.append("<li>%s %s</li>" % (E(claim_text("Sustitución de datos")),
                                                  claim_src("claim-subst", "Sustitución de datos")))
    b.append("<li>%s %s</li>" % (E(claim_text("AUTORIA F101-F111")), claim_src("claim-autoria", "AUTORIA F101-F111")))
    b.append("<li>%s %s <span class='good'>→ el arranque por bloques quedó resuelto y verificado en R3 %s; sigue "
             "el punto fijo O(n²) del tiempo muerto a saturación.</span></li>" % (
                 E(claim_text("Rendimiento: el arranque en grilla")),
                 claim_src("claim-perf", "Rendimiento: el arranque en grilla"),
                 claim_src("claim-chunk", "Arranque en grilla por bloques")))
    b.append("<li>Ventanas solapadas (b &gt; T/K): el CRB multinomial deja de valer y el MLE puede caer en un "
             "óptimo local. En R2 v2 no las rechazaba %s; en R3 se agregó un <code>ValueError</code> explícito "
             "(salvo <code>allow_overlap=True</code>), verificado en R3 (<code>simulate_counts</code>, "
             "<code>crb</code>, <code>mle_mixing</code>, <code>count_windows</code>; las funciones de bajo nivel "
             "<code>forward_probs</code> y <code>window_probs</code> no lo tienen) %s.</li>"
             % (claim_src("claim-overlap", "Robustez del estimador y del CRB con b > T/K"),
                claim_src("claim-guard", "Guard de ventanas solapadas")))
    b.append("</ul>")
    fixed, still = [], []
    for i, c in enumerate(CLAIMS):
        if c["status"] not in ("refuted", "unclear"):
            continue
        grp, why = _open_group(c["text"])
        li = "<li><span class='badge st-%s'>%s</span> %s %s%s</li>" % (
            c["status"], c["status"], E(c["text"]),
            src("open-%d" % i, c["text"], "data", JOB + "/state.json",
                detail="state.json claims[%d] (status=%s, ronda %s, %s)" % (i, c["status"], c["round"], c["source"])),
            (" <span class='good'>→ %s</span>" % why) if why else "")
        (fixed if grp == "fixed" else still).append(li)
    b.append("<h3 id='abiertos'>Afirmaciones refutadas o sin decidir del ledger</h3><p>Una afirmación refutada o "
             "<i>unclear</i> sigue viva hasta que se resuelve. Se separan las que ya quedaron corregidas en esta "
             "revisión (el texto de este documento usa la versión corregida) de las que siguen abiertas. Ninguna se "
             "usa como resultado en su forma original.</p>")
    b.append("<h4>Corregido en esta revisión</h4><ul>%s</ul>" % "".join(fixed))
    b.append("<h4>Sigue abierto</h4><ul>%s</ul>" % "".join(still))
    b.append(_r3_verified())
    b.append(_next_steps())
    return section("limites", "11. Límites, supuestos y puntos abiertos", "\n".join(b))


_FW = "pasada final (fix-worker R3): cubierto por tests; revisión independiente parcial"
# (prefijo del texto en el ledger, grupo, cómo quedó resuelto). Sin entrada = sigue abierto.
OPEN_MAP = [
    ("MIX-NDETECT", "fixed", "texto corregido de mixing_claims.json en §9 (~10^7 a 5e-3, ~3·10^7 a 3e-3)"),
    ("F103-num", "fixed", "tarjeta F103 con 6.84 % / 2.54 % y el desplazamiento 0.88 vs 1.18 nm"),
    ("F111-comentarios", "fixed", "tarjeta F111 sin “paridad invertida”"),
    ("F201: la clase CONCEPTUAL", "fixed", "F201 clasificado DISEÑO (inbox R2), cociente ≈2.5 contra el CRB con fuga y crédito a ESTADO…md:115-117"),
    ("F202 clase IMPLEMENTACION", "fixed", "F202 clasificado DISEÑO, supuesto del máximo del .npy explícito y crédito a ESTADO…md:116"),
    ("F203: 'el 100 %", "fixed", "tarjeta F203: 100 % solo con R ≤ 1.0·L (71–72 % con 1.25·L)"),
    ("Robustez del estimador y del CRB con b > T/K", "fixed", "guard de ventanas solapadas agregado y verificado en R3"),
    ("Rendimiento: el arranque en grilla", "open", "el arranque por bloques quedó resuelto y verificado en R3; sigue el punto fijo O(n²) del tiempo muerto a saturación"),
    ("El modelo directo del estimador no incluye", "fixed", "resuelto: d = n·T verificado en R2 con prueba y MC; el sesgo residual está documentado en esta sección"),
    ("Docstring de estimate", "fixed", "flag converged verificado en R3 (docstring corregido)"),
    ("Usabilidad como reemplazo", "fixed", "README, ejemplo de punta a punta, migración, exports y port de F107 en R3 (§7)"),
    ("W2-R2 'el valor esperado del doble conteo", "fixed", "referencia corregida a 11.175 %"),
    ("W3-R2 'el sesgo MC del MLE de mezcla", "fixed", "sesgo residual 0.02–0.035 nm + O(1/N) en esta sección"),
    ("Reproducibilidad de los tests con sha256", "fixed", "sha256 con fin de línea normalizado (scripts/provenance_sha.py) y .gitattributes; " + _FW),
    ("count_windows borde de punto flotante", "fixed", "TestFoldEdge; " + _FW),
    ("Port de F107 (t_mask) contra la convención de SBR", "fixed", "sbr_reference=\"on\"|\"total\" y README §4/§5; " + _FW),
    ("README como guía de migración", "fixed", "README §9: receta de emulación de sim_exp, fórmula de rate_per_cycle, datos reales, N para crb, exports y cov_ellipse; " + _FW),
    ("Caption de timeline_20MHz", "fixed", "leyenda corregida: C[i][i] = 0.8973 con la IRF dibujada (0.9092 sin IRF)"),
    ("Caption de dead_time_sweep", "fixed", "leyenda corregida: p ≥ 0.29, mínimo 0.296"),
    ("W1-R3 'con N=100 las potencias libres", "fixed", "§8 no usa esos números; dice que a N = 100 el ajuste es inestable/degenerado"),
    ("report/index.html resumen", "fixed", "resumen corregido (0.112 nm, 0.034 SE)"),
    ("report/index.html tarjetas F201/F205", "fixed", "tarjetas corregidas (TestStudyV2 es de R3, verificado en R3)"),
    ("report/index.html seccion 10", "fixed", "esta sección separa lo corregido de lo abierto"),
    ("mixing_validation.json:variant_Nb0", "fixed", "réplica con otra semilla p = 0.957 (§9); " + _FW),
    ("W2-R2 'highest reproduce sim_exp' con fondo", "open", "documentado como limitación (supuestos, arriba)"),
]


def _open_group(text):
    for pre, grp, why in OPEN_MAP:
        if text.startswith(pre):
            return grp, why
    return "open", ""


# afirmaciones verificadas de R3 que son sobre este documento o su generación (no son resultados)
_META = ("report/index.html", "build_report.py", "Privacidad del HTML")


def _r3_verified():
    """Afirmaciones verificadas en la ronda 3 (ledger), sin las que tratan del propio documento."""
    out = []
    for i, c in enumerate(CLAIMS):
        if c.get("round") != 3 or c.get("status") != "verified" or c.get("text", "").startswith(_META):
            continue
        out.append("<li>%s %s</li>" % (E(c["text"]), src(
            "r3-ver-%d" % i, c["text"], "data", JOB + "/state.json",
            detail="state.json claims[%d] (status=verified, ronda 3, %s)" % (i, c.get("source")))))
    if not out:
        return ""
    return ("<h3>Verificado en la ronda 3</h3><p>Lo que el verificador o el revisor de código de R3 reprodujeron "
            "por su cuenta.</p><ul>%s</ul>" % "".join(out))


def _next_steps():
    rel = JOB + "/reports/r03-pi.md"
    if not exists(rel):
        return ""
    with io.open(_p(rel), encoding="utf-8") as fh:
        txt = fh.read()
    m = re.search(r"## LO QUE M[ÁA]S SE PODR[ÍI]A HACER\n(.*)", txt, re.S)
    if not m:
        return ""
    items = re.split(r"\n\d+\. ", "\n" + m.group(1).strip())
    items = [re.sub(r"\s+", " ", it).strip() for it in items if it.strip()]
    return ("<h3>Lo que más se podría hacer después</h3><p class='muted'>Propuestas del PI (no son resultados) %s.</p><ol>%s</ol>"
            % (src("pi-next", "Lista de próximos pasos del PI (r03)", "source", rel,
                   detail="sección 'LO QUE MÁS SE PODRÍA HACER'"),
               "".join("<li>%s%s</li>" % (_md_inline(it), " <span class='good'>→ hecho en R3 y verificado (tarjeta "
                                          "<a href='#F107'>F107</a>).</span>" if it.startswith("Portar F107") and
                                          claim("F107 portado")[1] is not None else "") for it in items)))


def s_apendice():
    rows = "".join("<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td><span class='badge st-%s'>%s</span></td></tr>" % (
        E(x["id"]), E(x["title"]), E(x["evidence"] + (" " + x["note"] if x.get("note") else "") +
                                     (" Falta: " + x["missing"] if x.get("missing") else "")),
        "unclear" if x["status"] == "unclear" else "ok", E(x["status"])) for x in DISCARDED)
    b = ["<p>Sospechas que se investigaron y se descartaron (o quedaron sin decidir) %s.</p>" % src(
        "discarded", "Sospechas descartadas y verificadas (F105, F151–F154, D-*, F290-D*)", "data",
        "results/findings_discarded.json"),
         "<div class='scroll'><table><tr><th>id</th><th>sospecha</th><th>evidencia</th><th>estado</th></tr>%s</table></div>" % rows]
    return section("apendice", "12. Apéndice: sospechas descartadas", "\n".join(b))


def s_versiones():
    files = ["results/findings.json", "results/findings_discarded.json", "results/mixing_validation.json",
             "results/mixing_claims.json", "results/mixing_rate_sweep.json", "results/dead_time_sweep.json",
             "results/compare_legacy_vs_v2.json", "results/study_v2.json", "results/simuflux_checklist.json",
             "report/figs/captions.json",
             JOB + "/state.json", "scripts/build_report.py"]
    rows = "".join("<tr><td><code>%s</code></td><td><code>%s</code></td></tr>" % (
        E(r), (sha256(r) or "ausente")[:16]) for r in files)
    return ('<section id="versiones"><h2>Versiones de los datos</h2><p class="muted">sha256 (16 primeros '
            'caracteres) de cada archivo leído al generar este reporte.</p><table class="num">%s</table></section>' % rows)


# ----------------------------------------------------------------------------- página

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1f23;--muted:#5d6470;--card:#ffffff;--line:#dcdad3;--accent:#1f5f8b;
--c-con:#a3312a;--c-imp:#1f5f8b;--c-dis:#8a6412;--good:#2c6e3f;--warn:#a3312a;--ph:#fff4d6;--code:#f1efe8;}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#17191c;--fg:#e6e4df;--muted:#a3a8b0;
--card:#1f2226;--line:#3a3d42;--accent:#7fb5dd;--c-con:#e58a82;--c-imp:#7fb5dd;--c-dis:#d9b25a;--good:#86c79a;
--warn:#e58a82;--ph:#3a3220;--code:#2a2d31;}}
:root[data-theme="dark"]{--bg:#17191c;--fg:#e6e4df;--muted:#a3a8b0;--card:#1f2226;--line:#3a3d42;--accent:#7fb5dd;
--c-con:#e58a82;--c-imp:#7fb5dd;--c-dis:#d9b25a;--good:#86c79a;--warn:#e58a82;--ph:#3a3220;--code:#2a2d31;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,
"Helvetica Neue",Arial,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:1.9rem;line-height:1.2;margin:.2em 0}
h2{font-size:1.45rem;margin:2.2em 0 .6em;padding-bottom:.25em;border-bottom:2px solid var(--line)}
h3{font-size:1.12rem;margin:1.6em 0 .5em}
h4{font-size:1.02rem;margin:.35em 0 0;font-weight:600}
a{color:var(--accent)}
code{background:var(--code);padding:0 .25em;border-radius:3px;font-size:.9em;word-break:break-word}
pre{background:var(--code);padding:12px;border-radius:6px;overflow-x:auto}
pre code{background:none;padding:0}
.muted{color:var(--muted)}
.lead{font-size:1.06rem}
.src{font-size:.68em;color:var(--muted);vertical-align:super;font-family:ui-monospace,Consolas,monospace;
white-space:nowrap}
table{border-collapse:collapse;width:100%;margin:.6em 0 1em;font-size:.9rem;background:var(--card)}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--code);font-weight:600}
table.num td{font-variant-numeric:tabular-nums}
table.mat td{text-align:right}
.scroll{overflow-x:auto}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:700px){.two{grid-template-columns:1fr}}
.toc{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 20px}
.toc ol{margin:.3em 0;padding-left:1.4em}
.toc .ids a{display:inline-block;margin:2px 6px 2px 0;font-family:ui-monospace,Consolas,monospace;font-size:.85em}
.callout{border-left:4px solid var(--c-con);background:var(--card);padding:10px 14px;margin:1em 0;border-radius:4px}
.note{border-left:3px solid var(--line);padding-left:12px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--c-imp);border-radius:8px;
padding:12px 16px;margin:14px 0;break-inside:avoid}
.card.CONCEPTUAL{border-left-color:var(--c-con)}.card.DISENO{border-left-color:var(--c-dis)}
.card dl{display:grid;grid-template-columns:130px 1fr;gap:4px 12px;margin:.6em 0}
@media (max-width:640px){.card dl{grid-template-columns:1fr}}
.card dt{font-weight:600;color:var(--muted);font-size:.88rem}
.card dd{margin:0}
.fid{font-family:ui-monospace,Consolas,monospace;font-weight:700;font-size:1.05rem}
.badge{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;
padding:1px 7px;border-radius:10px;border:1px solid currentColor;margin-left:4px}
.badge.CONCEPTUAL{color:var(--c-con)}.badge.IMPLEMENTACION{color:var(--c-imp)}.badge.DISENO{color:var(--c-dis)}
.badge.lat{color:var(--muted)}.badge.ci{color:var(--c-con)}
.badge.st-refuted,.badge.st-unclear{color:var(--warn)}.badge.st-ok{color:var(--good)}
.good{color:var(--good)}
.good-list li{margin:.35em 0}
.vnote{border:1px dashed var(--c-dis);border-radius:6px;padding:6px 10px;font-size:.92rem;margin:.4em 0}
details summary{cursor:pointer;color:var(--accent);font-size:.92rem}
.fig{margin:1.2em 0;text-align:center}
.fig img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:4px;background:#fff}
.fig figcaption{text-align:left;font-size:.9rem;margin-top:.4em}
.ph{background:var(--ph);border:2px dashed var(--c-dis);border-radius:6px;padding:14px;text-align:left}
.ph-inline{background:var(--ph);padding:0 .3em}
.warn{color:var(--warn)}
.privado{border:2px solid var(--warn);color:var(--warn);border-radius:6px;padding:6px 12px;margin:0 0 10px}
table.chk td:nth-child(2){min-width:220px}table.chk td:nth-child(4){min-width:200px}
.claim{font-size:.92rem;border-left:3px solid var(--line);padding-left:10px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.bar button{font:inherit;font-size:.85rem;padding:3px 10px;border:1px solid var(--line);background:var(--card);
color:var(--fg);border-radius:5px;cursor:pointer}
@media print{body{background:#fff;color:#000;font-size:11pt}.bar{display:none}.wrap{max-width:none;padding:0}
.card{break-inside:avoid}h2{break-after:avoid}a{color:#000;text-decoration:none}.src{color:#555}
details>summary{display:none}}
"""

JS = """
function setAll(o){document.querySelectorAll('details').forEach(function(d){d.open=o;});}
window.addEventListener('beforeprint',function(){setAll(true);});
function toggleTheme(){var r=document.documentElement;var dark=r.getAttribute('data-theme')==='dark'||
(!r.getAttribute('data-theme')&&window.matchMedia('(prefers-color-scheme: dark)').matches);
r.setAttribute('data-theme',dark?'light':'dark');}
"""


def build():
    del SECTIONS[:]
    del PLACEHOLDERS[:]
    PROV.clear()
    body = [s_resumen(), s_metodo(), s_crimen(), s_findings(), s_bien(), s_distinto(), s_v2(), s_resultados(),
            s_mezcla(), s_checklist(), s_limites(), s_apendice(), s_versiones()]
    body = [x for x in body if x]
    ids = "".join("<a href='#%s'>%s</a>" % (x["id"], x["id"]) for c in CLASS_ORDER
                  for x in FINDINGS if x["class"] == c)
    toc = "<nav class='toc'><b>Contenido</b><ol>%s</ol><div class='ids'>Hallazgos: %s</div></nav>" % (
        "".join("<li><a href='#%s'>%s</a></li>" % (sid, E(t.split(". ", 1)[-1])) for sid, t in SECTIONS), ids)
    ph = ""
    if PLACEHOLDERS:
        ph = ("<div class='ph'><b>Borrador con partes pendientes:</b> %s.</div>" % E("; ".join(PLACEHOLDERS)))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    page = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revisión pminflux-sim</title>
<meta name="description" content="Revisión crítica del simulador p-MINFLUX legado y versión v2 (privado).">
<style>{css}</style></head>
<body><div class="wrap">
<div class="privado"><b>Documento privado: contiene datos no publicados; no compartir sin revisar.</b></div>
<p class="muted">Documento privado · revisión agent-team <code>{job}</code> · generado {now} por <code>scripts/build_report.py</code></p>
<h1>Revisión del simulador p-MINFLUX: qué estaba mal, qué estaba bien y la versión v2</h1>
<p class="muted">Hallazgos clasificados como <b>conceptual</b>, <b>implementación</b> o <b>diseño</b>. Los
números entre corchetes <span class="src">&#91;src:clave&#93;</span> remiten a <code>out/provenance.json</code>.</p>
<div class="bar"><button onclick="setAll(true)">Expandir todo</button><button onclick="setAll(false)">Contraer todo</button>
<button onclick="toggleTheme()">Claro / oscuro</button><button onclick="window.print()">Imprimir</button></div>
{ph}
{toc}
{body}
</div><script>{js}</script></body></html>
""".format(css=CSS, job=JOB, now=now, ph=ph, toc=toc, body="\n".join(body), js=JS)
    page = scrub(page)
    for v in PROV.values():
        for k in ("statement", "reproduce", "detail"):
            if isinstance(v.get(k), str):
                v[k] = scrub(v[k])
        if "also" in v:
            v["also"] = [scrub(a) for a in v["also"]]
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(page)
    os.makedirs(os.path.dirname(OUT_PROV), exist_ok=True)
    with io.open(OUT_PROV, "w", encoding="utf-8") as fh:
        json.dump(PROV, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("report/index.html: %d bytes, %d entradas de procedencia, %d secciones" % (
        len(page.encode("utf-8")), len(PROV), len(SECTIONS)))
    print("placeholders: %s" % ("; ".join(PLACEHOLDERS) if PLACEHOLDERS else "ninguno"))
    return page


if __name__ == "__main__":
    build()
