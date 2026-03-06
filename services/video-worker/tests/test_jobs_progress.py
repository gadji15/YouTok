from __future__ import annotations

import structlog

from video_worker.callback import JobStatus
from video_worker.jobs import _best_effort_progress_callback
from video_worker.pipeline.context import JobContext


def test_best_effort_progress_callback_posts_expected_payload(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    def fake_post_callback(
        *,
        callback_url: str,
        callback_secret: str,
        payload,
        timeout_seconds: float,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        logger=None,
    ) -> None:
        seen["callback_url"] = callback_url
        seen["callback_secret"] = callback_secret
        seen["payload"] = payload
        seen["timeout_seconds"] = timeout_seconds
        seen["max_retries"] = max_retries
        seen["retry_backoff_seconds"] = retry_backoff_seconds

    monkeypatch.setattr("video_worker.jobs.post_callback", fake_post_callback)

    ctx = JobContext(
        job_id="job_1",
        project_id="proj_1",
        youtube_url="https://youtube.test/watch?v=abc",
        callback_url="https://example.test/callback",
        callback_secret="secret",
        storage_root=tmp_path,
    )

    _best_effort_progress_callback(
        ctx=ctx,
        stage="download",
        progress_percent=10,
        message="Downloading source video",
        timeout_seconds=12.5,
        max_retries=2,
        retry_backoff_seconds=0.1,
        logger=structlog.get_logger(),
    )

    # Checkpoint written for resume support
    assert ctx.pipeline_state_path.exists()

    assert seen["callback_url"] == "https://example.test/callback"
    assert seen["callback_secret"] == "secret"

    payload = seen["payload"]
    assert payload.status == JobStatus.processing
    assert payload.stage == "download"
    assert payload.progress_percent == 10
    assert payload.message == "Downloading source video"
