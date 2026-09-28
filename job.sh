#!/usr/bin/env bash
# agent-team launcher for this project (bash: Linux, macOS, Git Bash):  ./job.sh <verb> ...
# Runs the vendored tool in agent-team/ with this folder as the project root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AGENT_TEAM_PROJECT="${AGENT_TEAM_PROJECT:-$ROOT}"
export PYTHONIOENCODING=utf-8

if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then PY=python3
elif command -v py >/dev/null 2>&1; then PY="py -3"
else PY=python
fi

JOB="$ROOT/agent-team/bin/job"
if command -v cygpath >/dev/null 2>&1; then JOB="$(cygpath -w "$JOB")"; fi   # Git Bash -> Windows Python
exec $PY "$JOB" "$@"
