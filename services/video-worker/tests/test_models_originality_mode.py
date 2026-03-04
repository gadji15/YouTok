from __future__ import annotations

from video_worker.models import JobCreateRequest


def test_job_create_request_accepts_originality_mode() -> None:
    req = JobCreateRequest(
        project_id="p1",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        callback_url="https://example.com/callback",
        callback_secret="s",
        originality_mode="voiceover",
    )

    assert req.originality_mode == "voiceover"


def test_job_create_request_defaults_originality_mode_none() -> None:
    req = JobCreateRequest(
        project_id="p1",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        callback_url="https://example.com/callback",
        callback_secret="s",
    )

    assert req.originality_mode == "none"
