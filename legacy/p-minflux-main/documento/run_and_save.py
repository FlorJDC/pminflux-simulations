"""Wrapper: corre simulation_misalignment.py guardando figuras en lugar de plt.show()"""
import matplotlib
matplotlib.use('Agg')   # backend sin pantalla

import sys, os, io

# Rutas derivadas de la ubicación de este archivo: el paquete `documento/` se
# puede mover entero sin tocar nada.
_HERE = os.path.dirname(os.path.abspath(__file__))   # .../p-minflux-main/documento
_PROJ = os.path.dirname(_HERE)                       # .../p-minflux-main
sys.path.insert(0, _PROJ)
os.chdir(_PROJ)

# Forzar UTF-8 en stdout (evita UnicodeEncodeError con °, ±, √, etc.) y además
# duplicar la salida a run_final.log, que es de donde `build_doc.py` lee la
# tabla de resultados. Así la cadena queda autocontenida.
_LOG_PATH = os.path.join(_HERE, 'run_final.log')


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)
        return len(data)

    def flush(self):
        for s in self._streams:
            s.flush()


_console = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
_logfile = open(_LOG_PATH, 'w', encoding='utf-8')
sys.stdout = _Tee(_console, _logfile)

import matplotlib.pyplot as plt

# Interceptar plt.show() para guardar en vez de mostrar
_fig_dir = os.path.join(_HERE, 'figs')
os.makedirs(_fig_dir, exist_ok=True)
_fig_counter = [1]

_original_show = plt.show
def _save_instead(*args, **kwargs):
    for i, fig in enumerate(map(plt.figure, plt.get_fignums())):
        path = os.path.join(_fig_dir, f'fig{_fig_counter[0]:02d}.png')
        fig.savefig(path, dpi=120, bbox_inches='tight')
        print(f'[guardada] {path}')
        _fig_counter[0] += 1
    plt.close('all')
plt.show = _save_instead

# Correr el script principal
try:
    exec(open('simulation_misalignment.py', encoding='utf-8').read())
finally:
    # Restaurar stdout ANTES de cerrar el log: si se cierra primero, el Tee
    # sigue apuntando a un archivo cerrado y el flush final del intérprete
    # falla con ValueError durante el shutdown.
    sys.stdout.flush()
    sys.stdout = _console
    _logfile.close()
    print(f'[log] {_LOG_PATH}')
