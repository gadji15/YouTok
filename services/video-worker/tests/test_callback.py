from __future__ import annotations

import httpx

from video_worker.callback import ClipArtifact, JobArtifacts, JobCallbackPayload, JobStatus, post_callback


def test_post_callback_sends_header_and_json(monkeypatch) -> None:
    seen: dict = {}

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> httpx.Response:
        seen["url"] = url
        seen["json"] = json
        seen["headers"] = headers
        seen["timeout"] = timeout
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("video_worker.callback.httpx.post", fake_post)

    payload = JobCallbackPayload(
        job_id="job_1",
        project_id="proj_1",
        status=JobStatus.processing,
        stage="download",
        progress_percent=10,
        message="Downloading",
    )

    post_callback(
        callback_url="https://example.test/callback",
        callback_secret="secret",
        payload=payload,
        timeout_seconds=12.5,
    )

    assert seen["headers"]["X-Callback-Secret"] == "secret"
    assert seen["json"]["job_id"] == "job_1"
    assert seen["json"]["status"] == "processing"
    assert seen["json"]["stage"] == "download"
    assert seen["json"]["progress_percent"] == 10
    assert seen["json"]["message"] == "Downloading"
    assert "artifacts" not in seen["json"]
    assert "error" not in seen["json"]
    assert seen["timeout"] == 12.5


def test_job_callback_payload_model_dump_includes_progress_fields() -> None:
    payload = JobCallbackPayload(
        job_id="job_1",
        project_id="proj_1",
        status=JobStatus.processing,
        stage="transcribe",
        progress_percent=50,
        message="Transcribing audio",
    )

    data = payload.model_dump(mode="json")

    assert data["stage"] == "transcribe"
    assert data["progress_percent"] == 50
    assert data["message"] == "Transcribing audio"


def test_callback_payload_includes_clip_subtitles_srt_path() -> None:
    payload = JobCallbackPayload(
        job_id="job_1",
        project_id="proj_1",
        status=JobStatus.completed,
        artifacts=JobArtifacts(
            clips=[
                ClipArtifact(
                    clip_id="clip_001",
                    start_seconds=0.0,
                    end_seconds=10.0,
                    score=0.5,
                    title_candidates={
                        "provider": "heuristic",
                        "description": "Desc",
                        "hashtags": ["#fyp", "#viral", "#learnontiktok"],
                        "candidates": [
                            {"title": "Stop doing this", "score": 0.9},
                            {"title": "What if you did this?", "score": 0.7},
                        ],
                        "top3": ["Stop doing this", "What if you did this?"],
                    },
                    quality_summary={
                        "template": "cinematic_karaoke",
                        "ui_safe_ymin": 0.78,
                        "final_overlap": {"face_overlap_ratio_p95": 0.03, "ui_overlap_ratio_p95": 0.0},
                    },
                    video_path="/shared/clip_001/video.mp4",
                    subtitles_ass_path="/shared/clip_001/subtitles.ass",
                    subtitles_srt_path="/shared/clip_001/subtitles.srt",
                )
            ]
        ),
    )

    data = payload.model_dump(mode="json")

    assert data["artifacts"]["clips"][0]["subtitles_srt_path"] == "/shared/clip_001/subtitles.srt"
    assert data["artifacts"]["clips"][0]["title_candidates"]["provider"] == "heuristic"
