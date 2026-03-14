#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from urllib.request import urlopen


ENDPOINTS = {
    "alpha": "/alpha/stability",
    "alpha-history": "/alpha/stability/history",
    "ranked": "/alpha/stability/ranked",
    "trends": "/alpha/stability/trends",
    "finance": "/binance/finance",
    "activity": "/binance/finance/activity",
    "scored": "/binance/finance/activity/scored",
    "activity-scored": "/binance/finance/activity/scored",
    "recommend": "/binance/finance/recommend",
    "finance-recommend": "/binance/finance/recommend",
    "finance-history": "/binance/finance/history",
    "summary": "/binance/copilot/summary",
    "copilot-summary": "/binance/copilot/summary",
}

USAGE = (
    "usage: query.py "
    "<alpha|alpha-history|ranked|trends|finance|activity|scored|activity-scored|"
    "recommend|finance-recommend|finance-history|summary|copilot-summary> [query_string]"
)


def load_config() -> dict:
    path = Path(__file__).resolve().parents[1] / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_api_base_url(config: dict) -> str:
    return str(config["apiBaseUrl"]).rstrip("/")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ENDPOINTS:
        print(USAGE, file=sys.stderr)
        return 1

    endpoint = ENDPOINTS[sys.argv[1]]
    query_pairs = dict(parse_qsl(sys.argv[2])) if len(sys.argv) > 2 else {}
    config = load_config()
    base_url = resolve_api_base_url(config)
    url = f"{base_url}{endpoint}"
    if query_pairs:
        url = f"{url}?{urlencode(query_pairs)}"

    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
