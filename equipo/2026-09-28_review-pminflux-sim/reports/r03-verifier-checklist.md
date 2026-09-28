# r03 — verificador: checklist SimuFLUX (21 ítems)

Revisé `results/simuflux_checklist.json` (21 entradas) y el resumen `reports/r03-simuflux-checklist.md`.
Los comparé con el texto de la checklist (`donut-beam-localization/docs/literature/C_insilico_vs_donutloc.md`
§5, l.161–214) y con `C_insilico_minflux.md`; esos dos archivos solo los leí.

Método:
- Las citas a hallazgos ya verificados (F1xx, F2xx, F290-D*) las comparé con el texto de `state.json`.
- Las ubicaciones del legado las abrí con `sed -n`.
- Los números nuevos (C01, C03, C07, C14, C16, C19) los rehíce con código propio en
  `work/verify/checklist/` antes de mirar los scripts del worker. Los scripts son `v_c01_c03_c07_c16.py`,
  `v_c03b.py`, `v_c03c.py`, `v_c14.py`, `v_c19.py` y `v_c19b.py`; cada uno tiene su `.out`.
- Recién después corrí los scripts del worker, para comparar (`worker_scripts_run.txt`).

## Resultado corto

- 17 ítems verificados sin reservas.
- **Ítem 3: refutado en un número.** La afirmación "el CRB cambia ≤ 1.6 % en |r| ≤ L/2" sale de
  muestrear 9–11 puntos. En el disco completo, con el propio método del worker, el cambio llega al
  5.5 %; con el modelo físico completo, al 8 %.
- **Ítem 8: el estado "falla" está mal asignado.** El ítem pregunta por los dwells y sus pesos, y
  esos están bien. La falla que se cita (F202, potencia de los haces) es otro problema y depende de
  un supuesto que no está confirmado.
- **Ítem 13: estado discutible** (queda unclear). Los números coinciden con F203, pero lo que el ítem pregunta
  literalmente sí lo cumple. Evaluó N = 100 y reporta el disco (77.4 nm).
- Hay detalles menores de texto y de ubicación en los ítems 1, 14, 16 y 19. Ninguno cambia el estado.

## Números nuevos, reproducidos por otro camino

**C01 (ítem 1). Verificado.**
- Modelo propio con integrales radiales (r ≤ 3000 nm).
- Pico del anillo: 1.000000 en r = 206.53 nm. SimuFLUX: 0.367879 = 1/e.
- Potencia (legado)/potencia (gaussiana) = 2.71828; SimuFLUX/gaussiana = 1.00000. El factor e está
  confirmado.
- Pedestal/amplitud de `fit_parameters.csv`: 0.1031/0.1291/0.1540/0.1277. Divididos por e dan
  0.0379/0.0475/0.0567/0.0470, o sea 3.79–5.67 veces el 0.01 de SimuFLUX. 0.01·e = 0.0272.
- En la grilla de 400 nm el máximo de la dona es 1.000000; el anillo entra solo por las diagonales.
- Detalles menores:
  - (a) El texto dice "zero_ratio 9.0–11.0 %", pero el mínimo es 8.66 % (NOTAS: 9.0/8.7/10.4/11.0).
    El "0.032–0.041" sí corresponde a 8.66 %.
  - (b) zero_ratio = min/max del mapa y el max incluye el pedestal. Dividirlo por e no da
    exactamente el zerooffset de SimuFLUX: con zr/(1−zr)/e da 0.035–0.046. El valor preciso es
    el pedestal/amplitud.
- `doughnut` en l.130–158, β = 2e en l.155: correcto.

**C03 (ítem 3). Refutado parcialmente.**
- Confirmo:
  - S(r)/S(0) = 1.0000–2.1055 en |r| ≤ L/2, y 4.65–4.69 en |r| = L.
  - S(0; 50)/S(0; 103.23) = 0.2461 (ley L²: 0.2346).
  - Mi CRB con SBR fija en (5,−5) da 0.8684; `ts.crb_minflux` da 0.8689.
