from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, HttpUrl


class JobCreateRequest(BaseModel):
    project_id: str

    # One of: youtube_url or local_video_path
    youtube_url: HttpUrl | None = None
    local_video_path: str | None = None

    callback_url: HttpUrl
    callback_secret: str

    language: Literal["fr", "en"] | None = None

    segmentation_mode: Literal["viral", "chapters"] = "viral"

    # Rendering
    output_aspect: Literal["vertical", "source"] = "vertical"

    # Originality / transformation (V1: best-effort, may be a no-op)
    originality_mode: Literal["none", "voiceover"] = "none"

    # Overrides. If omitted, the worker falls back to environment defaults.
    subtitles_enabled: bool = True
    subtitle_template: str | None = None

    clip_min_seconds: float | None = None
    clip_max_seconds: float | None = None
    max_clips: int | None = None


class JobCreateResponse(BaseModel):
    job_id: str
