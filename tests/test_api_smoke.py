from __future__ import annotations

from fastapi.testclient import TestClient

import backend.main as main


client = TestClient(main.app)


def test_alpha_ranked_route(monkeypatch):
    monkeypatch.setattr(
        main.service,
        "get_ranked_report",
        lambda top=6: {
            "analysis": [{"symbol": "ABCUSDT", "volatility": 0.1, "spread": 0.1, "score": 0.1, "risk_score": 10, "risk_label": "low", "abnormal_flag": False, "risk_reason": "ok"}],
            "alerts": [],
            "recommendation": "ok",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "source": "test",
            "window_minutes": 60,
            "total_symbols": 1,
            "last_refresh_error": None,
            "diagnostics": {},
            "scheduler_state": None,
            "most_stable": None,
            "most_risky": None,
            "abnormal_symbols": [],
        },
    )
    response = client.get("/alpha/stability/ranked?top=1")
    assert response.status_code == 200
    assert "analysis" in response.json()


def test_alpha_trends_route(monkeypatch):
    monkeypatch.setattr(
        main.service,
        "get_risk_trends",
        lambda limit=12: {
            "updated_at": "2026-01-01T00:00:00+00:00",
            "window_snapshots": 6,
            "items": [{"symbol": "ABCUSDT", "current_risk_score": 10, "current_risk_label": "low", "abnormal_flag": False, "risk_delta": 1, "score_delta": 0, "volatility_delta": 0, "spread_delta": 0, "trend_label": "stable", "trend_reason": "ok"}],
            "top_worsening": None,
            "top_improving": None,
        },
    )
    response = client.get("/alpha/stability/trends?limit=6")
    assert response.status_code == 200
    assert "items" in response.json()


def test_finance_recommend_route(monkeypatch):
    monkeypatch.setattr(
        main.finance_service,
        "get_recommended_products",
        lambda **_: {
            "items": [{"product_id": "p1", "product_name": "Test", "product_type": "activity", "asset": "USDT", "apr": 8.0, "term_days": 0, "source": "activity-derived"}],
            "updated_at": "2026-01-01T00:00:00+00:00",
            "source": "test",
            "total": 1,
            "last_refresh_error": None,
            "diagnostics": {},
            "scheduler_state": None,
        },
    )
    response = client.get("/binance/finance/recommend?limit=1")
    assert response.status_code == 200
    assert response.json()["items"][0]["product_id"] == "p1"


def test_activity_scored_route(monkeypatch):
    monkeypatch.setattr(
        main.finance_service,
        "get_scored_activities",
        lambda **_: {
            "items": [{"title": "Act", "activity_type": "finance", "status": "active", "score": 80, "score_label": "high"}],
            "updated_at": "2026-01-01T00:00:00+00:00",
            "source": "test",
            "total": 1,
            "last_refresh_error": None,
            "diagnostics": {},
            "scheduler_state": None,
        },
    )
    response = client.get("/binance/finance/activity/scored?limit=1")
    assert response.status_code == 200
    assert response.json()["items"][0]["score_label"] == "high"


def test_copilot_summary_route(monkeypatch):
    monkeypatch.setattr(
        main.copilot_service,
        "build_summary",
        lambda style="balanced": {
            "style": style,
            "updated_at": "2026-01-01T00:00:00+00:00",
            "top_alpha_opportunity": None,
            "top_finance_opportunity": None,
            "top_activity_opportunity": None,
            "alpha_risk_trends": {},
            "overall_highlights": [],
            "summary_text": "ok",
        },
    )
    response = client.get("/binance/copilot/summary?style=balanced")
    assert response.status_code == 200
    assert response.json()["style"] == "balanced"


def test_dashboard_route():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Binance Copilot Dashboard" in response.text
