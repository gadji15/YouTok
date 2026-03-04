from __future__ import annotations

import json


def test_metrics_json_final_overlap_shape() -> None:
    # This is a unit-level shape test that mirrors what clip.py writes.
    raw = {"clip_id": "clip_001", "subtitles": {"enabled": True}}

    face95 = 0.03
    ui95 = 0.0

    raw.setdefault("subtitles", {}).setdefault("final_overlap", {})
    raw["subtitles"]["final_overlap"] = {
        "measured_on": "rendered_video",
        "sample_fps": 1,
        "face_overlap_ratio_p95": face95,
        "ui_overlap_ratio_p95": ui95,
    }

    s = json.dumps(raw)
    assert "final_overlap" in s
    assert raw["subtitles"]["final_overlap"]["measured_on"] == "rendered_video"
    assert 0.0 <= raw["subtitles"]["final_overlap"]["face_overlap_ratio_p95"] <= 1.0
    assert 0.0 <= raw["subtitles"]["final_overlap"]["ui_overlap_ratio_p95"] <= 1.0
