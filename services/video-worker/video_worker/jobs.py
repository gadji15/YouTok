from __future__ import annotations

from pathlib import Path

import structlog

from .callback import ClipArtifact, JobArtifacts, JobCallbackPayload, JobStatus, post_callback
from .config import get_settings
from .logging import get_logger
from .pipeline.audio import extract_audio_wav
from .pipeline.clip import render_clips
from .pipeline.context import JobContext
from .pipeline.download import download_youtube_video
from .pipeline.segment import segment_candidates, write_clips_json
from .pipeline.subtitles import write_srt
from .pipeline.title_generator import generate_title_candidates_for_clip
from .pipeline.transcribe import transcribe_audio, write_transcript_json
from .pipeline.word_alignment import (
    align_words_with_whisperx,
    approximate_words_from_segments,
    write_words_json,
)
from .utils.errors import format_exception_short


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
    callback_url: str,
    callback_secret: str,
    language: str | None = None,
    subtitles_enabled: bool | None = None,
    subtitle_template: str | None = None,
    clip_min_seconds: float | None = None,
    clip_max_seconds: float | None = None,
    max_clips: int | None = None,
) -> dict:
    settings = get_settings()
    logger = get_logger(service="video-worker", job_id=job_id, project_id=project_id)

    effective_min_seconds = settings.clip_min_seconds if clip_min_seconds is None else float(clip_min_seconds)
    effective_max_seconds = settings.clip_max_seconds if clip_max_seconds is None else float(clip_max_seconds)

    # Product constraint: clips must be 1–3 minutes.
    effective_min_seconds = max(60.0, effective_min_seconds)
    effective_max_seconds = max(effective_min_seconds, min(180.0, effective_max_seconds))

    effective_max_clips = settings.max_clips if max_clips is None else int(max_clips)
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
        root_dir=Path(settings.storage_path) / job_id,
    )

    ctx.ensure_dirs()

    current_stage = "start"
    current_progress = 0

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
        current_stage = "download"
        current_progress = 10
        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Downloading source video",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )
        download_youtube_video(
            youtube_url=ctx.youtube_url,
            output_path=ctx.source_video_path,
            logger=logger,
            max_retries=settings.download_max_retries,
            retry_backoff_seconds=settings.download_retry_backoff_seconds,
        )

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
        extract_audio_wav(
            input_video=ctx.source_video_path,
            output_wav=ctx.audio_path,
            logger=logger,
        )

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
        segments = transcribe_audio(
            audio_path=ctx.audio_path,
            model_name=settings.whisper_model,
            logger=logger,
            device=settings.whisper_device,
            temperature=settings.whisper_temperature,
            beam_size=settings.whisper_beam_size,
            best_of=settings.whisper_best_of,
        )

        write_transcript_json(segments=segments, output_path=ctx.transcript_json_path)
        write_srt(segments=segments, output_path=ctx.subtitles_srt_path)

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

        words = align_words_with_whisperx(
            audio_path=ctx.audio_path,
            segments=segments,
            language=language,
            logger=logger,
            device=settings.whisper_device,
        )
        if words is None:
            words = approximate_words_from_segments(segments=segments)
            logger.info("align.fallback_approximate", word_count=len(words))

        write_words_json(words=words, output_path=ctx.words_json_path)

        current_stage = "segment"
        current_progress = 70
        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Selecting clip candidates",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )
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

        current_stage = "titles"
        current_progress = 80
        _best_effort_progress_callback(
            ctx=ctx,
            stage=current_stage,
            progress_percent=current_progress,
            message="Generating viral titles",
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        title_candidates_by_clip_id: dict[str, dict] = {}
        updated_clips = []

        for c in clips:
            res = generate_title_candidates_for_clip(
                clip=c,
                segments=segments,
                language=language,
                provider=settings.title_provider,
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_model,
                openai_base_url=settings.openai_base_url,
                logger=logger.bind(clip_id=c.clip_id),
            )

            title_payload = res.to_payload()
            title_candidates_by_clip_id[c.clip_id] = title_payload

            best_title = res.candidates[0].title if res.candidates else c.title

            updated_clips.append(
                type(c)(
                    clip_id=c.clip_id,
                    start_seconds=c.start_seconds,
                    end_seconds=c.end_seconds,
                    score=c.score,
                    reason=c.reason,
                    title=best_title,
                )
            )

        clips = updated_clips
        write_clips_json(clips=clips, output_path=ctx.clips_json_path)

        current_stage = "render_clips"
        current_progress = 90
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
        rendered = render_clips(
            source_video=ctx.source_video_path,
            transcript_segments=segments,
            clips=clips,
            output_dir=ctx.clips_dir,
            logger=logger,
            subtitles_enabled=effective_subtitles_enabled,
            subtitle_template=effective_subtitle_template,
            target_fps=settings.target_fps,
            enable_loudnorm=settings.enable_loudnorm,
            word_timings=words,
        )

        clip_artifacts: list[ClipArtifact] = []
        for c in rendered:
            clip_id = str(c.get("clip_id") or "")
            if clip_id and clip_id in title_candidates_by_clip_id:
                c = {**c, "title_candidates": title_candidates_by_clip_id[clip_id]}
            clip_artifacts.append(ClipArtifact(**c))

        artifacts = JobArtifacts(
            source_video_path=str(ctx.source_video_path),
            audio_path=str(ctx.audio_path),
            transcript_json_path=str(ctx.transcript_json_path),
            subtitles_srt_path=str(ctx.subtitles_srt_path),
            clips_json_path=str(ctx.clips_json_path),
            clips=clip_artifacts,
        )

        completed_payload = JobCallbackPayload(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.completed,
            stage="completed",
            progress_percent=100,
            message="Job completed",
            artifacts=artifacts,
        )

        post_callback(
            callback_url=ctx.callback_url,
            callback_secret=ctx.callback_secret,
            payload=completed_payload,
            timeout_seconds=settings.callback_timeout_seconds,
            max_retries=settings.callback_max_retries,
            retry_backoff_seconds=settings.callback_retry_backoff_seconds,
            logger=logger,
        )

        logger.info("job.completed", clip_count=len(rendered))
        return completed_payload.model_dump(mode="json")
    except Exception as e:
        failed_payload = JobCallbackPayload(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.failed,
            stage=current_stage,
            progress_percent=current_progress,
            message=f"Failed during stage: {current_stage}",
            error=format_exception_short(e),
            artifacts=JobArtifacts(
                source_video_path=str(ctx.source_video_path),
                audio_path=str(ctx.audio_path),
                transcript_json_path=str(ctx.transcript_json_path),
                subtitles_srt_path=str(ctx.subtitles_srt_path),
                clips_json_path=str(ctx.clips_json_path),
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
