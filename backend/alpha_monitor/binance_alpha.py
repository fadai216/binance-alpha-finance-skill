from __future__ import annotations

import json
import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings


class BinanceAlphaError(RuntimeError):
    pass


class BinanceAlphaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
            }
        )

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.settings.base_url}{path}"
        response = self.session.get(url, params=params, timeout=self.settings.request_timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("success") is False or payload.get("code") not in (None, "000000"):
            raise BinanceAlphaError(f"unexpected Binance payload: {payload}")
        return payload

    def fetch_token_list(self) -> list[dict[str, Any]]:
        payload = self._get_json(self.settings.token_list_path)
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise BinanceAlphaError("token list format error")
        return data

    def fetch_exchange_info(self) -> dict[str, Any]:
        payload = self._get_json(self.settings.exchange_info_path)
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise BinanceAlphaError("exchange info format error")
        return data

    def fetch_klines(self, market_symbol: str, interval: str = "1m", limit: int = 60) -> list[list[str]]:
        payload = self._get_json(
            self.settings.klines_path,
            params={"symbol": market_symbol, "interval": interval, "limit": limit},
        )
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise BinanceAlphaError(f"klines format error for {market_symbol}")
        return data

    def fetch_book_ticker(self, market_symbol: str) -> dict[str, Any]:
        payload = self._get_json(
            self.settings.book_ticker_path,
            params={"symbol": market_symbol},
        )
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise BinanceAlphaError(f"book ticker format error for {market_symbol}")
        return data

    def fetch_four_x_tokens(self) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        scraped_symbols, page_diagnostics = self.try_scrape_points_page_symbols()
        token_list = self.fetch_token_list()
        exchange_info = self.fetch_exchange_info()
        pair_map = self._build_pair_map(exchange_info.get("symbols") or [])

        tokens: list[dict[str, Any]] = []
        for token in token_list:
            mul_point = token.get("mulPoint")
            if int(mul_point or 0) != 4:
                continue
            if token.get("offline") or token.get("offsell") or token.get("cexOffDisplay"):
                continue

            alpha_id = token.get("alphaId")
            pair = pair_map.get(alpha_id)
            if not alpha_id or not pair:
                continue

            display_symbol = f"{token.get('symbol', alpha_id)}{pair['quoteAsset']}"
            tokens.append(
                {
                    "alpha_id": alpha_id,
                    "market_symbol": pair["symbol"],
                    "display_symbol": display_symbol,
                    "token_symbol": token.get("symbol", alpha_id),
                    "quote_asset": pair["quoteAsset"],
                    "chain_name": token.get("chainName"),
                    "listing_time": token.get("listingTime"),
                    "mul_point": 4,
                    "page_match": display_symbol in scraped_symbols if scraped_symbols else None,
                }
            )

        page_matches = sum(1 for item in tokens if item["page_match"])
        if page_diagnostics.get("waf_challenge"):
            source = "alpha-api-fallback"
        elif scraped_symbols and page_matches:
            source = "page+alpha-api"
        else:
            source = "alpha-api"

        diagnostics = {
            "points_page": page_diagnostics,
            "token_list_total": len(token_list),
            "four_x_total": len(tokens),
            "exchange_symbol_total": len(exchange_info.get("symbols") or []),
            "page_symbol_count": len(scraped_symbols),
            "page_match_count": page_matches,
        }
        tokens.sort(key=lambda item: item["display_symbol"])
        return tokens, source, diagnostics

    def try_scrape_points_page_symbols(self) -> tuple[set[str], dict[str, Any]]:
        diagnostics: dict[str, Any] = {
            "status": "not_attempted",
            "status_code": None,
            "waf_challenge": False,
            "waf_action": None,
            "error": None,
        }
        try:
            response = self.session.get(
                self.settings.alpha_points_url,
                timeout=self.settings.request_timeout,
            )
        except requests.RequestException as exc:
            diagnostics["status"] = "request_error"
            diagnostics["error"] = str(exc)
            return set(), diagnostics

        diagnostics["status_code"] = response.status_code
        waf_action = response.headers.get("x-amzn-waf-action")
        diagnostics["waf_action"] = waf_action
        challenge = waf_action == "challenge" or response.status_code == 202
        if challenge:
            diagnostics["status"] = "waf_challenge"
            diagnostics["waf_challenge"] = True
            return set(), diagnostics

        if response.status_code != 200 or not response.text.strip():
            diagnostics["status"] = f"http_{response.status_code}"
            return set(), diagnostics

        soup = BeautifulSoup(response.text, "html.parser")
        matches: set[str] = set()
        text_candidates = re.findall(r"\b[A-Z0-9]{2,20}(?:USDT|USDC)\b", soup.get_text(" ", strip=True))
        matches.update(text_candidates)

        for script in soup.find_all("script"):
            content = script.string or script.get_text(" ", strip=True)
            if not content:
                continue
            for token in re.findall(r'"symbol"\s*:\s*"([A-Z0-9]{2,20}(?:USDT|USDC)?)"', content):
                if token.endswith("USDT") or token.endswith("USDC"):
                    matches.add(token)

            # Try to extract JSON blobs that already contain mulPoint markers.
            if '"mulPoint"' not in content:
                continue
            for candidate in re.findall(r"\{.*?\}", content):
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if int(parsed.get("mulPoint") or 0) != 4:
                    continue
                symbol = parsed.get("symbol")
                if isinstance(symbol, str) and symbol:
                    matches.add(symbol)

        diagnostics["status"] = "ok"
        diagnostics["symbol_count"] = len(matches)
        return matches, diagnostics

    @staticmethod
    def _build_pair_map(symbols: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        pair_map: dict[str, dict[str, Any]] = {}
        quote_priority = {"USDT": 0, "USDC": 1}

        for item in symbols:
            if item.get("status") != "TRADING":
                continue

            base_asset = item.get("baseAsset")
            quote_asset = item.get("quoteAsset")
            if not base_asset or quote_asset not in quote_priority:
                continue

            current = pair_map.get(base_asset)
            if current is None or quote_priority[quote_asset] < quote_priority[current["quoteAsset"]]:
                pair_map[base_asset] = {
                    "symbol": item["symbol"],
                    "quoteAsset": quote_asset,
                }

        return pair_map
