---
description: Crea un trabajo agent-team interactivo en equipo/<id>/ (andamiaje, sin correr rondas)
argument-hint: <tipo: derive|feature|draft|wiki|<receta propia>> <intent o @archivo>
---

Crea un trabajo interactivo con la metodología agent-team (ver `AGENTS.md`). **No corras
ninguna ronda**: solo el andamiaje, y luego muéstrale a la persona la configuración.

Argumentos: `$ARGUMENTS`

1. **¿Hace falta un equipo?** Si la tarea es chica y bien entendida, dilo con franqueza y ofrece
   hacerla directo en la sesión. Sigue solo si la persona confirma o si la verificación
   independiente es el producto.
2. **Tipo** (`derive`, `feature`, `draft`, `wiki` o una receta de `.agent-team/recipes/`). Si no
   está claro, pregunta. Para `feature`, verifica que el proyecto esté bajo git (`git status`);
   si no, avisa: sin git no hay diff ni punto de rollback.
3. **id** = `AAAA-MM-DD_<slug-corto>` (fecha de hoy). Crea:
   ```
   equipo/<id>/
     intent.md      el contrato (ver abajo)
     state.json     el ledger (ver abajo)
     inbox.jsonl    vacío
     reports/  work/  out/
   ```
4. **`intent.md`** — corto (~50 líneas). Partí de `OBJECTIVE.md` si la persona ya lo completó,
   si no de `OBJECTIVE.template.md` (para `feature`, de `.agent-team/plantillas/intent-feature.md`). Cubre solo lo que un test no puede
   expresar: objetivo, entorno y cómo correr cosas, convenciones congeladas, límites de datos,
   anti-objetivos explícitos ("no reescribir el módulo X"). Si el argumento es `@archivo`, usa
   ese archivo.
5. **Test de aceptación** (lo más valioso de todo el setup). Pregunta a la persona si ya tiene
   uno; si no, ofrece redactarlo con ella (plantilla en `.agent-team/plantillas/`). Debe estar
   **en rojo** antes de empezar. Registra su comando y calcula el sha256 de cada archivo
   protegido (`python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <ruta>`).
6. **`state.json`** inicial:
   ```json
   {
     "id": "<id>", "type": "<tipo>", "status": "active", "round": 0,
     "rounds_budget": 3, "worker_count": 1,
     "team": {"lead": "pi", "workers": ["worker"], "verifier": "<verifier|code-reviewer>", "extra": ["writer"]},
     "writer_when": "every | last",
     "deliverable": "out/notes.tex",
     "checks": {"command": "<ver tabla>"},
     "acceptance": {"command": "", "guard": [{"path": "", "sha256": ""}]},
     "claims": [], "plan": [], "backlog": [], "history": [],
     "last_checks": null, "last_acceptance": null, "writer_seen_verified": 0
   }
   ```
   Defaults por tipo (iguales a las recetas del tool; si hay receta en `.agent-team/recipes/`, usa esa):

   | tipo | verifier | workers | writer | entregable | checks |
   |---|---|---|---|---|---|
   | derive | verifier | 2 | every | out/notes.tex | provenance + `python out/checks.py` si existe |
   | feature | code-reviewer | 1 | last | out/notes.tex (+ out/changes.diff) | provenance + `out/checks.sh` (tests del proyecto) |
   | draft | verifier | 2 | every | out/draft.tex | provenance |
   | wiki | verifier | 2 | every | out/wiki/index.html | provenance |

   El check de procedencia es:
   `python ../../agent-team/bin/check_provenance.py <entregable> out/provenance.json`
   (corrido desde `equipo/<id>/`).
   Crea `out/provenance.json` como `{}`. Para `derive` copia `.agent-team/plantillas/checks.py`
   a `out/checks.py`; para `feature`, `.agent-team/plantillas/checks.sh` a `out/checks.sh` y
   anota el commit base (`git rev-parse HEAD`) en `state.json` como `base_commit`.
7. Muestra el resumen: id, tipo, equipo, rondas, checks, aceptación. Recuerda que cada ronda se
   corre con `/equipo-ronda <id>` y que la persona decide después de cada una.
