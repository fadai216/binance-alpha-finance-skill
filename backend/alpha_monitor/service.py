from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from .binance_alpha import BinanceAlphaClient
from .config import Settings, get_settings
from .history_store import HistoryStore
from .storage import load_state, save_state


class AlphaStabilityService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = BinanceAlphaClient(self.settings)
        self.history_store = HistoryStore(self.settings.sqlite_file) if self.settings.enable_sqlite_persistence else None

    def refresh(self) -> dict[str, Any]:
        state = load_state(self.settings.cache_file)
        now = datetime.now(timezone.utc)
        now_epoch = now.timestamp()

        tokens, source, diagnostics = self._discover_tokens(state)
        current_symbols = {token["display_symbol"] for token in tokens}
        seen_symbols = set(state.get("seen_symbols") or [])
        bootstrap_completed = bool(state.get("bootstrap_completed"))
        new_symbols = [] if not bootstrap_completed else sorted(current_symbols - seen_symbols)

        state["bootstrap_completed"] = True
        state["seen_symbols"] = sorted(seen_symbols | current_symbols)
        state["active_symbols"] = sorted(current_symbols)
        state["tracked_tokens"] = tokens
        spread_history = state.get("spread_history") or {}

        analysis: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            futures = {executor.submit(self._collect_token_metrics, token): token for token in tokens}
            for future in as_completed(futures):
                token = futures[future]
                try:
                    metrics = future.result()
                except Exception as exc:  # noqa: BLE001
                    metrics = {
                        "symbol": token["display_symbol"],
                        "volatility": 0.0,
                        "spread": 0.0,
                        "score": 999.0,
                        "market_symbol": token["market_symbol"],
                        "error": str(exc),
                    }
                history_items = spread_history.get(metrics["symbol"], [])
                history_items.append({"timestamp": now_epoch, "spread": metrics.pop("current_spread", metrics["spread"])})
                cutoff = now_epoch - self.settings.analysis_window_seconds
                history_items = [item for item in history_items if item["timestamp"] >= cutoff]
                spread_history[metrics["symbol"]] = history_items
                metrics["spread"] = self._mean_spread(history_items, metrics["spread"])
                if metrics.get("error"):
                    metrics["score"] = 999.0
                else:
                    metrics["score"] = metrics["volatility"] * 0.6 + metrics["spread"] * 0.4
                analysis.append(metrics)

        analysis.sort(key=lambda item: item["score"])
        analysis = [self._annotate_risk(item) for item in analysis]
        alerts = self._build_alerts(analysis, new_symbols)
        recommendation = self._build_recommendation(analysis, new_symbols)

        report = {
            "analysis": analysis,
            "alerts": alerts,
            "recommendation": recommendation,
            "updated_at": now.isoformat(),
            "source": source,
            "window_minutes": self.settings.data_window_minutes,
            "diagnostics": {
                **diagnostics,
                "new_symbol_count": len(new_symbols),
                "bootstrap_completed": bootstrap_completed,
            },
        }

        state["spread_history"] = spread_history
        state["latest_report"] = report
        state["last_refresh_error"] = None
        state["last_fetch_diagnostics"] = report["diagnostics"]
        if self.history_store is not None:
            try:
                self.history_store.persist_report(report)
            except Exception as exc:  # noqa: BLE001
                report["diagnostics"]["sqlite_persistence_error"] = str(exc)
                state["last_fetch_diagnostics"] = report["diagnostics"]
                state["latest_report"] = report
        save_state(self.settings.cache_file, state)
        return report

    def refresh_safe(self) -> dict[str, Any]:
        try:
            return self.refresh()
        except Exception as exc:  # noqa: BLE001
            state = load_state(self.settings.cache_file)
            state["last_refresh_error"] = {
                "message": str(exc),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            save_state(self.settings.cache_file, state)
            raise

    def get_report(self, top: int | None = None) -> dict[str, Any]:
        top = top or self.settings.default_top
        state = load_state(self.settings.cache_file)
        latest_report = state.get("latest_report")

        if not latest_report or self._is_stale(latest_report.get("updated_at")):
            try:
                latest_report = self.refresh_safe()
                state = load_state(self.settings.cache_file)
            except Exception:
                state = load_state(self.settings.cache_file)
                latest_report = state.get("latest_report")
                if not latest_report:
                    raise

        sliced_report = dict(latest_report)
        sliced_report["total_symbols"] = len(latest_report["analysis"])
        sliced_report["analysis"] = latest_report["analysis"][:top]
        sliced_report["last_refresh_error"] = state.get("last_refresh_error")
        sliced_report["diagnostics"] = latest_report.get("diagnostics") or state.get("last_fetch_diagnostics")
        sliced_report["scheduler_state"] = state.get("scheduler_state")
        sliced_report["most_stable"] = latest_report["analysis"][0] if latest_report["analysis"] else None
        sliced_report["most_risky"] = latest_report["analysis"][-1] if latest_report["analysis"] else None
        sliced_report["abnormal_symbols"] = [
            item["symbol"] for item in latest_report["analysis"] if item.get("abnormal_flag")
        ]
        return sliced_report

    def get_ranked_report(self, top: int | None = None) -> dict[str, Any]:
        report = self.get_report(top=top)
        analysis = list(report.get("analysis") or [])
        report["analysis"] = sorted(
            analysis,
            key=lambda item: float(item.get("risk_score") or 0),
        )[: len(analysis)]
        report["most_stable"] = report["analysis"][0] if report["analysis"] else None
        report["most_risky"] = max(
            analysis,
            key=lambda item: float(item.get("risk_score") or 0),
            default=None,
        )
        report["abnormal_symbols"] = [item["symbol"] for item in analysis if item.get("abnormal_flag")]
        report["risk_trends"] = self.get_risk_trends(limit=6).get("items", [])[: len(report["analysis"])]
        return report

    def get_risk_trends(self, limit: int = 12) -> dict[str, Any]:
        snapshots = self.get_history(limit=limit)
        latest_by_symbol: dict[str, dict[str, Any]] = {}
        previous_by_symbol: dict[str, dict[str, Any]] = {}

        for snapshot in snapshots:
            for item in snapshot.get("analysis", []):
                symbol = item["symbol"]
                if symbol not in latest_by_symbol:
                    latest_by_symbol[symbol] = item
                elif symbol not in previous_by_symbol:
                    previous_by_symbol[symbol] = item

        trend_items: list[dict[str, Any]] = []
        for symbol, current in latest_by_symbol.items():
            previous = previous_by_symbol.get(symbol)
            risk_delta = float(current.get("risk_score") or 0) - float((previous or {}).get("risk_score") or 0)
            score_delta = float(current.get("score") or 0) - float((previous or {}).get("score") or 0)
            volatility_delta = float(current.get("volatility") or 0) - float((previous or {}).get("volatility") or 0)
            spread_delta = float(current.get("spread") or 0) - float((previous or {}).get("spread") or 0)
            trend_items.append(
                {
                    "symbol": symbol,
                    "current_risk_score": current.get("risk_score"),
                    "current_risk_label": current.get("risk_label"),
                    "abnormal_flag": current.get("abnormal_flag"),
                    "risk_delta": round(risk_delta, 4),
                    "score_delta": round(score_delta, 6),
                    "volatility_delta": round(volatility_delta, 6),
                    "spread_delta": round(spread_delta, 6),
                    "trend_label": self._trend_label(risk_delta),
                    "trend_reason": self._trend_reason(risk_delta, volatility_delta, spread_delta),
                }
            )

        trend_items.sort(key=lambda item: abs(float(item["risk_delta"])), reverse=True)
        worsening = [item for item in trend_items if item["trend_label"] == "worsening"]
        improving = [item for item in trend_items if item["trend_label"] == "improving"]
        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "window_snapshots": len(snapshots),
            "items": trend_items,
            "top_worsening": worsening[0] if worsening else None,
            "top_improving": improving[0] if improving else None,
        }

    def get_history(self, limit: int = 12) -> list[dict[str, Any]]:
        limit = max(1, limit)
        if self.history_store is None:
            state = load_state(self.settings.cache_file)
            latest_report = state.get("latest_report")
            if not latest_report:
                return []
            return [
                {
                    "timestamp": latest_report["updated_at"],
                    "analysis": [
                        {
                            **self._annotate_risk(
                                {
                                    "symbol": item["symbol"],
                                    "volatility": item["volatility"],
                                    "spread": item["spread"],
                                    "score": item["score"],
                                }
                            ),
                        }
                        for item in latest_report.get("analysis", [])
                    ],
                    "alerts": latest_report.get("alerts", []),
                }
            ]

        snapshots = self.history_store.fetch_recent_snapshots(limit=limit)
        if snapshots:
            return self._annotate_history_risk(snapshots)

        try:
            self.refresh_safe()
        except Exception:
            return []
        snapshots = self.history_store.fetch_recent_snapshots(limit=limit)
        return self._annotate_history_risk(snapshots)

    def _collect_token_metrics(self, token: dict[str, Any]) -> dict[str, Any]:
        klines = self.client.fetch_klines(
            token["market_symbol"],
            interval="1m",
            limit=self.settings.data_window_minutes,
        )
        book_ticker = self.client.fetch_book_ticker(token["market_symbol"])
        volatility = self._compute_volatility(klines)
        current_spread = self._compute_relative_spread(book_ticker)
        return {
            "symbol": token["display_symbol"],
            "volatility": volatility,
            "spread": current_spread,
            "current_spread": current_spread,
            "score": 0.0,
            "market_symbol": token["market_symbol"],
            "chain_name": token.get("chain_name"),
        }

    def note_scheduler_attempt(self) -> None:
        state = load_state(self.settings.cache_file)
        scheduler_state = state.get("scheduler_state") or {}
        scheduler_state["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
        state["scheduler_state"] = scheduler_state
        save_state(self.settings.cache_file, state)

    def note_scheduler_success(self) -> None:
        state = load_state(self.settings.cache_file)
        scheduler_state = state.get("scheduler_state") or {}
        scheduler_state["consecutive_failures"] = 0
        scheduler_state["last_success_at"] = datetime.now(timezone.utc).isoformat()
        scheduler_state["last_error"] = None
        scheduler_state["last_error_at"] = None
        state["scheduler_state"] = scheduler_state
        save_state(self.settings.cache_file, state)

    def note_scheduler_failure(self, message: str) -> None:
        state = load_state(self.settings.cache_file)
        scheduler_state = state.get("scheduler_state") or {}
        scheduler_state["consecutive_failures"] = int(scheduler_state.get("consecutive_failures") or 0) + 1
        scheduler_state["last_error"] = message
        scheduler_state["last_error_at"] = datetime.now(timezone.utc).isoformat()
        state["scheduler_state"] = scheduler_state
        save_state(self.settings.cache_file, state)

    def _compute_volatility(self, klines: list[list[str]]) -> float:
        closes = np.array([float(entry[4]) for entry in klines if len(entry) >= 5], dtype=float)
        closes = closes[closes > 0]
        if closes.size < 2:
            return 0.0

        log_returns = np.diff(np.log(closes))
        if log_returns.size == 0:
            return 0.0
        return float(np.std(log_returns))

    @staticmethod
    def _compute_relative_spread(book_ticker: dict[str, Any]) -> float:
        bid = float(book_ticker.get("bidPrice") or 0)
        ask = float(book_ticker.get("askPrice") or 0)
        if bid <= 0 or ask <= 0:
            return 0.0
        mid = (bid + ask) / 2
        raw_spread = max(ask - bid, 0.0)
        return float(raw_spread / mid) if mid else 0.0

    @staticmethod
    def _mean_spread(history_items: list[dict[str, float]], fallback: float) -> float:
        if not history_items:
            return max(fallback, 0.0)
        values = np.array([max(float(item["spread"]), 0.0) for item in history_items], dtype=float)
        if values.size == 0:
            return max(fallback, 0.0)
        return float(np.mean(values))

    def _build_alerts(self, analysis: list[dict[str, Any]], new_symbols: list[str]) -> list[str]:
        alerts: list[str] = []
        if new_symbols:
            alerts.append(f"🔔 新上线 4×积分代币: {', '.join(new_symbols)}")

        high_vol_symbols = [
            item["symbol"]
            for item in analysis
            if item["volatility"] > self.settings.volatility_alert_threshold
        ]
        if high_vol_symbols:
            alerts.append(f"⚠️ 波动率过高代币: {', '.join(high_vol_symbols)}")

        return alerts

    def _build_recommendation(self, analysis: list[dict[str, Any]], new_symbols: list[str]) -> str:
        if not analysis:
            return (
                "Alpha 4×积分代币稳定性排名（最近1小时）暂无可用数据。\n"
                "⚠️ 风险提示：接口短时异常或无 4× 标的时，请等待下一轮刷新。"
            )

        top_symbols = [item["symbol"] for item in analysis[:3]]
        lines = [
            f"Alpha 4×积分代币稳定性排名（最近1小时）已更新，当前相对更稳的是 {', '.join(top_symbols)}。",
            (
                f"综合评分最低的是 {analysis[0]['symbol']}，"
                f"volatility={analysis[0]['volatility']:.4f}，"
                f"spread={analysis[0]['spread']:.4f}。"
            ),
        ]

        if new_symbols:
            lines.append(f"新上线标的已纳入监控：{', '.join(new_symbols)}。")

        risky = [
            item["symbol"]
            for item in analysis
            if item["volatility"] > self.settings.volatility_alert_threshold
        ]
        if risky:
            lines.append(f"短线波动偏高的代币有 {', '.join(risky)}，更适合降低追单权重。")

        lines.append("⚠️ 风险提示：4×积分代币通常上市时间短、深度变化快，低分只代表相对稳定，不代表无滑点或无回撤。")
        return "\n".join(lines)

    def _is_stale(self, updated_at: str | None) -> bool:
        if not updated_at:
            return True
        try:
            updated = datetime.fromisoformat(updated_at)
        except ValueError:
            return True
        ttl = timedelta(seconds=self.settings.refresh_interval_seconds * 2)
        return datetime.now(timezone.utc) - updated > ttl

    def _discover_tokens(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        try:
            tokens, source, diagnostics = self.client.fetch_four_x_tokens()
            if not tokens:
                raise RuntimeError("token discovery returned zero 4x symbols")
            diagnostics["used_cached_discovery"] = False
            return tokens, source, diagnostics
        except Exception as exc:  # noqa: BLE001
            cached_tokens = self._load_cached_tokens(state)
            if not cached_tokens:
                raise
            return (
                cached_tokens,
                "cached-discovery",
                {
                    "used_cached_discovery": True,
                    "cached_token_count": len(cached_tokens),
                    "discovery_error": str(exc),
                    "points_page": {
                        "status": "skipped_after_failure",
                        "waf_challenge": False,
                    },
                },
            )

    @staticmethod
    def _load_cached_tokens(state: dict[str, Any]) -> list[dict[str, Any]]:
        tokens = state.get("tracked_tokens") or []
        if not isinstance(tokens, list):
            return []
        required_keys = {"market_symbol", "display_symbol"}
        return [token for token in tokens if required_keys.issubset(token)]

    def _annotate_risk(self, item: dict[str, Any]) -> dict[str, Any]:
        annotated = dict(item)
        if annotated.get("error"):
            annotated["risk_score"] = 100.0
            annotated["risk_label"] = "high"
            annotated["abnormal_flag"] = True
            annotated["risk_reason"] = "行情抓取失败，风险不可判定"
            return annotated

        volatility = float(annotated.get("volatility") or 0)
        spread = float(annotated.get("spread") or 0)
        score = float(annotated.get("score") or 0)
        vol_component = min((volatility / max(self.settings.volatility_alert_threshold, 1e-9)) * 45, 55)
        spread_component = min((spread / 0.01) * 30, 30)
        score_component = min((score / 0.01) * 20, 20)
        risk_score = round(min(vol_component + spread_component + score_component, 100.0), 2)
        abnormal_flag = (
            volatility > self.settings.volatility_alert_threshold
            or spread > 0.008
            or risk_score >= 75
        )

        reasons: list[str] = []
        if volatility > self.settings.volatility_alert_threshold:
            reasons.append("波动率偏高")
        elif volatility < self.settings.volatility_alert_threshold / 2:
            reasons.append("波动率相对平稳")
        if spread > 0.005:
            reasons.append("盘口价差较大")
        elif spread < 0.002:
            reasons.append("盘口价差较小")
        if score > 0.004:
            reasons.append("综合稳定性偏弱")
        elif score < 0.002:
            reasons.append("综合稳定性较好")

        annotated["risk_score"] = risk_score
        annotated["risk_label"] = self._risk_label(risk_score)
        annotated["abnormal_flag"] = abnormal_flag
        annotated["risk_reason"] = "；".join(reasons[:3]) if reasons else "风险中性"
        return annotated

    @staticmethod
    def _risk_label(risk_score: float) -> str:
        if risk_score >= 70:
            return "high"
        if risk_score >= 40:
            return "medium"
        return "low"

    def _annotate_history_risk(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        annotated: list[dict[str, Any]] = []
        for snapshot in snapshots:
            annotated.append(
                {
                    "timestamp": snapshot["timestamp"],
                    "analysis": [self._annotate_risk(item) for item in snapshot.get("analysis", [])],
                    "alerts": snapshot.get("alerts", []),
                }
            )
        return annotated

    @staticmethod
    def _trend_label(risk_delta: float) -> str:
        if risk_delta >= 10:
            return "worsening"
        if risk_delta <= -10:
            return "improving"
        return "stable"

    @staticmethod
    def _trend_reason(risk_delta: float, volatility_delta: float, spread_delta: float) -> str:
        reasons: list[str] = []
        if risk_delta >= 10:
            reasons.append("整体风险上升")
        elif risk_delta <= -10:
            reasons.append("整体风险下降")
        if volatility_delta > 0:
            reasons.append("波动率抬升")
        elif volatility_delta < 0:
            reasons.append("波动率回落")
        if spread_delta > 0:
            reasons.append("价差扩大")
        elif spread_delta < 0:
            reasons.append("价差收敛")
        return "；".join(reasons[:3]) if reasons else "变化有限"
