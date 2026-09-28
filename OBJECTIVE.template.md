OBJETIVO
========
Uno o dos párrafos: qué tiene que ser cierto cuando esto esté terminado, dicho como un
resultado, no como una lista de tareas. Si es reproducir un paper, nombra la afirmación,
figura o número exacto que se reproduce.


FUENTES
=======
Qué puede leer el equipo para hacerlo: papers en `papers/`, un repo, documentación, datos.
Di para qué sirve cada fuente; no te limites a listar rutas.


CERCO -- no leer nada más
==========================
Lo que NO se debe leer (soluciones existentes, respuestas, trabajo cercano que haría el
resultado poco confiable). Borra esta sección si no hay nada que cercar.


LO QUE LAS FUENTES NO DICEN
===========================
Las decisiones de criterio que nadie escribió: rangos de parámetros, resolución, qué casos
borde testear, cuántas repeticiones. Nombrarlas aquí hace que el equipo elija a conciencia y
lo declare, en lugar de elegir en silencio.


DISCIPLINA
==========
Restricciones del entorno (cómo correr cosas, qué Python/venv), qué NO instalar ni modificar,
qué hay que derivar vs. qué se puede recordar, qué significa "mostrar el trabajo" aquí.
Convenciones congeladas y anti-objetivos ("no reescribir el módulo X").


DEFINICIÓN DE TERMINADO
=======================
El/los check(s) ejecutables que deciden que esto terminó: un `out/checks.py`, un comando de
tests, un test de aceptación (`tests/test_acceptance.py`, escrito por ti y en ROJO antes de
empezar), una comparación con una tolerancia. Si no hay check, no hay verificador, y el
trabajo no debería correr.


ENTREGABLE
==========
El/los archivo(s) exactos que el trabajo debe producir en `out/` y sus restricciones (HTML
autocontenido sin red, un notebook, un diff, notas tex). Di qué significa "procedencia" para
este entregable si cada número tiene que rastrearse hasta algo.
