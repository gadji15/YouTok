from __future__ import annotations

from video_worker.pipeline.text_aware_crop import OneEuroFilter, pad_and_fix_ratio, union_boxes


def test_union_boxes() -> None:
    b = union_boxes([(10, 20, 30, 40), (5, 15, 35, 38)])
    assert b == (5, 15, 35, 40)


def test_pad_and_fix_ratio_stays_within_bounds_and_aspect() -> None:
    # 16:9 source
    frame_w = 1920
    frame_h = 1080

    # detected text box
    box = (1200, 200, 1500, 280)

    x0, y0, x1, y1 = pad_and_fix_ratio(
        box=box,
        frame_w=frame_w,
        frame_h=frame_h,
        out_w=1080,
        out_h=1920,
        pad_ratio=0.2,
    )

    assert 0 <= x0 < x1 <= frame_w
    assert 0 <= y0 < y1 <= frame_h

    w = x1 - x0
    h = y1 - y0

    ar = float(w) / float(h)
    target_ar = 1080.0 / 1920.0
    assert abs(ar - target_ar) < 0.04


def test_one_euro_filter_constant_signal() -> None:
    f = OneEuroFilter(freq=30.0, min_cutoff=1.0, beta=0.0)

    ys = [f.apply(10.0) for _ in range(60)]
    assert all(abs(y - 10.0) < 1e-9 for y in ys)
