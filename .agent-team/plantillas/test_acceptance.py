"""Test de aceptación — LA definición de "terminado", escrita por la persona.

Reglas:
- Escríbelo ANTES de correr el equipo y confirma que está en ROJO.
- Pruebas de comportamiento observable (entradas -> salidas), no de implementación.
- Protégelo con --acceptance-guard (CLI) o con el sha256 en state.json (modo interactivo):
  el equipo puede hacerlo pasar, nunca editarlo.

Copia este archivo a tests/test_acceptance.py y reemplaza los ejemplos.
Correr:  python -m pytest tests/test_acceptance.py -q      (o: python -m unittest tests/test_acceptance.py)
"""

import unittest


class Aceptacion(unittest.TestCase):
    def test_la_funcionalidad_existe(self):
        # Ejemplo: el módulo/función nueva se puede importar.
        # from mi_paquete.nuevo_modulo import funcion_nueva
        self.fail("reemplaza este ejemplo por tu primer criterio de aceptación")

    def test_resultado_conocido(self):
        # Ejemplo: un caso con respuesta conocida (analítica, de referencia, de un dataset chico).
        # self.assertAlmostEqual(funcion_nueva(datos_ejemplo), 1.2345, places=3)
        self.fail("reemplaza por un caso con resultado conocido")

    def test_borde(self):
        # Ejemplo: entrada vacía / fuera de rango -> error claro, no un resultado silencioso.
        # with self.assertRaises(ValueError):
        #     funcion_nueva([])
        self.fail("reemplaza por un caso borde")


if __name__ == "__main__":
    unittest.main()