- **No se sostiene** "CRB_fondo/CRB_fija = 0.984–0.999 en |r| ≤ L/2":
  - El script evalúa solo 9 puntos: 3 radios × 3 ángulos, más 2 puntos.
  - Con el mismo método (SBR local congelada en SBR₀·S(r)/S(0), N = Ns + Nb(r)), en una grilla densa
    (60 radios × 180 ángulos) el cociente va de 0.945 a 1.000. El mínimo está en r ≈ 46–47 nm en
    dirección a un haz periférico, donde el CRB con SBR fija es 2.2–2.3 nm.
  - Con el modelo físico completo el cociente va de 0.919 a 1.003:
    p_i = (I_i + β)/(S + Kβ) con β constante, así que el gradiente también incluye el cambio de la SBR.
    En el peor punto el CRB pasa de 2.370 a 2.178 nm, un 8 %.
  - Ese mínimo cae entre los puntos que eligió el worker: está a 47 nm, y la muestra tiene 25.8 y 51.6 nm.
- La conclusión cualitativa sigue en pie. En el r0 de los Monte Carlo (~7–10 nm del centro) el
  cociente es 0.99–1.00, así que no cambia los números de los estudios. Los mapas de CRB
  (`simulation_misalignment.py:340-359`) sí difieren hasta un 8 % cerca de los haces.
- Imparcialidad: el estado "falla" es discutible.
  - Con Ns y Nb fijos en una sola posición, `sim_exp` deposita un fondo uniforme en el tiempo,
    es decir constante por exposición. Ahí el modelo físico y el de SBR fija coinciden.
  - La SBR fija solo actúa en los mapas de CRB. La autora lo documenta en `crb_minflux`, l.602–606.
  - "Falla menor, de convención" es defendible. "Aplica-ok con matiz" también lo sería.

**C07 (ítem 7). Verificado.**
- Esfera uniforme proyectada, con peso √(a²−ρ²).
- Perla de 20 nm: llena el cero hasta 0.2546 % del pico del anillo (aprox. 4e·ln2·(2a²/5)/fwhm² =
  0.2549 %). Eso es 2.3–2.9 % del zero_ratio de 8.66–11.02 %.
- Perla de 100 nm: 6.16 %, o sea 55.9–71.1 % del zero_ratio.
- Sensibilidad al modelo: si la perla fuera un disco uniforme, 20 nm daría 0.318 %. La conclusión
  no cambia.
- Matiz: el llenado se refiere al pico del anillo y el zero_ratio al máximo del mapa (anillo +
  pedestal). La mezcla de referencias es de ~10 % y no cambia nada.

**C14 (ítem 14). Verificado.**
- MLE asintótico propio (Nelder–Mead sobre la entropía cruzada, SBR 21.05).
- En las 4 posiciones del worker: (5,−5), (−5,−8), (20,0) y (0,−30).
  - Datos 343.9 / estimador 360: máx 0.0437 nm.
  - Datos 360 / estimador 432: máx 0.147 nm.
  - Datos 399.3 / estimador 343.9: máx 0.1275 nm.
- Las cotas "≤" valen solo para esas 4 posiciones. En (14,14) obtengo 0.048, 0.163 y 0.140 nm. Siguen
  siendo despreciables (≤ 0.19 CRB).
- **Ubicación errónea:** `make_fig_eficiencia.py:69-71` es el `flush` de una clase Tee. El fwhm está
  en l.48 y l.82–86. `run_final.log:3` está en `documento/run_final.log`.
- No verifiqué la frase de la nota "≤ 0.13 de los ~5.4 nm de Realista ingenua": el 5.4 no está en
  NOTAS.

**C16 (ítem 16). Verificado.**
- `ts.crb_minflux` a SBR 21.05: 0.8863 nm en el píxel central; los vecinos dan 0.8847–0.8849.
- Mi Fisher continuo da 0.8858 en r = 0 y 0.8858 a 0.014 nm.
- SBR 1e12:
  - Legado, valor puntual: 0.8509.
  - Continuo en r = 0 exacto: 0.8505 con h = 1e−3 y 0.8509 con h = 1 nm.
  - Límite r→0: 0.7469/0.7492/0.7495/0.7496 para r = 1/0.1/0.01/0.001 nm.
- Detalle de texto: "el límite es 0.7496 (13.5 % menor)". En realidad el punto es 13.5 % *mayor*
  que el límite; el límite es 11.9 % menor que el punto.

**C19 (ítem 19). Verificado.**
- Simulación propia: telegrafo con arranque estacionario, pulsos en t = n·50 + k·12.5 ns durante
  10 ms, propagación lineal con Fisher y control no lineal por MLE asintótico.
