from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from ..utils.ffprobe import probe_video
from .segment import score_text
from .types import ClipCandidate, TranscriptSegment


@dataclass(frozen=True)
class YoutubeChapter:
    title: str
    start_seconds: float
    end_seconds: float


def get_youtube_chapters(
    *,
    youtube_url: str,
    logger: structlog.BoundLogger,
    video_path: Path | None = None,
) -> list[YoutubeChapter]:
    """Best-effort extraction of YouTube chapters.

    Uses yt-dlp metadata. Returns an empty list when chapters aren't available.
    """

    duration = None
    if video_path is not None and video_path.exists():
        try:
            duration = float(probe_video(video_path).duration_seconds)
        except Exception:
            duration = None

    try:
        proc = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--dump-single-json",
                "--no-warnings",
                youtube_url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
    except Exception:
        logger.info("chapters.unavailable")
        return []

    raw = payload.get("chapters")
    if not isinstance(raw, list) or not raw:
        return []

    out: list[YoutubeChapter] = []

    for c in raw:
        if not isinstance(c, dict):
            continue

        title = str(c.get("title") or "").strip() or "Chapter"
        start = c.get("start_time")
        end = c.get("end_time")

        try:
            start_f = float(start)
        except Exception:
            continue

        end_f = None
        try:
            if end is not None:
                end_f = float(end)
        except Exception:
            end_f = None

        if end_f is None and duration is not None:
            end_f = duration

        if end_f is None:
            continue

        if end_f <= start_f:
            continue

        out.append(YoutubeChapter(title=title, start_seconds=start_f, end_seconds=end_f))

    # Defensive: ensure deterministic ordering.
    out.sort(key=lambda ch: (ch.start_seconds, ch.end_seconds))

    # Drop near-duplicates / tiny chapters.
    cleaned: list[YoutubeChapter] = []
    for ch in out:
        if cleaned and abs(cleaned[-1].start_seconds - ch.start_seconds) < 0.01 and abs(cleaned[-1].end_seconds - ch.end_seconds) < 0.01:
            continue
        if (ch.end_seconds - ch.start_seconds) < 1.0:
            continue
        cleaned.append(ch)

    return cleaned


def _collect_text(*, segments: list[TranscriptSegment], start: float, end: float) -> str:
    parts: list[str] = []
    for s in segments:
        if s.end_seconds <= start:
            continue
        if s.start_seconds >= end:
            break
        if s.text.strip():
            parts.append(s.text.strip())
    return " ".join(parts).strip()


def build_chapter_clips(
    *,
    chapters: list[YoutubeChapter],
    segments: list[TranscriptSegment],
    max_seconds: float | None = None,
    min_seconds: float = 1.0,
) -> list[ClipCandidate]:
    clips: list[ClipCandidate] = []

    max_s = float(max_seconds) if max_seconds is not None else None
    if max_s is not None:
        max_s = max(1.0, max_s)

    min_s = max(1.0, float(min_seconds))

    idx = 1
    for ch in chapters:
        start = float(ch.start_seconds)
        end = float(ch.end_seconds)
        if end <= start:
            continue

        if max_s is None or (end - start) <= max_s + 0.01:
            text = _collect_text(segments=segments, start=start, end=end)
            s, _ = score_text(text)

            clips.append(
                ClipCandidate(
                    clip_id=f"clip_{idx:03d}",
                    start_seconds=round(float(start), 2),
                    end_seconds=round(float(end), 2),
                    score=round(float(s), 4),
                    reason="chapter",
                    title=ch.title,
                )
            )
            idx += 1
            continue

        # Split long chapters into slices.
        part = 1
        cur = start
        while cur < end - 0.01:
            slice_end = min(end, cur + max_s)
            if slice_end - cur < min_s:
                break

            text = _collect_text(segments=segments, start=cur, end=slice_end)
            s, _ = score_text(text)

            clips.append(
                ClipCandidate(
                    clip_id=f"clip_{idx:03d}",
                    start_seconds=round(float(cur), 2),
                    end_seconds=round(float(slice_end), 2),
                    score=round(float(s), 4),
                    reason="chapter_slice",
                    title=f"{ch.title} (Part {part})",
                )
            )
            idx += 1
            part += 1
            cur = slice_end

    return clips


def build_sequential_clips(
    *,
    duration_seconds: float,
    max_seconds: float,
    min_seconds: float = 1.0,
) -> list[ClipCandidate]:
    duration_seconds = max(0.0, float(duration_seconds))
    max_seconds = max(1.0, float(max_seconds))
    min_seconds = max(1.0, float(min_seconds))

    if duration_seconds <= 0.01:
        return []

    clips: list[ClipCandidate] = []

    start = 0.0
    idx = 1
    while start < duration_seconds - 0.01:
        end = min(duration_seconds, start + max_seconds)
        if end - start >= min_seconds:
            clips.append(
                ClipCandidate(
                    clip_id=f"clip_{idx:03d}",
                    start_seconds=round(float(start), 2),
                    end_seconds=round(float(end), 2),
                    score=0.0,
                    reason="slice",
                    title=None,
                )
            )
            idx += 1

        start = end

    return clips
