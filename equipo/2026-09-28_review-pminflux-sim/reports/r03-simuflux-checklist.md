# r03 — worker: checklist SimuFLUX sobre las simulaciones legado

Pedido de la autora: auditar `legacy/p-minflux-main` contra los 21 ítems de errores frecuentes
de simulaciones MINFLUX que salen de SimuFLUX (Marin & Ries), según la lista de
`donut-beam-localization/docs/literature/C_insilico_vs_donutloc.md` §5. Esa carpeta solo se leyó:
no se editó ni se copió nada ahí.

- Entregable: `results/simuflux_checklist.json`, una lista de 21 objetos
  `{item, pregunta, estado, evidencia, legacy_location, ref_finding_or_script, numero, nota}`.
- Scripts nuevos en `scripts/findings/`. Cada uno tarda menos de 6 s:
  - `C01_donut_normalization_factor_e.py`
  - `C03_fixed_sbr_vs_constant_background.py`
  - `C07_bead_fills_zero.py`
  - `C14_estimator_fwhm_mismatch.py`
  - `C16_crb_at_exact_zero.py`
  - `C19_blinking_vs_pattern_period.py`
- No toqué `src/`, `legacy/`, `README.md`, `report/`, los scripts del reporte ni `tests/test_acceptance.py`.

## Resultado

- **aplica-ok (11):** 1, 2, 4, 6, 7, 9, 12, 14, 15, 16, 19
- **falla (3):** 3, 8, 13
- **no aplica (7):** 5, 10, 11, 17, 18, 20, 21

Lo que ella hizo bien, que es la mayor parte:
- La normalización está explícita y el cero se refiere al pico del anillo, igual que Balzarotti.
- La comparación honesta/ingenua es exactamente el diseño que pide [MR].
- La escalera `geom_exp`/`exp` separa la geometría de la forma de la dona.
- El fwhm está ajustado a las donas medidas y es el mismo en los datos y en el estimador.
- La convención ×1.2 está documentada.
- El RMSE lleva la raíz, promedia por eje y coincide con la convención del CRB (lo validó ella misma en el documento, §4.2).
- Advirtió el efecto del tamaño de la perla.

Las tres fallas:
- **Ítem 3.** La SBR es fija en toda la grilla, lo que implica un fondo que depende de la posición. Con un fondo constante por exposición, S(r)/S(0) va de 1.000 a 2.106 dentro de |r| ≤ L/2. A SBR 21 el CRB cambia ≤ 1.6 % (cociente 0.984–0.999), así que no mueve números. La SBR cae ~L² al achicar L, pero ella no barre L.
- **Ítem 8.** Los dwells de p-MINFLUX son correctos, pero el peso por potencia del haz se pierde en `realistic_ebp` (F202: sesgo 10.6 nm, bajo el supuesto de F202).
- **Ítem 13.** Evaluó el caso de pocos fotones y declaró el radio R, pero no reporta la fracción de estimaciones en el borde ni la dependencia con R. Según F203, el RMSE va de 12.1 a 81.9 nm para R = 0.5–1.25 L.

Números nuevos:
- **Ítem 1 (C01).** El pico del anillo vale 1 en el legado y 1/e en SimuFLUX (factor e = 2.7183). El pedestal/pico del anillo es 0.103–0.154, que equivale a un zerooffset de SimuFLUX de 0.038–0.057 (3.8–5.7 veces el 0.01 de SI Fig. 5). El docstring de `doughnut` no advierte esa diferencia de prefactor.
- **Ítem 7 (C07).** Una perla de 20 nm llena el cero hasta 0.255 % del pico del anillo, o sea 2.3–2.9 % del cero medido. La perla no explica el 9–11 %.
- **Ítem 14 (C14).** Un desajuste de fwhm casi no afecta al MLE con L ≈ 103 nm. El default 360 contra 343.9 da ≤ 0.044 nm; confundir la convención (360/432) da ≤ 0.147 nm; el ajuste 2D (399.3) contra el radial (343.9) da ≤ 0.127 nm.
- **Ítem 16 (C16).** Con SBR 21 el CRB es continuo en r = 0 (0.8863 contra 0.8848 nm a 1 nm). Solo con SBR 1e12 el punto (0.851) se separa del límite (0.750).
- **Ítem 19 (C19).** En p-MINFLUX el barrido de 50 ns hace despreciable el parpadeo: σ_fl/σ_CRB = 7.6e-4 con t_on = t_off = 100 µs, contra 3.1 con exposiciones secuenciales 4×100 µs. El riesgo real es F107, porque `t_mask` se ignora.