- En (−5,−8), p-MINFLUX:
  - σ_fl = 6.46e−4 nm = 7.5e−4 σ_CRB con t_on = t_off = 100 µs.
  - 6.40e−3 nm = 7.4e−3 σ_CRB con 1 µs.
  - Worker: 7.6e−4 y 7.1e−3. Coinciden dentro del ruido de Monte Carlo.
- Exposiciones secuenciales de 4×100 µs **repetidas durante 10 ms (25 barridos)**:
  - 2.60 nm = 3.0 σ_CRB (worker: 2.67 nm / 3.1).
  - El cálculo no lineal da lo mismo: 2.89 contra 2.96 nm en (5,−5).
- **Precisión necesaria en el texto:** el JSON y el resumen dicen solo "4 x 100 µs". Con un único
  barrido de 400 µs el resultado es 23 nm = 26 σ_CRB. Hay que decir "25 barridos, 10 ms" (el
  docstring del script sí lo dice).

## Citas a hallazgos ya verificados

Todas coinciden con el texto de `state.json`:
- F290-D7: comparación justa.
- F152 y F290-D4: |z| ≤ 1.3 con 628 500 fotones.
- F104: latente con b < T/K.
- F105: 0–0.71 %, 0.993–1.000.
- F290-D1: 0/300 fallas; márgenes 3/55/76/105.
- F202: 10.6 nm; [0.111, 0.262, 0.314, 0.313] → [0.111, 0.207, 0.342, 0.340]; 1.379.
- F203: 12.1/13.2/50.0/81.9 nm; 0/1/50/87 %; 12–26 nm.
- F204: 1.63–1.88.
- F205: 0.43 contra 0.02 nm.
- F151: 4.4e−4 nm.
- F110: NaN con SBR = ∞.
- F107: 51.35 %.
- F101: ≤ 0.09–0.10 SE y ≤ 0.05 SE (MIX-STUDY y MIX-TRACKING en r01-verifier-A).

También coinciden con los archivos fuente:
- NOTAS_Simulacion.txt: 0.12/0.99; 62.76/23.45; 0.38/1.06; std 4.30/21.28; RMSE 46.96; 62.76/√2 = 44.4.
- eficiencia.log: N = 100, 1.89 y 4.138.
- build_doc §4.2: traza a 1e−9.

Nota: NOTAS usa r0 = (5,−5). El script actual usa R0_NM = (−5.07,−7.56).

## Ubicaciones en el legado (spot-check)

Correctas:
- `tools_simulations.py`:
  - l.130–158 y l.155
  - l.444–449 (λ en r0)
  - l.454–466 y l.473–491 (t_mask)
  - l.533–566
  - l.602–606
  - l.649–661
  - l.698
  - l.1002–1041 (l.1041 es la fórmula de p)
- `realistic_ebp.py`: l.55–89, 100–103, 152 y 181–185.
- `ebp.py`: l.545–549 y 578.
- `simulation_misalignment.py`:
  - l.18–23, 50–52, 66–75, 99–100, 124–126, 130–147, 161–175
  - l.187–192, 199–225 (sim_exp en l.216–217), 226–241, 263–281, 340–359
- `tools_analysis.py:434-483`: MLE sobre grilla, con log y argmax.
- `realistic_ebp.py:140`: el único least_squares.
- `build_doc.py`: l.481–491 y 684–691.
- ESTADO: l.20–27, 31 y 114–118.

Errónea: `make_fig_eficiencia.py:69-71` (ítem 14).

## Imparcialidad: estados demasiado generosos o demasiado duros

- **Ítem 8, demasiado duro o mal asignado.**
  - El ítem es sobre dwell/ctrDwellFactor/CFR. En la tabla de §4 de la misma nota, "pesos"
    quiere decir dwell: p_i ∝ w_i I_i. La potencia del haz entra en I_i.
  - En p-MINFLUX los dwells son iguales, y eso es correcto. La propia autora de donutloc descartó
    ese punto por la misma razón.
  - F202 (potencia) ya es un hallazgo DISENO aparte y está condicionado a un supuesto sin confirmar.
  - Recomiendo "aplica-ok" con una nota que remita a F202.
- **Ítem 13, duro en la lectura literal.**
  - Evaluó pocos fotones (N = 100) y reporta el disco (77.4 nm, impreso). La elección de raíz no aplica.
  - La falla que se cita (no reporta la fracción en el borde ni la dependencia con R) sí es real
    (F203) y va en el espíritu del ítem.
  - "Falla parcial" sería más justo que "falla".
