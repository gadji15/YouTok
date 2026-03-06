from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class WordTiming:
    word: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None


@dataclass(frozen=True)
class ClipCandidate:
    clip_id: str
    start_seconds: float
    end_seconds: float
    score: float
    reason: str
    title: str | None = None
    features: dict[str, float] | None = None
