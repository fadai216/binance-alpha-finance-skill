#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
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

def load_config() -> dict:
    path = Path(__file__).resolve().parents[1] / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_api_base_url(config: dict) -> str:
    return str(config["apiBaseUrl"]).rstrip("/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the local Binance Alpha / Finance backend"
    )
    parser.add_argument(
        "endpoint",
        choices=sorted(ENDPOINTS.keys()),
        help="endpoint alias",
    )
    parser.add_argument(
        "query_string",
        nargs="?",
        default="",
        help="query string such as sort_by=apr&limit=5",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON output (default)",
    )
    mode.add_argument(
        "--raw",
        action="store_true",
        help="emit compact raw JSON",
    )
    parser.add_argument(
        "--save",
        nargs="?",
        const="",
        default=None,
        help="save output to file; if omitted path, defaults to ./<endpoint>.json",
    )
    return parser


def resolve_save_path(endpoint: str, save_arg: str | None) -> Path | None:
    if save_arg is None:
        return None

    if save_arg == "":
        return Path.cwd() / f"{endpoint}.json"

    candidate = Path(save_arg).expanduser()
    if candidate.exists() and candidate.is_dir():
        return candidate / f"{endpoint}.json"
    if str(candidate).endswith("/"):
        return candidate / f"{endpoint}.json"
    return candidate


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    endpoint = ENDPOINTS[args.endpoint]
    query_pairs = dict(parse_qsl(args.query_string)) if args.query_string else {}
    config = load_config()
    base_url = resolve_api_base_url(config)
    url = f"{base_url}{endpoint}"
    if query_pairs:
        url = f"{url}?{urlencode(query_pairs)}"

    try:
        with urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    pretty = not args.raw
    rendered = (
        json.dumps(payload, ensure_ascii=False, indent=2)
        if pretty
        else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    save_path = resolve_save_path(args.endpoint, args.save)
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Saved to {save_path}", file=sys.stderr)

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
