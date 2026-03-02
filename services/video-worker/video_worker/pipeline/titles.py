from __future__ import annotations

import re

from .types import ClipCandidate, TranscriptSegment


def _clean_phrase(text: str) -> str:
    t = re.sub(r"\s+", " ", text.strip())
    t = t.strip("-–—:;,. ")
    return t


def generate_clip_title(
    *,
    clip: ClipCandidate,
    segments: list[TranscriptSegment],
    language: str | None,
) -> str:
    lang = (language or "en").lower().strip()

    window_texts: list[str] = []
    for s in segments:
        if s.end_seconds <= clip.start_seconds:
            continue
        if s.start_seconds >= clip.end_seconds:
            break
        t = _clean_phrase(s.text)
        if t:
            window_texts.append(t)

    seed = window_texts[0] if window_texts else ""

    # Prefer a sentence that already looks like a hook.
    for t in window_texts:
        if "?" in t or re.search(r"\b(secret|mistake|never|stop|nobody)\b", t, re.I):
            seed = t
            break

    seed_short = " ".join(seed.split()[:10])
    seed_short = _clean_phrase(seed_short)

    reasons = set([r for r in (clip.reason or "").split(",") if r])

    if lang == "fr":
        if "question_hook" in reasons or "?" in seed:
            return _clean_phrase(f"Et si vous pouviez {seed_short.lower()} ?")
        if "pattern_interrupt" in reasons:
            return _clean_phrase(f"Ne fais plus cette erreur : {seed_short}")
        if seed_short:
            return _clean_phrase(f"Le déclic : {seed_short}")
        return "Le passage le plus important"

    if "question_hook" in reasons or "?" in seed:
        return _clean_phrase(f"What if you could {seed_short.lower()}?")
    if "pattern_interrupt" in reasons:
        return _clean_phrase(f"Stop making this mistake: {seed_short}")
    if seed_short:
        return _clean_phrase(f"The key insight: {seed_short}")
    return "The most important part"
