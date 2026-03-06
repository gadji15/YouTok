from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import re

from ..utils.files import atomic_write_text
from .features import compute_audio_window_features
from .types import TranscriptSegment, WordTiming


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)

_HOOK_PATTERNS_EN: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\b(you|your)\b", re.I), 0.10),
    (re.compile(r"\b(how to|how do|why|what if|wait|watch)\b", re.I), 0.25),
    (re.compile(r"\b(secret|mistake|never|stop|nobody|everyone)\b", re.I), 0.25),
    (re.compile(r"\b(shocking|insane|crazy|unbelievable|wild)\b", re.I), 0.20),
]

_HOOK_PATTERNS_FR: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\b(tu|toi|ton|ta|tes|vous|votre|vos)\b", re.I), 0.10),
    (re.compile(r"\b(comment|pourquoi|et si|attends|regarde)\b", re.I), 0.25),
    (re.compile(r"\b(secret|erreur|jamais|arrete|arrête|stop|personne|tout le monde)\b", re.I), 0.25),
    (re.compile(r"\b(incroyable|choquant|dingue|fou|impossible)\b", re.I), 0.20),
]

_EMOTION_WORDS_EN = {
    "amazing",
    "insane",
    "shocking",
    "crazy",
    "unbelievable",
    "truth",
    "mistake",
    "warning",
    "secret",
    "story",
    "error",
}

_EMOTION_WORDS_FR = {
    "incroyable",
    "choquant",
    "dingue",
    "fou",
    "vérité",
    "verite",
    "erreur",
    "histoire",
    "secret",
    "attention",
}


@dataclass(frozen=True)
class HookDetection:
    start_seconds: float
    score: float


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def score_text(text: str, *, language: str | None = None) -> float:
    t = (text or "").strip()
    if not t:
        return 0.0

    lang = (language or "en").lower().strip()
    patterns = _HOOK_PATTERNS_FR if lang == "fr" else _HOOK_PATTERNS_EN

    score = 0.0

    exclaim = t.count("!")
    question = t.count("?")
    if exclaim:
        score += 0.05 * min(exclaim, 3)
    if question:
        score += 0.08 * min(question, 3)

    word_count = len(_WORD_RE.findall(t))
    score += min(word_count / 32.0, 0.25)

    for pattern, weight in patterns:
        if pattern.search(t):
            score += weight

    return _clamp01(score)


def emotion_word_score(text: str, *, language: str | None = None) -> float:
    t = (text or "").strip()
    if not t:
        return 0.0

    lang = (language or "en").lower().strip()
    emo = _EMOTION_WORDS_FR if lang == "fr" else _EMOTION_WORDS_EN

    tokens = [w.lower() for w in _WORD_RE.findall(t)]
    if not tokens:
        return 0.0

    hits = 0
    for w in tokens:
        if w in emo:
            hits += 1

    return float(min(1.0, hits / 2.0))


def _collect_text(*, segments: list[TranscriptSegment], start: float, end: float) -> str:
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


def detect_hook_start_seconds(
    *,
    segments: list[TranscriptSegment],
    words: list[WordTiming] | None,
    audio_path: Path | None,
    clip_start_seconds: float,
    clip_end_seconds: float,
    language: str | None,
    hook_window_seconds: float = 3.0,
    shift_max_seconds: float = 2.0,
) -> HookDetection | None:
    if clip_end_seconds <= clip_start_seconds:
        return None

    hook_window_seconds = max(0.5, float(hook_window_seconds))
    shift_max_seconds = max(0.0, float(shift_max_seconds))

    clip_duration = float(clip_end_seconds - clip_start_seconds)
    if clip_duration < 2.0:
        return None

    step = 0.25
    max_off = min(shift_max_seconds, max(0.0, clip_duration - 1.0))

    best: HookDetection | None = None

    off = 0.0
    while off <= (max_off + 1e-9):
        t0 = float(clip_start_seconds + off)
        t1 = float(min(clip_end_seconds, t0 + hook_window_seconds))

        text = _collect_text(segments=segments, start=t0, end=t1)
        text_score = score_text(text, language=language)
        emo = emotion_word_score(text, language=language)

        boundary_bonus = 0.0
        if words:
            for w in words:
                if w.start_seconds < t0:
                    continue
                if w.start_seconds > t0 + 0.15:
                    break
                boundary_bonus = 0.05
                break

        energy_score = 0.0
        silence_score = 0.0
        if audio_path is not None and audio_path.exists():
            a = compute_audio_window_features(
                wav_path=audio_path,
                start_seconds=t0,
                end_seconds=min(clip_end_seconds, t0 + 1.0),
            )
            if a is not None:
                energy_score = _clamp01((a.rms * 4.0) + (a.rms_std * 10.0))
                silence_score = _clamp01(1.0 - float(a.silence_ratio))

        score = (
            (0.45 * float(text_score))
            + (0.15 * float(emo))
            + (0.30 * float(energy_score))
            + (0.10 * float(silence_score))
            + boundary_bonus
        )

        score = _clamp01(score - (off * 0.03))

        cand = HookDetection(start_seconds=t0, score=score)

        if best is None:
            best = cand
        else:
            if cand.score > best.score + 1e-6:
                best = cand
            elif abs(cand.score - best.score) <= 1e-6 and cand.start_seconds < best.start_seconds:
                best = cand

        off += step

    if best is None or best.score < 0.62:
        return None

    return best


