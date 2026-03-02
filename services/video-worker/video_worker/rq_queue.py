from __future__ import annotations

from rq import Queue

from .config import get_settings
from .redis_conn import get_redis


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(
        name=settings.queue_name,
        connection=get_redis(),
        default_timeout=settings.rq_job_timeout_seconds,
    )
