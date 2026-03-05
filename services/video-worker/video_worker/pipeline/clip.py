from __future__ import annotations

from pathlib import Path

import json
import structlog

from ..utils.ffprobe import probe_video
from ..utils.subprocess import run
from .face_tracking import estimate_face_center_x
from .saliency import estimate_edge_center_x_with_confidence, estimate_motion_center_x_with_confidence
from .subtitle_placement import SubtitlePlacement, choose_subtitle_placement, measure_overlap_p95_for_video
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

    edge = estimate_edge_center_x_with_confidence(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir / "edge",
    )

    motion = estimate_motion_center_x_with_confidence(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir / "motion",
    )

    if edge is not None and motion is not None:
        edge_x, edge_conf = edge
        motion_x, motion_conf = motion
        return edge_x if edge_conf >= motion_conf else motion_x

    if edge is not None:
        return float(edge[0])

    if motion is not None:
        return float(motion[0])

    return None


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
    output_aspect: str = "vertical",
    target_fps: int = 30,
    enable_loudnorm: bool = False,
    stabilization_enabled: bool = True,
    visual_enhance_enabled: bool = True,
    word_timings: list[WordTiming] | None = None,
    word_timings_by_clip_id: dict[str, list[WordTiming]] | None = None,
    audio_override_by_clip_id: dict[str, Path] | None = None,
    quality_gate_enabled: bool = False,
    quality_gate_face_overlap_p95_threshold: float = 0.05,
    quality_gate_max_attempts: int = 2,
    ui_safe_ymin: float = 0.78,
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

    effective_output_aspect = (output_aspect or "vertical").strip().lower()
    if effective_output_aspect not in {"vertical", "source"}:
        effective_output_aspect = "vertical"

    # Vertical (9:16) is the default TikTok-ready output.
    # "source" keeps the original aspect ratio/resolution (no vertical crop).
    source_info = probe_video(source_video)

    if effective_output_aspect == "source":
        play_res_x = int(source_info.width) - (int(source_info.width) % 2)
        play_res_y = int(source_info.height) - (int(source_info.height) % 2)
        effective_ui_safe_ymin = 1.0
    else:
        play_res_x = 1080
        play_res_y = 1920
        effective_ui_safe_ymin = ui_safe_ymin

    is_source_aspect = effective_output_aspect == "source"

    # Vertical (9:16) is the default TikTok-ready output
    for clip in clips:
        clip_dir = output_dir / clip.clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)

        out_video = clip_dir / "video.mp4"
        out_srt = clip_dir / "subtitles.srt"
        out_ass = clip_dir / "subtitles.ass"

        # Fast path for resumed jobs: if the final video and subtitle files exist,
        # skip all expensive subtitle placement + alignment work.
        if out_video.exists() and out_video.stat().st_size > 0:
            subs_ok = True
            if subtitles_enabled:
                subs_ok = out_srt.exists() and out_srt.stat().st_size > 0 and out_ass.exists() and out_ass.stat().st_size > 0

            if subs_ok:
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

        clip_word_timings = (
            word_timings_by_clip_id.get(clip.clip_id)
            if word_timings_by_clip_id is not None and clip.clip_id in word_timings_by_clip_id
            else word_timings
        )

        clip_audio_override = (
            audio_override_by_clip_id.get(clip.clip_id)
            if audio_override_by_clip_id is not None and clip.clip_id in audio_override_by_clip_id
            else None
        )

        write_srt_for_clip(
            clip_start_seconds=clip.start_seconds,
            clip_end_seconds=clip.end_seconds,
            segments=transcript_segments,
            output_path=out_srt,
        )

        tool_ass_generated = False

        placement = None
        if subtitles_enabled:
            try:
                placement = choose_subtitle_placement(
                    source_video=source_video,
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    play_res_x=play_res_x,
                    play_res_y=play_res_y,
                    work_dir=clip_dir / "subtitle_placement",
                    logger=logger.bind(clip_id=clip.clip_id),
                    ui_safe_ymin=effective_ui_safe_ymin,
                )
            except TypeError:
                placement = choose_subtitle_placement(
                    source_video=source_video,
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    play_res_x=play_res_x,
                    play_res_y=play_res_y,
                    work_dir=clip_dir / "subtitle_placement",
                    logger=logger.bind(clip_id=clip.clip_id),
                )

        # Attempt to produce word-level timings and an ASS via the bundled tools.
        # NOTE: This runs inside the worker image where the package lives at /app/video_worker.
        # If clip audio is overridden (voiceover mode), skip this step (it would align against
        # the original source audio and produce incorrect subtitles).
        if clip_audio_override is None:
            try:
                tools_dir = Path(__file__).resolve().parents[1] / "tools"

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
                    run(
                        ["python3", str(wxa), "--wav", str(audio_wav), "--out", str(words_json)],
                        logger=logger.bind(clip_id=clip.clip_id),
                    )

                # If words.json produced, call make_ass to create an ASS file
                mak = tools_dir / "make_ass.py"
                if words_json.exists() and mak.exists():
                    cmd = [
                        "python3",
                        str(mak),
                        "--words",
                        str(words_json),
                        "--out",
                        str(out_ass),
                        "--video",
                        str(source_video),
                        "--play-res-x",
                        str(play_res_x),
                        "--play-res-y",
                        str(play_res_y),
                        "--template",
                        str(subtitle_template),
                        "--ui-safe-ymin",
                        str(effective_ui_safe_ymin),
                    ]

                    if placement is not None:
                        cmd += [
                            "--an",
                            str(placement.alignment),
                            "--x",
                            str(placement.x),
                            "--y",
                            str(placement.y),
                        ]

                    run(cmd, logger=logger.bind(clip_id=clip.clip_id))
                    tool_ass_generated = out_ass.exists() and out_ass.stat().st_size > 0
            except Exception:
                logger.exception("external_ass_generation_failed", clip_id=clip.clip_id)

        clip_segments = [
            s
            for s in transcript_segments
            if s.text.strip() and s.end_seconds > clip.start_seconds and s.start_seconds < clip.end_seconds
        ]

        if subtitles_enabled:
            used_source = "stylized"

            # Prefer true word timings (WhisperX or heuristic approximation from the full transcript).
            if tool_ass_generated:
                used_source = "word_timings_tools"
            elif placement is not None and clip_word_timings and len(clip_word_timings) > 0:
                write_word_level_ass_for_clip(
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    words=clip_word_timings,
                    output_path=out_ass,
                    placement=(placement.alignment, placement.x, placement.y),
                    play_res_x=play_res_x,
                    play_res_y=play_res_y,
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
                        play_res_x=play_res_x,
                        play_res_y=play_res_y,
                        template=subtitle_template,
                    )
                    used_source = "approximate"
                else:
                    write_stylized_ass_for_clip(
                        clip_start_seconds=clip.start_seconds,
                        clip_end_seconds=clip.end_seconds,
                        segments=transcript_segments,
                        output_path=out_ass,
                        play_res_x=play_res_x,
                        play_res_y=play_res_y,
                        template=subtitle_template,
                    )
                    used_source = "stylized"

            stats = _best_effort_log_ass_stats(ass_path=out_ass, clip_id=clip.clip_id, source=used_source)

            # Persist initial placement diagnostics for later QA / scoring.
            try:
                metrics_path = clip_dir / "metrics.json"
                payload = {
                    "clip_id": clip.clip_id,
                    "subtitles": {
                        "enabled": True,
                        "template": subtitle_template,
                        "ui_safe_ymin": effective_ui_safe_ymin,
                        "placement": {
                            "alignment": placement.alignment,
                            "x": placement.x,
                            "y": placement.y,
                            "face_overlap_ratio": getattr(placement, "face_overlap_ratio", 0.0),
                            "ui_overlap_ratio": getattr(placement, "ui_overlap_ratio", 0.0),
                            "ui_score": getattr(placement, "ui_score", 0.0),
                        },
                        "ass_stats": stats,
                        "render_attempts": [],
                    },
                }
                metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                logger.exception("clip.metrics_write_failed", clip_id=clip.clip_id)

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
                        play_res_x=play_res_x,
                        play_res_y=play_res_y,
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

        if is_source_aspect:
            vf_parts = [
                # Ensure even dimensions for yuv420p without changing aspect.
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                f"fps={fps}",
            ]
        else:
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

        if stabilization_enabled:
            # Prefer a higher-quality 2-pass stabilization when available:
            # - pass 1: vidstabdetect writes transforms
            # - pass 2: vidstabtransform applies them
            # Fallback to deshake if vidstab isn't available or fails.

            stab_trf = clip_dir / "stab.trf"

            def _run_vidstab_detect() -> None:
                # Analyze only the clip window to keep it fast.
                # Use a reduced resolution for speed; this doesn't affect final quality.
                args = [
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
                    "scale=640:-2,vidstabdetect=shakiness=6:accuracy=12:result=" + _ffmpeg_filter_escape_path(stab_trf),
                    "-f",
                    "null",
                    "-",
                ]
                run(args, logger=logger.bind(clip_id=clip.clip_id, step="vidstabdetect"))

            try:
                if not stab_trf.exists() or stab_trf.stat().st_size <= 0:
                    _run_vidstab_detect()

                if stab_trf.exists() and stab_trf.stat().st_size > 0:
                    vf_parts.append(
                        "vidstabtransform=input="
                        + _ffmpeg_filter_escape_path(stab_trf)
                        + ":zoom=0:smoothing=18:optzoom=0"
                    )
                else:
                    vf_parts.append("deshake=x=16:y=16:w=64:h=64:rx=16:ry=16:edge=mirror")
            except Exception:
                logger.exception("stabilization.vidstab_failed_fallback_deshake", clip_id=clip.clip_id)
                vf_parts.append("deshake=x=16:y=16:w=64:h=64:rx=16:ry=16:edge=mirror")

        if visual_enhance_enabled:
            # Mobile-first, conservative enhancements.
            vf_parts.append("eq=contrast=1.06:saturation=1.05:brightness=0.01")
            vf_parts.append("unsharp=5:5:0.8:3:3:0.4")

        if subtitles_enabled:
            vf_parts.append(f"ass={_ffmpeg_filter_escape_path(out_ass)}")

        # TikTok-friendly encode settings:
        # - Constant frame rate (CFR)
        # - Regular keyframes every ~2 seconds (helps TikTok transcode more cleanly)
        # - Keep bitrate reasonable to avoid extra aggressive recompression
        gop = int(max(1, fps * 2))

        def _build_ffmpeg_args(*, vf: str) -> list[str]:
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
            ]

            if clip_audio_override is not None:
                ffmpeg_args += [
                    "-i",
                    str(clip_audio_override),
                ]

                audio_chain = f"[1:a]atrim=0:{duration},asetpts=PTS-STARTPTS,apad=pad_dur={duration}"
                if enable_loudnorm:
                    audio_chain += ",loudnorm=I=-16:TP=-1.5:LRA=11"
                audio_chain += "[a]"

                ffmpeg_args += [
                    "-filter_complex",
                    audio_chain,
                    "-map",
                    "0:v:0",
                    "-map",
                    "[a]",
                ]
            elif enable_loudnorm:
                ffmpeg_args += [
                    "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
                ]

            ffmpeg_args += [
                "-vsync",
                "cfr",
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-profile:v",
                "high",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-maxrate",
                "10M",
                "-bufsize",
                "12M",
                "-x264-params",
                f"keyint={gop}:min-keyint={gop}:scenecut=0",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                "-vf",
                vf,
                str(out_video),
            ]

            return ffmpeg_args

        # Quality gate rerender loop: if subtitles overlap faces/UI on the final video,
        # regenerate the ASS with an alternative placement and re-render.
        attempt_placements: list[tuple[int, int, int]] = []
        if subtitles_enabled and placement is not None:
            attempt_placements.append((placement.alignment, placement.x, placement.y))

            if quality_gate_enabled:
                # Shift up relative to configured UI safe zone.
                shift = int(max(play_res_y * 0.06, 100))

                if effective_output_aspect == "vertical":
                    safe_top = int(max(play_res_y * 0.10, play_res_y * (float(effective_ui_safe_ymin) - 0.16)))
                else:
                    safe_top = int(play_res_y * 0.10)

                y_up = max(safe_top, placement.y - shift)
                attempt_placements.append((2, play_res_x // 2, y_up))

                top_margin = int(max(play_res_y * 0.08, 120))
                attempt_placements.append((8, play_res_x // 2, top_margin))

        max_attempts = max(1, int(quality_gate_max_attempts))
        attempt_placements = attempt_placements[: max_attempts]

        def _write_ass_for_attempt(pl: tuple[int, int, int]) -> None:
            # If we have a word-level ASS generator available, prefer it (precise placement).
            if clip_word_timings and len(clip_word_timings) > 0:
                write_word_level_ass_for_clip(
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    words=clip_word_timings,
                    output_path=out_ass,
                    placement=pl,
                    play_res_x=play_res_x,
                    play_res_y=play_res_y,
                    template=subtitle_template,
                )
                return

            approx = approximate_words_from_segments(segments=clip_segments)
            if approx:
                write_word_level_ass_for_clip(
                    clip_start_seconds=clip.start_seconds,
                    clip_end_seconds=clip.end_seconds,
                    words=approx,
                    output_path=out_ass,
                    placement=pl,
                    play_res_x=play_res_x,
                    play_res_y=play_res_y,
                    template=subtitle_template,
                )
                return

            # Fallback: stylized ASS without explicit pos.
            write_stylized_ass_for_clip(
                clip_start_seconds=clip.start_seconds,
                clip_end_seconds=clip.end_seconds,
                segments=transcript_segments,
                output_path=out_ass,
                play_res_x=play_res_x,
                play_res_y=play_res_y,
                template=subtitle_template,
            )

        attempts_log: list[dict] = []

        # Always render at least once.
        if not attempt_placements:
            vf_once = list(vf_parts)
            ffmpeg_args = _build_ffmpeg_args(vf=",".join(vf_once))
            run(ffmpeg_args, logger=logger.bind(clip_id=clip.clip_id, attempt=1))
        else:
            ok = False
            last_face95 = 0.0
            last_ui95 = 0.0

            for attempt_idx, pl in enumerate(attempt_placements, start=1):
                # When an external tool generated an ASS, we keep it as-is.
                # Otherwise we regenerate ASS for each attempt to apply the alternative placement.
                if not tool_ass_generated:
                    _write_ass_for_attempt(pl)

                vf_once = list(vf_parts)

                ffmpeg_args = _build_ffmpeg_args(vf=",".join(vf_once))

                run(ffmpeg_args, logger=logger.bind(clip_id=clip.clip_id, attempt=attempt_idx))

                try:
                    face95, ui95 = measure_overlap_p95_for_video(
                        video_path=out_video,
                        start_seconds=0.0,
                        end_seconds=float(duration),
                        placement=SubtitlePlacement(alignment=pl[0], x=pl[1], y=pl[2]),
                        play_res_x=play_res_x,
                        play_res_y=play_res_y,
                        work_dir=clip_dir / f"overlap_final_attempt_{attempt_idx}",
                        logger=logger.bind(clip_id=clip.clip_id, attempt=attempt_idx),
                        sample_fps=1,
                        ui_safe_ymin=effective_ui_safe_ymin,
                    )
                except TypeError:
                    # Best-effort: older worker images may not support ui_safe_ymin.
                    face95, ui95 = measure_overlap_p95_for_video(
                        video_path=out_video,
                        start_seconds=0.0,
                        end_seconds=float(duration),
                        placement=SubtitlePlacement(alignment=pl[0], x=pl[1], y=pl[2]),
                        play_res_x=play_res_x,
                        play_res_y=play_res_y,
                        work_dir=clip_dir / f"overlap_final_attempt_{attempt_idx}",
                        logger=logger.bind(clip_id=clip.clip_id, attempt=attempt_idx),
                        sample_fps=1,
                    )

                last_face95 = face95
                last_ui95 = ui95

                passed = face95 <= float(quality_gate_face_overlap_p95_threshold)
                attempts_log.append(
                    {
                        "attempt": attempt_idx,
                        "placement": {"alignment": pl[0], "x": pl[1], "y": pl[2]},
                        "face_overlap_ratio_p95": face95,
                        "ui_overlap_ratio_p95": ui95,
                        "passed": passed,
                    }
                )

                if not quality_gate_enabled or passed:
                    ok = True
                    break

            # If quality gate is enabled and we still failed, keep the last render but record failure.
            if quality_gate_enabled and not ok:
                logger.warning(
                    "subtitles.quality_gate_failed",
                    clip_id=clip.clip_id,
                    face_overlap_ratio_p95=last_face95,
                    threshold=quality_gate_face_overlap_p95_threshold,
                )

        if not out_video.exists() or out_video.stat().st_size <= 0:
            raise RuntimeError(f"ffmpeg produced no output for {clip.clip_id}")

        # Persist attempt log + final overlap metrics.
        if subtitles_enabled:
            try:
                metrics_path = clip_dir / "metrics.json"
                if metrics_path.exists():
                    raw = json.loads(metrics_path.read_text(encoding="utf-8"))
                else:
                    raw = {"clip_id": clip.clip_id, "subtitles": {"enabled": True}}

                raw.setdefault("subtitles", {}).setdefault("render_attempts", [])
                raw["subtitles"]["render_attempts"] = attempts_log

                if attempts_log:
                    last = attempts_log[-1]
                    raw.setdefault("subtitles", {}).setdefault("final_overlap", {})
                    raw["subtitles"]["final_overlap"] = {
                        "measured_on": "rendered_video",
                        "sample_fps": 1,
                        "ui_safe_ymin": effective_ui_safe_ymin,
                        "face_overlap_ratio_p95": last.get("face_overlap_ratio_p95", 0.0),
                        "ui_overlap_ratio_p95": last.get("ui_overlap_ratio_p95", 0.0),
                    }

                metrics_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                logger.exception("clip.final_overlap_write_failed", clip_id=clip.clip_id)

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
