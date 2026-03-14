#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen


EXAMPLES = {
    "alpha-ranked.json": "/alpha/stability/ranked?top=3",
    "alpha-trends.json": "/alpha/stability/trends?limit=6",
    "finance-recommend.json": "/binance/finance/recommend?sort_by=stability&limit=3",
    "activity-scored.json": "/binance/finance/activity/scored?limit=3",
    "copilot-summary.json": "/binance/copilot/summary?style=balanced",
}


def load_config() -> dict:
    path = Path(__file__).resolve().parents[1] / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    base_url = str(load_config()["apiBaseUrl"]).rstrip("/")

    for filename, endpoint in EXAMPLES.items():
        url = f"{base_url}{endpoint}"
        with urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        (out_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"generated {filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

