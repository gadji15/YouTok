from __future__ import annotations

from pathlib import Path

import json
import shutil

import structlog

from .callback import ClipArtifact, JobArtifacts, JobCallbackPayload, JobStatus, post_callback
from .config import get_settings
from .logging import get_logger
from .pipeline.audio import extract_audio_wav
from .pipeline.chapters import build_chapter_clips, build_sequential_clips, get_youtube_chapters
from .pipeline.clip import render_clips
from .pipeline.voiceover import build_voiceover_overrides
from .pipeline.context import JobContext
from .pipeline.download import download_youtube_video
from .pipeline.segment import load_clips_json, segment_candidates, write_clips_json
from .pipeline.subtitles import write_srt
from .pipeline.title_generator import generate_title_candidates_for_clip
from .pipeline.transcribe import load_transcript_json, transcribe_audio, write_transcript_json
from .pipeline.transcript_cleanup import cleanup_transcript_segments
from .pipeline.transcript_normalize import normalize_transcript_segments
from .pipeline.word_alignment import (
    align_words_with_whisperx,
    approximate_words_from_segments,
    load_words_json,
    write_words_json,
)
from .redis_conn import get_redis
from .utils.errors import format_exception_short
from .utils.ffprobe import probe_video
from .utils.files import atomic_write_text
from .utils.retry import retry


class JobCancelledError(RuntimeError):
    pass


def _load_title_candidates_json(path: Path) -> dict[str, dict] | None:
    if not path.exists() or path.stat().st_size <= 0:
        return None

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None

    clips = raw.get("clips")
    if not isinstance(clips, dict):
        return None

    out: dict[str, dict] = {}
    for k, v in clips.items():
        if isinstance(k, str) and k and isinstance(v, dict):
            out[k] = v

    return out