def build_hook_text(
    *,
    segments: list[TranscriptSegment],
    clip_start_seconds: float,
    clip_end_seconds: float,
    window_seconds: float = 3.0,
    max_chars: int = 70,
) -> str:
    text = _collect_text(
        segments=segments,
        start=float(clip_start_seconds),
        end=float(min(clip_end_seconds, clip_start_seconds + float(window_seconds))),
    )

    if not text:
        return ""

    for sep in ["? ", "! ", ". ", "… ", "... "]:
        if sep in text:
            text = text.split(sep, 1)[0].strip() + sep.strip()
            break

    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text

    out: list[str] = []
    n = 0
    for w in text.split():
        if n + len(w) + (1 if out else 0) > max_chars:
            break
        out.append(w)
        n += len(w) + (1 if out else 0)

    s = " ".join(out).strip()
    if s and s[-1] not in {"?", "!", "."}:
        s += "…"
    return s


_EMOJI_MAP_FR: list[tuple[set[str], str]] = [
    ({"argent", "money", "riche", "richesse", "euro", "euros"}, "💰"),
    ({"incroyable", "dingue", "choquant", "fou", "impossible"}, "😲"),
    ({"secret", "secrets"}, "🤫"),
    ({"attention", "danger", "risque"}, "⚠️"),
    ({"gratuit", "cadeau", "bonus"}, "🎁"),
    ({"voyage", "voyager", "avion", "pays"}, "✈️"),
]

_EMOJI_MAP_EN: list[tuple[set[str], str]] = [
    ({"money", "cash", "wealth", "rich"}, "💰"),
    ({"unbelievable", "insane", "shocking", "crazy"}, "😲"),
    ({"secret", "secrets"}, "🤫"),
    ({"warning", "danger", "risk"}, "⚠️"),
    ({"free", "gift", "bonus"}, "🎁"),
    ({"travel", "trip", "flight", "country"}, "✈️"),
]


def find_emoji_events(
    *,
    words: list[WordTiming],
    clip_start_seconds: float,
    clip_end_seconds: float,
    language: str | None,
    max_emojis: int = 6,
) -> list[dict]:
    max_emojis = max(0, int(max_emojis))
    if max_emojis <= 0:
        return []

    lang = (language or "en").lower().strip()
    mapping = _EMOJI_MAP_FR if lang == "fr" else _EMOJI_MAP_EN

    lookup: dict[str, str] = {}
    for tokens, emoji in mapping:
        for t in tokens:
            lookup[t] = emoji

    out: list[dict] = []
    used: set[str] = set()

    for w in words:
        if w.end_seconds <= clip_start_seconds:
            continue
        if w.start_seconds >= clip_end_seconds:
            break

        token = (w.word or "").strip().lower()
        token = re.sub(r"[^\w']+", "", token)
        if not token or token in used:
            continue

        emoji = lookup.get(token)
        if not emoji:
            continue

        used.add(token)

        start = max(0.0, float(w.start_seconds - clip_start_seconds) - 0.05)
        end = min(float(clip_end_seconds - clip_start_seconds), start + 0.55)

        out.append({"emoji": emoji, "start": start, "end": end, "token": token})
        if len(out) >= max_emojis:
            break

    return out


def write_viral_overlays_ass_for_clip(
    *,
    clip_start_seconds: float,
    clip_end_seconds: float,
    transcript_segments: list[TranscriptSegment],
    word_timings: list[WordTiming] | None,
    language: str | None,
    output_path: Path,
    play_res_x: int,
    play_res_y: int,
    hook_text_enabled: bool,
    emojis_enabled: bool,
    max_emojis: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = max(0.01, float(clip_end_seconds - clip_start_seconds))

    hook_text = ""
    if hook_text_enabled:
        hook_text = build_hook_text(
            segments=transcript_segments,
            clip_start_seconds=clip_start_seconds,
            clip_end_seconds=clip_end_seconds,
            window_seconds=min(3.0, duration),
        )

    emoji_events: list[dict] = []
    if emojis_enabled and word_timings:
        emoji_events = find_emoji_events(
            words=word_timings,
            clip_start_seconds=clip_start_seconds,
            clip_end_seconds=clip_end_seconds,
            language=language,
            max_emojis=max_emojis,
        )

    if not hook_text and not emoji_events:
        return

    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {int(play_res_x)}",
            f"PlayResY: {int(play_res_y)}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Hook,DejaVu Sans,78,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,1,0,0,0,100,100,0,0,1,6,0,8,80,80,40,1",
            "Style: Emoji,DejaVu Sans,96,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,1,0,0,0,100,100,0,0,1,6,0,9,60,60,40,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

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

    events: list[str] = []

    if hook_text:
        start = 0.05
        end = min(1.9, duration)
        x = int(round(play_res_x * 0.50))
        y = int(round(play_res_y * 0.18))
        text = hook_text.replace("\n", " ").replace("\\N", " ")
        events.append(
            "Dialogue: 20,{},{},Hook,,0,0,0,,{{\\pos({},{})\\fad(100,160)}}{}".format(
                _ass_ts(start),
                _ass_ts(end),
                x,
                y,
                text,
            )
        )

    for idx, ev in enumerate(emoji_events):
        start = float(ev["start"])
        end = float(ev["end"])
        x = int(round(play_res_x * (0.84 - (0.05 * (idx % 2)))))
        y = int(round(play_res_y * (0.22 + (0.07 * (idx % 3)))))
        events.append(
            "Dialogue: 30,{},{},Emoji,,0,0,0,,{{\\pos({},{})\\fad(60,120)}}{}".format(
                _ass_ts(start),
                _ass_ts(end),
                x,
                y,
                ev["emoji"],
            )
        )

    atomic_write_text(output_path, header + "\n" + "\n".join(events).rstrip() + "\n")
