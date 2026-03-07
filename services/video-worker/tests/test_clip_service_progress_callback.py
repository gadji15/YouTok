from __future__ import annotations

from pathlib import Path

from video_worker.clip_service_api import RenderRequest, render


def test_clip_service_emits_progress_callbacks_when_callback_fields_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("video_worker.clip_service_api.clip_settings.storage_path", str(tmp_path), raising=False)

    seen: dict = {}

    def fake_post_callback(*, callback_url: str, callback_secret: str, payload, **_kwargs) -> None:
        seen["callback_url"] = callback_url
        seen["callback_secret"] = callback_secret
        seen["payload"] = payload

    monkeypatch.setattr("video_worker.clip_service_api.post_callback", fake_post_callback)

    def fake_render_clips(*, progress_callback=None, **_kwargs):
        assert progress_callback is not None
        progress_callback(
            {
                "event": "render.clip.progress",
                "clip_id": "clip_1",
                "index": 1,
                "total": 1,
                "progress": 0.5,
                "running_seconds": 12.0,
            }
        )
        return []

    monkeypatch.setattr("video_worker.clip_service_api.render_clips", fake_render_clips)
    monkeypatch.setattr("video_worker.clip_service_api.time.time", lambda: 100.0)

    req = RenderRequest(
        job_id="job_1",
        project_id="proj_1",
        callback_url="https://example.test/callback",
        callback_secret="secret",
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

    render(req)

    assert seen["callback_url"] == "https://example.test/callback"
    assert seen["callback_secret"] == "secret"
    assert seen["payload"].stage == "render_clips"
    assert seen["payload"].progress_percent == 94
    assert seen["payload"].message.startswith("Rendering clip 1/1 (clip_1) — 50%")
