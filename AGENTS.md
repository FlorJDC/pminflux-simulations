<!-- agent-team:inicio (agent-team-template; no editar dentro de este bloque) -->
# Cómo se trabaja en este proyecto (metodología agent-team)

Este proyecto usa la metodología de [agent-team](https://github.com/matiaszaldarriaga/agent-team):
**un equipo acotado de agentes, con verificación independiente, que produce UN entregable y se
detiene**. La persona decide siempre qué sigue. Estas reglas valen para cualquier agente (Claude,
Codex) que trabaje aquí.

## Principios (no negociables)

1. **Empezar simple.** Una tarea chica y bien entendida se hace en la sesión interactiva, directo.
   El equipo se usa cuando la verificación independiente *es* el producto, o cuando el problema
   no entra en un solo contexto.
2. **La verificación es la columna vertebral.** Todo equipo tiene un verificador permanente
   (`verifier` para matemática/análisis, `code-reviewer` para código). Un resultado solo pasa a
   "verificado" cuando alguien *sin interés en él* lo reproduce por su cuenta. Lo verificado
   queda verificado: nadie lo re-deriva después.
3. **Nada se inventa (procedencia).** Toda afirmación importante del entregable lleva una etiqueta
   (`\src{clave}` en tex, `[src:clave]` en html/notebook/markdown) que resuelve en
   `out/provenance.json` con *cómo reproducirla*. Lo que no tiene respaldo reproducible no se
   escribe: va a "Puntos abiertos".
4. **La definición de "terminado" la escribe la persona**, como test de aceptación ejecutable,
   en rojo, antes de empezar. El equipo puede hacerlo pasar, nunca editarlo.
5. **Siempre acotado. Nunca un scheduler.** Rondas contadas, presupuesto de tokens, kill-switch.
   Nada de loops, timers ni relanzamientos automáticos.
6. **Trabajos descartables, uno por resultado.** Cada trabajo vive en su propio subárbol
   (`jobs/<id>/` o `equipo/<id>/`). Al terminar la persona decide: **continuar (con una
   indicación) / congelar / abandonar**. Integrar el resultado al proyecto es un paso aparte,
   dirigido por la persona.
7. **Pocas rondas.** El número de rondas multiplica todo. Tres, leer, y continuar si hace falta.

## El elenco (roles)

| Rol | Qué hace | Qué NO hace |
|---|---|---|
| `pi` | Lee el estado, planifica la ronda, asigna **una tarea concreta por worker**. Declara `[[DONE]]` solo con todo verificado y los checks en verde. | No hace el trabajo original. |
| `worker` | Ejecuta una tarea: deriva, calcula, programa. Se auto-verifica. Los tests van **con** el código. Reporta afirmaciones precisas y verificables. | No sobre-afirma. No re-deriva lo ya verificado. |
| `verifier` | Reproduce cada afirmación **por un camino independiente**; intenta romperla (límites, casos especiales, unidades, otra ruta). | No sella VERIFIED algo que no comprobó él mismo. |
| `code-reviewer` | Lee el diff real (no la descripción), busca defectos con escenario concreto de falla, confirma cobertura de tests, compara con el intent. | No edita el código. |
| `test-writer` | Convierte los cambios en tests ejecutables y reporta el resultado real. | No tapa fallas. |
| `writer` | Transcribe el ledger verificado al entregable + `out/provenance.json`, en sincronía. | No verifica; si no hay nada nuevo verificado responde `NOOP`. |

**El verificador es miembro permanente de todo equipo.** Un equipo sin verificador no es válido.

## Tipos de trabajo (recetas)

| Receta | Para qué | Entregable | Equipo por defecto |
|---|---|---|---|
| `derive` | Derivar / probar un resultado | `out/notes.tex` + `out/checks.py` | pi · 2 workers · verifier · writer |
| `feature` | Agregar una funcionalidad al código | `out/changes.diff` + `out/notes.tex` + `out/checks.sh` | pi · 1 worker · code-reviewer (xhigh) · writer al final |
| `draft` | Escribir un borrador (paper/notas) | `out/draft.tex` | pi · 2 workers · verifier · writer |
| `wiki` | Construir una wiki | `out/wiki/index.html` | pi · 2 workers · verifier · writer |

## Cada ronda

```
pi planifica → workers ejecutan (en paralelo) → verifier re-comprueba de forma independiente
→ se cosechan las afirmaciones (bloque ```claims```) → writer actualiza entregable + procedencia
→ corren los checks ejecutables → corre el test de aceptación de la persona
→ se actualiza el estado → la persona decide
```

El verificador termina **siempre** su respuesta con un bloque JSON:

````
```claims
[{"status": "verified", "text": "<afirmación reproducida>"},
 {"status": "refuted",  "text": "<afirmación> — <cómo falla>"},
 {"status": "unclear",  "text": "<afirmación> — <qué falta para decidir>"}]
```
````

Una afirmación `refuted` o `unclear` sigue **viva**: se resuelve o se explica por qué se mantiene.

## Dos formas de aplicar la metodología aquí

- **Modo CLI (`job`)** — el motor completo de agent-team (vendorizado en `agent-team/`; se
  lanza con `.\job.cmd` en Windows o `./job.sh` en bash, desde la raíz del proyecto): rondas acotadas, cosecha de
  afirmaciones, tripwires, `view.html`. Los trabajos quedan en `jobs/<id>/`. Gasta tokens reales:
  **pedir confirmación explícita antes de `job staff`, `job run`, `job resume` o `job new --pi`**.
- **Modo interactivo** — el mismo elenco como subagentes dentro de la sesión (Claude Code:
  `/equipo-nuevo`, `/equipo-ronda`). Los trabajos quedan en `equipo/<id>/`. Útil cuando la
  persona quiere seguir y entender cada paso (trabajo de "comprensión").

## Configuración propia del proyecto

- `.agent-team/policy.json` — límites a lo que el PI puede elegir (workers, esfuerzo, backends).
- `.agent-team/roles/*.md` — roles propios o versiones adaptadas (tienen prioridad sobre los del tool).
- `.agent-team/recipes/*.json` — tipos de trabajo propios.
- `.agent-team/plantillas/` — plantillas de intent (`feature`), test de aceptación y checks.
- `OBJECTIVE.template.md` — plantilla del objetivo; `papers/` — material fuente que el equipo puede leer.

## Guardrails para agentes

- **Nunca** iniciar, dotar o correr un trabajo por iniciativa propia: solo si la persona lo pide.
- Antes de gastar, decir costo/tiempo aproximado y esperar un "sí" explícito.
- Nunca editar un archivo de aceptación protegido. Nunca declarar terminado con afirmaciones sin verificar.
- Tener el proyecto bajo git antes de un trabajo `feature` (el diff y el punto de rollback dependen de eso).
<!-- agent-team:fin -->
