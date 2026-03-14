from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from alpha_monitor.config import get_settings
from alpha_monitor.service import AlphaStabilityService
from copilot_service import BinanceCopilotService
from finance_monitor.service import BinanceFinanceService


settings = get_settings()
service = AlphaStabilityService(settings)
finance_service = BinanceFinanceService(settings)
copilot_service = BinanceCopilotService(service, finance_service)

app = FastAPI(
    title=settings.app_name,
    version="1.3.0",
    description=(
        "Binance Alpha 4×积分代币稳定性分析 API。\n\n"
        "- 自动发现当前 `mulPoint = 4` 的 Alpha 代币\n"
        "- 每分钟刷新最近 1 小时 volatility / spread / score\n"
        "- 支持新代币提醒与高波动提醒\n"
        "- 文档地址：`/docs`\n"
        "- OpenAPI：`/openapi.json`"
    ),
    openapi_tags=[
        {"name": "system", "description": "健康检查与系统状态"},
        {"name": "alpha", "description": "Alpha 4×积分代币稳定性分析"},
        {"name": "finance", "description": "币安理财产品与活动"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisItem(BaseModel):
    symbol: str = Field(description="前端展示用交易对，例如 LABUSDT")
    volatility: float = Field(description="最近 1 小时波动率")
    spread: float = Field(description="最近 1 小时平均相对价差")
    score: float = Field(description="综合评分，越低越稳定")
    market_symbol: str | None = Field(default=None, description="Binance Alpha 真实 market symbol")
    chain_name: str | None = Field(default=None, description="代币所在链")
    error: str | None = Field(default=None, description="单个代币拉取异常时的错误信息")
    risk_score: float | None = None
    risk_label: str | None = None
    abnormal_flag: bool | None = None
    risk_reason: str | None = None


class RefreshError(BaseModel):
    message: str
    updated_at: str


class SchedulerState(BaseModel):
    consecutive_failures: int = 0
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None


class StabilityResponse(BaseModel):
    analysis: list[AnalysisItem]
    alerts: list[str]
    recommendation: str
    updated_at: str
    source: str | None = None
    window_minutes: int
    total_symbols: int
    last_refresh_error: RefreshError | None = None
    diagnostics: dict[str, Any] | None = None
    scheduler_state: SchedulerState | None = None
    most_stable: AnalysisItem | None = None
    most_risky: AnalysisItem | None = None
    abnormal_symbols: list[str] | None = None


class HistoryAnalysisItem(BaseModel):
    symbol: str
    volatility: float
    spread: float
    score: float
    risk_score: float | None = None
    risk_label: str | None = None
    abnormal_flag: bool | None = None
    risk_reason: str | None = None


class HistorySnapshot(BaseModel):
    timestamp: str
    analysis: list[HistoryAnalysisItem]
    alerts: list[str]


class FinanceProductItem(BaseModel):
    product_id: str
    product_name: str
    product_type: str
    asset: str | None = None
    apr: float
    term_days: int
    min_purchase_amount: str | None = None
    available_balance: str | None = None
    reward_label: str | None = None
    reward_type: str | None = None
    source: str
    redeemable: bool | None = None
    recommendation_score: float | None = None
    recommendation_reason: list[str] | None = None
    risk_hint: str | None = None
    estimated_min_requirement_usd: float | None = None


class FinanceActivityItem(BaseModel):
    title: str
    activity_type: str
    participation_condition: str | None = None
    reward_summary: str | None = None
    reward_type: str | None = None
    status: str
    article_code: str | None = None
    publish_date: str | None = None
    end_time: str | None = None
    source: str | None = None
    score: float | None = None
    score_label: str | None = None
    reasons: list[str] | None = None
    participation_difficulty: str | None = None
    time_urgency: str | None = None
    estimated_min_requirement: str | None = None
    estimated_min_requirement_usd: float | None = None
    low_barrier: bool | None = None
    low_barrier_reason: str | None = None
    complexity_score: float | None = None
    requires_kyc: bool | None = None
    requires_holding: bool | None = None
    requires_region_eligibility: bool | None = None
    requires_trading_volume: bool | None = None
    restriction_flags: list[str] | None = None


class FinanceListResponse(BaseModel):
    items: list[FinanceProductItem]
    updated_at: str
    source: str | None = None
    total: int
    last_refresh_error: RefreshError | None = None
    diagnostics: dict[str, Any] | None = None
    scheduler_state: SchedulerState | None = None


class FinanceActivityResponse(BaseModel):
    items: list[FinanceActivityItem]
    updated_at: str
    source: str | None = None
    total: int
    last_refresh_error: RefreshError | None = None
    diagnostics: dict[str, Any] | None = None
    scheduler_state: SchedulerState | None = None


class FinanceHistorySnapshot(BaseModel):
    timestamp: str
    products: list[FinanceProductItem]
    activities: list[FinanceActivityItem]


class SummaryResponse(BaseModel):
    style: str
    updated_at: str
    top_alpha_opportunity: dict[str, Any] | None = None
    top_finance_opportunity: dict[str, Any] | None = None
    top_activity_opportunity: dict[str, Any] | None = None
    alpha_risk_trends: dict[str, Any] | None = None
    overall_highlights: list[dict[str, Any]]
    summary_text: str


class AlphaTrendItem(BaseModel):
    symbol: str
    current_risk_score: float | None = None
    current_risk_label: str | None = None
    abnormal_flag: bool | None = None
    risk_delta: float
    score_delta: float
    volatility_delta: float
    spread_delta: float
    trend_label: str
    trend_reason: str


class AlphaTrendResponse(BaseModel):
    updated_at: str
    window_snapshots: int
    items: list[AlphaTrendItem]
    top_worsening: AlphaTrendItem | None = None
    top_improving: AlphaTrendItem | None = None


EXAMPLE_RESPONSE = {
    "analysis": [
        {
            "symbol": "LABUSDT",
            "volatility": 0.0021,
            "spread": 0.0023,
            "score": 0.0022,
            "market_symbol": "ALPHA_123USDT",
            "chain_name": "BSC",
            "error": None,
        },
        {
            "symbol": "GUAUSDT",
            "volatility": 0.0030,
            "spread": 0.0029,
            "score": 0.00296,
            "market_symbol": "ALPHA_456USDT",
            "chain_name": "BSC",
            "error": None,
        },
    ],
    "alerts": ["🔔 新上线 4×积分代币: XXX", "⚠️ 波动率过高代币: YYY"],
    "recommendation": "Alpha 4×积分代币稳定性排名（最近1小时）...",
    "updated_at": "2026-03-14T05:32:59.000000+00:00",
    "source": "alpha-api-fallback",
    "window_minutes": 60,
    "total_symbols": 8,
    "last_refresh_error": None,
    "diagnostics": {
        "used_cached_discovery": False,
        "four_x_total": 8,
        "page_match_count": 0,
        "points_page": {
            "status": "waf_challenge",
            "status_code": 202,
            "waf_challenge": True,
        },
    },
    "scheduler_state": {
        "consecutive_failures": 0,
        "last_attempt_at": "2026-03-14T05:32:59.000000+00:00",
        "last_success_at": "2026-03-14T05:32:59.000000+00:00",
        "last_error": None,
        "last_error_at": None,
    },
}

EXAMPLE_HISTORY_RESPONSE = [
    {
        "timestamp": "2026-03-14T13:40:00+08:00",
        "analysis": [
            {
                "symbol": "LABUSDT",
                "volatility": 0.0021,
                "spread": 0.0023,
                "score": 0.0018,
            },
            {
                "symbol": "GUAUSDT",
                "volatility": 0.0030,
                "spread": 0.0029,
                "score": 0.0022,
            },
        ],
        "alerts": ["⚠️ 波动率过高代币: LYNUSDT"],
    }
]

EXAMPLE_FINANCE_RESPONSE = {
    "items": [
        {
            "product_id": "flexible:RLUSD",
            "product_name": "RLUSD Flexible",
            "product_type": "flexible",
            "asset": "RLUSD",
            "apr": 8.0,
            "term_days": 0,
            "min_purchase_amount": "1 RLUSD",
            "available_balance": "10000 RLUSD",
            "reward_label": "RLUSD APR 8.00%",
            "reward_type": "apr",
            "source": "activity-derived",
        },
        {
            "product_id": "locked:Axs*90",
            "product_name": "AXS Locked 90D",
            "product_type": "locked",
            "asset": "AXS",
            "apr": 1.2069,
            "term_days": 90,
            "min_purchase_amount": "0.1 AXS",
            "available_balance": "100 AXS",
            "reward_label": "AXS APR 1.2069%",
            "reward_type": "apr",
            "source": "signed-sapi",
        },
    ],
    "updated_at": "2026-03-14T05:58:33.776279+00:00",
    "source": "signed-sapi+cms-activities+activity-derived-products",
    "total": 2,
    "last_refresh_error": None,
    "diagnostics": {"products": {}, "activities": {}},
    "scheduler_state": {
        "consecutive_failures": 0,
        "last_attempt_at": "2026-03-14T05:58:00+00:00",
        "last_success_at": "2026-03-14T05:58:33+00:00",
        "last_error": None,
        "last_error_at": None,
    },
}

EXAMPLE_FINANCE_ACTIVITY_RESPONSE = {
    "items": [
        {
            "title": "Binance Earn: Enjoy Up to 8% APR with RLUSD Flexible Products – 10,000 RLUSD Limit Available!",
            "activity_type": "finance",
            "participation_condition": "During the Promotion Period, users who subscribe to RLUSD Flexible Products may enjoy up to 8% APR.",
            "reward_summary": "Users who subscribe to RLUSD Flexible Products may enjoy up to 8% APR.",
            "reward_type": "apr",
            "status": "active",
            "article_code": "65317d61d1c445f99f73a04c05233dd2",
            "publish_date": "2026-03-13T00:00:07.387000+00:00",
            "end_time": None,
            "source": "cms-detail",
        }
    ],
    "updated_at": "2026-03-14T05:58:33.776279+00:00",
    "source": "cms-activities",
    "total": 1,
    "last_refresh_error": None,
    "diagnostics": {"activities": {"article_count": 12}},
    "scheduler_state": {
        "consecutive_failures": 0,
        "last_attempt_at": "2026-03-14T05:58:00+00:00",
        "last_success_at": "2026-03-14T05:58:33+00:00",
        "last_error": None,
        "last_error_at": None,
    },
}

EXAMPLE_FINANCE_HISTORY_RESPONSE = [
    {
        "timestamp": "2026-03-14T05:58:33.776279+00:00",
        "products": [
            {
                "product_id": "activity:65317d61d1c445f99f73a04c05233dd2",
                "product_name": "RLUSD Flexible",
                "product_type": "activity",
                "asset": "RLUSD",
                "apr": 8.0,
                "term_days": 0,
                "min_purchase_amount": None,
                "available_balance": "10000 RLUSD",
                "reward_label": "Users who subscribe to RLUSD Flexible Products may enjoy up to 8% APR.",
                "reward_type": "apr",
                "source": "activity-derived",
            }
        ],
        "activities": [
            {
                "title": "Binance Earn: Enjoy Up to 8% APR with RLUSD Flexible Products – 10,000 RLUSD Limit Available!",
                "activity_type": "finance",
                "participation_condition": "During the Promotion Period, users who subscribe to RLUSD Flexible Products may enjoy up to 8% APR.",
                "reward_summary": "Users who subscribe to RLUSD Flexible Products may enjoy up to 8% APR.",
                "reward_type": "apr",
                "status": "active",
                "article_code": "65317d61d1c445f99f73a04c05233dd2",
                "publish_date": "2026-03-13T00:00:07.387000+00:00",
                "end_time": None,
                "source": "cms-detail",
            }
        ],
    }
]

EXAMPLE_ACTIVITY_SCORED_RESPONSE = {
    "items": [
        {
            "title": "Binance Earn: Enjoy Up to 8% APR with RLUSD Flexible Products – 10,000 RLUSD Limit Available!",
            "activity_type": "finance",
            "reward_summary": "Users who subscribe to RLUSD Flexible Products may enjoy up to 8% APR.",
            "reward_type": "apr",
            "status": "active",
            "score": 78.0,
            "score_label": "high",
            "reasons": ["奖励强度高，APR 突出", "参与动作相对简单", "门槛约 500 USD，可视为低门槛"],
            "participation_difficulty": "low",
            "time_urgency": "medium",
            "estimated_min_requirement": None,
            "estimated_min_requirement_usd": None,
            "low_barrier": True,
            "low_barrier_reason": "无需明显资金门槛，操作简单",
            "complexity_score": 24.0,
            "requires_kyc": False,
            "requires_holding": False,
            "requires_region_eligibility": False,
            "requires_trading_volume": False,
            "restriction_flags": []
        }
    ],
    "updated_at": "2026-03-14T05:58:33.776279+00:00",
    "source": "cms-activities",
    "total": 1
}

EXAMPLE_FINANCE_RECOMMEND_RESPONSE = {
    "items": [
        {
            "product_id": "activity:65317d61d1c445f99f73a04c05233dd2",
            "product_name": "Enjoy Up to 8% APR with RLUSD Flexible Products",
            "product_type": "activity",
            "asset": "RLUSD",
            "apr": 8.0,
            "term_days": 0,
            "source": "activity-derived",
            "redeemable": True,
            "recommendation_score": 86.0,
            "recommendation_reason": ["APR 较高", "可灵活赎回", "活动派生机会"],
            "risk_hint": "medium"
        }
    ],
    "updated_at": "2026-03-14T05:58:33.776279+00:00",
    "source": "public-finance-fallback+cms-activities+activity-derived-products",
    "total": 1
}

EXAMPLE_SUMMARY_RESPONSE = {
    "style": "balanced",
    "updated_at": "2026-03-14T06:00:00+00:00",
    "top_alpha_opportunity": {
        "symbol": "GUAUSDT",
        "risk_label": "low",
        "risk_reason": "波动率相对平稳；盘口价差较小；综合稳定性较好"
    },
    "top_finance_opportunity": {
        "product_id": "activity:65317d61d1c445f99f73a04c05233dd2",
        "product_name": "Enjoy Up to 8% APR with RLUSD Flexible Products",
        "recommendation_score": 86.0,
        "risk_hint": "medium"
    },
    "top_activity_opportunity": {
        "title": "Binance Earn: Enjoy Up to 8% APR with RLUSD Flexible Products – 10,000 RLUSD Limit Available!",
        "score": 78.0,
        "low_barrier": True
    },
    "alpha_risk_trends": {
        "top_worsening": {
            "symbol": "LYNUSDT",
            "trend_label": "worsening"
        }
    },
    "overall_highlights": [
        {
            "type": "alpha",
            "title": "GUAUSDT",
            "reason": "风险排序靠前"
        }
    ],
    "summary_text": "今日 Binance 机会总结（balanced 风格）..."
}

EXAMPLE_ALPHA_TREND_RESPONSE = {
    "updated_at": "2026-03-14T06:00:00+00:00",
    "window_snapshots": 6,
    "items": [
        {
            "symbol": "LYNUSDT",
            "current_risk_score": 78.4,
            "current_risk_label": "high",
            "abnormal_flag": True,
            "risk_delta": 12.3,
            "score_delta": 0.0012,
            "volatility_delta": 0.0021,
            "spread_delta": 0.0004,
            "trend_label": "worsening",
            "trend_reason": "整体风险上升；波动率抬升；价差扩大"
        }
    ],
    "top_worsening": {
        "symbol": "LYNUSDT",
        "current_risk_score": 78.4,
        "current_risk_label": "high",
        "abnormal_flag": True,
        "risk_delta": 12.3,
        "score_delta": 0.0012,
        "volatility_delta": 0.0021,
        "spread_delta": 0.0004,
        "trend_label": "worsening",
        "trend_reason": "整体风险上升；波动率抬升；价差扩大"
    },
    "top_improving": None
}


@app.get("/health", tags=["system"], summary="健康检查")
def health() -> dict[str, Any]:
    from alpha_monitor.storage import load_state as _load_alpha_state
    from finance_monitor.storage import load_state as _load_finance_state

    alpha_state = _load_alpha_state(settings.cache_file)
    finance_state = _load_finance_state(settings.finance_cache_file)

    alpha_report = alpha_state.get("latest_report")
    finance_snapshot = finance_state.get("latest_snapshot")
    alpha_scheduler = alpha_state.get("scheduler_state") or {}
    finance_scheduler = finance_state.get("scheduler_state") or {}

    return {
        "status": "ok",
        "alpha": {
            "updated_at": alpha_report.get("updated_at") if alpha_report else None,
            "source": alpha_report.get("source") if alpha_report else None,
            "consecutive_failures": alpha_scheduler.get("consecutive_failures", 0),
            "last_error": alpha_scheduler.get("last_error"),
        },
        "finance": {
            "updated_at": finance_snapshot.get("updated_at") if finance_snapshot else None,
            "source": finance_snapshot.get("source") if finance_snapshot else None,
            "consecutive_failures": finance_scheduler.get("consecutive_failures", 0),
            "last_error": finance_scheduler.get("last_error"),
        },
    }


@app.get(
    "/alpha/stability",
    response_model=StabilityResponse,
    tags=["alpha"],
    summary="获取 Alpha 4×积分代币稳定性分析",
    description=(
        "返回最近 1 小时分析窗口下的 4×积分代币稳定性排序、alerts 和自然语言 recommendation。"
        "接口会优先返回最新刷新结果；如果当前刷新失败且本地有缓存，会回退到最近一次缓存结果。"
    ),
    responses={
        200: {
            "description": "稳定性分析结果",
            "content": {
                "application/json": {
                    "example": EXAMPLE_RESPONSE,
                }
            },
        }
    },
)
def get_alpha_stability(
    top: int = Query(default=settings.default_top, ge=1, le=20, description="返回前 N 个稳定性最高的代币"),
) -> dict:
    return service.get_report(top=top)


@app.get(
    "/alpha/stability/history",
    response_model=list[HistorySnapshot],
    tags=["alpha"],
    summary="获取 Alpha 4×积分代币历史快照",
    description=(
        "返回最近 N 条稳定性分析快照，供前端绘制多分钟趋势图。"
        "每条快照包含 timestamp、analysis 和 alerts。"
    ),
    responses={
        200: {
            "description": "历史快照列表",
            "content": {
                "application/json": {
                    "example": EXAMPLE_HISTORY_RESPONSE,
                }
            },
        }
    },
)
def get_alpha_stability_history(
    limit: int = Query(default=12, ge=1, le=120, description="返回最近 N 条历史快照"),
) -> list[dict[str, Any]]:
    return service.get_history(limit=limit)


@app.get(
    "/alpha/stability/ranked",
    response_model=StabilityResponse,
    tags=["alpha"],
    summary="获取 Alpha 风险排序结果",
)
def get_alpha_stability_ranked(
    top: int = Query(default=settings.default_top, ge=1, le=20),
) -> dict[str, Any]:
    return service.get_ranked_report(top=top)


@app.get(
    "/alpha/stability/trends",
    response_model=AlphaTrendResponse,
    tags=["alpha"],
    summary="获取 Alpha 风险变化趋势",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_ALPHA_TREND_RESPONSE}}}},
)
def get_alpha_stability_trends(
    limit: int = Query(default=12, ge=2, le=120),
) -> dict[str, Any]:
    return service.get_risk_trends(limit=limit)


