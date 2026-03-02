from __future__ import annotations

from pathlib import Path

from ..utils.files import atomic_write_text
from .types import TranscriptSegment, WordTiming


def _srt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms_total = int(round(seconds * 1000))
    ms = ms_total % 1000
    s_total = ms_total // 1000
    s = s_total % 60
    m_total = s_total // 60
    m = m_total % 60
    h = m_total // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(*, segments: list[TranscriptSegment], output_path: Path) -> None:
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_srt_ts(seg.start_seconds)} --> {_srt_ts(seg.end_seconds)}")
        lines.append(seg.text)
        lines.append("")

    atomic_write_text(output_path, "\n".join(lines).rstrip() + "\n")


def write_srt_for_clip(
    *,
    clip_start_seconds: float,
    clip_end_seconds: float,
    segments: list[TranscriptSegment],
    output_path: Path,
) -> None:
    lines: list[str] = []
    idx = 1

    for seg in segments:
        if seg.end_seconds <= clip_start_seconds:
            continue
        if seg.start_seconds >= clip_end_seconds:
            break

        start = max(seg.start_seconds, clip_start_seconds) - clip_start_seconds
        end = min(seg.end_seconds, clip_end_seconds) - clip_start_seconds
        if end <= start:
            continue

        text = seg.text.strip()
        if not text:
            continue

        lines.append(str(idx))
        lines.append(f"{_srt_ts(start)} --> {_srt_ts(end)}")
        lines.append(text)
        lines.append("")
        idx += 1

    atomic_write_text(output_path, "\n".join(lines).rstrip() + "\n")


def _ass_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    cs_total = int(round(seconds * 100))
    cs = cs_total % 100
    s_total = cs_total // 100
    s = s_total % 60
    m_total = s_total // 60
    m = m_total % 60
    h = m_total // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _wrap(text: str, *, max_chars: int = 32) -> str:
    words = text.split()
    if not words:
        return ""

    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0

    for w in words:
        add = len(w) + (1 if cur else 0)
        if cur and cur_len + add > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += add

    if cur:
        lines.append(" ".join(cur))

    return "\\N".join(lines)


