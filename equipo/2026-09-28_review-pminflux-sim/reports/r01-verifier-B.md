# r01 — Verificador B: auditoría B de Worker 3 (F201–F206, F290 D1–D8)

## Qué hice
- Leí `state.json` (ronda 0, sin afirmaciones vivas), `inbox.jsonl`, `r01-pi.md` (criterio de clases), `r01-worker-3.md`,
  `results/findings_B.json`, el código legado del alcance B, `ESTADO_Y_PLAN_REALISMO_PSF.md`, `NOTAS*`, los logs y
  `C_pminflux_practice.md` §5.
- Escribí mi propio código en `work/verify/B/`. No usé los scripts del worker hasta tener mis números. Después solo abrí
  `work/w3/F203_out.json` y dos líneas de `F203_*.py` para explicar una diferencia.
  - `v_common.py`: dona propia, reconstrucción propia de `donut_2d`, matriz de mezcla propia (suma de exponenciales plegada),
    argmax asintótico con conteos esperados más refinamiento subpíxel, y un Fisher propio.
  - `v_F201_asym.py`: cálculo asintótico, sin Monte Carlo.
  - `v_F201_mc.py`: el pipeline legado `sim_exp` + `nMINFLUX` + `pos_MINFLUX`, con una semilla propia (777) y con la del worker.
  - `v_F201_eff.py`, `v_F202.py`, `v_F203.py`, `v_F204.py`, `v_F205.py`, `v_F290.py`.
  - Las salidas quedan en `v_*.json`.
- **Datos:** `C:\Data\psf\20260820` no existe; lo confirmé (solo están 20260703/0707/0924 y una 0925 vacía).
  - Los EBP ideal, geom_exp (posiciones de `run_final.log`, fwhm 343.9) y realistic_fit (desde `fit_parameters.csv`) se
    reconstruyen de forma exacta.
  - Lo compruebo reproduciendo **al 4.º decimal** toda la escalera de `comparison_metrics.csv` hasta la etapa "background"
    (CRB 0.8389/0.8382/1.7599/2.4276/2.3483; RMSE honesto 0.9122…2.3923; RMSE del estimador geométrico 0.9883…9.6561),
    con la secuencia RNG 20260901 de ella y sus propias funciones `monte_carlo`/`stripped_params`.
  - El sustituto 20260703 está rotulado como tal en `data_note` de `findings_B.json` y en los scripts.
  - **La sustitución no invalida ninguna conclusión cualitativa.** F201, F202 y F205 no usan PSF medidas. F203 y F204 usan el
    sustituto solo para mostrar un mecanismo (borde del disco, colas pesadas), y ese mecanismo también aparece con
    realistic_fit, que es exacto.
  - Los números "Experimental" (18.35 / 62.76 / 1.89) no se reprodujeron, y el worker lo declara.

## Resultados por hallazgo

### F201 — fuga apagada en los estudios. VERIFICADO (números); clase: recomiendo DISENO
- **Pipeline legado, semilla propia 777, 1000 muestras**, en el píxel (−5,−8):

  | caso | C0 \|b\| | C3 \|b\| | C0 RMSE | C3 RMSE | RMSE/CRB |
  |---|---|---|---|---|---|
  | Ideal | 0.06 | 2.96 | 0.92 | 2.36 | 1.07 → 2.73 (CRB 0.864) |
  | Realista honesta | 0.13 | 1.88 | 2.45 | 2.94 | 1.04 → 1.25 |
  | Realista ingenua | 5.4 | 10.2 | 13.0 | 24.0 | — |

  - Diferencia pareada del ideal, C3 − C0: (−0.95 ± 0.02, −2.76 ± 0.02) nm. El worker da (−1.00, −2.70), a unos 2σ.
  - **Con la semilla 20260825 mi script reproduce exactamente sus números:** 0.11 → 2.98, RMSE 0.92 → 2.38, 0.18 → 1.94,
    5.50 → 10.85, 12.96 → 24.83. Hubo 0 fallos.
