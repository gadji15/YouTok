from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from .features import compute_audio_window_features, compute_motion_score
from .titles import generate_clip_title
from .types import ClipCandidate, TranscriptSegment


_HOOK_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\b(you|your)\b", re.I), 0.10, "direct_address"),
    (re.compile(r"\b(how to|how do|why|what if)\b", re.I), 0.25, "question_hook"),
    (re.compile(r"\b(secret|mistake|never|stop|nobody)\b", re.I), 0.25, "pattern_interrupt"),
    (re.compile(r"\b(shocking|insane|crazy|unbelievable)\b", re.I), 0.20, "strong_adjective"),
    (re.compile(r"\b(quick|simple|easy)\b", re.I), 0.10, "simplicity"),
]


def score_text(text: str) -> tuple[float, list[str]]:
    t = text.strip()
    if not t:
        return 0.0, []

    score = 0.0
    reasons: list[str] = []

    exclaim = t.count("!")
    question = t.count("?")
    if exclaim:
        score += 0.05 * min(exclaim, 3)
        reasons.append("exclaim")
    if question:
        score += 0.08 * min(question, 3)
        reasons.append("question")

    word_count = len(t.split())
    score += min(word_count / 40.0, 0.25)

    for pattern, weight, reason in _HOOK_PATTERNS:
        if pattern.search(t):
            score += weight
            reasons.append(reason)

    return score, reasons


def segment_candidates(
    *,
    segments: list[TranscriptSegment],
    min_seconds: float,
    max_seconds: float,
    max_clips: int,
    audio_path: Path | None = None,
    video_path: Path | None = None,
    language: str | None = None,
) -> list[ClipCandidate]:
    if not segments:
        return []

    min_seconds = max(1.0, float(min_seconds))
    max_seconds = max(min_seconds, float(max_seconds))

    per_seg_score: list[float] = []
    for s in segments:
        score, _ = score_text(s.text)
        per_seg_score.append(score)

    candidates: list[ClipCandidate] = []

    for i, start_seg in enumerate(segments):
        start_t = start_seg.start_seconds
        best_for_start: ClipCandidate | None = None

        agg_score = 0.0
        reasons: dict[str, int] = {}

        for j in range(i, len(segments)):
            end_t = segments[j].end_seconds
            duration = end_t - start_t
            agg_score += per_seg_score[j]

            _, seg_reasons = score_text(segments[j].text)
            for r in seg_reasons:
                reasons[r] = reasons.get(r, 0) + 1

            if duration < min_seconds:
                continue
            if duration > max_seconds:
                break

            density = agg_score / max(duration, 0.001)
            target = (min_seconds + max_seconds) / 2.0
            length_penalty = 1.0 - 0.15 * abs(duration - target) / max(target, 0.001)
            length_penalty = max(0.6, min(1.0, length_penalty))

            score = density * length_penalty
            score = max(0.0, min(1.0, score))

            top_reasons = sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)[:3]
            reason_str = ",".join([r for r, _ in top_reasons]) or "baseline"

            cand = ClipCandidate(
                clip_id="",
                start_seconds=float(start_t),
                end_seconds=float(end_t),
                score=float(score),
                reason=reason_str,
            )

            if best_for_start is None or cand.score > best_for_start.score:
                best_for_start = cand

        if best_for_start is not None:
            candidates.append(best_for_start)

    candidates.sort(key=lambda c: c.score, reverse=True)

    deduped: list[ClipCandidate] = []
    for cand in candidates:
        overlaps = False
        for other in deduped:
            overlap = min(cand.end_seconds, other.end_seconds) - max(
                cand.start_seconds, other.start_seconds
            )
            if overlap > 0:
                overlap_ratio = overlap / max(
                    0.001,
                    min(
                        cand.end_seconds - cand.start_seconds,
                        other.end_seconds - other.start_seconds,
                    ),
                )
                if overlap_ratio > 0.6:
                    overlaps = True
                    break
        if overlaps:
            continue
        deduped.append(cand)
        if len(deduped) >= max_clips:
            break

    # Optional enrichment with cheap audio/visual features.
    enriched: list[ClipCandidate] = []
    for c in deduped:
        score = float(c.score)
        reasons = [r for r in (c.reason or "").split(",") if r]

        silence_penalty = 1.0
        if audio_path is not None and audio_path.exists():
            a = compute_audio_window_features(
                wav_path=audio_path,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
            )
            if a is not None:
                energy = min(1.0, a.rms * 4.0)
                silence_penalty = 1.0 - 0.5 * min(1.0, a.silence_ratio)
                score = 0.75 * score + 0.25 * energy
                if energy > 0.25:
                    reasons.append("high_energy")
                if a.silence_ratio < 0.25:
                    reasons.append("low_silence")

        if video_path is not None and video_path.exists():
            m = compute_motion_score(
                video_path=video_path,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
            )
            if m is not None:
                score = 0.85 * score + 0.15 * float(m)
                if m > 0.25:
                    reasons.append("high_motion")

        score = max(0.0, min(1.0, score * silence_penalty))

        if not reasons:
            reasons = ["baseline"]
        reason_str = ",".join(list(dict.fromkeys(reasons))[:5])

        enriched.append(
            ClipCandidate(
                clip_id=c.clip_id,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
                score=score,
                reason=reason_str,
            )
        )

    # Re-rank after enrichment.
    enriched.sort(key=lambda c: c.score, reverse=True)

    final: list[ClipCandidate] = []
    for idx, c in enumerate(enriched[:max_clips], start=1):
        base = ClipCandidate(
            clip_id=f"clip_{idx:03d}",
            start_seconds=round(c.start_seconds, 2),
            end_seconds=round(c.end_seconds, 2),
            score=round(c.score, 4),
            reason=c.reason,
        )

        title = generate_clip_title(clip=base, segments=segments, language=language)

        final.append(
            ClipCandidate(
                clip_id=base.clip_id,
                start_seconds=base.start_seconds,
                end_seconds=base.end_seconds,
                score=base.score,
                reason=base.reason,
                title=title,
            )
        )

    return final


def write_clips_json(*, clips: list[ClipCandidate], output_path: Path) -> None:
    payload = {"clips": [asdict(c) for c in clips]}

    import json

    from ..utils.files import atomic_write_text

    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
