# -*- coding: utf-8 -*-
"""Collector of audit A (Worker 2, round 1): runs every F1xx script of this audit and writes
results/findings_A.json = metadata of each finding (text, class, location, authorship, fix)
+ the numbers each script actually produced ("evidence").  Status of every entry: "candidate"
(findings) or "descartado" (discarded suspicions) until the verifier reproduces them.
Run: python scripts/findings/F100_collect_findings_A.py      (~7 min, fixed seeds)
     python scripts/findings/F100_collect_findings_A.py --no-run   (metadata only)
"""
import os
import sys
import json
import math
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LEG = "legacy/p-minflux-main/tools/tools_simulations.py"

CRITERION = ("CONCEPTUAL = el modelo fisico o estadistico esta mal (el resultado es incorrecto aunque "
             "el codigo haga lo que pretende); IMPLEMENTACION = el codigo no hace lo que dice o pretende "
             "(bug); DISENO = decision defendible que limita el alcance o la validez. 'Latente' = no "
             "afecta a ningun numero publicado por la autora con su configuracion actual.")

FINDINGS = [
 dict(id="F101", script="scripts/findings/F101_tmicro_overwrite.py",
  title="sim_exp: en un ciclo con fotones de >=2 haces sobrevive el de indice k MAS ALTO (TCSPC real: el mas temprano)",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":511-531 (bucle Tmicro[m1] = k1*Texp + Exp); recorte por ranura l.464",
  authorship="Masullo (nucleo original; la ruta rapida de la autora conserva el mismo comportamiento)",
  scenario="lambda=[0.12,0.28,0.35,0.25], Tlife=0.001, Nb=0, a=0, b=dt/K; tasa 0.5 fotones/ciclo, 60000 fotones",
  impact=("Mecanismo confirmado: las fracciones de sim_exp coinciden con 'gana el k mas alto' (|z|<=1.1) y se "
          "apartan de p hasta 25 SE (ventana 3: 0.297 vs 0.25). A la tasa de los estudios (0.0105/ciclo) el 0.38 % de "
          "los ciclos ocupados tiene >=2 haces y el sesgo relativo maximo previsto es 0.46 % (haz 0). "
          "Impacto cuantitativo y barrido de tasa: ver W1 (results/mixing_rate_sweep.json)."),
  fix="Por ciclo, quedarse con el fotón de microtiempo MINIMO (primer foton) y aplicar tiempo muerto; o simular a tasa baja y declararlo.",
  what_was_right="El recorte a 1 foton por ranura y el reparto multinomial+ciclos uniformes son correctos (F152a).",
  overlaps="W1 cuantifica el impacto (tarea 1c)."),
 dict(id="F102", script="scripts/findings/F102_zeros_in_window0.py",
  title="Los ceros de los ciclos vacios en relTime se cuentan en la ventana 0 si la ventana abre antes del pulso (a<0)",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":517 (Tmicro=np.zeros(M_p)), :569 (concatenate), :994-996 (relTime>ti estricto)",
  authorship="Masullo (original)",
  scenario="TCP beams(K=4,L=100), fwhm 360, emisor (5,-5), Ns=2000, Nb=95, M_p=2e5, Tlife=0.001, dt=50, b=12.5; a=0 vs a=-0.25 ns; 20 repeticiones",
  impact=("relTime tiene 200095 elementos, 198000 de ellos 0.0 exacto. Con a=0 la ventana 0 cuenta 37 fotones y el MLE da "
          "error medio 1.28 nm; con a=-0.25 ns la ventana 0 cuenta 198037, el MLE termina en el borde de busqueda en el "
          "100 % de los casos, estimacion media (74.4,-4.2) nm, error medio 69.9 nm. Latente: todos los estudios usan a=0 "
          "y funcionan solo por la desigualdad estricta."),
  fix="Devolver solo los microtiempos de fotones detectados (sin ceros) o una mascara; validar a,b en nMINFLUX.",
  what_was_right="Con a=0 y la desigualdad estricta el conteo es correcto (los ceros quedan fuera).",
  overlaps="Sospecha (i) del plan del PI."),
 dict(id="F103", script="scripts/findings/F103_windows_not_periodic.py",
  title="nMINFLUX no pliega las ventanas modulo el periodo ni controla solapamiento",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":993-997",
  authorship="Masullo (original)",
  scenario=("S1: ceros filtrados, a=-0.5, b=12.5, Tlife=4.21 y 0.001, TCP, emisor (5,-5), SBR 21; "
            "S2: b=13 > dt/K"),
  impact=("S1: la ventana 0 pierde [49.5,50): -5.9 % de sus cuentas con Tlife=4.21 (-2.8 % con 0.001); fondo 0.24 vs "
          "0.25 del ciclo; sesgo asintotico extra del MLE 0.34 nm (Tlife=4.21) y 0.06 nm (0.001). S2: fotones contados "
          "dos veces: 11.2 % (Tlife=4.21) y 94.9 % (Tlife=0.001), sin aviso. Latente (estudios: a=0, b=dt/K)."),
  fix="Ventana i = {t : (t - tau_i - a) mod T in [0, b)}; error si b > T/K.",
  what_was_right="Con a=0 y b<=dt/K (lo que usan todos los estudios) las ventanas son correctas.",
  overlaps="Sospecha (ii)."),
 dict(id="F104", script="scripts/findings/F104_naive_model_windows_leakage.py",
  title="pos_MINFLUX/crb_minflux (Ec. 3.5, fondo 1/K, sin fuga) no describen ventanas b<T/K ni la fuga entre pulsos",
  **{"class": "CONCEPTUAL"},
  legacy_location=LEG + ":1041 (p de pos_MINFLUX), :649-661 (crb_minflux), comentario :423-435 ('EXACTAMENTE')",
  authorship="Modelo Ec. 3.5: Masullo (tesis y codigo). El comentario que lo declara exacto y su verificacion: la autora.",
  scenario=("TCP beams(K=4,L=100), fwhm 360; setup medido tau=4.21 ns, ventana [0,10.1] ns, dt=50; SBR 21 (2000/95) y 6 "
            "(2000/333); 5 posiciones; sesgo asintotico (sin ruido) del MLE con el modelo de pos_MINFLUX sobre E[n] exacto "
            "de sim_exp+nMINFLUX (verificado por MC: chi2 p=0.38 modelo de mezcla, chi2=2559 modelo ingenuo)"),
  impact=("Configuracion de los estudios (Tlife=0.001, b=12.5): sesgo 0.000 nm, el comentario es correcto ahi. Setup medido, "
          "SBR 21: sesgo 0.85 (5,-5), 1.51 (-5.07,-7.56), 1.63 (20,0), 2.69 (-15,15), 2.36 (0,-30) nm, frente a CRB "
          "0.82-1.22 nm (sesgo 1.0-2.7 CRB); la ventana 0 en (5,-5) tiene 46 % de fotones de otros haces; el CRB real es "
          "8.6-13.5 % mayor que el que da crb_minflux. SBR 6: sesgo 0.59-2.32 nm. Solo b=10.1 sin fuga: 0.01-0.48 nm (SBR "
          "en ventanas 26.1 vs 21.05 nominal)."),
  fix="p_i' = (Ns sum_j C_ij q_j + Nb b/T) / total, con la matriz de mezcla periodica C y el fondo por ancho de ventana; CRB con ese p' y N en ventanas.",
  what_was_right="La autora verifico que el fondo uniforme reproduce Ec. 3.5 con b=dt/K; F104 lo confirma (sesgo 0, chi2 p=0.31).",
  overlaps="W1 valida C contra sim_exp; W3 cuantifica el impacto en los estudios (Tlife=0.001). Aqui: sesgo del estimador del nucleo."),
 dict(id="F106", script="scripts/findings/F106_grid_emitter_and_mle.py",
  title="Emisor y MLE atados a la grilla de la PSF: el emisor se ajusta al nodo y el argmax discreto cuantiza",
  **{"class": "DISENO"},
  legacy_location=LEG + ":444 (lambda=psf[i,r0[0],r0[1]]), :93-106 (spaceToIndex), :1099 (argmax)",
  authorship="Masullo (diseno original). La autora ya identifico el termino px^2/12 (docx 6.3) y corrigio el truncado.",
  scenario="TCP ideal, fwhm 360, grilla 200 nm/1 nm, SBR 21; (a) emisor pedido (-5.07,-7.56), 200 sim_exp; (b) N=2095/20950/104750, 400 MC, emisor en nodo (5,-5) y fuera (5.4,-5.3)",
  impact=("(a) se simula en (-5,-8) (0.45 nm del pedido); media MC (-5.01,-7.86)+-0.06: 'sesgo' respecto del pedido "
          "(0.06,-0.30) nm, del nodo (-0.01,0.14). (b) en nodo: RMSE/CRB 1.09, 0.93 y 0.00 (100 % aciertos exactos con "
          "CRB 0.115 nm: supereficiencia artificial); fuera de nodo: 1.05, 1.77, 3.40 (sesgo de redondeo (-0.22,0.25) nm)."),
  fix="Emisor continuo (lambda evaluado analiticamente o interpolado) y MLE continuo (grilla gruesa + refinamiento); sesgo siempre contra la posicion realmente simulada.",
  what_was_right="spaceToIndex redondea (fix de la autora, F153) y ella ya documento la cuantizacion px^2/12.",
  overlaps="simulation_misalignment.py:230 calcula el sesgo contra R0_NM y no contra el nodo: ambito de W3."),
 dict(id="F107", script="scripts/findings/F107_tmask_ignored_p_minflux.py",
  title="sim_exp('p_minflux') ignora t_mask (parpadeo) en silencio",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":454-466 (_photons_ready=True), :473-491 (mascara solo en la otra ruta)",
  authorship="La autora (refactor de la ruta rapida, comentario l.454-457); a confirmar con el historial",
  scenario="t_mask = 0 en la primera mitad de M_p=2e5 ciclos, Ns=2000, Nb=0",
  impact="p_minflux pone 1028/2000 fotones (51.4 %) en la mitad apagada; cw_minflux con la misma mascara: 0. Latente (todos los estudios pasan t_mask=None).",
  fix="Aplicar la mascara en la ruta rapida (muestrear ciclos con probabilidad proporcional a t_mask) o lanzar error si t_mask no es None.",
  what_was_right="La ruta rapida es estadisticamente equivalente al multinomial original (F152a) y ~100x mas rapida.",
  overlaps=""),
 dict(id="F108", script="scripts/findings/F108_cov_ellipse.py",
  title="cov_ellipse ordena mal los autovectores y no usa el nivel de confianza",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":80-90",
  authorship="Masullo/Lopez/Richter (original; el TODO de r2 ya estaba)",
  scenario="cov con desvios 3 y 1 nm y eje mayor a phi = 0, 30, 60, 120, 150 grados; nsig = 1, 2",
  impact="Eje mayor devuelto con error de -90, -90, -30, +30, -90 grados (no es un cambio de convencion constante); ejes siempre 2 y 6 para nsig 1 y 2 (correctos: 3.03/9.09 y 4.97/14.92). No se usa en ningun script: latente.",
  fix="vec = vec[:, order] con orden descendente, theta = degrees(arctan2(vec[1,0], vec[0,0])), ejes 2*sqrt(r2*val).",
  what_was_right="",
  overlaps="Sospecha (viii)."),
 dict(id="F109", script="scripts/findings/F109_psf_helper.py",
  title="psf(): la rama gaussiana ignora donut_fwhm, la rama SW da NameError y fov_center desplaza x con signo opuesto",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":181-199",
  authorship="donut_fwhm lo agrego la autora (sin actualizar la rama gaussiana); SW/theta y fov_center: original, a confirmar",
  scenario="psf(d='gaussian', donut_fwhm=250); psf(d='sw'); dona en (0,0) con fov_center=(20,20)",
  impact="FWHM gaussiana medida 361 nm (pedida 250); NameError 'SW'; centro real de la grilla (-20.5, 20.5) en vez de (20,20). Latente: todos los usos son d='donut', fov_center=[0,0].",
  fix="Pasar el fwhm a gaussian(); quitar la rama SW; x = arange(-size/2 + c_x, ...), y analogo.",
  what_was_right="La rama 'donut' con fov_center=[0,0] es consistente con indexToSpace (F153).",
  overlaps="Sospecha (viii)."),
 dict(id="F110", script="scripts/findings/F110_sbr_infinite.py",
  title="SBR=inf (sin fondo) da NaN: pos_MINFLUX devuelve la esquina del FOV y crb_minflux NaN, sin aviso",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":1041, :1050, :649-653",
  authorship="Masullo (expresion SBR/(SBR+1) original)",
  scenario="TCP ideal, grilla 200/1 nm, emisor (5,-5), cuentas esperadas 1000 p, SBR=inf vs 1e12",
  impact="SBR=inf: estimacion (-100,100) nm (pixel (0,0), fuera incluso de r_max) y CRB NaN en toda la grilla; SBR=1e12: (5,-5) y CRB 1.05 nm. Latente.",
  fix="s = 1 si SBR es inf (o parametrizar por s = Ns/(Ns+Nb)).",
  what_was_right="",
  overlaps=""),
 dict(id="F111", script="scripts/findings/F111_ebp_centres_K.py",
  title="ebp_centres falla para K>4 (L=[L,L,L,L]) y los comentarios de paridad estan invertidos",
  **{"class": "IMPLEMENTACION"},
  legacy_location=LEG + ":266, :273-289",
  authorship="L. Richter (docstring '[Lars]')",
  scenario="ebp_centres(K, 100, True) con K = 4, 5, 7",
  impact="K=5 y K=7: IndexError. K=4 coincide con beams() (angulos 120/240/0), que difiere de ebp.ideal_positions (210/330/90), diferencia ya documentada en C_pminflux_practice.md 5.2. Latente: los estudios actuales usan ebp.py.",
  fix="L = np.full(K, L); corregir comentarios; un solo generador de geometria (ebp.py).",
  what_was_right="La autora centralizo la geometria en ebp.py.",
  overlaps=""),
]

