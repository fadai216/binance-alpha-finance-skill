from __future__ import annotations

import logging
import time

from alpha_monitor.storage import load_state
from alpha_monitor.config import get_settings
from alpha_monitor.service import AlphaStabilityService
from finance_monitor.service import BinanceFinanceService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main() -> None:
    settings = get_settings()
    service = AlphaStabilityService(settings)
    finance_service = BinanceFinanceService(settings)
    interval = settings.refresh_interval_seconds
    logging.info("scheduler started, refresh interval=%ss", interval)

    while True:
        started_at = time.time()
        service.note_scheduler_attempt()
        try:
            report = service.refresh_safe()
            service.note_scheduler_success()
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

        sleep_for = max(0, interval - (time.time() - started_at))
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
