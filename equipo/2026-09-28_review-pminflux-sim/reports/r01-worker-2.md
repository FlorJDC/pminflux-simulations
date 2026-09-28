# r01 — Worker 2: auditoría A de `legacy/p-minflux-main/tools/tools_simulations.py`

## Qué hice
- Leí `OBJECTIVE.md`, `CLAUDE.md`, `inbox.jsonl`, `reports/r01-pi.md`, el handoff y `C_pminflux_practice.md` §5, que registra
  lo que la autora ya había encontrado y corregido: la búsqueda del MLE sin acotar, la mezcla px/nm en `r_max`, el truncado de
  `spaceToIndex`, la verificación del término de fondo y la convención de fwhm. No los reporto como abiertos.
- Revisé línea por línea `sim_exp` (ramas `p_minflux`, `cw_minflux` y `simplified`), `nMINFLUX`, `pos_MINFLUX`, `crb_minflux`,
  `psf`/`doughnut`/`gaussian`, `beams`/`ebp_centres`, `spaceToIndex`/`indexToSpace` y `cov_ellipse`.
- Cada sospecha tiene un script autocontenido en `scripts/findings/F1xx_*.py`: semilla fija, importa el legado en solo lectura y
  usa `donutloc` como referencia independiente donde hace falta. `F100_collect_findings_A.py` corre todos los scripts y escribe
  `results/findings_A.json` con los metadatos y los números que produjo cada script (`evidence_numbers`). La corrida completa
  tarda ~7 min.
- Criterio de clasificación: el del PI (ver `criterion` en el JSON). **Latente** = no cambia ningún número publicado por la
  autora con su configuración actual.
- No toqué `legacy/`, ni `src/`, ni los archivos de W1/W3. No hice commit.

## Hallazgos (status "candidate")
| id | clase | afirmación (con su número) | autoría |
|---|---|---|---|
| F101 | IMPL | En un ciclo con fotones de ≥2 haces, `Tmicro[m1]` se sobrescribe y queda el de k **más alto**; un TCSPC real se queda con el más temprano. Con 0.5 fotones/ciclo las fracciones coinciden con "gana el k más alto" (\|z\| ≤ 1.1) y se apartan de p hasta 25 SE. A la tasa de los estudios (0.0105/ciclo): 0.38 % de ciclos con ≥2 haces y un sesgo relativo máximo de 0.46 %. **El impacto lo mide W1.** | Masullo |
| F102 | IMPL (latente) | `relTime` trae un 0.0 por cada ciclo vacío (198000 de 200095). Con a = −0.25 ns la ventana 0 cuenta 198037 fotones en lugar de 37 y el MLE termina en el borde en el 100 % de los casos (error medio de 69.9 nm frente a 1.28 nm con a = 0). Con a = 0 funciona **solo** porque la desigualdad es estricta. | Masullo |
| F103 | IMPL (latente) | `nMINFLUX` no pliega las ventanas módulo T. Con a = −0.5 y b = 12.5, la ventana 0 pierde 5.9 % de sus cuentas (τ = 4.21) y el sesgo extra es de 0.34 nm. Con b = 13 > dt/K se cuenta dos veces el 11.2 % de los fotones (τ = 4.21) o el 94.9 % (τ = 0.001), sin aviso. | Masullo |
| F104 | CONCEPTUAL | La Ec. 3.5 (fondo 1/K, sin fuga) de `pos_MINFLUX`/`crb_minflux` es exacta **solo** con b = dt/K y τ ≪ dt/K (sesgo 0.000 nm, chi² p = 0.31: el comentario de la autora es correcto en su configuración). En el setup medido (τ = 4.21, [0, 10.1] ns, SBR 21), el sesgo asintótico del MLE va de 0.85 a 2.69 nm en 5 posiciones, **1.0–2.7 veces el CRB** (0.82–1.22 nm). El CRB real es 8.6–13.5 % mayor que el de `crb_minflux`. La ventana 0 en (5, −5) tiene 46 % de fotones de otros haces. Con SBR 6 el sesgo va de 0.59 a 2.32 nm. Con b = 10.1 y sin fuga solo se desplaza la SBR (26.1 frente a 21.05): 0.01–0.48 nm. MC de `sim_exp` a 1e-3/ciclo: chi² p = 0.38 contra el modelo de mezcla y chi² = 2559 contra el ingenuo. | Ec. 3.5: Masullo; comentario "EXACTAMENTE": la autora |
| F106 | DISEÑO | El emisor se ajusta al nodo: (−5.07, −7.56) se simula en (−5, −8), a 0.45 nm. La media del MC queda a (0.06, −0.30) ± 0.06 nm de la posición pedida. El MLE en grilla es supereficiente en un nodo (RMSE/CRB = 0.00 con CRB 0.115 nm: el 100 % de las estimaciones cae exacta en el nodo) y cuantiza fuera de un nodo (RMSE/CRB 1.77 y 3.40, con sesgo de redondeo (−0.22, 0.25) nm). | diseño de Masullo; px²/12 ya lo identificó la autora |
| F107 | IMPL (latente) | `sim_exp('p_minflux')` ignora `t_mask`: pone 51.4 % de los fotones en la mitad "apagada"; `cw_minflux` pone 0 %. | la autora (refactor de la ruta rápida), a confirmar |
| F108 | IMPL (latente, sin uso) | `cov_ellipse`: el eje mayor sale girado −90/−90/−30/+30/−90° (para φ = 0/30/60/120/150°) y los ejes no dependen de nsig (siempre 2 y 6; correcto: 3.03/9.09 con nsig = 1). | Masullo/López/Richter |
| F109 | IMPL (latente) | `psf`: la rama gaussiana ignora `donut_fwhm` (FWHM medido de 361 nm cuando se piden 250), la rama SW da NameError y `fov_center` = (20, 20) centra la grilla en (−20.5, 20.5). | mixta, a confirmar |
| F110 | IMPL (latente) | Con SBR = inf aparece inf/inf = NaN: `pos_MINFLUX` devuelve el píxel (0, 0), es decir (−100, 100) nm, fuera incluso de `r_max`, y `crb_minflux` da NaN en toda la grilla. Con SBR = 1e12 el resultado es correcto. | Masullo |
| F111 | IMPL (latente) | `ebp_centres` da IndexError con K = 5 y K = 7 (`L = [L]*4` fijo). Los comentarios de paridad están invertidos. | L. Richter |