## Puntos abiertos y límites

- El ítem 8 depende del supuesto de F202 (el máximo de cada .npy refleja la potencia del haz), sin confirmar.
- Ítem 6: aplica-ok, pero solo en 2D; no hay dependencia con z.
- Ítem 7: supone una dona 2D sin z y una perla uniforme de 20 nm (el tamaño sale de ESTADO_Y_PLAN).
- Ítem 19: solo propaga el desbalance de exposición entre haces, linealmente.
- Ítem 21: lo marqué "no aplica" (sin movimiento ni tracking). El tiempo muerto del detector y la regla TCSPC son F101, que ya está verificado como despreciable.
- Durante el trabajo maté con `taskkill /IM python.exe` un script mío colgado (C19, primera versión lenta). Solo terminó un proceso (PID 11352), que coincide con el fin de mi tarea en segundo plano. Aun así, si el otro worker vio morir un proceso de Python, fue esto.

```claims
[{"status": "unclear", "text": "Ítem 1 aplica-ok: doughnut (tools_simulations.py:130-158) tiene pico del anillo 1.000000 y potencia e = 2.7183 veces la gaussiana; SimuFLUX 1/e. El pedestal/pico del anillo de fit_parameters.csv es 0.103/0.129/0.154/0.128, que equivale a un zerooffset de SimuFLUX 0.038/0.048/0.057/0.047; zero_ratio 9.0-11.0 % -> 0.032-0.041 (C01)"},
 {"status": "unclear", "text": "Ítem 2 aplica-ok: en los casos honestos el pedestal está en los datos y en el estimador; honesta |b| 0.12 nm y RMSE/CRB 0.99 vs ingenua |b| 62.76 nm y RMSE/CRB 23.45 (NOTAS_Simulacion.txt; comparación justa, F290-D7)"},
 {"status": "unclear", "text": "Ítem 3 falla (menor): SBR fija en toda la grilla (crb_minflux l.653, pos_MINFLUX l.1041). Con fondo constante por exposición, S(r)/S(0) = 1.000-2.106 en |r| <= L/2 y CRB_fondo/CRB_fija = 0.984-0.999 a SBR 21; S(0;L=50)/S(0;103.23) = 0.246; el CRB propio reproduce ts.crb_minflux (0.8684 vs 0.8689 nm) (C03)"},
 {"status": "unclear", "text": "Ítem 4 aplica-ok: pos_MINFLUX usa la SBR verdadera y el fondo 1/K coincide con sim_exp cuando b = dt/K (F152, F290-D4 |z| <= 1.3); SBR oráculo; F104 queda latente con b < T/K"},
 {"status": "unclear", "text": "Ítem 5 no aplica: la detección no se modela (p_i = PSF_i/sum PSF), lo que equivale a una detección uniforme y común a todos los haces"},
 {"status": "unclear", "text": "Ítem 6 aplica-ok (solo 2D): geom_exp vs exp separa la geometría de la forma; geometría sola |b| 0.38 nm vs forma 62.76 nm (NOTAS_Simulacion.txt); no se considera z"},
 {"status": "unclear", "text": "Ítem 7 aplica-ok: una perla de 20 nm llena el cero hasta 0.255 % del pico del anillo (analítico 0.255 %) = 2.3-2.9 % del zero_ratio medido 8.7-11.0 %; con 100 nm, 56-71 % (C07)"},
 {"status": "unclear", "text": "Ítem 8 falla (condicionada al supuesto de F202): realistic_ebp descarta intensity_scale (realistic_ebp.py:100-103,152) y el estimador realista queda sesgado 10.6 nm; los dwells de p-MINFLUX (un pulso por haz y por ciclo) son correctos"},
 {"status": "unclear", "text": "Ítem 9 aplica-ok: Ns y Nb fijos y declarados; sigma/CRB multinomial = 0.993-1.000 (F105)"},
 {"status": "unclear", "text": "Ítem 10 no aplica: no hay filtros ni esquema iterativo; fallas de sim_exp 0/300 con Ns = 2000 (F290-D1)"},
 {"status": "unclear", "text": "Ítem 11 no aplica: solo hay un MLE sobre grilla (pos_MINFLUX l.1002-1110, tools_analysis.pos_minflux l.434); no hay ningún estimador linealizado"},
 {"status": "unclear", "text": "Ítem 12 aplica-ok: reporta std, |sesgo|, RMSE y RMSE/CRB con el MLE usado (simulation_misalignment.py:226-281); defectos ya verificados: F205 (referencia del sesgo, 0.43 vs 0.02 nm) y F204 (SE)"},
 {"status": "unclear", "text": "Ítem 13 falla: no reporta la fracción en el borde ni la dependencia con R; Realista ingenua RMSE 12.1/13.2/50.0/81.9 nm para R = 0.5/0.75/1.0/1.25 L (F203); sí evaluó N = 100 (eficiencia.log: RMSE/CRB 1.89, |b| 4.14 nm)"},
 {"status": "unclear", "text": "Ítem 14 aplica-ok: DONUT_FWHM ajustado (343.9 nm) y usado igual en los datos y en el estimador (desajuste 0); sesgo asintótico si no: 343.9/360 <= 0.044 nm, 360/432 <= 0.147 nm, 399.3/343.9 <= 0.127 nm (C14)"},
 {"status": "unclear", "text": "Ítem 15 aplica-ok: RMSE = sqrt(0.5*(sx^2+sy^2+bx^2+by^2)) y CRB = sqrt(tr Sigma/2) (l.698, build_doc §4.2); crb_minflux vs Fisher continuo <= 4.4e-4 nm (F151); solo la tabla mezcla |b| 2D con RMSE por eje (F203)"},
 {"status": "unclear", "text": "Ítem 16 aplica-ok: con SBR 21, crb_minflux da 0.8863 nm en r = 0 vs 0.8848 a 1 nm (continuo; Fisher propio 0.8858). Solo con SBR 1e12 el punto (0.8509) difiere del límite (0.7496, -13.5 %); SBR = inf da NaN (F110) (C16)"},
 {"status": "unclear", "text": "Ítem 17 no aplica: no hay búsqueda ni iteraciones (patrón fijo centrado)"},
 {"status": "unclear", "text": "Ítem 18 no aplica: una sola L, potencia y SBR por estudio"},
 {"status": "unclear", "text": "Ítem 19 aplica-ok: sin parpadeo en los estudios, justificado en p-MINFLUX: sigma_fl/sigma_CRB = 7.6e-4 (t_on = t_off = 100 us) y 7.1e-3 (1 us) contra 3.1 con exposiciones secuenciales 4x100 us; la opción t_mask no funciona en la ruta p_minflux (F107) (C19)"},
 {"status": "unclear", "text": "Ítem 20 no aplica: un solo emisor con Ns fijo; sin blanqueo ni vecinos"},
 {"status": "unclear", "text": "Ítem 21 no aplica: emisor estático y sin tracking; relacionado: detector sin tiempo muerto y regla 'gana el k más alto' (F101), despreciable (<= 0.10 SE por localización)"}]
```
