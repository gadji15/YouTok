from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClipServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIDEO_WORKER_", extra="ignore")

    storage_path: str = Field(
        "/shared/storage",
        description="Shared storage root (contains projects/, clips/, transcripts/, subtitles/, exports/)",
    )

    quality_gate_enabled: bool = Field(
        False,
        description="If true, measure face/UI overlap and attempt alternate placements",
    )

    quality_gate_face_overlap_p95_threshold: float = Field(0.05, ge=0.0, le=1.0)
    quality_gate_max_attempts: int = Field(2, ge=1, le=5)

    # Part 8 — viral engine (render-time optimizations)
    viral_engine_enabled: bool = Field(
        True,
        description="If true, apply viral editing optimizations (hook/zoom/text/emojis)",
    )

    viral_hook_text_enabled: bool = Field(
        True,
        description="If true, add a short hook text overlay during the first seconds",
    )

    viral_emojis_enabled: bool = Field(
        True,
        description="If true, overlay brief emojis for high-signal keywords",
    )

    viral_max_emojis: int = Field(6, ge=0, le=20)

    viral_zoom_intensity: float = Field(0.06, ge=0.0, le=0.25)

    viral_effect_style: str = Field(
        "subtle",
        description="Viral effect style preset: subtle|strong",
    )

    log_level: str = Field("INFO")


@lru_cache(maxsize=1)
def get_clip_service_settings() -> ClipServiceSettings:
    return ClipServiceSettings()