def _write_title_candidates_json(*, path: Path, title_candidates_by_clip_id: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(
            {
                "clips": title_candidates_by_clip_id,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


def _ensure_title_candidates_for_clips(
    *,
    clips,
    segments,
    language: str | None,
    used_chapters: bool,
    provider: str,
    openai_api_key: str | None,
    openai_model: str,
    openai_base_url: str | None,
    logger: structlog.BoundLogger,
    existing: dict[str, dict] | None = None,
    generate_fn=generate_title_candidates_for_clip,
) -> tuple[dict[str, dict], list]:
    title_candidates_by_clip_id: dict[str, dict] = dict(existing or {})

    updated_clips = []

    for c in clips:
        clip_id = str(getattr(c, "clip_id", "") or "")
        if not clip_id:
            updated_clips.append(c)
            continue

        payload = title_candidates_by_clip_id.get(clip_id)
        if not isinstance(payload, dict):
            res = generate_fn(
                clip=c,
                segments=segments,
                language=language,
                provider=provider,
                openai_api_key=openai_api_key,
                openai_model=openai_model,
                openai_base_url=openai_base_url,
                logger=logger.bind(clip_id=clip_id),
            )

            payload = res.to_payload()
            title_candidates_by_clip_id[clip_id] = payload

            if used_chapters and getattr(c, "title", None):
                best_title = getattr(c, "title")
            else:
                best_title = res.candidates[0].title if res.candidates else getattr(c, "title", None)

            updated_clips.append(
                type(c)(
                    clip_id=c.clip_id,
                    start_seconds=c.start_seconds,
                    end_seconds=c.end_seconds,
                    score=c.score,
                    reason=c.reason,
                    title=best_title,
                    features=getattr(c, "features", None),
                )
            )
            continue

        # Resume path: keep existing title on the clip to ensure deterministic outputs.
        updated_clips.append(c)

    return title_candidates_by_clip_id, updated_clips


def _best_effort_callback(
    *,
    ctx: JobContext,
    payload: JobCallbackPayload,
    timeout_seconds: float,
    max_retries: int,
    retry_backoff_seconds: float,
    logger: structlog.BoundLogger,
) -> None:
    try:
        post_callback(
            callback_url=ctx.callback_url,
            callback_secret=ctx.callback_secret,
            payload=payload,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            logger=logger,
        )
    except Exception:
        logger.exception("callback.post_failed", status=payload.status)


def _best_effort_progress_callback(
    *,
    ctx: JobContext,
    stage: str,
    progress_percent: int,
    message: str,
    timeout_seconds: float,
    max_retries: int,
    retry_backoff_seconds: float,
    logger: structlog.BoundLogger,
) -> None:
    logger.info("job.stage", stage=stage, progress_percent=progress_percent, message=message)

    # Checkpoint (Part 2): persist the last known stage/progress so the pipeline can resume.
    try:
        ctx.pipeline_state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            ctx.pipeline_state_path,
            json.dumps(
                {
                    "job_id": ctx.job_id,
                    "project_id": ctx.project_id,
                    "stage": stage,
                    "progress_percent": int(progress_percent),
                    "message": message,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception:
        logger.exception("checkpoint.write_failed")

    _best_effort_callback(
        ctx=ctx,
        payload=JobCallbackPayload(
            job_id=ctx.job_id,
            project_id=ctx.project_id,
            status=JobStatus.processing,
            stage=stage,
            progress_percent=progress_percent,
            message=message,
        ),
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        logger=logger,
    )


def process_job(
    job_id: str,
    project_id: str,
    youtube_url: str,
    local_video_path: str | None,
    callback_url: str,
    callback_secret: str,
    language: str | None = None,
    segmentation_mode: str | None = None,
    subtitles_enabled: bool | None = None,
    subtitle_template: str | None = None,
    clip_min_seconds: float | None = None,
    clip_max_seconds: float | None = None,
    max_clips: int | None = None,
    originality_mode: str | None = None,
    output_aspect: str | None = None,
) -> dict:
    settings = get_settings()
    logger = get_logger(service="video-worker", job_id=job_id, project_id=project_id)

    effective_segmentation_mode = (segmentation_mode or "viral").strip().lower()
    effective_originality_mode = (originality_mode or "none").strip().lower()
    effective_output_aspect = (output_aspect or "vertical").strip().lower()

    if effective_output_aspect not in {"vertical", "source"}:
        effective_output_aspect = "vertical"

    if effective_originality_mode not in {"none", "voiceover"}:
        effective_originality_mode = "none"

    if effective_originality_mode == "voiceover" and not settings.openai_api_key:
        logger.warning("voiceover.disabled_missing_openai_key")
        effective_originality_mode = "none"

    effective_min_seconds = settings.clip_min_seconds if clip_min_seconds is None else float(clip_min_seconds)
    effective_max_seconds = settings.clip_max_seconds if clip_max_seconds is None else float(clip_max_seconds)

    # Product constraint (viral mode): clips must be 15–60 seconds (TikTok/Reels-ready).
    if effective_segmentation_mode == "viral":
        effective_min_seconds = max(15.0, min(60.0, effective_min_seconds))
        effective_max_seconds = max(effective_min_seconds, min(60.0, effective_max_seconds))
    else:
        # Chapter/slice mode still uses clip_max_seconds as the slice size.
        effective_min_seconds = max(15.0, min(60.0, effective_min_seconds))
        effective_max_seconds = max(effective_min_seconds, min(60.0, effective_max_seconds))

    effective_max_clips = settings.max_clips if max_clips is None else int(max_clips)
    if effective_segmentation_mode == "viral":
        effective_max_clips = max(5, min(12, effective_max_clips))
    else:
        effective_max_clips = max(1, min(12, effective_max_clips))

    effective_subtitles_enabled = (
        settings.subtitles_enabled if subtitles_enabled is None else bool(subtitles_enabled)
    )
    effective_subtitle_template = settings.subtitle_template if not subtitle_template else subtitle_template

    ctx = JobContext(
        job_id=job_id,
        project_id=project_id,
        youtube_url=youtube_url,
        callback_url=callback_url,
        callback_secret=callback_secret,
        storage_root=Path(settings.storage_path),
    )

    ctx.ensure_dirs()

    def raise_if_cancelled() -> None:
        try:
            if get_redis().exists(f"video-worker:cancel:{job_id}") == 1:
                raise JobCancelledError("job cancelled")
        except JobCancelledError:
            raise
        except Exception:
            return

    def run_with_stage_retries(stage_name: str, fn):
        def _wrapped():
            raise_if_cancelled()
            return fn()

        def _should_retry(exc: Exception) -> bool:
            return not isinstance(exc, JobCancelledError)

        return retry(
            _wrapped,
            should_retry=_should_retry,
            max_retries=settings.pipeline_stage_max_retries,
            backoff_seconds=settings.pipeline_stage_retry_backoff_seconds,
            logger=logger.bind(stage=stage_name),
            log_event="pipeline_stage.retry",
        )

    current_stage = "start"
    current_progress = 0

    raise_if_cancelled()

    _best_effort_progress_callback(
        ctx=ctx,
        stage=current_stage,
        progress_percent=current_progress,
        message="Starting job",
        timeout_seconds=settings.callback_timeout_seconds,
        max_retries=settings.callback_max_retries,
        retry_backoff_seconds=settings.callback_retry_backoff_seconds,
        logger=logger,
    )

    try:
        raise_if_cancelled()

        current_stage = "download"
        current_progress = 10

        if local_video_path:
            download_message = "Ingesting local source video"
        else:
            download_message = "Downloading source video"

        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message=download_message,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        if local_video_path:
            src = Path(local_video_path)
            if not src.exists() or not src.is_file():
                raise RuntimeError(f"local_video_path_not_found: {local_video_path}")

            ctx.source_video_path.parent.mkdir(parents=True, exist_ok=True)

            if not (ctx.source_video_path.exists() and ctx.source_video_path.stat().st_size > 0):
                shutil.copyfile(src, ctx.source_video_path)

            # Best-effort metadata from ffprobe.
            if not ctx.source_metadata_json_path.exists():
                try:
                    info = probe_video(ctx.source_video_path)
                    atomic_write_text(
                        ctx.source_metadata_json_path,
                        json.dumps(
                            {
                                "source": "local_file",
                                "local_video_path": str(src),
                                "duration": float(info.duration_seconds),
                                "width": int(info.width),
                                "height": int(info.height),
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                except Exception:
                    logger.exception("source_metadata.write_failed")
        else:
            download_youtube_video(
                youtube_url=ctx.youtube_url,
                output_path=ctx.source_video_path,
                logger=logger,
                max_retries=settings.download_max_retries,
                retry_backoff_seconds=settings.download_retry_backoff_seconds,
                metadata_json_path=ctx.source_metadata_json_path,
                thumbnail_path=ctx.source_thumbnail_path,
            )

        raise_if_cancelled()

        current_stage = "extract_audio"
        current_progress = 20
        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Extracting audio",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )
        if ctx.audio_path.exists() and ctx.audio_path.stat().st_size > 0:
            logger.info("extract_audio.skip_existing", path=str(ctx.audio_path))
        else:
            extract_audio_wav(
                input_video=ctx.source_video_path,
                output_wav=ctx.audio_path,
                logger=logger,
                normalize=settings.audio_extract_normalize_enabled,
                denoise=settings.audio_extract_denoise_enabled,
                max_retries=settings.audio_extract_max_retries,
            )

        raise_if_cancelled()

        current_stage = "transcribe"
        current_progress = 50
        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Transcribing audio",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )
        default_prompt = ""
        if (language or "").strip().lower() == "fr" and not settings.whisper_initial_prompt.strip():
            default_prompt = (
                "Noms propres: Ibrahim, Muhammad. "
                "Formules: sallallahu alayhi wa sallam; alayhi salam; alayhi wa sallam. "
                "Mots: subhanallah, alhamdulillah, allahu akbar."
            )

        initial_prompt = (settings.whisper_initial_prompt.strip() or default_prompt).strip() or None

        loaded_transcript = False
        segments = []

        if ctx.transcript_json_path.exists() and ctx.transcript_json_path.stat().st_size > 0:
            try:
                segments = load_transcript_json(path=ctx.transcript_json_path)
                loaded_transcript = len(segments) > 0
                if loaded_transcript:
                    logger.info("transcribe.skip_existing", path=str(ctx.transcript_json_path), segment_count=len(segments))
            except Exception:
                logger.exception("transcribe.load_failed_retranscribe")
                loaded_transcript = False

        if not loaded_transcript:
            def _do_transcribe() -> list:
                segs = transcribe_audio(
                    audio_path=ctx.audio_path,
                    model_name=settings.whisper_model,
                    logger=logger,
                    language=language,
                    initial_prompt=initial_prompt,
                    device=settings.whisper_device,
                    temperature=settings.whisper_temperature,
                    beam_size=settings.whisper_beam_size,
                    best_of=settings.whisper_best_of,
                )

                segs = normalize_transcript_segments(segments=segs)

                segs = cleanup_transcript_segments(
                    segments=segs,
                    language=language,
                    provider=settings.transcript_cleanup_provider,
                    openai_api_key=settings.openai_api_key,
                    openai_model=settings.openai_model,
                    openai_base_url=settings.openai_base_url,
                    logger=logger,
                )

                write_transcript_json(
                    segments=segs,
                    output_path=ctx.transcript_json_path,
                    meta={
                        "model": settings.whisper_model,
                        "requested_language": language,
                        "initial_prompt": initial_prompt,
                        "cleanup_provider": settings.transcript_cleanup_provider,
                    },
                )

                return segs

            segments = run_with_stage_retries("transcribe", _do_transcribe)

        # Always (re)write SRT: cheap and ensures downstream consistency.
        write_srt(segments=segments, output_path=ctx.subtitles_srt_path)

        raise_if_cancelled()

        current_stage = "align"
        current_progress = 60
        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Aligning words (forced alignment)",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        loaded_words = False
        words = None

        if ctx.words_json_path.exists() and ctx.words_json_path.stat().st_size > 0:
            try:
                loaded = load_words_json(ctx.words_json_path)
                if loaded:
                    words = loaded
                    loaded_words = True
                    logger.info("align.skip_existing", path=str(ctx.words_json_path), word_count=len(words))
            except Exception:
                logger.exception("align.load_failed_realign")

        if not loaded_words:
            def _do_align():
                w = align_words_with_whisperx(
                    audio_path=ctx.audio_path,
                    segments=segments,
                    language=language,
                    logger=logger,
                    device=settings.whisper_device,
                )
                if w is None:
                    w = approximate_words_from_segments(segments=segments)
                    logger.info("align.fallback_approximate", word_count=len(w))

                write_words_json(words=w, output_path=ctx.words_json_path)
                return w

            words = run_with_stage_retries("align", _do_align)

        raise_if_cancelled()

        current_stage = "segment"
        current_progress = 70

        used_chapters = False

        segment_message = "Selecting clip candidates"
        if effective_segmentation_mode == "chapters":
            segment_message = "Building chapters/slices"

        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message=segment_message,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        loaded_clips = False
        clips = []

        if ctx.clips_json_path.exists() and ctx.clips_json_path.stat().st_size > 0:
            try:
                clips = load_clips_json(path=ctx.clips_json_path)
                loaded_clips = len(clips) > 0
                if loaded_clips:
                    logger.info("segment.skip_existing", path=str(ctx.clips_json_path), clip_count=len(clips))
            except Exception:
                logger.exception("segment.load_failed_resegment")
                loaded_clips = False

        if not loaded_clips:
            if effective_segmentation_mode == "chapters":
                duration_seconds = float(probe_video(ctx.source_video_path).duration_seconds)

                chapters = []
                if ctx.youtube_url:
                    chapters = get_youtube_chapters(
                        youtube_url=ctx.youtube_url,
                        logger=logger,
                        video_path=ctx.source_video_path,
                    )

                if chapters:
                    used_chapters = True
                    clips = build_chapter_clips(
                        chapters=chapters,
                        segments=segments,
                        max_seconds=effective_max_seconds,
                        min_seconds=effective_min_seconds,
                    )
                else:
                    clips = build_sequential_clips(
                        duration_seconds=duration_seconds,
                        max_seconds=effective_max_seconds,
                        min_seconds=effective_min_seconds,
                    )
            else:
                clips = segment_candidates(
                    segments=segments,
                    min_seconds=effective_min_seconds,
                    max_seconds=effective_max_seconds,
                    max_clips=effective_max_clips,
                    audio_path=ctx.audio_path,
                    video_path=ctx.source_video_path,
                    words=words,
                    language=language,
                )

        # Resume-safe: if we're in chapters mode and clips already carry titles, keep them.
        if effective_segmentation_mode == "chapters" and any(getattr(c, "title", None) for c in clips):
            used_chapters = True

        raise_if_cancelled()

        current_stage = "titles"
        current_progress = 80

        titles_message = "Generating viral titles"
        if effective_segmentation_mode == "chapters":
            titles_message = "Generating titles"

        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message=titles_message,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        existing_title_candidates = _load_title_candidates_json(ctx.title_candidates_json_path)

        title_candidates_by_clip_id, updated_clips = _ensure_title_candidates_for_clips(
            clips=clips,
            segments=segments,
            language=language,
            used_chapters=used_chapters,
            provider=settings.title_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
            logger=logger,
            existing=existing_title_candidates,
        )

        clips = updated_clips
        write_clips_json(clips=clips, output_path=ctx.clips_json_path)
        _write_title_candidates_json(
            path=ctx.title_candidates_json_path,
            title_candidates_by_clip_id=title_candidates_by_clip_id,
        )

        # Analysis output: segments with text + word timestamps (used downstream for subtitles/UI).
        def _collect_text_window(start: float, end: float) -> str:
            parts: list[str] = []
            for s in segments:
                if s.end_seconds <= start:
                    continue
                if s.start_seconds >= end:
                    break
                txt = s.text.strip()
                if txt:
                    parts.append(txt)
            return " ".join(parts).strip()

        segments_payload = {
            "segments": [
                {
                    "segment_id": c.clip_id,
                    "start_time": c.start_seconds,
                    "end_time": c.end_seconds,
                    "viral_score": c.score,
                    "text": _collect_text_window(c.start_seconds, c.end_seconds),
                    "word_timestamps": [
                        {
                            "word": w.word,
                            "start": w.start_seconds,
                            "end": w.end_seconds,
                            "confidence": w.confidence,
                        }
                        for w in words
                        if (w.end_seconds > c.start_seconds and w.start_seconds < c.end_seconds)
                    ],
                    "features": c.features,
                    "title": c.title,
                }
                for c in clips
            ]
        }

        atomic_write_text(
            ctx.segments_json_path,
            json.dumps(segments_payload, ensure_ascii=False, indent=2),
        )

        raise_if_cancelled()

        current_stage = "render_clips"
        current_progress = 90

        render_segments = segments
        render_word_timings = words
        render_word_timings_by_clip_id = None
        render_audio_override_by_clip_id = None

        if effective_originality_mode == "voiceover":
            _best_effort_progress_callback(
                ctx=ctx,
                stage=current_stage,
                progress_percent=88,
                message="Generating voice-over",
                timeout_seconds=settings.callback_timeout_seconds,
                max_retries=settings.callback_max_retries,
                retry_backoff_seconds=settings.callback_retry_backoff_seconds,
                logger=logger,
            )

            render_segments, render_word_timings_by_clip_id, render_audio_override_by_clip_id = build_voiceover_overrides(
                clips=clips,
                transcript_segments=segments,
                language=language,
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_model,
                openai_base_url=settings.openai_base_url,
                tts_model=settings.tts_model,
                tts_voice=settings.tts_voice,
                tts_instructions=settings.tts_instructions,
                whisper_model=settings.whisper_model,
                whisper_device=settings.whisper_device,
                whisper_temperature=settings.whisper_temperature,
                whisper_beam_size=settings.whisper_beam_size,
                whisper_best_of=settings.whisper_best_of,
                whisper_initial_prompt=initial_prompt,
                clips_dir=ctx.clips_dir,
                logger=logger,
            )

            render_word_timings = None

        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Rendering clips",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        def _do_render():
            return render_clips(
                source_video=ctx.source_video_path,
                transcript_segments=render_segments,
                clips=clips,
                output_dir=ctx.clips_dir,
                logger=logger,
                subtitles_enabled=effective_subtitles_enabled,
                subtitle_template=effective_subtitle_template,
                output_aspect=effective_output_aspect,
                target_fps=settings.target_fps,
                enable_loudnorm=settings.enable_loudnorm,
                stabilization_enabled=settings.stabilization_enabled,
                visual_enhance_enabled=settings.visual_enhance_enabled,
                word_timings=render_word_timings,
                word_timings_by_clip_id=render_word_timings_by_clip_id,
                audio_override_by_clip_id=render_audio_override_by_clip_id,
                quality_gate_enabled=settings.quality_gate_enabled,
                quality_gate_face_overlap_p95_threshold=settings.quality_gate_face_overlap_p95_threshold,
                quality_gate_max_attempts=settings.quality_gate_max_attempts,
                ui_safe_ymin=settings.ui_safe_ymin,
            )

        rendered = run_with_stage_retries("render_clips", _do_render)

        def _load_quality_summary(video_path: str | None) -> dict | None:
            if not video_path:
                return None

            try:
                metrics_path = Path(video_path).parent / "metrics.json"
                if not metrics_path.exists():
                    return None

                raw = json.loads(metrics_path.read_text(encoding="utf-8"))
                subs = raw.get("subtitles") or {}

                final_overlap = subs.get("final_overlap")
                attempts = subs.get("render_attempts")

                return {
                    "template": subs.get("template"),
                    "ui_safe_ymin": subs.get("ui_safe_ymin"),
                    "final_overlap": final_overlap,
                    "attempts": attempts,
                }
            except Exception:
                logger.exception("clip.quality_summary_read_failed")
                return None

        clip_artifacts: list[ClipArtifact] = []
        for c in rendered:
            raise_if_cancelled()

            clip_id = str(c.get("clip_id") or "")
            if clip_id and clip_id in title_candidates_by_clip_id:
                c = {**c, "title_candidates": title_candidates_by_clip_id[clip_id]}

            q = _load_quality_summary(c.get("video_path"))
            if q is not None:
                c = {**c, "quality_summary": q}

            clip_artifacts.append(ClipArtifact(**c))

        artifacts = JobArtifacts(
            source_video_path=str(ctx.source_video_path),
            audio_path=str(ctx.audio_path),
            transcript_json_path=str(ctx.transcript_json_path),
            subtitles_srt_path=str(ctx.subtitles_srt_path),
            clips_json_path=str(ctx.clips_json_path),
            words_json_path=str(ctx.words_json_path),
            segments_json_path=str(ctx.segments_json_path),
            source_metadata_json_path=(
                str(ctx.source_metadata_json_path) if ctx.source_metadata_json_path.exists() else None
            ),
            source_thumbnail_path=(
                str(ctx.source_thumbnail_path) if ctx.source_thumbnail_path.exists() else None
            ),
            clips=clip_artifacts,
        )

        try:
            atomic_write_text(
                ctx.pipeline_state_path,
                json.dumps(
                    {
                        "job_id": ctx.job_id,
                        "project_id": ctx.project_id,
                        "stage": "completed",
                        "progress_percent": 100,
                        "message": "Job completed",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception:
            logger.exception("checkpoint.write_failed")

        completed_payload = JobCallbackPayload(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.completed,
            stage="completed",
            progress_percent=100,
            message="Job completed",
            artifacts=artifacts,
        )

        _best_effort_callback(
            ctx=ctx,
            payload=completed_payload,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        logger.info("job.completed", clip_count=len(rendered))
        return completed_payload.model_dump(mode="json")
    except JobCancelledError:
        logger.info("job.cancelled")

        try:
            atomic_write_text(
                ctx.pipeline_state_path,
                json.dumps(
                    {
                        "job_id": ctx.job_id,
                        "project_id": ctx.project_id,
                        "stage": current_stage,
                        "progress_percent": int(current_progress),
                        "message": "Job cancelled",
                        "error": "cancelled",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception:
            logger.exception("checkpoint.write_failed")

        cancelled_payload = JobCallbackPayload(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.failed,
            stage=current_stage,
            progress_percent=current_progress,
            message="Job cancelled",
            error="cancelled",
        )

        _best_effort_callback(
            ctx=ctx,
            payload=cancelled_payload,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        return cancelled_payload.model_dump(mode="json")
    except Exception as e:
        try:
            atomic_write_text(
                ctx.pipeline_state_path,
                json.dumps(
                    {
                        "job_id": ctx.job_id,
                        "project_id": ctx.project_id,
                        "stage": current_stage,
                        "progress_percent": int(current_progress),
                        "message": f"Failed during stage: {current_stage}",
                        "error": format_exception_short(e),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception:
            logger.exception("checkpoint.write_failed")

        failed_payload = JobCallbackPayload(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.failed,
            stage=current_stage,
            progress_percent=current_progress,
            message=f"Failed during stage: {current_stage}",
            error=format_exception_short(e),
            artifacts=JobArtifacts(
                source_video_path=str(ctx.source_video_path) if ctx.source_video_path.exists() else None,
                audio_path=str(ctx.audio_path) if ctx.audio_path.exists() else None,
                transcript_json_path=str(ctx.transcript_json_path) if ctx.transcript_json_path.exists() else None,
                subtitles_srt_path=str(ctx.subtitles_srt_path) if ctx.subtitles_srt_path.exists() else None,
                clips_json_path=str(ctx.clips_json_path) if ctx.clips_json_path.exists() else None,
                words_json_path=str(ctx.words_json_path) if ctx.words_json_path.exists() else None,
                segments_json_path=str(ctx.segments_json_path) if ctx.segments_json_path.exists() else None,
                source_metadata_json_path=(
                    str(ctx.source_metadata_json_path) if ctx.source_metadata_json_path.exists() else None
                ),
                source_thumbnail_path=(
                    str(ctx.source_thumbnail_path) if ctx.source_thumbnail_path.exists() else None
                ),
            ),
        )

        _best_effort_callback(
            ctx=ctx,
            payload=failed_payload,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )
        raise
