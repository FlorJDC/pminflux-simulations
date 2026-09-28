---
description: Resume el estado de los trabajos agent-team del proyecto (interactivos en equipo/ y CLI en jobs/)
argument-hint: "[<id>]"
---

Argumentos: `$ARGUMENTS`

Sin id: lista cada trabajo de `equipo/*/state.json` (id, tipo, status, ronda/presupuesto,
nº de afirmaciones verified/refuted/unclear, último resultado de checks y aceptación). Si existe
`jobs/` y el comando `job` está disponible, agrega la salida de `job status`.

Con id: muestra el intent (resumido), las afirmaciones agrupadas por estado (las `refuted` y
`unclear` primero: están vivas), el backlog, el historial de rondas, y dónde está el entregable.

No modifiques nada. Termina recordando las opciones: continuar / congelar / abandonar.
