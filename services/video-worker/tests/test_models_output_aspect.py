from __future__ import annotations

from video_worker.models import JobCreateRequest


def test_job_create_request_accepts_output_aspect() -> None:
    req = JobCreateRequest(
        project_id="p1",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        callback_url="https://example.com/callback",
        callback_secret="s",
        output_aspect="source",
    )

    assert req.output_aspect == "source"


def test_job_create_request_defaults_output_aspect_vertical() -> None:
    req = JobCreateRequest(
        project_id="p1",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        callback_url="https://example.com/callback",
        callback_secret="s",
    )

    assert req.output_aspect == "vertical"
