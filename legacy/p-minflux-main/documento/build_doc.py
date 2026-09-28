# -*- coding: utf-8 -*-
"""Genera el documento técnico sobre desalineamiento de EBP en p-MINFLUX."""
import os, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Todas las rutas se derivan de la ubicación de este archivo, así el paquete
# `documento/` se puede mover entero sin tocar nada.
BASE = os.path.dirname(os.path.abspath(__file__))   # .../p-minflux-main/documento
PROJ = os.path.dirname(BASE)                        # .../p-minflux-main

FIGS = os.path.join(BASE, 'figs')                   # figuras generadas por run_and_save.py
LOG = os.path.join(BASE, 'run_final.log')           # salida de esa misma corrida
OUT = os.path.join(PROJ, 'EBP_desalineamiento.docx')

# Para regenerar el documento de cero, en este orden:
#     python documento/run_and_save.py        -> simulación: fig01..fig06 + run_final.log
#     python documento/make_fig_fwhm.py       -> figura del ajuste de la dona
#     python documento/make_fig_eficiencia.py -> barrido en fotones + eficiencia.log
#     python documento/build_doc.py           -> arma el .docx con todo lo anterior

# ── leer la tabla de resultados de la corrida ────────────────────────────────
RESULTS = []
if os.path.exists(LOG):
    txt = open(LOG, encoding='utf-8', errors='replace').read()
    for line in txt.splitlines():
        m = re.match(r'^(.{1,22}?)\s{2,}([\d.]+)\s+([\d.]+)±([\d.]+)\s+'
                     r'([\d.]+)±([\d.]+)\s+([\d.]+)±([\d.]+)\s+'
                     r'([\d.]+)±([\d.]+)\s+([\d.]+)\s*$', line.strip())
        if m:
            g = m.groups()
            RESULTS.append((g[0].strip(), g[1], f'{g[2]}±{g[3]}', f'{g[4]}±{g[5]}',
                            f'{g[6]}±{g[7]}', f'{g[8]}±{g[9]}', g[10]))
if not RESULTS:
    raise SystemExit(f'No pude leer la tabla de resultados de {LOG}')
print(f'Leí {len(RESULTS)} filas de resultados')

doc = Document()

# ── estilos ──────────────────────────────────────────────────────────────────
st = doc.styles['Normal']
st.font.name = 'Calibri'
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(8)
st.paragraph_format.line_spacing = 1.15

for name, size in [('Heading 1', 16), ('Heading 2', 13), ('Heading 3', 11.5)]:
    s = doc.styles[name]
    s.font.name = 'Calibri'
    s.font.size = Pt(size)
    s.font.color.rgb = RGBColor(0x1F, 0x3B, 0x57)
    s.paragraph_format.space_before = Pt(16)
    s.paragraph_format.space_after = Pt(6)


def para(text, italic=False, bold=False, size=None, align=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic, r.bold = italic, bold
    if size:
        r.font.size = Pt(size)
    if align:
        p.alignment = align
    return p


def rich(parts, align=None):
    p = doc.add_paragraph()
    for text, fmt in parts:
        r = p.add_run(text)
        r.bold = fmt.get('b', False)
        r.italic = fmt.get('i', False)
        if fmt.get('mono'):
            r.font.name = 'Consolas'
            r.font.size = Pt(9.5)
    if align:
        p.alignment = align
    return p


def code_block(lines):
    for ln in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.left_indent = Inches(0.3)
        r = p.add_run(ln if ln else ' ')
        r.font.name = 'Consolas'
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x20, 0x20, 0x20)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def figure(fname, caption, width=6.4):
    doc.add_picture(os.path.join(FIGS, fname), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(caption)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), hexcolor)
    tcPr.append(shd)


def table(headers, rows, widths=None, highlight_rows=(), fs=9.5):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ''
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(fs)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shade(c, 'D9E2EC')
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''
            p = cells[i].paragraphs[0]
            r = p.add_run(str(v))
            r.font.size = Pt(fs)
            if ri in highlight_rows:
                r.bold = True
                shade(cells[i], 'FFF3CD')
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


# ═══════════════════════════════════════════════════════════════════════════
# PORTADA
# ═══════════════════════════════════════════════════════════════════════════
for line in ('Efecto del desalineamiento del EBP sobre',
             'la precisión de localización en p-MINFLUX'):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(line)
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = RGBColor(0x1F, 0x3B, 0x57)
doc.paragraphs[-1].paragraph_format.space_after = Pt(10)

