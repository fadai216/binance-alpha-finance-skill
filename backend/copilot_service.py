from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from alpha_monitor.service import AlphaStabilityService
from finance_monitor.service import BinanceFinanceService


class BinanceCopilotService:
    def __init__(
        self,
        alpha_service: AlphaStabilityService,
        finance_service: BinanceFinanceService,
    ) -> None:
        self.alpha_service = alpha_service
        self.finance_service = finance_service

    def build_summary(self, style: str = "balanced") -> dict[str, Any]:
        alpha_report = self.alpha_service.get_ranked_report(top=6)
        alpha_trends = self.alpha_service.get_risk_trends(limit=6)
        finance_report = self.finance_service.get_recommended_products(
            sort_by="stability" if style == "conservative" else "apr",
            order="desc",
            limit=6,
            redeemable_only=(style == "conservative"),
        )
        activity_report = self.finance_service.get_scored_activities(
            limit=6,
            low_barrier_only=(style == "conservative"),
            active_only=True,
        )

        top_alpha = self._pick_alpha(alpha_report, style)
        top_finance = self._pick_finance(finance_report["items"], style)
        top_activity = self._pick_activity(activity_report["items"], style)
        highlights = self._build_highlights(top_alpha, top_finance, top_activity, alpha_trends)

        return {
            "style": style,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "top_alpha_opportunity": top_alpha,
            "top_finance_opportunity": top_finance,
            "top_activity_opportunity": top_activity,
            "alpha_risk_trends": alpha_trends,
            "overall_highlights": highlights,
            "summary_text": self._build_summary_text(style, top_alpha, top_finance, top_activity, alpha_trends),
        }

    @staticmethod
    def _pick_alpha(report: dict[str, Any], style: str) -> dict[str, Any] | None:
        analysis = list(report.get("analysis") or [])
        if not analysis:
            return None
        if style == "aggressive":
            medium = [item for item in analysis if item.get("risk_label") in {"medium", "low"}]
            return medium[0] if medium else analysis[0]
        return report.get("most_stable") or analysis[0]

    @staticmethod
    def _pick_finance(items: list[dict[str, Any]], style: str) -> dict[str, Any] | None:
        if not items:
            return None
        if style == "conservative":
            low_risk = [item for item in items if item.get("risk_hint") == "low"]
            return low_risk[0] if low_risk else items[0]
        if style == "aggressive":
            return max(items, key=lambda item: float(item.get("apr") or 0))
        return max(items, key=lambda item: float(item.get("recommendation_score") or 0))

    @staticmethod
    def _pick_activity(items: list[dict[str, Any]], style: str) -> dict[str, Any] | None:
        if not items:
            return None
        active = [item for item in items if item.get("status") == "active"]
        pool = active or items
        if style == "conservative":
            low_barrier = [item for item in pool if item.get("low_barrier")]
            if low_barrier:
                return max(low_barrier, key=lambda item: float(item.get("score") or 0))
        return max(pool, key=lambda item: float(item.get("score") or 0))

    @staticmethod
    def _build_highlights(
        top_alpha: dict[str, Any] | None,
        top_finance: dict[str, Any] | None,
        top_activity: dict[str, Any] | None,
        alpha_trends: dict[str, Any],
    ) -> list[dict[str, Any]]:
        highlights: list[dict[str, Any]] = []
        if top_alpha:
            highlights.append(
                {
                    "type": "alpha",
                    "title": top_alpha["symbol"],
                    "reason": top_alpha.get("risk_reason") or "风险排序靠前",
                }
            )
        if top_finance:
            highlights.append(
                {
                    "type": "finance",
                    "title": top_finance["product_name"],
                    "reason": ", ".join(top_finance.get("recommendation_reason") or []) or top_finance.get("risk_hint"),
                }
            )
        if top_activity:
            highlights.append(
                {
                    "type": "activity",
                    "title": top_activity["title"],
                    "reason": ", ".join(top_activity.get("reasons") or []) or top_activity.get("score_label"),
                }
            )
        worsening = alpha_trends.get("top_worsening")
        if worsening:
            highlights.append(
                {
                    "type": "alpha-trend",
                    "title": worsening["symbol"],
                    "reason": worsening.get("trend_reason") or worsening.get("trend_label"),
                }
            )
        return highlights

    @staticmethod
    def _build_summary_text(
        style: str,
        top_alpha: dict[str, Any] | None,
        top_finance: dict[str, Any] | None,
        top_activity: dict[str, Any] | None,
        alpha_trends: dict[str, Any],
    ) -> str:
        lines = [f"今日 Binance 机会总结（{style} 风格）"]
        if top_alpha:
            lines.append(
                f"Alpha 方向优先关注 {top_alpha['symbol']}，当前风险标签 {top_alpha.get('risk_label')}，原因：{top_alpha.get('risk_reason')}。"
            )
        if top_finance:
            lines.append(
                f"理财方向优先关注 {top_finance['product_name']}，APR {top_finance.get('apr')}%，来源 {top_finance.get('source')}，风险提示 {top_finance.get('risk_hint')}。"
            )
        if top_activity:
            lines.append(
                f"活动方向优先关注《{top_activity['title']}》，评分 {top_activity.get('score')}，门槛判断 {top_activity.get('low_barrier')}。"
            )
        worsening = alpha_trends.get("top_worsening")
        if worsening:
            lines.append(
                f"风险趋势方面，{worsening['symbol']} 近期在走弱，变化原因：{worsening.get('trend_reason')}。"
            )
        lines.append("结果仅供 skill 辅助判断，参与前仍需结合地区资格、KYC 和资金规模复核。")
        return "\n".join(lines)
