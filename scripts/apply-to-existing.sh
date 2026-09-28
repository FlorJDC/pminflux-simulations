#!/usr/bin/env bash
# Brings the agent-team methodology from this template into an EXISTING project (bash version
# of apply-to-existing.ps1). For a new project, just create it from the template on GitHub.
#
#   ./scripts/apply-to-existing.sh <target> [--force] [--git]
#
# Copies the template's files without overwriting existing ones (unless --force). CLAUDE.md,
# AGENTS.md and .gitignore are never replaced: a marked agent-team section is appended, or
# refreshed on re-run. The template's README.md is not copied. Safe to re-run.
set -euo pipefail

TEMPLATE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="" FORCE=0 GIT=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --git) GIT=1 ;;
    -h|--help) sed -n 2,9p "$0"; exit 0 ;;
    *) TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || { echo "usage: $0 <target> [--force] [--git]" >&2; exit 2; }
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"
[ "$TARGET" != "$TEMPLATE" ] || { echo "Target cannot be the template itself." >&2; exit 2; }
PY="$(command -v python3 || command -v python)" || { echo "Python 3 is required." >&2; exit 2; }

echo "Applying agent-team-template to: $TARGET"

if git -C "$TEMPLATE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  list() { git -C "$TEMPLATE" ls-files; }
else
  list() { (cd "$TEMPLATE" && find . -type f -not -path './.git/*' -not -path '*/__pycache__/*' | sed 's|^\./||'); }
fi
copied=0 kept=0
while IFS= read -r rel; do
  case "$rel" in CLAUDE.md|AGENTS.md|.gitignore|README.md) continue ;; esac
  [ -e "$TEMPLATE/$rel" ] || continue
  if [ -e "$TARGET/$rel" ] && [ "$FORCE" -eq 0 ]; then kept=$((kept + 1)); continue; fi
  mkdir -p "$(dirname "$TARGET/$rel")"
  cp -p "$TEMPLATE/$rel" "$TARGET/$rel"
  copied=$((copied + 1))
done < <(list)
echo "  files copied: $copied  (already present, left alone: $kept)"

PYTHONIOENCODING=utf-8 "$PY" - "$TEMPLATE" "$TARGET" <<'PYEOF'
import io, os, sys
tpl, dst = sys.argv[1], sys.argv[2]
INI = "<!-- agent-team:inicio (agent-team-template; no editar dentro de este bloque) -->"
FIN = "<!-- agent-team:fin -->"
GI_INI, GI_FIN = "# --- agent-team (agent-team-template) ---", "# --- /agent-team ---"
rd = lambda p: io.open(p, encoding="utf-8").read()
def wr(p, t):
    with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(t)
def block(t, a, b):
    i, j = t.find(a), t.find(b)
    return None if i < 0 or j < i else t[i:j + len(b)]
def merge(name, blk, a, b, when_new):
    p = os.path.join(dst, name)
    if not os.path.exists(p):
        wr(p, when_new); print(f"  {name} created"); return
    cur = rd(p); old = block(cur, a, b)
    if old == blk:
        print(f"  {name} already up to date"); return
    wr(p, cur.rstrip() + "\n\n" + blk + "\n" if old is None else cur.replace(old, blk))
    print(f"  {name} exists: agent-team section added/updated")

claude = rd(os.path.join(tpl, "CLAUDE.md"))
merge("CLAUDE.md", block(claude, INI, FIN), INI, FIN, claude)
agents_blk = INI + "\n" + rd(os.path.join(tpl, "AGENTS.md")).rstrip() + "\n" + FIN
merge("AGENTS.md", agents_blk, INI, FIN, agents_blk + "\n")
gi = (GI_INI + "\n# agent-team job data is local state (delete these lines to version it)\n"
      "jobs/*\n!jobs/.gitkeep\nequipo/*\n!equipo/.gitkeep\nagent-team/policy.json\n__pycache__/\n" + GI_FIN)
merge(".gitignore", gi, GI_INI, GI_FIN, gi + "\n")
PYEOF

if git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1; then :
elif [ "$GIT" -eq 1 ]; then git -C "$TARGET" init -q && echo "  git init done"
else echo "  NOTE: target is not a git repo; 'feature' jobs need one (use --git)."
fi
echo
echo "Next: fill in 'Sobre este proyecto' in CLAUDE.md, copy OBJECTIVE.template.md to OBJECTIVE.md,"
echo "then open Claude Code there and use /equipo-nuevo (interactive) or /job-preparar (./job.sh)."
