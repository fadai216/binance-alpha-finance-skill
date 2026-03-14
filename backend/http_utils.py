from __future__ import annotations

import time
from typing import Any

import requests


TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504, 520, 522, 524}


def apply_proxy(session: requests.Session, proxy_url: str | None) -> None:
    if not proxy_url:
        return
    session.proxies.update(
        {
            "http": proxy_url,
            "https": proxy_url,
        }
    )


def request_with_backoff(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: int,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_attempts: int = 4,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = session.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            if response.status_code >= 400:
                if response.status_code not in TRANSIENT_STATUS_CODES:
                    response.raise_for_status()
                raise requests.HTTPError(
                    f"transient http status {response.status_code}",
                    response=response,
                )
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                break
            sleep_for = min(0.75 * (2**attempt), 6.0)
            time.sleep(sleep_for)

    assert last_error is not None
    raise last_error
