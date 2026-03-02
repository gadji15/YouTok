from __future__ import annotations

from pathlib import Path

import structlog

from ..utils.ffprobe import probe_video
from ..utils.subprocess import run
from .face_tracking import estimate_face_center_x
from .saliency import estimate_motion_center_x
from .subtitle_placement import choose_subtitle_placement
from .subtitles import write_srt_for_clip, write_stylized_ass_for_clip, write_word_level_ass_for_clip
from .types import ClipCandidate, TranscriptSegment, WordTiming


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _compute_crop_x_pixels(
    *,
    source_video: Path,
    center_x_rel: float,
    target_w: int = 1080,
    target_h: int = 1920,
) -> int:
    info = probe_video(source_video)
    a_target = target_w / target_h
    a_src = info.width / info.height

    if a_src > a_target:
        # We'll scale the source to target height, then crop horizontally.
        scale = target_h / info.height
        scaled_w = info.width * scale
    else:
        # We'll scale the source to target width; no horizontal crop needed.
        scaled_w = float(target_w)

    crop_x = center_x_rel * scaled_w - target_w / 2.0
    crop_x = _clamp(crop_x, 0.0, max(0.0, scaled_w - target_w))
    return int(round(crop_x))


def _estimate_best_center_x_rel(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> float | None:
    face_x = estimate_face_center_x(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir,
    )
    if face_x is not None:
        return face_x

    return estimate_motion_center_x(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir,
    )


def render_clips(
    *,
    source_video: Path,
    transcript_segments: list[TranscriptSegment],
    clips: list[ClipCandidate],
    output_dir: Path,
    logger: structlog.BoundLogger,
    subtitles_enabled: bool = True,
    subtitle_template: str = "default",
    target_fps: int = 30,
    enable_loudnorm: bool = False,
    word_timings: list[WordTiming] | None = None,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[dict] = []

    def _ffmpeg_filter_escape_path(p: Path) -> str:
        # ffmpeg filter args treat ':', ',', and '\\' specially.
        s = p.as_posix()
        return s.replace('\\', '\\\\').replace(':', '\\:').replace(',', '\\,')

    fps = max(1, int(target_fps))

    for clip in clips:
        clip_dir = output_dir / clip.clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)

        out_video = clip_dir / "video.mp4"
        out_srt = clip_dir / "subtitles.srt"
        out_ass = clip_dir / "subtitles.ass"

        write_srt_for_clip(
            clip_start_seconds=clip.start_seconds,
            clip_end_seconds=clip.end_seconds,
            segments=transcript_segments,
            output_path=out_srt,
        )

        if subtitles_enabled:
            placement = choose_subtitle_placement(
                source_video=source_video,
                clip_start_seconds=clip.start_seconds,
                clip_end_seconds=clip.end_seconds,
                play_res_x=1080,
                play_res_y=1920,
                work_dir=clip_dir / "subtitle_placement",
                logger=logger.bind(clip_id=clip.clip_id),
            )

            if word_timings:
                write_word_level_ass_for_clip(
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    words=word_timings,
                    output_path=out_ass,
                    placement=(placement.alignment, placement.x, placement.y),
                    template=subtitle_template,
                )
            else:
                write_stylized_ass_for_clip(
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    segments=transcript_segments,
                    output_path=out_ass,
                    template=subtitle_template,
                )

        if out_video.exists() and out_video.stat().st_size > 0:
            rendered.append(
                {
                    "clip_id": clip.clip_id,
                    "start_seconds": clip.start_seconds,
                    "end_seconds": clip.end_seconds,
                    "score": clip.score,
                    "reason": clip.reason,
                    "title": getattr(clip, "title", None),
                    "video_path": str(out_video),
                    "subtitles_ass_path": str(out_ass) if subtitles_enabled else None,
                    "subtitles_srt_path": str(out_srt),
                }
            )
            continue

        duration = max(0.0, clip.end_seconds - clip.start_seconds)
        if duration <= 0:
            continue

        # Dynamic horizontal reframing:
        # - Prefer face center.
        # - Fall back to motion center for scenes with no visible person.
        # - Use a simple pan from start->end when centers differ.
        win = min(10.0, max(4.0, duration / 8.0))

        start_center = _estimate_best_center_x_rel(
            video_path=source_video,
            start_seconds=clip.start_seconds,
            end_seconds=clip.start_seconds + win,
            work_dir=clip_dir / "track_start",
        )
        end_center = _estimate_best_center_x_rel(
            video_path=source_video,
            start_seconds=max(clip.start_seconds, clip.end_seconds - win),
            end_seconds=clip.end_seconds,
            work_dir=clip_dir / "track_end",
        )

        if start_center is None and end_center is None:
            start_center = 0.5
            end_center = 0.5
        elif start_center is None:
            start_center = end_center
        elif end_center is None:
            end_center = start_center

        crop_x0 = _compute_crop_x_pixels(source_video=source_video, center_x_rel=float(start_center))
        crop_x1 = _compute_crop_x_pixels(source_video=source_video, center_x_rel=float(end_center))

        if abs(crop_x1 - crop_x0) < 24:
            crop_filter = f"crop=1080:1920:x={crop_x0}:y=(ih-1920)/2"
        else:
            d = max(0.001, float(duration))
            crop_filter = (
                "crop=1080:1920:"
                + f"x='max(0,min({crop_x0}+({crop_x1}-{crop_x0})*t/{d},iw-1080))'"
                + ":y=(ih-1920)/2"
            )

        vf_parts = [
            "scale=1080:1920:force_original_aspect_ratio=increase",
            crop_filter,
            f"fps={fps}",
        ]
        if subtitles_enabled:
            vf_parts.append(f"ass={_ffmpeg_filter_escape_path(out_ass)}")

        ffmpeg_args: list[str] = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(clip.start_seconds),
            "-i",
            str(source_video),
            "-t",
            str(duration),
            "-vf",
            ",".join(vf_parts),
        ]

        if enable_loudnorm:
            ffmpeg_args += [
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
            ]

        ffmpeg_args += [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(out_video),
        ]

        run(
            ffmpeg_args,
            logger=logger.bind(clip_id=clip.clip_id),
        )

        if not out_video.exists() or out_video.stat().st_size <= 0:
            raise RuntimeError(f"ffmpeg produced no output for {clip.clip_id}")

        rendered.append(
            {
                "clip_id": clip.clip_id,
                "start_seconds": clip.start_seconds,
                "end_seconds": clip.end_seconds,
                "score": clip.score,
                "reason": clip.reason,
                "title": getattr(clip, "title", None),
                "video_path": str(out_video),
                "subtitles_ass_path": str(out_ass) if subtitles_enabled else None,
                "subtitles_srt_path": str(out_srt),
            }
        )

    return rendered
