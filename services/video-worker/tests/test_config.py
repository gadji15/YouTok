from __future__ import annotations

import os

from video_worker.config import get_settings


def test_get_settings_reads_env(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("VIDEO_WORKER_REDIS_URL", "redis://localhost:6379/0")
    s = get_settings()
    assert s.redis_url.startswith("redis://")
