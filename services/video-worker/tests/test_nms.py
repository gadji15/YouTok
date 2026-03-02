from __future__ import annotations

from dataclasses import dataclass

from video_worker.pipeline.nms import non_max_suppression, time_iou


@dataclass(frozen=True)
class Cand:
    start_seconds: float
    end_seconds: float
    score: float


def test_time_iou() -> None:
    assert time_iou(0.0, 10.0, 0.0, 10.0) == 1.0
    assert time_iou(0.0, 10.0, 10.0, 20.0) == 0.0
    assert 0.0 < time_iou(0.0, 10.0, 5.0, 15.0) < 1.0


def test_non_max_suppression_prefers_high_score() -> None:
    c1 = Cand(0.0, 10.0, 0.9)
    c2 = Cand(2.0, 9.0, 0.8)  # heavily overlaps c1
    c3 = Cand(12.0, 20.0, 0.7)

    kept = non_max_suppression(candidates=[c2, c3, c1], iou_threshold=0.3, max_keep=10)

    assert kept[0] == c1
    assert c2 not in kept
    assert c3 in kept
