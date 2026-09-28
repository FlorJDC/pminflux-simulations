#!/usr/bin/env bash
# out/checks.sh — check spine de un trabajo `feature`. Corre en cada ronda.
# Normalmente: la suite de tests del proyecto. Debe imprimir "SPINE OK" como ÚLTIMO acto en caso
# de éxito: un spine que muere antes sin decir que terminó NO cuenta como aprobado.
set -euo pipefail

# Raíz del proyecto (el CLI la pasa en AGENT_TEAM_PROJECT; si no, git).
PROJECT="${AGENT_TEAM_PROJECT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT"

# Reemplaza por el comando de tests de tu proyecto:
python -m pytest -q

echo "SPINE OK"
