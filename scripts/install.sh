#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${HOME}/.openclaw/skills/binance-alpha-finance"

mkdir -p "${HOME}/.openclaw/skills"

if [ -e "$TARGET_DIR" ]; then
  echo "Target already exists: $TARGET_DIR" >&2
  echo "Remove it first or move this repo directly there." >&2
  exit 1
fi

cp -R "$REPO_ROOT" "$TARGET_DIR"
chmod +x "$TARGET_DIR"/scripts/*.sh "$TARGET_DIR"/scripts/query.py

echo "Installed to: $TARGET_DIR"
echo "Next step:"
echo "  bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh"

