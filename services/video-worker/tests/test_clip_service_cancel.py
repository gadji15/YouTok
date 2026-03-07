from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

import video_worker.clip_service_api as clip_service_api


def test_clip_service_render_aborts_when_cancel_key_exists(monkeypatch, tmp_path: Path) -> None:
    # Ensure paths are accepted by _resolve_within_storage_root.
    monkeypatch.setattr(clip_service_api.clip_settings, "storage_path", str(tmp_path))

    class FakeRedis:
        def exists(self, _key: str) -> int:
            return 1

    monkeypatch.setattr(clip_service_api, "get_redis", lambda: FakeRedis())

    def fake_render_clips(*, cancel_check=None, **_kwargs):
        assert cancel_check is not None
        cancel_check()
        return []

    monkeypatch.setattr(clip_service_api, "render_clips", fake_render_clips)

    req = clip_service_api.RenderRequest(
        job_id="job_1",
        source_video_path=str((tmp_path / "src.mp4").resolve()),
        output_dir=str((tmp_path / "out").resolve()),
        clips=[
            {
                "clip_id": "clip_1",
                "start_seconds": 0.0,
                "end_seconds": 1.0,
                "score": 0.0,
                "reason": "baseline",
            }
        ],
        transcript_segments=[
            {
                "start_seconds": 0.0,
                "end_seconds": 1.0,
                "text": "hello",
            }
        ],
    )

    with pytest.raises(HTTPException) as exc:
        clip_service_api.render(req)

    assert exc.value.status_code == 409
    assert exc.value.detail == "cancelled"
