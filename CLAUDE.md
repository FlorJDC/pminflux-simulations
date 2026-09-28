# CLAUDE.md

<!-- agent-team:inicio (agent-team-template; no editar dentro de este bloque) -->
## Metodología agent-team

@AGENTS.md

## Específico de Claude Code

### Subagentes disponibles (`.claude/agents/`)
`pi`, `worker`, `verifier`, `code-reviewer`, `test-writer`, `writer` — el elenco de agent-team
adaptado a la sesión interactiva. El verificador nunca es la misma instancia que hizo el trabajo:
lánzalo como subagente aparte, con el trabajo a revisar pero **sin** el razonamiento del worker
(para que la comprobación sea independiente).

### Comandos
- `/equipo-nuevo <intent>` — crea un trabajo interactivo en `equipo/<id>/` (sin gasto extra).
- `/equipo-ronda <id> [indicación]` — corre UNA ronda: pi → workers → verifier → writer → checks.
- `/equipo-estado [<id>]` — resume el estado de los trabajos (interactivos y CLI).
- `/job-preparar <tipo> <descripción>` — ayuda a preparar un trabajo del CLI `job`: test de
  aceptación primero, intent corto, y el comando listo para que la persona lo confirme.
- El skill `agent-team` (`.claude/skills/`) sabe manejar el CLI `job` de este proyecto (`.\job.cmd` / `./job.sh`).

### Reglas de la sesión
- Una ronda por pedido. Al terminar una ronda, mostrar el resumen y **esperar** la decisión de la
  persona (continuar con indicación / congelar / abandonar). Nunca encadenar rondas solo.
- Si la tarea es chica y bien entendida, decirlo y ofrecer hacerla directo, sin equipo.
- El estado de un trabajo es de las máquinas (`state.json`); la persona lee el entregable en `out/`.
<!-- agent-team:fin -->

## Sobre este proyecto
- Qué es: revisión crítica y versión mejorada del simulador p-MINFLUX de la autora
  (`legacy/p-minflux-main`, copia de solo lectura) + validación de la matriz de mezcla de fuga
  contra `sim_exp` + reporte HTML de hallazgos. Contrato completo en `OBJECTIVE.md`.
- **PRIVADO**: trabajo no publicado de la autora. Sin remoto; no publicar nada (tampoco artifacts).
- Setup de referencia: p-MINFLUX a 20 MHz (T = 50 ns), K = 4, Δt = 12.5 ns; τ = 4.21 ns y ventana
  [0, 10.1] ns medidos en los datos 20260707 (tracking_analysis/PIPELINE.md §11).
- Entorno: Windows, Python 3.8 (numpy, scipy, matplotlib). Los scripts con caracteres no ASCII
  llevan `# -*- coding: utf-8 -*-`. Tests: `python -m unittest discover -s tests`.
- Para importar el legado: `sys.path.insert(0, "legacy/p-minflux-main")` y después
  `from tools import tools_simulations as ts`. No editar `legacy/`.
- Referencia independiente ya verificada: `GithubPRO/donut-beam-localization/src` (paquete `donutloc`).
- No tocar: `tests/test_acceptance.py` (hash en `equipo/*/state.json`), `legacy/`, nada fuera del proyecto.
