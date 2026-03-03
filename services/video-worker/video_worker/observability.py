from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response


def configure_sentry(*, dsn: str, traces_sample_rate: float = 0.0) -> None:
    if not dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=float(traces_sample_rate or 0.0),
    )


def configure_metrics(*, app: FastAPI) -> None:
    from prometheus_client import Counter, Histogram, make_asgi_app

    request_count = Counter(
        "video_worker_http_requests_total",
        "HTTP requests received",
        ["method", "path", "status"],
    )
    request_latency = Histogram(
        "video_worker_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
    )

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next: Callable[[Request], Response]):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        path = request.url.path
        request_count.labels(request.method, path, str(response.status_code)).inc()
        request_latency.labels(request.method, path).observe(elapsed)

        return response

    app.mount("/metrics", make_asgi_app())
