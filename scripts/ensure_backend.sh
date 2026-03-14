#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$SKILL_ROOT/config.json"

BACKEND_ROOT="$(python3 - <<'PY' "$CONFIG" "$SKILL_ROOT"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    cfg = json.load(f)
root = sys.argv[2]
backend = cfg["backendRoot"]
print(backend if backend.startswith("/") else f"{root}/{backend.lstrip('./')}")
PY
)"

VENV_DIR="$(python3 - <<'PY' "$CONFIG" "$SKILL_ROOT"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    cfg = json.load(f)
root = sys.argv[2]
venv = cfg["venvDir"]
print(venv if venv.startswith("/") else f"{root}/{venv.lstrip('./')}")
PY
)"

API_HOST="$(python3 - <<'PY' "$CONFIG"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print(json.load(f)["apiHost"])
PY
)"

API_PORT="$(python3 - <<'PY' "$CONFIG"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print(json.load(f)["apiPort"])
PY
)"

RUNTIME_DIR="$SKILL_ROOT/.runtime"
mkdir -p "$RUNTIME_DIR"
HEALTH_URL="http://${API_HOST}:${API_PORT}/health"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install -r "$BACKEND_ROOT/requirements.txt"
fi

if lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "API already running and healthy on ${API_HOST}:${API_PORT}"
    exit 0
  fi
  echo "Port ${API_PORT} is occupied, but health check failed at ${HEALTH_URL}" >&2
  exit 1
fi

nohup /bin/zsh -lc "cd '$BACKEND_ROOT' && source '$VENV_DIR/bin/activate' && uvicorn main:app --host '$API_HOST' --port '$API_PORT'" > "$RUNTIME_DIR/skill-api.log" 2>&1 &

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "API started and healthy on ${API_HOST}:${API_PORT}"
    exit 0
  fi
  sleep 1
done

echo "Failed to start API. Check $RUNTIME_DIR/skill-api.log" >&2
exit 1
