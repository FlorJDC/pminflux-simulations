# r03 — Worker 2: figuras del reporte

## Qué hice
- `scripts/make_report_figures.py`: matplotlib Agg, 130 dpi, 7.2 in de ancho (936 px), rótulos en español con
  unidades, paleta Okabe-Ito (segura para daltonismo) más marcadores, estilos de línea y rayado como segundo código.
  Corre en unos 7 s: `python scripts/make_report_figures.py`.
- Salidas: `report/figs/{timeline_20MHz,mixing_validation,rate_sweep,legacy_vs_v2,f201_leakage,dead_time_sweep}.png`
  y `report/figs/captions.json` = `{archivo: {title, caption, source}}`. Los números de los captions se leen de los
  JSON al correr el script: no hay ninguno tipeado a mano.
- Solo lee JSON: `results/mixing_validation.json`, `mixing_rate_sweep.json`, `compare_legacy_vs_v2.json`,
  `dead_time_sweep.json`, `findings.json` (el CRB con fuga de F201, que saca con una regex de `F201.impact`) y
  `work/w3/F201_out.json`. La única cuenta nueva es el esquema analítico de `pminflux_sim.mixing` (decay_pdf y
  mixing_matrix). Además hay operaciones de presentación, declaradas en los captions: máximos sobre ventanas,
  RMSE/CRB = rmse/crb en F201 y el reescalado de 'earliest' por √(2000/n_detected_total).
- Miré cada PNG con Read y corregí la leyenda y el recuadro superpuestos en la línea de tiempo, los rótulos
  encimados en F201, la leyenda que tapaba la línea de 1 SE en rate_sweep y la leyenda encima de las barras en
  mixing_validation. pyflakes quedó limpio.

## Autochequeos (en el script, con assert)
- La C recalculada para el esquema coincide con `mixing_validation.json:C_no_irf` (atol 1e-10).
- El reescalado √(2000/n_detected_total) aplicado a `pred_highest_minus_mixing_in_se` reproduce la clave
  `pred_highest_minus_mixing_in_se_per_2000ph_localization` (rtol 1e-6). Por eso uso el mismo factor para earliest.
- Si falta el CRB con fuga en findings.json:F201.impact, el script falla en lugar de inventarlo.

## Figuras y valores clave (todos leídos del JSON)
1. **timeline_20MHz.png**: C[1][0] = 0.0467 (4.7 %) y C[i][i] = 0.9092, con τ = 4.21 y [0, 10.1]. El panel del
   supuesto de los estudios (Tlife = 0.001, b = 12.5) da fuga máxima 0. Fuente: `mixing_validation.json:C_no_irf`.
2. **mixing_validation.png**: 2000 llamadas, 4.16e6 fotones, 1e-3/ciclo. La mezcla da χ² = 5.66 y p = 0.129, con
   desvíos entre −1.6 y +2.2 SE. El ingenuo da χ² = 1927 y p = 0 (en la leyenda "p < 1e-300"), con +27.6 SE en w0
   y −32.8 en w1.
3. **rate_sweep.png**: el máximo del desvío highest contra la mezcla es 0.009 SE/loc a 1e-3 y 0.026 a 3e-3 (los dos
   puntos calculados dentro de la banda 1e-3–5.5e-3 = 20–110 kHz). Da 0.086 a 0.01, 0.90 a 0.1 y 3.06 a 0.3. La
   configuración de los estudios a 0.0105 da 0.093 (τ 4.21) y 0.097 (τ 0.001). earliest tiene la misma magnitud con
   signo opuesto, así que las curvas se superponen; el caption lo dice.
4. **legacy_vs_v2.png** (source = v2sim, 500 bootstrap): el legado tiene |b| 0.57–2.69 nm y RMSE/CRB 1.12–2.06, y
   sigue al sesgo asintótico. La mezcla y la mezcla con free_bg quedan en |b| 0.011–0.112 nm y RMSE/CRB 0.982–1.022.
   Son paneles SBR 21/6 × IRF 0/0.3, con P1..P5 definidos en el caption.
5. **f201_leakage.png**: el ideal honesto pasa de |b| 0.11 a 2.98 nm. Su RMSE/CRB va de 1.07 a 2.75 contra el CRB
   sin fuga (0.864); contra el CRB con fuga (0.945, rombo) da **2.51**. La realista ingenua pasa de 5.5 a 10.8 nm y
   la realista honesta de 0.18 a 1.94. Escala log. Se rotula la clase DISEÑO.
6. **dead_time_sweep.png**: con d = 50 el sesgo queda en 0.012–0.024 SE/loc y con d = 100 en 0.015–0.034. Las dos
   curvas están dentro del ruido de MC (2·SE_MC = 0.037) y la p del χ² es ≥ 0.30, así que se rotulan "d = n·T, sin
   sesgo", un resultado demostrado. Con d = 22 ns, rotulado "SUPUESTO, no medido", da 0.030/0.057/0.079/0.099 a
   1e-3/2.5e-3/5.5e-3/0.0105. highest (sim_exp) da 0.028–0.109. En la banda del tracking todo queda ≤ 0.08 SE.

## Límites y notas
- El RMSE de F201 en `F201_out.json` es por eje (rmse/crb reproduce el 1.07/2.75 del ledger). Para las filas
  geom./realista solo existe el CRB sin fuga del estudio; el cociente con fuga (≈2.5) se muestra solo para el ideal
  honesto, que es el único con ese CRB en el ledger.
- rate_sweep no tiene un punto en 5.5e-3. Interpolando entre 3e-3 y 1e-2 daría unos 0.05 SE, pero el caption no lo
  afirma: solo cita los puntos calculados.
- Si W1 regenera `compare_legacy_vs_v2.json` o `findings.json`, basta con volver a correr el script. Los captions
  se regeneran solos, y la regex de F201 solo necesita que el texto conserve "conoce la fuga (0.945 nm)".
- No toqué archivos de W1 ni del writer. No hice commits.
