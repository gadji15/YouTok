from __future__ import annotations

from video_worker.config import get_settings


def test_quality_gate_env(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("VIDEO_WORKER_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("VIDEO_WORKER_QUALITY_GATE_ENABLED", "true")
    monkeypatch.setenv("VIDEO_WORKER_QUALITY_GATE_FACE_OVERLAP_P95_THRESHOLD", "0.07")
    monkeypatch.setenv("VIDEO_WORKER_QUALITY_GATE_MAX_ATTEMPTS", "3")

    s = get_settings()
    assert s.quality_gate_enabled is True
    assert abs(s.quality_gate_face_overlap_p95_threshold - 0.07) < 1e-6
    assert s.quality_gate_max_attempts == 3