- **Asintótico independiente** (C propia: C_ii = 0.9092, del haz anterior 0.0467, de dos antes 0.0024; conteos esperados; argmax subpíxel):

  | caso | sesgo C3 | \|b\| C3 |
  |---|---|---|
  | ideal | (−1.02, −2.67) | 2.85 |
  | geom honesta | — | 2.77 |
  | geom ingenua | — | 2.47 |
  | realista honesta | — | 1.79 |

  - Coincide con el MC a 0.1–0.2 nm en los casos honestos, como afirma el worker.
  - Descomposición en el ideal: la ventana sola (C1) da 0.30 nm y la fuga sola (C2) 3.03 nm. Coincide con ≈0.25 / ≈3.1.
  - En el ingenuo realista el asintótico (20 nm en C0) **no** describe el MC (5.4 nm). La verosimilitud es casi plana o multimodal.
    El worker solo afirma la coincidencia para los honestos, así que eso no lo refuta.
- **Eficiencia** (ideal, SBR 9, r0 = (5,−5), 400 muestras, semilla propia):

  | N | C0 → C3 | worker |
  |---|---|---|
  | 100 | 0.97 → 1.19 | 1.23 |
  | 1600 | 0.98 → 1.53 | 1.65 |

  La tendencia es la misma; las diferencias de ~0.1 son compatibles con el ruido MC entre semillas.
- **Matiz que falta:** el 2.75 divide por el CRB **sin fuga** (0.864). El CRB de un estimador que conoce la fuga es 0.945 nm.
  Con él el cociente es ≈2.5. El sesgo sigue dominando, pero hay que decirlo.
- **Clase.** Con el criterio del PI, "parámetro por defecto, supuesto no declarado" es DISENO. El simulador modela bien la fuga;
  el modelo erróneo del estimador ya es F104 (CONCEPTUAL, W2). Si F201 también se clasifica CONCEPTUAL, se cuenta dos veces.
- **Justicia:** hay que corregir "sin declararlo".
  - Ella anota como extensión pendiente "incorporar drift, blinking, IRF y **lifetime medidos**" en `ESTADO_Y_PLAN_REALISMO_PSF.md:115-117`.
  - Lo cierto es que ni el .docx ni los scripts lo declaran; lo busqué en el texto del docx y no hay "vida"/"lifetime"/"Tlife".
  - El hallazgo tiene que acreditarle ese pendiente.
- Ubicaciones verificadas: `simulation_misalignment.py:55,99-100`, `make_fig_eficiencia.py:40,76-77`, `simulations_example.py:51,134-136`
  (Masullo, dt = 25, l.47).
- La cita de la tesis de Masullo (p. 127) solo la pude contrastar con la fuente secundaria (C_pminflux_practice P5), que dice lo mismo.

### F202 — realistic_ebp descarta intensity_scale. VERIFICADO (números); clase IMPLEMENTACION REFUTADA → DISENO
- Código: `realistic_ebp.py:100-103` (target = image/scale), `:152` (se guarda y no se usa) y `:181-185`. Confirmado.
- Las escalas 21.02/16.65/22.96/22.86 dan un máximo/mínimo de 1.379.
- p_señal en el emisor pasa de [0.1109, 0.2622, 0.3136, 0.3133] a [0.1108, 0.2073, 0.3419, 0.3400]: −20.9 % y +9.0/+8.5 %.
- CRB legado: 2.348 → 2.333 nm.
- Estimador realista sin potencias sobre datos con potencias:
  - asintótico (−10.59, −0.44) = 10.60 nm;
  - MC propio 10.65 nm, RMSE 8.1;
  - estimador geométrico 8.5 nm en MC (10.6 asintótico), contra 8.8 del worker.
