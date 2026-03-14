from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_state(cache_file: Path) -> dict[str, Any]:
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(cache_file: Path, state: dict[str, Any]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(state, ensure_ascii=False, default=str), "utf-8")
