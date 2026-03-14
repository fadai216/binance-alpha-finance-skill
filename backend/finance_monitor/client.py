from __future__ import annotations

import hashlib
import hmac
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from alpha_monitor.config import Settings


class BinanceFinanceError(RuntimeError):
    pass


class BinanceFinanceClient:
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

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(url, params=params, timeout=self.settings.request_timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("success") is False or payload.get("code") not in (None, "000000", "0"):
            raise BinanceFinanceError(f"unexpected Binance payload: {payload}")
        return payload

    def _signed_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.binance_api_key or not self.settings.binance_api_secret:
            raise BinanceFinanceError("BINANCE_API_KEY or BINANCE_API_SECRET not configured")

        query = urlencode(params, doseq=True)
        signature = hmac.new(
            self.settings.binance_api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signed_query = f"{query}&signature={signature}"
        response = self.session.get(
            f"{self.settings.api_base_url}{path}?{signed_query}",
            headers={"X-MBX-APIKEY": self.settings.binance_api_key},
            timeout=self.settings.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def fetch_signed_flexible_products(self, timestamp_ms: int, size: int = 100) -> list[dict[str, Any]]:
        payload = self._signed_get(
            "/sapi/v1/simple-earn/flexible/list",
            {"current": 1, "size": size, "timestamp": timestamp_ms},
        )
        rows = payload.get("rows") or payload.get("data") or []
        if not isinstance(rows, list):
            raise BinanceFinanceError("signed flexible product list format error")
        return rows

    def fetch_signed_locked_products(self, timestamp_ms: int, size: int = 100) -> list[dict[str, Any]]:
        payload = self._signed_get(
            "/sapi/v1/simple-earn/locked/list",
            {"current": 1, "size": size, "timestamp": timestamp_ms},
        )
        rows = payload.get("rows") or payload.get("data") or []
        if not isinstance(rows, list):
            raise BinanceFinanceError("signed locked product list format error")
        return rows

    def fetch_activity_articles(self, catalog_id: int, page_size: int) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        per_page = min(page_size, 10)
        page_no = 1

        while len(collected) < page_size:
            payload = self._get_json(
                f"{self.settings.base_url}/bapi/composite/v1/public/cms/article/list/query",
                params={"type": 1, "catalogId": catalog_id, "pageNo": page_no, "pageSize": per_page},
            )
            catalogs = ((payload.get("data") or {}).get("catalogs")) or []
            if not catalogs:
                break
            articles = catalogs[0].get("articles") or []
            if not isinstance(articles, list):
                raise BinanceFinanceError("activity article list format error")
            if not articles:
                break
            collected.extend(articles)
            if len(articles) < per_page:
                break
            page_no += 1

        return collected[:page_size]

    def fetch_activity_detail(self, article_code: str) -> dict[str, Any]:
        payload = self._get_json(
            f"{self.settings.base_url}/bapi/composite/v1/public/cms/article/detail/query",
            params={"articleCode": article_code},
        )
        detail = payload.get("data") or {}
        if not isinstance(detail, dict):
            raise BinanceFinanceError(f"activity detail format error for {article_code}")
        return detail

    def probe_public_finance_bapi(self) -> dict[str, Any]:
        candidates = [
            "/bapi/finance/v1/public/simple-earn/flexible/list",
            "/bapi/finance/v1/public/simple-earn/locked/list",
            "/bapi/simple-earn/v1/public/simple-earn/flexible/list",
            "/bapi/simple-earn/v1/public/simple-earn/locked/list",
        ]
        diagnostics: dict[str, Any] = {"attempts": []}
        for path in candidates:
            response = self.session.get(
                f"{self.settings.base_url}{path}",
                timeout=self.settings.request_timeout,
            )
            attempt = {
                "path": path,
                "status_code": response.status_code,
                "waf_challenge": response.status_code in (202, 403)
                or bool(response.headers.get("x-amzn-waf-action")),
            }
            diagnostics["attempts"].append(attempt)
            if response.status_code == 200:
                try:
                    attempt["payload"] = response.json()
                except ValueError:
                    pass
                return diagnostics
        return diagnostics
