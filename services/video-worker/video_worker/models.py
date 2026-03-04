from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, HttpUrl


class JobCreateRequest(BaseModel):
    project_id: str
    youtube_url: HttpUrl
    callback_url: HttpUrl
    callback_secret: str

    language: Literal["fr", "en"] | None = None

    segmentation_mode: Literal["viral", "chapters"] = "viral"

    # Overrides. If omitted, the worker falls back to environment defaults.
    subtitles_enabled: bool = True
    subtitle_template: str | None = None

    clip_min_seconds: float | None = None
    clip_max_seconds: float | None = None
    max_clips: int | None = None


class JobCreateResponse(BaseModel):
    job_id: str
