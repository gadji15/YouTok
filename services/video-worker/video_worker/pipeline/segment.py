from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from .features import (
    compute_audio_window_features,
    compute_face_presence_score,
    compute_motion_score,
    find_first_non_silent_time,
    find_last_non_silent_time,
)
from .nms import non_max_suppression
from .titles import generate_clip_title
from .types import ClipCandidate, TranscriptSegment, WordTiming


_HOOK_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\b(you|your)\b", re.I), 0.10, "direct_address"),
    (re.compile(r"\b(how to|how do|why|what if|wait|watch)\b", re.I), 0.25, "question_hook"),
    (re.compile(r"\b(secret|mistake|never|stop|nobody|everyone)\b", re.I), 0.25, "pattern_interrupt"),
    (re.compile(r"\b(shocking|insane|crazy|unbelievable|wild)\b", re.I), 0.20, "strong_adjective"),
    (re.compile(r"\b(quick|simple|easy)\b", re.I), 0.10, "simplicity"),
    (re.compile(r"\b(top \d+|\d+ (tips|ways|steps))\b", re.I), 0.10, "listicle"),
]


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _collect_text(*, segments: list[TranscriptSegment], start: float, end: float) -> str:
    parts: list[str] = []
    for s in segments:
        if s.end_seconds <= start:
            continue
        if s.start_seconds >= end:
            break
        if s.text.strip():
            parts.append(s.text.strip())
    return " ".join(parts).strip()


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


def _speech_rate_score(*, words: list[WordTiming], start: float, end: float) -> tuple[float, float]:
    duration = max(0.01, end - start)
    count = 0
    for w in words:
        if w.end_seconds <= start:
            continue
        if w.start_seconds >= end:
            break
        count += 1

    wps = count / duration

    # Typical speech: ~2–4 wps. Normalize into [0..1].
    score = _clamp01((wps - 1.6) / 2.4)
    return score, float(wps)


def _polish_boundaries(
    *,
    start_seconds: float,
    end_seconds: float,
    min_seconds: float,
    audio_path: Path | None,
    words: list[WordTiming] | None,
) -> tuple[float, float]:
    original_start = float(start_seconds)
    original_end = float(end_seconds)

    start = float(start_seconds)
    end = float(end_seconds)

    if audio_path is not None and audio_path.exists():
        # Trim leading/trailing silence but keep a tiny pre/post roll.
        lead_search_end = min(end, start + 1.5)
        t0 = find_first_non_silent_time(
            wav_path=audio_path,
            start_seconds=start,
            end_seconds=lead_search_end,
        )
        if t0 is not None and (t0 - start) > 0.20:
            start = max(start, float(t0) - 0.15)

        tail_search_start = max(start, end - 1.5)
        t1 = find_last_non_silent_time(
            wav_path=audio_path,
            start_seconds=tail_search_start,
            end_seconds=end,
        )
        if t1 is not None and (end - t1) > 0.20:
            end = min(end, float(t1) + 0.10)

    if words:
        # Snap obvious "dead air" at the boundaries using word timings.
        window: list[WordTiming] = []
        for w in words:
            if w.end_seconds <= start:
                continue
            if w.start_seconds >= end:
                break
            window.append(w)

        if window:
            first = window[0]
            last = window[-1]

            if (first.start_seconds - start) > 0.25:
                start = max(start, float(first.start_seconds) - 0.15)

            if (end - last.end_seconds) > 0.25:
                end = min(end, float(last.end_seconds) + 0.10)

    if (end - start) < min_seconds:
        return original_start, original_end

    return float(max(0.0, start)), float(max(start + 0.01, end))


