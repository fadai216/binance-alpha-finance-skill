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

cd "$BACKEND_ROOT"
source "$VENV_DIR/bin/activate"
export NO_PROXY="$NO_PROXY_VALUE"
export no_proxy="$NO_PROXY_VALUE"
if [ -n "$PROXY_URL" ]; then
  export OUTBOUND_PROXY="$PROXY_URL"
  export HTTP_PROXY="$PROXY_URL"
  export HTTPS_PROXY="$PROXY_URL"
  export http_proxy="$PROXY_URL"
  export https_proxy="$PROXY_URL"
  export ALL_PROXY="$PROXY_URL"
  export all_proxy="$PROXY_URL"
fi
exec uvicorn main:app --host "$API_HOST" --port "$API_PORT"
