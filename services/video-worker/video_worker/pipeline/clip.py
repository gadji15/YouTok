from __future__ import annotations

from pathlib import Path

import json
import structlog

from ..utils.ffprobe import probe_video
from ..utils.subprocess import run
from .face_tracking import estimate_face_center_x
from .saliency import estimate_motion_center_x
from .subtitle_placement import choose_subtitle_placement
from .subtitles import write_srt_for_clip, write_stylized_ass_for_clip, write_word_level_ass_for_clip
from .types import ClipCandidate, TranscriptSegment, WordTiming
from .word_alignment import approximate_words_from_segments


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


def _ema_smooth(values: list[float], alpha: float) -> list[float]:
    if not values:
        return []
    alpha = _clamp(alpha, 0.0, 1.0)

    out = [float(values[0])]
    for v in values[1:]:
        out.append(alpha * float(v) + (1.0 - alpha) * out[-1])
    return out


def _build_piecewise_linear_x_expr(*, t_points: list[float], x_points: list[int]) -> str:
    """Build an ffmpeg expression for piecewise-linear x(t).

    - t is in seconds (ffmpeg variable).
    - Returns an expression string usable inside crop x='...'.

    We deliberately keep this expression simple and bounded in size.
    """

    assert len(t_points) == len(x_points)
    if len(t_points) == 1:
        return str(int(x_points[0]))

    expr = str(int(x_points[-1]))

    # Build nested if(between(t,ti,tj), segment_expr, fallback)
    for i in range(len(t_points) - 2, -1, -1):
        t0 = float(t_points[i])
        t1 = float(t_points[i + 1])
        x0 = int(x_points[i])
        x1 = int(x_points[i + 1])

        dt = max(0.001, t1 - t0)
        seg = f"{x0}+({x1}-{x0})*(t-{t0})/{dt}"

        expr = f"if(between(t,{t0},{t1}),{seg},{expr})"

    return expr


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

    def _best_effort_log_ass_stats(*, ass_path: Path, clip_id: str, source: str) -> dict | None:
        try:
            text = ass_path.read_text(encoding="utf-8", errors="replace")

            dialogue_count = text.count("Dialogue:")
            has_karaoke = "\\k" in text
            has_pos = "\\pos(" in text

            import re

            rx = re.compile(r"^Dialogue:\\s*[^,]*,([^,]+),([^,]+),", re.M)

            def _ass_ts_to_seconds(t: str) -> float:
                # h:mm:ss.cs
                h, m, rest = t.split(":")
                s, cs = rest.split(".")
                return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0

            durations: list[float] = []
            for start, end in rx.findall(text):
                s = _ass_ts_to_seconds(start)
                e = _ass_ts_to_seconds(end)
                if e >= s:
                    durations.append(e - s)

            max_event_seconds = max(durations) if durations else None

            stats = {
                "clip_id": clip_id,
                "dialogue_count": dialogue_count,
                "max_event_seconds": max_event_seconds,
                "has_karaoke": has_karaoke,
                "has_pos": has_pos,
                "source": source,
            }

            logger.info("subtitles.ass_stats", **stats)
            return stats
        except Exception:
            logger.exception("subtitles.ass_stats_failed", clip_id=clip_id)
            return None

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

        # Attempt to produce word-level timings and an ASS via the new tools.
        try:
            repo_root = Path(__file__).resolve().parents[4]
            tools_dir = repo_root / "services" / "video-worker" / "video_worker" / "tools"

            audio_wav = clip_dir / "audio.wav"
            words_json = clip_dir / "words.json"

            # extract clip audio for alignment
            ff_args = [
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
                str(max(0.01, clip.end_seconds - clip.start_seconds)),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(audio_wav),
            ]
            run(ff_args, logger=logger.bind(clip_id=clip.clip_id))

            # run whisperx_align.py (best-effort)
            wxa = tools_dir / "whisperx_align.py"
            if wxa.exists():
                run(["python3", str(wxa), "--wav", str(audio_wav), "--out", str(words_json)], logger=logger.bind(clip_id=clip.clip_id))

            # If words.json produced, call make_ass to create an ASS file
            mak = tools_dir / "make_ass.py"
            if words_json.exists() and mak.exists():
                run(["python3", str(mak), "--words", str(words_json), "--out", str(out_ass), "--video", str(source_video)], logger=logger.bind(clip_id=clip.clip_id))
                # mark that we've generated the ASS from tools
                used_source = "word_timings_tools"
        except Exception:
            logger.exception("external_ass_generation_failed", clip_id=clip.clip_id)

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

            clip_segments = [
                s
                for s in transcript_segments
                if s.text.strip() and s.end_seconds > clip.start_seconds and s.start_seconds < clip.end_seconds
            ]

            used_source = "stylized"

            # Prefer true word timings (WhisperX or heuristic approximation from the full transcript).
            if (word_timings and len(word_timings) > 0) or (out_ass.exists() and used_source == "word_timings_tools"):
                write_word_level_ass_for_clip(
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    words=word_timings or [],
                    output_path=out_ass,
                    placement=(placement.alignment, placement.x, placement.y),
                    template=subtitle_template,
                )
                used_source = "word_timings"
            else:
                approx = approximate_words_from_segments(segments=clip_segments)
                if approx:
                    logger.info(
                        "subtitles.word_timings_fallback_approximate",
                        clip_id=clip.clip_id,
                        word_count=len(approx),
                    )
                    write_word_level_ass_for_clip(
                        clip_start_seconds=clip.start_seconds,
                        clip_end_seconds=clip.end_seconds,
                        words=approx,
                        output_path=out_ass,
                        placement=(placement.alignment, placement.x, placement.y),
                        template=subtitle_template,
                    )
                    used_source = "approximate"
                else:
                    write_stylized_ass_for_clip(
                        clip_start_seconds=clip.start_seconds,
                        clip_end_seconds=clip.end_seconds,
                        segments=transcript_segments,
                        output_path=out_ass,
                        template=subtitle_template,
                    )
                    used_source = "stylized"

            stats = _best_effort_log_ass_stats(ass_path=out_ass, clip_id=clip.clip_id, source=used_source)

            # Persist placement diagnostics for later QA / scoring.
            try:
                metrics_path = clip_dir / "metrics.json"
                payload = {
                    "clip_id": clip.clip_id,
                    "subtitles": {
                        "enabled": True,
                        "template": subtitle_template,
                        "placement": {
                            "alignment": placement.alignment,
                            "x": placement.x,
                            "y": placement.y,
                            "face_overlap_ratio": getattr(placement, "face_overlap_ratio", 0.0),
                            "ui_overlap_ratio": getattr(placement, "ui_overlap_ratio", 0.0),
                            "ui_score": getattr(placement, "ui_score", 0.0),
                        },
                        "ass_stats": stats,
                    },
                }
                metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                logger.exception("clip.metrics_write_failed", clip_id=clip.clip_id)

            # Persist placement diagnostics for later QA / scoring
            # Safety net: if we ended up with a tiny number of very long Dialogue events,
            # regenerate using approximate timings (prevents "frozen" subtitles even if
            # upstream word timings are sparse/broken).
            if (
                used_source == "word_timings"
                and stats
                and ((stats.get("dialogue_count") or 0) <= 3 or (stats.get("max_event_seconds") or 0) > 10)
            ):
                approx = approximate_words_from_segments(segments=clip_segments)
                if approx:
                    logger.info(
                        "subtitles.regenerate_with_approximate_timings",
                        clip_id=clip.clip_id,
                        word_count=len(approx),
                    )
                    write_word_level_ass_for_clip(
                        clip_start_seconds=clip.start_seconds,
                        clip_end_seconds=clip.end_seconds,
                        words=approx,
                        output_path=out_ass,
                        placement=(placement.alignment, placement.x, placement.y),
                        template=subtitle_template,
                    )
                    _best_effort_log_ass_stats(
                        ass_path=out_ass,
                        clip_id=clip.clip_id,
                        source="approximate_regenerated",
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

        # Dynamic horizontal reframing (subject tracking + smoothing):
        # - Prefer face center per sampled frame.
        # - Fall back to motion center when no face is detected.
        # - Smooth the resulting crop curve to avoid jitter.
        # - Use a piecewise-linear crop x(t) for better framing than start->end only.

        # We'll keep the expression small by using up to 5 knot points.
        knot_count = 5
        if duration < 8.0:
            knot_count = 3

        t_points = [i * (duration / max(1, knot_count - 1)) for i in range(knot_count)]

        crop_x_points: list[int] = []
        centers_dbg: list[float | None] = []

        for i, t_rel in enumerate(t_points):
            # Small window around the knot (stabilizes detection).
            w = 3.0 if duration > 20 else 2.0
            a0 = max(clip.start_seconds, clip.start_seconds + t_rel - w / 2.0)
            a1 = min(clip.end_seconds, clip.start_seconds + t_rel + w / 2.0)
            center = _estimate_best_center_x_rel(
                video_path=source_video,
                start_seconds=a0,
                end_seconds=a1,
                work_dir=clip_dir / f"track_knot_{i}",
            )
            centers_dbg.append(center)
            if center is None:
                center = 0.5

            crop_x_points.append(_compute_crop_x_pixels(source_video=source_video, center_x_rel=float(center)))

        # Smooth crop positions using an exponential moving average.
        smoothed = [int(round(v)) for v in _ema_smooth([float(x) for x in crop_x_points], alpha=0.55)]

        # Enforce a max pan speed between consecutive knots.
        max_pan_px_per_sec = 220.0
        for i in range(1, len(smoothed)):
            dt = max(0.001, t_points[i] - t_points[i - 1])
            max_delta = int(round(max_pan_px_per_sec * dt))
            delta = smoothed[i] - smoothed[i - 1]
            if abs(delta) > max_delta:
                smoothed[i] = smoothed[i - 1] + (max_delta if delta > 0 else -max_delta)

        # If still basically static, keep filter simple.
        if max(smoothed) - min(smoothed) < 24:
            crop_filter = f"crop=1080:1920:x={smoothed[0]}:y=(ih-1920)/2"
        else:
            expr = _build_piecewise_linear_x_expr(t_points=t_points, x_points=smoothed)
            crop_filter = "crop=1080:1920:" + f"x='max(0,min({expr},iw-1080))'" + ":y=(ih-1920)/2"

        # Persist tracking diagnostics (useful for QA).
        try:
            track_path = clip_dir / "track.json"
            track_path.write_text(
                json.dumps(
                    {
                        "duration": duration,
                        "t_points": t_points,
                        "centers_x_rel": centers_dbg,
                        "crop_x_points": crop_x_points,
                        "crop_x_points_smoothed": smoothed,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            logger.exception("clip.track_write_failed", clip_id=clip.clip_id)

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
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            # Target bitrate-based encode for more predictable TikTok packaging.
            "-b:v",
            "10M",
            "-maxrate",
            "12M",
            "-bufsize",
            "20M",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
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
