from __future__ import annotations

import re
from difflib import SequenceMatcher

from .types import TranscriptSegment


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_SPLIT_RE = re.compile(r"(\b[\w']+\b)", re.UNICODE)


def _norm_word(w: str) -> str:
    return w.strip().lower()


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# Keep this list small + conservative. The goal is to fix very common
# transliteration drift without rewriting the transcript.
_WORD_CANON: dict[str, str] = {
    # Common variants for Muhammad
    "mohamed": "Muhammad",
    "mohammed": "Muhammad",
    "mohamad": "Muhammad",
    "mohammad": "Muhammad",
    "muhamed": "Muhammad",
    "muhammad": "Muhammad",
    "mouhamed": "Muhammad",
    "mouhamad": "Muhammad",
    "mouhammad": "Muhammad",

    # Common noisy transliterations (FR phonetics)
    "salalahou": "sallallahu",
    "sallalahou": "sallallahu",
    "salallahu": "sallallahu",

    # Ibrahim
    "ibrahim": "Ibrahim",
}


_PHRASES: list[tuple[str, float, set[str]]] = [
    (
        "sallallahu alayhi wa sallam",
        0.82,
        {"salam", "sallam", "alayhi", "haleyhi", "aleyhi"},
    ),
    (
        "alayhi wa sallam",
        0.86,
        {"salam", "sallam", "alayhi", "haleyhi", "aleyhi"},
    ),
    (
        "alayhi salam",
        0.86,
        {"salam", "alayhi", "haleyhi", "aleyhi"},
    ),
    (
        "subhanallah",
        0.88,
        {"subhanallah", "subhana"},
    ),
    (
        "alhamdulillah",
        0.88,
        {"alhamdulillah", "hamdulillah"},
    ),
    (
        "allahu akbar",
        0.86,
        {"akbar", "allahu", "allahou"},
    ),
]


def _apply_word_canon(text: str) -> str:
    parts = _SPLIT_RE.split(text)

    # Replace only word tokens (captured by split).
    for i, p in enumerate(parts):
        if not p or not _WORD_RE.fullmatch(p):
            continue

        k = _norm_word(p)
        canon = _WORD_CANON.get(k)
        if canon:
            parts[i] = canon

    return "".join(parts)


def _apply_phrase_canon(text: str) -> str:
    parts = _SPLIT_RE.split(text)
    word_positions = [i for i, p in enumerate(parts) if p and _WORD_RE.fullmatch(p)]
    words = [parts[i] for i in word_positions]
    lower = [_norm_word(w) for w in words]

    # Collect candidate matches then apply greedily (highest score first) without overlap.
    candidates: list[tuple[float, int, int, str]] = []

    for phrase, threshold, hints in _PHRASES:
        phrase_words = phrase.split()
        phrase_l = " ".join([w.lower() for w in phrase_words])
        n = len(phrase_words)

        # Skip if no hint word is present (cheap prefilter).
        if not any(h in lower for h in hints):
            continue

        for start in range(0, max(0, len(words) - 1)):
            # try small length variations
            for ln in (n - 1, n, n + 1):
                if ln <= 0:
                    continue
                end = start + ln
                if end > len(words):
                    continue

                window_l = " ".join(lower[start:end])
                score = _ratio(window_l, phrase_l)
                if score >= threshold:
                    candidates.append((score, start, end, phrase))

    candidates.sort(key=lambda x: (x[0], x[2] - x[1]), reverse=True)

    used = [False] * len(words)

    for score, start, end, phrase in candidates:
        if any(used[i] for i in range(start, end)):
            continue

        # Replace by writing the whole phrase into the first token and blanking the rest.
        words[start] = phrase
        for i in range(start + 1, end):
            words[i] = ""

        for i in range(start, end):
            used[i] = True

    # Write words back into the split parts and collapse whitespace.
    for w, pos in zip(words, word_positions, strict=True):
        parts[pos] = w

    out = "".join(parts)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def normalize_transcript_text(text: str) -> str:
    text = text.strip()
    if not text:
        return ""

    text = _apply_word_canon(text)
    text = _apply_phrase_canon(text)
    return text


def normalize_transcript_segments(
    *,
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    out: list[TranscriptSegment] = []
    for s in segments:
        out.append(
            TranscriptSegment(
                start_seconds=s.start_seconds,
                end_seconds=s.end_seconds,
                text=normalize_transcript_text(s.text),
            )
        )

    return out
