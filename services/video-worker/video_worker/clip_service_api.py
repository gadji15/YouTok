from __future__ import annotations

from pathlib import Path
from typing import Any
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .callback import JobCallbackPayload, JobStatus, post_callback
from .clip_service_settings import get_clip_service_settings
from .logging import configure_logging, get_logger
from .pipeline.clip import render_clips
from .pipeline.types import ClipCandidate, TranscriptSegment, WordTiming
from .redis_conn import get_redis
from .utils.errors import format_exception_short


clip_settings = get_clip_service_settings()
configure_logging(clip_settings.log_level)

app = FastAPI(title="clip-service", version="0.1")


def _resolve_within_storage_root(path_str: str) -> Path:
    p = Path(path_str)

    # Allow absolute paths only (since we operate on shared volume mounts).
    if not p.is_absolute():
        raise HTTPException(status_code=400, detail="path_must_be_absolute")

    real = p.resolve()

    root = Path(clip_settings.storage_path).resolve()
    root_prefix = str(root).rstrip("/") + "/"

    if not str(real).startswith(root_prefix):
        raise HTTPException(status_code=403, detail="path_outside_storage_root")

    return real


class RenderClipPayload(BaseModel):
    clip_id: str
    start_seconds: float
    end_seconds: float
    score: float = 0.0
    reason: str = "baseline"
    title: str | None = None
    features: dict[str, float] | None = None


class RenderTranscriptSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float | None = None


class RenderWordTiming(BaseModel):
    word: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None


class RenderRequest(BaseModel):
    # Optional but strongly recommended: enables cooperative cancellation via Redis cancel key.
    job_id: str | None = None

    # Optional: if provided, the clip-service will emit progress callbacks during rendering.
    project_id: str | None = None
    callback_url: str | None = None
    callback_secret: str | None = None

    source_video_path: str
    output_dir: str

    clips: list[RenderClipPayload]
    transcript_segments: list[RenderTranscriptSegment]

    subtitles_enabled: bool = True
    subtitle_template: str = "default"
    subtitle_max_words_per_line: int = Field(6, ge=1, le=12)
    subtitle_max_chars_per_line: int = Field(36, ge=10, le=80)
    subtitle_clip_realign_enabled: bool = False

    output_aspect: str = "vertical"
    target_fps: int = 30
    enable_loudnorm: bool = False
    stabilization_enabled: bool = True
    visual_enhance_enabled: bool = True
    ui_safe_ymin: float = 0.78

    # Text-aware crop (Option A MVP)
    text_aware_crop_enabled: bool = False
    text_aware_crop_sample_fps: float = Field(5.0, ge=0.5, le=12.0)
    text_aware_crop_padding_ratio: float = Field(0.18, ge=0.0, le=0.6)
    text_aware_crop_ocr_lang: str = "eng+fra+ara"
    text_aware_crop_ocr_conf_threshold: float = Field(60.0, ge=0.0, le=100.0)
    text_aware_crop_min_zoom: float = Field(1.0, ge=1.0, le=4.0)
    text_aware_crop_max_zoom: float = Field(1.9, ge=1.0, le=4.0)
    text_aware_crop_reading_hold_sec: float = Field(0.8, ge=0.0, le=10.0)
    text_aware_crop_debug_frames: bool = False

    # Part 8 — viral engine
    language: str | None = None
    viral_engine_enabled: bool = True
    viral_effect_style: str = "subtle"
    viral_zoom_intensity: float = Field(0.06, ge=0.0, le=0.25)
    viral_hook_text_enabled: bool = True
    viral_emojis_enabled: bool = True
    viral_max_emojis: int = Field(6, ge=0, le=20)

    word_timings: list[RenderWordTiming] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/render")
