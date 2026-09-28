"""out/checks.py — la columna vertebral de verificación de un trabajo `derive`/análisis.

Corre en cada ronda (lo llama el check spine). Cada función check_* comprueba UNA afirmación
de forma ejecutable; el writer apunta la procedencia aquí:  "reproduce": "out/checks.py::check_x".
Sale con código != 0 si algún check falla.
Solo librería estándar por defecto; si usas numpy/sympy, asegúrate de que estén instalados.
"""

import math
import sys


def check_ejemplo_limite():
    """Ejemplo: un caso límite con respuesta conocida."""
    assert math.isclose(math.sin(1e-8) / 1e-8, 1.0, rel_tol=1e-12)


CHECKS = [v for k, v in sorted(globals().items()) if k.startswith("check_") and callable(v)]


def main():
    failed = 0
    for fn in CHECKS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 -- report every failure, keep going
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc!r}")
    print(f"{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
