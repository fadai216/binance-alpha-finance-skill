from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def default_state() -> dict[str, Any]:
    return {
        "seen_symbols": [],
        "active_symbols": [],
        "tracked_tokens": [],
        "bootstrap_completed": False,
        "spread_history": {},
        "latest_report": None,
        "last_refresh_error": None,
        "last_fetch_diagnostics": None,
        "last_prune_at": None,
        "scheduler_state": {
            "consecutive_failures": 0,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
            "last_error_at": None,
        },
    }


def load_state(path: Path) -> dict[str, Any]:
    state = default_state()
    if not path.exists():
        return state

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return state

    if not isinstance(loaded, dict):
        return state

    for key, value in loaded.items():
        state[key] = value

    scheduler_state = state.get("scheduler_state")
    if not isinstance(scheduler_state, dict):
        state["scheduler_state"] = default_state()["scheduler_state"]
    else:
        for key, value in default_state()["scheduler_state"].items():
            scheduler_state.setdefault(key, value)
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        temp_name = handle.name
    Path(temp_name).replace(path)