def write_stylized_ass_for_clip(
    *,
    clip_start_seconds: float,
    clip_end_seconds: float,
    segments: list[TranscriptSegment],
    output_path: Path,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    template: str = "default",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    template = (template or "default").lower().strip()

    style_line = "Style: Default,Arial,58,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,80,80,120,1"
    if template in {"modern", "modern_karaoke"}:
        # A cleaner, more modern look: slightly larger, stronger outline, and a safer bottom margin.
        style_line = "Style: Default,Arial,62,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,80,80,160,1"

    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            style_line,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    def karaoke_text(seg_text: str, *, duration_seconds: float) -> str:
        # ASS karaoke uses centiseconds.
        dur_cs = max(1, int(round(duration_seconds * 100)))
        words = [w for w in seg_text.split() if w]
        if not words:
            return ""

        per = max(1, dur_cs // len(words))
        remaining = dur_cs
        chunks: list[str] = []
        for i, w in enumerate(words):
            k = per if i < len(words) - 1 else max(1, remaining)
            remaining -= k
            chunks.append(f"{{\\k{k}}}{w}")
        return " ".join(chunks)

    events: list[str] = []

    for seg in segments:
        if seg.end_seconds <= clip_start_seconds:
            continue
        if seg.start_seconds >= clip_end_seconds:
            break

        start = max(seg.start_seconds, clip_start_seconds) - clip_start_seconds
        end = min(seg.end_seconds, clip_end_seconds) - clip_start_seconds
        if end <= start:
            continue

        if template in {"karaoke", "modern_karaoke"}:
            text = karaoke_text(seg.text, duration_seconds=(end - start))
        else:
            text = _wrap(seg.text)

        if not text:
            continue

        events.append(
            "Dialogue: 0,{},{},Default,,0,0,0,,{}".format(
                _ass_ts(start),
                _ass_ts(end),
                text,
            )
        )

    atomic_write_text(output_path, header + "\n" + "\n".join(events) + "\n")


def write_word_level_ass_for_clip(
    *,
    clip_start_seconds: float,
    clip_end_seconds: float,
    words: list[WordTiming],
    output_path: Path,
    placement: tuple[int, int, int] | None = None,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    template: str = "modern_karaoke",
    max_words_per_line: int = 10,
    max_chars_per_line: int = 42,
) -> None:
    """Generate a word-timed .ass file.

    - Uses real per-word durations when available.
    - Uses \pos() + \an to precisely place subtitles in a safe area.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    template = (template or "modern_karaoke").lower().strip()

    # Primary/Secondary are used by libass karaoke:
    # - SecondaryColour: base text
    # - PrimaryColour: highlighted portion
    style_line = "Style: Default,Arial,62,&H0000C8FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,80,80,160,1"
    if template in {"default", "karaoke"}:
        style_line = "Style: Default,Arial,58,&H0000C8FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,80,80,120,1"

    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            style_line,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    # placement = (alignment, x, y)
    if placement is None:
        placement = (2, play_res_x // 2, play_res_y - int(max(play_res_y * 0.08, 120)))

    an, px, py = placement
    pos_tag = f"{{\\an{an}\\pos({px},{py})\\blur2}}"

    # Select words for the clip and shift times to clip-relative.
    clip_words: list[WordTiming] = []
    for w in words:
        if w.end_seconds <= clip_start_seconds:
            continue
        if w.start_seconds >= clip_end_seconds:
            break
        start = max(w.start_seconds, clip_start_seconds) - clip_start_seconds
        end = min(w.end_seconds, clip_end_seconds) - clip_start_seconds
        if end <= start:
            continue
        clip_words.append(
            WordTiming(
                word=w.word,
                start_seconds=float(start),
                end_seconds=float(end),
                confidence=w.confidence,
            )
        )

    def _clean_text(t: str) -> str:
        return t.replace("{", "(").replace("}", ")").strip()

    def _emit_line(line_words: list[WordTiming]) -> tuple[float, float, str]:
        start = line_words[0].start_seconds
        end = line_words[-1].end_seconds
        dur_cs_total = max(1, int(round((end - start) * 100)))

        # Distribute centiseconds per word according to true durations.
        raw = [max(1, int(round((w.end_seconds - w.start_seconds) * 100))) for w in line_words]
        s = sum(raw)
        if s <= 0:
            raw = [1 for _ in raw]
            s = len(raw)

        scaled = [max(1, int(round(d * dur_cs_total / s))) for d in raw]
        # Fix rounding drift.
        drift = dur_cs_total - sum(scaled)
        if drift != 0:
            scaled[-1] = max(1, scaled[-1] + drift)

        parts = [f"{{\\k{scaled[i]}}}{_clean_text(w.word)}" for i, w in enumerate(line_words)]
        text = " ".join(parts)
        return start, end, text

    # Group into subtitle lines.
    lines: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    cur_chars = 0

    for w in clip_words:
        wtxt = _clean_text(w.word)
        add = len(wtxt) + (1 if cur else 0)

        gap = (w.start_seconds - cur[-1].end_seconds) if cur else 0.0
        too_long = (len(cur) >= max_words_per_line) or (cur_chars + add > max_chars_per_line)
        if cur and (gap > 0.60 or too_long):
            lines.append(cur)
            cur = []
            cur_chars = 0

        cur.append(w)
        cur_chars += add

    if cur:
        lines.append(cur)

    # Enforce 2-line max by merging extras.
    if len(lines) > 2:
        merged = lines[:1]
        rest = [w for l in lines[1:] for w in l]
        merged.append(rest)
        lines = merged

    events: list[str] = []
    for line_words in lines:
        if not line_words:
            continue

        start, end, text = _emit_line(line_words)

        events.append(
            "Dialogue: 0,{},{},Default,,0,0,0,,{}{}".format(
                _ass_ts(start),
                _ass_ts(end),
                pos_tag,
                text,
            )
        )

    atomic_write_text(output_path, header + "\n" + "\n".join(events) + "\n")