- **Ítem 3, discutible** (ver arriba). "Falla menor, de convención" es aceptable, siempre que el
  número del CRB se corrija.
- **Ítem 6, algo generoso.** El ítem pregunta explícitamente por z, y no se consideró. El JSON ya
  dice "Parcial" en la nota; convendría que el estado dijera "aplica-ok (parcial)".
- **Ítem 7, justo.** La advertencia es correcta y con 20 nm no hace falta corregir. El tamaño de la
  perla sale de ESTADO:31 y no está confirmado.
- Los demás (2, 4, 5, 9–12, 14–21) me parecen justos.

## Lo que no pude resolver

- El "~5.4 nm de Realista ingenua" del ítem 14.
- El tamaño real de la perla (ítem 7).
- El supuesto de F202 (ítem 8).

```claims
[{"status": "verified", "text": "CHK-1 aplica-ok: doughnut (tools_simulations.py:130-158, beta=2e l.155) tiene pico del anillo 1.000000 en r=206.53 nm y potencia e=2.71828 veces la gaussiana; SimuFLUX 1/e. Pedestal/amplitud 0.1031/0.1291/0.1540/0.1277 -> /e 0.0379/0.0475/0.0567/0.0470 (3.79-5.67 veces 0.01; 0.01*e=0.0272). Menor: el rango de zero_ratio es 8.66-11.02 % (no 9.0-11.0), y zr/e es aproximado porque el max del mapa incluye el pedestal (zr/(1-zr)/e = 0.035-0.046)"},
 {"status": "verified", "text": "CHK-2 aplica-ok: honesta |b| 0.12 nm, RMSE/CRB 0.99, contra ingenua 62.76 nm/23.45 (NOTAS_Simulacion.txt, r0=(5,-5)); comparación justa según F290-D7 (coincide con state.json)"},
 {"status": "refuted", "text": "CHK-3 'CRB_fondo/CRB_fija = 0.984-0.999 en |r|<=L/2 (cambio <=1.6 %)' — sale de muestrear 9 puntos; en el disco denso, con el mismo método (SBR local congelada), da 0.945-1.000, y con el modelo físico de fondo constante (gradiente completo) 0.919-1.003 (peor punto r~47 nm hacia un haz: 2.370 -> 2.178 nm, 8 %). Sí verificados: S(r)/S(0) 1.000-2.106 (4.65-4.69 en |r|=L), S(0;50)/S(0;103.23) = 0.246 (L^2 0.235), CRB propio 0.8684 contra ts 0.8689. En el r0 de los MC el cociente es 0.99-1.00 (no cambia números de los estudios). El estado 'falla' es discutible: con Ns y Nb fijos en una sola posición el fondo de sim_exp ya es constante por exposición; solo afecta a los mapas de CRB"},
 {"status": "verified", "text": "CHK-4 aplica-ok: pos_MINFLUX usa la SBR verdadera y el fondo 1/K (l.1041); F152 y F290-D4 (|z|<=1.3, 628 500 fotones) y F104 latente con b<T/K coinciden con state.json"},
 {"status": "verified", "text": "CHK-5 no aplica: p_i = PSF_i/sum PSF sin modelo de detección (tools_simulations.py:444-449, 1036-1041)"},
 {"status": "verified", "text": "CHK-6 aplica-ok parcial: geom_exp separa la geometría de la forma (geometría sola |b| 0.38 nm, RMSE/CRB 1.06, contra forma 62.76 nm en NOTAS); solo 2D, sin z: el estado debería decir 'parcial' (algo generoso)"},
 {"status": "verified", "text": "CHK-7 aplica-ok: una perla uniforme de 20 nm llena el cero hasta 0.2546 % del pico del anillo (aprox. 0.2549 %) = 2.3-2.9 % del zero_ratio de 8.66-11.02 %; 100 nm: 6.16 % = 55.9-71.1 %; como disco sería 0.318 % (misma conclusión); tamaño de 20 nm según ESTADO:31, sin confirmar"},
 {"status": "refuted", "text": "CHK-8 estado 'falla' — el ítem pregunta por dwells y pesos de dwell (ctrDwellFactor/CFR), que en p-MINFLUX están bien (iguales, b=dt/K); la falla citada es F202 (potencia de los haces, que entra en I_i, no en w_i), ya clasificada DISENO y condicionada a un supuesto sin confirmar. Los números citados coinciden con F202 (10.6 nm; [0.111,0.262,0.314,0.313] -> [0.111,0.207,0.342,0.340]; 1.379). Debería ser aplica-ok con una nota que remita a F202"},
 {"status": "verified", "text": "CHK-9 aplica-ok: Ns y Nb fijos y declarados; F105 (0-0.71 %, 0.993-1.000) coincide con state.json"},
 {"status": "verified", "text": "CHK-10 no aplica: sin filtros; F290-D1 (0/300, márgenes 3/55/76/105) coincide"},
 {"status": "verified", "text": "CHK-11 no aplica: solo hay MLE sobre grilla (tools_simulations.py:1002-1110, tools_analysis.py:434-483 con log+argmax); least_squares solo en realistic_ebp.py:140 (ajuste de PSF)"},
 {"status": "verified", "text": "CHK-12 aplica-ok: reporta std, |b|, RMSE y RMSE/CRB (simulation_misalignment.py:226-241, 263-281); F205 (0.43 contra 0.02 nm) y F204 (SE real 1.63-1.88 veces el impreso) coinciden"},
 {"status": "unclear", "text": "CHK-13 estado 'falla' — los números coinciden con F203 (12.1/13.2/50.0/81.9 nm, 0/1/50/87 % en el borde; honesto con N=100: 12-26 nm) y con eficiencia.log (N=100: 1.89, |b| 4.138), pero lo que el ítem pregunta literalmente se cumple (evaluó N=100 y reporta el disco de 77.4 nm); 'falla parcial' sería más justo. Decide la persona"},
 {"status": "verified", "text": "CHK-14 aplica-ok: MLE asintótico propio en (5,-5),(-5,-8),(20,0),(0,-30): datos 343.9/est 360 máx 0.044 nm, 360/432 máx 0.147, 399.3/343.9 máx 0.1275; en (14,14) 0.048/0.163/0.140 (las cotas valen solo para las 4 posiciones). Ubicación errónea: make_fig_eficiencia.py:69-71 es un flush; el fwhm está en l.48 y 82-86. No verificado el '~5.4 nm de Realista ingenua'"},
 {"status": "verified", "text": "CHK-15 aplica-ok: RMSE = sqrt(0.5*(sx^2+sy^2+bx^2+by^2)) (simulation_misalignment.py:231-232), CRB sqrt(1/(dN))sqrt(E/F) (l.698) = sqrt(tr Sigma/2); build_doc 4.2, traza a 1e-9; F151 4.4e-4 nm; 62.76/sqrt2 = 44.4 < 46.96"},
 {"status": "verified", "text": "CHK-16 aplica-ok: ts.crb_minflux a SBR 21.05 da 0.8863 en r=0 contra 0.8847-0.8849 en los vecinos; Fisher continuo propio 0.8858. SBR 1e12: punto 0.8509 (legado) / 0.8505 (continuo, h=1e-3); límite r->0: 0.7496. Texto: el punto es 13.5 % mayor que el límite (el límite es 11.9 % menor, no 13.5 %)"},
 {"status": "verified", "text": "CHK-17 no aplica: patrón fijo y centrado, sin búsqueda ni iteraciones"},
 {"status": "verified", "text": "CHK-18 no aplica: una sola L (103.23), potencia y SBR por estudio"},
 {"status": "verified", "text": "CHK-19 aplica-ok: simulación propia en (-5,-8): p-MINFLUX sigma_fl = 6.46e-4 nm = 7.5e-4 sigma_CRB (100 us) y 7.4e-3 (1 us), contra 7.6e-4/7.1e-3 del worker; secuencial 4x100 us repetido 25 veces (10 ms) 2.60 nm = 3.0 sigma_CRB (worker 2.67/3.1; el control no lineal coincide). Precisión: con un único barrido de 400 us daría 23 nm = 26 sigma_CRB; el JSON debería decir '25 barridos / 10 ms'. F107 (51.35 %) coincide"},
 {"status": "verified", "text": "CHK-20 no aplica: un solo emisor con Ns fijo (sim_exp); sin blanqueo ni vecinos"},
 {"status": "verified", "text": "CHK-21 no aplica: emisor estático y sin tracking; el F101 citado (<=0.09-0.10 SE a 0.0105/ciclo, <=0.05 SE en tracking) coincide con MIX-STUDY y MIX-TRACKING, verificados en r01"}]
```
