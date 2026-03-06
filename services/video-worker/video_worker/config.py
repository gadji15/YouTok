from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIDEO_WORKER_", extra="ignore")

    redis_url: str = Field(
        "redis://redis:6379/0",
        description="Redis connection URL",
    )
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
        "/shared/storage",
        description="Shared storage root (contains projects/, clips/, transcripts/, subtitles/, exports/)",
    )

    # Optional S3-compatible storage (V2 prep). When configured, artifacts can be uploaded
    # to object storage in addition to local /shared paths.
    s3_bucket: str = Field("", description="S3 bucket name for artifact uploads (optional)")
    s3_prefix: str = Field("hikma", description="Key prefix inside the bucket")
    s3_region: str = Field("", description="AWS region (optional depending on provider)")
    s3_endpoint_url: str = Field("", description="Custom S3 endpoint URL (MinIO/Wasabi/etc)")
    s3_access_key_id: str = Field("", description="S3 access key id")
    s3_secret_access_key: str = Field("", description="S3 secret access key")

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

    whisper_initial_prompt: str = Field(
        "",
        description="Optional Whisper initial prompt to bias transcription (e.g. names, domain vocabulary)",
    )

    max_clips: int = Field(8, ge=1, le=50)
    clip_min_seconds: float = Field(15.0, ge=1)
    clip_max_seconds: float = Field(60.0, ge=1)

    subtitles_enabled: bool = Field(
        True,
        description="If true, burn-in subtitles during render",
    )

    subtitle_template: str = Field(
        "modern_karaoke",
        description=(
            "Subtitle template: default|modern|karaoke|modern_karaoke|cinematic|cinematic_karaoke|"
            "storytelling|podcast|motivation"
        ),
    )

    subtitle_max_words_per_line: int = Field(
        6,
        ge=1,
        le=12,
        description="Max words per subtitle line (Part 4: 3–6 recommended)",
    )

    subtitle_max_chars_per_line: int = Field(
        36,
        ge=10,
        le=80,
        description="Max characters per subtitle line (Part 4: keep short for mobile)",
    )

    subtitle_clip_realign_enabled: bool = Field(
        False,
        description=(
            "If true, run a best-effort per-clip word re-alignment pass (slower but can improve timing precision)"
        ),
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

    tts_model: str = Field(
        "gpt-4o-mini-tts",
        description="OpenAI TTS model used for originality_mode=voiceover",
    )

    tts_voice: str = Field(
        "marin",
        description="OpenAI TTS voice used for originality_mode=voiceover",
    )

    tts_instructions: str = Field(
        "Speak clearly, with energetic but natural short-form narration.",
        description="Prompt instructions sent to the OpenAI speech endpoint",
    )

    target_fps: int = Field(30, ge=1, le=60)

    enable_loudnorm: bool = Field(
        False,
        description="If true, apply ffmpeg loudnorm to audio during render",
    )

    stabilization_enabled: bool = Field(
        True,
        description="If true, apply a conservative video stabilization filter during render (deshake)",
    )

    visual_enhance_enabled: bool = Field(
        True,
        description="If true, apply conservative contrast/saturation/sharpening for mobile-first output",
    )

    # Quality gate (Sprint 1): auto-correct subtitle placement if it overlaps faces/UI.
    quality_gate_enabled: bool = Field(
        False,
        description="If true, re-render clips when subtitle face overlap exceeds the threshold",
    )

    quality_gate_face_overlap_p95_threshold: float = Field(
        0.05,
        ge=0.0,
        le=1.0,
        description="Max allowed p95 face overlap ratio for subtitles (measured on final rendered video)",
    )

    quality_gate_max_attempts: int = Field(
        2,
        ge=1,
        le=5,
        description="Max render attempts per clip when quality gate is enabled",
    )

    # UI safe area calibration (TikTok/Shorts/Reels).
    # Example: 0.78 means "bottom 22% is considered UI".
    ui_safe_ymin: float = Field(
        0.78,
        ge=0.0,
        le=1.0,
        description="Relative Y (0..1) from which the bottom UI zone starts",
    )

    callback_timeout_seconds: float = Field(20.0, ge=1)

    callback_max_retries: int = Field(3, ge=0, le=10)
    callback_retry_backoff_seconds: float = Field(0.5, ge=0)

    download_max_retries: int = Field(2, ge=0, le=10)
    download_retry_backoff_seconds: float = Field(1.0, ge=0)

    pipeline_stage_max_retries: int = Field(
        1,
        ge=0,
        le=3,
        description="Max retries for transient failures within a pipeline stage (transcribe/align/render)",
    )

    pipeline_stage_retry_backoff_seconds: float = Field(
        1.0,
        ge=0,
        description="Backoff (seconds) between pipeline stage retries",
    )

    audio_extract_normalize_enabled: bool = Field(
        True,
        description="If true, apply light normalization during audio extraction (pre-transcription)",
    )

    audio_extract_denoise_enabled: bool = Field(
        True,
        description="If true, apply light denoise/EQ during audio extraction (pre-transcription)",
    )

    audio_extract_max_retries: int = Field(1, ge=0, le=5)

    transcript_cleanup_provider: str = Field(
        "spellcheck",
        description="Transcript cleanup provider: none|heuristic|spellcheck|openai",
    )

    rq_job_timeout_seconds: int = Field(60 * 45, ge=60)
    rq_result_ttl_seconds: int = Field(60 * 60, ge=0)

    # Observability
    metrics_enabled: bool = Field(True, description="Expose Prometheus metrics at /metrics")
    sentry_dsn: str = Field("", description="Sentry DSN (optional)")
    sentry_traces_sample_rate: float = Field(0.0, ge=0.0, le=1.0)

    clip_service_base_url: str = Field(
        "",
        validation_alias="VIDEO_WORKER_CLIP_SERVICE_BASE_URL",
        description="Optional external clip-service base URL (if set, render stage can be delegated)",
    )

    log_level: str = Field("INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
