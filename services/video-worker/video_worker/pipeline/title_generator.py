from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import httpx
import structlog

from .types import ClipCandidate, TranscriptSegment


_STOPWORDS_EN = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "why",
    "with",
    "you",
    "your",
}

_STOPWORDS_FR = {
    "alors",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "et",
    "eux",
    "il",
    "je",
    "la",
    "le",
    "les",
    "leur",
    "lui",
    "ma",
    "mais",
    "me",
    "meme",
    "mes",
    "moi",
    "mon",
    "ne",
    "nos",
    "notre",
    "nous",
    "on",
    "ou",
    "par",
    "pas",
    "pour",
    "qu",
    "que",
    "qui",
    "sa",
    "se",
    "ses",
    "son",
    "sur",
    "ta",
    "te",
    "tes",
    "toi",
    "ton",
    "tu",
    "un",
    "une",
    "vos",
    "votre",
    "vous",
}

_POWER_WORDS_EN = {
    "secret",
    "mistake",
    "never",
    "stop",
    "nobody",
    "simple",
    "easy",
    "fast",
    "hack",
    "truth",
    "warning",
    "insane",
    "shocking",
    "crazy",
}

_POWER_WORDS_FR = {
    "secret",
    "erreur",
    "jamais",
    "arrête",
    "stop",
    "personne",
    "simple",
    "facile",
    "rapide",
    "hack",
    "vérité",
    "attention",
    "incroyable",
}

_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


@dataclass(frozen=True)
class TitleCandidateScored:
    title: str
    score: float
    features: dict[str, float]


@dataclass(frozen=True)
class TitleCandidatesResult:
    provider: str
    description: str | None
    hashtags: list[str]
    candidates: list[TitleCandidateScored]

    @property
    def top3(self) -> list[str]:
        return [c.title for c in self.candidates[:3]]

    def to_payload(self) -> dict:
        return {
            "provider": self.provider,
            "description": self.description,
            "hashtags": self.hashtags,
            "candidates": [
                {
                    "title": c.title,
                    "score": round(float(c.score), 6),
                    "features": {k: round(float(v), 6) for k, v in c.features.items()},
                }
                for c in self.candidates
            ],
            "top3": self.top3,
        }


def _clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "").strip())
    t = t.strip("-–—:;,. ")
    t = re.sub(r"\s+([!?])", r"\1", t)
    return t


def _truncate_to_chars(s: str, max_chars: int) -> str:
    s = _clean_title(s)
    if len(s) <= max_chars:
        return s

    out = s[:max_chars].rstrip()
    out = out.rstrip("-–—:;,. ")
    return out


def _normalize_key(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿñæœ' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_window_text(*, clip: ClipCandidate, segments: list[TranscriptSegment]) -> str:
    parts: list[str] = []
    for s in segments:
        if s.end_seconds <= clip.start_seconds:
            continue
        if s.start_seconds >= clip.end_seconds:
            break
        txt = s.text.strip()
        if txt:
            parts.append(txt)
    return " ".join(parts).strip()


def _keywords(*, text: str, language: str) -> list[str]:
    lang = (language or "en").lower().strip()
    stop = _STOPWORDS_FR if lang == "fr" else _STOPWORDS_EN

    counts: dict[str, int] = {}
    for m in _WORD_RE.finditer(text.lower()):
        w = m.group(0)
        if len(w) <= 2:
            continue
        if w in stop:
            continue
        counts[w] = counts.get(w, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:8]]


def _length_score(title: str) -> float:
    n = len(title)
    if n == 0:
        return 0.0
    target = 48
    return max(0.0, 1.0 - (abs(n - target) / target))


def _power_words_score(title: str, *, language: str) -> float:
    lang = (language or "en").lower().strip()
    p = _POWER_WORDS_FR if lang == "fr" else _POWER_WORDS_EN

    tokens = {t.lower() for t in _WORD_RE.findall(title)}
    hits = len(tokens & p)
    return min(1.0, hits / 2.0)


