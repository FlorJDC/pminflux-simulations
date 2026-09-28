---
description: Corre UNA ronda agent-team (pi → workers → verificador → writer → checks) sobre un trabajo de equipo/<id>/
argument-hint: <id> [indicación para esta ronda]
---

Corre **exactamente una ronda** del trabajo interactivo indicado, con la metodología de
`AGENTS.md`. Tú eres el motor: orquestas los subagentes, cosechas las afirmaciones y actualizas
el estado. No haces tú el trabajo de los roles.

Argumentos: `$ARGUMENTS` (el primero es el id; el resto, si hay, es una indicación humana).

## 0. Preparación
- Lee `equipo/<id>/intent.md` y `state.json`. Si `status` no es `active`, detente y avisa.
- Si `round >= rounds_budget`, avisa que se agotó el presupuesto y pregunta si se extiende.
- Si hay indicación, agrégala a `inbox.jsonl` como `{"round": N, "text": "..."}`.
- N = `round + 1`. Rutas de reporte: `equipo/<id>/reports/rNN-<rol>.md` (NN con dos dígitos).
- Verifica los sha256 de `acceptance.guard`. Si alguno cambió, la aceptación está **adulterada**:
  detente y avisa a la persona.

## 1. PI
Lanza el subagente `pi` con: la ruta del trabajo, el número de ronda, `worker_count`, y la ruta
de su reporte. Devuelve un plan con tareas numeradas. Si responde `[[BLOCKED]]`, detente y
muéstrale a la persona por qué. Guarda el plan en `state.plan`; las tareas que excedan
`worker_count` van a `state.backlog` (nunca se descartan).

## 2. Workers (en paralelo)
Lanza un subagente `worker` por tarea, **todos en el mismo mensaje** para que corran en
paralelo. Cada uno recibe: la ruta del trabajo, su tarea, el tipo (en `feature` edita el
proyecto; en los demás trabaja dentro de `equipo/<id>/`), y la ruta de su reporte
(`rNN-worker-<k>.md`).

## 3. Verificador (independiente)
Lanza el verificador del equipo (`verifier` o `code-reviewer`) como subagente aparte. Pásale
**las afirmaciones de los workers y dónde están los artefactos, no su razonamiento**. Para
`feature`, indícale que revise `git diff <base_commit>` e incluya archivos nuevos.

Cosecha el bloque ```` ```claims ```` de su respuesta. Agrega cada entrada a `state.claims` como
`{"status", "text", "round": N}`. Una afirmación nueva que coincide con una ya `verified` no se
duplica. Si el bloque falta o está vacío, es un **contrato roto**: regístralo en el historial y
díselo a la persona al final.

## 4. Extras
- `writer`: córrelo si hay afirmaciones `verified` nuevas desde `writer_seen_verified` (o si es
  la última ronda del presupuesto, o si `writer_when` es `last` y esta es la última ronda).
  Si responde `NOOP`, no cambia nada. Luego actualiza `writer_seen_verified`.
- `test-writer`: solo si figura en `team.extra`.

## 5. Checks y aceptación
- Corre `checks.command` desde `equipo/<id>/` con bash (en Windows, Git Bash). Para `feature`, además, guarda el diff:
  `git add -N . && git diff <base_commit> > equipo/<id>/out/changes.diff`.
- Corre `acceptance.command` si existe. Guarda ambos resultados (pasa/falla + últimas líneas)
  en `last_checks` / `last_acceptance`.
- Si el PI dijo `[[DONE]]` pero los checks o la aceptación fallan, **el DONE se rechaza**.

## 6. Tripwires (detener y avisar si...)
- el verificador no devolvió afirmaciones;
- ninguna afirmación nueva quedó `verified` en 2 rondas seguidas;
- la misma tarea encabeza el plan 3 rondas seguidas;
- en `feature`, el proyecto no cambió en la ronda.

## 7. Cierre de ronda
- `round = N`; agrega a `history`: `{round, resumen, verified_nuevas, refuted, unclear, checks, acceptance}`.
- Si `[[DONE]]` válido: `status = "done"`.
- Muestra a la persona un resumen breve: qué se verificó, qué se refutó, qué quedó abierto,
  checks/aceptación, y la sección `LO QUE MÁS SE PODRÍA HACER` del PI. Termina con las opciones:
  **continuar** (`/equipo-ronda <id> "indicación"`), **congelar** (status `frozen`) o **abandonar**
  (status `abandoned`). **No corras otra ronda por tu cuenta.**
