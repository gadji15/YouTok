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

    log_level: str = Field("INFO")


@lru_cache(maxsize=1)
def get_clip_service_settings() -> ClipServiceSettings:
    return ClipServiceSettings()