def render(req: RenderRequest) -> dict[str, Any]:
    logger = get_logger(service="clip-service")

    try:
        source_video = _resolve_within_storage_root(req.source_video_path)
        output_dir = _resolve_within_storage_root(req.output_dir)

        clips = [
            ClipCandidate(
                clip_id=c.clip_id,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
                score=c.score,
                reason=c.reason,
                title=c.title,
                features=c.features,
            )
            for c in req.clips
        ]

        transcript = [
            TranscriptSegment(
                start_seconds=s.start_seconds,
                end_seconds=s.end_seconds,
                text=s.text,
                confidence=s.confidence,
            )
            for s in req.transcript_segments
        ]

        words = (
            [
                WordTiming(
                    word=w.word,
                    start_seconds=w.start_seconds,
                    end_seconds=w.end_seconds,
                    confidence=w.confidence,
                )
                for w in (req.word_timings or [])
            ]
            if req.word_timings is not None
            else None
        )

        cancel_key = f"video-worker:cancel:{req.job_id}" if req.job_id else ""

        def _cancel_check() -> bool:
            if not cancel_key:
                return False

            # If the parent job was cancelled, abort rendering promptly.
            # render_clips/subprocess will terminate ffmpeg and propagate this error.
            if get_redis().exists(cancel_key) == 1:
                raise HTTPException(status_code=409, detail="cancelled")

            return False

        callback_enabled = (
            bool(req.callback_url)
            and bool(req.callback_secret)
            and bool(req.job_id)
            and bool(req.project_id)
        )

        last_sent_at = 0.0
        last_bucket: tuple[str, int, int] | None = None

        def _progress(evt: dict) -> None:
            nonlocal last_sent_at, last_bucket

            if not callback_enabled:
                return

            ev = str(evt.get("event") or "")
            clip_id = str(evt.get("clip_id") or "")
            idx = int(evt.get("index") or 0)
            total = int(evt.get("total") or 0)

            base = 90
            if total > 0 and idx > 0:
                base = 90 + int(round(9.0 * min(1.0, max(0.0, float((idx - 1)) / float(total)))))

            progress_percent = base

            if ev == "render.clip.progress":
                frac = float(evt.get("progress") or 0.0)
                pct = int(round(frac * 100.0))
                running = float(evt.get("running_seconds") or 0.0)

                msg = f"Rendering clip {idx}/{total} ({clip_id}) — {pct}%"
                if running > 0:
                    msg += f" ({int(running)}s)"

                if total > 0:
                    progress_percent = min(
                        99,
                        max(base, base + int(round(9.0 * min(1.0, max(0.0, frac)) / float(total)))),
                    )

                bucket = (clip_id, idx, int(pct // 5))
                now = time.time()
                if bucket == last_bucket and now - last_sent_at < 10.0:
                    return
                if now - last_sent_at < 2.0:
                    return

                last_bucket = bucket
                last_sent_at = now
            elif ev == "render.clip.heartbeat":
                running = float(evt.get("running_seconds") or 0.0)
                msg = f"Rendering clip {idx}/{total} ({clip_id}) — still running ({int(running)}s)"

                now = time.time()
                if now - last_sent_at < 30.0:
                    return

                last_sent_at = now
            else:
                msg = f"Rendering clip {idx}/{total} ({clip_id})"

                now = time.time()
                if now - last_sent_at < 1.0:
                    return

                last_sent_at = now

            try:
                post_callback(
                    callback_url=str(req.callback_url),
                    callback_secret=str(req.callback_secret),
                    payload=JobCallbackPayload(
                        job_id=str(req.job_id),
                        project_id=str(req.project_id),
                        status=JobStatus.processing,
                        stage="render_clips",
                        progress_percent=int(progress_percent),
                        message=msg,
                    ),
                    timeout_seconds=3.0,
                    max_retries=0,
                    retry_backoff_seconds=0.0,
                    logger=logger.bind(render_event=ev, clip_id=clip_id or None),
                )
            except Exception:
                logger.exception("clip_service.progress_callback_failed", render_event=ev, clip_id=clip_id)

        rendered = render_clips(
            source_video=source_video,
            transcript_segments=transcript,
            clips=clips,
            output_dir=output_dir,
            logger=logger,
            progress_callback=_progress if callback_enabled else None,
            subtitles_enabled=req.subtitles_enabled,
            subtitle_template=req.subtitle_template,
            subtitle_max_words_per_line=req.subtitle_max_words_per_line,
            subtitle_max_chars_per_line=req.subtitle_max_chars_per_line,
            subtitle_clip_realign_enabled=req.subtitle_clip_realign_enabled,
            output_aspect=req.output_aspect,
            target_fps=req.target_fps,
            enable_loudnorm=req.enable_loudnorm,
            stabilization_enabled=req.stabilization_enabled,
            visual_enhance_enabled=req.visual_enhance_enabled,
            word_timings=words,
            ui_safe_ymin=req.ui_safe_ymin,
            text_aware_crop_enabled=req.text_aware_crop_enabled,
            text_aware_crop_sample_fps=req.text_aware_crop_sample_fps,
            text_aware_crop_padding_ratio=req.text_aware_crop_padding_ratio,
            text_aware_crop_ocr_lang=req.text_aware_crop_ocr_lang,
            text_aware_crop_ocr_conf_threshold=req.text_aware_crop_ocr_conf_threshold,
            text_aware_crop_min_zoom=req.text_aware_crop_min_zoom,
            text_aware_crop_max_zoom=req.text_aware_crop_max_zoom,
            text_aware_crop_reading_hold_sec=req.text_aware_crop_reading_hold_sec,
            text_aware_crop_debug_frames=req.text_aware_crop_debug_frames,
            quality_gate_enabled=clip_settings.quality_gate_enabled,
            quality_gate_face_overlap_p95_threshold=clip_settings.quality_gate_face_overlap_p95_threshold,
            quality_gate_max_attempts=clip_settings.quality_gate_max_attempts,
            viral_engine_enabled=bool(req.viral_engine_enabled) and bool(clip_settings.viral_engine_enabled),
            viral_effect_style=req.viral_effect_style or clip_settings.viral_effect_style,
            viral_zoom_intensity=float(req.viral_zoom_intensity),
            viral_hook_text_enabled=bool(req.viral_hook_text_enabled) and bool(clip_settings.viral_hook_text_enabled),
            viral_emojis_enabled=bool(req.viral_emojis_enabled) and bool(clip_settings.viral_emojis_enabled),
            viral_max_emojis=int(req.viral_max_emojis),
            language=req.language,
            cancel_check=_cancel_check if cancel_key else None,
        )

        return {"clips": rendered}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("clip_service.render_exception")
        raise HTTPException(status_code=500, detail=format_exception_short(e))
