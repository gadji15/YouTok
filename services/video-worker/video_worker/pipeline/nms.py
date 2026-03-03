from __future__ import annotations

from typing import Protocol, TypeVar


class HasTimeAndScore(Protocol):
    start_seconds: float
    end_seconds: float
    score: float


T = TypeVar("T", bound=HasTimeAndScore)


def time_iou(
    a_start: float,
    a_end: float,
    b_start: float,
    b_end: float,
) -> float:
    inter = min(a_end, b_end) - max(a_start, b_start)
    if inter <= 0:
        return 0.0

    union = (a_end - a_start) + (b_end - b_start) - inter
    if union <= 0:
        return 0.0

    return float(max(0.0, min(1.0, inter / union)))


def non_max_suppression(
    *,
    candidates: list[T],
    iou_threshold: float,
    max_keep: int,
) -> list[T]:
    if not candidates or max_keep <= 0:
        return []

    iou_threshold = float(max(0.0, min(1.0, iou_threshold)))

    sorted_cands = sorted(candidates, key=lambda c: c.score, reverse=True)

    kept: list[T] = []
    for cand in sorted_cands:
        keep = True
        for other in kept:
            iou = time_iou(
                float(cand.start_seconds),
                float(cand.end_seconds),
                float(other.start_seconds),
                float(other.end_seconds),
            )
            if iou >= iou_threshold:
                keep = False
                break
        if keep:
            kept.append(cand)
            if len(kept) >= max_keep:
                break

    return kept
