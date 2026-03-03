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

    style_line = "Style: Default,Noto Sans,58,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,80,80,220,1"
    if template in {"modern", "modern_karaoke"}:
        # A cleaner, more modern look: slightly larger, stronger outline, and a safer bottom margin.
        style_line = "Style: Default,Noto Sans,62,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,80,80,260,1"

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
    karaoke_mode = template in {"karaoke", "modern_karaoke"}

    if karaoke_mode:
        # Primary/Secondary are used by libass karaoke:
        # - SecondaryColour: base text
        # - PrimaryColour: highlighted portion
        style_line = "Style: Default,Noto Sans,62,&H0000C8FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,80,80,260,1"
        if template == "karaoke":
            style_line = "Style: Default,Noto Sans,58,&H0000C8FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,80,80,220,1"
    else:
        # Non-karaoke mode is more robust for mixed scripts (FR/EN/AR) and avoids
        # libass karaoke edge-cases.
        style_line = "Style: Default,Noto Sans,62,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,80,80,260,1"
        if template == "default":
            style_line = "Style: Default,Noto Sans,58,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,80,80,220,1"

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
        placement = (2, play_res_x // 2, play_res_y - int(max(play_res_y * 0.13, 220)))

    an, px, py = placement
    pos_tag = f"{{\\an{an}\\pos({px},{py})\\blur2}}"

    bidi_marks = {
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }

    def _clean_text(t: str) -> str:
        t = t.replace("{", "(").replace("}", ")")
        t = t.replace("\n", " ").replace("\r", " ")
        t = t.replace("\\", "/")
        t = "".join(ch for ch in t if ch not in bidi_marks)
        return t.strip()

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

        cleaned = _clean_text(w.word)
        if not cleaned:
            continue

        clip_words.append(
            WordTiming(
                word=cleaned,
                start_seconds=float(start),
                end_seconds=float(end),
                confidence=w.confidence,
            )
        )

    def _emit_event(page_lines: list[list[WordTiming]]) -> tuple[float, float, str] | None:
        event_words = [w for line in page_lines for w in line]
        if not event_words:
            return None

        start = event_words[0].start_seconds
        end = event_words[-1].end_seconds

        if karaoke_mode:
            dur_cs_total = max(1, int(round((end - start) * 100)))
            raw = [max(1, int(round((w.end_seconds - w.start_seconds) * 100))) for w in event_words]
            s = sum(raw)
            if s <= 0:
                raw = [1 for _ in raw]
                s = len(raw)

            scaled = [max(1, int(round(d * dur_cs_total / s))) for d in raw]
            drift = dur_cs_total - sum(scaled)
            if drift != 0:
                scaled[-1] = max(1, scaled[-1] + drift)

            idx = 0
            line_texts: list[str] = []
            for line in page_lines:
                parts: list[str] = []
                for w in line:
                    parts.append(f"{{\\k{scaled[idx]}}}{w.word}")
                    idx += 1
                line_texts.append(" ".join(parts))
            text = "\\N".join(line_texts)
        else:
            text = "\\N".join(" ".join(w.word for w in line) for line in page_lines)

        return start, end, text

    if not clip_words:
        atomic_write_text(output_path, header + "\n")
        return

    pages: list[list[list[WordTiming]]] = []
    page_lines: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    cur_chars = 0
    prev_end: float | None = None

    for w in clip_words:
        gap = (w.start_seconds - prev_end) if prev_end is not None else 0.0
        if (page_lines or cur) and gap > 0.80:
            if cur:
                page_lines.append(cur)
                cur = []
                cur_chars = 0
            if page_lines:
                pages.append(page_lines)
            page_lines = []

        add = len(w.word) + (1 if cur else 0)
        too_long = (len(cur) >= max_words_per_line) or (cur_chars + add > max_chars_per_line)

        if cur and too_long:
            if len(page_lines) == 0:
                page_lines.append(cur)
                cur = []
                cur_chars = 0
            else:
                page_lines.append(cur)
                pages.append(page_lines)
                page_lines = []
                cur = []
                cur_chars = 0

        cur.append(w)
        cur_chars += add
        prev_end = w.end_seconds

    if cur:
        page_lines.append(cur)
    if page_lines:
        pages.append(page_lines)

    events: list[str] = []
    for page in pages:
        emitted = _emit_event(page)
        if emitted is None:
            continue
        start, end, text = emitted
        events.append(
            "Dialogue: 0,{},{},Default,,0,0,0,,{}{}".format(
                _ass_ts(start),
                _ass_ts(end),
                pos_tag,
                text,
            )
        )

    atomic_write_text(output_path, header + "\n" + "\n".join(events) + "\n")