def segment_candidates(
    *,
    segments: list[TranscriptSegment],
    min_seconds: float,
    max_seconds: float,
    max_clips: int,
    audio_path: Path | None = None,
    video_path: Path | None = None,
    words: list[WordTiming] | None = None,
    language: str | None = None,
    candidates_per_start: int = 2,
    nms_iou_threshold: float = 0.35,
) -> list[ClipCandidate]:
    if not segments:
        return []

    min_seconds = max(1.0, float(min_seconds))
    max_seconds = max(min_seconds, float(max_seconds))
    max_clips = max(1, int(max_clips))

    per_seg_score: list[float] = []
    per_seg_reasons: list[list[str]] = []
    for s in segments:
        score, rs = score_text(s.text)
        per_seg_score.append(score)
        per_seg_reasons.append(rs)

    candidates: list[ClipCandidate] = []

    per_start_keep = max(1, int(candidates_per_start))

    for i, start_seg in enumerate(segments):
        start_t = float(start_seg.start_seconds)

        agg_score = 0.0
        reasons: dict[str, int] = {}
        scored_for_start: list[ClipCandidate] = []

        for j in range(i, len(segments)):
            end_t = float(segments[j].end_seconds)
            duration = end_t - start_t
            agg_score += per_seg_score[j]

            for r in per_seg_reasons[j]:
                reasons[r] = reasons.get(r, 0) + 1

            if duration < min_seconds:
                continue
            if duration > max_seconds:
                break

            density = agg_score / max(duration, 0.001)
            target = (min_seconds + max_seconds) / 2.0
            length_penalty = 1.0 - 0.15 * abs(duration - target) / max(target, 0.001)
            length_penalty = max(0.6, min(1.0, length_penalty))

            score = _clamp01(density * length_penalty)

            top_reasons = sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)[:3]
            reason_str = ",".join([r for r, _ in top_reasons]) or "baseline"

            scored_for_start.append(
                ClipCandidate(
                    clip_id="",
                    start_seconds=start_t,
                    end_seconds=end_t,
                    score=float(score),
                    reason=reason_str,
                )
            )

        if scored_for_start:
            scored_for_start.sort(key=lambda c: c.score, reverse=True)
            candidates.extend(scored_for_start[:per_start_keep])

    if not candidates:
        return []

    candidates.sort(key=lambda c: c.score, reverse=True)

    # Work on a limited set to keep video/audio feature extraction bounded.
    preselect = max(max_clips * 20, 50)
    candidates = candidates[:preselect]

    enriched: list[ClipCandidate] = []

    for c in candidates:
        start, end = _polish_boundaries(
            start_seconds=c.start_seconds,
            end_seconds=c.end_seconds,
            min_seconds=min_seconds,
            audio_path=audio_path,
            words=words,
        )

        duration = max(0.01, end - start)

        score = float(c.score)
        reasons = [r for r in (c.reason or "").split(",") if r]

        # Fresh text score over the exact window.
        window_text = _collect_text(segments=segments, start=start, end=end)
        text_score, text_reasons = score_text(window_text)
        score = 0.70 * score + 0.30 * _clamp01(text_score)
        reasons.extend(text_reasons)

        # Strong hook in the opening is worth more.
        open_text = _collect_text(segments=segments, start=start, end=min(end, start + 8.0))
        open_score, _ = score_text(open_text)
        if open_score >= 0.35:
            score = _clamp01(score + 0.06)
            reasons.append("hook_open")

        silence_ratio = None
        if audio_path is not None and audio_path.exists():
            a = compute_audio_window_features(
                wav_path=audio_path,
                start_seconds=start,
                end_seconds=end,
            )
            if a is not None:
                energy = _clamp01(a.rms * 4.0)
                silence_ratio = float(a.silence_ratio)

                score = 0.80 * score + 0.20 * energy

                if energy > 0.30:
                    reasons.append("high_energy")
                if a.silence_ratio < 0.25:
                    reasons.append("low_silence")

        if words:
            sr_score, wps = _speech_rate_score(words=words, start=start, end=end)
            score = 0.90 * score + 0.10 * sr_score

            if wps >= 3.2:
                reasons.append("fast_speech")

        if silence_ratio is not None:
            # Penalize dead air.
            score = _clamp01(score * (1.0 - 0.35 * _clamp01(silence_ratio)))

        reason_str = ",".join(list(dict.fromkeys([r for r in reasons if r]))[:6]) or "baseline"

        enriched.append(
            ClipCandidate(
                clip_id="",
                start_seconds=float(start),
                end_seconds=float(end),
                score=_clamp01(score),
                reason=reason_str,
            )
        )

    enriched.sort(key=lambda c: c.score, reverse=True)

    # Vision features are comparatively expensive; only apply to the top few.
    if video_path is not None and video_path.exists() and enriched:
        vision_keep = min(len(enriched), max(max_clips * 6, 25))
        updated: list[ClipCandidate] = []

        for c in enriched[:vision_keep]:
            score = float(c.score)
            reasons = [r for r in (c.reason or "").split(",") if r]

            m = compute_motion_score(
                video_path=video_path,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
            )
            if m is not None:
                score = 0.88 * score + 0.12 * float(m)
                if m > 0.25:
                    reasons.append("high_motion")

            f = compute_face_presence_score(
                video_path=video_path,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
            )
            if f is not None:
                score = 0.92 * score + 0.08 * float(f)
                if f > 0.20:
                    reasons.append("face")

            reason_str = ",".join(list(dict.fromkeys([r for r in reasons if r]))[:6]) or "baseline"

            updated.append(
                ClipCandidate(
                    clip_id="",
                    start_seconds=c.start_seconds,
                    end_seconds=c.end_seconds,
                    score=_clamp01(score),
                    reason=reason_str,
                )
            )

        enriched = updated + enriched[vision_keep:]
        enriched.sort(key=lambda c: c.score, reverse=True)

    selected = non_max_suppression(
        candidates=enriched,
        iou_threshold=nms_iou_threshold,
        max_keep=max_clips,
    )

    final: list[ClipCandidate] = []
    for idx, c in enumerate(selected, start=1):
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
