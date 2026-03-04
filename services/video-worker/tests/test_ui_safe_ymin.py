from __future__ import annotations

from video_worker.pipeline.subtitle_placement import _rect_area, _rect_inter_area


def test_ui_safe_zone_overlap_changes_with_ymin() -> None:
    # Subtitle box fixed at bottom area.
    sub = (0.08, 0.80, 0.92, 0.94)
    sub_area = _rect_area(sub)
    assert sub_area > 0

    ui_lo = (0.0, 0.78, 1.0, 1.0)
    ui_hi = (0.0, 0.90, 1.0, 1.0)

    ov_lo = _rect_inter_area(sub, ui_lo) / sub_area
    ov_hi = _rect_inter_area(sub, ui_hi) / sub_area

    # Higher ymin means smaller UI zone => lower overlap.
    assert ov_hi <= ov_lo
