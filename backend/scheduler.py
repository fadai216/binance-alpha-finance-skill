from __future__ import annotations

import logging
import signal
import time

from alpha_monitor.storage import load_state
from alpha_monitor.config import get_settings
from alpha_monitor.service import AlphaStabilityService
from finance_monitor.service import BinanceFinanceService
from web3_wallet_monitor.service import Web3WalletService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

_MAX_BACKOFF_SECONDS = 300  # 最多退避 5 分钟


def main() -> None:
    settings = get_settings()
    service = AlphaStabilityService(settings)
    finance_service = BinanceFinanceService(settings)
    web3_service = Web3WalletService(settings)
    interval = settings.refresh_interval_seconds
    logging.info("scheduler started, refresh interval=%ss", interval)

    running = True

    def _handle_shutdown(signum: int, _frame: object) -> None:
        nonlocal running
        logging.info("received signal %s, shutting down gracefully", signum)
        running = False

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    alpha_consecutive_failures = 0

    while running:
        started_at = time.time()
        service.note_scheduler_attempt()
        try:
            report = service.refresh_safe()
            service.note_scheduler_success()
            alpha_consecutive_failures = 0
            diagnostics = report.get("diagnostics") or {}
            page_status = (diagnostics.get("points_page") or {}).get("status")
            logging.info(
                "refresh complete | tokens=%s | alerts=%s | updated_at=%s | source=%s | page_status=%s",
                len(report["analysis"]),
                len(report["alerts"]),
                report["updated_at"],
                report.get("source"),
                page_status,
            )
        except Exception as exc:  # noqa: BLE001
            alpha_consecutive_failures += 1
            service.note_scheduler_failure(str(exc))
            state = load_state(settings.cache_file)
            cached_report = state.get("latest_report")
            scheduler_state = state.get("scheduler_state") or {}
            if cached_report:
                logging.exception(
                    "refresh failed, serving cached report | consecutive_failures=%s | cached_updated_at=%s | error=%s",
                    scheduler_state.get("consecutive_failures"),
                    cached_report.get("updated_at"),
                    exc,
                )
            else:
                logging.exception("refresh failed without cache: %s", exc)

        if finance_service.is_refresh_due():
            finance_service.note_scheduler_attempt()
            try:
                snapshot = finance_service.refresh_safe()
                finance_service.note_scheduler_success()
                logging.info(
                    "finance refresh complete | products=%s | activities=%s | updated_at=%s | source=%s",
                    len(snapshot["products"]),
                    len(snapshot["activities"]),
                    snapshot["updated_at"],
                    snapshot.get("source"),
                )
            except Exception as exc:  # noqa: BLE001
                finance_service.note_scheduler_failure(str(exc))
                logging.exception("finance refresh failed: %s", exc)

        if service.is_prune_due():
            try:
                result = service.prune_history()
                logging.info("alpha prune complete | %s", result)
            except Exception as exc:  # noqa: BLE001
                logging.exception("alpha prune failed: %s", exc)

        if finance_service.is_prune_due():
            try:
                result = finance_service.prune_history()
                logging.info("finance prune complete | %s", result)
            except Exception as exc:  # noqa: BLE001
                logging.exception("finance prune failed: %s", exc)

        if web3_service.is_refresh_due():
            try:
                web3_snapshot = web3_service.refresh_safe()
                logging.info(
                    "web3 refresh complete | pools=%s | updated_at=%s",
                    web3_snapshot["total"],
                    web3_snapshot["updated_at"],
                )
            except Exception as exc:  # noqa: BLE001
                logging.exception("web3 refresh failed: %s", exc)

        backoff = min(interval * (2 ** alpha_consecutive_failures), _MAX_BACKOFF_SECONDS)
        sleep_for = max(0, backoff - (time.time() - started_at))
        if alpha_consecutive_failures > 0:
            logging.info(
                "backoff applied | consecutive_failures=%s | sleep_for=%.1fs",
                alpha_consecutive_failures,
                sleep_for,
            )
        time.sleep(sleep_for)

    logging.info("scheduler stopped")


if __name__ == "__main__":
    main()
