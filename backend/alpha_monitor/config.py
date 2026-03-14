from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Settings:
    app_name: str = "Alpha 4x Stability Monitor"
    base_url: str = os.getenv("BINANCE_BASE_URL", "https://www.binance.com")
    api_base_url: str = os.getenv("BINANCE_API_BASE_URL", "https://api.binance.com")
    alpha_points_url: str = os.getenv("BINANCE_ALPHA_POINTS_URL", "https://www.binance.com/en/alpha")
    token_list_path: str = "/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
    exchange_info_path: str = "/bapi/defi/v1/public/alpha-trade/get-exchange-info"
    klines_path: str = "/bapi/defi/v1/public/alpha-trade/klines"
    book_ticker_path: str = "/bapi/defi/v1/public/alpha-trade/book-ticker"
    finance_activity_catalog_id: int = int(os.getenv("BINANCE_FINANCE_ACTIVITY_CATALOG_ID", "93"))
    finance_activity_page_size: int = int(os.getenv("BINANCE_FINANCE_ACTIVITY_PAGE_SIZE", "10"))
    finance_default_limit: int = int(os.getenv("BINANCE_FINANCE_DEFAULT_LIMIT", "20"))
    finance_history_default_limit: int = int(os.getenv("BINANCE_FINANCE_HISTORY_DEFAULT_LIMIT", "12"))
    finance_refresh_interval_seconds: int = int(os.getenv("BINANCE_FINANCE_REFRESH_INTERVAL_SECONDS", "300"))
    binance_api_key: str = os.getenv("BINANCE_API_KEY", "")
    binance_api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_base_url: str = os.getenv("ANTHROPIC_BASE_URL", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "20"))
    refresh_interval_seconds: int = int(os.getenv("REFRESH_INTERVAL_SECONDS", "60"))
    data_window_minutes: int = int(os.getenv("DATA_WINDOW_MINUTES", "60"))
    default_top: int = int(os.getenv("DEFAULT_TOP", "6"))
    max_workers: int = int(os.getenv("ALPHA_MAX_WORKERS", "8"))
    volatility_alert_threshold: float = float(os.getenv("VOLATILITY_ALERT_THRESHOLD", "0.007"))
    enable_sqlite_persistence: bool = os.getenv("ENABLE_SQLITE_PERSISTENCE", "1") not in {"0", "false", "False"}
    user_agent: str = os.getenv(
        "BINANCE_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )
    data_dir: Path = Path(
        os.getenv(
            "ALPHA_DATA_DIR",
            str(Path(__file__).resolve().parent.parent / "data"),
        )
    )
    cors_allow_origins: list[str] = field(
        default_factory=lambda: [
            item.strip()
            for item in os.getenv(
                "CORS_ALLOW_ORIGINS",
                "http://127.0.0.1:8000,http://localhost:8000",
            ).split(",")
            if item.strip()
        ]
    )

    @property
    def cache_file(self) -> Path:
        return self.data_dir / "alpha_stability_cache.json"

    @property
    def finance_cache_file(self) -> Path:
        return self.data_dir / "binance_finance_cache.json"

    @property
    def sqlite_file(self) -> Path:
        return self.data_dir / "alpha_stability_history.sqlite3"

    @property
    def analysis_window_seconds(self) -> int:
        return self.data_window_minutes * 60


def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