def _keyword_match_score(title: str, *, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    toks = {t.lower() for t in _WORD_RE.findall(title)}
    hits = 0
    for k in keywords:
        if k.lower() in toks:
            hits += 1
    return min(1.0, hits / max(3.0, float(len(keywords))))


def _curiosity_bonus(title: str, *, language: str) -> float:
    t = title.lower()
    bonus = 0.0
    if "?" in title:
        bonus += 0.25

    if re.search(r"\b\d+\b", title):
        bonus += 0.15

    if language == "fr":
        if re.search(r"\b(pourquoi|et si|personne ne|tu fais)\b", t):
            bonus += 0.15
    else:
        if re.search(r"\b(why|what if|nobody|you\s+are)\b", t):
            bonus += 0.15

    return min(0.5, bonus)


def _rule_penalties(title: str, *, language: str) -> float:
    # 0..1 penalty, higher is worse.
    if len(title) == 0:
        return 1.0
    if len(title) > 60:
        return 1.0

    lang = (language or "en").lower().strip()
    stop = _STOPWORDS_FR if lang == "fr" else _STOPWORDS_EN
    toks = [t.lower() for t in _WORD_RE.findall(title)]
    if not toks:
        return 1.0

    content = [t for t in toks if t not in stop]
    # Penalize titles that are almost only stopwords.
    if len(content) <= 1:
        return 0.8

    return 0.0


def score_and_rank_titles(
    *,
    titles: list[str],
    transcript_text: str,
    language: str | None,
) -> list[TitleCandidateScored]:
    lang = (language or "en").lower().strip()

    kws = _keywords(text=transcript_text, language=lang)

    seen: set[str] = set()
    scored: list[TitleCandidateScored] = []

    for raw in titles:
        t = _clean_title(raw)
        if not t:
            continue
        if len(t) > 80:
            # hard-trim to allow later filtering; better than dropping.
            t = t[:80].rstrip()

        key = _normalize_key(t)
        if key in seen:
            continue
        seen.add(key)

        penalty = _rule_penalties(t, language=lang)
        if penalty >= 1.0:
            continue

        length_s = _length_score(t)
        power_s = _power_words_score(t, language=lang)
        kw_s = _keyword_match_score(t, keywords=kws)
        cur_s = _curiosity_bonus(t, language=lang)

        score = 0.45 * length_s + 0.25 * power_s + 0.20 * kw_s + 0.10 * cur_s
        score = max(0.0, min(1.0, score * (1.0 - penalty)))

        scored.append(
            TitleCandidateScored(
                title=t,
                score=float(score),
                features={
                    "length": float(length_s),
                    "power": float(power_s),
                    "keyword": float(kw_s),
                    "curiosity": float(cur_s),
                    "penalty": float(penalty),
                },
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored


def _heuristic_titles(*, transcript_text: str, language: str, seed: str) -> tuple[list[str], str | None, list[str]]:
    lang = (language or "en").lower().strip()
    kws = _keywords(text=transcript_text, language=lang)

    primary_kw = kws[0] if kws else ""

    if not seed:
        seed = primary_kw

    seed_short = " ".join(seed.split()[:10]).strip()

    if lang == "fr":
        titles = [
            f"L'erreur que tout le monde fait : {seed_short}",
            f"Et si tu faisais {seed_short.lower()} ?",
            f"Arrête de faire ça : {seed_short}",
            f"Personne ne te dit ça sur {primary_kw}" if primary_kw else f"Personne ne te dit ça : {seed_short}",
            f"Le déclic en 30 secondes : {seed_short}",
            f"Tu fais ça mal depuis le début : {seed_short}",
            f"La méthode simple : {seed_short}",
            f"Le secret pour {seed_short.lower()}",
        ]
        desc = ("Le passage le plus important, résumé en 1 minute." if transcript_text else None)
        hashtags = ["#tiktok", "#conseils", "#pourtoi"]
    else:
        titles = [
            f"Stop doing this: {seed_short}",
            f"What if you could {seed_short.lower()}?",
            f"The mistake nobody talks about: {seed_short}",
            f"Do this before it's too late: {seed_short}",
            f"The simple way: {seed_short}",
            f"You're doing it wrong: {seed_short}",
            f"The key insight: {seed_short}",
            f"The secret to {seed_short.lower()}",
        ]
        desc = ("The most important moment from the video, in under a minute." if transcript_text else None)
        hashtags = ["#fyp", "#learnontiktok", "#viral"]

    titles = [_truncate_to_chars(t, 60) for t in titles]

    # Add one keyword hashtag when available.
    if primary_kw:
        safe = re.sub(r"[^a-z0-9_]+", "", primary_kw.lower())
        if safe:
            hashtags = hashtags[:2] + [f"#{safe}"]

    return titles, desc, hashtags


def _select_seed(*, clip: ClipCandidate, segments: list[TranscriptSegment]) -> str:
    # Prefer a sentence that already looks like a hook.
    window = _extract_window_text(clip=clip, segments=segments)
    if not window:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", window)
    for s in sentences[:6]:
        if "?" in s:
            return s
        if re.search(r"\b(secret|mistake|never|stop|nobody)\b", s, re.I):
            return s

    return sentences[0] if sentences else window


OPENAI_TITLE_PROMPT_TEMPLATE = """You are a viral short-form copywriter.

Goal: Generate TikTok-ready *titles* for a short clip.

Rules:
- Output ONLY valid JSON (no markdown, no code block fences, no commentary)
- Generate exactly 8 distinct title candidates
- Each title must be <= 60 characters
- Prefer hooks: question, imperative, curiosity gap, pattern interrupt
- Avoid repeating the same phrasing (no near-duplicates)
- Keep language consistent with the requested language
- Generate 1 short description (<= 100 characters)
- Generate exactly 3 hashtags

Output schema:
{"titles":["..." x8],"description":"...","hashtags":["#...","#...","#..."]}
"""


def _openai_generate(
    *,
    clip: ClipCandidate,
    segments: list[TranscriptSegment],
    language: str,
    api_key: str,
    model: str,
    base_url: str,
    logger: structlog.BoundLogger,
    timeout_seconds: float = 25.0,
) -> tuple[list[str], str | None, list[str]]:
    transcript_text = _extract_window_text(clip=clip, segments=segments)

    prompt = OPENAI_TITLE_PROMPT_TEMPLATE

    user = (
        f"Language: {language}\n"
        f"Clip duration: {round(clip.end_seconds - clip.start_seconds, 2)}s\n"
        f"Viral score (0..1): {clip.score}\n"
        f"Reasons: {clip.reason}\n"
        f"Transcript (verbatim):\n{transcript_text}"
    )

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
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": prompt},
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

    try:
        payload = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"openai: failed to parse JSON: {e}")

    titles = payload.get("titles")
    description = payload.get("description")
    hashtags = payload.get("hashtags")

    if not isinstance(titles, list) or len(titles) != 8:
        raise RuntimeError("openai: expected titles[8]")

    titles_out = [str(t) for t in titles]

    desc_out = str(description) if isinstance(description, str) else None

    hash_out: list[str] = []
    if isinstance(hashtags, list):
        for h in hashtags:
            s = str(h).strip()
            if not s:
                continue
            if not s.startswith("#"):
                s = "#" + s
            hash_out.append(s)

    hash_out = hash_out[:3]

    logger.info(
        "titles.openai_generated",
        duration_ms=int((time.time() - started) * 1000),
        model=model,
        clip_id=clip.clip_id,
    )

    return titles_out, desc_out, hash_out


def generate_title_candidates_for_clip(
    *,
    clip: ClipCandidate,
    segments: list[TranscriptSegment],
    language: str | None,
    provider: str,
    openai_api_key: str = "",
    openai_model: str = "gpt-4.1-mini",
    openai_base_url: str = "https://api.openai.com/v1",
    logger: structlog.BoundLogger,
) -> TitleCandidatesResult:
    lang = (language or "en").lower().strip()

    transcript_text = _extract_window_text(clip=clip, segments=segments)
    seed = _select_seed(clip=clip, segments=segments)

    titles_raw: list[str]
    description: str | None
    hashtags: list[str]

    provider_norm = (provider or "heuristic").lower().strip()

    if provider_norm == "openai" and openai_api_key:
        try:
            titles_raw, description, hashtags = _openai_generate(
                clip=clip,
                segments=segments,
                language=lang,
                api_key=openai_api_key,
                model=openai_model,
                base_url=openai_base_url,
                logger=logger,
            )
        except Exception:
            logger.exception("titles.openai_failed_fallback_heuristic", clip_id=clip.clip_id)
            titles_raw, description, hashtags = _heuristic_titles(
                transcript_text=transcript_text, language=lang, seed=seed
            )
            provider_norm = "heuristic"
    else:
        titles_raw, description, hashtags = _heuristic_titles(
            transcript_text=transcript_text, language=lang, seed=seed
        )
        provider_norm = "heuristic"

    scored = score_and_rank_titles(titles=titles_raw, transcript_text=transcript_text, language=lang)

    # Ensure we keep a predictable number: up to 8 after filtering.
    scored = scored[:8]

    return TitleCandidatesResult(
        provider=provider_norm,
        description=description,
        hashtags=hashtags,
        candidates=scored,
    )
