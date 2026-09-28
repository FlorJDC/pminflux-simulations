---
description: Prepara un trabajo para el CLI `job` de agent-team (aceptación primero, intent corto) y deja el comando listo para confirmar
argument-hint: <tipo: derive|feature|draft|wiki> <descripción>
---

Argumentos: `$ARGUMENTS`

Ayuda a la persona a preparar un trabajo del CLI `job` (motor completo de agent-team). En este
proyecto `job` es el lanzador local: `.\job.cmd` (Windows) o `./job.sh` (bash). Usa el
skill `agent-team` si está disponible. **No gastes nada sin un "sí" explícito.**

1. **¿Vale la pena?** Si es chico y bien entendido, dilo: hacerlo interactivo puede ser mejor.
   Un trabajo se justifica cuando la verificación independiente es el producto.
2. **Test de aceptación primero, en rojo.** Es la especificación y no se puede hacer trampa.
   Ofrece redactarlo (plantilla: `.agent-team/plantillas/test_acceptance.py`), guárdalo en el
   proyecto (p. ej. `tests/test_acceptance.py`) y córrelo para confirmar que falla.
3. **Intent corto** (~50 líneas) en `.agent-team/intents/<slug>.md`, desde `OBJECTIVE.md` /
   `OBJECTIVE.template.md` (para `feature`, `.agent-team/plantillas/intent-feature.md`): entorno, cómo correr cosas, convenciones
   congeladas, límites de datos, anti-objetivos. Nada de listas de certificados en prosa.
4. **Para `feature`**: el proyecto debe estar bajo git y con el árbol limpio.
5. Arma el comando (sin ejecutarlo) y muéstralo, por ejemplo:
   ```
   .\job.cmd new feature "@.agent-team/intents/<slug>.md" --name <slug> --rounds 3 \
     --acceptance "cd {PROJECT} && python -m pytest tests/test_acceptance.py" \
     --acceptance-guard tests/test_acceptance.py
   ```
   `job new` sin `--pi` es gratis (solo andamiaje). Luego `job staff <id>` (1 llamada del PI) y
   `job run <id>` (gasto real; se detiene sola en el checkpoint de 2 rondas).
   Sugiere un verificador en otro backend cuando aplique (`--role verifier:backend=codex`): un
   modelo distinto es una comprobación genuinamente independiente.
6. Da una idea de costo (referencia del repo original: ~6M tokens por ronda de `feature` en
   xhigh; una ronda de `derive` son millones por naturaleza) y espera confirmación antes de
   `job staff`/`job run`.
7. Recuerda: monitorear con `job status`, `job watch <id>`, `jobs/<id>/view.html` o
   `job serve`; dirigir con `job say <id> "..."`; al final `job resume` / `job freeze` /
   `job abandon`.
