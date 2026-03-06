from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field

import httpx
import structlog

from .segment import emotion_word_score, score_text
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
    hooks: list[str] = field(default_factory=list)
    analysis: dict | None = None

    @property
    def top3(self) -> list[str]:
        return [c.title for c in self.candidates[:3]]

    def to_payload(self) -> dict:
        return {
            "provider": self.provider,
            "description": self.description,
            "hashtags": self.hashtags,
            "hooks": self.hooks,
            "analysis": self.analysis,
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


_ISLAM_KEYWORDS = {
    "allah",
    "islam",
    "musulman",
    "muslim",
    "quran",
    "coran",
    "hadith",
    "sunnah",
    "sounnah",
    "ramadan",
    "salat",
    "priere",
    "prière",
    "dhikr",
    "dua",
    "duaa",
    "hijab",
    "imam",
    "prophète",
    "prophete",
    "muhammad",
    "mohamed",
}

_STORY_KEYWORDS_FR = {"histoire", "anecdote", "raconte", "raconter", "storytime"}
_STORY_KEYWORDS_EN = {"story", "anecdote", "storytime"}

_PODCAST_KEYWORDS_FR = {"podcast", "interview", "épisode", "episode"}
_PODCAST_KEYWORDS_EN = {"podcast", "interview", "episode"}


def _split_sentences(text: str) -> list[str]:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    parts = re.split(r"(?<=[.!?])\s+", t)
    return [p.strip() for p in parts if p and p.strip()]


def _detect_signals(text: str, *, language: str) -> list[str]:
    t = (text or "").lower()
    out: list[str] = []

    if re.search(r"\b(secret|cache|hidden|mystere|mystère|personne ne|nobody)\b", t):
        out.append("mystery")
    if re.search(r"\b(incroyable|choquant|dingue|shocking|insane|unbelievable)\b", t):
        out.append("surprise")
    if re.search(r"\b(sagesse|leçon|lesson|wisdom)\b", t):
        out.append("wisdom")
    if re.search(r"\b(verite|vérité|truth|revelation|révélation|voici)\b", t):
        out.append("revelation")

    if language == "fr" and re.search(r"\b(allah|islam|coran|quran|hadith|rappel)\b", t):
        out.append("islam")
    if language != "fr" and re.search(r"\b(allah|islam|quran|hadith|reminder)\b", t):
        out.append("islam")

    # unique, stable order
    seen: set[str] = set()
    deduped: list[str] = []
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        deduped.append(s)

    return deduped


def _power_phrase_score(phrase: str, *, language: str) -> float:
    if not phrase:
        return 0.0

    hook_s, _ = score_text(phrase, language=language)
    emo_s, _ = emotion_word_score(phrase, language=language)

    t = phrase.lower()
    bonus = 0.0

    # Surprise / revelation / mystery patterns.
    if language == "fr":
        if re.search(r"\b(personne ne|voici|ce que personne|ce qui s'est passe|ce qui s’est passe)\b", t):
            bonus += 0.20
        if re.search(r"\b(sagesse|leçon|lecon)\b", t):
            bonus += 0.10
    else:
        if re.search(r"\b(nobody|here's what|what happened next|this will change)\b", t):
            bonus += 0.20
        if re.search(r"\b(wisdom|lesson)\b", t):
            bonus += 0.10

    if "!" in phrase:
        bonus += 0.05

    return float(min(1.0, 0.55 * hook_s + 0.35 * emo_s + 0.10 * bonus))


def _extract_power_phrases(*, text: str, language: str, limit: int = 8) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    scored = [(s, _power_phrase_score(s, language=language)) for s in sentences]
    scored.sort(key=lambda kv: kv[1], reverse=True)

    out: list[str] = []
    seen: set[str] = set()
    for s, _ in scored:
        clean = _clean_title(s)
        if not clean:
            continue
        key = _normalize_key(clean)
        if key in seen:
            continue
        seen.add(key)
        out.append(_truncate_to_chars(clean, 120))
        if len(out) >= limit:
            break

    return out


def _detect_theme(*, full_text: str, keywords: list[str], language: str) -> str | None:
    t = (full_text or "").lower()
    kws = [k.lower() for k in (keywords or [])]

    if any(k in _ISLAM_KEYWORDS for k in kws) or any(k in t for k in _ISLAM_KEYWORDS):
        return "islam"

    if language == "fr":
        if any(k in t for k in _PODCAST_KEYWORDS_FR):
            return "podcast"
        if any(k in t for k in _STORY_KEYWORDS_FR):
            return "story"
    else:
        if any(k in t for k in _PODCAST_KEYWORDS_EN):
            return "podcast"
        if any(k in t for k in _STORY_KEYWORDS_EN):
            return "story"

    if kws:
        return kws[0]

    return None


def _analyze_transcript(*, segments: list[TranscriptSegment], language: str) -> dict:
    full_text = " ".join([s.text.strip() for s in segments if s.text and s.text.strip()])
    keywords = _keywords(text=full_text, language=language)
    theme = _detect_theme(full_text=full_text, keywords=keywords, language=language)

    power_phrases = _extract_power_phrases(text=full_text, language=language, limit=8)
    key_phrase = power_phrases[0] if power_phrases else None

    summary = None
    if key_phrase:
        summary = _truncate_to_chars(key_phrase, 90)

    signals = _detect_signals(full_text, language=language)

    return {
        "summary": summary,
        "theme": theme,
        "key_phrase": key_phrase,
        "power_phrases": power_phrases,
        "signals": signals,
    }


def _length_score(title: str) -> float:
    n = len(title)
    if n == 0:
        return 0.0

    # TikTok titles: sweet spot ~40–80 chars.
    if n < 20 or n > 90:
        return 0.0

    target = 60
    # 60 => 1.0, 40/80 => 0.5
    return max(0.0, 1.0 - (abs(n - target) / 40.0))


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


def _emotion_score(title: str, *, language: str) -> float:
    s, _ = emotion_word_score(title, language=language)
    return float(s)


def _clarity_score(title: str, *, language: str) -> float:
    lang = (language or "en").lower().strip()
    stop = _STOPWORDS_FR if lang == "fr" else _STOPWORDS_EN

    toks = [t.lower() for t in _WORD_RE.findall(title)]
    if not toks:
        return 0.0

    content = [t for t in toks if t not in stop]
    ratio = len(content) / max(1.0, float(len(toks)))

    word_penalty = 0.0
    if len(toks) > 14:
        word_penalty += 0.35
    if len(toks) < 4:
        word_penalty += 0.20

    return float(max(0.0, min(1.0, ratio * (1.0 - word_penalty))))


def _impact_score(title: str, *, language: str) -> float:
    base = _power_words_score(title, language=language)
    bonus = 0.0
    if "!" in title:
        bonus += 0.10
    if language == "fr":
        if re.search(r"\b(tu|toi|vous|votre|vos)\b", title, re.I):
            bonus += 0.05
    else:
        if re.search(r"\b(you|your)\b", title, re.I):
            bonus += 0.05

    return float(min(1.0, base + bonus))


def _rule_penalties(title: str, *, language: str) -> float:
    # 0..1 penalty, higher is worse.
    if len(title) == 0:
        return 1.0
    if len(title) > 80:
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
        emo_s = _emotion_score(t, language=lang)
        imp_s = _impact_score(t, language=lang)
        clar_s = _clarity_score(t, language=lang)
        kw_s = _keyword_match_score(t, keywords=kws)
        cur_s = _curiosity_bonus(t, language=lang)

        score = (
            0.10 * length_s
            + 0.15 * emo_s
            + 0.25 * cur_s
            + 0.20 * clar_s
            + 0.20 * imp_s
            + 0.10 * kw_s
        )
        score = max(0.0, min(1.0, score * (1.0 - penalty)))

        scored.append(
            TitleCandidateScored(
                title=t,
                score=float(score),
                features={
                    "length": float(length_s),
                    "emotion": float(emo_s),
                    "curiosity": float(cur_s),
                    "clarity": float(clar_s),
                    "impact": float(imp_s),
                    "relevance": float(kw_s),
                    "penalty": float(penalty),
                },
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored


def _sanitize_hashtag(token: str) -> str | None:
    t = (token or "").strip()
    if not t:
        return None
    if t.startswith("#"):
        t = t[1:]

    t = unicodedata.normalize("NFKD", t)
    t = "".join([c for c in t if not unicodedata.combining(c)])
    t = t.lower()
    t = re.sub(r"[^a-z0-9_]+", "", t)
    t = t.strip("_")

    if not t or len(t) < 2:
        return None

    return "#" + t[:50]


def _build_hashtags(*, keywords: list[str], theme: str | None, language: str) -> list[str]:
    lang = (language or "en").lower().strip()

    if lang == "fr":
        base_viral = ["#pourtoi", "#tiktok", "#viral"]
        broad = ["#fr", "#foryou"]
        niche: list[str] = []
        if theme == "islam":
            niche = ["#islam", "#rappel", "#sunnah", "#quran"]
        elif theme == "story":
            niche = ["#histoire", "#storytime", "#anecdote"]
        elif theme == "podcast":
            niche = ["#podcast", "#extrait", "#interview"]
        else:
            niche = ["#histoire", "#sagesse", "#conseils"]
    else:
        base_viral = ["#fyp", "#viral", "#tiktok"]
        broad = ["#foryou", "#learnontiktok"]
        niche = []
        if theme == "islam":
            niche = ["#islam", "#reminder", "#quran", "#hadith"]
        elif theme == "story":
            niche = ["#storytime", "#story", "#life"]
        elif theme == "podcast":
            niche = ["#podcast", "#clip", "#interview"]
        else:
            niche = ["#storytime", "#wisdom", "#tips"]

    out: list[str] = []

    def _add_many(items: list[str]) -> None:
        for it in items:
            s = _sanitize_hashtag(it)
            if not s:
                continue
            if s in out:
                continue
            out.append(s)

    _add_many(base_viral)
    _add_many(niche)

    # Add 1–2 keyword hashtags.
    for kw in keywords[:3]:
        s = _sanitize_hashtag(kw)
        if s and s not in out:
            out.append(s)
        if len(out) >= 7:
            break

    _add_many(broad)

    return out[:8]


def _build_description(*, summary: str | None, theme: str | None, language: str) -> str | None:
    if not summary:
        return None

    lang = (language or "en").lower().strip()

    line1 = _truncate_to_chars(summary, 90)
    if lang == "fr":
        if theme == "islam":
            line2 = "Regarde jusqu'à la fin."
        else:
            line2 = "Dis-moi en commentaire ce que tu en penses."
    else:
        if theme == "islam":
            line2 = "Watch till the end."
        else:
            line2 = "Comment what you think."

    return f"{line1}\n{line2}".strip()


def _heuristic_titles(
    *,
    transcript_text: str,
    language: str,
    seed: str,
    analysis: dict | None,
) -> tuple[list[str], str | None, list[str], list[str]]:
    lang = (language or "en").lower().strip()

    analysis = analysis or {}
    theme = analysis.get("theme") if isinstance(analysis.get("theme"), str) else None
    keywords = analysis.get("keywords") if isinstance(analysis.get("keywords"), list) else []
    keywords = [str(k) for k in keywords if str(k).strip()]

    seed = _clean_title(seed)
    if not seed:
        seed = str(analysis.get("key_phrase") or "")

    seed_short = _truncate_to_chars(" ".join(seed.split()[:16]).strip(), 80)
    primary_kw = keywords[0] if keywords else ""

    # Hooks (5–10). Start with the seed if it already feels hooky.
    hooks: list[str] = []

    hooky_seed_score, _ = score_text(seed_short, language=lang)
    if hooky_seed_score >= 0.35 or "?" in seed_short:
        hooks.append(seed_short)

    if lang == "fr":
        base = [
            f"99% des gens ignorent ça sur {primary_kw}" if primary_kw else "99% des gens ignorent ça…",
            f"Personne ne parle de ça : {seed_short}",
            f"Ce que personne ne te dit sur {primary_kw}" if primary_kw else f"Ce que personne ne te dit : {seed_short}",
            f"Cette histoire va changer ta vision : {seed_short}",
            f"Le secret que tu dois connaître : {seed_short}",
            f"Ce qui s'est passé ensuite est incroyable…",
            f"Une leçon de sagesse en 60s : {seed_short}",
            f"Arrête de faire ça : {seed_short}",
            f"Et si tu faisais {seed_short.lower()} ?",
        ]
        if theme == "islam":
            base = [
                f"Une leçon en Islam que tu dois entendre",
                f"Ce rappel va te toucher : {seed_short}",
                f"Ce que le Coran nous apprend ici…",
                *base,
            ]
    else:
        base = [
            f"99% of people ignore this about {primary_kw}" if primary_kw else "99% of people ignore this…",
            f"Nobody talks about this: {seed_short}",
            f"Here's what nobody tells you about {primary_kw}" if primary_kw else f"Here's what nobody tells you: {seed_short}",
            f"This story will change how you see it: {seed_short}",
            f"The secret you need to know: {seed_short}",
            "What happened next is unbelievable…",
            f"A powerful lesson in 60s: {seed_short}",
            f"Stop doing this: {seed_short}",
            f"What if you could {seed_short.lower()}?",
        ]
        if theme == "islam":
            base = [
                "An Islamic reminder you need today",
                f"This reminder will hit different: {seed_short}",
                "What the Quran teaches us here…",
                *base,
            ]

    for h in base:
        clean = _truncate_to_chars(h, 80)
        if not clean:
            continue
        if _normalize_key(clean) in {_normalize_key(x) for x in hooks}:
            continue
        hooks.append(clean)
        if len(hooks) >= 10:
            break

    summary = analysis.get("summary") if isinstance(analysis.get("summary"), str) else None
    desc = _build_description(summary=summary or seed_short, theme=theme, language=lang)
    hashtags = _build_hashtags(keywords=keywords, theme=theme, language=lang)

    return hooks[:10], desc, hashtags, hooks[:10]


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

Goal: Generate TikTok-ready *titles/hooks* for a short clip.

Rules:
- Output ONLY valid JSON (no markdown, no code block fences, no commentary)
- Generate exactly 10 distinct title candidates
- Each title must be 40–80 characters (hard max 80)
- Prefer hooks: curiosity gap, revelation, mystery, surprise, wisdom
- Avoid repeating the same phrasing (no near-duplicates)
- Keep language consistent with the requested language
- Generate 1 short description with 2 lines (<= 180 characters total)
- Generate 5 to 8 hashtags

Output schema:
{"titles":["..." x10],"description":"line1\nline2","hashtags":["#..." x5..8]}
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

    if not isinstance(titles, list) or len(titles) != 10:
        raise RuntimeError("openai: expected titles[10]")

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

    hash_out = hash_out[:8]

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

    analysis = _analyze_transcript(segments=segments, language=lang)

    clip_phrases = _extract_power_phrases(text=transcript_text, language=lang, limit=6)
    if clip_phrases:
        analysis = {
            **analysis,
            "clip_key_phrase": clip_phrases[0],
            "clip_phrases": clip_phrases,
        }

    titles_raw: list[str]
    description: str | None
    hashtags: list[str]
    hooks: list[str]

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
            hooks = [str(t) for t in titles_raw]

            # Ensure hashtag count is in the product range.
            if len(hashtags) < 5:
                fallback = _build_hashtags(
                    keywords=analysis.get("keywords") or [],
                    theme=analysis.get("theme") if isinstance(analysis.get("theme"), str) else None,
                    language=lang,
                )
                for h in fallback:
                    if h not in hashtags:
                        hashtags.append(h)
                hashtags = hashtags[:8]
        except Exception:
            logger.exception("titles.openai_failed_fallback_heuristic", clip_id=clip.clip_id)
            titles_raw, description, hashtags, hooks = _heuristic_titles(
                transcript_text=transcript_text,
                language=lang,
                seed=seed,
                analysis=analysis,
            )
            provider_norm = "heuristic"
    else:
        titles_raw, description, hashtags, hooks = _heuristic_titles(
            transcript_text=transcript_text,
            language=lang,
            seed=seed,
            analysis=analysis,
        )
        provider_norm = "heuristic"

    scored = score_and_rank_titles(titles=titles_raw, transcript_text=transcript_text, language=lang)

    # Ensure we keep a predictable number: up to 10 after filtering.
    scored = scored[:10]

    return TitleCandidatesResult(
        provider=provider_norm,
        description=description,
        hashtags=hashtags,
        candidates=scored,
        hooks=hooks,
        analysis=analysis,
    )
