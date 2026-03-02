from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import structlog


T = TypeVar("T")


def retry(
    fn: Callable[[], T],
    *,
    should_retry: Callable[[Exception], bool],
    max_retries: int,
    backoff_seconds: float,
    logger: structlog.BoundLogger | None = None,
    log_event: str = "retry",
) -> T:
    retries = max(0, int(max_retries))
    backoff = max(0.0, float(backoff_seconds))

    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:
            if attempt >= retries or not should_retry(e):
                raise

            sleep_seconds = backoff * (2**attempt)
            if logger is not None:
                logger.warning(
                    log_event,
                    attempt=attempt + 1,
                    max_retries=retries,
                    sleep_seconds=round(sleep_seconds, 3),
                    error=str(e),
                    error_type=type(e).__name__,
                )

            time.sleep(sleep_seconds)
            attempt += 1
