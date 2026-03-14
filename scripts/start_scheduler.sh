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

cd "$BACKEND_ROOT"
source "$VENV_DIR/bin/activate"
exec python scheduler.py
