# -*- coding: utf-8 -*-
"""
F206 - La cadena documento/run_and_save.py -> run_final.log -> build_doc.py ya
no reproduce el documento: la configuración actual de
simulation_misalignment.py (Ns/Nb, r0, muestras, casos) no es la del
run_final.log que build_doc.py lee, y build_doc.py escribe a mano (texto y
tabla 9.1) los parámetros de la corrida vieja.  Si hoy se corre la cadena, el
.docx sale con números de una configuración y parámetros de otra.
(La autora ya lo advirtió para los logs sueltos en ESTADO_Y_PLAN_REALISMO_PSF.md;
aquí se muestra que también afecta a la cadena que arma el documento.)

Chequeo estático (no ejecuta nada del legado):
  - lee las constantes de simulation_misalignment.py con `ast`;
  - lee r0, muestras y casos de run_final.log;
  - busca en build_doc.py los parámetros escritos a mano.
Uso:  python scripts/findings/F206_doc_numbers_vs_scripts.py
"""
import os
import re
import ast
import sys
import json

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LEG = os.path.join(ROOT, 'legacy', 'p-minflux-main')


def script_constants(path, names):
    tree = ast.parse(open(path, encoding='utf-8').read())
    vals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    vals[t.id] = ast.get_source_segment(open(path, encoding='utf-8').read(), node.value)
                if isinstance(t, ast.Tuple):
                    for k, el in enumerate(t.elts):
                        if isinstance(el, ast.Name) and el.id in names and isinstance(node.value, ast.Tuple):
                            vals[el.id] = ast.get_source_segment(
                                open(path, encoding='utf-8').read(), node.value.elts[k])
    return vals


def main():
    sm = os.path.join(LEG, 'simulation_misalignment.py')
    const = script_constants(sm, {'Ns', 'Nb', 'samples', 'R0_NM', 'INCLUDE_REALISTIC_FIT',
                                  'Tlife', 'dt', 'SEED'})
    log = open(os.path.join(LEG, 'documento', 'run_final.log'), encoding='utf-8', errors='replace').read()
    m_r0 = re.search(r'Emisor r0 = \[(.*?)\]', log)
    m_n = re.search(r'(\d+) muestras por caso', log)
    rows = re.findall(r'^(Ideal|Geom\.[^\d]+|Experimental[^\d]+|Realista[^\d]+)\s+\d', log, re.M)
    crb = re.findall(r'(\w+)\s+CRB\(r0\) =\s+([\d.]+)', log)
    bd = open(os.path.join(LEG, 'documento', 'build_doc.py'), encoding='utf-8').read()
    hard = {
        "Ns / Nb '90 / 10'": "'90 / 10'" in bd,
        "muestras '300'": "['muestras', '300'" in bd,
        "r0 '(5, −5) nm'": "'(5, −5) nm'" in bd,
        "texto §5 'Trescientas ... Ns = 90 ... Nb = 10'": ('Trescientas' in bd and 'Ns = 90' in bd),
    }
    out = {'simulation_misalignment.py': const,
           'run_final.log': {'r0': m_r0.group(1) if m_r0 else None,
                             'samples': m_n.group(1) if m_n else None,
                             'cases': [r.strip() for r in rows], 'crb': crb},
           'build_doc.py_hardcoded': hard}
    print('simulation_misalignment.py (actual):')
    for k, v in const.items():
        print('   %-22s = %s' % (k, v))
    print('run_final.log (lo que lee build_doc.py):')
    print('   r0 = [%s]   muestras = %s   CRB(r0) = %s' % (out['run_final.log']['r0'],
                                                       out['run_final.log']['samples'], crb))
    print('   casos en la tabla: %s' % out['run_final.log']['cases'])
    print('build_doc.py escribe a mano:')
    for k, v in hard.items():
        print('   %-48s %s' % (k, 'SÍ' if v else 'no'))
    mismatch = []
    if const.get('samples') and m_n and const['samples'].strip() != m_n.group(1):
        mismatch.append('muestras %s (script) vs %s (log)' % (const['samples'], m_n.group(1)))
    if 'R0_NM' in const and m_r0 and '-5.07' in const['R0_NM'] and '-5.07' not in m_r0.group(1):
        mismatch.append('r0 %s (script) vs [%s] (log)' % (const['R0_NM'], m_r0.group(1)))
    if const.get('Ns', '').strip() == '2000' and "'90 / 10'" in bd:
        mismatch.append('Ns/Nb 2000/95 (script) vs 90/10 (build_doc y CRB 4.28 nm del log = N 100)')
    if const.get('INCLUDE_REALISTIC_FIT', '').strip() == 'True' and not any('Realista' in r for r in rows):
        mismatch.append('INCLUDE_REALISTIC_FIT=True pero el log no tiene filas "Realista"')
    out['mismatches'] = mismatch
    print('\nDISCREPANCIAS (%d):' % len(mismatch))
    for s in mismatch:
        print('   -', s)
    fn = os.path.join(ROOT, 'equipo', '2026-09-28_review-pminflux-sim', 'work', 'w3', 'F206_out.json')
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    json.dump(out, open(fn, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
