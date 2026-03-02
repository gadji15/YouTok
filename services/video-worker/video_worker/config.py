from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIDEO_WORKER_", extra="ignore")

    redis_url: str = Field(..., description="Redis connection URL")
    queue_name: str = Field("video-worker", description="RQ queue name")

    # Optional API key to protect POST /jobs.
    # If set, clients must send `Authorization: Bearer <key>`.
    api_key: str = Field("", description="API key for authenticating callers to the video-worker API")

    # Optional comma-separated list of allowed callback hosts.
    # If set, callback_url.host must be in this list.
    callback_host_allowlist: str = Field(
        "",
        description="Comma-separated allowlist of callback_url hosts",
    )

    storage_path: str = Field(
        "/shared/video-worker",
        description="Shared storage path for downloaded sources and generated clips",
    )

    whisper_model: str = Field(
        "base",
        description="Whisper model name (e.g. tiny, base, small, medium)",
    )

    whisper_device: str = Field(
        "auto",
        description="Whisper device: auto, cpu, cuda, mps",
    )

    whisper_temperature: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Whisper temperature (0.0 for deterministic greedy/beam search)",
    )

    whisper_beam_size: int = Field(
        1,
        ge=1,
        le=10,
        description="Whisper beam size (used when temperature=0)",
    )

    whisper_best_of: int = Field(
        1,
        ge=1,
        le=10,
        description="Whisper best_of (used when temperature>0)",
    )

    max_clips: int = Field(5, ge=1, le=50)
    clip_min_seconds: float = Field(60.0, ge=1)
    clip_max_seconds: float = Field(180.0, ge=1)

    subtitles_enabled: bool = Field(
        True,
        description="If true, burn-in subtitles during render",
    )

    subtitle_template: str = Field(
        "modern",
        description="Subtitle template: default|modern|karaoke|modern_karaoke",
    )

    title_provider: str = Field(
        "heuristic",
        description="Title generation provider: heuristic|openai",
    )

    openai_api_key: str = Field(
        "",
        description="OpenAI API key used when title_provider=openai",
    )

    openai_model: str = Field(
        "gpt-4.1-mini",
        description="OpenAI model used when title_provider=openai",
    )

    openai_base_url: str = Field(
        "https://api.openai.com/v1",
        description="OpenAI API base URL",
    )

    target_fps: int = Field(30, ge=1, le=60)

    enable_loudnorm: bool = Field(
        False,
        description="If true, apply ffmpeg loudnorm to audio during render",
    )

    callback_timeout_seconds: float = Field(20.0, ge=1)

    callback_max_retries: int = Field(3, ge=0, le=10)
    callback_retry_backoff_seconds: float = Field(0.5, ge=0)

    download_max_retries: int = Field(2, ge=0, le=10)
    download_retry_backoff_seconds: float = Field(1.0, ge=0)

    rq_job_timeout_seconds: int = Field(60 * 45, ge=60)
    rq_result_ttl_seconds: int = Field(60 * 60, ge=0)

    log_level: str = Field("INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
