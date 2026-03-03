from __future__ import annotations

from rq import Connection, Worker

from .config import get_settings
from .logging import configure_logging, get_logger
from .redis_conn import get_redis

try:
    from .observability import configure_sentry
except ModuleNotFoundError:
    def configure_sentry(*, dsn: str, traces_sample_rate: float = 0.0) -> None:
        return


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = get_logger(service="video-worker")

    configure_sentry(dsn=settings.sentry_dsn, traces_sample_rate=settings.sentry_traces_sample_rate)

    logger.info("worker.start", queue=settings.queue_name)

    redis_conn = get_redis()
    with Connection(redis_conn):
        worker = Worker([settings.queue_name])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