- **El supuesto no está en el hallazgo.** Que el máximo de cada `.npy` refleje la potencia relativa del haz solo aparece en
  "lo que no pude resolver" del reporte. Hay que ponerlo en `scenario`/`impact` de F202.
  - Lo apoyo con datos: el orden de los máximos se repite en las tres calibraciones disponibles. El haz 2 es siempre el más
    débil y el 3 el más fuerte (20260703: 245/205/291/253; 20260707: 6.4/4.8/6.8/5.3; 20260924: 21.2/18.4/26.6/19.7).
  - Eso indica algo sistemático (potencia × detección), no ruido. Sigue siendo un supuesto.
- **Hay una parte que no depende del supuesto:** la etapa "experimental" de la escalera usa los `.npy` crudos, con su escala, y las
  demás etapas no. El salto 9.66 → 35.6 nm mezcla las dos cosas en cualquier caso.
- **Clase.** El docstring (`realistic_ebp.py:5-6`) declara "unidades relativas al máximo de cada PSF": el código hace lo que dice.
  Con el criterio del PI no es IMPLEMENTACION; es DISENO (supuesto con consecuencias no declaradas).
- **Justicia:** ella misma recomienda "permitir distinta potencia entre haces" (`ESTADO…md:116`), y C_pminflux_practice P4 ya lo
  sugiere. Hay que acreditarlo. El aporte nuevo es cuantificarlo y mostrar que contamina la escalera.

### F203 — radio de búsqueda. VERIFICADO con una corrección de texto
- MC multinomial propio, 1000 muestras, R ∈ {0.5, 0.75, 1, 1.25}·L:

  | caso | RMSE | \|b\| | fracción en el borde |
  |---|---|---|---|
  | realista ingenua | 12.1 / 13.2 / 50.0 / 81.9 | — | 0 / 0.01 / 0.50 / 0.87 |
  | sustituto ingenuo | — | 48.3 / 72.4 / 96.3 / 118.5 | 1.00 / 1.00 / 1.00 / **0.72** |
  | realista honesto, N = 100 | 12.1 / 15.0 / 19.8 / 26.1 | — | — |
  | sustituto honesto, N = 100 | 14.1 / 19.6 / 29.4 / 39.6 | — | — |

  - Del realista ingenuo coinciden con el worker tanto el RMSE (12.1/13.9/51.0/82.1) como la fracción en el borde.
  - En el realista honesto con N = 100 el worker da 11.4/14.1/18.3/23.4: la misma tendencia, a ~10 %.
- **Corrección:** "el 100 % queda en el borde para los cuatro R" es falso para R = 1.25. Sus propios datos (`w3/F203_out.json`) dan
  0.71 y los míos 0.72. Hay que decir "100 % para R ≤ 1.0·L".
- **Matiz:** con el R de ella (0.75) y el EBP realista, el ingenuo tiene solo un 1 % en el borde. "Lo fija R" vale para el
  experimental/sustituto y para R ≥ 1.
- La aritmética de la métrica mezclada está verificada: √(0.5·(4.30² + 21.28² + 62.76²)) = 46.96 < |b| = 62.76.
- Ubicaciones verificadas. Clase DISENO: de acuerdo.

### F204 — SE con supuesto normal. VERIFICADO
- 400 réplicas × 250 muestras (N = 100, SBR 9, r0 = (5,−5)).
- SE real / SE impreso de RMSE/CRB:
  - ideal 0.77 (el worker da 0.74);
  - realista 1.88 (1.86);
  - sustituto 1.63 (1.55).
- SE de std_x: 2.20 y 1.69 (el worker da 2.10 y 1.62).
- Exceso de curtosis: 6.6/4.6 en el realista y 3.0/3.1 en el sustituto, contra 0.17/0.06 en el ideal.
- Piso de |b| en el ideal: 0.357 nm (≈ √(π/2)·σ/√n = 0.33).
- Lo de "1.89 ± 0.13–0.15" es una extrapolación desde EBP sustitutos. Hay que rotularlo como estimación.
- No verifiqué por separado la no monotonía entre N = 200 y 400 con las PSF reales: no están.
- Clase DISENO: de acuerdo.

