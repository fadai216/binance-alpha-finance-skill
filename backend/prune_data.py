#!/usr/bin/env python3
from __future__ import annotations

import json

from alpha_monitor.config import get_settings
from alpha_monitor.service import AlphaStabilityService
from finance_monitor.service import BinanceFinanceService


def main() -> int:
    settings = get_settings()
    alpha_service = AlphaStabilityService(settings)
    finance_service = BinanceFinanceService(settings)
    alpha_result = alpha_service.prune_history()
    finance_result = finance_service.prune_history()
    print(
        json.dumps(
            {
                "alpha": alpha_result,
                "finance": finance_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
