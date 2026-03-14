from __future__ import annotations

from typing import Any

from alpha_monitor.storage import load_state as load_json_state
from alpha_monitor.storage import save_state as save_json_state


def default_state() -> dict[str, Any]:
    return {
        "latest_snapshot": None,
        "last_refresh_error": None,
        "last_fetch_diagnostics": None,
        "scheduler_state": {
            "consecutive_failures": 0,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
            "last_error_at": None,
        },
    }


def load_state(path) -> dict[str, Any]:
    state = default_state()
    loaded = load_json_state(path)
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


def save_state(path, state: dict[str, Any]) -> None:
    save_json_state(path, state)