### F205 — referencia R0_NM contra el píxel. VERIFICADO, con un impacto extra
- R0 (−5.07, −7.56) va al píxel (208,195), que es (−5,−8). El desplazamiento es (0.07, −0.44), con norma 0.4455.
- MC propio con 1e5 muestras:

  | caso | \|b\| contra R0 | \|b\| contra el píxel |
  |---|---|---|
  | ideal honesto | 0.426 | 0.021 |
  | geom honesta | 0.426 | 0.020 |
  | geom ingenua | 0.312 | 0.674 |
  | realista honesta | 0.421 | 0.044 |

  - El worker da 0.437/0.012 para el ideal y 0.302/0.663 para la geométrica ingenua.
  - La diferencia vectorial es (−0.35, 0.56).
  - **La inversión del orden honesto/ingenuo está confirmada.** Con 1000 muestras el SE de |b| es ≈0.04: el artefacto está a ~10σ.
- **Impacto que falta:** su escalera también calcula el **RMSE** contra R0_NM (`analyze_realistic_psf.py:88`). En el ideal el RMSE
  pasa de 0.912 a 0.960 nm por esta causa. Su RMSE/CRB honesto de ≈1.09 en la etapa de geometría sería ≈1.02 contra el píxel.
- **Clase:** IMPLEMENTACION es aceptable (el sesgo reportado no mide lo que pretende). También es admisible DISENO, porque el
  redondeo es F106 del núcleo. Autoría: ella (R0_NM no entero). run_final.log no está afectado.

### F206 — el documento no es reproducible desde la cadena. VERIFICADO (estático)
- Confirmé las cuatro discrepancias:
  - 1000 muestras contra 300;
  - r0 (−5.07, −7.56) contra (5,−5);
  - 2000/95 contra 90/10 (el CRB 4.28 corresponde a N = 100);
  - `INCLUDE_REALISTIC_FIT = True` sin filas "Realista".
- Encontré una quinta: `CASES` incluye "Experimental ingenua 1/2", que tampoco están en el log.
- Parámetros escritos a mano en `build_doc.py:535-537` y `:812-821`.
- Justicia: ella lo advierte en `ESTADO…md:64-67`, y eso está acreditado. Clase DISENO: de acuerdo.

### F290 (descartes)
| id | resultado | detalle |
|---|---|---|
| D1 | VERIFICADO | 0/300 fallos. Márgenes mínimos de ciclos: 3 / 55 / 76 / 105 para Ns = 90/1440/2000/2880. El "margen ≥ 77" del reporte es falso para N bajo (con Ns = 90 el margen es de 2–3), pero la tasa de fallos es 0 igual. |
| D2 | VERIFICADO | Mi dona con la convención de indexToSpace coincide con `ebp_ideal` a 3e-16, y argmin = pos redondeada. |
| D3 | VERIFICADO | Por lectura (`simulations_example.py:182-183`): los NaN van por columnas completas. |
| D4 | VERIFICADO, sin la atribución | 628 500 fotones, z = (−1.27, 0.73, −0.90, 0.61). No reproduzco el +2.6σ del haz 3: el "+0.6 % = F101" parece una fluctuación. La conclusión (equivalencia) se mantiene. |
| D5 | VERIFICADO | Con 20260703, argmin = pos_nm en los 4 haces. |
| D6 | VERIFICADO | Por lectura (`ebp.py:545` contra `:578`). |
| D7 | VERIFICADO | Por lectura (`simulation_misalignment.py:250-256`). |
| D8 | VERIFICADO | max\|p_crb − p_MC\| en r0 = 4e-4, y el CRB de Fisher propio da 0.864 = el legado. |

## Lo que queda abierto
- La clase de F201 y F202 la decide el PI. Mi recomendación para ambos es DISENO.
- El supuesto de potencias de F202 se confirma con la autora.
- Los números "Experimental" exactos requieren las PSF 20260820.

