from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from alpha_monitor.config import Settings


class Web3WalletError(RuntimeError):
    pass


class Web3WalletClient:
    _WEB3_BASE = "https://web3.binance.com"
    _WEB3_EARN_PATH = "/bapi/defi/v1/public/wallet-direct/buw/earn/list"
    _CMS_ACTIVITY_PATH = "/bapi/composite/v1/public/cms/article/list/query"

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
                "Accept": "application/json",
                "Origin": self._WEB3_BASE,
                "Referer": f"{self._WEB3_BASE}/",
            }
        )

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.session.get(url, params=params, timeout=self.settings.request_timeout)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("success") is False or payload.get("code") not in (None, "000000", "0"):
            raise Web3WalletError(f"bad payload: {payload}")
        return payload

    def fetch_defi_earn_pools(self) -> list[dict[str, Any]]:
        payload = self._get_json(f"{self._WEB3_BASE}{self._WEB3_EARN_PATH}")
        data = payload.get("data")
        if not isinstance(data, list):
            raise Web3WalletError(f"unexpected earn list format: {type(data)}")
        return data

    def fetch_web3_cms_activities(self, catalog_id: int, page_size: int = 10) -> list[dict[str, Any]]:
        """Fetch Web3 wallet-related CMS activities from the Binance CMS catalog."""
        collected: list[dict[str, Any]] = []
        per_page = min(page_size, 10)
        page_no = 1
        base_url = self.settings.base_url

        while len(collected) < page_size:
            payload = self._get_json(
                f"{base_url}{self._CMS_ACTIVITY_PATH}",
                params={"type": 1, "catalogId": catalog_id, "pageNo": page_no, "pageSize": per_page},
            )
            catalogs = (payload.get("data") or {}).get("catalogs") or []
            if not catalogs:
                break
            articles = catalogs[0].get("articles") or []
            if not isinstance(articles, list) or not articles:
                break
            collected.extend(articles)
            if len(articles) < per_page:
                break
            page_no += 1

        return collected[:page_size]
