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

PROXY_URL="$(python3 - <<'PY' "$CONFIG"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print(json.load(f).get("proxy", ""))
PY
)"

NO_PROXY_VALUE="$(python3 - <<'PY' "$CONFIG"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print(json.load(f).get("noProxy", "127.0.0.1,localhost,.local"))
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

ENV_EXPORTS="export NO_PROXY='$NO_PROXY_VALUE'; export no_proxy='$NO_PROXY_VALUE';"
if [ -n "$PROXY_URL" ]; then
  ENV_EXPORTS="$ENV_EXPORTS export OUTBOUND_PROXY='$PROXY_URL'; export HTTP_PROXY='$PROXY_URL'; export HTTPS_PROXY='$PROXY_URL'; export http_proxy='$PROXY_URL'; export https_proxy='$PROXY_URL'; export ALL_PROXY='$PROXY_URL'; export all_proxy='$PROXY_URL';"
fi

nohup /bin/zsh -lc "$ENV_EXPORTS cd '$BACKEND_ROOT' && source '$VENV_DIR/bin/activate' && uvicorn main:app --host '$API_HOST' --port '$API_PORT'" > "$RUNTIME_DIR/skill-api.log" 2>&1 &

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "API started and healthy on ${API_HOST}:${API_PORT}"
    break
  fi
  sleep 1
done

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "Failed to start API. Check $RUNTIME_DIR/skill-api.log" >&2
  exit 1
fi

SCHEDULER_PID_FILE="$RUNTIME_DIR/skill-scheduler.pid"
SCHEDULER_LOG="$RUNTIME_DIR/skill-scheduler.log"

if [ -f "$SCHEDULER_PID_FILE" ]; then
  SCHEDULER_PID=$(cat "$SCHEDULER_PID_FILE")
  if kill -0 "$SCHEDULER_PID" 2>/dev/null; then
    echo "Scheduler already running (pid=$SCHEDULER_PID)"
    exit 0
  else
    rm -f "$SCHEDULER_PID_FILE"
  fi
fi

nohup /bin/zsh -lc "$ENV_EXPORTS cd '$BACKEND_ROOT' && source '$VENV_DIR/bin/activate' && python scheduler.py" > "$SCHEDULER_LOG" 2>&1 &
echo $! > "$SCHEDULER_PID_FILE"
echo "Scheduler started (pid=$(cat "$SCHEDULER_PID_FILE"))"
exit 0