```claims
[{"status":"verified","text":"F201: con el pipeline legado (sim_exp+nMINFLUX+pos_MINFLUX, Ns=2000, Nb=95, emisor en el píxel (-5,-8), R=0.75·L_eff, 1000 muestras), pasar de (Tlife=0.001, b=12.5) a (τ=4.21 ns, [0,10.1] ns) lleva el ideal honesto de |b| 0.06–0.11 a 2.96–2.98 nm y RMSE/CRB(sin fuga, 0.864) de 1.07 a 2.73–2.75; se reproduce exactamente con la semilla 20260825 y dentro del ruido con la semilla 777; realista honesta 0.13–0.18 -> 1.88–1.94 nm; realista ingenua 5.4–5.5 -> 10.2–10.9 nm (RMSE 13.0 -> 24–25)"},
 {"status":"verified","text":"F201: el sesgo asintótico independiente (C propia: C_ii=0.9092, del haz anterior 0.0467; conteos esperados; argmax subpíxel) da (-1.02,-2.67) nm, |b|=2.85, en el ideal C3 y coincide con el MC a 0.1–0.2 nm en los casos honestos; ventana sola 0.30 nm, fuga sola 3.03 nm (domina la fuga)"},
 {"status":"verified","text":"F201: barrido de eficiencia (ideal, SBR 9): RMSE/CRB sube con la fuga, 0.97->1.19 con N=100 y 0.98->1.53 con N=1600 (semilla propia); los 1.23/1.65 del worker son compatibles dentro del ruido MC"},
 {"status":"unclear","text":"F201: la clase CONCEPTUAL — con el criterio del PI (parámetro o supuesto no declarado) corresponde DISENO, y lo conceptual ya es F104. Además hay que acreditar que la autora anotó 'IRF y lifetime medidos' como pendiente (ESTADO_Y_PLAN_REALISMO_PSF.md:115-117) y que el 2.75 es respecto del CRB sin fuga (el CRB con fuga es 0.945 nm, cociente ≈2.5). Decide el PI"},
 {"status":"verified","text":"F202: realistic_ebp normaliza cada PSF por su máximo y no usa intensity_scale (realistic_ebp.py:100-103,152,181-185); escalas con máx/mín 1.379; p_señal [0.111,0.262,0.314,0.313]->[0.111,0.207,0.342,0.340]; CRB 2.348->2.333 nm; el estimador realista sin potencias sobre datos con potencias queda sesgado 10.6 nm (asintótico 10.60, MC 10.65); la escalera de comparison_metrics.csv se reproduce al 4.º decimal"},
 {"status":"refuted","text":"F202 clase IMPLEMENTACION — el docstring (realistic_ebp.py:5-6) declara unidades relativas al máximo de cada PSF, así que el código hace lo que dice; con el criterio del PI es DISENO. Además el supuesto 'el máximo del .npy = potencia del haz' tiene que figurar en el hallazgo (hoy solo está en el reporte; lo apoya que el orden de los máximos se repite en 3 calibraciones), y hay que acreditar que ella ya recomendó 'permitir distinta potencia entre haces' (ESTADO…md:116)"},
 {"status":"verified","text":"F203: el RMSE y el |b| de los ingenuos dependen de R: realista ingenua RMSE 12.1/13.2/50.0/81.9 nm con 0/1/50/87 % en el borde para R=0.5/0.75/1/1.25·L; sustituto 20260703 ingenuo |b| 48/72/96/118 ≈ R−|r0|; el honesto con N=100 también depende de R (realista 12–26 nm); en el log |b|=62.76 > RMSE=46.96 porque el RMSE es por eje"},
 {"status":"refuted","text":"F203: 'el 100 % de las estimaciones ingenuas (sustituto) queda en el borde para los cuatro R' — con R=1.25·L es el 71–72 % (sus propios datos en w3/F203_out.json y los míos); vale para R ≤ 1.0·L. Con el R de ella (0.75) y el EBP realista, el ingenuo solo tiene un 1 % en el borde"},
 {"status":"verified","text":"F204: con N=100 (SBR 9, 250 muestras), SE real/SE impreso de RMSE/CRB = 1.88 (realistic_fit), 1.63 (sustituto 20260703) y 0.77 (ideal); exceso de curtosis 6.6/4.6 (realista) contra 0.2/0.1 (ideal); piso de ruido de |b| en el ideal ≈0.36 nm con n=250. El '±0.13–0.15' para su 1.89 es una extrapolación desde sustitutos"},
 {"status":"verified","text":"F205: R0_NM=(-5.07,-7.56) se simula en el píxel (-5,-8) (desplazamiento 0.4455 nm); el |b| honesto ideal es 0.43 contra R0 y 0.02 contra el píxel (1e5 muestras); la geométrica ingenua es 0.31 contra R0 y 0.67 contra el píxel, así que el orden honesto/ingenuo se invierte; la diferencia vectorial (-0.35,0.56) no depende de la referencia. Impacto extra: el RMSE de la escalera también se calcula contra R0 (analyze_realistic_psf.py:88) y pasa de 0.912 a 0.960 nm en el ideal"},
 {"status":"verified","text":"F206: la cadena run_and_save -> run_final.log -> build_doc no reproduce el documento: 1000 vs 300 muestras, r0 (-5.07,-7.56) vs (5,-5), Ns/Nb 2000/95 vs 90/10, casos Realista (y 'Experimental ingenua 1/2') ausentes del log, parámetros escritos a mano en build_doc.py:535-537 y 812-821; la autora ya lo advierte en ESTADO…md:64-67"},
 {"status":"verified","text":"F290-D1: sim_exp no falla en las configuraciones de los estudios (0/300 con Ns=2000); el margen mínimo de ciclos es 3/55/76/105 para Ns=90/1440/2000/2880 (el 'margen ≥77' del reporte solo vale para Ns ≥ 2000)"},
 {"status":"verified","text":"F290-D2: la convención de ejes de psf()/Grid/ebp es consistente (mi dona coincide con ebp_ideal a 3e-16; argmin = posición redondeada)"},
 {"status":"verified","text":"F290-D3: el reshape tras quitar NaN en simulations_example.py:182-183 conserva los pares (x,y)"},
 {"status":"verified","text":"F290-D4: con Tlife=0.001 y b=dt/K, las fracciones por ventana de sim_exp coinciden con el modelo 1/K (628 500 fotones, |z| ≤ 1.3). No reproduzco el +2.6σ del haz 3 que el worker atribuye a F101; parece una fluctuación"},
 {"status":"verified","text":"F290-D5: el centrado entero de ebp_experimental deja argmin = pos_nm en los 4 haces (PSF 20260703)"},
 {"status":"verified","text":"F290-D6: zero_ratio usa min/max del mapa 2D mientras el docstring dice 'del perfil' (ebp.py:545 vs 578); es solo una inconsistencia del docstring"},
 {"status":"verified","text":"F290-D7: la comparación honesta/ingenua es justa (una semilla antes de todos los casos, mismo r0, SBR y R_SEARCH_NM; simulation_misalignment.py:250-256)"},
 {"status":"verified","text":"F290-D8: el CRB con N=Ns+Nb es consistente con el MC de N fijo: max|p_crb − p_MC| en r0 = 4e-4 y el Fisher propio da 0.864 nm, igual que el legado"},
 {"status":"verified","text":"Sustitución de datos: C:\\Data\\psf\\20260820 no existe; los EBP ideal/geom_exp/realistic_fit se reconstruyen de forma exacta (la escalera se reproduce al 4.º decimal), el sustituto 20260703 está rotulado en findings_B.json, y ninguna conclusión cualitativa de F201–F206 depende de él; los números 'Experimental' exactos (18.35/62.76/1.89) no se reprodujeron, y eso está declarado"}]
```