@app.get(
    "/binance/finance",
    response_model=FinanceListResponse,
    tags=["finance"],
    summary="获取币安理财产品列表",
    description="返回币安理财产品列表，支持按收益率或期限排序。",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_FINANCE_RESPONSE}}}},
)
def get_binance_finance(
    sort_by: str = Query(default="apr", pattern="^(apr|term|term_days|product_name|stability|recommendation)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    product_type: str = Query(default="all", pattern="^(all|flexible|locked|activity)$"),
    min_apr: float = Query(default=0.0, ge=0.0),
    max_term: int | None = Query(default=None, ge=0),
    redeemable_only: bool = False,
    source: str | None = Query(default=None),
    limit: int = Query(default=settings.finance_default_limit, ge=1, le=100),
) -> dict[str, Any]:
    return finance_service.get_products(
        sort_by=sort_by,
        order=order,
        product_type=product_type,
        min_apr=min_apr,
        max_term=max_term,
        redeemable_only=redeemable_only,
        source_filter=source,
        limit=limit,
    )


@app.get(
    "/binance/finance/activity",
    response_model=FinanceActivityResponse,
    tags=["finance"],
    summary="获取币安活动列表",
    description="返回币安活动信息，支持按状态和奖励类型筛选。",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_FINANCE_ACTIVITY_RESPONSE}}}},
)
def get_binance_finance_activity(
    status: str = Query(default="active", pattern="^(all|active|expired|unknown)$"),
    reward_type: str = Query(default="all", pattern="^(all|apr|points|voucher|token|unknown)$"),
    max_capital: float | None = Query(default=None, ge=0.0),
    low_barrier_only: bool = False,
    active_only: bool = False,
    limit: int = Query(default=settings.finance_default_limit, ge=1, le=100),
) -> dict[str, Any]:
    return finance_service.get_activities(
        status=status,
        reward_type=reward_type,
        max_capital=max_capital,
        low_barrier_only=low_barrier_only,
        active_only=active_only,
        limit=limit,
    )


