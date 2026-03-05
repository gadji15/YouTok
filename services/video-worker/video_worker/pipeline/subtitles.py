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


def _scale_font_size(*, base: int, play_res_x: int, play_res_y: int) -> int:
    scaled = base * float(play_res_y) / 1920.0

    # For landscape (YouTube/source) outputs, videos are often letterboxed on phone
    # screens which makes subtitles feel smaller. Compensate slightly.
    if play_res_x > play_res_y:
        scaled *= 1.35

    return max(30, min(112, int(round(scaled))))


def _wrap(text: str, *, max_chars: int = 32) -> str:
    # break words that exceed max_chars to avoid horizontal overflow
    def _break_long_word(word: str) -> list[str]:
        if len(word) <= max_chars:
            return [word]
        parts: list[str] = []
        idx = 0
        while idx < len(word):
            parts.append(word[idx : idx + max_chars])
            idx += max_chars
        return parts

    words = text.split()
    if not words:
        return ""

    expanded: list[str] = []
    for w in words:
        if len(w) > max_chars:
            expanded.extend(_break_long_word(w))
        else:
            expanded.append(w)

    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0

    for w in expanded:
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

    font_size = _scale_font_size(
        base=74 if template == "default" else 78,
        play_res_x=play_res_x,
        play_res_y=play_res_y,
    )

    # increase horizontal margins to give extra padding from screen edges
    style_line = f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,120,120,220,1"
    if template in {"modern", "modern_karaoke"}:
        # A cleaner, more modern look: slightly larger, stronger outline, and a safer bottom margin.
        style_line = f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,120,120,260,1"

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
    r"""Generate a word-timed .ass file.

    Templates:
    - default|modern|karaoke|modern_karaoke (existing)
    - cinematic|cinematic_karaoke (new): slightly larger, more contrast, subtle pop-in.

    Notes:
    - Uses per-word timings to split into short, readable subtitle "chunks".
    - Karaoke highlighting is only enabled for templates explicitly ending with "_karaoke"
      (or "karaoke"), and is disabled for RTL scripts (e.g. Arabic) where karaoke is
      frequently rendered poorly.
    - Uses \pos() + \an to precisely place subtitles in a safe area.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    template = (template or "modern_karaoke").lower().strip()

    def _clean_text(t: str) -> str:
        t = t.replace("{", "(").replace("}", ")")
        # Strip common bidi markers that can break line layout.
        t = t.replace("\u200e", "").replace("\u200f", "").replace("\u202a", "").replace("\u202b", "").replace("\u202c", "")
        return t.strip()

    def _contains_rtl(t: str) -> bool:
        import re

        return re.search(r"[\u0590-\u08FF]", t) is not None

    karaoke_enabled = template in {"karaoke", "modern_karaoke", "cinematic_karaoke"}

    cinematic = template in {"cinematic", "cinematic_karaoke"}

    base_size = 78
    if template == "default":
        base_size = 74
    elif template in {"cinematic", "cinematic_karaoke"}:
        base_size = 84

    font_size = _scale_font_size(base=base_size, play_res_x=play_res_x, play_res_y=play_res_y)

    # Styles:
    # - Karaoke: Primary = highlight, Secondary = base
    # - Non-karaoke: Primary = base
    if karaoke_enabled:
        style_line = f"Style: Default,Noto Sans,{font_size},&H0000C8FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,120,120,160,1"
        if template == "karaoke":
            style_line = f"Style: Default,Noto Sans,{font_size},&H0000C8FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,120,120,120,1"
        if template == "cinematic_karaoke":
            # Larger, higher contrast, slightly stronger shadow.
            style_line = f"Style: Default,Noto Sans,{font_size},&H0000C8FF,&H00FFFFFF,&H00101010,&H90000000,1,0,0,0,100,100,0,0,1,7,1,2,120,120,170,1"
    else:
        style_line = f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,120,120,160,1"
        if template == "default":
            style_line = f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,120,120,120,1"
        if template == "cinematic":
            style_line = f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,1,0,0,0,100,100,0,0,1,7,1,2,120,120,170,1"

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
        placement = (2, play_res_x // 2, play_res_y - int(max(play_res_y * 0.14, 240)))

    an, px, py = placement

    # Cinematic template: subtle pop-in and slightly stronger blur for a smoother look.
    if template in {"cinematic", "cinematic_karaoke"}:
        pos_tag = f"{{\\an{an}\\pos({px},{py})\\blur3\\fad(80,120)}}"
    else:
        pos_tag = f"{{\\an{an}\\pos({px},{py})\\blur2}}"

    # Select words for the clip and shift times to clip-relative.
    clip_words: list[WordTiming] = []

    def _is_punct_only(t: str) -> bool:
        import re

        return re.fullmatch(r"[\,\.\!\?\;\:\…\)\]\}\»]+", t) is not None

    for w in words:
        if w.end_seconds <= clip_start_seconds:
            continue
        if w.start_seconds >= clip_end_seconds:
            break
        start = max(w.start_seconds, clip_start_seconds) - clip_start_seconds
        end = min(w.end_seconds, clip_end_seconds) - clip_start_seconds
        if end <= start:
            continue

        wt = _clean_text(w.word)
        if not wt:
            continue

        # WhisperX often emits punctuation as separate "words" (e.g. "," or "?").
        # If we join with spaces, we get "anti-space" before punctuation.
        # Merge punctuation tokens into the previous word instead.
        if _is_punct_only(wt) and clip_words:
            prev = clip_words[-1]
            clip_words[-1] = WordTiming(
                word=prev.word + wt,
                start_seconds=prev.start_seconds,
                end_seconds=float(end),
                confidence=prev.confidence,
            )
            continue

        clip_words.append(
            WordTiming(
                word=wt,
                start_seconds=float(start),
                end_seconds=float(end),
                confidence=w.confidence,
            )
        )

    clip_words.sort(key=lambda x: (x.start_seconds, x.end_seconds))

    if any(_contains_rtl(w.word) for w in clip_words):
        karaoke_enabled = False
        cinematic = False

    def _norm_for_match(t: str) -> str:
        import re

        t = t.lower()
        t = re.sub(r"[^0-9a-zA-Z\u00C0-\u024F]+", "", t)
        return t

    def _pick_hook_words() -> set[str]:
        # Best-effort keyword selection for the opening hook.
        # We keep it deterministic and simple (no ML here).
        hook_window_seconds = 3.0

        power_words = {
            # EN
            "secret",
            "shocking",
            "insane",
            "unbelievable",
            "truth",
            "warning",
            "listen",
            "imagine",
            "story",
            "miracle",
            # FR
            "incroyable",
            "dingue",
            "vérité",
            "verite",
            "attention",
            "écoute",
            "ecoute",
            "histoire",
            "miracle",
            # Common transliterations / niche words (kept minimal)
            "subhanallah",
            "allah",
            "quran",
            "coran",
            "hadith",
            "sunnah",
        }

        stop = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "to",
            "of",
            "in",
            "on",
            "for",
            "with",
            "is",
            "are",
            "was",
            "were",
            "be",
            "this",
            "that",
            "it",
            "i",
            "you",
            "we",
            "they",
            "he",
            "she",
            "them",
            "his",
            "her",
            "our",
            "your",
            "my",
            "me",
            "do",
            "does",
            "did",
            "dont",
            "not",
            "no",
            "oui",
            "non",
            "et",
            "ou",
            "de",
            "des",
            "du",
            "la",
            "le",
            "les",
            "un",
            "une",
            "dans",
            "sur",
            "pour",
            "avec",
            "est",
            "sont",
            "été",
            "etre",
            "être",
            "ce",
            "cet",
            "cette",
            "ça",
            "ca",
            "je",
            "tu",
            "il",
            "elle",
            "nous",
            "vous",
            "ils",
            "elles",
        }

        scored: dict[str, float] = {}
        for w in clip_words:
            if w.start_seconds > hook_window_seconds:
                break

            raw = _norm_for_match(w.word)
            if not raw or raw in stop:
                continue

            score = 0.0
            if raw in power_words:
                score += 3.0

            if len(raw) >= 4:
                score += min(12, len(raw)) / 8.0

            # Prefer earlier
            score += 1.0 / (0.35 + float(w.start_seconds))

            scored[raw] = max(scored.get(raw, 0.0), score)

        top = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {k for k, _ in top}

    hook_words = _pick_hook_words() if cinematic else set()

    def _is_hook_word(word: str, start_seconds: float) -> bool:
        if not cinematic:
            return False
        if start_seconds > 3.0:
            return False
        k = _norm_for_match(word)
        return bool(k) and k in hook_words

    def _split_two_lines(parts: list[str], lens: list[int]) -> tuple[list[str], list[str]]:
        # split text parts into two lines, breaking overlong words if necessary
        def _break_part(p: str) -> list[str]:
            if len(p) <= max_chars_per_line:
                return [p]
            # break mid-part on max_chars_per_line boundaries
            return [p[i : i + max_chars_per_line] for i in range(0, len(p), max_chars_per_line)]

        expanded_parts: list[str] = []
        expanded_lens: list[int] = []
        for p, ln in zip(parts, lens):
            if ln > max_chars_per_line:
                subs = _break_part(p)
                expanded_parts.extend(subs)
                expanded_lens.extend([len(s) for s in subs])
            else:
                expanded_parts.append(p)
                expanded_lens.append(ln)

        line1: list[str] = []
        line2: list[str] = []
        c1 = 0
        c2 = 0

        for p, ln in zip(expanded_parts, expanded_lens):
            add1 = ln + (1 if line1 else 0)
            add2 = ln + (1 if line2 else 0)

            fits1 = (len(line1) < max_words_per_line) and (c1 + add1 <= max_chars_per_line)
            fits2 = (len(line2) < max_words_per_line) and (c2 + add2 <= max_chars_per_line)

            if line2:
                if fits2:
                    line2.append(p)
                    c2 += add2
                else:
                    # Best-effort: overflow, but avoid dropping words.
                    line2.append(p)
            else:
                if fits1:
                    line1.append(p)
                    c1 += add1
                else:
                    line2.append(p)
                    c2 += add2

        return line1, line2

    def _emit_event(chunk: list[WordTiming]) -> tuple[float, float, str]:
        if not chunk:
            return 0.0, 0.01, ""

        chunk = sorted(chunk, key=lambda x: (x.start_seconds, x.end_seconds))
        start = min(w.start_seconds for w in chunk)
        end = max(w.end_seconds for w in chunk)
        if end <= start:
            end = start + 0.01

        cinematic = template in {"cinematic", "cinematic_karaoke"}

        highlighted = 0
        max_highlights_per_event = 3

        def _format_word(*, w: WordTiming, prefix: str = "") -> str:
            nonlocal highlighted
            if _is_hook_word(w.word, w.start_seconds) and highlighted < max_highlights_per_event:
                highlighted += 1
                return prefix + f"{{\\c&H0033D6FF&\\b1\\bord7}}{w.word}{{\\r}}"
            return prefix + w.word

        if karaoke_enabled:
            dur_cs_total = max(1, int(round((end - start) * 100)))
            raw = [max(1, int(round((w.end_seconds - w.start_seconds) * 100))) for w in chunk]
            s = sum(raw)
            if s <= 0:
                raw = [1 for _ in raw]
                s = len(raw)

            scaled = [max(1, int(round(d * dur_cs_total / s))) for d in raw]
            drift = dur_cs_total - sum(scaled)
            if drift != 0:
                scaled[-1] = max(1, scaled[-1] + drift)

            parts = [_format_word(w=chunk[i], prefix=f"{{\\k{scaled[i]}}}") for i in range(len(chunk))]
        else:
            parts = [_format_word(w=w) for w in chunk]

        lens = [len(w.word) for w in chunk]
        line1, line2 = _split_two_lines(parts, lens)

        if line2:
            text = " ".join(line1) + "\\N" + " ".join(line2)
        else:
            text = " ".join(line1)

        if cinematic:
            # Subtle scale-in at the start of each event.
            # This works well on TikTok without being distracting.
            text = "{\\t(0,120,\\fscx105\\fscy105)}" + text

        return start, end, text

    max_words_per_event = max_words_per_line * 2
    max_chars_per_event = max_chars_per_line * 2

    # Without karaoke, long events feel like "frozen" subtitles because the text doesn't change.
    # With karaoke enabled, keeping events a bit longer is fine since highlighting moves.
    max_event_seconds = 6.0 if karaoke_enabled else 2.8

    chunks: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    cur_chars = 0

    for w in clip_words:
        gap = (w.start_seconds - cur[-1].end_seconds) if cur else 0.0

        add = len(w.word) + (1 if cur else 0)

        # Flush current chunk on obvious breaks.
        if cur and gap > 0.85:
            chunks.append(cur)
            cur = []
            cur_chars = 0

        # Enforce max chunk duration even when speech is continuous (small gaps).
        if cur:
            next_duration = w.end_seconds - cur[0].start_seconds
            if next_duration > max_event_seconds:
                chunks.append(cur)
                cur = []
                cur_chars = 0

        would_exceed = (len(cur) >= max_words_per_event) or (cur_chars + add > max_chars_per_event)
        if cur and would_exceed:
            chunks.append(cur)
            cur = []
            cur_chars = 0
            add = len(w.word)

        cur.append(w)
        cur_chars += add

    if cur:
        chunks.append(cur)

    events: list[str] = []
    for chunk in chunks:
        start, end, text = _emit_event(chunk)
        if not text:
            continue

        events.append(
            "Dialogue: 0,{},{},Default,,0,0,0,,{}{}".format(
                _ass_ts(start),
                _ass_ts(end),
                pos_tag,
                text,
            )
        )

    atomic_write_text(output_path, header + "\n" + "\n".join(events) + "\n")
