# -*- coding: utf-8 -*-
"""sha256 de archivos de código/datos robusto a los finales de línea (R3).

Los ``.py`` se guardan en git con LF; un ``git clone`` en Windows con ``core.autocrlf=true`` los
saca con CRLF y el sha256 de los bytes crudos cambia sin que cambie el código. Para archivos de
texto se hashea el contenido con ``\r\n`` (y ``\r`` suelto) normalizado a ``\n``; en un árbol
con LF el resultado es idéntico al sha256 de los bytes crudos. Los binarios (``.png``, ``.npy``,
``.docx``, ``.pdf``, ...) se hashean tal cual.

Uso: ``from provenance_sha import sha256_file`` (con ``scripts/`` en ``sys.path``).
"""

import hashlib
import os

__all__ = ["sha256_file", "normalize_eol", "BINARY_EXT"]

BINARY_EXT = frozenset((".png", ".jpg", ".jpeg", ".gif", ".npy", ".npz", ".docx", ".pdf",
                        ".pkl", ".h5", ".hdf5", ".zip", ".gz", ".tif", ".tiff", ".ptu"))


def normalize_eol(data):
    """bytes con CRLF (o CR suelto) convertido a LF."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_file(path, text=None):
    """sha256 hex del archivo; ``None`` si no existe.

    ``text``: None = decidir por la extensión (todo lo que no está en ``BINARY_EXT`` se trata
    como texto y se normaliza el fin de línea); True/False fuerza el modo.
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except (IOError, OSError):
        return None
    if text is None:
        text = os.path.splitext(path)[1].lower() not in BINARY_EXT
    if text:
        data = normalize_eol(data)
    return hashlib.sha256(data).hexdigest()
