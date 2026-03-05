from __future__ import annotations

import json
import re
import time
from functools import lru_cache

import httpx
import structlog

from .types import TranscriptSegment


_FILLERS_EN = {
    "um",
    "uh",
    "erm",
    "like",
}

_FILLERS_FR = {
    "euh",
    "heu",
    "bah",
}


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def _clean_whitespace(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r"\s+([!?;:,.])", r"\1", s)
    return s


def _dedupe_immediate_words(text: str) -> str:
    tokens = text.split()
    if len(tokens) < 3:
        return text

    out: list[str] = []
    prev = None
    repeat = 0

    for tok in tokens:
        k = tok.lower()
        if prev is not None and k == prev:
            repeat += 1
            # Keep at most 2 immediate repeats.
            if repeat >= 2:
                continue
        else:
            repeat = 0
        out.append(tok)
        prev = k

    return " ".join(out)


def _remove_fillers(text: str, *, language: str) -> str:
    lang = (language or "en").lower().strip()
    fillers = _FILLERS_FR if lang == "fr" else _FILLERS_EN

    parts = text.split()
    if not parts:
        return text

    out: list[str] = []
    for p in parts:
        w = re.sub(r"[^\w']+", "", p.lower())
        if w in fillers:
            continue
        out.append(p)

    return " ".join(out)


def heuristic_cleanup_text(text: str, *, language: str) -> str:
    text = _clean_whitespace(text)
    if not text:
        return ""

    text = _dedupe_immediate_words(text)
    text = _remove_fillers(text, language=language)
    text = _clean_whitespace(text)
    return text


def _edit_distance_limited(a: str, b: str, limit: int) -> int:
    # Early-exit Levenshtein for small limits.
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        row_min = cur[0]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            v = min(ins, dele, sub)
            cur.append(v)
            if v < row_min:
                row_min = v

        if row_min > limit:
            return limit + 1
        prev = cur

    return prev[-1]


try:
    from spellchecker import SpellChecker as _SpellChecker  # type: ignore
except Exception:  # pragma: no cover
    _SpellChecker = None


@lru_cache(maxsize=4)
def _get_spellchecker(lang: str):
    if _SpellChecker is None:
        return None

    try:
        return _SpellChecker(language=lang)
    except Exception:
        return _SpellChecker(language="en")


def spellcheck_cleanup_text(text: str, *, language: str) -> str:
    # Heuristic cleanup first (remove fillers/repeats), then conservative spellcheck.
    cleaned = heuristic_cleanup_text(text, language=language)
    if not cleaned:
        return ""

    lang = (language or "en").strip().lower()
    sc = _get_spellchecker(lang)
    if sc is None:
        return cleaned

    tokens = [m.group(0) for m in _WORD_RE.finditer(cleaned)]
    candidates = [
        t
        for t in tokens
        if t == t.lower() and t.isalpha() and len(t) >= 3 and "'" not in t
    ]

    if not candidates:
        return cleaned

    unknown = sc.unknown(candidates)
    if not unknown:
        return cleaned

    replacements: dict[str, str] = {}
    for w in unknown:
        corr = sc.correction(w)
        if not corr or not isinstance(corr, str):
            continue

        corr = corr.strip()
        if not corr or corr == w:
            continue

        if len(w) <= 4:
            limit = 2
        elif len(w) <= 7:
            limit = 1
        else:
            limit = 2

        if _edit_distance_limited(w, corr, limit) > limit:
            continue

        replacements[w] = corr

    if not replacements:
        return cleaned

    def _sub(m: re.Match[str]) -> str:
        tok = m.group(0)
        return replacements.get(tok, tok)

    return _clean_whitespace(_WORD_RE.sub(_sub, cleaned))





_OPENAI_PROMPT = """You are a transcription cleaner.

Task:
- You will receive a JSON object with a list of transcript segments.
- For each segment, you may ONLY correct spelling/typos and remove obvious filler words/repetitions.
- DO NOT change meaning.
- DO NOT merge or split segments.
- Keep the same number of segments and the same start/end timestamps.

Output:
- Return ONLY valid JSON matching the schema.

Schema:
{"segments":[{"start":0.0,"end":1.0,"text":"..."}...]}
"""


def _openai_cleanup(
    *,
    segments: list[TranscriptSegment],
    language: str,
    api_key: str,
    model: str,
    base_url: str,
    logger: structlog.BoundLogger,
    timeout_seconds: float = 30.0,
) -> list[TranscriptSegment]:
    req_segments = [
        {
            "start": s.start_seconds,
            "end": s.end_seconds,
            "text": s.text,
        }
        for s in segments
    ]

    user = json.dumps({"language": language, "segments": req_segments}, ensure_ascii=False)

    url = base_url.rstrip("/") + "/chat/completions"
    started = time.time()

    res = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _OPENAI_PROMPT},
                {"role": "user", "content": user},
            ],
        },
        timeout=timeout_seconds,
    )
    res.raise_for_status()

    data = res.json()
    content = (
        (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
        if isinstance(data, dict)
        else None
    )

    if not content or not isinstance(content, str):
        raise RuntimeError("openai: missing content")

    payload = json.loads(content)
    segs = payload.get("segments")
    if not isinstance(segs, list) or len(segs) != len(segments):
        raise RuntimeError("openai: invalid segments")

    out: list[TranscriptSegment] = []
    for orig, cleaned in zip(segments, segs, strict=True):
        if not isinstance(cleaned, dict):
            raise RuntimeError("openai: invalid segment")

        text = cleaned.get("text")
        if not isinstance(text, str):
            text = orig.text

        out.append(
            TranscriptSegment(
                start_seconds=orig.start_seconds,
                end_seconds=orig.end_seconds,
                text=_clean_whitespace(text),
                confidence=orig.confidence,
            )
        )

    logger.info(
        "transcript.cleanup.openai_done",
        duration_ms=int((time.time() - started) * 1000),
        model=model,
        segment_count=len(out),
    )

    return out


def cleanup_transcript_segments(
    *,
    segments: list[TranscriptSegment],
    language: str | None,
    provider: str,
    openai_api_key: str = "",
    openai_model: str = "gpt-4.1-mini",
    openai_base_url: str = "https://api.openai.com/v1",
    logger: structlog.BoundLogger,
) -> list[TranscriptSegment]:
    provider_norm = (provider or "heuristic").strip().lower()
    lang = (language or "en").strip().lower()

    if provider_norm in {"none", "off", "disabled"}:
        return segments

    if provider_norm == "openai" and openai_api_key:
        try:
            return _openai_cleanup(
                segments=segments,
                language=lang,
                api_key=openai_api_key,
                model=openai_model,
                base_url=openai_base_url,
                logger=logger,
            )
        except Exception:
            logger.exception("transcript.cleanup.openai_failed_fallback_heuristic")

    cleanup_fn = heuristic_cleanup_text
    if provider_norm == "spellcheck":
        cleanup_fn = spellcheck_cleanup_text

    out: list[TranscriptSegment] = []
    for s in segments:
        out.append(
            TranscriptSegment(
                start_seconds=s.start_seconds,
                end_seconds=s.end_seconds,
                text=cleanup_fn(s.text, language=lang),
                confidence=s.confidence,
            )
        )

    return out