DISCARDED = [
 dict(id="F105", script="scripts/findings/F105_fixed_Ns_Nb_vs_multinomial_crb.py",
  title="(v) Ns y Nb fijos exactos en sim_exp vs el modelo Mult(N,p) del CRB",
  legacy_location=LEG + ":533-559",
  evidence=("Real pero despreciable: la sigma del MLE con reparto fijo es 0-0.71 % menor que el CRB multinomial "
            "(sandwich; MC donutloc 40000 loc.: 0.9918 +- 0.005 en (5,-5), SBR 21). RMSE/CRB de los estudios queda "
            "sesgado a la baja < 1 %."),
  status="descartado"),
 dict(id="F151", script="scripts/findings/F151_crb_minflux_vs_donutloc.py",
  title="(vii) crb_minflux vs donutloc.fisher",
  legacy_location=LEG + ":583-885",
  evidence=("Metodos 1, 2 y 3 coinciden con donutloc dentro de 5.4e-4 (px=1) y 1.3e-4 (px=0.5): error O(px^2) de la "
            "diferencia finita. La suma de lambda es constante (dispersion 7e-16): el comentario de l.602-607 es correcto."),
  status="descartado"),
 dict(id="F152", script="scripts/findings/F152_sampling_and_background_checks.py",
  title="(v) fondo solo en ciclos sin senal y sin recorte TCSPC; muestreo en dos pasos; pliegue % dt",
  legacy_location=LEG + ":454-465, :558-573",
  evidence=("Los microtiempos del fondo son independientes de los ciclos: cuentas por ventana chi2 p=0.52 contra "
            "Mult(Nb, b/dt); solo absTimeBinary se ve afectado (valores hasta 5). Perdida selectiva por haz que "
            "impondria un TCSPC real: <= 3.6e-4 a la tasa de los estudios. Muestreo en dos pasos: ocupacion de ranuras "
            "igual al multinomial completo (t-test p = 0.04, 0.99, 0.44, 0.77; exacto por factorizacion). Pliegue: "
            "periodico, chi2 p=0.38 (F104)."),
  status="descartado"),
 dict(id="F153", script="scripts/findings/F153_index_space_consistency.py",
  title="spaceToIndex/indexToSpace vs la grilla de psf()",
  legacy_location=LEG + ":93-114, :181-185",
  evidence=("0/20 discrepancias entre el minimo de la dona y spaceToIndex (px 1 y 0.5); ida y vuelta dentro de px/2 con "
            "error medio < 0.005 nm. El truncado viejo sesgaba (-0.50, +0.50) nm con px=1: el fix de la autora es correcto."),
  status="descartado"),
 dict(id="F154", script="scripts/findings/F154_cw_minflux_branch.py",
  title="(ix) rama cw_minflux",
  legacy_location=LEG + ":389-419, :473-493, :531",
  evidence=("Con el haz recuperado del macrotiempo las cuentas siguen s q + (1-s)/K (chi2 p=0.74) y t_mask funciona. "
            "Limitacion: nMINFLUX no sirve para cw (88.5 % en la ventana 0) y no hay funcion que cuente por macrotiempo; "
            "M_p debe ser multiplo de cycle_time/dt o np.reshape falla con ValueError. Ningun script usa cw."),
  status="descartado"),
 dict(id="D-iv", script="",
  title="(iv) docstring de dt 'typically 25 ns'",
  legacy_location=LEG + ":337, :352, :404 ('6.5 ns' en vez de 6.25)",
  evidence=("No es un error: 25 ns era el setup de 40 MHz de Masullo (simulations_example.py:47). Los scripts de la "
            "autora pasan dt=50 (simulation_misalignment.py:54, make_fig_eficiencia.py:39). Solo actualizar el docstring."),
  status="descartado"),
 dict(id="D-ii-edges", script="",
  title="(ii) desigualdad estricta en los bordes de nMINFLUX",
  legacy_location=LEG + ":996",
  evidence=("Los microtiempos son continuos: la unica masa puntual es el 0.0 de los ciclos vacios (F102). Fuera de eso "
            "el borde abierto/cerrado no cambia ningun conteo con probabilidad 1."),
  status="descartado"),
 dict(id="D-vi-nan", script="",
  title="(vi) NaN -> -inf en pos_MINFLUX",
  legacy_location=LEG + ":1049-1050",
  evidence=("Correcto para los bordes rellenados con ceros (normPSF=0). El unico caso patologico es SBR=inf (F110)."),
  status="descartado"),
]


def _load(path):
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clean(x):
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def main(run=True):
    for lst in (FINDINGS, DISCARDED):
        for f in lst:
            f.setdefault("status", "candidate")
            if run and f["script"]:
                print("running", f["script"], flush=True)
                f["evidence_numbers"] = _clean(_load(os.path.join(ROOT, f["script"])).main())
    out = {"audit": "A - tools/tools_simulations.py", "worker": "W2", "round": 1,
           "criterion": CRITERION, "findings": FINDINGS, "discarded": DISCARDED}
    path = os.path.join(ROOT, "results", "findings_A.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print("wrote", path)


if __name__ == "__main__":
    main(run="--no-run" not in sys.argv)
