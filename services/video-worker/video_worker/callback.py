from __future__ import annotations

from enum import Enum

import httpx
import structlog
from pydantic import BaseModel, Field

from .utils.retry import retry


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TitleCandidate(BaseModel):
    title: str
    score: float
    features: dict[str, float] | None = None


class TitleCandidates(BaseModel):
    provider: str | None = None
    description: str | None = None
    hashtags: list[str] = Field(default_factory=list)

    # Optional extended copywriting fields (Part 5).
    hooks: list[str] = Field(default_factory=list)
    analysis: dict | None = None

    candidates: list[TitleCandidate] = Field(default_factory=list)
    top3: list[str] = Field(default_factory=list)


class ClipArtifact(BaseModel):
    clip_id: str
    start_seconds: float
    end_seconds: float
    score: float
    reason: str | None = None
    title: str | None = None
    title_candidates: TitleCandidates | None = None

    # Summary of subtitle quality diagnostics (best-effort).
    quality_summary: dict | None = None

    video_path: str
    subtitles_ass_path: str | None = None
    subtitles_srt_path: str | None = None


class JobArtifacts(BaseModel):
    source_video_path: str | None = None
    audio_path: str | None = None

    transcript_json_path: str | None = None
    subtitles_srt_path: str | None = None

    clips_json_path: str | None = None

    # Additional analysis artifacts (best-effort).
    words_json_path: str | None = None
    segments_json_path: str | None = None
    source_metadata_json_path: str | None = None
    source_thumbnail_path: str | None = None

    clips: list[ClipArtifact] = Field(default_factory=list)


class JobCallbackPayload(BaseModel):
    job_id: str
    project_id: str
    status: JobStatus

    stage: str | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    message: str | None = None

    artifacts: JobArtifacts | None = None

    error: str | None = None


def post_callback(
    *,
    callback_url: str,
    callback_secret: str,
    payload: JobCallbackPayload,
    timeout_seconds: float,
    max_retries: int = 3,
    retry_backoff_seconds: float = 0.5,
    logger: structlog.BoundLogger | None = None,
) -> None:
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, httpx.RequestError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            return code in {408, 429} or (500 <= code < 600)
        return False

    def _do_post() -> None:
        response = httpx.post(
            callback_url,
            json=payload.model_dump(mode="json", exclude_none=True),
            headers={
                "X-Callback-Secret": callback_secret,
                "Accept": "application/json",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()

    retry(
        _do_post,
        should_retry=_should_retry,
        max_retries=max_retries,
        backoff_seconds=retry_backoff_seconds,
        logger=logger,
        log_event="callback.retry",
    )
