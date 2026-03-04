from __future__ import annotations

from video_worker.pipeline.subtitle_placement import _p95, _rect_area, _rect_inter_area


def test_p95_empty() -> None:
    assert _p95([]) == 0.0


def test_p95_basic() -> None:
    assert _p95([0.0, 1.0]) in {0.0, 1.0}
    assert _p95([0.0, 0.1, 0.2, 0.3, 1.0]) >= 0.2


def test_rect_inter_area() -> None:
    a = (0.0, 0.0, 1.0, 1.0)
    b = (0.5, 0.5, 1.5, 1.5)
    assert _rect_area(a) == 1.0
    assert _rect_area(b) == 1.0
    assert _rect_inter_area(a, b) == 0.25
