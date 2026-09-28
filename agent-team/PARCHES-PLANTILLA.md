# Cambios de este `agent-team/` respecto del upstream

Base: <https://github.com/matiaszaldarriaga/agent-team> commit `87e1368`
("fix(engine): a refutation must outlive the round that filed it").

## Compatibilidad Windows / Python 3.8
| Archivo | Cambio |
|---|---|
| `agentteam/recipes.py`, `agentteam/roles.py`, `bin/check_provenance.py` | `from __future__ import annotations` (las anotaciones `list[str]` fallan en Python 3.8). |
| `agentteam/backends.py` | `Popen(..., encoding="utf-8", errors="replace")`: la salida de los CLIs no se decodifica con la página de códigos de Windows. |
| `agentteam/engine.py` | `_shell_run` / `_sh_path`: checks y aceptación corren en `bash` (Git Bash) en Windows en lugar de `cmd.exe`, con rutas con `/`. |
| `agentteam/jobs.py` | `is_running` usa `OpenProcess` en Windows (`os.kill(pid, 0)` no es un chequeo de existencia allí). |
| `tests/test_agentteam.py` | `test_the_zsh_under_bash_death...` acepta también el error de bash ≥ 4 (sale ≠ 0 antes de llegar al sentinel). |
| Todo | Finales de línea LF (los `.sh` con CRLF rompen bash). |

## Configuración por proyecto (nuevo)
| Archivo | Cambio |
|---|---|
| `agentteam/__init__.py` | `project_config_dir`, `lookup_dirs`, `find_file`, `list_names`: busca primero en `<proyecto>/.agent-team/`. |
| `agentteam/roles.py`, `agentteam/recipes.py` | Roles y recetas del proyecto tienen prioridad sobre los del tool; `job roles` / `job recipes` listan la unión. |
| `agentteam/staffing.py` | `load_policy` usa `<proyecto>/.agent-team/policy.json` si existe. |
| `tests/test_agentteam.py` | Clase `ProjectOverrides` (4 tests). |
| `skills/agent-team/SKILL.md` | El tool está vendorizado en `agent-team/` del proyecto y se lanza con `job.cmd`/`job.sh`; menciona `.agent-team/`, el modo interactivo y Windows. Copia en `.claude/skills/agent-team/` (mantenerlas iguales). |

## Actualizar desde el upstream

```sh
git clone https://github.com/matiaszaldarriaga/agent-team /tmp/at-up
cd /tmp/at-up && git diff 87e1368 HEAD > /tmp/up.patch
cd <proyecto> && git apply --3way --directory=agent-team /tmp/up.patch    # resolver conflictos con esta tabla a mano
python -m unittest discover -s tests
```
Luego actualiza el commit base de este archivo y copia `agent-team/skills/agent-team/SKILL.md` a `.claude/skills/agent-team/`.