@app.get(
    "/binance/finance/activity/scored",
    response_model=FinanceActivityResponse,
    tags=["finance"],
    summary="获取活动评分列表",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_ACTIVITY_SCORED_RESPONSE}}}},
)
def get_binance_finance_activity_scored(
    status: str = Query(default="active", pattern="^(all|active|expired|unknown)$"),
    reward_type: str = Query(default="all", pattern="^(all|apr|points|voucher|token|unknown)$"),
    max_capital: float | None = Query(default=None, ge=0.0),
    low_barrier_only: bool = False,
    active_only: bool = True,
    limit: int = Query(default=settings.finance_default_limit, ge=1, le=100),
) -> dict[str, Any]:
    return finance_service.get_scored_activities(
        status=status,
        reward_type=reward_type,
        max_capital=max_capital,
        low_barrier_only=low_barrier_only,
        active_only=active_only,
        limit=limit,
    )


@app.get(
    "/binance/finance/recommend",
    response_model=FinanceListResponse,
    tags=["finance"],
    summary="获取理财智能推荐结果",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_FINANCE_RECOMMEND_RESPONSE}}}},
)
def get_binance_finance_recommend(
    min_apr: float = Query(default=0.0, ge=0.0),
    max_term: int | None = Query(default=None, ge=0),
    redeemable_only: bool = False,
    source: str | None = Query(default=None),
    product_type: str = Query(default="all", pattern="^(all|flexible|locked|activity)$"),
    sort_by: str = Query(default="stability", pattern="^(apr|term|term_days|stability|recommendation)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=settings.finance_default_limit, ge=1, le=100),
) -> dict[str, Any]:
    return finance_service.get_recommended_products(
        min_apr=min_apr,
        max_term=max_term,
        redeemable_only=redeemable_only,
        source_filter=source,
        product_type=product_type,
        sort_by=sort_by,
        order=order,
        limit=limit,
    )


@app.get(
    "/binance/finance/history",
    response_model=list[FinanceHistorySnapshot],
    tags=["finance"],
    summary="获取币安理财和活动历史快照",
    description="返回最近 N 条理财产品和活动快照，供前端趋势图使用。",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_FINANCE_HISTORY_RESPONSE}}}},
)
def get_binance_finance_history(
    limit: int = Query(default=settings.finance_history_default_limit, ge=1, le=120),
    product_id: str | None = Query(default=None, description="按稳定产品 ID 筛选历史快照"),
    symbol: str | None = Query(default=None, description="按产品名或资产符号筛选历史快照"),
) -> list[dict[str, Any]]:
    if product_id or symbol:
        return finance_service.get_history_for_product(product_id=product_id, symbol=symbol, limit=limit)
    return finance_service.get_history(limit=limit)


@app.get(
    "/binance/copilot/summary",
    response_model=SummaryResponse,
    tags=["finance"],
    summary="获取今日 Binance 机会总结",
    responses={200: {"content": {"application/json": {"example": EXAMPLE_SUMMARY_RESPONSE}}}},
)
def get_binance_copilot_summary(
    style: str = Query(default="balanced", pattern="^(conservative|balanced|aggressive)$"),
) -> dict[str, Any]:
    return copilot_service.build_summary(style=style)
