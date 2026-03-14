from __future__ import annotations

import json
import re
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from typing import Any

from alpha_monitor.config import Settings, get_settings
from finance_monitor.client import BinanceFinanceClient, BinanceFinanceError
from finance_monitor.history_store import FinanceHistoryStore
from finance_monitor.storage import load_state, save_state

_STATE_CACHE_TTL = 20.0  # seconds


class BinanceFinanceService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = BinanceFinanceClient(self.settings)
        self.history_store = FinanceHistoryStore(self.settings.sqlite_file) if self.settings.enable_sqlite_persistence else None
        self._state_cache: dict[str, Any] | None = None
        self._state_cache_at: float = 0.0

    def _load_state(self) -> dict[str, Any]:
        now = _time.monotonic()
        if self._state_cache is not None and (now - self._state_cache_at) < _STATE_CACHE_TTL:
            return self._state_cache
        state = load_state(self.settings.finance_cache_file)
        self._state_cache = state
        self._state_cache_at = now
        return state

    def _invalidate_state_cache(self) -> None:
        self._state_cache = None

    def refresh(self) -> dict[str, Any]:
        state = load_state(self.settings.finance_cache_file)
        now = datetime.now(UTC)
        timestamp_ms = int(now.timestamp() * 1000)
        diagnostics: dict[str, Any] = {}
        sources: list[str] = []

        products, product_diag, product_source = self._fetch_products(timestamp_ms)
        diagnostics["products"] = product_diag
        if product_source:
            sources.append(product_source)

        activities, activity_diag = self._fetch_activities()
        diagnostics["activities"] = activity_diag
        sources.append("cms-activities")

        derived_products = self._derive_products_from_activities(activities)
        if derived_products:
            products = self._merge_products(products, derived_products)
            sources.append("activity-derived-products")

        snapshot = {
            "products": products,
            "activities": activities,
            "updated_at": now.isoformat(),
            "source": "+".join(dict.fromkeys(sources)) or "unknown",
            "diagnostics": diagnostics,
        }

        state["latest_snapshot"] = snapshot
        state["last_refresh_error"] = None
        state["last_fetch_diagnostics"] = diagnostics
        save_state(self.settings.finance_cache_file, state)
        if self.history_store is not None:
            self.history_store.persist_snapshot(snapshot)
        return snapshot

    def refresh_safe(self) -> dict[str, Any]:
        try:
            return self.refresh()
        except Exception as exc:  # noqa: BLE001
            state = load_state(self.settings.finance_cache_file)
            state["last_refresh_error"] = {
                "message": str(exc),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            save_state(self.settings.finance_cache_file, state)
            raise

    def get_products(
        self,
        *,
        sort_by: str = "apr",
        order: str = "desc",
        product_type: str = "all",
        limit: int | None = None,
        min_apr: float = 0.0,
        max_term: int | None = None,
        redeemable_only: bool = False,
        source_filter: str | None = None,
    ) -> dict[str, Any]:
        limit = limit or self.settings.finance_default_limit
        snapshot, state = self._get_latest_snapshot()
        items = [self._annotate_product(item) for item in list(snapshot.get("products") or [])]

        if product_type != "all":
            items = [item for item in items if item.get("product_type") == product_type]
        if source_filter:
            items = [item for item in items if item.get("source") == source_filter]
        if min_apr > 0:
            items = [item for item in items if float(item.get("apr") or 0) >= min_apr]
        if max_term is not None:
            items = [
                item
                for item in items
                if int(item.get("term_days") or 0) == 0 or int(item.get("term_days") or 0) <= max_term
            ]
        if redeemable_only:
            items = [item for item in items if item.get("redeemable")]

        reverse = order != "asc"
        if sort_by in {"term", "term_days"}:
            items.sort(key=lambda item: int(item.get("term_days") or 0), reverse=reverse)
        elif sort_by == "stability":
            items.sort(key=self._product_stability_sort_key, reverse=reverse)
        elif sort_by == "product_name":
            items.sort(key=lambda item: item.get("product_name") or "", reverse=reverse)
        elif sort_by == "recommendation":
            items.sort(key=lambda item: float(item.get("recommendation_score") or 0), reverse=reverse)
        else:
            items.sort(key=lambda item: float(item.get("apr") or 0), reverse=reverse)

        return {
            "items": items[:limit],
            "updated_at": snapshot["updated_at"],
            "source": snapshot.get("source"),
            "total": len(items),
            "last_refresh_error": state.get("last_refresh_error"),
            "diagnostics": snapshot.get("diagnostics") or state.get("last_fetch_diagnostics"),
            "scheduler_state": state.get("scheduler_state"),
        }

    def get_recommended_products(
        self,
        *,
        min_apr: float = 0.0,
        max_term: int | None = None,
        redeemable_only: bool = False,
        source_filter: str | None = None,
        product_type: str = "all",
        sort_by: str = "stability",
        order: str = "desc",
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self.get_products(
            sort_by=sort_by,
            order=order,
            product_type=product_type,
            limit=limit,
            min_apr=min_apr,
            max_term=max_term,
            redeemable_only=redeemable_only,
            source_filter=source_filter,
        )

    def get_activities(
        self,
        *,
        status: str = "active",
        reward_type: str = "all",
        limit: int | None = None,
        max_capital: float | None = None,
        low_barrier_only: bool = False,
        active_only: bool = False,
    ) -> dict[str, Any]:
        limit = limit or self.settings.finance_default_limit
        snapshot, state = self._get_latest_snapshot()
        items = [self._annotate_activity(item) for item in list(snapshot.get("activities") or [])]

        effective_status = "active" if active_only and status == "all" else status
        if effective_status != "all":
            items = [item for item in items if item.get("status") == effective_status]
        if reward_type != "all":
            items = [item for item in items if item.get("reward_type") == reward_type]
        if max_capital is not None:
            items = [
                item
                for item in items
                if item.get("estimated_min_requirement_usd") is None
                or float(item.get("estimated_min_requirement_usd") or 0) <= max_capital
            ]
        if low_barrier_only:
            items = [item for item in items if item.get("low_barrier")]

        items.sort(
            key=lambda item: item.get("publish_date") or "",
            reverse=True,
        )
        return {
            "items": items[:limit],
            "updated_at": snapshot["updated_at"],
            "source": snapshot.get("source"),
            "total": len(items),
            "last_refresh_error": state.get("last_refresh_error"),
            "diagnostics": snapshot.get("diagnostics") or state.get("last_fetch_diagnostics"),
            "scheduler_state": state.get("scheduler_state"),
        }

    def get_scored_activities(
        self,
        *,
        status: str = "active",
        reward_type: str = "all",
        limit: int | None = None,
        max_capital: float | None = None,
        low_barrier_only: bool = False,
        active_only: bool = True,
    ) -> dict[str, Any]:
        response = self.get_activities(
            status=status,
            reward_type=reward_type,
            limit=None,
            max_capital=max_capital,
            low_barrier_only=low_barrier_only,
            active_only=active_only,
        )
        items = list(response["items"])
        items.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        response["items"] = items[: (limit or self.settings.finance_default_limit)]
        response["total"] = len(items)
        return response

    def get_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        limit = limit or self.settings.finance_history_default_limit
        if self.history_store is None:
            snapshot, _ = self._get_latest_snapshot()
            return [
                {
                    "timestamp": snapshot["updated_at"],
                    "products": snapshot.get("products") or [],
                    "activities": snapshot.get("activities") or [],
                }
            ]
        history = self.history_store.fetch_recent_snapshots(limit=limit)
        if history:
            return history
        try:
            self.refresh_safe()
        except Exception:
            return []
        return self.history_store.fetch_recent_snapshots(limit=limit)

    def get_history_for_product(
        self,
        *,
        product_id: str | None = None,
        symbol: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_product_id = (product_id or "").strip().lower()
        normalized = (symbol or "").strip().lower()
        snapshots = self.get_history(limit=limit)
        if not normalized_product_id and not normalized:
            return snapshots

        filtered: list[dict[str, Any]] = []
        for snapshot in snapshots:
            products = [
                item
                for item in snapshot.get("products", [])
                if self._matches_product(item, normalized_product_id, normalized)
            ]
            activities = [
                item
                for item in snapshot.get("activities", [])
                if self._matches_related_activity(
                    item,
                    normalized_product_id=normalized_product_id,
                    normalized_symbol=normalized,
                )
            ]
            filtered.append(
                {
                    "timestamp": snapshot["timestamp"],
                    "products": products,
                    "activities": activities,
                }
            )
        return filtered

    def note_scheduler_attempt(self) -> None:
        state = load_state(self.settings.finance_cache_file)
        scheduler_state = state.get("scheduler_state") or {}
        scheduler_state["last_attempt_at"] = datetime.now(UTC).isoformat()
        state["scheduler_state"] = scheduler_state
        save_state(self.settings.finance_cache_file, state)

    def note_scheduler_success(self) -> None:
        state = load_state(self.settings.finance_cache_file)
        scheduler_state = state.get("scheduler_state") or {}
        scheduler_state["consecutive_failures"] = 0
        scheduler_state["last_success_at"] = datetime.now(UTC).isoformat()
        scheduler_state["last_error"] = None
        scheduler_state["last_error_at"] = None
        state["scheduler_state"] = scheduler_state
        save_state(self.settings.finance_cache_file, state)

    def note_scheduler_failure(self, message: str) -> None:
        state = load_state(self.settings.finance_cache_file)
        scheduler_state = state.get("scheduler_state") or {}
        scheduler_state["consecutive_failures"] = int(scheduler_state.get("consecutive_failures") or 0) + 1
        scheduler_state["last_error"] = message
        scheduler_state["last_error_at"] = datetime.now(UTC).isoformat()
        state["scheduler_state"] = scheduler_state
        save_state(self.settings.finance_cache_file, state)

    def is_refresh_due(self) -> bool:
        state = self._load_state()
        latest = state.get("latest_snapshot")
        return self._is_stale((latest or {}).get("updated_at"))

    def _get_latest_snapshot(self) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self._load_state()
        latest = state.get("latest_snapshot")
        if not latest or self._is_stale(latest.get("updated_at")):
            try:
                latest = self.refresh_safe()
                self._invalidate_state_cache()
                state = self._load_state()
            except Exception:
                self._invalidate_state_cache()
                state = self._load_state()
                latest = state.get("latest_snapshot")
                if not latest:
                    raise
        normalized_latest = self._normalize_snapshot(latest)
        if normalized_latest != latest:
            state["latest_snapshot"] = normalized_latest
            save_state(self.settings.finance_cache_file, state)
        return normalized_latest, state

    def _fetch_products(self, timestamp_ms: int) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        diagnostics: dict[str, Any] = {}
        products: list[dict[str, Any]] = []

        if self.settings.binance_api_key and self.settings.binance_api_secret:
            try:
                flexible_rows = self.client.fetch_signed_flexible_products(timestamp_ms, size=100)
                locked_rows = self.client.fetch_signed_locked_products(timestamp_ms, size=100)
                products.extend(self._map_flexible_products(flexible_rows))
                products.extend(self._map_locked_products(locked_rows))
                diagnostics["signed_sapi"] = {
                    "flexible_count": len(flexible_rows),
                    "locked_count": len(locked_rows),
                    "enabled": True,
                }
                return self._merge_products(products, []), diagnostics, "signed-sapi"
            except Exception as exc:  # noqa: BLE001
                diagnostics["signed_sapi_error"] = str(exc)

        bapi_diag = self.client.probe_public_finance_bapi()
        diagnostics["public_bapi_probe"] = bapi_diag
        return products, diagnostics, "public-finance-fallback"

    def _fetch_activities(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        articles = self.client.fetch_activity_articles(
            catalog_id=self.settings.finance_activity_catalog_id,
            page_size=self.settings.finance_activity_page_size,
        )
        details: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self.client.fetch_activity_detail, article["code"]): article
                for article in articles
            }
            for future in as_completed(futures):
                article = futures[future]
                try:
                    detail = future.result()
                except Exception as exc:  # noqa: BLE001
                    details.append(
                        {
                            "title": article.get("title", ""),
                            "activity_type": self._infer_activity_type(article.get("title", "")),
                            "participation_condition": "",
                            "reward_summary": "",
                            "reward_type": "unknown",
                            "status": "unknown",
                            "article_code": article.get("code"),
                            "publish_date": self._format_publish_date(article.get("releaseDate")),
                            "end_time": None,
                            "source": "cms-detail-error",
                            "error": str(exc),
                        }
                    )
                    continue
                details.append(self._build_activity_item(detail))

        details.sort(key=lambda item: item.get("publish_date") or "", reverse=True)
        return details, {"article_count": len(articles), "detail_count": len(details)}

    def _map_flexible_products(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in rows:
            raw_id = row.get("productId") or row.get("product_id")
            asset = row.get("asset") or raw_id or "UNKNOWN"
            apr = self._to_float(row.get("latestAnnualPercentageRate"))
            available = row.get("leftQuota") or row.get("leftPersonalQuota") or row.get("upLimit")
            items.append(
                {
                    "product_id": self._build_product_id(
                        product_type="flexible",
                        raw_id=raw_id,
                        asset=asset,
                        term_days=0,
                        product_name=f"{asset} Flexible",
                    ),
                    "product_name": f"{asset} Flexible",
                    "product_type": "flexible",
                    "asset": asset,
                    "apr": apr,
                    "term_days": 0,
                    "min_purchase_amount": row.get("minPurchaseAmount"),
                    "available_balance": available,
                    "reward_label": self._build_reward_label(asset=asset, apr=apr),
                    "reward_type": "apr",
                    "source": "signed-sapi",
                }
            )
        return items

    def _map_locked_products(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in rows:
            detail = row.get("detail") or {}
            raw_id = row.get("projectId") or detail.get("projectId") or row.get("productId")
            asset = detail.get("asset") or row.get("asset") or raw_id or "UNKNOWN"
            term_days = int(detail.get("duration") or row.get("duration") or 0)
            apr = self._to_float(detail.get("apr") or row.get("apr"))
            quota = row.get("quota") or {}
            reward_asset = detail.get("extraRewardAsset") or detail.get("rewardAsset") or asset
            reward_label = self._build_locked_reward_label(detail, reward_asset)
            items.append(
                {
                    "product_id": self._build_product_id(
                        product_type="locked",
                        raw_id=raw_id,
                        asset=asset,
                        term_days=term_days,
                        product_name=f"{asset} Locked {term_days}D" if term_days else f"{asset} Locked",
                    ),
                    "product_name": f"{asset} Locked {term_days}D" if term_days else f"{asset} Locked",
                    "product_type": "locked",
                    "asset": asset,
                    "apr": apr,
                    "term_days": term_days,
                    "min_purchase_amount": detail.get("minPurchaseAmount") or row.get("minPurchaseAmount"),
                    "available_balance": quota.get("leftPersonalQuota") or row.get("leftPersonalQuota"),
                    "reward_label": reward_label,
                    "reward_type": "apr",
                    "source": "signed-sapi",
                }
            )
        return items

    def _derive_products_from_activities(self, activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        for item in activities:
            title = item.get("title") or ""
            if not self._is_finance_activity(title, item.get("participation_condition", ""), item.get("reward_summary", "")):
                continue
            body_text = " ".join(filter(None, [title, item.get("participation_condition"), item.get("reward_summary")]))
            product_name = self._extract_product_name(title)
            apr = self._extract_apr(body_text)
            term_days = self._extract_term_days(body_text)
            min_amount = self._extract_min_amount(body_text)
            limit_amount = self._extract_limit_amount(body_text)
            reward_type = item.get("reward_type") or "apr"
            product_name = self._extract_product_name(title)
            products.append(
                {
                    "product_id": self._build_product_id(
                        product_type="activity",
                        raw_id=item.get("article_code"),
                        asset=self._extract_asset_symbol(title),
                        term_days=term_days,
                        product_name=product_name,
                    ),
                    "product_name": product_name,
                    "product_type": "activity",
                    "asset": self._extract_asset_symbol(title),
                    "apr": apr,
                    "term_days": term_days,
                    "min_purchase_amount": min_amount,
                    "available_balance": limit_amount,
                    "reward_label": item.get("reward_summary") or item.get("title"),
                    "reward_type": reward_type,
                    "source": "activity-derived",
                }
            )
        return products

    def _build_activity_item(self, detail: dict[str, Any]) -> dict[str, Any]:
        title = detail.get("title") or ""
        text = self._extract_plain_text(detail.get("body") or detail.get("contentJson") or "")
        publish_date = self._format_publish_date(detail.get("publishDate"))
        end_time = self._extract_end_time(text, publish_date)
        reward_summary = self._extract_reward_summary(title, text)
        activity = {
            "title": title,
            "activity_type": self._infer_activity_type(title),
            "participation_condition": self._extract_condition_summary(text),
            "reward_summary": reward_summary,
            "reward_type": self._infer_reward_type(reward_summary or title),
            "status": self._infer_activity_status(title, publish_date, end_time),
            "article_code": detail.get("code"),
            "publish_date": publish_date,
            "end_time": end_time,
            "source": "cms-detail",
        }
        return activity

    def _normalize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(snapshot)
        products = []
        for item in snapshot.get("products", []):
            normalized_item = dict(item)
            normalized_item["product_id"] = normalized_item.get("product_id") or self._build_product_id(
                product_type=normalized_item.get("product_type") or "unknown",
                raw_id=normalized_item.get("raw_id"),
                asset=normalized_item.get("asset"),
                term_days=int(normalized_item.get("term_days") or 0),
                product_name=normalized_item.get("product_name") or "unknown",
            )
            normalized_item["source"] = normalized_item.get("source") or self._default_product_source(
                product_type=normalized_item.get("product_type"),
            )
            products.append(normalized_item)
        normalized["products"] = products
        return normalized

    def _annotate_product(self, item: dict[str, Any]) -> dict[str, Any]:
        annotated = dict(item)
        apr = float(annotated.get("apr") or 0)
        term_days = int(annotated.get("term_days") or 0)
        source = annotated.get("source") or self._default_product_source(annotated.get("product_type"))
        redeemable = bool(
            annotated.get("redeemable")
            if annotated.get("redeemable") is not None
            else term_days == 0 or annotated.get("product_type") == "flexible"
        )
        estimated_min_requirement = annotated.get("min_purchase_amount")
        min_req_usd = self._amount_to_usd(estimated_min_requirement)
        reasons: list[str] = []
        score = 0.0

        if apr >= 8:
            score += 34
            reasons.append("APR 较高")
        elif apr >= 4:
            score += 26
            reasons.append("APR 较好")
        elif apr >= 2:
            score += 18
            reasons.append("APR 达到可参与区间")
        elif apr > 0:
            score += 10
            reasons.append("APR 可接受")

        if redeemable:
            score += 24
            reasons.append("可灵活赎回")
        elif term_days <= 30:
            score += 14
            reasons.append("期限较短")
        elif term_days <= 90:
            score += 8
            reasons.append("期限中等")
        else:
            score += 2
            reasons.append("锁定期较长")

        if source == "signed-sapi":
            score += 18
            reasons.append("官方 Simple Earn 来源")
        elif source == "activity-derived":
            score += 10
            reasons.append("活动派生机会")
        else:
            score += 6
            reasons.append("回退来源，需自行复核")

        if min_req_usd is None:
            score += 6
        elif min_req_usd <= 10:
            score += 10
            reasons.append("起投门槛低")
        elif min_req_usd <= 100:
            score += 6
            reasons.append("起投门槛适中")

        risk_hint = self._infer_product_risk_hint(
            source=source,
            product_type=annotated.get("product_type"),
            term_days=term_days,
            apr=apr,
            redeemable=redeemable,
        )
        if risk_hint == "low":
            score += 10
            reasons.append("风险相对低")
        elif risk_hint == "medium":
            score += 4
        else:
            score -= 4
            reasons.append("需关注活动或锁仓风险")

        annotated["source"] = source
        annotated["redeemable"] = redeemable
        annotated["recommendation_score"] = round(max(min(score, 100.0), 0.0), 2)
        annotated["recommendation_reason"] = reasons[:4]
        annotated["risk_hint"] = risk_hint
        annotated["estimated_min_requirement_usd"] = min_req_usd
        return annotated

    def _annotate_activity(self, item: dict[str, Any]) -> dict[str, Any]:
        annotated = dict(item)
        title = annotated.get("title") or ""
        condition = annotated.get("participation_condition") or ""
        reward_summary = annotated.get("reward_summary") or ""
        blob = " ".join([title, condition, reward_summary])
        estimated_requirement = self._extract_min_amount(blob)
        estimated_requirement_usd = self._amount_to_usd(estimated_requirement)
        reward_score, reward_reason = self._activity_reward_strength(blob)
        difficulty, difficulty_penalty, difficulty_reason = self._activity_difficulty(blob)
        restriction_info = self._activity_restrictions(blob)
        restriction_penalty = restriction_info["penalty"]
        restriction_reason = restriction_info["reason"]
        urgency, urgency_bonus, urgency_reason = self._activity_urgency(annotated.get("end_time"))

        base_score = reward_score + urgency_bonus - difficulty_penalty - restriction_penalty
        if annotated.get("status") == "active":
            base_score += 8
        elif annotated.get("status") == "expired":
            base_score -= 35

        low_barrier, low_barrier_reason = self._is_low_barrier_activity(
            estimated_requirement=estimated_requirement,
            estimated_requirement_usd=estimated_requirement_usd,
            difficulty=difficulty,
            blob=blob,
        )

        reasons = [reason for reason in [reward_reason, difficulty_reason, restriction_reason, urgency_reason, low_barrier_reason] if reason]
        annotated["score"] = round(max(min(base_score, 100.0), 0.0), 2)
        annotated["score_label"] = self._score_label(float(annotated["score"]), high=68, medium=42)
        annotated["reasons"] = reasons[:5]
        annotated["participation_difficulty"] = difficulty
        annotated["complexity_score"] = self._complexity_score(difficulty, difficulty_penalty, restriction_penalty)
        annotated["time_urgency"] = urgency
        annotated["estimated_min_requirement"] = estimated_requirement
        annotated["estimated_min_requirement_usd"] = estimated_requirement_usd
        annotated["low_barrier"] = low_barrier
        annotated["low_barrier_reason"] = low_barrier_reason
        annotated["requires_kyc"] = restriction_info["requires_kyc"]
        annotated["requires_holding"] = restriction_info["requires_holding"]
        annotated["requires_region_eligibility"] = restriction_info["requires_region_eligibility"]
        annotated["requires_trading_volume"] = restriction_info["requires_trading_volume"]
        annotated["restriction_flags"] = restriction_info["restriction_flags"]
        return annotated

    @staticmethod
    def _extract_plain_text(raw_body: str) -> str:
        if not raw_body:
            return ""

        def walk(node: Any, parts: list[str]) -> None:
            if isinstance(node, dict):
                if node.get("node") == "text":
                    text = str(node.get("text") or "").strip()
                    if text:
                        parts.append(text)
                for value in node.values():
                    walk(value, parts)
            elif isinstance(node, list):
                for value in node:
                    walk(value, parts)

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return re.sub(r"\s+", " ", raw_body).strip()

        parts: list[str] = []
        walk(parsed, parts)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    @staticmethod
    def _extract_reward_summary(title: str, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        keywords = ("reward", "apr", "prize", "voucher", "bonus", "points", "share")
        matches = [sentence for sentence in sentences if any(keyword in sentence.lower() for keyword in keywords)]
        if matches:
            return " ".join(matches[:2]).strip()
        return title

    @staticmethod
    def _extract_condition_summary(text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        keywords = ("eligible", "subscribe", "trade", "users who", "complete", "join", "during the promotion period")
        matches = [sentence for sentence in sentences if any(keyword in sentence.lower() for keyword in keywords)]
        if matches:
            return " ".join(matches[:2]).strip()
        return text[:220].strip()

    def _extract_end_time(self, text: str, publish_date: str | None) -> str | None:
        candidates: list[datetime] = []
        for match in re.findall(r"(20\d{2}-\d{2}-\d{2})", text):
            parsed = self._parse_date(match, "%Y-%m-%d")
            if parsed:
                candidates.append(parsed)
        for match in re.findall(r"([A-Z][a-z]+ \d{1,2}, 20\d{2})", text):
            parsed = self._parse_date(match, "%B %d, %Y")
            if parsed:
                candidates.append(parsed)
        if not candidates:
            return None

        end = max(candidates).replace(tzinfo=UTC)
        if publish_date:
            published = datetime.fromisoformat(publish_date)
            if end < published - timedelta(days=1):
                return None
        return end.isoformat()

    @staticmethod
    def _parse_date(value: str, fmt: str) -> datetime | None:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            return None

    def _infer_activity_status(self, title: str, publish_date: str | None, end_time: str | None) -> str:
        lower = title.lower()
        if "ended" in lower or "expired" in lower:
            return "expired"
        now = datetime.now(UTC)
        if end_time:
            return "expired" if datetime.fromisoformat(end_time) < now else "active"
        if publish_date:
            published = datetime.fromisoformat(publish_date)
            return "active" if now - published <= timedelta(days=45) else "unknown"
        return "unknown"

    @staticmethod
    def _infer_activity_type(title: str) -> str:
        lower = title.lower()
        if "earn" in lower or "apr" in lower or "flexible" in lower or "locked" in lower:
            return "finance"
        if "trading" in lower or "tournament" in lower or "competition" in lower:
            return "trading"
        if "airdrop" in lower:
            return "airdrop"
        if "wallet" in lower:
            return "wallet"
        return "activity"

    @staticmethod
    def _infer_reward_type(text: str) -> str:
        lower = text.lower()
        if "apr" in lower:
            return "apr"
        if "point" in lower:
            return "points"
        if "voucher" in lower:
            return "voucher"
        if "usdt" in lower or "usdc" in lower or "token" in lower or "reward" in lower:
            return "token"
        return "unknown"

    @staticmethod
    def _is_finance_activity(title: str, conditions: str, reward: str) -> bool:
        blob = " ".join([title, conditions, reward]).lower()
        keywords = (
            "binance earn",
            "simple earn",
            "flexible product",
            "flexible products",
            "locked product",
            "locked products",
            "apr",
            "staking",
            "subscribe to",
        )
        return any(keyword in blob for keyword in keywords)

    @staticmethod
    def _extract_asset_symbol(text: str) -> str | None:
        match = re.search(r"\b([A-Z]{2,10})\b(?: Flexible| Locked| Products| Product)", text)
        if match:
            return match.group(1)
        return None

    def _extract_product_name(self, title: str) -> str:
        match = re.search(r"(?:Binance Earn:\s*)?(.*?)(?:[–-]|$)", title)
        if match:
            return match.group(1).strip() or title
        return title

    @staticmethod
    def _extract_apr(text: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*APR", text, re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    @staticmethod
    def _extract_term_days(text: str) -> int:
        match = re.search(r"(\d{1,3})\s*(?:day|days|d)\b", text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _extract_min_amount(text: str) -> str | None:
        match = re.search(
            r"(?:minimum|min(?:imum)? purchase|min(?:imum)? subscribed amount(?: is)?)\s*[:\-]?\s*([0-9,.]+\s*[A-Z]{2,10})",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        match = re.search(r"at least\s+([0-9,.]+\s*[A-Z]{2,10})", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"with at least\s+([0-9,.]+\s*[A-Z]{2,10})", text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_limit_amount(text: str) -> str | None:
        match = re.search(r"([0-9,.]+\s*[A-Z]{2,10})\s+limit available", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"limit\s+of\s+([0-9,.]+\s*[A-Z]{2,10})", text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _build_reward_label(*, asset: str, apr: float) -> str:
        if apr > 0:
            return f"{asset} APR {apr:.2f}%"
        return f"{asset} APR"

    @staticmethod
    def _build_locked_reward_label(detail: dict[str, Any], reward_asset: str) -> str:
        apr = detail.get("apr")
        extra_apr = detail.get("extraRewardAPR")
        if apr and extra_apr:
            return f"{reward_asset} APR {apr}% + Extra {extra_apr}%"
        if apr:
            return f"{reward_asset} APR {apr}%"
        return reward_asset

    @staticmethod
    def _merge_products(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str, int], dict[str, Any]] = {}
        for item in [*primary, *secondary]:
            key = (
                item.get("product_name") or "",
                item.get("product_type") or "",
                int(item.get("term_days") or 0),
            )
            if key not in merged:
                merged[key] = item
        return list(merged.values())

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _matches_product(item: dict[str, Any], normalized_product_id: str, normalized_symbol: str) -> bool:
        product_id = (item.get("product_id") or "").strip().lower()
        product_name = (item.get("product_name") or "").strip().lower()
        asset = (item.get("asset") or "").strip().lower()
        if normalized_product_id and product_id:
            return normalized_product_id == product_id
        return bool(normalized_symbol) and normalized_symbol in {product_name, asset}

    @staticmethod
    def _matches_related_activity(
        item: dict[str, Any],
        *,
        normalized_product_id: str,
        normalized_symbol: str,
    ) -> bool:
        if normalized_product_id:
            article_code = (item.get("article_code") or "").strip().lower()
            if normalized_product_id.startswith("activity:") and article_code:
                return normalized_product_id.split("activity:", 1)[1] == article_code
            return False
        if not normalized_symbol:
            return False
        return normalized_symbol in (item.get("title") or "").lower() or normalized_symbol in (
            item.get("reward_summary") or ""
        ).lower()

    @staticmethod
    def _build_product_id(
        *,
        product_type: str,
        raw_id: str | None,
        asset: str | None,
        term_days: int,
        product_name: str,
    ) -> str:
        base = (raw_id or "").strip()
        if base:
            return f"{product_type}:{base}"

        asset_part = (asset or "unknown").strip().lower()
        name_part = re.sub(r"[^a-z0-9]+", "-", product_name.strip().lower()).strip("-")
        return f"{product_type}:{asset_part}:{term_days}:{name_part}"

    @staticmethod
    def _default_product_source(product_type: str | None) -> str:
        if product_type == "activity":
            return "activity-derived"
        if product_type in {"flexible", "locked"}:
            return "public-finance-fallback"
        return "public-finance-fallback"

    @staticmethod
    def _amount_to_usd(raw_amount: str | None) -> float | None:
        if not raw_amount:
            return None
        match = re.search(r"([0-9,.]+)\s*([A-Z]{2,10})", raw_amount)
        if not match:
            return None
        value = float(match.group(1).replace(",", ""))
        unit = match.group(2).upper()
        if unit in {"USDT", "USDC", "FDUSD", "BUSD", "RLUSD", "USD"}:
            return value
        return None

    @staticmethod
    def _infer_product_risk_hint(
        *,
        source: str,
        product_type: str | None,
        term_days: int,
        apr: float,
        redeemable: bool,
    ) -> str:
        if source == "signed-sapi" and redeemable and apr <= 8:
            return "low"
        if product_type == "locked" and term_days > 90:
            return "high"
        if source == "activity-derived" and apr >= 8:
            return "medium"
        if source == "public-finance-fallback":
            return "medium"
        return "low" if redeemable else "medium"

    @staticmethod
    def _activity_reward_strength(text: str) -> tuple[float, str | None]:
        apr = BinanceFinanceService._extract_apr(text)
        if apr >= 8:
            return 42.0, "奖励强度高，APR 突出"
        if apr >= 4:
            return 32.0, "奖励强度较高"
        if apr > 0:
            return 20.0, "带有 APR 奖励"

        reward_match = re.search(
            r"(?<![A-Za-z])([0-9][0-9,]*(?:\.\d+)?)\s*(K|M)?\s*(USDT|USDC|USD)?\b",
            text,
            re.IGNORECASE,
        )
        if reward_match:
            value = float(reward_match.group(1).replace(",", ""))
            suffix = (reward_match.group(2) or "").upper()
            if suffix == "K":
                value *= 1_000
            elif suffix == "M":
                value *= 1_000_000
            if value >= 100_000:
                return 34.0, "奖励池规模大"
            if value >= 10_000:
                return 24.0, "奖励池规模中等"
        return 12.0, "奖励信息一般"

    @staticmethod
    def _activity_difficulty(text: str) -> tuple[str, float, str | None]:
        lower = text.lower()
        if any(keyword in lower for keyword in ["leaderboard", "futures", "trade volume", "trading competition", "creatorpad"]):
            return "high", 18.0, "参与复杂度高"
        if any(keyword in lower for keyword in ["subscribe", "trade", "wallet", "holders", "net subscriptions"]):
            return "medium", 10.0, "需要完成指定参与动作"
        return "low", 4.0, "参与动作相对简单"

    @staticmethod
    def _activity_restrictions(text: str) -> dict[str, Any]:
        lower = text.lower()
        penalties = 0.0
        reasons: list[str] = []
        requires_kyc = any(keyword in lower for keyword in ["kyc", "verify", "identity verification"])
        requires_region = any(keyword in lower for keyword in ["eligible users", "selected users", "region", "jurisdiction"])
        requires_holding = any(keyword in lower for keyword in ["holders", "holding", "maintain", "vip"])
        requires_volume = any(keyword in lower for keyword in ["trade volume", "leaderboard", "net subscriptions", "ranked"])
        restriction_flags: list[str] = []

        if requires_kyc:
            penalties += 12
            reasons.append("存在 KYC/认证限制")
            restriction_flags.append("kyc")
        if requires_region:
            penalties += 8
            reasons.append("存在地区或资格限制")
            restriction_flags.append("region")
        if requires_holding:
            penalties += 6
            reasons.append("需要额外持仓或资格")
            restriction_flags.append("holding")
        if requires_volume:
            penalties += 7
            reasons.append("需要交易量/排行条件")
            restriction_flags.append("volume")
        return {
            "penalty": penalties,
            "reason": "；".join(reasons) if reasons else None,
            "requires_kyc": requires_kyc,
            "requires_holding": requires_holding,
            "requires_region_eligibility": requires_region,
            "requires_trading_volume": requires_volume,
            "restriction_flags": restriction_flags,
        }

    def _activity_urgency(self, end_time: str | None) -> tuple[str, float, str | None]:
        if not end_time:
            return "low", 2.0, "无明确截止时间"
        try:
            end = datetime.fromisoformat(end_time)
        except ValueError:
            return "low", 2.0, None
        remaining = end - datetime.now(UTC)
        if remaining <= timedelta(days=1):
            return "high", 12.0, "接近截止，时效性强"
        if remaining <= timedelta(days=3):
            return "medium", 8.0, "剩余时间较短"
        return "low", 3.0, "时间相对充足"

    @staticmethod
    def _is_low_barrier_activity(
        *,
        estimated_requirement: str | None,
        estimated_requirement_usd: float | None,
        difficulty: str,
        blob: str,
    ) -> tuple[bool, str]:
        lower = blob.lower()
        if any(keyword in lower for keyword in ["kyc", "identity verification", "vip", "leaderboard"]):
            return False, "存在额外资格或高复杂度要求"
        if estimated_requirement_usd is not None:
            if estimated_requirement_usd <= 500:
                return True, f"门槛约 {estimated_requirement_usd:.0f} USD，可视为低门槛"
            return False, f"门槛约 {estimated_requirement_usd:.0f} USD，偏高"
        if estimated_requirement:
            return False, f"存在最低参与要求：{estimated_requirement}"
        if difficulty == "low":
            return True, "无需明显资金门槛，操作简单"
        return difficulty != "high", "未发现明显大资金门槛"

    @staticmethod
    def _complexity_score(difficulty: str, difficulty_penalty: float, restriction_penalty: float) -> float:
        base = {"low": 20.0, "medium": 50.0, "high": 78.0}.get(difficulty, 50.0)
        return round(min(base + difficulty_penalty + restriction_penalty * 0.6, 100.0), 2)

    @staticmethod
    def _product_stability_sort_key(item: dict[str, Any]) -> tuple[float, int, int, float]:
        risk_order = {"low": 0, "medium": 1, "high": 2}
        return (
            risk_order.get(str(item.get("risk_hint")), 3),
            0 if item.get("redeemable") else 1,
            int(item.get("term_days") or 0),
            -float(item.get("apr") or 0),
        )

    @staticmethod
    def _score_label(score: float, *, high: float, medium: float) -> str:
        if score >= high:
            return "high"
        if score >= medium:
            return "medium"
        return "low"

    @staticmethod
    def _format_publish_date(value: Any) -> str | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat()
        try:
            return datetime.fromisoformat(str(value)).isoformat()
        except ValueError:
            return None

    def _is_stale(self, updated_at: str | None) -> bool:
        if not updated_at:
            return True
        try:
            updated = datetime.fromisoformat(updated_at)
        except ValueError:
            return True
        ttl = timedelta(seconds=self.settings.finance_refresh_interval_seconds * 2)
        return datetime.now(UTC) - updated > ttl