## Descartados (con evidencia)
- **F105 (v) N fijo en lugar de Poisson.** La diferencia es real pero despreciable: la σ del MLE con Ns y Nb fijos es 0–0.71 %
  menor que el CRB multinomial (sándwich analítico; MC con donutloc: 0.9918 ± 0.005). Comparar RMSE/CRB con `sim_exp` queda
  sesgado a la baja en menos de 1 %.
- **F151 (vii) `crb_minflux`.** Los métodos 1, 2 y 3 coinciden con `donutloc.fisher.crb` dentro de 5.4e-4 con px = 1 y de
  1.3e-4 con px = 0.5 (el error es O(px²) de la diferencia finita). λb es constante (dispersión 7e-16), así que el comentario
  de la l.602 es correcto.
- **F152 (v) fondo, muestreo en dos pasos y pliegue.**
  - Las cuentas de fondo por ventana dan chi² p = 0.52. Solo `absTimeBinary` se ve afectado (llega a valores de 5).
  - Un TCSPC real produciría una pérdida selectiva por haz ≤ 3.6e-4 a la tasa de los estudios.
  - El muestreo en dos pasos es exacto por factorización (un t-test da p = 0.04 en 1 de 4 comparaciones; con 4 tests eso es
    compatible con el azar).
  - El pliegue `% dt` equivale al modelo periódico (chi² p = 0.38, en F104).
- **F153 `spaceToIndex`.** Hay 0/20 discrepancias contra el mínimo de `psf`. El fix de la autora (rint) es correcto: el
  truncado viejo sesgaba (−0.50, +0.50) nm con px = 1.
- **F154 (ix) rama cw.** Es correcta si el haz se recupera del macrotiempo (chi² p = 0.74) y aplica `t_mask`. Tiene dos
  limitaciones: `nMINFLUX` no sirve para cw (88.5 % de las cuentas cae en la ventana 0) y M_p tiene que ser múltiplo de
  cycle_time/dt (si no, ValueError). Ningún script usa esta rama.
- **(iv) dt = 25 ns en el docstring.** No es un bug: corresponde al setup de 40 MHz de Masullo. Los scripts de la autora usan
  dt = 50. Hay una errata menor: dice "6.5 ns" donde debería decir 6.25 ns.
- **(ii) desigualdad estricta en los bordes.** No tiene efecto, salvo en los ceros (eso es F102).
- **(vi) NaN → −inf.** Es correcto para los bordes rellenados. El único caso patológico es F110.

## Lo que estaba bien (para el reporte)
- El fondo como fotones aparte, uniformes en el ciclo, reproduce exactamente la Ec. 3.5 en la configuración de los estudios
  (F104: sesgo 0.000 nm, chi² p = 0.31). La autora lo había verificado y el comentario de l.423–435 es correcto ahí.
- La ruta rápida de `sim_exp` es equivalente al multinomial original y ~100× más rápida.
- `crb_minflux` es correcto en sus tres métodos (F151).
- Los fixes de `spaceToIndex`, de la mezcla px/nm en `r_max` y de `DEBUG` en `crb_minflux` son correctos.

## Notas para otros roles
- **W3:** `simulation_misalignment.py:230` calcula el sesgo contra `R0_NM` = (−5.07, −7.56), pero `sim_exp` simula en el nodo
  (−5, −8). Eso agrega un sesgo espurio de ~0.45 nm (F106a: medido (0.06, −0.30) ± 0.06 con TCP ideal y N = 2095). Queda en tu
  ámbito.
- **W1:** en F104, a la tasa de los estudios (M_p = 2e5, 0.0105/ciclo, 3e5 fotones), el chi² contra el modelo de mezcla dio
  9.9 (p = 0.02). A 1e-3/ciclo dio p = 0.38. Es un indicio compatible con F101 a la tasa de los estudios.
- **Verificador:** los números de F104 son asintóticos (argmax continuo sobre E[n]), no sesgos de MC. Hay un chequeo cruzado:
  `pos_MINFLUX` sobre la grilla con 1e7·p da (6, −5), consistente con el continuo (5.76, −5.37).

## Lo que no resolví / límites
- La autoría de F107 y de parte de F109 está marcada "a confirmar": sin historial git no se puede separar el refactor de la
  autora del código de Masullo y Richter. Los comentarios en español no bastan, porque Masullo también es hispanohablante.
- En F104 no hay IRF (la aporta el C de W1) ni se evaluaron las PSF experimentales.
- F106a usa TCP ideal, no las PSF experimentales del estudio.