para('Separación cuantitativa de las dos causas de pérdida de precisión: '
     'la geometría del patrón y la forma de las donas',
     italic=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
para('Datos: C:\\Data\\psf\\20260820  ·  400 × 400 px, 1 nm/px  ·  K = 4 haces  ·  '
     '300 localizaciones por caso',
     size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()

doc.add_heading('Resumen', level=1)
para('Se estudió cuánta precisión de localización se pierde cuando el patrón de '
     'excitación (EBP) de un sistema p-MINFLUX no coincide con el triángulo '
     'equilátero ideal. La pérdida puede provenir de dos causas que en la práctica '
     'aparecen mezcladas: que los mínimos de los haces no estén en las posiciones '
     'de diseño (geometría), y que cada dona real no sea una dona ideal, en '
     'particular que su mínimo no sea un cero perfecto (forma).')
rich([('Para separarlas se construyeron tres EBP sobre la misma grilla, que difieren '
       'en una sola cosa por vez, y se los simuló con dos estimadores distintos. '
       'El resultado principal es que, para este conjunto de datos, ', {}),
      ('la geometría medida prácticamente no cuesta precisión, mientras que la forma '
       'real de las donas la degrada por un factor mayor que dos', {'b': True}),
      (': el límite de Cramér-Rao pasa de 4,3 nm a 9,7 nm al reemplazar donas '
       'analíticas por donas medidas, manteniendo la geometría fija.', {})])
rich([('Un segundo resultado, que el CRB por sí solo no muestra, es que ', {}),
      ('un cero imperfecto cobra dos veces', {'b': True}),
      (': además de subir el límite teórico, impide alcanzarlo en el régimen de pocos '
       'fotones en que MINFLUX opera. A cien fotones por localización el error '
       'observado con las donas medidas es casi el doble de su propio CRB, mientras '
       'que con donas ideales el límite se alcanza en todo el rango.', {})])
para('El documento detalla la verificación de la convención de coordenadas de los '
     'datos, la construcción de los tres patrones, el modelo de dona y sus '
     'convenciones en la literatura, las métricas empleadas y su validación, los '
     'resultados, el contraste con la bibliografía, y los problemas metodológicos '
     'detectados en el código de análisis.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('1. La pregunta y la estrategia', level=1)
doc.add_heading('1.1 Qué se quiere separar', level=2)
para('Un EBP MINFLUX ideal de K = 4 consiste en un haz central y tres haces '
     'periféricos cuyos mínimos de intensidad forman un triángulo equilátero '
     'inscripto en un círculo de diámetro L. En un instrumento real ese patrón '
     'nunca es exacto, y hay dos desviaciones independientes:')
rich([('(a) Geometría. ', {'b': True}),
      ('Los mínimos no caen exactamente en los vértices del triángulo equilátero. '
       'El patrón está deformado o descentrado, pero cada haz sigue siendo una dona '
       'con un cero bien definido.', {})])
rich([('(b) Forma. ', {'b': True}),
      ('Cada dona medida no es una dona ideal. Tiene aberraciones, fondo, y sobre '
       'todo su mínimo no llega a cero: hay intensidad residual donde debería no '
       'haber nada. Esto reduce la profundidad de modulación, que es lo que MINFLUX '
       'usa para localizar.', {})])
para('Ambas degradan la precisión, pero por mecanismos distintos y con remedios '
     'distintos: la geometría se puede medir y compensar en el estimador; la forma '
     'de las donas es una limitación óptica del instrumento.')

doc.add_heading('1.2 Cómo se separan', level=2)
para('La estrategia es construir tres patrones sobre exactamente la misma grilla, '
     'de manera que entre uno y el siguiente cambie una sola cosa:')
table(['EBP', 'Donas', 'Geometría', 'Qué agrega respecto del anterior'],
      [['ideal', 'analíticas perfectas', 'triángulo perfecto', '— (referencia)'],
       ['geom_exp', 'analíticas perfectas', 'la medida', 'el efecto de la geometría'],
       ['exp', 'las medidas', 'la medida', 'el efecto de la forma de las donas']],
      widths=[0.95, 1.55, 1.35, 2.55])
para('Comparar «ideal» con «geom_exp» aísla la contribución de la geometría, porque '
     'las donas son idénticas en ambos casos. Comparar «geom_exp» con «exp» aísla la '
     'contribución de la forma, porque la geometría es idéntica en ambos casos.')
rich([('Para que la comparación sea limpia, el EBP ideal se construye con ', {}),
      ('L = L_eff del patrón medido', {'b': True}),
      (' (103,2 nm) y no con un valor redondo, y las donas analíticas se generan con '
       'el tamaño ajustado a las donas medidas (sección 3.3). Así entre «ideal» y '
       '«geom_exp» lo único que cambia es la forma del triángulo, y entre «geom_exp» '
       'y «exp» lo único que cambia es la forma de cada dona.', {})])

doc.add_heading('1.3 Estimador honesto y estimador ingenuo', level=2)
para('Además de cómo se generan los fotones, importa qué modelo usa el software para '
     'estimar la posición. Se consideran dos:')
rich([('Honesto. ', {'b': True}),
      ('El estimador usa las mismas PSFs que generaron los fotones. Es el mejor caso '
       'posible: el modelo es correcto, así que el error debería ser sólo varianza y '
       'debería alcanzar el límite de Cramér-Rao.', {})])
rich([('Ingenuo. ', {'b': True}),
      ('El estimador supone el EBP ideal aunque la física sea otra. Representa la '
       'situación real de un laboratorio que no caracterizó su patrón. El modelo es '
       'incorrecto, y eso introduce un ', {}),
      ('sesgo', {'b': True}),
      (': un error sistemático que, a diferencia de la varianza, no se reduce '
       'juntando más fotones.', {})])

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('2. Datos y verificación de la convención', level=1)
para('Antes de simular hubo que establecer sin ambigüedad cómo se mapean los índices '
     'de los arreglos a coordenadas físicas. Un error de convención —por ejemplo un '
     'reflejo vertical espurio— invalida silenciosamente toda la comparación, porque '
     'las donas analíticas quedarían colocadas en posiciones que no corresponden a '
     'las medidas.')

doc.add_heading('2.1 La grilla', level=2)
rich([('El archivo ', {}), ('fit_config.txt', {'mono': True}),
      (' que acompaña a las PSFs fija la grilla, de modo que ni el tamaño de píxel ni '
       'la cantidad de píxeles quedan escritos a mano en el script:', {})])
code_block(['[FittingParameters]',
            'scan_range_um  = 0.4      ->  FOV  = 400 nm',
            'fitted_pixels  = 400      ->  n_px = 400',
            'pixel_size_um  = 0.001    ->  px   = 1 nm'])
para('El código verifica además que fitted_pixels × pixel_size coincida con '
     'scan_range, y aborta si no cierra.')

doc.add_heading('2.2 La convención de coordenadas', level=2)
para('Se adoptó una única convención, la misma que usan las funciones de conversión '
     'del paquete:')
code_block(['x_nm = col * px_nm - size_nm/2',
            'y_nm = size_nm/2 - fila * px_nm'])
rich([('Se verificó que el archivo ', {}),
      ('Min_positions_fit_fwd_not_centered.txt', {'mono': True}),
      (' reproduce ', {}), ('exactamente', {'b': True}),
      (' el argmin de cada archivo .npy, con la convención X = índice de columna, '
       'Y = índice de fila, ', {}),
      ('sin reflejo vertical', {'b': True}), (':', {})])
table(['Haz', 'argmin del .npy (fila, col)', 'Archivo (X, Y)', '¿Coincide?'],
      [['1', '(204, 162)', '(162, 204)', 'Sí'],
       ['2', '(231, 118)', '(118, 231)', 'Sí'],
       ['3', '(230, 207)', '(207, 230)', 'Sí'],
       ['4', '(153, 157)', '(157, 153)', 'Sí']],
      widths=[0.7, 2.3, 1.7, 1.2])
rich([('Se verificó también que la función que genera las donas analíticas produce '
       'arreglos con esta misma convención: pidiéndole un cero en (−38, −4) nm, el '
       'argmin del arreglo resultante cae en (fila 204, col 162), el mismo índice que '
       'el del haz 1 experimental. ', {}),
      ('Conclusión: no corresponde aplicar ningún flip en ninguna parte del pipeline.',
       {'b': True})])

doc.add_heading('2.3 Centrado', level=2)
para('Centrar es un cambio de sistema de referencia: se resta un mismo vector a los '
     'cuatro mínimos, de modo que el haz de referencia quede en el origen. En el '
     'código el mismo vector se usa para trasladar las PSFs y para trasladar las '
     'posiciones, así que ambos no pueden desincronizarse.')
para('Los píxeles que quedan vacíos al trasladar se rellenan replicando el borde y no '
     'con ceros. Rellenar con ceros hace que la suma de las cuatro PSFs valga cero en '
     'el borde, y eso produce divisiones por cero y valores NaN en la función de '
     'verosimilitud, que a su vez engañan al argmax.')

doc.add_heading('2.4 Advertencia sobre el archivo de posiciones centradas', level=2)
rich([('El archivo ', {}), ('Min_positions_fit_fwd_centered.txt', {'mono': True}),
      (' presente en la carpeta ', {}), ('no es consistente', {'b': True}),
      (' con el archivo de posiciones sin centrar. Centrar exige restar un mismo '
       'offset a los cuatro haces, pero el offset implicado por cada haz no es '
       'constante:', {})])
table(['Haz', 'not_centered', 'centered', 'Offset implicado'],
      [['1', '(162, 204)', '(0, 0)', '(162, 204)'],
       ['2', '(118, 231)', '(−46, 31)', '(164, 200)'],
       ['3', '(207, 230)', '(41, 26)', '(166, 204)'],
       ['4', '(157, 153)', '(−7, −55)', '(164, 208)']],
      widths=[0.7, 1.7, 1.5, 2.0])
para('El offset varía 4 nm en X y 8 nm en Y, de modo que no existe ningún cambio de '
     'sistema de referencia que mapee un archivo al otro: no describen el mismo '
     'conjunto de mínimos. Se descartó que la diferencia venga de una estimación '
     'sub-píxel, porque refinando los mínimos con centroide y con ajuste parabólico '
     'se mueven menos de medio píxel.')
para('La geometría permite decidir cuál es el conjunto correcto. Centrando desde los '
     'datos crudos, las tres distancias del haz central a los periféricos son 51,6 / '
     '52,0 / 51,2 nm (dispersión 0,30 nm), es decir un triángulo casi perfectamente '
     'equilátero, como debe ser un EBP MINFLUX. Los valores del archivo centrado dan '
     '55,5 / 48,5 / 55,4 nm (dispersión 3,26 nm), notoriamente más irregular.')
rich([('Por eso todo el análisis centra desde los datos crudos y el archivo de '
       'posiciones centradas se ignora. ', {'b': True}),
      ('Queda pendiente localizar el error en el script que lo genera.', {})])

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('3. Los tres patrones', level=1)
figure('fig01.png',
       'Figura 1. Geometría de los tres EBP. Los tres comparten el mismo '
       'L_eff = 103,2 nm. El ideal tiene asimetría nula por construcción; los otros '
       'dos comparten la geometría medida, con una asimetría de sólo 0,30 nm. La '
       'estrella marca la posición del emisor, idéntica en todos los casos.')

doc.add_heading('3.1 Geometría del patrón medido', level=2)
para('La métrica de asimetría es la desviación estándar de las distancias del haz '
     'central a los tres periféricos. Vale cero para un triángulo perfecto y crece '
     'con la deformación del patrón.')
table(['EBP', 'L_eff [nm]', 'Asimetría [nm]', 'Centroide [nm]'],
      [['ideal', '103,23', '0,00', '(0,00, 0,00)'],
       ['geom_exp', '103,23', '0,30', '(−1,00, −0,50)'],
       ['exp', '103,23', '0,30', '(−1,00, −0,50)']],
      widths=[1.3, 1.4, 1.5, 1.7])
rich([('Ya acá se anticipa el resultado: ', {}),
      ('la geometría medida se desvía muy poco de la ideal', {'b': True}),
      ('. Una asimetría de 0,30 nm frente a un patrón de 103 nm es una deformación '
       'del orden del 0,3 %.', {})])

figure('fig02.png',
       'Figura 2. Las PSFs de los tres patrones, con zoom a la región de operación. '
       'Cada fila usa una misma escala de color, de modo que las cuatro donas de un '
       'mismo EBP son comparables entre sí. El círculo turquesa marca el mínimo de '
       'cada haz. La diferencia visible entre la fila «geom_exp» y la fila «exp» es '
       'la forma real de las donas, que es justamente lo que se quiere aislar.')

doc.add_page_break()

doc.add_heading('3.2 El modelo de dona y sus convenciones', level=2)
para('Las donas analíticas se generan con el modelo estándar de la literatura '
     'MINFLUX, introducido por Balzarotti y colaboradores (ec. S16 del material '
     'suplementario):')
code_block(['I(r) = A0 · 4e·ln2 · (r²/fwhm²) · exp( -4·ln2 · r²/fwhm² )'])
rich([('El parámetro ', {}), ('fwhm', {'mono': True}),
      (' NO es el ancho a media altura de la dona. En palabras del propio artículo, '
       'es «un parámetro relacionado con el tamaño para el caso de la dona, y el '
       'ancho a media altura para el haz gaussiano». Lo que se deriva de él es la '
       'posición del anillo:', {})])
code_block(['radio   del anillo = fwhm / (2·√ln2) ≈ 0,6006 · fwhm',
            'diámetro del anillo = fwhm / √ln2    ≈ 1,2011 · fwhm'])

rich([('Durante este trabajo se detectó que ', {}),
      ('coexisten dos convenciones distintas para ese parámetro', {'b': True}),
      (', lo cual es una fuente seria de confusión al comparar valores entre trabajos:',
       {})])
table(['Fuente', 'Cómo entra el parámetro', 'Valor usado', 'Radio del anillo'],
      [['Balzarotti et al. 2017, ec. S16', 'directo en la fórmula', '—', '0,6006·fwhm'],
       ['Tarkowski & Stefani 2025, ec. [4]', 'directo en la fórmula', '360 nm', '216,2 nm'],
       ['Marin & Ries 2026, SimuFLUX', 'directo en la fórmula', '310 nm', '186,2 nm'],
       ['Stefani-Lab/sml-ssi (código)', 'se usa 1,2·fwhm', '360 nm', '259,4 nm']],
      widths=[2.15, 1.75, 1.05, 1.35], highlight_rows=(3,), fs=9)
para('Es decir: tres fuentes independientes ponen el parámetro directo en la fórmula, '
     'mientras que el código publicado del grupo lo multiplica antes por 1,2. Para la '
     'misma dona física, el número que reporta ese código es 1,2 veces menor:')
code_block(['fwhm_literatura = 1,2 × fwhm_sml-ssi'])
rich([('En este trabajo el código fue modificado para seguir la convención de la '
       'literatura. Se verificó que ', {}),
      ('la dona física no cambia', {'b': True}),
      (' —el radio del anillo de las donas medidas sigue siendo 206,5 nm, y los tres '
       'valores de CRB quedaron idénticos (4,28 / 4,32 / 9,69 nm)— y que sólo cambia '
       'el número que se reporta.', {})])
rich([('Recomendación práctica: ', {'b': True}),
      ('reportar siempre el ', {}), ('radio del anillo', {'b': True}),
      (', que es invariante ante estas convenciones y directamente medible. Si además '
       'se da un FWHM, explicitar la convención.', {})])

doc.add_heading('3.3 Cómo se determina el tamaño de las donas medidas', level=2)
para('Para que la comparación entre donas analíticas y medidas no esté contaminada '
     'por una diferencia de tamaño, el parámetro de las donas analíticas se ajusta al '
     'de las medidas. El procedimiento requiere cuidado por dos razones.')

figure('explicacion_fwhm.png',
       'Figura 3. Los tres pasos del argumento, sobre la dona del haz 0. '
       '(1) El máximo del anillo cae en el borde del campo medido o fuera de él. '
       '(2) Por eso el perfil radial sube monótonamente y el argmax devuelve siempre '
       'el último bin, sea cual sea la dona: el estimador satura. '
       '(3) Lo que sí determina el parámetro es cuánto se aparta el perfil de una '
       'parábola (zona sombreada).', width=6.6)

rich([('Primero: no sirve medir el radio del anillo buscando el máximo. ', {'b': True}),
      ('Con estas donas el anillo está en r ≈ 200–217 nm, es decir en el borde del FOV '
       'de ±200 nm o más allá. El perfil radial sube monótonamente en el 99,5 % de los '
       'puntos y el argmax devuelve r = 199 nm, el último bin. Y devolvería 199 nm '
       'para cualquier dona: si el anillo real estuviera en 210, 260 o 350 nm, el '
       'resultado sería el mismo. El estimador satura y deja de contener información.',
       {})])
rich([('Segundo: tampoco alcanza con la curvatura cerca del mínimo. ', {'b': True}),
      ('Cerca de r = 0 el modelo se reduce a I(r) ≈ C + (A/fwhm²)·r². Como la amplitud '
       'A es libre —los datos están en cuentas de cámara, en unidades arbitrarias— la '
       'curvatura observada es el cociente A/fwhm², y hay infinitas parejas (A, fwhm) '
       'que dan la misma parábola. Con la curvatura sola el parámetro queda '
       'indeterminado.', {})])
rich([('Lo que rompe la degeneración es ', {}),
      ('cuánto se aparta el perfil del comportamiento parabólico', {'b': True}),
      (' dentro del rango medido, que es lo que controla el factor exponencial. Por '
       'eso se ajusta el modelo completo con C y A libres, sobre todo el perfil radial '
       'disponible.', {})])

para('Resultado del ajuste sobre las cuatro donas medidas:')
table(['Haz', 'fwhm [nm]', 'Radio del anillo [nm]', 'Cero (mín/máx)', 'Error del ajuste'],
      [['0', '332,9', '199,9', '9,00 %', '0,24 %'],
       ['1', '341,1', '204,9', '8,66 %', '0,62 %'],
       ['2', '360,7', '216,6', '10,35 %', '0,63 %'],
       ['3', '340,9', '204,7', '11,02 %', '0,80 %'],
       ['promedio', '343,9', '206,5', '9,76 %', '—']],
      widths=[0.85, 1.15, 1.75, 1.35, 1.4], highlight_rows=(4,))

figure('fig06.png',
       'Figura 4. Perfil radial de cada dona medida (azul) y el modelo ajustado '
       '(rojo punteado). El acuerdo es mejor que 1 % en los cuatro haces.')

doc.add_heading('3.4 Límite de validez del ajuste', level=2)
para('El método tiene un rango de validez que conviene dejar anotado. Cuanto más '
     'ancha es la dona, menos se aparta de una parábola dentro del campo medido, y '
     'peor queda determinado el parámetro. El control consiste en ajustar donas '
     'sintéticas de tamaño conocido y ver cuánto se recupera:')
table(['fwhm real [nm]', 'Apartamiento de la parábola', 'Recuperado [nm]',
       'Error', 'Correlación A↔fwhm'],
      [['200', '93,8 %', '198,9', '0,55 %', '−0,13'],
       ['310  (SimuFLUX)', '68,5 %', '307,8', '0,70 %', '+0,23'],
       ['344  (estas donas)', '60,8 %', '341,9', '0,57 %', '+0,59'],
       ['360  (Tarkowski)', '57,5 %', '358,3', '0,47 %', '+0,72'],
       ['500', '35,8 %', '506,2', '1,25 %', '+0,98'],
       ['800', '15,9 %', '882,5', '10,31 %', '+0,999']],
      widths=[1.55, 1.75, 1.25, 0.85, 1.35], highlight_rows=(2,), fs=9)
para('La correlación entre la amplitud y el parámetro de tamaño en la matriz de '
     'covarianza del ajuste mide directamente la degeneración. Para estas donas vale '
     '+0,59 y la incerteza es de décimas de nanómetro; para donas de 800 nm la '
     'correlación llega a +0,999 y el ajuste deja de ser confiable. El método es '
     'sólido en el régimen de este trabajo, pero dejaría de serlo con donas mucho más '
     'anchas o con un campo de barrido más chico.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('4. Métricas', level=1)
doc.add_heading('4.1 Límite de Cramér-Rao', level=2)
para('El CRB da la mínima varianza alcanzable por cualquier estimador insesgado, dada '
     'la geometría del patrón, las PSFs, el número de fotones y la relación '
     'señal-fondo. Es el patrón de referencia contra el cual se juzga el desempeño: si '
     'un estimador honesto no lo alcanza, algo está mal en el estimador o en el modelo.')
para('El CRB sólo tiene sentido dentro de la región de operación de MINFLUX, del orden '
     'de L/2 alrededor del centro del patrón; lejos de ahí la información se desploma '
     'y los valores no son interpretables. Por eso los mapas se muestran con zoom.')

doc.add_heading('4.2 Validación de la implementación del CRB', level=2)
para('Se verificó que la implementación usada coincide con la convención publicada por '
     'el grupo. El material suplementario de Tarkowski & Stefani define')
code_block(['σ_CRB(r) = sqrt( tr[Σ(r)] / 3 )        (caso 3D)'])
para('Partiendo de la matriz de información de Fisher por fotón y de Σ = (N·F)⁻¹ se '
     'obtiene tr[Σ] = (F_xx + F_yy)/(N·det F), de donde')
code_block(['sqrt( tr[Σ] / d )  =  sqrt(1/(d·N)) · sqrt(E/F)'])
para('que es literalmente la expresión del código con d = 2. Se comprobó además '
     'numéricamente reimplementando el CRB por el camino de la traza de la '
     'covarianza: ambos dan 1,9741 nm, coincidentes a 1×10⁻⁹.')
para('Controles adicionales:')
table(['Control', 'Resultado'],
      [['Escaleo con el número de fotones',
        'N = 100 / 500 / 2000 → 4,414 / 1,974 / 0,987 nm, exactamente 1/√N'],
       ['Independencia del tamaño de píxel',
        'px = 0,5 / 1 / 2 / 4 nm → 4,114 / 4,115 / 4,122 / 4,147 nm (0,8 % de dispersión)'],
       ['Contraste con Tabla S1 del artículo',
        '3D K=5: 2,37 nm en el centro; aquí 2D K=4: 1,97 nm, mismo orden y mejor, '
        'como corresponde a menos dimensiones']],
      widths=[2.1, 4.3], fs=9)

doc.add_heading('4.3 Sesgo, varianza y RMSE', level=2)
para('De cada caso se simulan 300 localizaciones independientes y se calculan:')
rich([('Varianza. ', {'b': True}),
      ('La dispersión de las estimaciones alrededor de su propia media. Es el error '
       'aleatorio, y se reduce juntando más fotones.', {})])
rich([('Sesgo. ', {'b': True}),
      ('La diferencia entre la media de las estimaciones y la posición verdadera. Es '
       'el error sistemático, y ', {}),
      ('no se reduce juntando más fotones', {'b': True}),
      (': es la firma de un modelo incorrecto.', {})])
rich([('RMSE. ', {'b': True}),
      ('Combina ambos: RMSE² = varianza + sesgo². Es el error total.', {})])
rich([('El cociente ', {}), ('RMSE / CRB', {'b': True}),
      (' es el diagnóstico central. Un valor cercano a 1 indica que el estimador '
       'alcanza el límite teórico y que el error es sólo varianza. Un valor mucho '
       'mayor que 1 indica sesgo, o que el modelo del estimador no coincide con la '
       'física.', {})])
para('Con un número finito de muestras los estadísticos tienen su propia '
     'incertidumbre: el error estándar de una desviación estándar es σ/√(2n) y el de '
     'una media es σ/√n. Se reportan explícitamente, y la simulación usa una semilla '
     'fija para que los resultados sean reproducibles.')

figure('fig03.png',
       'Figura 5. Mapas del límite de Cramér-Rao, en la misma escala de color para que '
       'sean comparables entre sí, con zoom a la región de operación. El círculo '
       'punteado marca el patrón y la estrella roja el emisor. Los dos primeros mapas '
       'son prácticamente indistinguibles; el tercero, construido con las PSFs '
       'medidas, es visiblemente peor en toda la región.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('5. Resultados', level=1)
para('Trescientas localizaciones independientes por caso, con un emisor en '
     '(5, −5) nm, Ns = 90 fotones de señal, Nb = 10 de fondo (SBR = 9), y búsqueda '
     'del estimador restringida a |r| < 77,4 nm. Todos los valores en nanómetros '
     'salvo la última columna.')
table(['Caso', 'CRB', 'σx', 'σy', '|sesgo|', 'RMSE', 'RMSE/CRB'],
      RESULTS,
      widths=[1.75, 0.6, 1.0, 1.0, 1.0, 1.0, 0.85],
      highlight_rows=(3, 4), fs=9)

figure('fig04.png',
       'Figura 6. Las estimaciones de cada caso. La estrella negra es la posición '
       'verdadera y la cruz roja la media de las estimaciones: la separación entre '
       'ambas es el sesgo. En los tres primeros casos la nube está centrada en la '
       'posición verdadera; en los dos últimos aparece dispersión y corrimiento.')
figure('fig05.png',
       'Figura 7. Descomposición del error en sus dos componentes. La parte azul baja '
       'juntando más fotones; la parte roja no. Las estrellas marcan el CRB de cada '
       'caso.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('6. Interpretación', level=1)
doc.add_heading('6.1 La geometría casi no cuesta precisión', level=2)
para('El CRB pasa de 4,28 a 4,32 nm al reemplazar la geometría ideal por la medida: '
     'un 1 % de degradación. El estimador honesto alcanza el límite en ambos casos.')
rich([('Más llamativo todavía: el caso ', {}), ('ingenuo', {'b': True}),
      (' con geometría medida tampoco paga prácticamente nada. Es decir, ', {}),
      ('para este patrón, estimar con el EBP ideal cuando la física es la geometría '
       'medida es casi inofensivo', {'b': True}), ('.', {})])
para('La razón es directa: la geometría medida se desvía muy poco de la ideal. La '
     'asimetría es de 0,30 nm sobre un patrón de 103 nm. El EBP ideal es, a todos los '
     'efectos, una descripción excelente del patrón real, así que el modelo del '
     'estimador ingenuo casi no está equivocado y por lo tanto casi no hay sesgo.')

doc.add_heading('6.2 La forma de las donas sí cuesta, y bastante', level=2)
para('Comparando el segundo caso con el cuarto, donde la geometría es idéntica y lo '
     'único que cambia son las donas:')
rich([('El CRB pasa de 4,32 a 9,69 nm: ', {}),
      ('un factor 2,2 de degradación, atribuible enteramente a la forma de las donas',
       {'b': True}), ('. El RMSE observado empeora todavía más.', {})])
para('El mecanismo es la profundidad de modulación. MINFLUX localiza a partir de cómo '
     'cambia la fracción de fotones que aporta cada haz al moverse el emisor. Esa '
     'fracción es la cantidad informativa, y su rango accesible determina cuánta '
     'información hay:')
table(['Patrón', 'Rango de PSF₀ / ΣPSF', 'Modulación'],
      [['analítico (donas ideales)', 'desde 0,000', 'cero profundo, modulación completa'],
       ['experimental', '0,130 – 0,284', 'sin cero, modulación parcial']],
      widths=[2.1, 1.9, 2.4])
para('En las donas analíticas el mínimo es un cero verdadero: cuando el emisor está '
     'exactamente en el cero de un haz, ese haz no aporta ningún fotón, y la señal es '
     'máximamente informativa. En las donas medidas queda intensidad residual en el '
     'mínimo, la fracción nunca baja de 0,13, y la función de verosimilitud resulta '
     'mucho más chata. Un máximo chato se localiza peor.')
rich([('La consecuencia práctica para el diseño experimental es clara: ', {}),
      ('el esfuerzo de alineación tiene rendimientos decrecientes frente al esfuerzo '
       'de mejorar la calidad óptica de las donas', {'b': True}),
      ('. Una vez que el patrón está alineado al orden del 1 %, lo que limita la '
       'precisión es la profundidad del cero, no la posición de los mínimos.', {})])

doc.add_heading('6.3 El cero malo cobra dos veces', level=2)
rich([('Hay un segundo efecto, más sutil, que el CRB por sí solo no muestra. En la '
       'tabla de resultados el caso experimental honesto da RMSE/CRB ≈ 1,5, pese a que '
       'ahí no hay ningún desajuste de modelo: el estimador usa exactamente las mismas '
       'PSFs que generaron los fotones. ', {}),
      ('La causa es que el CRB es una cota asintótica', {'b': True}),
      (', que el estimador de máxima verosimilitud alcanza en el límite de muchos '
       'fotones, no necesariamente con los pocos fotones de una localización MINFLUX '
       'real.', {})])
para('La predicción es verificable: si ésa es la causa, el cociente debe converger a 1 '
     'al aumentar el número de fotones, y el caso ideal —con modulación completa— debe '
     'estar en 1 en todo el rango. Es exactamente lo que ocurre:')
table(['N (fotones)', 'RMSE/CRB ideal', 'RMSE/CRB experimental'],
      [['100', '0,97 ± 0,04', '1,89 ± 0,08'],
       ['200', '0,95 ± 0,04', '1,20 ± 0,05'],
       ['400', '0,98 ± 0,04', '1,27 ± 0,06'],
       ['800', '0,98 ± 0,04', '1,06 ± 0,05'],
       ['1600', '1,06 ± 0,05', '1,03 ± 0,05'],
       ['3200', '1,11 ± 0,05', '1,03 ± 0,05']],
      widths=[1.5, 2.0, 2.4], highlight_rows=(0,))

figure('eficiencia_vs_fotones.png',
       'Figura 8. Izquierda: cociente RMSE/CRB en función del número de fotones. El EBP '
       'ideal es eficiente en todo el rango; el experimental sólo alcanza el límite a '
       'partir de algunos cientos de fotones. Las líneas punteadas finas marcan el '
       'límite impuesto por la cuantización de la grilla, que explica el ascenso a N '
       'grande. Derecha: el CRB en sí mismo, con la pendiente −1/2 esperada.')

rich([('Sobre el ascenso del caso ideal a N grande: no es una falla del estimador sino '
       'un artefacto de la grilla. El estimador devuelve un índice entero de píxel, de '
       'modo que su salida está cuantizada y eso agrega una varianza de px²/12. Un '
       'estimador perfectamente eficiente pero cuantizado daría '
       '√(CRB² + px²/12)/CRB, que a N = 3200 vale 1,07 —el CRB ya es menor que el '
       'píxel de 1 nm—. Corrigiendo por ese efecto, el caso ideal queda entre 0,95 y '
       '1,04 en todo el rango, y el experimental converge a 1,02.', {})])

rich([('El resultado se puede enunciar así: ', {}),
      ('una mala profundidad del cero cobra dos veces', {'b': True}),
      ('. Primero sube el CRB por un factor 2,26 —el efecto que ya se discutió—. Y '
       'además impide alcanzarlo con pocos fotones, por otro factor de aproximadamente '
       '1,9 a N = 100. En condiciones realistas de una localización MINFLUX, el costo '
       'combinado frente al patrón ideal es cercano a un factor 4.', {})])
para('Esto refuerza la conclusión de la sección anterior y agrega un matiz práctico: '
     'evaluar un instrumento sólo por su CRB subestima el efecto de un cero '
     'imperfecto, porque no captura la penalización adicional por no alcanzar el '
     'límite en el régimen de pocos fotones en que MINFLUX opera.')

doc.add_heading('6.4 Alcance de la conclusión', level=2)
rich([('Este resultado está enunciado ', {}),
      ('para este conjunto de datos', {'b': True}),
      (', cuyo patrón está muy bien alineado (asimetría 0,3 %). No debe leerse como '
       '«la geometría nunca importa»: el caso ingenuo no paga sesgo precisamente '
       'porque el EBP ideal describe bien al real. Con un patrón más deformado el '
       'estimador ingenuo sí acumularía sesgo, y ese es un experimento que el código '
       'permite hacer directamente pasando otras coordenadas.', {})])
para('El caso «Experimental ingenua» ilustra el punto: ahí el modelo del estimador sí '
     'difiere sustancialmente de la física —no por la geometría sino por la forma— y '
     'el sesgo y el RMSE/CRB se disparan.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('7. Contraste con la literatura', level=1)

doc.add_heading('7.1 Tamaño de las donas', level=2)
para('Expresadas en la convención de la literatura, las donas medidas caen dentro del '
     'rango de los valores publicados:')
table(['Fuente', 'fwhm [nm]', 'Radio del anillo [nm]'],
      [['Marin & Ries 2026 (SimuFLUX)', '310', '186,2'],
       ['Estas donas medidas', '343,9', '206,5'],
       ['Tarkowski & Stefani 2025', '360', '216,2'],
       ['Default del código sml-ssi', '432', '259,4']],
      widths=[2.6, 1.3, 1.9], highlight_rows=(1,))
rich([('El valor de SimuFLUX está calibrado contra un cálculo vectorial riguroso de la '
       'PSF, según indica el propio código. El default heredado del código del grupo, '
       'en cambio, resulta un 20–25 % más ancho que ambas referencias y que las donas '
       'reales. ', {}),
      ('Ajustar el tamaño a los datos medidos, en lugar de usar el default, no fue '
       'sólo prolijidad: alinea el trabajo con la literatura.', {'b': True}),
      (' Usar el default habría subestimado la curvatura cerca del cero y por lo tanto '
       'la precisión alcanzable.', {})])

doc.add_heading('7.2 Profundidad del cero, y una advertencia', level=2)
para('Balzarotti y colaboradores reportan que en sus experimentos «el mínimo de la '
     'dona alcanzó menos del 0,2 % de la cresta». Las donas de este trabajo dan entre '
     '8,7 % y 11,0 %, es decir entre 45 y 55 veces más. Esto sostiene el resultado '
     'central: lo que limita la precisión es la profundidad del cero.')
rich([('Sin embargo, esa comparación requiere una verificación antes de darla por '
       'buena. ', {'b': True}),
      ('Marin & Ries señalan que «las perlas grandes introducen un fondo aparente en '
       'la forma de la PSF al promediar el cero», y su simulador incluye un parámetro '
       'de tamaño de perla que convoluciona la perla con la PSF teórica para modelar '
       'ese efecto.', {})])
rich([('Es decir: parte del 9–11 % medido puede provenir del tamaño de la perla usada '
       'para calibrar las PSFs, y no de la calidad real del haz. ', {}),
      ('Antes de usar la comparación con Balzarotti hay que establecer con qué '
       'diámetro de perla se tomaron estas PSFs y, si es apreciable frente a los '
       '~200 nm del anillo, acotar o deconvolucionar ese efecto.', {'b': True}),
      (' Los valores medidos también incluyen fondo del detector y luz espuria, que '
       'no son la misma magnitud que reporta Balzarotti.', {})])

doc.add_heading('7.3 El trabajo de Ries sobre simulación realista', level=2)
rich([('Marin & Ries publicaron ', {}), ('SimuFLUX', {'b': True}),
      (', un simulador de MINFLUX construido para investigar los límites de desempeño '
       'causados por dinámica del fluoróforo, fondo, estimadores y desalineamiento. '
       'Es el trabajo más cercano al presente y sus conclusiones convergen con las de '
       'aquí desde otro ángulo:', {})])
table(['Hallazgo de Marin & Ries', 'Correspondencia en este trabajo'],
      [['El CRB no predice la degradación causada por imperfecciones',
        'Aquí se identifica un mecanismo concreto de esa insuficiencia: con un cero '
        'imperfecto el CRB es correcto pero no se alcanza a pocos fotones (sección 6.3)'],
       ['El fondo es en última instancia el factor limitante de la precisión',
        'La profundidad del cero —fondo en el mínimo— domina sobre la geometría'],
       ['El fondo produce además sesgo, no sólo pérdida de precisión',
        'Motiva la descomposición explícita en sesgo y varianza'],
       ['El sesgo por fondo desaparece si el fondo se resta de los conteos o se '
        'ajusta como parámetro libre del estimador',
        'Indica el camino para resolver el problema abierto de la sección 8.3']],
      widths=[2.9, 3.5], fs=9)
rich([('Conviene explicitar una distinción. ', {'b': True}),
      ('El «desalineamiento» que estudian Marin & Ries es óptico: la placa de fase '
       'desplazada fuera de eje, que deforma la PSF y produce sesgo dependiente de z. '
       'El de este trabajo es geométrico: dónde caen los mínimos del patrón. Son '
       'fenómenos distintos y complementarios. De hecho el resultado obtenido aquí —que '
       'la forma pesa más que la geometría— es consistente con que ellos encuentren '
       'que lo que rompe la predicción del CRB son las imperfecciones que degradan la '
       'forma de la PSF (aberraciones, desalineamiento óptico, fondo) y no el '
       'posicionamiento de los haces.', {})])
para('Como validación cruzada futura, sería valioso procesar estas mismas PSFs '
     'experimentales con SimuFLUX, que admite cargar PSFs calibradas directamente y '
     'cubre las mismas variables. Que dos implementaciones independientes coincidan '
     'sobre los mismos datos es un argumento fuerte.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('8. Notas metodológicas', level=1)
para('Durante el análisis se detectaron tres problemas en el código heredado. Dos '
     'fueron corregidos; el tercero queda documentado porque su resolución es una '
     'decisión sobre el modelo, no un error de programación.')

doc.add_heading('8.1 Corregido: la búsqueda del estimador no estaba acotada', level=2)
para('El estimador de máxima verosimilitud buscaba el máximo sobre los 400 × 400 '
     'píxeles completos. Con PSFs experimentales, cuya estructura de fondo se extiende '
     'por todo el campo, aproximadamente una de cada seis estimaciones se iba a un '
     'máximo espurio lejos del patrón, a veces a más de 200 nm del emisor.')
para('Esto inflaba artificialmente la dispersión. Acotar la búsqueda a un entorno del '
     'centro del patrón es además lo físicamente correcto, porque un MINFLUX real '
     'estima localmente. El efecto sobre la desviación estándar del caso experimental:')
table(['Radio de búsqueda', 'σx [nm]', 'σy [nm]'],
      [['sin cota', '56,60', '48,87'],
       ['|r| < 150 nm', '35,54', '34,73'],
       ['|r| < 100 nm', '19,71', '24,20'],
       ['|r| < 75 nm', '11,65', '15,23']],
      widths=[2.0, 1.4, 1.4])
para('En el análisis se usa un radio de 0,75 · L_eff, parametrizado respecto del '
     'tamaño del patrón y no como un número fijo.')

doc.add_heading('8.2 Corregido: mezcla de unidades en la restricción espacial', level=2)
para('La función del estimador ya ofrecía una opción para restringir la búsqueda, pero '
     'estaba mal implementada: construía el mapa de radios en unidades de píxel y lo '
     'comparaba contra un umbral expresado en nanómetros.')
code_block(['size = np.shape(PSF)[1]              # cantidad de PIXELES (400)',
            'x = np.arange(-size/2, size/2)       # paso = 1  ->  unidades de pixel',
            'Mr = np.sqrt(Mx**2 + My**2)          # radio en PIXELES',
            'likelihood[Mr > L/2] = -np.inf       # pero L esta en NANOMETROS'])
para('El corte se aplicaba en «radio menor a L/2 píxeles», no «menor a L/2 nanómetros». '
     'Con un tamaño de píxel de 1 nm ambas cosas coinciden numéricamente y el error '
     'pasa desapercibido; con cualquier otro tamaño de píxel escala linealmente. Para '
     'un umbral pedido de 50 nm:')
table(['Tamaño de píxel', 'Radio realmente aplicado', 'Factor de error'],
      [['0,5 nm', '25,0 nm', '0,5 ×'],
       ['1,0 nm', '50,0 nm', '1,0 ×  (coincidencia)'],
       ['2,0 nm', '99,9 nm', '2,0 ×'],
       ['5,0 nm', '249,9 nm', '5,0 ×'],
       ['10,0 nm', '499,7 nm', '10,0 ×']],
      widths=[1.6, 2.2, 2.0], highlight_rows=(1,))
para('Con un píxel de 5 nm la región permitida resulta cinco veces más grande en radio '
     'y veinticinco veces más grande en área que la pedida. La versión corregida '
     'calcula el radio en nanómetros usando el tamaño de píxel. Se verificó que el '
     'cálculo del CRB, que también recibe el tamaño de píxel, no tiene este problema: '
     'pasa el espaciado en nanómetros a la derivada numérica y su resultado es estable '
     'dentro del 0,8 % sobre un rango de 8× en tamaño de píxel.')

doc.add_heading('8.3 Verificado: el fondo se genera correctamente', level=2)
para('Una inspección parcial del código puede sugerir que hay un desajuste entre el '
     'generador de fotones y el estimador, y conviene dejar aclarado por qué no lo hay. '
     'La rama p-MINFLUX del generador reparte los fotones según')
code_block(['p_i = lambda_i / sum(lambda)          # sólo los Ns fotones de SEÑAL'])
para('sin término de fondo, mientras que el estimador y el CRB asumen')
code_block(['p_i = (SBR/(SBR+1)) * PSF_i/sum(PSF) + (1/(SBR+1)) * (1/K)'])
rich([('El fondo no falta: se agrega unas cien líneas más abajo, en el tramo de código '
       'común a todas las ramas. Los ', {}), ('Nb', {'mono': True}),
      (' fotones de fondo se generan con micro-tiempo uniforme sobre todo el ciclo '
       'TCSPC, de modo que al binear en las K ventanas depositan Nb/K en cada haz. '
       'La fracción total que ve el estimador resulta entonces', {})])
code_block(['(Ns·λ_i/Σλ + Nb/K) / (Ns + Nb)',
            '   = SBR/(SBR+1) · λ_i/Σλ  +  1/(SBR+1) · 1/K        [SBR = Ns/Nb]'])
para('que es exactamente el modelo del estimador. Se verificó empíricamente acumulando '
     '40.000 fotones sobre 400 localizaciones: las fracciones simuladas coinciden con '
     'el modelo con fondo dentro del error de muestreo (desviación máxima 0,0022 '
     'frente a 0,0028 esperado), mientras que el modelo sin fondo queda a cuatro veces '
     'esa distancia.')
rich([('La diferencia con la rama «simplified» del mismo módulo es sólo dónde entra el '
       'fondo: esa rama lo mezcla en las probabilidades antes de sortear, y la rama '
       'p-MINFLUX lo agrega como fotones separados con micro-tiempo uniforme. ', {}),
      ('Lo segundo es más fiel a la física de p-MINFLUX', {'b': True}),
      (', donde el fondo no está correlacionado con el pulso de excitación.', {})])
para('La explicación del RMSE/CRB residual del caso experimental honesto es por lo '
     'tanto otra, y se desarrolla en la sección 6.3.')

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('9. Reproducibilidad', level=1)
doc.add_heading('9.1 Parámetros', level=2)
table(['Parámetro', 'Valor', 'Significado'],
      [['K', '4', 'haces del EBP'],
       ['Ns / Nb', '90 / 10', 'fotones de señal / de fondo'],
       ['SBR', '9', 'relación señal-fondo'],
       ['M_p', '2 × 10⁵', 'ciclos de excitación'],
       ['dt', '50 ns', 'período del ciclo TCSPC'],
       ['muestras', '300', 'localizaciones por caso'],
       ['semilla', '20260825', 'fija los resultados Monte Carlo'],
       ['r₀', '(5, −5) nm', 'emisor, igual en todos los casos'],
       ['fwhm de las donas', '343,9 nm', 'ajustado a las medidas (anillo 206,5 nm)'],
       ['radio de búsqueda', '0,75 · L_eff', '77,4 nm']],
      widths=[1.7, 1.5, 2.6])

doc.add_heading('9.2 Organización del código', level=2)
rich([('La construcción de patrones vive en ', {}), ('tools/ebp.py', {'mono': True}),
      (', única fuente de verdad para eso. Ofrece tres constructores que devuelven la '
       'misma estructura y por lo tanto son intercambiables:', {})])
code_block(['grid = E.grid_from_fit_config(".../fit_config.txt")',
            '',
            '# 1. PSFs medidas',
            'exp  = E.ebp_experimental(folder, K=4, grid=grid)',
            '',
            '# 2. donas perfectas en posiciones ARBITRARIAS',
            'geo  = E.ebp_analytic(exp.pos_nm, grid, donut_fwhm=343.9)',
            '',
            '# 3. patron ideal',
            'ide  = E.ebp_ideal(grid, L=103.2, K=4, donut_fwhm=343.9)'])
rich([('El segundo constructor acepta cualquier arreglo de coordenadas (K, 2) en '
       'nanómetros, de modo que para estudiar otra geometría —por ejemplo un patrón '
       'deliberadamente deformado— alcanza con pasarle las coordenadas deseadas. Los '
       'tres comparten la misma ', {}), ('Grid', {'mono': True}),
      (', que es lo que garantiza que los resultados sean comparables.', {})])

doc.add_heading('9.3 Casos simulados', level=2)
para('Los casos se declaran como una lista de tripletes: etiqueta, patrón que genera '
     'los fotones, patrón que asume el estimador. Cuando ambos coinciden el estimador '
     'es honesto; cuando difieren es ingenuo. Agregar un caso nuevo es agregar una '
     'línea.')
code_block(['CASES = [',
            '    ("Ideal",                "ideal",    "ideal"),',
            '    ("Geom. medida honesta", "geom_exp", "geom_exp"),',
            '    ("Geom. medida ingenua", "geom_exp", "ideal"),',
            '    ("Experimental honesta", "exp",      "exp"),',
            '    ("Experimental ingenua", "exp",      "ideal"),',
            ']'])

# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading('10. Referencias', level=1)
refs = [
    'Balzarotti, F. et al. Nanometer resolution imaging and tracking of fluorescent '
    'molecules with minimal photon fluxes. Science 355, 606–612 (2017). '
    'Modelo de dona, ec. (S16); expresión del CRB, ec. (S26); profundidad del cero '
    'medida, < 0,2 % de la cresta.',

    'Tarkowski, N. & Stefani, F. D. Guidelines for MINFLUX Excitation Pattern Design. '
    'ACS Photonics (2025). Ecuación [4] del campo de excitación con dx = dy = 360 nm; '
    'definición del CRB 3D en el material suplementario; Tabla S1 de valores de '
    'referencia.',

    'Marin, Z. & Ries, J. Evaluating MINFLUX experimental performance in silico. '
    'Nature Communications 17, 246 (2026). Simulador SimuFLUX; efecto del fondo, de '
    'los estimadores y del desalineamiento óptico; efecto del tamaño de perla sobre '
    'el cero medido.',

    'Deguchi, T. & Ries, J. Simple and robust 3D MINFLUX excitation with a variable '
    'phase plate. Light: Science & Applications 13, 134 (2024). Aspectos '
    'instrumentales; preservación del contraste del cero.',

    'Masullo, L. A. et al. Pulsed Interleaved MINFLUX. Nano Letters (2021). '
    'Implementación de p-MINFLUX.',

    'Código: Stefani-Lab/sml-ssi (implementación de referencia del grupo) y '
    'ries-lab/SimuFLUX (simulador de Marin & Ries), ambos en GitHub.',
]
for i, r in enumerate(refs, 1):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.first_line_indent = Inches(-0.3)
    run = p.add_run(f'[{i}]  ')
    run.bold = True
    p.add_run(r)

doc.save(OUT)
print(f'OK -> {OUT}   ({os.path.getsize(OUT)/1024:.0f} KB)')
